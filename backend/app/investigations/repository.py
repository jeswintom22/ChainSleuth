"""Persistence of findings, rules, investigations and reviewer decisions in FalkorDB.

All write Cypher is fixed here; only parameters vary.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.detection.base import RULES, Signal
from app.graph.client import read, write
from app.graph.schema import NODE_KEYS
from app.scoring import severity

INVOLVABLE = ["Supplier", "Invoice", "PurchaseOrder", "Shipment", "BankAccount", "Owner", "Product", "Warehouse"]
FINDING_STATUSES = {"open", "needs_review", "confirmed", "dismissed"}
INVESTIGATION_STATUSES = {"open", "in_review", "closed"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def finding_id_for(rule_id: str, subject_key: str) -> str:
    """Stable ID: the same rule hit on the same subject always maps to the same Finding node."""
    return "F-" + hashlib.sha1(f"{rule_id}|{subject_key}".encode()).hexdigest()[:12]


def upsert_rules() -> None:
    for r in RULES.values():
        write("""MERGE (d:DetectionRule {rule_key: $key})
                 SET d.rule_id = $rid, d.version = $ver, d.title = $title, d.description = $desc,
                     d.config_json = $cfg, d.queries = $queries""",
              {"key": r.rule_key, "rid": r.rule_id, "ver": r.version, "title": r.title, "desc": r.description,
               "cfg": json.dumps(r.config, sort_keys=True), "queries": list(r.query_names)})


def persist_signals(signals: list[Signal], timings: dict | None = None) -> dict[str, Any]:
    """Upsert one Finding per signal. Re-running on unchanged data creates no new nodes or edges.
    Reviewer status is set only on creation, so detection never overwrites a human decision."""
    upsert_rules()
    ts, run_id = now(), "RUN-" + uuid.uuid4().hex[:10]
    write("CREATE (:DetectionRun {run_id: $id, started_at: $ts, signal_count: $n, timings_json: $t, dataset_version: $dv})",
          {"id": run_id, "ts": ts, "n": len(signals), "t": json.dumps(timings or {}), "dv": settings.dataset_version})
    ids, created = [], 0
    for s in signals:
        fid = finding_id_for(s.rule_id, s.subject_key)
        ids.append(fid)
        res = write(
            """MERGE (f:Finding {finding_id: $fid})
               ON CREATE SET f.created_at = $ts, f.status = 'open', f.is_new = true
               ON MATCH SET f.is_new = false
               SET f.rule_id = $rule_id, f.rule_version = $ver, f.subject_key = $subject, f.category = $cat,
                   f.score = $score, f.severity = $sev, f.last_evaluated_at = $ts, f.dataset_version = $dv,
                   f.evidence_summary = $summary, f.values_json = $values, f.record_ids_json = $records,
                   f.evidence_paths = $paths, f.query_json = $query, f.active = true
               WITH f
               MATCH (d:DetectionRule {rule_key: $rule_key})
               MERGE (f)-[:TRIGGERED_BY]->(d)
               WITH f
               MATCH (run:DetectionRun {run_id: $run})
               MERGE (run)-[:PRODUCED]->(f)
               RETURN f.is_new AS is_new""",
            {"fid": fid, "ts": ts, "rule_id": s.rule_id, "ver": s.rule.version, "subject": s.subject_key,
             "cat": s.category, "score": s.points, "sev": severity(s.points), "dv": settings.dataset_version,
             "summary": s.summary, "values": json.dumps(s.values, sort_keys=True, default=str),
             "records": json.dumps(s.record_ids, sort_keys=True), "paths": s.evidence_paths,
             "query": json.dumps(s.query, sort_keys=True), "rule_key": s.rule.rule_key, "run": run_id})
        created += bool(res and res[0]["is_new"])
        for label in INVOLVABLE:
            if s.record_ids.get(label):
                write(f"""MATCH (f:Finding {{finding_id: $fid}})
                          UNWIND $ids AS rid
                          MATCH (n:{label} {{{NODE_KEYS[label]}: rid}})
                          MERGE (f)-[:INVOLVES]->(n)""", {"fid": fid, "ids": s.record_ids[label]})
    # Findings not reproduced by this run are marked inactive (the underlying data changed); never deleted.
    write("MATCH (f:Finding) WHERE NOT f.finding_id IN $ids SET f.active = false", {"ids": ids})
    write("""MATCH (f1:Finding)-[:INVOLVES]->(n)<-[:INVOLVES]-(f2:Finding)
             WHERE f1.finding_id < f2.finding_id AND (n:Invoice OR n:BankAccount OR n:PurchaseOrder)
             MERGE (f1)-[:RELATED_TO]->(f2)""")
    return {"run_id": run_id, "signals": len(signals), "new_findings": created, "finding_ids": ids}


def _finding_row(f) -> dict:
    p = f.properties if hasattr(f, "properties") else f
    return {**{k: v for k, v in p.items() if not k.endswith("_json")},
            "values": json.loads(p.get("values_json") or "{}"),
            "record_ids": json.loads(p.get("record_ids_json") or "{}"),
            "query": json.loads(p.get("query_json") or "{}")}


def list_findings(status: str | None = None, rule_id: str | None = None, active_only: bool = True) -> list[dict]:
    res = read("""MATCH (f:Finding)
                  WHERE ($status IS NULL OR f.status = $status) AND ($rule IS NULL OR f.rule_id = $rule)
                    AND ($active = false OR f.active = true)
                  RETURN f ORDER BY f.score DESC, f.finding_id""",
               {"status": status, "rule": rule_id, "active": active_only})
    return [_finding_row(r["f"]) for r in res]


def get_finding(finding_id: str) -> dict | None:
    res = read("MATCH (f:Finding {finding_id: $id}) RETURN f", {"id": finding_id})
    if not res:
        return None
    out = _finding_row(res[0]["f"])
    out["reviews"] = [r["a"].properties for r in read(
        "MATCH (:Finding {finding_id: $id})-[:HAS_REVIEW]->(a:ReviewAction) RETURN a ORDER BY a.created_at", {"id": finding_id})]
    out["policy_evidence"] = [r["c"].properties for r in read(
        "MATCH (:Finding {finding_id: $id})-[:SUPPORTED_BY]->(c:EvidenceChunk) RETURN c ORDER BY c.chunk_id", {"id": finding_id})]
    out["related"] = [r["id"] for r in read(
        "MATCH (:Finding {finding_id: $id})-[:RELATED_TO]-(o:Finding) RETURN DISTINCT o.finding_id AS id ORDER BY id",
        {"id": finding_id})]
    return out


def findings_in_scope(supplier_ids: list[str], invoice_ids: list[str], po_ids: list[str], shipment_ids: list[str]) -> list[dict]:
    res = read("""MATCH (f:Finding)-[:INVOLVES]->(n)
                  WHERE f.active = true AND ((n:Supplier AND n.supplier_id IN $s) OR (n:Invoice AND n.invoice_id IN $i)
                     OR (n:PurchaseOrder AND n.po_id IN $p) OR (n:Shipment AND n.shipment_id IN $sh))
                  RETURN DISTINCT f ORDER BY f.score DESC, f.finding_id""",
               {"s": supplier_ids, "i": invoice_ids, "p": po_ids, "sh": shipment_ids})
    return [_finding_row(r["f"]) for r in res]


def record_review(finding_id: str, decision: str, reviewer: str, note: str = "", investigation_id: str | None = None) -> dict:
    if decision not in FINDING_STATUSES:
        raise ValueError(f"decision must be one of {sorted(FINDING_STATUSES)}")
    if not reviewer.strip():
        raise ValueError("reviewer is required")
    aid = "RA-" + uuid.uuid4().hex[:10]
    res = write("""MATCH (f:Finding {finding_id: $fid})
                   WITH f, f.status AS previous
                   CREATE (a:ReviewAction {action_id: $aid, decision: $d, reviewer: $r, note: $note,
                                           created_at: $ts, previous_status: previous, investigation_id: $inv})
                   CREATE (f)-[:HAS_REVIEW]->(a)
                   SET f.status = $d, f.reviewed_by = $r, f.reviewed_at = $ts
                   RETURN previous""",
                {"fid": finding_id, "aid": aid, "d": decision, "r": reviewer, "note": note, "ts": now(),
                 "inv": investigation_id})
    if not res:
        raise KeyError(finding_id)
    return {"action_id": aid, "finding_id": finding_id, "previous_status": res[0]["previous"], "status": decision}


def attach_policy_evidence(finding_id: str, chunks: list[dict]) -> None:
    """Copy retrieved document passages into the operational graph with provenance, linked SUPPORTED_BY."""
    for c in chunks:
        write("""MATCH (f:Finding {finding_id: $fid})
                 MERGE (c:EvidenceChunk {chunk_id: $cid})
                 SET c.document_id = $doc, c.text = $text, c.section = $section, c.source = $source,
                     c.retrieval_method = $method
                 MERGE (f)-[:SUPPORTED_BY]->(c)""",
              {"fid": finding_id, "cid": c["chunk_id"], "doc": c["document_id"], "text": c["text"],
               "section": c.get("section", ""), "source": c.get("source", ""), "method": c.get("method", "")})
