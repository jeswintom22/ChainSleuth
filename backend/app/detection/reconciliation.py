"""R3: product-level reconciliation of invoice lines, PO lines and delivered shipment lines.

FalkorDB performs the traversals (Invoice->Line->Product, PO->Line->Product, PO->Shipment->Line->Product);
the arithmetic below is plain, deterministic Python so it can be unit-tested in isolation.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from app.detection.base import RULES, Signal
from app.graph.queries import run_named

RULE = RULES["R3_RECONCILIATION"]


@dataclass
class ProductLedger:
    po_id: str
    product_id: str
    supplier_id: str | None = None
    billed: int = 0
    ordered: int = 0
    delivered: int = 0
    in_transit: int = 0
    cancelled: int = 0
    billed_units: set = field(default_factory=set)
    ordered_units: set = field(default_factory=set)
    delivered_units: set = field(default_factory=set)
    invoice_ids: set = field(default_factory=set)
    invoice_line_ids: list = field(default_factory=list)
    po_line_ids: list = field(default_factory=list)
    shipment_ids: set = field(default_factory=set)
    shipment_line_ids: list = field(default_factory=list)


def build_ledgers(billed: list[dict], ordered: list[dict], shipped: list[dict]) -> dict[tuple, ProductLedger]:
    ledgers: dict[tuple, ProductLedger] = {}

    def get(po, prod):
        return ledgers.setdefault((po, prod), ProductLedger(po, prod))

    for r in billed:
        lg = get(r["po_id"], r["product_id"])
        lg.supplier_id = r["supplier_id"]
        lg.billed += r["quantity"]
        lg.billed_units.add(r["unit"])
        lg.invoice_ids.add(r["invoice_id"])
        lg.invoice_line_ids.append(r["line_id"])
    for r in ordered:
        lg = get(r["po_id"], r["product_id"])
        lg.ordered += r["quantity"]
        lg.ordered_units.add(r["unit"])
        lg.po_line_ids.append(r["po_line_id"])
    for r in shipped:
        lg = get(r["po_id"], r["product_id"])
        lg.shipment_ids.add(r["shipment_id"])
        lg.shipment_line_ids.append(r["shipment_line_id"])
        if r["shipment_status"] == "delivered":
            lg.delivered += r["quantity"]
            lg.delivered_units.add(r["unit"])
        elif r["shipment_status"] == "cancelled":
            lg.cancelled += r["quantity"]
        else:
            lg.in_transit += r["quantity"]
    return ledgers


def classify(lg: ProductLedger, tolerance_pct: float) -> str | None:
    """Return the reconciliation category for one PO/product ledger, or None if it reconciles."""
    if lg.billed == 0:
        return None  # nothing billed yet; outstanding deliveries are not an exception
    units = lg.billed_units | lg.ordered_units | lg.delivered_units
    if len(units) > 1:
        return "unit_mismatch"
    if lg.delivered == 0:
        return "missing_shipment_evidence"
    limit = min(lg.delivered, lg.ordered) * (1 + tolerance_pct / 100.0)
    if lg.billed > limit:
        return "quantity_mismatch"
    return None


def _signal(lg: ProductLedger, category: str) -> Signal:
    pts = RULE.config["points"][category]
    unit = next(iter(lg.billed_units), None)
    invs = sorted(lg.invoice_ids)
    values = {"po_id": lg.po_id, "product_id": lg.product_id, "supplier_id": lg.supplier_id,
              "billed_quantity": lg.billed, "ordered_quantity": lg.ordered, "delivered_quantity": lg.delivered,
              "in_transit_quantity": lg.in_transit, "cancelled_quantity": lg.cancelled,
              "billed_units": sorted(lg.billed_units), "ordered_units": sorted(lg.ordered_units),
              "delivered_units": sorted(lg.delivered_units), "tolerance_pct": RULE.config["tolerance_pct"]}
    if category == "quantity_mismatch":
        values["excess_over_delivered"] = lg.billed - lg.delivered
        values["excess_over_ordered"] = lg.billed - lg.ordered
        summary = (f"{', '.join(invs)} billed {lg.billed} {unit} of {lg.product_id} on {lg.po_id}; "
                   f"{lg.ordered} ordered and {lg.delivered} delivered (excess over delivered: {lg.billed - lg.delivered})")
    elif category == "missing_shipment_evidence":
        summary = (f"{', '.join(invs)} billed {lg.billed} {unit} of {lg.product_id} on {lg.po_id} but no delivered "
                   f"shipment line exists (cancelled: {lg.cancelled}, in transit: {lg.in_transit})")
    else:
        summary = (f"Unit mismatch for {lg.product_id} on {lg.po_id}: billed in {sorted(lg.billed_units)}, "
                   f"ordered in {sorted(lg.ordered_units)}, delivered in {sorted(lg.delivered_units)}")
    paths = [f"(Supplier {lg.supplier_id})-[:SUBMITTED]->(Invoice {i})-[:BILLS]->(PurchaseOrder {lg.po_id})" for i in invs]
    paths += [f"(InvoiceLine {l})-[:BILLS_PRODUCT]->(Product {lg.product_id})" for l in lg.invoice_line_ids]
    paths += [f"(PurchaseOrder {lg.po_id})-[:HAS_LINE]->(POLine {l})-[:ORDERS_PRODUCT]->(Product {lg.product_id})"
              for l in lg.po_line_ids]
    paths += [f"(PurchaseOrder {lg.po_id})-[:FULFILLED_BY]->(Shipment {s})" for s in sorted(lg.shipment_ids)]
    paths += [f"(ShipmentLine {l})-[:SHIPS_PRODUCT]->(Product {lg.product_id})" for l in lg.shipment_line_ids]
    return Signal(
        rule_id=RULE.rule_id, subject_key=f"{lg.po_id}:{lg.product_id}:{category}", category=category, points=pts,
        summary=summary, values=values,
        record_ids={"PurchaseOrder": [lg.po_id], "Product": [lg.product_id], "Invoice": invs,
                    "Supplier": [lg.supplier_id] if lg.supplier_id else [], "Shipment": sorted(lg.shipment_ids),
                    "InvoiceLine": lg.invoice_line_ids, "POLine": lg.po_line_ids, "ShipmentLine": lg.shipment_line_ids},
        evidence_paths=paths,
        query={"name": "recon_billed_lines+recon_ordered_lines+recon_shipped_lines", "params": {"po_ids": [lg.po_id]}},
    )


def detect_reconciliation(po_ids: list[str] | None = None, invoice_ids: list[str] | None = None) -> list[Signal]:
    tol = RULE.config["tolerance_pct"]
    signals: list[Signal] = []
    if invoice_ids is None or po_ids is not None:
        ledgers = build_ledgers(run_named("recon_billed_lines", po_ids=po_ids),
                                run_named("recon_ordered_lines", po_ids=po_ids),
                                run_named("recon_shipped_lines", po_ids=po_ids))
        for key in sorted(ledgers):
            cat = classify(ledgers[key], tol)
            if cat:
                signals.append(_signal(ledgers[key], cat))
    if po_ids is None or invoice_ids is not None:
        for r in run_named("unlinked_invoices", invoice_ids=invoice_ids):
            inv = r["invoice_id"]
            signals.append(Signal(
                rule_id=RULE.rule_id, subject_key=f"{inv}:unresolved_purchase_order_link",
                category="unresolved_purchase_order_link",
                points=RULE.config["points"]["unresolved_purchase_order_link"],
                summary=f"Invoice {inv} from {r['supplier_id']} ({r['amount']:.2f} {r['currency']}) is not linked to any purchase order",
                values={"invoice_id": inv, "supplier_id": r["supplier_id"], "amount": r["amount"],
                        "currency": r["currency"], "status": r["status"]},
                record_ids={"Invoice": [inv], "Supplier": [r["supplier_id"]]},
                evidence_paths=[f"(Supplier {r['supplier_id']})-[:SUBMITTED]->(Invoice {inv}), no (Invoice {inv})-[:BILLS]->(PurchaseOrder)"],
                query={"name": "unlinked_invoices", "params": {"invoice_ids": [inv]}},
            ))
    return signals
