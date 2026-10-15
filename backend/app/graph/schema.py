"""Graph schema: node labels, key properties and indexes for the operational procurement graph."""
from falkordb import Graph

from app.graph.client import get_graph

# label -> key property
NODE_KEYS: dict[str, str] = {
    "Supplier": "supplier_id",
    "BankAccount": "account_ref",
    "Owner": "owner_id",
    "Invoice": "invoice_id",
    "InvoiceLine": "line_id",
    "PurchaseOrder": "po_id",
    "POLine": "po_line_id",
    "Shipment": "shipment_id",
    "ShipmentLine": "shipment_line_id",
    "Warehouse": "warehouse_id",
    "Payment": "payment_id",
    "Product": "product_id",
    # Investigation layer
    "Finding": "finding_id",
    "Investigation": "investigation_id",
    "DetectionRule": "rule_key",
    "EvidenceChunk": "chunk_id",
    "ReviewAction": "action_id",
}

EXTRA_INDEXES = [("Invoice", "fingerprint"), ("Finding", "rule_id"), ("Finding", "status")]


def ensure_indexes(graph: Graph | None = None) -> None:
    g = graph or get_graph()
    for label, prop in list(NODE_KEYS.items()) + EXTRA_INDEXES:
        try:
            g.query(f"CREATE INDEX FOR (n:{label}) ON (n.{prop})")
        except Exception as e:  # index already exists
            if "already indexed" not in str(e).lower() and "already exists" not in str(e).lower():
                raise
