"""Graph integrity checks run after ingestion. All checks are read-only Cypher against FalkorDB."""
from __future__ import annotations

import csv
from pathlib import Path

from app.config import settings
from app.graph.client import read
from app.graph.ingest import NODES, RELS

# Structural rules every loaded record must satisfy: (description, cypher returning `n` = violation count)
STRUCTURAL_CHECKS = [
    ("invoice line without product", "MATCH (l:InvoiceLine) WHERE NOT (l)-[:BILLS_PRODUCT]->(:Product) RETURN count(l) AS n"),
    ("invoice line without invoice", "MATCH (l:InvoiceLine) WHERE NOT (:Invoice)-[:HAS_LINE]->(l) RETURN count(l) AS n"),
    ("invoice without supplier", "MATCH (i:Invoice) WHERE NOT (:Supplier)-[:SUBMITTED]->(i) RETURN count(i) AS n"),
    ("PO line without product", "MATCH (l:POLine) WHERE NOT (l)-[:ORDERS_PRODUCT]->(:Product) RETURN count(l) AS n"),
    ("shipment without PO", "MATCH (s:Shipment) WHERE NOT (:PurchaseOrder)-[:FULFILLED_BY]->(s) RETURN count(s) AS n"),
    ("shipment line without product", "MATCH (l:ShipmentLine) WHERE NOT (l)-[:SHIPS_PRODUCT]->(:Product) RETURN count(l) AS n"),
    ("shipment without route", "MATCH (s:Shipment) WHERE NOT (s)-[:ROUTE_STOP]->(:Warehouse) RETURN count(s) AS n"),
    ("supplier without payout account", "MATCH (s:Supplier) WHERE NOT (s)-[:USES_ACCOUNT]->(:BankAccount) RETURN count(s) AS n"),
    ("payment without payee", "MATCH (p:Payment) WHERE NOT (p)-[:PAID_TO]->(:Supplier) RETURN count(p) AS n"),
]


def _csv_len(path: Path, fcol: str | None = None, tcol: str | None = None) -> int:
    with open(path, newline="", encoding="utf-8") as f:
        return sum(1 for r in csv.DictReader(f) if (fcol is None or (r.get(fcol) and r.get(tcol))))


def validate_graph(data_dir: Path | None = None) -> dict:
    data_dir = data_dir or settings.data_dir
    problems: list[str] = []
    node_counts, rel_counts = {}, {}

    for file, label, _key, _ in NODES:
        expected = _csv_len(data_dir / file)
        actual = read(f"MATCH (n:{label}) RETURN count(n) AS n")[0]["n"]
        node_counts[label] = actual
        if actual != expected:
            problems.append(f"{label}: expected {expected}, found {actual}")

    expected_rels: dict[str, int] = {}
    for file, _fl, _fk, fcol, rel, _tl, _tk, tcol, _ in RELS:
        expected_rels[rel] = expected_rels.get(rel, 0) + _csv_len(data_dir / file, fcol, tcol)
    for rel, expected in expected_rels.items():
        actual = read(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS n")[0]["n"]
        rel_counts[rel] = actual
        if actual != expected:
            problems.append(f"{rel}: expected {expected}, found {actual}")

    for desc, q in STRUCTURAL_CHECKS:
        n = read(q)[0]["n"]
        if n:
            problems.append(f"{n} x {desc}")

    return {"ok": not problems, "problems": problems, "nodes": node_counts, "relationships": rel_counts}
