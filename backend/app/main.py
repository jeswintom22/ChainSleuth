"""ChainSleuth API. No endpoint accepts Cypher; every graph operation goes through named functions.

Every state-changing route requires a bearer token (see app/auth.py); reviewer identity comes from that token."""
from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.agent import orchestrator
from app.agent.llm import llm_available
from app.auth import User, current_user, require_admin
from app.config import settings
from app.detection.base import RULES
from app.graph import client
from app.graph.ingest import load_dataset, reset_operational_graph
from app.graph.integrity import validate_graph
from app.graphrag import client as graphrag_client
from app.investigations import repository as repo
from app.investigations import service

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="ChainSleuth", version="1.0.0",
              description="Explainable procurement anomaly investigation on FalkorDB. Findings are review signals, "
                          "not determinations of wrongdoing.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3001", "http://127.0.0.1:3001"],
                   allow_methods=["*"], allow_headers=["*"])

ID_PATTERN = r"^(SUP-\d{3}|INV-\d{4}|PO-\d{4}|SHP-\d{4})$"


class LoadRequest(BaseModel):
    reset: bool = False


class InvestigationRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    entity_id: str | None = Field(default=None, pattern=ID_PATTERN)
    use_llm: bool | None = None


class ReviewRequest(BaseModel):
    decision: str = Field(pattern=r"^(open|needs_review|confirmed|dismissed)$")
    note: str = Field(default="", max_length=1000)
    investigation_id: str | None = None


class StatusRequest(BaseModel):
    status: str = Field(pattern=r"^(open|in_review|closed)$")


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)
    use_llm: bool | None = None


def _404(what: str):
    raise HTTPException(status_code=404, detail=f"{what} not found")


def _server_version() -> str | None:
    try:
        for mod in client.get_db().connection.execute_command("MODULE", "LIST"):
            d = {(k.decode() if isinstance(k, bytes) else k): v for k, v in zip(mod[::2], mod[1::2])}
            name = d.get("name")
            name = name.decode() if isinstance(name, bytes) else name
            if name and name.lower() == "graph":
                return str(d.get("ver"))
    except Exception:
        return None
    return None


@app.get("/api/health")
def health():
    ok = client.ping()
    loaded = ok and bool(client.read("MATCH (s:Supplier) RETURN count(s) AS n")[0]["n"])
    return {"falkordb": ok, "falkordb_module_version": _server_version() if ok else None,
            "graph": settings.graph_name, "dataset_loaded": loaded, "llm_available": llm_available(),
            "graphrag_available": graphrag_client.is_available(),
            "graphrag_detail": None if graphrag_client.is_available() else graphrag_client.unavailable_reason()}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {"name": user.name, "role": user.role}


@app.post("/api/admin/load-dataset")
def load(req: LoadRequest, _: User = Depends(require_admin)):
    if req.reset:
        reset_operational_graph()
    counts = load_dataset()
    return {"loaded": counts, "integrity": validate_graph()}


@app.get("/api/graph/integrity")
def integrity():
    return validate_graph()


@app.get("/api/rules")
def rules():
    return [{"rule_id": r.rule_id, "version": r.version, "title": r.title, "description": r.description,
             "queries": list(r.query_names), "config": r.config} for r in RULES.values()]


@app.post("/api/detect/run")
def detect(_: User = Depends(current_user)):
    return service.run_detection()


@app.get("/api/stats")
def stats():
    findings = repo.list_findings()
    by = lambda key: {k: sum(1 for f in findings if f[key] == k) for k in sorted({f[key] for f in findings})}  # noqa: E731
    counts = client.read("""MATCH (n) WHERE n:Supplier OR n:Invoice OR n:PurchaseOrder OR n:Shipment OR n:Investigation
                            RETURN labels(n)[0] AS label, count(n) AS n""")
    return {"entities": {c["label"]: c["n"] for c in counts}, "findings": len(findings),
            "findings_by_status": by("status"), "findings_by_rule": by("rule_id"), "findings_by_severity": by("severity")}


@app.get("/api/findings")
def findings(status: str | None = None, rule_id: str | None = None, include_inactive: bool = False):
    return repo.list_findings(status, rule_id, active_only=not include_inactive)


@app.get("/api/findings/{finding_id}")
def finding(finding_id: str):
    return repo.get_finding(finding_id) or _404("Finding")


@app.post("/api/findings/{finding_id}/review")
def review(finding_id: str, req: ReviewRequest, user: User = Depends(current_user)):
    try:
        return repo.record_review(finding_id, req.decision, user.name, req.note, req.investigation_id)
    except KeyError:
        _404("Finding")


@app.get("/api/investigations")
def investigations():
    return service.list_investigations()


@app.post("/api/investigations")
def create_investigation(req: InvestigationRequest, user: User = Depends(current_user)):
    try:
        return orchestrator.investigate(req.question, req.entity_id, user.name, req.use_llm)
    except (ValueError, LookupError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/api/investigations/{inv_id}")
def get_investigation(inv_id: str):
    return service.get_investigation(inv_id) or _404("Investigation")


@app.patch("/api/investigations/{inv_id}")
def update_investigation(inv_id: str, req: StatusRequest, user: User = Depends(current_user)):
    try:
        return service.set_status(inv_id, req.status, user.name)
    except KeyError:
        _404("Investigation")


@app.get("/api/investigations/{inv_id}/graph")
def investigation_graph(inv_id: str):
    return service.investigation_graph(inv_id)


@app.get("/api/investigations/{inv_id}/turns")
def turns(inv_id: str):
    return service.list_turns(inv_id)


@app.post("/api/investigations/{inv_id}/ask")
def ask(inv_id: str, req: AskRequest, _: User = Depends(current_user)):
    try:
        return orchestrator.ask(inv_id, req.question, req.use_llm)
    except KeyError:
        _404("Investigation")


@app.get("/api/investigations/{inv_id}/compare")
def compare(inv_id: str):
    inv = service.get_investigation(inv_id) or _404("Investigation")
    return service.compare_with_previous(inv["target_id"], exclude_investigation=inv_id)


@app.get("/api/entities/{entity_id}/prior")
def prior(entity_id: str):
    return service.prior_investigations(entity_id.upper())


@app.get("/api/suppliers")
def suppliers():
    return client.read("""MATCH (s:Supplier) OPTIONAL MATCH (s)-[:SUBMITTED]->(i:Invoice)
                          RETURN s.supplier_id AS supplier_id, s.name AS name, count(i) AS invoices
                          ORDER BY supplier_id""")
