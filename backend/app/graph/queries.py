"""Registry of reviewed, named Cypher queries.

This is the ONLY place detection/investigation Cypher lives. Queries are parameterized and executed
by name via `run_named()`; nothing in the application executes free-form or LLM-generated Cypher.

Server behaviours the queries account for (pinned by tests/test_ingestion.py and test_detection.py):
  * A single relationship may bind more than once within a pattern (v4.22.0 and 6.0.2), so queries
    that match two nodes through a shared neighbour exclude self-matches explicitly.
  * On 6.0.2, `MATCH ... WHERE` followed by `OPTIONAL MATCH ... WHERE` silently dropped the first
    WHERE. The pinned v4.22.0 does not, but queries keep a `WITH` barrier there for portability.
"""
from __future__ import annotations

from typing import Any

from app.graph.client import read

QUERIES: dict[str, str] = {
    # ---- R1: shared payout accounts ----
    "shared_accounts": """
        MATCH (s1:Supplier)-[:USES_ACCOUNT]->(a:BankAccount)<-[:USES_ACCOUNT]-(s2:Supplier)
        WHERE s1.supplier_id < s2.supplier_id
          AND ($supplier_id IS NULL OR s1.supplier_id = $supplier_id OR s2.supplier_id = $supplier_id)
        OPTIONAL MATCH (s1)-[:CONTROLLED_BY]->(o:Owner)<-[:CONTROLLED_BY]-(s2)
        RETURN a.account_ref AS account_ref, a.registered_intermediary AS registered_intermediary,
               a.bank_code AS bank_code,
               s1.supplier_id AS supplier_a, s1.name AS supplier_a_name,
               s2.supplier_id AS supplier_b, s2.name AS supplier_b_name,
               collect(DISTINCT o.owner_id) AS shared_owners
        ORDER BY account_ref, supplier_a, supplier_b
        LIMIT 500
    """,
    # ---- R2: exact duplicate invoices (fingerprint collision) ----
    "duplicate_invoices": """
        MATCH (i1:Invoice), (i2:Invoice)
        WHERE i2.fingerprint = i1.fingerprint AND i1.invoice_id < i2.invoice_id
          AND ($invoice_id IS NULL OR i1.invoice_id = $invoice_id OR i2.invoice_id = $invoice_id)
        WITH i1, i2
        MATCH (s1:Supplier)-[:SUBMITTED]->(i1)
        MATCH (s2:Supplier)-[:SUBMITTED]->(i2)
        OPTIONAL MATCH (s1)-[:USES_ACCOUNT]->(a:BankAccount)<-[:USES_ACCOUNT]-(s2)
        WHERE s1 <> s2
        RETURN i1.invoice_id AS invoice_a, i2.invoice_id AS invoice_b,
               s1.supplier_id AS supplier_a, s2.supplier_id AS supplier_b,
               i1.invoice_number AS invoice_number, i1.amount AS amount, i1.currency AS currency,
               i1.invoice_date AS invoice_date, i1.fingerprint AS fingerprint,
               i1.status AS status_a, i2.status AS status_b,
               collect(DISTINCT a.account_ref) AS shared_accounts
        ORDER BY invoice_a, invoice_b
    """,
    # ---- R3: line-level reconciliation inputs ----
    "recon_billed_lines": """
        MATCH (s:Supplier)-[:SUBMITTED]->(i:Invoice)-[:BILLS]->(po:PurchaseOrder)
        WHERE $po_ids IS NULL OR po.po_id IN $po_ids
        MATCH (i)-[:HAS_LINE]->(il:InvoiceLine)-[:BILLS_PRODUCT]->(p:Product)
        RETURN po.po_id AS po_id, s.supplier_id AS supplier_id, i.invoice_id AS invoice_id, i.status AS invoice_status,
               il.line_id AS line_id, p.product_id AS product_id, il.quantity AS quantity, il.unit AS unit
        ORDER BY po_id, invoice_id, line_id
    """,
    "recon_ordered_lines": """
        MATCH (po:PurchaseOrder)-[:HAS_LINE]->(pl:POLine)-[:ORDERS_PRODUCT]->(p:Product)
        WHERE $po_ids IS NULL OR po.po_id IN $po_ids
        RETURN po.po_id AS po_id, pl.po_line_id AS po_line_id, p.product_id AS product_id,
               pl.quantity AS quantity, pl.unit AS unit
        ORDER BY po_id, po_line_id
    """,
    "recon_shipped_lines": """
        MATCH (po:PurchaseOrder)-[:FULFILLED_BY]->(sh:Shipment)
        WHERE $po_ids IS NULL OR po.po_id IN $po_ids
        MATCH (sh)-[:HAS_LINE]->(sl:ShipmentLine)-[:SHIPS_PRODUCT]->(p:Product)
        RETURN po.po_id AS po_id, sh.shipment_id AS shipment_id, sh.status AS shipment_status,
               sl.shipment_line_id AS shipment_line_id, p.product_id AS product_id,
               sl.quantity AS quantity, sl.unit AS unit
        ORDER BY po_id, shipment_id, shipment_line_id
    """,
    "unlinked_invoices": """
        MATCH (s:Supplier)-[:SUBMITTED]->(i:Invoice)
        WHERE $invoice_ids IS NULL OR i.invoice_id IN $invoice_ids
        OPTIONAL MATCH (i)-[:BILLS]->(po:PurchaseOrder)
        WITH s, i, po WHERE po IS NULL
        RETURN i.invoice_id AS invoice_id, s.supplier_id AS supplier_id, i.amount AS amount,
               i.currency AS currency, i.status AS status
        ORDER BY invoice_id
    """,
    # ---- R4: route transitions not in the approved warehouse network ----
    "route_deviations": """
        MATCH (sh:Shipment)-[r1:ROUTE_STOP]->(w1:Warehouse), (sh)-[r2:ROUTE_STOP]->(w2:Warehouse)
        WHERE r2.sequence = r1.sequence + 1
          AND ($shipment_ids IS NULL OR sh.shipment_id IN $shipment_ids)
        OPTIONAL MATCH (w1)-[ap:APPROVED_NEXT]->(w2)
        WITH sh, r1, r2, w1, w2, ap WHERE ap IS NULL
        MATCH (po:PurchaseOrder)-[:FULFILLED_BY]->(sh)
        OPTIONAL MATCH (sup:Supplier)-[:RECEIVED_PO]->(po)
        RETURN sh.shipment_id AS shipment_id, sh.status AS shipment_status, po.po_id AS po_id,
               sup.supplier_id AS supplier_id, r1.sequence AS from_sequence, r2.sequence AS to_sequence,
               w1.warehouse_id AS origin, w2.warehouse_id AS destination
        ORDER BY shipment_id, to_sequence
    """,
    # ---- investigation scope / context ----
    "resolve_entity": """
        MATCH (n) WHERE (n:Supplier AND n.supplier_id = $id) OR (n:Invoice AND n.invoice_id = $id)
                     OR (n:PurchaseOrder AND n.po_id = $id) OR (n:Shipment AND n.shipment_id = $id)
        RETURN labels(n)[0] AS label LIMIT 1
    """,
    "entity_supplier": """
        MATCH (s:Supplier {supplier_id: $id}) RETURN s.supplier_id AS supplier_id
        UNION MATCH (s:Supplier)-[:SUBMITTED]->(:Invoice {invoice_id: $id}) RETURN s.supplier_id AS supplier_id
        UNION MATCH (s:Supplier)-[:RECEIVED_PO]->(:PurchaseOrder {po_id: $id}) RETURN s.supplier_id AS supplier_id
        UNION MATCH (s:Supplier)-[:RECEIVED_PO]->(:PurchaseOrder)-[:FULFILLED_BY]->(:Shipment {shipment_id: $id})
              RETURN s.supplier_id AS supplier_id
    """,
    "invoice_context": """
        MATCH (s:Supplier)-[:SUBMITTED]->(i:Invoice {invoice_id: $invoice_id})
        OPTIONAL MATCH (i)-[:BILLS]->(po:PurchaseOrder)
        OPTIONAL MATCH (po)-[:FULFILLED_BY]->(sh:Shipment)
        RETURN s.supplier_id AS supplier_id, s.name AS supplier_name, i.invoice_id AS invoice_id,
               i.invoice_number AS invoice_number, i.amount AS amount, i.currency AS currency,
               i.invoice_date AS invoice_date, i.status AS status, po.po_id AS po_id,
               collect(DISTINCT sh.shipment_id) AS shipment_ids
    """,
    "supplier_network": """
        MATCH (s:Supplier {supplier_id: $supplier_id})
        OPTIONAL MATCH (s)-[:USES_ACCOUNT]->(a:BankAccount)<-[:USES_ACCOUNT]-(o:Supplier)
        WHERE o <> s AND a.registered_intermediary = false
        WITH s, collect(DISTINCT o.supplier_id) AS account_linked, collect(DISTINCT a.account_ref) AS shared_accounts
        OPTIONAL MATCH (s)-[:CONTROLLED_BY]->(w:Owner)<-[:CONTROLLED_BY]-(c:Supplier)
        WHERE c <> s
        RETURN s.supplier_id AS supplier_id, s.name AS name, account_linked, shared_accounts,
               collect(DISTINCT c.supplier_id) AS owner_linked, collect(DISTINCT w.owner_id) AS shared_owners
    """,
    "supplier_activity": """
        MATCH (s:Supplier) WHERE s.supplier_id IN $supplier_ids
        OPTIONAL MATCH (s)-[:SUBMITTED]->(i:Invoice)
        OPTIONAL MATCH (i)-[:BILLS]->(po:PurchaseOrder)
        OPTIONAL MATCH (po)-[:FULFILLED_BY]->(sh:Shipment)
        RETURN s.supplier_id AS supplier_id, s.name AS name,
               collect(DISTINCT i.invoice_id) AS invoice_ids, collect(DISTINCT po.po_id) AS po_ids,
               collect(DISTINCT sh.shipment_id) AS shipment_ids
        ORDER BY supplier_id
    """,
    "graph_neighbourhood": """
        MATCH (s:Supplier) WHERE s.supplier_id IN $supplier_ids
        OPTIONAL MATCH (s)-[r:USES_ACCOUNT|CONTROLLED_BY]->(m)
        RETURN s.supplier_id AS source, s.name AS source_name, type(r) AS rel, labels(m)[0] AS target_label,
               coalesce(m.account_ref, m.owner_id) AS target, m.registered_intermediary AS intermediary
    """,
}

DEFAULT_PARAMS: dict[str, dict[str, Any]] = {
    "shared_accounts": {"supplier_id": None},
    "duplicate_invoices": {"invoice_id": None},
    "recon_billed_lines": {"po_ids": None},
    "recon_ordered_lines": {"po_ids": None},
    "recon_shipped_lines": {"po_ids": None},
    "unlinked_invoices": {"invoice_ids": None},
    "route_deviations": {"shipment_ids": None},
}


def run_named(name: str, **params: Any) -> list[dict[str, Any]]:
    """Execute a registered query read-only. Unknown names or unexpected parameters are rejected."""
    if name not in QUERIES:
        raise KeyError(f"Unknown query: {name}")
    merged = {**DEFAULT_PARAMS.get(name, {}), **params}
    allowed = set(DEFAULT_PARAMS.get(name, {})) | {p for p in params if f"${p}" in QUERIES[name]}
    extra = set(merged) - allowed
    if extra:
        raise ValueError(f"Unexpected parameters for {name}: {extra}")
    return read(QUERIES[name], merged)
