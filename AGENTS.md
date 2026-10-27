# Notes for coding agents working on ChainSleuth

## Environment
- FalkorDB: `docker compose up -d` (image pinned to `falkordb/falkordb:v4.22.0`; **do not** move to 6.x while `graphrag-sdk` 1.3.0 is used, because its full-text index call fails on 6.x).
- Backend venv: `backend/.venv` (Python 3.10). Install with `pip install -r requirements.lock.txt`, then `pip install --no-deps -r requirements-graphrag.txt`.
- Secrets: `backend/.env` (gitignored). A key in `.env` wins over the shell environment, and placeholder values are treated as "not set".
- Resolve new dependencies with a publication cutoff of at least 7 days (`pip --uploaded-prior-to`, `npm install --before=`). Check `npm view <pkg> time` yourself, because `npm view --before` does not filter.

## Commands (run from `backend/` unless noted)
- Tests: `.venv/Scripts/python -m pytest -q` (85 tests; uses graphs `chainsleuth_test` and `chainsleuth_docs_gate_test`; tests marked `llm` skip when there is no key).
- Generate data: `python -m data.generate_synthetic`. Load it: `python -m app.graph.ingest --reset`.
- GraphRAG documents: `python -m app.graphrag.ingest_documents --reset` (deletes the `chainsleuth_docs` and `chainsleuth_docs__ontology` graphs first).
- Evaluation: `CHAINSLEUTH_GRAPH=chainsleuth_eval python -m app.evaluate` (refuses to run against the demo graph).
- API: `uvicorn app.main:app --port 8000`. UI: `cd frontend && npm run dev` (port 3001, proxies `/api` to 8000).
- Frontend typecheck: `cd frontend && npx tsc --noEmit`.

## Conventions
- All detection and investigation Cypher goes in `app/graph/queries.py` (named, parameterized, read-only), and write Cypher goes in `app/investigations/repository.py`. Never execute LLM-generated Cypher.
- Two-sided pattern queries must exclude self-matches (FalkorDB binds the same edge twice). Keep a `WITH` barrier between a filtered `MATCH` and a filtered `OPTIONAL MATCH`.
- Rule changes require bumping `Rule.version` in `app/detection/base.py`.
- Never describe findings as fraud or proof. LLM output must pass `app/agent/grounding.py`.
