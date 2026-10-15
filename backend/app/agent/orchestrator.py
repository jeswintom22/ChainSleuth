"""Investigation orchestrator.

The agent (LLM with tool calling) decides which validated tools to invoke. The orchestrator owns the
lifecycle and guarantees, regardless of what the model does:
  1. an investigation is opened through the deterministic detection + persistence path;
  2. policy evidence is retrieved per finding with fixed questions and stored with provenance;
  3. the final explanation passes the grounding validator or is replaced by the deterministic one.
Without an API key the same tool sequence runs deterministically.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from app.agent import grounding
from app.agent.explain import DISCLAIMER, generate_explanation
from app.agent.llm import chat, llm_available
from app.agent.tools import call_tool, tool_schemas
from app.graphrag.retriever import policy_question_for, retrieve_policy
from app.investigations import repository as repo
from app.investigations import service
from app.investigations.evidence import build_evidence_pack

log = logging.getLogger(__name__)
MAX_STEPS = 8
STATUS_RANK = {"graphrag": 3, "fallback": 2, "unavailable": 1}

AGENT_PROMPT = """You are ChainSleuth, a procurement investigation agent working on a FalkorDB graph.
You can only act through the provided tools; you cannot write queries.
For an investigation request:
1. resolve the entity and check prior investigations;
2. you MUST then call open_investigation exactly once for the target entity (this runs detection and persists findings);
3. optionally use other tools (network, reconciliation, policy search, compare_with_previous) for context the auditor
   explicitly asked about.
Only reply "DONE" (with no tool calls) after open_investigation has returned."""


class Trace:
    def __init__(self, current_investigation: str | None = None) -> None:
        self.steps: list[dict] = []
        self.current_investigation = current_investigation

    def call(self, name: str, args: dict, allow_writes: bool = True, actor: str = "orchestrator") -> Any:
        t = time.perf_counter()
        try:
            result = call_tool(name, args, allow_writes=allow_writes,
                               context={"current_investigation": self.current_investigation})
            if name == "open_investigation":
                self.current_investigation = result["investigation_id"]
            ok, err = True, None
        except Exception as e:
            result, ok, err = None, False, f"{type(e).__name__}: {e}"
        self.steps.append({"actor": actor, "tool": name, "args": args, "ok": ok, "error": err,
                           "ms": round((time.perf_counter() - t) * 1000, 1),
                           "result_preview": json.dumps(result, default=str)[:400] if ok else None})
        return result if ok else {"error": err}


def _agent_loop(messages: list[dict], trace: Trace, allow_writes: bool) -> list[dict]:
    """Run the tool-calling loop; returns the tool outputs gathered (for evidence)."""
    outputs = []
    for _ in range(MAX_STEPS):
        reply = chat(messages, tools=tool_schemas(allow_writes))
        if not reply["tool_calls"]:
            messages.append({"role": "assistant", "content": reply["content"]})
            break
        messages.append({"role": "assistant", "content": reply["content"] or None, "tool_calls": [
            {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}}
            for c in reply["tool_calls"]]})
        for c in reply["tool_calls"]:
            try:
                args = json.loads(c["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {"_invalid": c["arguments"]}
            result = trace.call(c["name"], args, allow_writes=allow_writes, actor="agent")
            outputs.append({"tool": c["name"], "args": args, "result": result})
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(result, default=str)[:12000]})
    return outputs


def _attach_policy(inv: dict, trace: Trace) -> tuple[list[dict], str, str]:
    """Fixed per-finding policy retrieval; passages are persisted as EvidenceChunk nodes (SUPPORTED_BY)."""
    by_chunk: dict[str, dict] = {}
    statuses, details = [], set()
    for f in inv["findings"]:
        q = policy_question_for(f["rule_id"], f["category"])
        t = time.perf_counter()
        res = retrieve_policy(q, k=2)
        trace.steps.append({"actor": "orchestrator", "tool": "retrieve_policy", "args": {"question": q,
                            "finding_id": f["finding_id"]}, "ok": True, "error": None, "status": res["status"],
                            "ms": round((time.perf_counter() - t) * 1000, 1)})
        statuses.append(res["status"])
        details.add(res["detail"])
        repo.attach_policy_evidence(f["finding_id"], [{**c, "method": c.get("method", res["status"])} for c in res["chunks"]])
        for c in res["chunks"]:
            entry = by_chunk.setdefault(c["chunk_id"], {**c, "finding_ids": []})
            entry["finding_ids"].append(f["finding_id"])
    status = min(statuses, key=lambda s: STATUS_RANK[s]) if statuses else "not_requested"
    return list(by_chunk.values()), status, "; ".join(sorted(details))


def investigate(question: str, entity_id: str | None = None, created_by: str = "auditor",
                use_llm: bool | None = None) -> dict:
    use_llm = llm_available() if use_llm is None else use_llm
    trace = Trace()
    entity_id = (entity_id or service.extract_entity_id(question) or "").upper() or None
    agent_outputs: list[dict] = []

    if use_llm:
        user = question + (f"\nTarget entity: {entity_id}" if entity_id else "")
        try:
            agent_outputs = _agent_loop([{"role": "system", "content": AGENT_PROMPT},
                                         {"role": "user", "content": user}], trace, allow_writes=True)
        except Exception as e:
            log.warning("Agent loop failed, continuing deterministically: %s", e)
            trace.steps.append({"actor": "orchestrator", "tool": "agent_loop", "ok": False, "error": str(e)})
    opened = [o["result"] for o in agent_outputs if o["tool"] == "open_investigation" and "investigation_id" in (o["result"] or {})]

    if not opened:  # deterministic plan (also the guarantee if the model skipped the step)
        if not entity_id:
            raise ValueError("An investigation needs a target entity (supplier, invoice, PO or shipment ID)")
        done = {(o["tool"], o["args"].get("entity_id")) for o in agent_outputs
                if isinstance(o["result"], list) or (isinstance(o["result"], dict) and o["result"].get("found", True)
                                                     and "error" not in o["result"])}
        if ("resolve_entity", entity_id) not in done:
            resolved = trace.call("resolve_entity", {"entity_id": entity_id})
            if not resolved.get("found"):
                raise LookupError(f"Unknown entity {entity_id}")
        if ("get_prior_investigations", entity_id) not in done:
            agent_outputs.append({"tool": "get_prior_investigations", "args": {"entity_id": entity_id},
                                  "result": trace.call("get_prior_investigations", {"entity_id": entity_id})})
        opened = [trace.call("open_investigation", {"entity_id": entity_id, "question": question})]
        if "error" in opened[0]:
            raise RuntimeError(opened[0]["error"])
    inv_id = opened[-1]["investigation_id"]

    inv = service.get_investigation(inv_id)
    policy, policy_status, policy_detail = _attach_policy(inv, trace)
    context = [o for o in agent_outputs if o["tool"] in ("get_prior_investigations", "compare_with_previous",
                                                          "search_policy", "get_supplier_network")]
    pack = build_evidence_pack(inv, policy, policy_status, agent_context=context)
    exp = generate_explanation(pack, use_llm=use_llm)
    exp["grounding"]["policy_detail"] = policy_detail
    service.save_explanation(inv_id, exp["text"], exp["mode"], exp["grounding"], policy, policy_status, trace.steps)
    return service.get_investigation(inv_id)


ASK_PROMPT = """You answer an auditor's follow-up question about one persisted investigation.
Use ONLY the evidence pack and tool results. You may call read-only tools for more graph context.
Rules: cite record IDs and numbers only if they appear in the evidence or tool results; never compute new numbers;
never use the words fraud, fraudulent, guilt, criminal, proof or prove; never claim payments are blocked;
if the evidence does not answer the question, say so. Plain text, at most 150 words, "-" bullets allowed."""


def ask(inv_id: str, question: str, use_llm: bool | None = None) -> dict:
    inv = service.get_investigation(inv_id)
    if inv is None:
        raise KeyError(inv_id)
    pack = build_evidence_pack(inv)
    use_llm = llm_available() if use_llm is None else use_llm
    trace = Trace(current_investigation=inv_id)
    if use_llm:
        messages = [{"role": "system", "content": ASK_PROMPT},
                    {"role": "user", "content": f"Evidence pack:\n{json.dumps(pack, default=str)}\n\nQuestion: {question}"}]
        try:
            outputs = _agent_loop(messages, trace, allow_writes=False)
            answer = messages[-1].get("content") or ""
            report = grounding.validate(answer, pack, outputs)
            if report["supported"] and answer:
                turn = service.save_turn(inv_id, question, answer, True, "llm_grounded", trace.steps)
                return {**turn, "grounding": report}
            rejected = report
        except Exception as e:
            rejected = {"error": f"{type(e).__name__}: {e}"}
    else:
        rejected = None
    answer = ("I can only answer from the recorded evidence. Findings in this investigation:\n" +
              "\n".join(f"- {f['finding_id']} ({f['rule_id']}): {f['summary']}" for f in pack["findings"]) +
              f"\n\n{DISCLAIMER}")
    turn = service.save_turn(inv_id, question, answer, True, "deterministic" if not use_llm else "deterministic_fallback",
                             trace.steps)
    return {**turn, "grounding": grounding.validate(answer, pack), "rejected": rejected}
