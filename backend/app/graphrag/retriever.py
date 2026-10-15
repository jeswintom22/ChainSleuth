"""Unified policy-evidence retrieval: GraphRAG SDK first, limited direct retrieval as fallback.

Always returns an explicit status so the UI and explanations can say when document evidence is
unavailable instead of silently omitting it.
"""
from __future__ import annotations

import logging

from app.graphrag import fallback

log = logging.getLogger(__name__)

# Per-rule retrieval questions (fixed, reviewed) used to attach policy context to findings.
RULE_POLICY_QUESTIONS = {
    "R1_SHARED_ACCOUNT": "bank account used by more than one supplier record shared payout account review intermediary",
    "R2_DUPLICATE_INVOICE": "duplicate invoice same invoice number amount date line items held reviewed",
    "R3_RECONCILIATION": "billed quantity delivered quantity tolerance purchase order delivery evidence three-way match",
    "R4_ROUTE_ANOMALY": "route deviation transfer not in approved warehouse network",
}
CATEGORY_POLICY_QUESTIONS = {
    "unit_mismatch": "units of measure invoice line different unit box each",
    "missing_shipment_evidence": "no delivered shipment line missing receipt evidence cancelled",
    "unresolved_purchase_order_link": "invoices cannot be linked to a purchase order exceptions queue",
}


def policy_question_for(rule_id: str, category: str | None = None) -> str:
    return CATEGORY_POLICY_QUESTIONS.get(category or "", RULE_POLICY_QUESTIONS[rule_id])


def retrieve_policy(question: str, k: int = 2) -> dict:
    """Returns {"status": "graphrag"|"fallback"|"unavailable", "chunks": [...], "detail": str}."""
    try:
        from app.graphrag import client as gr

        if gr.is_available():
            chunks = gr.retrieve_evidence(question, k=k)
            if chunks:
                return {"status": "graphrag", "chunks": chunks, "detail": "GraphRAG SDK retrieval"}
            detail = "GraphRAG returned no source-attributed passages"
        else:
            detail = gr.unavailable_reason()
    except Exception as e:  # SDK failure must never break the core investigation
        log.warning("GraphRAG retrieval failed: %s", e)
        detail = f"GraphRAG error: {type(e).__name__}: {e}"
    chunks = fallback.retrieve(question, k=k)
    if chunks:
        return {"status": "fallback", "chunks": chunks, "detail": f"{detail}; used direct document retrieval"}
    return {"status": "unavailable", "chunks": [], "detail": f"{detail}; no matching document evidence"}
