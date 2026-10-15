"""Unsupported explanation claims are detected and never persisted (Phase H)."""
import pytest

from app.agent import explain, grounding
from app.agent.tools import call_tool

PACK = {
    "investigation_id": "INVG-TEST0001", "target": {"id": "INV-1043", "label": "Invoice"},
    "score": {"score": 100, "score_cap": 100, "severity": "critical", "finding_count": 1, "breakdown": []},
    "findings": [{"finding_id": "F-8d0c29d5e986", "rule_id": "R3_RECONCILIATION", "rule_version": "1.0.0",
                  "category": "quantity_mismatch", "status": "open", "points": 25,
                  "summary": "INV-1043 billed 100 each of PRD-007 on PO-5043; 100 ordered and 60 delivered",
                  "values": {"billed_quantity": 100, "delivered_quantity": 60, "excess_over_delivered": 40, "amount": 1250.0},
                  "record_ids": {"Invoice": ["INV-1043"], "Shipment": ["SHP-7043"]},
                  "evidence_paths": ["(PurchaseOrder PO-5043)-[:FULFILLED_BY]->(Shipment SHP-7043)"]}],
    "policy_status": "fallback",
    "policy_evidence": [{"chunk_id": "PP-100#quantity-tolerance", "document_id": "PP-100", "section": "Quantity Tolerance",
                         "text": "no more than 2 percent"}],
}


def test_supported_text_passes():
    text = ("INV-1043 billed 100 units of PRD-007 but SHP-7043 delivered 60, an excess of 40 (1,250.00 USD). "
            "PP-100 allows at most 2 percent. Finding F-8d0c29d5e986 is recommended for human review.")
    r = grounding.validate(text, PACK)
    assert r["supported"], r


@pytest.mark.parametrize("text,field,bad", [
    ("INV-1043 relates to INV-9999.", "unsupported_ids", ["INV-9999"]),
    ("SUP-777 shares an account.", "unsupported_ids", ["SUP-777"]),
    ("INV-1043 billed 120 units.", "unsupported_numbers", [120.0]),
    ("The excess is 45 units.", "unsupported_numbers", [45.0]),
    ("The total is 1,300.00 USD.", "unsupported_numbers", [1300.0]),
    ("This is clearly fraudulent.", "banned_phrases", ["fraudulent"]),
    ("This proves collusion.", "banned_phrases", ["proves"]),
    ("We blocked the payment.", "banned_phrases", ["blocked the payment"]),
])
def test_unsupported_claims_detected(text, field, bad):
    r = grounding.validate(text, PACK)
    assert not r["supported"] and r[field] == bad


def test_dates_list_markers_and_versions_not_flagged():
    r = grounding.validate("1. On 2026-02-04 rule R3_RECONCILIATION v1.0.0 flagged INV-1043.", PACK)
    assert r["supported"], r


def test_deterministic_explanation_is_grounded_and_disclaimed():
    out = explain.generate_explanation(PACK, use_llm=False)
    assert out["mode"] == "deterministic" and out["grounding"]["supported"]
    assert explain.DISCLAIMER in out["text"] and "fraud" not in out["text"].lower()


def test_ungrounded_llm_output_is_rejected(monkeypatch):
    """A hallucinating model (invented ID and quantity) is rejected twice, then the deterministic text is used."""
    calls = []

    def fake_chat(messages, tools=None):
        calls.append(messages)
        return {"content": "INV-1043 billed 150 units and is linked to SUP-999.", "tool_calls": []}

    monkeypatch.setattr(explain, "chat", fake_chat)
    out = explain.generate_explanation(PACK, use_llm=True)
    assert len(calls) == 2 and out["mode"] == "deterministic_fallback"
    assert [a["unsupported_ids"] for a in out["grounding"]["rejected_attempts"]] == [["SUP-999"], ["SUP-999"]]
    assert "SUP-999" not in out["text"] and "150" not in out["text"]


def test_grounded_llm_output_is_accepted(monkeypatch):
    monkeypatch.setattr(explain, "chat", lambda m, tools=None: {
        "content": "INV-1043 billed 100 units; 60 were delivered (PP-100, Quantity Tolerance). Recommend human review.",
        "tool_calls": []})
    out = explain.generate_explanation(PACK, use_llm=True)
    assert out["mode"] == "llm_grounded" and out["text"].endswith(explain.DISCLAIMER)


@pytest.mark.parametrize("name,args,exc", [
    ("run_cypher", {"query": "MATCH (n) DETACH DELETE n"}, ValueError),
    ("check_shared_accounts", {"supplier_id": "SUP-010' OR 1=1"}, ValueError),
    ("check_shared_accounts", {"supplier_id": "SUP-010", "extra": "x"}, ValueError),
    ("reconcile_invoice", {}, ValueError),
    ("open_investigation", {"entity_id": "INV-1043", "question": "q"}, PermissionError),
])
def test_agent_tools_reject_invalid_calls(name, args, exc):
    with pytest.raises(exc):
        call_tool(name, args, allow_writes=False)
