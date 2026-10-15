"""Explicit, deterministic CSV -> FalkorDB ingestion for structured procurement data.

No LLM is involved. Every node keeps `source_file` for provenance. Ingestion uses MERGE on key
properties, so re-running it is idempotent and never touches Finding/Investigation nodes.
"""
from __future__ import annotations

import csv
from pathlib import Path

from falkordb import Graph

from app.config import settings
from app.graph.client import get_graph
from app.graph.schema import ensure_indexes

BATCH = 500

# (csv file, label, key column, {column: type})
NODES = [
    ("products.csv", "Product", "product_id", {"name": str, "unit": str, "list_price": float}),
    ("warehouses.csv", "Warehouse", "warehouse_id", {"name": str, "region": str}),
    ("suppliers.csv", "Supplier", "supplier_id", {"name": str, "status": str, "created_at": str}),
    ("bank_accounts.csv", "BankAccount", "account_ref",
     {"bank_code": str, "account_status": str, "registered_intermediary": bool}),
    ("owners.csv", "Owner", "owner_id", {"name": str}),
    ("purchase_orders.csv", "PurchaseOrder", "po_id", {"ordered_at": str, "status": str}),
    ("po_lines.csv", "POLine", "po_line_id", {"quantity": int, "unit": str, "unit_price": float}),
    ("invoices.csv", "Invoice", "invoice_id",
     {"invoice_number": str, "amount": float, "currency": str, "invoice_date": str, "status": str, "fingerprint": str}),
    ("invoice_lines.csv", "InvoiceLine", "line_id", {"quantity": int, "unit": str, "unit_price": float}),
    ("shipments.csv", "Shipment", "shipment_id", {"status": str, "shipped_at": str}),
    ("shipment_lines.csv", "ShipmentLine", "shipment_line_id", {"quantity": int, "unit": str}),
    ("payments.csv", "Payment", "payment_id", {"amount": float, "currency": str, "paid_at": str, "status": str}),
]

# (csv file, from label, from key prop, from column, REL, to label, to key prop, to column, {rel prop: (column, type)})
RELS = [
    ("supplier_accounts.csv", "Supplier", "supplier_id", "supplier_id", "USES_ACCOUNT", "BankAccount", "account_ref", "account_ref", {}),
    ("supplier_owners.csv", "Supplier", "supplier_id", "supplier_id", "CONTROLLED_BY", "Owner", "owner_id", "owner_id", {}),
    ("invoices.csv", "Supplier", "supplier_id", "supplier_id", "SUBMITTED", "Invoice", "invoice_id", "invoice_id", {}),
    ("invoices.csv", "Invoice", "invoice_id", "invoice_id", "BILLS", "PurchaseOrder", "po_id", "po_id", {}),
    ("invoice_lines.csv", "Invoice", "invoice_id", "invoice_id", "HAS_LINE", "InvoiceLine", "line_id", "line_id", {}),
    ("invoice_lines.csv", "InvoiceLine", "line_id", "line_id", "BILLS_PRODUCT", "Product", "product_id", "product_id", {}),
    ("purchase_orders.csv", "Supplier", "supplier_id", "supplier_id", "RECEIVED_PO", "PurchaseOrder", "po_id", "po_id", {}),
    ("po_lines.csv", "PurchaseOrder", "po_id", "po_id", "HAS_LINE", "POLine", "po_line_id", "po_line_id", {}),
    ("po_lines.csv", "POLine", "po_line_id", "po_line_id", "ORDERS_PRODUCT", "Product", "product_id", "product_id", {}),
    ("shipments.csv", "PurchaseOrder", "po_id", "po_id", "FULFILLED_BY", "Shipment", "shipment_id", "shipment_id", {}),
    ("shipment_lines.csv", "Shipment", "shipment_id", "shipment_id", "HAS_LINE", "ShipmentLine", "shipment_line_id", "shipment_line_id", {}),
    ("shipment_lines.csv", "ShipmentLine", "shipment_line_id", "shipment_line_id", "SHIPS_PRODUCT", "Product", "product_id", "product_id", {}),
    ("shipment_stops.csv", "Shipment", "shipment_id", "shipment_id", "ROUTE_STOP", "Warehouse", "warehouse_id", "warehouse_id",
     {"sequence": ("sequence", int)}),
    ("warehouse_routes.csv", "Warehouse", "warehouse_id", "from_warehouse", "APPROVED_NEXT", "Warehouse", "warehouse_id", "to_warehouse", {}),
    ("payments.csv", "Invoice", "invoice_id", "invoice_id", "SETTLED_BY", "Payment", "payment_id", "payment_id", {}),
    ("payments.csv", "Payment", "payment_id", "payment_id", "PAID_TO", "Supplier", "supplier_id", "supplier_id", {}),
]


def _cast(value: str, typ):
    if typ is bool:
        return value.strip().lower() in ("true", "1", "yes")
    return typ(value)


def _read(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _batched(items: list, n: int = BATCH):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def load_dataset(data_dir: Path | None = None, graph: Graph | None = None) -> dict[str, int]:
    data_dir = data_dir or settings.data_dir
    g = graph or get_graph()
    ensure_indexes(g)
    counts: dict[str, int] = {}

    for file, label, key, props in NODES:
        rows = [{"key": r[key], "props": {**{c: _cast(r[c], t) for c, t in props.items()}, "source_file": file}}
                for r in _read(data_dir / file)]
        for chunk in _batched(rows):
            g.query(f"UNWIND $rows AS row MERGE (n:{label} {{{key}: row.key}}) SET n += row.props", {"rows": chunk})
        counts[label] = len(rows)

    for file, fl, fk, fcol, rel, tl, tk, tcol, rprops in RELS:
        rows = [{"a": r[fcol], "b": r[tcol], "props": {p: _cast(r[c], t) for p, (c, t) in rprops.items()}}
                for r in _read(data_dir / file) if r.get(fcol) and r.get(tcol)]
        # ROUTE_STOP can legitimately repeat between the same pair, so its identity includes `sequence`.
        merge_props = "{sequence: row.props.sequence}" if "sequence" in rprops else ""
        for chunk in _batched(rows):
            g.query(
                f"UNWIND $rows AS row MATCH (a:{fl} {{{fk}: row.a}}), (b:{tl} {{{tk}: row.b}}) "
                f"MERGE (a)-[r:{rel} {merge_props}]->(b) SET r += row.props",
                {"rows": chunk},
            )
        counts[f"{rel}:{file}"] = len(rows)
    return counts


def reset_operational_graph(graph: Graph | None = None) -> None:
    """Delete the whole graph (used for clean test runs and the demo reset)."""
    g = graph or get_graph()
    try:
        g.delete()
    except Exception as e:
        if "empty key" not in str(e).lower() and "invalid graph" not in str(e).lower():
            raise


if __name__ == "__main__":
    import sys

    if "--reset" in sys.argv:
        reset_operational_graph()
    for k, v in load_dataset().items():
        print(f"{k:40s} {v}")
