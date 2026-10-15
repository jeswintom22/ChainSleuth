"""Phase F gate: isolated GraphRAG SDK ingestion + evidence retrieval on the pinned versions.

Requires OPENAI_API_KEY (real extraction and embedding calls). Uses its own graph and deletes it.
"""
import importlib.metadata

import pytest

from app.config import settings
from app.graph.client import get_graph, read

pytestmark = pytest.mark.llm
GATE_GRAPH = "chainsleuth_docs_gate_test"


def test_pinned_sdk_version():
    assert importlib.metadata.version("graphrag-sdk") == "1.3.0"
    assert importlib.metadata.version("falkordb") == "1.7.1"


@pytest.fixture(scope="module")
def ingested():
    if not settings.openai_api_key:
        pytest.skip("OPENAI_API_KEY not configured")
    import asyncio

    from app.graphrag.client import ingest_documents, reset_docs_graph

    reset_docs_graph(GATE_GRAPH)
    result = asyncio.run(ingest_documents(GATE_GRAPH, [settings.policies_dir / "procurement_policy.md"]))
    yield result
    reset_docs_graph(GATE_GRAPH)


def test_ingestion_creates_document_chunks_and_entities(ingested):
    g = get_graph(GATE_GRAPH)
    assert ingested["documents"]["procurement_policy.md"]["chunks"] == 6  # title block + one chunk per section
    docs = read("MATCH (d:Document) RETURN d.path AS path", graph=g)
    assert [d["path"].replace("\\", "/") for d in docs] == ["data/policies/procurement_policy.md"]
    assert read("MATCH (:Document)-[:PART_OF]-(c:Chunk) RETURN count(c) AS n", graph=g)[0]["n"] > 0
    assert read("MATCH (e:__Entity__) RETURN count(e) AS n", graph=g)[0]["n"] > 0


def test_retrieval_returns_source_attributed_evidence(ingested):
    from app.graphrag.client import retrieve_evidence

    chunks = retrieve_evidence("What quantity tolerance applies when billed quantity exceeds delivered quantity?",
                               k=3, graph_name=GATE_GRAPH)
    assert chunks, "no provenance-verified passages returned"
    assert all(c["document_id"] == "PP-100" and c["method"] == "graphrag_sdk" for c in chunks)
    tol = [c for c in chunks if "2 percent" in c["text"]]
    assert tol and tol[0]["section"] == "Quantity Tolerance"


def test_operational_graph_untouched_by_sdk(ingested, loaded_graph):
    # The SDK writes only to its own graph; the operational test graph has no SDK labels.
    labels = {r["l"] for r in read("MATCH (n) UNWIND labels(n) AS l RETURN DISTINCT l")}
    assert not labels & {"Document", "Chunk", "__Entity__"}
