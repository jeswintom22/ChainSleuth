"""R4: consecutive shipment route stops whose transition is absent from the approved network."""
from __future__ import annotations

from app.detection.base import RULES, Signal
from app.graph.queries import run_named

RULE = RULES["R4_ROUTE_ANOMALY"]


def detect_route_anomalies(shipment_ids: list[str] | None = None) -> list[Signal]:
    signals = []
    for r in run_named("route_deviations", shipment_ids=shipment_ids):
        shp, o, d, seq = r["shipment_id"], r["origin"], r["destination"], r["to_sequence"]
        signals.append(Signal(
            rule_id=RULE.rule_id, subject_key=f"{shp}:{seq}:{o}->{d}", category="unapproved_transition",
            points=RULE.config["points"],
            summary=(f"Shipment {shp} (PO {r['po_id']}) moved from {o} (stop {r['from_sequence']}) to {d} "
                     f"(stop {seq}); this transition is not in the approved warehouse network"),
            values={"shipment_id": shp, "po_id": r["po_id"], "supplier_id": r["supplier_id"], "origin": o,
                    "destination": d, "from_sequence": r["from_sequence"], "to_sequence": seq,
                    "shipment_status": r["shipment_status"]},
            record_ids={"Shipment": [shp], "PurchaseOrder": [r["po_id"]], "Warehouse": [o, d],
                        "Supplier": [r["supplier_id"]] if r["supplier_id"] else []},
            evidence_paths=[
                f"(Shipment {shp})-[:ROUTE_STOP {{sequence: {r['from_sequence']}}}]->(Warehouse {o})",
                f"(Shipment {shp})-[:ROUTE_STOP {{sequence: {seq}}}]->(Warehouse {d})",
                f"no (Warehouse {o})-[:APPROVED_NEXT]->(Warehouse {d})",
            ],
            query={"name": "route_deviations", "params": {"shipment_ids": [shp]}},
        ))
    return signals
