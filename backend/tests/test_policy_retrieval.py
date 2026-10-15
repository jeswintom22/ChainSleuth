"""Policy evidence retrieval: GraphRAG path, fallback path and explicit 'unavailable' reporting."""
from app.graphrag import client as gr
from app.graphrag import fallback
from app.graphrag.retriever import policy_question_for, retrieve_policy


def test_fallback_sections_keep_provenance():
    secs = fallback.load_sections()
    assert {s["document_id"] for s in secs} == {"PP-100", "DS-210", "SO-050", "WR-300", "IR-2025-Q4-07"}
    assert all(s["chunk_id"].startswith(s["document_id"] + "#") and s["text"] for s in secs)


def test_fallback_finds_rule_relevant_policy():
    top = fallback.retrieve(policy_question_for("R3_RECONCILIATION", "quantity_mismatch"), k=3)
    assert ("PP-100", "Quantity Tolerance") in {(c["document_id"], c["section"]) for c in top}
    top = fallback.retrieve(policy_question_for("R4_ROUTE_ANOMALY"), k=1)
    assert top[0]["document_id"] == "WR-300"


def test_retriever_uses_fallback_when_graphrag_unavailable(monkeypatch):
    monkeypatch.setattr(gr, "is_available", lambda: False)
    monkeypatch.setattr(gr, "unavailable_reason", lambda: "test: not ingested")
    res = retrieve_policy("duplicate invoice")
    assert res["status"] == "fallback" and res["chunks"] and "test: not ingested" in res["detail"]


def test_retriever_survives_graphrag_exception(monkeypatch):
    monkeypatch.setattr(gr, "is_available", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("SDK exploded")

    monkeypatch.setattr(gr, "retrieve_evidence", boom)
    res = retrieve_policy("shared payout account")
    assert res["status"] == "fallback" and "SDK exploded" in res["detail"]


def test_retriever_reports_unavailable_when_nothing_matches(monkeypatch):
    monkeypatch.setattr(gr, "is_available", lambda: False)
    res = retrieve_policy("zzzz qqqq xxyyzz")
    assert res == {"status": "unavailable", "chunks": [], "detail": res["detail"]}
    assert "no matching document evidence" in res["detail"]


def test_graphrag_preferred_when_available(monkeypatch):
    chunk = {"chunk_id": "graphrag:c1", "document_id": "PP-100", "section": "Quantity Tolerance", "text": "t",
             "source": "data/policies/procurement_policy.md", "method": "graphrag_sdk"}
    monkeypatch.setattr(gr, "is_available", lambda: True)
    monkeypatch.setattr(gr, "retrieve_evidence", lambda q, k=2: [chunk])
    assert retrieve_policy("anything") == {"status": "graphrag", "chunks": [chunk], "detail": "GraphRAG SDK retrieval"}
