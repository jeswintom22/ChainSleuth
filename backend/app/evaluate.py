"""Measure detection quality, repeatability, grounding and latency against data/ground_truth.csv.

Usage (from backend/):  CHAINSLEUTH_GRAPH=chainsleuth_eval python -m app.evaluate
The configured graph is reset and reloaded from the CSVs first, so run it against a dedicated graph name.
Results are printed and written to data/evaluation_results.json. Ground truth is read from the CSV only;
it is never loaded into FalkorDB.
"""
from __future__ import annotations

import csv
import json
import os
import platform
import statistics
import time

from app.config import BACKEND_DIR, FALKORDB_IMAGE
from app.detection.engine import DETECTORS
from app.graph.client import read


def _timed(fn, n=5):
    times, out = [], None
    for _ in range(n):
        t = time.perf_counter()
        out = fn()
        times.append((time.perf_counter() - t) * 1000)
    return out, round(statistics.median(times), 1)


def evaluate() -> dict:
    os.environ["CHAINSLEUTH_DISABLE_LLM"] = "1"  # measure the deterministic path; LLM latency varies by network
    from app.agent.orchestrator import investigate
    from app.investigations import service

    with open(BACKEND_DIR / "data" / "ground_truth.csv", newline="", encoding="utf-8") as f:
        truth = list(csv.DictReader(f))
    per_rule, all_tp, all_fp, all_fn = {}, 0, 0, 0
    for rule_id, fn in DETECTORS.items():
        signals, latency = _timed(fn)
        found = {s.subject_key for s in signals}
        expected = {t["subject_key"] for t in truth if t["rule_id"] == rule_id and t["expected"] == "anomaly"}
        legit = [t["subject_key"] for t in truth if t["rule_id"] == rule_id and t["expected"] == "legitimate"]
        legit_flagged = [k for k in legit if any(part in s for s in found for part in k.split("|"))]
        tp, fp, fn_ = len(found & expected), len(found - expected), len(expected - found)
        all_tp, all_fp, all_fn = all_tp + tp, all_fp + fp, all_fn + fn_
        per_rule[rule_id] = {"planted": len(expected), "detected": len(found), "true_positives": tp,
                             "false_positives": fp, "missed": sorted(expected - found),
                             "recall": round(tp / len(expected), 3) if expected else None,
                             "precision": round(tp / len(found), 3) if found else None,
                             "legitimate_controls": len(legit), "legitimate_flagged": legit_flagged,
                             "median_query_ms": latency}

    first = service.run_detection()
    count1 = read("MATCH (f:Finding) RETURN count(f) AS n")[0]["n"]
    second = service.run_detection()
    count2 = read("MATCH (f:Finding) RETURN count(f) AS n")[0]["n"]

    targets = ["INV-1043", "SUP-020", "PO-5060", "PO-5070", "PO-5075", "SHP-7090", "SUP-043", "SUP-044"]
    inv_times, grounded, evidence_complete, total_findings = [], 0, 0, 0
    for t in targets:
        start = time.perf_counter()
        inv = investigate(f"Investigate {t}", entity_id=t, created_by="evaluation", use_llm=False)
        inv_times.append((time.perf_counter() - start) * 1000)
        grounded += bool(inv["grounding"]["supported"])
        for f in inv["findings"]:
            total_findings += 1
            evidence_complete += bool(f["evidence_paths"] and f["record_ids"] and f["rule_version"] and f["values"])

    return {
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "falkordb_image": FALKORDB_IMAGE},
        "per_rule": per_rule,
        "overall": {"recall": round(all_tp / (all_tp + all_fn), 3), "precision": round(all_tp / (all_tp + all_fp), 3)},
        "repeatability": {"first_run_new_findings": first["new_findings"], "second_run_new_findings": second["new_findings"],
                          "finding_nodes_after_run_1": count1, "finding_nodes_after_run_2": count2},
        "explanations": {"investigations": len(targets), "grounded": grounded,
                         "findings_with_complete_evidence": f"{evidence_complete}/{total_findings}"},
        "latency_ms": {"detection_run_total": round(sum(first["timings_ms"].values()), 1),
                       "investigation_median": round(statistics.median(inv_times), 1),
                       "investigation_max": round(max(inv_times), 1)},
    }


if __name__ == "__main__":
    from app.config import settings
    from app.graph.ingest import load_dataset, reset_operational_graph

    if settings.graph_name == "chainsleuth":
        raise SystemExit("Refusing to reset the demo graph; set CHAINSLEUTH_GRAPH=chainsleuth_eval")
    reset_operational_graph()
    load_dataset()
    res = evaluate()
    (BACKEND_DIR / "data" / "evaluation_results.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
