"""Evidence pack: the complete, structured set of graph records an explanation may draw on."""
from __future__ import annotations

from app.scoring import SCORE_CAP

MAIN_LABELS = ["Supplier", "Invoice", "PurchaseOrder", "Shipment", "BankAccount", "Owner", "Product", "Warehouse"]


def build_evidence_pack(inv: dict, policy: list[dict] | None = None, policy_status: str | None = None,
                        agent_context: list[dict] | None = None) -> dict:
    policy = policy if policy is not None else inv.get("policy_evidence", [])
    return {
        "investigation_id": inv["investigation_id"],
        "question": inv["question"],
        "target": {"id": inv["target_id"], "label": inv["target_label"]},
        "suppliers_in_scope": inv["scope"].get("suppliers", []),
        "score": {"score": inv["score"], "score_cap": SCORE_CAP, "severity": inv["severity"],
                  "finding_count": len(inv["findings"]), "breakdown": inv["score_detail"].get("breakdown", [])},
        "findings": [{
            "finding_id": f["finding_id"], "rule_id": f["rule_id"], "rule_version": f["rule_version"],
            "category": f["category"], "status": f["status"], "points": f["score"],
            "summary": f["evidence_summary"], "values": f["values"],
            "record_ids": {k: v for k, v in f["record_ids"].items() if k in MAIN_LABELS and v},
            "evidence_paths": f["evidence_paths"],
        } for f in inv["findings"]],
        "policy_status": policy_status or inv.get("policy_status", "not_requested"),
        "policy_evidence": [{k: c.get(k) for k in ("chunk_id", "document_id", "section", "text", "finding_ids", "method")}
                            for c in policy],
        "agent_context": agent_context or [],
    }
