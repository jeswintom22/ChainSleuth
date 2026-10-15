"""Investigation lifecycle: scope by graph traversal, run detection, persist, link findings."""
from __future__ import annotations

import json
import re
import uuid

from app.config import settings
from app.detection.engine import run_all
from app.graph.client import read, write
from app.graph.queries import run_named
from app.investigations import repository as repo
from app.scoring import investigation_score

ENTITY_RE = re.compile(r"\b(?:SUP|INV|PO|SHP)-\d+\b", re.IGNORECASE)


def extract_entity_id(text: str) -> str | None:
    m = ENTITY_RE.search(text or "")
    return m.group(0).upper() if m else None


def run_detection() -> dict:
    signals, timings = run_all()
    result = repo.persist_signals(signals, timings)
    result["timings_ms"] = timings
    return result


def compute_scope(entity_id: str) -> dict:
    """Traverse from the target entity to its supplier, then to suppliers linked by a shared
    (non-intermediary) payout account or a shared owner, then to their invoices, POs and shipments."""
    label = run_named("resolve_entity", id=entity_id)
    if not label:
        raise LookupError(f"Unknown entity {entity_id}")
    roots = [r["supplier_id"] for r in run_named("entity_supplier", id=entity_id)]
    network = [run_named("supplier_network", supplier_id=s)[0] for s in roots]
    suppliers = sorted(set(roots) | {x for n in network for x in n["account_linked"] + n["owner_linked"]})
    activity = run_named("supplier_activity", supplier_ids=suppliers)
    return {
        "target_id": entity_id, "target_label": label[0]["label"], "root_suppliers": roots,
        "suppliers": suppliers, "network": network,
        "invoice_ids": sorted({i for a in activity for i in a["invoice_ids"]}),
        "po_ids": sorted({p for a in activity for p in a["po_ids"]}),
        "shipment_ids": sorted({s for a in activity for s in a["shipment_ids"]}),
    }


def open_investigation(question: str, entity_id: str | None = None, created_by: str = "auditor",
                       rerun_detection: bool = True) -> dict:
    entity_id = (entity_id or extract_entity_id(question) or "").upper()
    if not entity_id:
        raise ValueError("An investigation needs a target entity (supplier, invoice, PO or shipment ID)")
    if rerun_detection:
        run_detection()
    scope = compute_scope(entity_id)
    findings = repo.findings_in_scope(scope["suppliers"], scope["invoice_ids"], scope["po_ids"], scope["shipment_ids"])
    score = investigation_score(findings)
    inv_id = "INVG-" + uuid.uuid4().hex[:8].upper()
    ts = repo.now()
    key = repo.NODE_KEYS[scope["target_label"]]
    write(f"""CREATE (i:Investigation {{investigation_id: $id, question: $q, target_id: $t, target_label: $tl,
                                       status: 'open', created_at: $ts, updated_at: $ts, created_by: $by,
                                       score: $score, severity: $sev, score_json: $score_json, scope_json: $scope,
                                       dataset_version: $dv, policy_status: 'not_requested'}})
              WITH i MATCH (n:{scope['target_label']} {{{key}: $t}}) MERGE (i)-[:FOCUSES_ON]->(n)
              WITH i UNWIND $fids AS fid MATCH (f:Finding {{finding_id: fid}}) MERGE (i)-[:CONTAINS]->(f)""",
          {"id": inv_id, "q": question, "t": entity_id, "tl": scope["target_label"], "ts": ts, "by": created_by,
           "score": score["score"], "sev": score["severity"], "score_json": json.dumps(score),
           "scope": json.dumps(scope, default=str), "dv": settings.dataset_version,
           "fids": [f["finding_id"] for f in findings]})
    # Cross-session continuity: link earlier investigations that touched the same findings or target.
    write("""MATCH (cur:Investigation {investigation_id: $id})
             MATCH (prev:Investigation) WHERE prev.investigation_id <> $id AND prev.created_at <= cur.created_at
               AND (prev.target_id = cur.target_id OR (prev)-[:CONTAINS]->(:Finding)<-[:CONTAINS]-(cur))
             MERGE (prev)-[:FOLLOWED_BY]->(cur)""", {"id": inv_id})
    return get_investigation(inv_id)


def _inv_props(node) -> dict:
    p = dict(node.properties)
    p["score_detail"] = json.loads(p.pop("score_json", "{}") or "{}")
    p["scope"] = json.loads(p.pop("scope_json", "{}") or "{}")
    p["grounding"] = json.loads(p.pop("grounding_json", "null") or "null")
    p["policy_evidence"] = json.loads(p.pop("policy_json", "[]") or "[]")
    p["tool_trace"] = json.loads(p.pop("tool_trace_json", "[]") or "[]")
    return p


def get_investigation(inv_id: str) -> dict | None:
    res = read("MATCH (i:Investigation {investigation_id: $id}) RETURN i", {"id": inv_id})
    if not res:
        return None
    inv = _inv_props(res[0]["i"])
    fids = [r["id"] for r in read(
        "MATCH (:Investigation {investigation_id: $id})-[:CONTAINS]->(f:Finding) RETURN f.finding_id AS id", {"id": inv_id})]
    inv["findings"] = sorted((repo.get_finding(f) for f in fids), key=lambda f: (-f["score"], f["finding_id"]))
    # Score is recomputed from current reviewer state (dismissed findings drop out) and kept in sync.
    live = investigation_score(inv["findings"])
    inv["score_detail"], inv["score"], inv["severity"] = live, live["score"], live["severity"]
    inv["history"] = {
        "previous": [r["i"].properties for r in read(
            """MATCH (p:Investigation)-[:FOLLOWED_BY]->(:Investigation {investigation_id: $id})
               RETURN p AS i ORDER BY p.created_at""", {"id": inv_id})],
        "next": [r["i"].properties for r in read(
            """MATCH (:Investigation {investigation_id: $id})-[:FOLLOWED_BY]->(n:Investigation)
               RETURN n AS i ORDER BY n.created_at""", {"id": inv_id})],
    }
    for k in ("previous", "next"):
        inv["history"][k] = [{x: h.get(x) for x in ("investigation_id", "question", "status", "created_at", "score")}
                             for h in inv["history"][k]]
    return inv


def list_investigations() -> list[dict]:
    res = read("""MATCH (i:Investigation) OPTIONAL MATCH (i)-[:CONTAINS]->(f:Finding)
                  RETURN i.investigation_id AS investigation_id, i.question AS question, i.target_id AS target_id,
                         i.status AS status, i.created_at AS created_at, i.score AS score, i.severity AS severity,
                         count(f) AS finding_count
                  ORDER BY created_at DESC""")
    return res


def set_status(inv_id: str, status: str, reviewer: str) -> dict:
    if status not in repo.INVESTIGATION_STATUSES:
        raise ValueError(f"status must be one of {sorted(repo.INVESTIGATION_STATUSES)}")
    res = write("""MATCH (i:Investigation {investigation_id: $id})
                   SET i.status = $s, i.updated_at = $ts, i.status_by = $r RETURN i.investigation_id AS id""",
                {"id": inv_id, "s": status, "ts": repo.now(), "r": reviewer})
    if not res:
        raise KeyError(inv_id)
    return get_investigation(inv_id)


def save_explanation(inv_id: str, text: str, mode: str, grounding: dict, policy: list[dict],
                     policy_status: str, tool_trace: list[dict] | None = None) -> None:
    write("""MATCH (i:Investigation {investigation_id: $id})
             SET i.explanation = $text, i.explanation_mode = $mode, i.grounding_json = $g, i.policy_json = $p,
                 i.policy_status = $ps, i.tool_trace_json = $tt, i.updated_at = $ts""",
          {"id": inv_id, "text": text, "mode": mode, "g": json.dumps(grounding), "p": json.dumps(policy),
           "ps": policy_status, "tt": json.dumps(tool_trace or [], default=str), "ts": repo.now()})


def prior_investigations(entity_id: str) -> list[dict]:
    """Earlier investigations focused on, or containing findings involving, this entity."""
    return read("""MATCH (i:Investigation)
                   WHERE i.target_id = $id OR (i)-[:CONTAINS]->(:Finding)-[:INVOLVES]->({supplier_id: $id})
                      OR (i)-[:CONTAINS]->(:Finding)-[:INVOLVES]->({invoice_id: $id})
                   RETURN i.investigation_id AS investigation_id, i.question AS question, i.status AS status,
                          i.created_at AS created_at, i.score AS score, i.target_id AS target_id
                   ORDER BY created_at DESC""", {"id": entity_id})


def compare_with_previous(entity_id: str, exclude_investigation: str | None = None) -> dict:
    """What has changed since the most recent earlier investigation of this entity?"""
    prior = [p for p in prior_investigations(entity_id) if p["investigation_id"] != exclude_investigation]
    if not prior:
        return {"entity_id": entity_id, "has_previous": False}
    prev = prior[0]
    prev_findings = read("""MATCH (:Investigation {investigation_id: $id})-[:CONTAINS]->(f:Finding)
                            RETURN f.finding_id AS finding_id, f.rule_id AS rule_id, f.status AS status,
                                   f.active AS active, f.evidence_summary AS summary""", {"id": prev["investigation_id"]})
    scope = compute_scope(entity_id)
    current = repo.findings_in_scope(scope["suppliers"], scope["invoice_ids"], scope["po_ids"], scope["shipment_ids"])
    prev_ids = {f["finding_id"] for f in prev_findings}
    return {
        "entity_id": entity_id, "has_previous": True, "previous_investigation": prev,
        "new_findings": [{"finding_id": f["finding_id"], "rule_id": f["rule_id"], "summary": f["evidence_summary"],
                          "created_at": f["created_at"]} for f in current if f["finding_id"] not in prev_ids],
        "previous_findings": prev_findings,
        "no_longer_detected": [f["finding_id"] for f in prev_findings if not f["active"]],
    }


def save_turn(inv_id: str, question: str, answer: str, grounded: bool, mode: str, trace: list[dict]) -> dict:
    turn = {"turn_id": "TURN-" + uuid.uuid4().hex[:8], "question": question, "answer": answer, "grounded": grounded,
            "mode": mode, "created_at": repo.now(), "trace_json": json.dumps(trace, default=str)}
    write("""MATCH (i:Investigation {investigation_id: $id})
             CREATE (i)-[:HAS_TURN]->(t:AgentTurn) SET t = $turn""", {"id": inv_id, "turn": turn})
    return turn


def list_turns(inv_id: str) -> list[dict]:
    res = read("""MATCH (:Investigation {investigation_id: $id})-[:HAS_TURN]->(t:AgentTurn)
                  RETURN t ORDER BY t.created_at, t.turn_id""", {"id": inv_id})
    out = []
    for r in res:
        p = dict(r["t"].properties)
        p["trace"] = json.loads(p.pop("trace_json", "[]"))
        out.append(p)
    return out


def investigation_graph(inv_id: str) -> dict:
    """Nodes/edges for visualisation: findings, the entities they involve, and real graph edges among them."""
    ent = read("""MATCH (:Investigation {investigation_id: $id})-[:CONTAINS]->(f:Finding)-[:INVOLVES]->(n)
                  RETURN f.finding_id AS fid, f.rule_id AS rule, labels(n)[0] AS label,
                         coalesce(n.supplier_id, n.invoice_id, n.po_id, n.shipment_id, n.account_ref, n.owner_id,
                                  n.product_id, n.warehouse_id) AS key, n.name AS name""", {"id": inv_id})
    keys = sorted({e["key"] for e in ent})
    edges = read("""MATCH (a)-[r]->(b)
                    WHERE coalesce(a.supplier_id, a.invoice_id, a.po_id, a.shipment_id, a.account_ref, a.owner_id,
                                   a.product_id, a.warehouse_id) IN $keys
                      AND coalesce(b.supplier_id, b.invoice_id, b.po_id, b.shipment_id, b.account_ref, b.owner_id,
                                   b.product_id, b.warehouse_id) IN $keys
                      AND NOT a:Finding AND NOT b:Finding
                    RETURN DISTINCT coalesce(a.supplier_id, a.invoice_id, a.po_id, a.shipment_id, a.account_ref,
                                             a.owner_id, a.product_id, a.warehouse_id) AS source, type(r) AS type,
                           coalesce(b.supplier_id, b.invoice_id, b.po_id, b.shipment_id, b.account_ref, b.owner_id,
                                    b.product_id, b.warehouse_id) AS target""", {"keys": keys})
    nodes = {e["key"]: {"id": e["key"], "label": e["label"], "name": e["name"]} for e in ent}
    for e in ent:
        nodes[e["fid"]] = {"id": e["fid"], "label": "Finding", "name": e["rule"]}
    return {"nodes": list(nodes.values()),
            "edges": edges + [{"source": e["fid"], "type": "INVOLVES", "target": e["key"]} for e in ent]}
