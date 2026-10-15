"""R2: exact duplicate invoices by normalized fingerprint (computed deterministically at ingestion)."""
from __future__ import annotations

from app.detection.base import RULES, Signal
from app.graph.queries import run_named

RULE = RULES["R2_DUPLICATE_INVOICE"]


def detect_duplicate_invoices(invoice_id: str | None = None) -> list[Signal]:
    signals = []
    for r in run_named("duplicate_invoices", invoice_id=invoice_id):
        a, b = r["invoice_a"], r["invoice_b"]
        same_supplier = r["supplier_a"] == r["supplier_b"]
        paths = [f"(Supplier {r['supplier_a']})-[:SUBMITTED]->(Invoice {a}) "
                 f"fingerprint={r['fingerprint']} (Invoice {b})<-[:SUBMITTED]-(Supplier {r['supplier_b']})"]
        paths += [f"(Supplier {r['supplier_a']})-[:USES_ACCOUNT]->(BankAccount {acc})<-[:USES_ACCOUNT]-(Supplier {r['supplier_b']})"
                  for acc in r["shared_accounts"]]
        who = f"supplier {r['supplier_a']}" if same_supplier else f"suppliers {r['supplier_a']} and {r['supplier_b']}"
        signals.append(Signal(
            rule_id=RULE.rule_id, subject_key=f"{a}|{b}", category="exact_duplicate", points=RULE.config["points"],
            summary=(f"Invoices {a} and {b} from {who} have identical fingerprints "
                     f"(number {r['invoice_number']}, {r['amount']:.2f} {r['currency']}, dated {r['invoice_date']})"),
            values={"invoice_a": a, "invoice_b": b, "supplier_a": r["supplier_a"], "supplier_b": r["supplier_b"],
                    "invoice_number": r["invoice_number"], "amount": r["amount"], "currency": r["currency"],
                    "invoice_date": r["invoice_date"], "fingerprint": r["fingerprint"],
                    "same_supplier": same_supplier, "shared_accounts": r["shared_accounts"],
                    "status_a": r["status_a"], "status_b": r["status_b"]},
            record_ids={"Invoice": [a, b], "Supplier": sorted({r["supplier_a"], r["supplier_b"]}),
                        "BankAccount": r["shared_accounts"]},
            evidence_paths=paths,
            query={"name": "duplicate_invoices", "params": {"invoice_id": invoice_id}},
        ))
    return signals
