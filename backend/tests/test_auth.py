"""Authentication on state-changing routes; reviewer identity comes from the token, not the request body."""
import pytest
from fastapi.testclient import TestClient

from app.auth import parse_users
from app.main import app
from tests.conftest import TEST_TOKENS

REVIEWER = {"Authorization": f"Bearer {TEST_TOKENS['auditor.a']}"}
ADMIN = {"Authorization": f"Bearer {TEST_TOKENS['admin.t']}"}


@pytest.fixture(scope="module")
def anon(clean_investigation_layer):
    return TestClient(app)


@pytest.mark.parametrize("method,path,body", [
    ("post", "/api/admin/load-dataset", {"reset": True}),
    ("post", "/api/detect/run", None),
    ("post", "/api/findings/F-x/review", {"decision": "dismissed"}),
    ("post", "/api/investigations", {"question": "Check SUP-043", "entity_id": "SUP-043"}),
    ("patch", "/api/investigations/INVG-X", {"status": "closed"}),
    ("post", "/api/investigations/INVG-X/ask", {"question": "why?"}),
    ("get", "/api/auth/me", None),
])
def test_mutating_routes_require_token(anon, method, path, body):
    for headers in ({}, {"Authorization": "Bearer not-a-real-token-123456"}, {"Authorization": "Basic abc"}):
        r = getattr(anon, method)(path, json=body, headers=headers) if body is not None \
            else getattr(anon, method)(path, headers=headers)
        assert r.status_code == 401, (path, headers, r.text)


def test_read_routes_stay_open(anon):
    assert anon.get("/api/health").status_code == 200
    assert anon.get("/api/findings").status_code == 200


def test_load_dataset_requires_admin(anon):
    assert anon.post("/api/admin/load-dataset", json={"reset": True}, headers=REVIEWER).status_code == 403


def test_me_reports_token_identity(anon):
    assert anon.get("/api/auth/me", headers=REVIEWER).json() == {"name": "auditor.a", "role": "reviewer"}
    assert anon.get("/api/auth/me", headers=ADMIN).json() == {"name": "admin.t", "role": "admin"}


def test_reviewer_identity_comes_from_token(anon, monkeypatch):
    monkeypatch.setenv("CHAINSLEUTH_DISABLE_LLM", "1")
    inv = anon.post("/api/investigations", headers=REVIEWER,
                    json={"question": "Why INV-1043?", "entity_id": "INV-1043", "created_by": "alice"}).json()
    assert inv["created_by"] == "auditor.a"
    fid = inv["findings"][0]["finding_id"]
    r = anon.post(f"/api/findings/{fid}/review", headers=REVIEWER,
                  json={"decision": "needs_review", "reviewer": "alice", "note": "spoof attempt"})
    assert r.status_code == 200, r.text
    assert anon.get(f"/api/findings/{fid}").json()["reviews"][-1]["reviewer"] == "auditor.a"
    r = anon.patch(f"/api/investigations/{inv['investigation_id']}", headers=REVIEWER,
                   json={"status": "in_review", "reviewer": "alice"})
    assert r.status_code == 200 and r.json()["status"] == "in_review"


def test_parse_users_rejects_bad_config():
    assert parse_users("") == []
    assert parse_users("a:admin:0123456789abcdef") == [("a", "admin", "0123456789abcdef")]
    for bad in ("a:reviewer", "a:root:0123456789abcdef", "a:reviewer:short", ":admin:0123456789abcdef"):
        with pytest.raises(ValueError):
            parse_users(bad)
