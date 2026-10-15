"""Phase B gate: synthetic data ingested into FalkorDB with full integrity."""
from app.graph.client import read
from app.graph.ingest import load_dataset
from app.graph.integrity import validate_graph


def test_integrity(loaded_graph):
    report = validate_graph()
    assert report["ok"], report["problems"]
    assert report["nodes"]["Supplier"] == 80
    assert report["nodes"]["Warehouse"] == 10


def test_demo_traversals(loaded_graph):
    # Invoice -> Supplier -> BankAccount <- Supplier
    net = read("""
        MATCH (i:Invoice {invoice_id: 'INV-1043'})<-[:SUBMITTED]-(s:Supplier)-[:USES_ACCOUNT]->(a:BankAccount)
              <-[:USES_ACCOUNT]-(o:Supplier)
        WHERE o <> s
        RETURN a.account_ref AS acct, o.supplier_id AS other ORDER BY other""")
    assert net == [{"acct": "ACC-900", "other": "SUP-011"}, {"acct": "ACC-900", "other": "SUP-012"}]


def test_pinned_server_does_not_enforce_relationship_uniqueness(loaded_graph):
    """Verified on falkordb/falkordb:v4.22.0 and 6.0.2: one edge may bind twice in a pattern, so detection
    queries must exclude self-matches explicitly (WHERE a <> b / id ordering)."""
    r = read("""
        MATCH (s:Supplier {supplier_id: 'SUP-010'})-[:USES_ACCOUNT]->(:BankAccount)<-[:USES_ACCOUNT]-(o:Supplier)
        RETURN collect(o.supplier_id) AS others""")[0]["others"]
    assert "SUP-010" in r
    # Invoice -> InvoiceLine -> Product <- ShipmentLine <- Shipment
    ship = read("""
        MATCH (i:Invoice {invoice_id: 'INV-1043'})-[:HAS_LINE]->(:InvoiceLine)-[:BILLS_PRODUCT]->(p:Product)
              <-[:SHIPS_PRODUCT]-(sl:ShipmentLine)<-[:HAS_LINE]-(sh:Shipment)<-[:FULFILLED_BY]-(:PurchaseOrder)<-[:BILLS]-(i)
        RETURN sh.shipment_id AS shp, sl.quantity AS qty""")
    assert ship == [{"shp": "SHP-7043", "qty": 60}]


def test_typed_properties(loaded_graph):
    r = read("MATCH (a:BankAccount {account_ref: 'ACC-950'}) RETURN a.registered_intermediary AS ri")[0]
    assert r["ri"] is True
    r = read("MATCH (i:Invoice {invoice_id: 'INV-1043'}) RETURN i.amount AS amt, i.source_file AS src")[0]
    assert r == {"amt": 1250.0, "src": "invoices.csv"}


def test_ingestion_is_idempotent(loaded_graph):
    load_dataset()
    report = validate_graph()
    assert report["ok"], report["problems"]


def test_ground_truth_not_in_graph(loaded_graph):
    labels = {r["l"] for r in read("MATCH (n) UNWIND labels(n) AS l RETURN DISTINCT l")}
    assert not any("truth" in l.lower() or "label" in l.lower() for l in labels)
    assert read("MATCH (n) WHERE n.expected IS NOT NULL OR n.case_id IS NOT NULL RETURN count(n) AS n")[0]["n"] == 0
