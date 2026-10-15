"""Limited direct document retrieval used when the GraphRAG SDK path is unavailable.

Splits the synthetic policy markdown files into heading-level sections and ranks them by TF-IDF
term overlap. Deterministic, offline, and every passage keeps its document and section provenance.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from app.config import settings

TOKEN = re.compile(r"[a-z0-9]+")
STOP = set("a an and are as at be by for from has have if in is it its may must no not of on or per such that the "
           "their there this to was were which with without".split())


def _tokens(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP and len(t) > 1]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


@lru_cache(maxsize=1)
def load_sections(policies_dir: str | None = None) -> tuple[dict, ...]:
    sections = []
    for path in sorted(Path(policies_dir or settings.policies_dir).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ").strip()
        m = re.search(r"Document ID:\s*([A-Z0-9-]+)", text)
        doc_id = m.group(1) if m else path.stem
        for block in re.split(r"\n(?=## )", text)[1:]:
            heading, _, body = block.partition("\n")
            heading = heading.lstrip("# ").strip()
            sections.append({"chunk_id": f"{doc_id}#{_slug(heading)}", "document_id": doc_id, "title": title,
                             "section": heading, "text": body.strip(), "source": path.name})
    return tuple(sections)


def retrieve(question: str, k: int = 3) -> list[dict]:
    sections = load_sections()
    docs = [Counter(_tokens(s["section"] + " " + s["section"] + " " + s["text"])) for s in sections]
    df = Counter(t for d in docs for t in d)
    q = set(_tokens(question))
    scored = []
    for s, d in zip(sections, docs):
        score = sum((1 + math.log(d[t])) * math.log(1 + len(docs) / df[t]) for t in q if d[t])
        if score > 0:
            scored.append({**s, "score": round(score, 3), "method": "direct_keyword_fallback"})
    return sorted(scored, key=lambda x: (-x["score"], x["chunk_id"]))[:k]
