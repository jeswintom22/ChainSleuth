"""Grounding validator: every record ID and number in a generated text must appear in the evidence.

Checks (deterministic, no LLM):
  * record-style IDs (e.g. INV-1043, SUP-010, PP-100, F-8578f4e3d45e) must occur in the evidence pack;
  * numbers (quantities, amounts, scores) must occur in the evidence pack;
  * the generated body must not characterise the case as fraud, guilt or proof, or claim to block payment.
Limitations: numbers written as words ("forty") are not checked.
"""
from __future__ import annotations

import json
import re

ID_RE = re.compile(r"\b[A-Z]{1,4}-(?=[A-Za-z0-9-]*\d)[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*\b")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:T[\d:+]+)?\b")
LIST_MARKER_RE = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)
NUM_RE = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])\d+(?:\.\d+)?")
BANNED_RE = re.compile(r"\bfraud\w*|\bguilt\w*|\bcriminal\w*|\bprove[sdn]?\b|\bproof\b|\bembezzl\w*|"
                       r"\bblock(?:ed|ing|s)?\s+(?:the\s+)?payments?\b|\bstop(?:ped|ping|s)?\s+(?:the\s+)?payments?\b",
                       re.IGNORECASE)


def _numbers(text: str) -> set[float]:
    text = DATE_RE.sub(" ", ID_RE.sub(" ", text))
    return {round(float(n.replace(",", "")), 2) for n in NUM_RE.findall(text)}


def _pack_text(pack: dict) -> str:
    return json.dumps(pack, default=str)


def validate(text: str, pack: dict, extra_evidence: list | None = None) -> dict:
    corpus = _pack_text(pack) + " " + json.dumps(extra_evidence or [], default=str)
    allowed_ids = set(ID_RE.findall(corpus))
    allowed_nums = _numbers(corpus)
    body = LIST_MARKER_RE.sub(" ", text)
    ids = sorted(set(ID_RE.findall(body)))
    nums = sorted(_numbers(body))
    bad_ids = [i for i in ids if i not in allowed_ids]
    bad_nums = [n for n in nums if n not in allowed_nums]
    banned = sorted({m.group(0).lower() for m in BANNED_RE.finditer(body)})
    return {"supported": not (bad_ids or bad_nums or banned), "ids_checked": len(ids), "numbers_checked": len(nums),
            "unsupported_ids": bad_ids, "unsupported_numbers": bad_nums, "banned_phrases": banned}
