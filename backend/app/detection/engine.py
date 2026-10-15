"""Runs all detection rules (global scope)."""
from __future__ import annotations

import time

from app.detection.base import Signal
from app.detection.duplicate_invoice import detect_duplicate_invoices
from app.detection.reconciliation import detect_reconciliation
from app.detection.route_anomaly import detect_route_anomalies
from app.detection.supplier_network import detect_shared_accounts

DETECTORS = {
    "R1_SHARED_ACCOUNT": detect_shared_accounts,
    "R2_DUPLICATE_INVOICE": detect_duplicate_invoices,
    "R3_RECONCILIATION": detect_reconciliation,
    "R4_ROUTE_ANOMALY": detect_route_anomalies,
}


def run_all() -> tuple[list[Signal], dict[str, float]]:
    signals, timings = [], {}
    for rule_id, fn in DETECTORS.items():
        t = time.perf_counter()
        signals += fn()
        timings[rule_id] = round((time.perf_counter() - t) * 1000, 1)
    return signals, timings
