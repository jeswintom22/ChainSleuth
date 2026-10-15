"""Phase C: detection rules evaluated against planted anomalies and legitimate controls."""
import pytest

from app.detection.duplicate_invoice import detect_duplicate_invoices
from app.detection.engine import run_all
from app.detection.reconciliation import ProductLedger, classify, detect_reconciliation
from app.detection.route_anomaly import detect_route_anomalies
from app.detection.supplier_network import detect_shared_accounts
from app.graph.client import read
from app.graph.queries import run_named


@pytest.fixture(scope="module")
def all_signals(loaded_graph):
    signals, _ = run_all()
    return signals


def _keys(signals, rule_id):
    return {s.subject_key for s in signals if s.rule_id == rule_id}


@pytest.mark.parametrize("rule_id", ["R1_SHARED_ACCOUNT", "R2_DUPLICATE_INVOICE", "R3_RECONCILIATION", "R4_ROUTE_ANOMALY"])
def test_rule_matches_ground_truth_exactly(all_signals, ground_truth, rule_id):
    expected = {g["subject_key"] for g in ground_truth if g["rule_id"] == rule_id and g["expected"] == "anomaly"}
    assert _keys(all_signals, rule_id) == expected  # recall = precision = 1.0 on the planted set


def test_legitimate_shared_intermediary_account_not_flagged(all_signals):
    assert "ACC-950" not in _keys(all_signals, "R1_SHARED_ACCOUNT")
    # ...but the graph does contain the shared account, so this is a deliberate rule exclusion
    assert any(r["account_ref"] == "ACC-950" for r in run_named("shared_accounts"))


def test_recurring_invoices_not_duplicates(all_signals):
    flagged = {i for k in _keys(all_signals, "R2_DUPLICATE_INVOICE") for i in k.split("|")}
    assert not flagged & {"INV-1100", "INV-1101", "INV-1102"}


def test_partial_shipments_not_flagged(all_signals):
    po_ids = {s.values.get("po_id") for s in all_signals if s.rule_id == "R3_RECONCILIATION"}
    assert not po_ids & {"PO-5080", "PO-5081"}


def test_shared_account_corroboration_and_values(loaded_graph):
    sig = {s.subject_key: s for s in detect_shared_accounts()}
    assert sig["ACC-900"].values["suppliers"] == ["SUP-010", "SUP-011", "SUP-012"]
    assert sig["ACC-900"].values["shared_owners"] == ["OWN-900"] and sig["ACC-900"].points == 35
    assert sig["ACC-901"].values["corroborated"] is False and sig["ACC-901"].points == 20


def test_scoped_detection(loaded_graph):
    assert {s.subject_key for s in detect_shared_accounts("SUP-012")} == {"ACC-900"}
    assert {s.subject_key for s in detect_duplicate_invoices("INV-1044")} == {"INV-1043|INV-1044"}
    assert detect_route_anomalies(["SHP-7043"]) == []


def test_demo_invoice_reconciliation_values(loaded_graph):
    [s] = [s for s in detect_reconciliation(po_ids=["PO-5043"])]
    assert s.category == "quantity_mismatch"
    assert (s.values["billed_quantity"], s.values["ordered_quantity"], s.values["delivered_quantity"]) == (100, 100, 60)
    assert s.values["excess_over_delivered"] == 40
    assert s.record_ids["Shipment"] == ["SHP-7043"] and s.record_ids["Invoice"] == ["INV-1043"]


def test_route_anomaly_reports_exact_transition(loaded_graph):
    [s] = detect_route_anomalies(["SHP-7090"])
    assert (s.values["origin"], s.values["destination"], s.values["to_sequence"]) == ("WH-02", "WH-09", 3)


# ---- pure arithmetic (no database) ----
def _lg(**kw):
    lg = ProductLedger("PO-X", "PRD-X")
    for k, v in kw.items():
        setattr(lg, k, v)
    return lg


@pytest.mark.parametrize("ledger,expected", [
    (dict(billed=0, ordered=100, delivered=0), None),                     # nothing billed yet
    (dict(billed=60, ordered=100, delivered=60), None),                   # partial delivery, partial invoice
    (dict(billed=100, ordered=100, delivered=60), "quantity_mismatch"),
    (dict(billed=101, ordered=100, delivered=100), None),                 # within 2% tolerance
    (dict(billed=103, ordered=100, delivered=100), "quantity_mismatch"),  # beyond tolerance
    (dict(billed=30, ordered=30, delivered=0, cancelled=30), "missing_shipment_evidence"),
    (dict(billed=30, ordered=30, delivered=0, in_transit=30), "missing_shipment_evidence"),
    (dict(billed=20, ordered=20, delivered=20, billed_units={"box"}, delivered_units={"each"}), "unit_mismatch"),
    (dict(billed=10, ordered=0, delivered=10), "quantity_mismatch"),      # billed product never ordered
])
def test_classify(ledger, expected):
    assert classify(_lg(**ledger), tolerance_pct=2.0) == expected


# ---- server behaviours that the queries depend on ----
def test_with_barrier_keeps_match_filter_before_filtered_optional_match(loaded_graph):
    """On falkordb 6.0.2 the first WHERE was silently dropped without the WITH barrier (63,368 rows instead
    of 2). v4.22.0 applies it either way. The barrier is correct on both, so queries keep it."""
    base = ("MATCH (i1:Invoice), (i2:Invoice) WHERE i2.fingerprint = i1.fingerprint AND i1.invoice_id < i2.invoice_id "
            "{barrier} MATCH (s1:Supplier)-[:SUBMITTED]->(i1) MATCH (s2:Supplier)-[:SUBMITTED]->(i2) "
            "OPTIONAL MATCH (s1)-[:USES_ACCOUNT]->(a:BankAccount)<-[:USES_ACCOUNT]-(s2) WHERE s1 <> s2 RETURN count(*) AS n")
    assert read(base.format(barrier="WITH i1, i2"))[0]["n"] == 2
    assert read(base.format(barrier=""))[0]["n"] == 2  # pinned v4.22.0 behaviour


def test_unknown_query_and_params_rejected():
    with pytest.raises(KeyError):
        run_named("MATCH (n) DETACH DELETE n")
    with pytest.raises(ValueError):
        run_named("shared_accounts", evil="x")
