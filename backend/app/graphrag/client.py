"""GraphRAG SDK (graphrag-sdk==1.3.0) integration for synthetic policy documents.

Responsibilities:
  * ingest the markdown policy documents into a dedicated FalkorDB graph with an explicit ontology;
  * retrieve passages for a question and VERIFY provenance: a passage is returned only if its exact
    text exists as a Chunk node linked by PART_OF to the Document it claims as its source.
The SDK is never used for transaction data, and it never writes to the operational graph.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import threading
from functools import lru_cache
from pathlib import Path

from app.config import BACKEND_DIR, settings
from app.graph.client import get_graph, read
from app.graphrag import fallback

log = logging.getLogger(__name__)
SOURCE_RE = re.compile(r"^\[Source: (?P<path>[^\]]+)\]\n(?P<text>.*)$", re.DOTALL)


def _rag(graph_name: str | None = None):
    from graphrag_sdk import ConnectionConfig, GraphRAG, LiteLLM, LiteLLMEmbedder

    from app.graphrag.ontology import POLICY_ONTOLOGY

    key = settings.openai_api_key
    return GraphRAG(
        connection=ConnectionConfig(host=settings.falkordb_host, port=settings.falkordb_port,
                                    password=settings.falkordb_password,
                                    graph_name=graph_name or settings.docs_graph_name, query_timeout_ms=30_000),
        llm=LiteLLM(model=settings.llm_model, api_key=key, temperature=0.0),
        embedder=LiteLLMEmbedder(model=settings.embedding_model, api_key=key, dimensions=settings.embedding_dim),
        ontology=POLICY_ONTOLOGY,
        embedding_dimension=settings.embedding_dim,
    )


def _doc_count(graph_name: str | None = None) -> int:
    try:
        return read("MATCH (d:Document) RETURN count(d) AS n", graph=get_graph(graph_name or settings.docs_graph_name))[0]["n"]
    except Exception:
        return 0


def is_available() -> bool:
    return (os.getenv("CHAINSLEUTH_DISABLE_GRAPHRAG") != "1" and bool(settings.openai_api_key) and _doc_count() > 0)


def unavailable_reason() -> str:
    if os.getenv("CHAINSLEUTH_DISABLE_GRAPHRAG") == "1":
        return "GraphRAG disabled by configuration"
    if not settings.openai_api_key:
        return "GraphRAG unavailable: no OPENAI_API_KEY configured"
    if _doc_count() == 0:
        return "GraphRAG unavailable: policy documents not ingested (python -m app.graphrag.ingest_documents)"
    return "GraphRAG available"


def reset_docs_graph(graph_name: str | None = None) -> None:
    """Delete the document graph AND the SDK's companion ontology graph (`<name>__ontology`)."""
    name = graph_name or settings.docs_graph_name
    for g in (name, f"{name}__ontology"):
        try:
            get_graph(g).delete()
        except Exception:
            pass  # graph did not exist


def _rel(path: Path) -> str:
    return path.resolve().relative_to(BACKEND_DIR).as_posix()


def split_sections(text: str) -> list[str]:
    """One chunk per markdown heading section, so each Chunk maps to exactly one policy section."""
    parts = [p.strip() for p in re.split(r"\n(?=#{1,6} )", text) if p.strip()]
    return parts if len(parts) > 1 else [p.strip() for p in text.split("\n\n") if p.strip()]


async def ingest_documents(graph_name: str | None = None, paths: list[Path] | None = None) -> dict:
    from graphrag_sdk import CallableChunking, GraphExtraction, LLMExtractor

    from app.graphrag.ontology import POLICY_ONTOLOGY

    paths = paths or sorted(settings.policies_dir.glob("*.md"))
    results = {}
    async with _rag(graph_name) as rag:
        # LLM-only entity extraction (the default extractor first tries GLiNER, which is not installed).
        extractor = GraphExtraction(rag.llm, entity_extractor=LLMExtractor(rag.llm),
                                    entity_types=[e.label for e in POLICY_ONTOLOGY.entities])
        chunker = CallableChunking(split_sections, strategy_name="markdown_sections")
        for p in paths:
            r = await rag.ingest(_rel(p), extractor=extractor, chunker=chunker)
            results[p.name] = {"nodes": r.nodes_created, "relationships": r.relationships_created, "chunks": r.chunks_indexed}
        fin = await rag.finalize()
    return {"documents": results, "finalize": fin.model_dump() if hasattr(fin, "model_dump") else dict(fin)}


def _section_for(source_name: str, text: str) -> tuple[str, str]:
    """Map a verified chunk back to the policy's document ID and heading section."""
    sections = [s for s in fallback.load_sections() if s["source"] == source_name]
    heading = re.match(r"#{1,6}\s+(.+)", text.strip())
    for s in sections:
        if heading and heading.group(1).strip() == s["section"]:
            return s["document_id"], s["section"]
    probe = re.sub(r"^#{1,6}\s+.+\n", "", text.strip())[:80]
    for s in sections:
        if probe and probe in s["text"]:
            return s["document_id"], s["section"]
    best = max(sections, key=lambda s: len(set(s["text"].split()) & set(text.split())), default=None)
    return (best["document_id"], best["section"]) if best else (Path(source_name).stem, "")


_LOOP: asyncio.AbstractEventLoop | None = None
_LOOP_LOCK = threading.Lock()
_RAGS: dict[str, object] = {}


def _run(coro):
    """Run a coroutine on one long-lived background loop. Reusing the loop (and the GraphRAG instance)
    avoids per-call asyncio.run() teardown, which leaks 'Event loop is closed' errors from open SSL
    transports on Windows, and keeps the SDK's connection pool warm."""
    global _LOOP
    with _LOOP_LOCK:
        if _LOOP is None:
            _LOOP = asyncio.new_event_loop()
            threading.Thread(target=_LOOP.run_forever, name="graphrag-loop", daemon=True).start()
    return asyncio.run_coroutine_threadsafe(coro, _LOOP).result(timeout=120)


async def _retrieve_async(question: str, graph_name: str) -> list[dict]:
    if graph_name not in _RAGS:
        rag = _rag(graph_name)
        await rag.__aenter__()  # same setup as `async with`, kept open for the process lifetime
        _RAGS[graph_name] = rag
    res = await _RAGS[graph_name].retrieve(question)
    passages = [i.content for i in res.items if i.metadata.get("section") == "passages"]
    if not passages:
        return []
    body = passages[0].split("\n", 1)[1] if passages[0].startswith("## ") else passages[0]
    return [m.groupdict() for p in body.split("\n---\n") if (m := SOURCE_RE.match(p.strip()))]


@lru_cache(maxsize=128)
def _retrieve_cached(question: str, graph_name: str) -> tuple:
    return tuple(tuple(sorted(d.items())) for d in _run(_retrieve_async(question, graph_name)))


def retrieve_evidence(question: str, k: int = 2, graph_name: str | None = None) -> list[dict]:
    graph_name = graph_name or settings.docs_graph_name
    out = []
    for item in _retrieve_cached(question, graph_name):
        p = dict(item)
        # Provenance gate: the passage must be a stored Chunk of the Document it cites.
        rows = read("""MATCH (d:Document)-[:PART_OF]-(c:Chunk) WHERE c.text = $t AND d.path = $path
                       RETURN c.id AS chunk_id, d.path AS path LIMIT 1""",
                    {"t": p["text"], "path": p["path"]}, graph=get_graph(graph_name))
        if not rows:
            log.warning("Dropping GraphRAG passage without verifiable provenance (source %s)", p["path"])
            continue
        doc_id, section = _section_for(re.split(r"[\\/]", rows[0]["path"])[-1], p["text"])
        out.append({"chunk_id": f"graphrag:{rows[0]['chunk_id']}", "document_id": doc_id, "section": section,
                    "text": p["text"].strip(), "source": rows[0]["path"], "method": "graphrag_sdk"})
        if len(out) >= k:
            break
    return out
