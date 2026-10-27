"""Validated investigation tools exposed to the agent.

Each tool wraps a named, reviewed query or detection function. The agent can choose WHICH tool to
call and with which entity ID, but it can never supply Cypher. Arguments are validated against the
declared schema and an ID pattern before execution.
"""
from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any, Callable

from app.detection.base import Signal
from app.detection.duplicate_invoice import detect_duplicate_invoices
from app.detection.reconciliation import detect_reconciliation
from app.detection.route_anomaly import detect_route_anomalies
from app.detection.supplier_network import detect_shared_accounts
from app.graph.queries import run_named
from app.graphrag.retriever import retrieve_policy
from app.investigations import service

ID_PATTERNS = {"supplier_id": r"SUP-\d{3}", "invoice_id": r"INV-\d{4}", "po_id": r"PO-\d{4}",
               "shipment_id": r"SHP-\d{4}", "entity_id": r"(SUP-\d{3}|INV-\d{4}|PO-\d{4}|SHP-\d{4})"}


def _sig(s: Signal) -> dict:
    d = asdict(s)
    d["rule_version"] = s.rule.version
    d.pop("query", None)
    return d


def resolve_entity(entity_id: str) -> dict:
    label = run_named("resolve_entity", id=entity_id)
    if not label:
        return {"entity_id": entity_id, "found": False}
    return {"entity_id": entity_id, "found": True, "label": label[0]["label"],
            "supplier_ids": [r["supplier_id"] for r in run_named("entity_supplier", id=entity_id)]}


def get_supplier_network(supplier_id: str) -> dict:
    rows = run_named("supplier_network", supplier_id=supplier_id)
    return rows[0] if rows else {"supplier_id": supplier_id, "found": False}


def check_shared_accounts(supplier_id: str) -> list[dict]:
    return [_sig(s) for s in detect_shared_accounts(supplier_id)]


def check_duplicate_invoices(invoice_id: str) -> list[dict]:
    return [_sig(s) for s in detect_duplicate_invoices(invoice_id)]


def reconcile_invoice(invoice_id: str) -> dict:
    ctx = run_named("invoice_context", invoice_id=invoice_id)
    if not ctx:
        return {"invoice_id": invoice_id, "found": False}
    po = ctx[0]["po_id"]
    sigs = detect_reconciliation(po_ids=[po]) if po else []
    sigs += detect_reconciliation(invoice_ids=[invoice_id]) if not po else []
    return {"invoice": ctx[0], "signals": [_sig(s) for s in sigs],
            "reconciled_without_exception": not sigs}


def check_routes(po_id: str) -> list[dict]:
    shipments = [r["shipment_id"] for r in run_named("recon_shipped_lines", po_ids=[po_id])]
    return [_sig(s) for s in detect_route_anomalies(sorted(set(shipments)))] if shipments else []


def get_prior_investigations(entity_id: str) -> list[dict]:
    return service.prior_investigations(entity_id)


def compare_with_previous(entity_id: str, *, current_investigation: str | None = None) -> dict:
    return service.compare_with_previous(entity_id, exclude_investigation=current_investigation)


def search_policy(question: str) -> dict:
    return retrieve_policy(question[:300], k=3)


def open_investigation(entity_id: str, question: str, created_by: str = "auditor") -> dict:
    inv = service.open_investigation(question[:500], entity_id=entity_id, created_by=created_by)
    return {"investigation_id": inv["investigation_id"], "score": inv["score"], "severity": inv["severity"],
            "findings": [{"finding_id": f["finding_id"], "rule_id": f["rule_id"], "summary": f["evidence_summary"]}
                         for f in inv["findings"]]}


def _schema(name: str, desc: str, props: dict[str, str], required: list[str]) -> dict:
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {
        "type": "object", "properties": {p: {"type": "string", "description": d} for p, d in props.items()},
        "required": required, "additionalProperties": False}}}


TOOLS: dict[str, tuple[Callable[..., Any], dict, bool]] = {
    # name: (function, schema, writes_to_graph)
    "resolve_entity": (resolve_entity, _schema("resolve_entity", "Identify what kind of record an ID is and its supplier.",
                                               {"entity_id": "SUP-xxx, INV-xxxx, PO-xxxx or SHP-xxxx"}, ["entity_id"]), False),
    "get_supplier_network": (get_supplier_network, _schema(
        "get_supplier_network", "Suppliers linked to this supplier via a shared payout account or shared owner.",
        {"supplier_id": "SUP-xxx"}, ["supplier_id"]), False),
    "check_shared_accounts": (check_shared_accounts, _schema(
        "check_shared_accounts", "Run rule R1 (shared payout accounts) for one supplier.", {"supplier_id": "SUP-xxx"},
        ["supplier_id"]), False),
    "check_duplicate_invoices": (check_duplicate_invoices, _schema(
        "check_duplicate_invoices", "Run rule R2 (exact duplicate invoice fingerprint) for one invoice.",
        {"invoice_id": "INV-xxxx"}, ["invoice_id"]), False),
    "reconcile_invoice": (reconcile_invoice, _schema(
        "reconcile_invoice", "Run rule R3: compare billed, ordered and delivered quantities for the invoice's PO.",
        {"invoice_id": "INV-xxxx"}, ["invoice_id"]), False),
    "check_routes": (check_routes, _schema(
        "check_routes", "Run rule R4: unapproved warehouse transitions on shipments of a PO.", {"po_id": "PO-xxxx"},
        ["po_id"]), False),
    "get_prior_investigations": (get_prior_investigations, _schema(
        "get_prior_investigations", "Earlier persisted investigations about an entity (cross-session memory).",
        {"entity_id": "SUP-xxx, INV-xxxx, PO-xxxx or SHP-xxxx"}, ["entity_id"]), False),
    "compare_with_previous": (compare_with_previous, _schema(
        "compare_with_previous", "Compare current findings for an entity with its most recent prior investigation.",
        {"entity_id": "SUP-xxx, INV-xxxx, PO-xxxx or SHP-xxxx"}, ["entity_id"]), False),
    "search_policy": (search_policy, _schema(
        "search_policy", "Retrieve synthetic procurement policy passages relevant to a question.",
        {"question": "natural-language policy question"}, ["question"]), False),
    "open_investigation": (open_investigation, _schema(
        "open_investigation", "Run all detection rules, persist findings and open a scored investigation for an entity.",
        {"entity_id": "SUP-xxx, INV-xxxx, PO-xxxx or SHP-xxxx", "question": "the auditor's question"},
        ["entity_id", "question"]), True),
}


# Orchestrator-supplied context (never settable by the model), e.g. the investigation opened in this session.
CONTEXT_PARAMS = {"compare_with_previous": ("current_investigation",), "open_investigation": ("created_by",)}


def call_tool(name: str, args: dict, allow_writes: bool = True, context: dict | None = None) -> Any:
    if name not in TOOLS:
        raise ValueError(f"Unknown tool {name}")
    fn, schema, writes = TOOLS[name]
    if writes and not allow_writes:
        raise PermissionError(f"Tool {name} is not allowed in this context")
    params = schema["function"]["parameters"]
    if set(args) - set(params["properties"]) or set(params["required"]) - set(args):
        raise ValueError(f"Invalid arguments for {name}: {sorted(args)}")
    clean = {}
    for k, v in args.items():
        if not isinstance(v, str):
            raise ValueError(f"{k} must be a string")
        v = v.strip()
        if k in ID_PATTERNS:
            v = v.upper()
            if not re.fullmatch(ID_PATTERNS[k], v):
                raise ValueError(f"{k} has invalid format: {v!r}")
        clean[k] = v
    extra = {k: v for k, v in (context or {}).items() if k in CONTEXT_PARAMS.get(name, ())}
    return fn(**clean, **extra)


def tool_schemas(allow_writes: bool = True) -> list[dict]:
    return [schema for _, (fn, schema, writes) in TOOLS.items() if allow_writes or not writes]
