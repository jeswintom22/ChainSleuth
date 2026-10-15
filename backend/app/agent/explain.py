"""Explanations built from an evidence pack: deterministic template, or LLM text gated by grounding."""
from __future__ import annotations

import json
import logging

from app.agent import grounding
from app.agent.llm import chat, llm_available

log = logging.getLogger(__name__)

DISCLAIMER = ("These are risk signals that recommend human review. They are not a determination of wrongdoing, "
              "and ChainSleuth does not approve, hold or release payments.")

SYSTEM_PROMPT = """You write audit investigation summaries for procurement reviewers.
Use ONLY the JSON evidence pack provided. Strict rules:
- Mention record IDs (suppliers, invoices, POs, shipments, accounts, products, findings, policy documents) only if they appear in the pack.
- Mention quantities, amounts, scores and other numbers only if they appear in the pack. Do not compute new numbers.
- Do not use the words fraud, fraudulent, guilt, criminal, proof or prove. Do not claim payments are blocked or stopped.
- Describe findings as review signals and recommend human review.
- When citing policy, cite the document_id and section from policy_evidence. If policy_status is "unavailable", say that document evidence is unavailable.
- Use short paragraphs or "-" bullets, no numbered lists, at most 220 words. Plain text, no markdown headings."""


def deterministic_explanation(pack: dict) -> str:
    s = pack["score"]
    lines = [f"Investigation {pack['investigation_id']} for {pack['target']['label']} {pack['target']['id']}.",
             f"Review priority: {s['severity']} (score {s['score']} of {s['score_cap']}, "
             f"from {len(pack['findings'])} finding(s))."]
    if not pack["findings"]:
        lines.append("No detection rule produced a finding for this entity or its connected suppliers.")
    for f in pack["findings"]:
        lines.append(f"- {f['finding_id']} [{f['rule_id']} v{f['rule_version']}, {f['points']} points, status {f['status']}]: "
                     f"{f['summary']}.")
        for p in f["evidence_paths"][:3]:
            lines.append(f"    path: {p}")
    if pack["policy_evidence"]:
        lines.append("Policy context:")
        for c in pack["policy_evidence"]:
            first = c["text"].split(". ")[0].rstrip(".")
            lines.append(f"- {c['document_id']} / {c['section']}: \"{first}.\"")
    elif pack["policy_status"] in ("unavailable", "error"):
        lines.append("Document evidence is unavailable for this investigation.")
    if pack["findings"]:
        lines.append("Recommendation: route the listed records to a procurement reviewer before any payment decision.")
    return "\n".join(lines)


def generate_explanation(pack: dict, use_llm: bool | None = None) -> dict:
    """Returns {"text", "mode", "grounding"}. LLM output is accepted only if fully grounded; otherwise
    one corrective retry, then the deterministic explanation is used and the rejection is recorded."""
    use_llm = llm_available() if use_llm is None else use_llm
    rejected = []
    if use_llm:
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": "Evidence pack:\n" + json.dumps(pack, default=str)}]
        for _attempt in range(2):
            try:
                text = chat(messages)["content"].strip()
            except Exception as e:
                log.warning("LLM explanation failed: %s", e)
                rejected.append({"error": f"{type(e).__name__}: {e}"})
                break
            report = grounding.validate(text, pack)
            if report["supported"]:
                return {"text": f"{text}\n\n{DISCLAIMER}", "mode": "llm_grounded",
                        "grounding": {**report, "rejected_attempts": rejected}}
            rejected.append({"text": text, **report})
            messages += [{"role": "assistant", "content": text},
                         {"role": "user", "content": "Your summary contains content not supported by the pack: "
                          f"ids={report['unsupported_ids']} numbers={report['unsupported_numbers']} "
                          f"banned={report['banned_phrases']}. Rewrite it using only pack content."}]
    text = deterministic_explanation(pack)
    report = grounding.validate(text, pack)
    mode = "deterministic_fallback" if use_llm else "deterministic"
    return {"text": f"{text}\n\n{DISCLAIMER}", "mode": mode, "grounding": {**report, "rejected_attempts": rejected}}
