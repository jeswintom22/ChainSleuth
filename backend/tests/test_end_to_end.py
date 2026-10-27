"""Final acceptance test (deterministic agent path; the live-LLM variant is marked `llm`).

Covers: FalkorDB connection, dataset load + integrity, planted network / duplicate / delivery mismatch,
persisted investigation with deterministic score and evidence paths, grounded explanation, policy
evidence status, and reopening the investigation in a new session with reviewer state preserved.
"""
import pytest
from fastapi.testclient import TestClient

from app.config import EXPECTED_MODULE_VERSION, settings
from app.graph import client as graph_client
from app.main import app
from tests.conftest import TEST_TOKENS

AUTH = {"Authorization": f"Bearer {TEST_TOKENS['auditor.a']}"}


@pytest.fixture(scope="module")
def api(clean_investigation_layer):
    return TestClient(app, headers=AUTH)


def test_acceptance_flow(api, monkeypatch):
    monkeypatch.setenv("CHAINSLEUTH_DISABLE_LLM", "1")
    # 1-2. connection and dataset integrity
    h = api.get("/api/health").json()
    assert h["falkordb"] and h["dataset_loaded"] and h["falkordb_module_version"] == EXPECTED_MODULE_VERSION
    assert api.get("/api/graph/integrity").json()["ok"]

    # 3-5. investigation with detection, deterministic score and evidence paths
    r = api.post("/api/investigations", json={"question": "Why should INV-1043 be investigated?",
                                              "entity_id": "INV-1043"})
    assert r.status_code == 200, r.text
    inv = r.json()
    by_rule = {f["rule_id"]: f for f in inv["findings"]}
    assert by_rule["R1_SHARED_ACCOUNT"]["values"]["suppliers"] == ["SUP-010", "SUP-011", "SUP-012"]
    assert {f["subject_key"] for f in inv["findings"] if f["rule_id"] == "R2_DUPLICATE_INVOICE"} == {"INV-1043|INV-1044"}
    mismatch = next(f for f in inv["findings"] if f["category"] == "quantity_mismatch")
    assert (mismatch["values"]["billed_quantity"], mismatch["values"]["delivered_quantity"]) == (100, 60)
    assert all(f["evidence_paths"] and f["rule_version"] for f in inv["findings"])
    assert inv["score"] == 100 and inv["status"] == "open" and inv["created_by"] == "auditor.a"

    # 6. explanation tied to records, verified by the grounding validator
    assert inv["grounding"]["supported"] and inv["grounding"]["ids_checked"] > 0
    assert "INV-1043" in inv["explanation"] and "60" in inv["explanation"]
    assert "fraud" not in inv["explanation"].lower()

    # 7. policy evidence via GraphRAG or explicitly reported fallback/unavailable
    assert inv["policy_status"] in ("graphrag", "fallback", "unavailable")
    if inv["policy_status"] != "unavailable":
        assert any(f["policy_evidence"] for f in inv["findings"])

    # reviewer actions
    fid = mismatch["finding_id"]
    assert api.post(f"/api/findings/{fid}/review", json={"decision": "confirmed",
                                                         "note": "Receipt shortfall confirmed with warehouse",
                                                         "investigation_id": inv["investigation_id"]}).status_code == 200
    dup = by_rule["R2_DUPLICATE_INVOICE"]["finding_id"]
    api.post(f"/api/findings/{dup}/review", json={"decision": "dismissed", "note": "credited"})
    api.patch(f"/api/investigations/{inv['investigation_id']}", json={"status": "in_review"})

    # 8. new session: drop cached connections, re-run detection, reopen from FalkorDB
    graph_client.get_db.cache_clear()
    fresh = TestClient(app, headers=AUTH)
    fresh.post("/api/detect/run")
    again = fresh.get(f"/api/investigations/{inv['investigation_id']}").json()
    status = {f["finding_id"]: f["status"] for f in again["findings"]}
    assert status[fid] == "confirmed" and status[dup] == "dismissed" and again["status"] == "in_review"
    assert again["findings"][0]["reviews"] or any(f["reviews"] for f in again["findings"])
    assert again["score"] == 70  # dismissed duplicate (30 points) no longer counts
    assert again["explanation"] == inv["explanation"]

    # cross-session memory: a later investigation links back and reports the earlier reviewer decisions
    later = fresh.post("/api/investigations", json={"question": "What changed for SUP-010?", "entity_id": "SUP-010"}).json()
    assert inv["investigation_id"] in {p["investigation_id"] for p in later["history"]["previous"]}
    cmp = fresh.get(f"/api/investigations/{later['investigation_id']}/compare").json()
    assert cmp["has_previous"]


def test_clean_entity_produces_no_findings(api, monkeypatch):
    monkeypatch.setenv("CHAINSLEUTH_DISABLE_LLM", "1")
    inv = api.post("/api/investigations", json={"question": "Check SUP-043", "entity_id": "SUP-043"}).json()
    assert inv["findings"] == [] and inv["score"] == 0
    assert "No detection rule produced a finding" in inv["explanation"]


def test_api_rejects_bad_input(api):
    assert api.post("/api/investigations", json={"question": "x", "entity_id": "DROP GRAPH"}).status_code == 422
    assert api.post("/api/investigations", json={"question": "about INV-9999"}).status_code == 422
    assert api.post("/api/findings/F-x/review", json={"decision": "confirmed"}).status_code == 404
    assert api.post("/api/findings/F-x/review", json={"decision": "fraud"}).status_code == 422


@pytest.mark.llm
def test_acceptance_flow_with_live_llm(api):
    if not settings.openai_api_key:
        pytest.skip("OPENAI_API_KEY not configured")
    inv = api.post("/api/investigations", json={
        "question": "Why should INV-1043 be investigated, and which procurement policy supports the recommendation?",
        "entity_id": "INV-1043", "use_llm": True}).json()
    assert inv["grounding"]["supported"]
    assert inv["explanation_mode"] in ("llm_grounded", "deterministic_fallback")
    assert any(s["actor"] == "agent" for s in inv["tool_trace"])
