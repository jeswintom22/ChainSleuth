"""Phase D/G: deterministic scoring, persistent findings, repeatability, reviewer state."""
import pytest

from app.graph.client import read
from app.investigations import repository as repo
from app.investigations import service
from app.scoring import investigation_score, severity


@pytest.fixture(scope="module")
def detected(clean_investigation_layer):
    return service.run_detection()


def test_severity_thresholds():
    assert [severity(s) for s in (0, 24, 25, 49, 50, 74, 75, 100)] == \
        ["low", "low", "medium", "medium", "high", "high", "critical", "critical"]


def test_score_dedup_cap_and_dismissal():
    f = [{"finding_id": "A", "rule_id": "R2", "score": 30}, {"finding_id": "A", "rule_id": "R2", "score": 30},
         {"finding_id": "B", "rule_id": "R1", "score": 35}, {"finding_id": "C", "rule_id": "R3", "score": 25},
         {"finding_id": "D", "rule_id": "R3", "score": 25}, {"finding_id": "E", "rule_id": "R4", "score": 15, "status": "dismissed"}]
    s = investigation_score(f)
    assert (s["raw_points"], s["score"], s["capped"]) == (115, 100, True)
    assert [b["finding_id"] for b in s["breakdown"]] == ["A", "B", "C", "D"]


def test_finding_has_required_fields(detected):
    f = repo.get_finding(repo.finding_id_for("R3_RECONCILIATION", "PO-5043:PRD-007:quantity_mismatch"))
    assert f["rule_id"] == "R3_RECONCILIATION" and f["rule_version"] == "1.0.0"
    assert f["record_ids"]["Invoice"] == ["INV-1043"] and f["record_ids"]["Shipment"] == ["SHP-7043"]
    assert f["values"]["billed_quantity"] == 100 and f["values"]["delivered_quantity"] == 60
    assert any("SHP-7043" in p for p in f["evidence_paths"])
    assert f["query"]["params"] == {"po_ids": ["PO-5043"]}
    assert f["status"] == "open" and f["dataset_version"]
    rule = read("""MATCH (:Finding {finding_id: $id})-[:TRIGGERED_BY]->(d:DetectionRule)
                   RETURN d.rule_key AS k""", {"id": f["finding_id"]})
    assert rule == [{"k": "R3_RECONCILIATION@1.0.0"}]
    involved = {r["k"] for r in read("""MATCH (:Finding {finding_id: $id})-[:INVOLVES]->(n)
                   RETURN coalesce(n.invoice_id, n.shipment_id, n.po_id, n.supplier_id, n.product_id) AS k""",
                                      {"id": f["finding_id"]})}
    assert {"INV-1043", "SHP-7043", "PO-5043", "SUP-010", "PRD-007"} <= involved


def test_evidence_paths_are_reproducible(detected):
    """Re-running the finding's recorded query reproduces the stored values."""
    from app.detection.reconciliation import detect_reconciliation

    f = repo.get_finding(repo.finding_id_for("R3_RECONCILIATION", "PO-5043:PRD-007:quantity_mismatch"))
    [again] = detect_reconciliation(po_ids=f["query"]["params"]["po_ids"])
    assert again.values == f["values"] and again.evidence_paths == f["evidence_paths"]


def _counts():
    return read("""MATCH (f:Finding) OPTIONAL MATCH (f)-[r]->()
                   RETURN count(DISTINCT f) AS findings, count(r) AS edges""")[0]


def test_repeated_detection_runs_are_idempotent(detected):
    before = _counts()
    again = service.run_detection()
    assert again["new_findings"] == 0 and _counts() == before
    assert before["findings"] == detected["signals"] == 12


def test_detection_rerun_preserves_reviewer_decision(detected):
    fid = repo.finding_id_for("R1_SHARED_ACCOUNT", "ACC-901")
    repo.record_review(fid, "dismissed", "auditor.a", "Verified common treasury arrangement")
    service.run_detection()
    f = repo.get_finding(fid)
    assert f["status"] == "dismissed" and f["reviews"][-1]["reviewer"] == "auditor.a"
    repo.record_review(fid, "open", "auditor.a", "reopen for later tests")


def test_review_validation(detected):
    fid = repo.finding_id_for("R1_SHARED_ACCOUNT", "ACC-900")
    with pytest.raises(ValueError):
        repo.record_review(fid, "fraud", "x")
    with pytest.raises(ValueError):
        repo.record_review(fid, "confirmed", " ")
    with pytest.raises(KeyError):
        repo.record_review("F-doesnotexist", "confirmed", "x")


def test_investigation_scope_and_score(detected):
    inv = service.open_investigation("Why should INV-1043 be investigated?", rerun_detection=False)
    assert inv["target_label"] == "Invoice" and inv["scope"]["suppliers"] == ["SUP-010", "SUP-011", "SUP-012"]
    keys = {f["subject_key"] for f in inv["findings"]}
    assert keys == {"ACC-900", "INV-1043|INV-1044", "PO-5043:PRD-007:quantity_mismatch",
                    "INV-1044:unresolved_purchase_order_link"}
    assert inv["score"] == 100 and inv["severity"] == "critical"
    assert inv["status"] == "open"  # never auto-confirmed


def test_unrelated_supplier_investigation_is_clean(detected):
    inv = service.open_investigation("Check SUP-043", rerun_detection=False)  # legitimate partial deliveries
    assert inv["findings"] == [] and inv["score"] == 0 and inv["severity"] == "low"


def test_compare_tool_excludes_investigation_opened_in_same_session(detected):
    """Regression: an agent calling compare_with_previous right after open_investigation must compare
    against the EARLIER investigation, not the one it just opened."""
    from app.agent.orchestrator import Trace

    first = service.open_investigation("first look at SUP-020", rerun_detection=False)
    trace = Trace()
    opened = trace.call("open_investigation", {"entity_id": "SUP-020", "question": "second look"})
    cmp = trace.call("compare_with_previous", {"entity_id": "SUP-020"})
    assert cmp["previous_investigation"]["investigation_id"] == first["investigation_id"]
    assert cmp["previous_investigation"]["investigation_id"] != opened["investigation_id"]


def test_unknown_entity_rejected(detected):
    with pytest.raises(LookupError):
        service.open_investigation("What about INV-9999?", rerun_detection=False)
    with pytest.raises(ValueError):
        service.open_investigation("no id here", rerun_detection=False)
