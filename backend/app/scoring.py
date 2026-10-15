"""Deterministic, capped risk scoring.

Points per rule live in the versioned rule config (app/detection/base.py). They are engineering
choices, not calibrated fraud probabilities. A score indicates review priority only.
"""
from __future__ import annotations

SCORE_CAP = 100
SEVERITY_THRESHOLDS = [(75, "critical"), (50, "high"), (25, "medium"), (0, "low")]


def severity(score: int) -> str:
    return next(label for threshold, label in SEVERITY_THRESHOLDS if score >= threshold)


def investigation_score(findings: list[dict]) -> dict:
    """Sum points of distinct findings (deduplicated by finding_id), capped at SCORE_CAP.
    Dismissed findings are excluded; each finding counts once however many paths reach it."""
    seen, breakdown = set(), []
    for f in sorted(findings, key=lambda f: f["finding_id"]):
        if f["finding_id"] in seen or f.get("status") == "dismissed":
            continue
        seen.add(f["finding_id"])
        breakdown.append({"finding_id": f["finding_id"], "rule_id": f["rule_id"], "points": int(f["score"])})
    raw = sum(b["points"] for b in breakdown)
    total = min(raw, SCORE_CAP)
    return {"score": total, "raw_points": raw, "capped": raw > SCORE_CAP, "severity": severity(total),
            "breakdown": breakdown}
