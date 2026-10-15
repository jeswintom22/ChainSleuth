"""Shared types and the versioned detection-rule registry."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Rule:
    rule_id: str
    version: str
    title: str
    description: str
    query_names: tuple[str, ...]
    config: dict[str, Any]

    @property
    def rule_key(self) -> str:
        return f"{self.rule_id}@{self.version}"


RULES: dict[str, Rule] = {
    r.rule_id: r
    for r in [
        Rule("R1_SHARED_ACCOUNT", "1.0.0", "Shared payout account",
             "Two or more supplier records pay out to the same bank account. Accounts flagged as registered "
             "payment intermediaries (e.g. factoring agents) are excluded.",
             ("shared_accounts",),
             {"points": 20, "corroboration_points": 15, "exclude_registered_intermediaries": True}),
        Rule("R2_DUPLICATE_INVOICE", "1.0.0", "Exact duplicate invoice",
             "Two invoices share the same normalized fingerprint (invoice number, amount, currency, date, lines).",
             ("duplicate_invoices",), {"points": 30}),
        Rule("R3_RECONCILIATION", "1.0.0", "Invoice / order / delivery reconciliation",
             "Per purchase order and product, billed quantity is compared with ordered quantity and with "
             "delivered (non-cancelled) shipment quantity, in compatible units.",
             ("recon_billed_lines", "recon_ordered_lines", "recon_shipped_lines", "unlinked_invoices"),
             {"tolerance_pct": 2.0,
              "points": {"quantity_mismatch": 25, "missing_shipment_evidence": 15, "unit_mismatch": 10,
                         "unresolved_purchase_order_link": 10}}),
        Rule("R4_ROUTE_ANOMALY", "1.0.0", "Unapproved warehouse transition",
             "Consecutive shipment route stops whose transition is not in the approved warehouse network.",
             ("route_deviations",), {"points": 15}),
    ]
}


@dataclass
class Signal:
    """A deterministic rule hit. All values come from graph records or arithmetic over them."""
    rule_id: str
    subject_key: str
    category: str
    points: int
    summary: str
    values: dict[str, Any]
    record_ids: dict[str, list[str]]
    evidence_paths: list[str]
    query: dict[str, Any] = field(default_factory=dict)

    @property
    def rule(self) -> Rule:
        return RULES[self.rule_id]
