"""Ingest the synthetic policy documents with the GraphRAG SDK.

Usage (from backend/):  python -m app.graphrag.ingest_documents [--reset]
"""
import asyncio
import json
import sys

from app.config import settings
from app.graphrag.client import ingest_documents, reset_docs_graph

if __name__ == "__main__":
    if not settings.openai_api_key:
        sys.exit("OPENAI_API_KEY is required for GraphRAG ingestion (extraction + embeddings).")
    if "--reset" in sys.argv:
        reset_docs_graph()
    print(json.dumps(asyncio.run(ingest_documents()), indent=2, default=str))
