"""Deterministic synthetic procurement dataset generator for ChainSleuth.

All data is synthetic. Planted anomalies use fixed, readable IDs; normal records use separate ID
ranges (INV-2xxx, PO-6xxx, SHP-8xxx) so they can never collide with planted cases.

Evaluation labels are written to data/ground_truth.csv, which is NEVER loaded into the graph.

Usage:  python -m data.generate_synthetic   (from backend/)
"""
from __future__ import annotations

import csv
import hashlib
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

SEED = 42
BACKEND = Path(__file__).resolve().parent.parent
OUT = BACKEND / "data" / "generated"
GROUND_TRUTH = BACKEND / "data" / "ground_truth.csv"

N_SUPPLIERS = 80
N_PRODUCTS = 40
N_NORMAL_POS = 150
BASE_DATE = date(2026, 1, 5)

UNITS = ["each", "box", "kg", "litre", "metre"]
REGIONS = ["North", "South", "East", "West", "Central"]
APPROVED_ROUTES = [
    ("WH-01", "WH-02"), ("WH-02", "WH-03"), ("WH-03", "WH-04"), ("WH-04", "WH-05"),
    ("WH-01", "WH-06"), ("WH-06", "WH-07"), ("WH-07", "WH-08"), ("WH-05", "WH-10"),
    ("WH-08", "WH-10"), ("WH-06", "WH-09"), ("WH-09", "WH-10"), ("WH-02", "WH-06"),
]


def fingerprint(invoice_number: str, amount: float, currency: str, invoice_date: str, lines: list[dict]) -> str:
    """Normalized exact-duplicate fingerprint. Deliberately excludes supplier_id so the same invoice
    submitted under two supplier records collides."""
    line_part = ";".join(sorted(f"{l['product_id']}:{l['quantity']}:{float(l['unit_price']):.2f}" for l in lines))
    raw = f"{invoice_number.strip().upper()}|{float(amount):.2f}|{currency.upper()}|{invoice_date}|{line_part}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


class Dataset:
    def __init__(self) -> None:
        self.rnd = random.Random(SEED)
        self.t: dict[str, list[dict]] = defaultdict(list)
        self.truth: list[dict] = []
        self.products: dict[str, dict] = {}
        self._inv_no = 400000
        self._pay = 1

    # ---------- helpers ----------
    def day(self, offset: int) -> str:
        return (BASE_DATE + timedelta(days=offset)).isoformat()

    def next_invoice_number(self) -> str:
        self._inv_no += self.rnd.randint(1, 9)
        return f"N-{self._inv_no}"

    def add_po(self, po_id: str, supplier_id: str, lines: list[tuple[str, int]], day: int, status="open") -> list[dict]:
        self.t["purchase_orders"].append({"po_id": po_id, "supplier_id": supplier_id, "ordered_at": self.day(day), "status": status})
        out = []
        for n, (pid, qty) in enumerate(lines, 1):
            p = self.products[pid]
            row = {"po_line_id": f"{po_id}-L{n}", "po_id": po_id, "product_id": pid, "quantity": qty,
                   "unit": p["unit"], "unit_price": p["list_price"]}
            self.t["po_lines"].append(row)
            out.append(row)
        return out

    def add_shipment(self, shp_id: str, po_id: str, lines: list[tuple[str, int]], day: int, route: list[str],
                     status="delivered", unit_override: dict | None = None) -> None:
        self.t["shipments"].append({"shipment_id": shp_id, "po_id": po_id, "status": status, "shipped_at": self.day(day)})
        for n, (pid, qty) in enumerate(lines, 1):
            unit = (unit_override or {}).get(pid, self.products[pid]["unit"])
            self.t["shipment_lines"].append({"shipment_line_id": f"{shp_id}-L{n}", "shipment_id": shp_id,
                                             "product_id": pid, "quantity": qty, "unit": unit})
        for seq, wh in enumerate(route, 1):
            self.t["shipment_stops"].append({"shipment_id": shp_id, "sequence": seq, "warehouse_id": wh})

    def add_invoice(self, inv_id: str, supplier_id: str, po_id: str | None, lines: list[tuple[str, int]], day: int,
                    status="approved", invoice_number: str | None = None, unit_override: dict | None = None,
                    price_override: dict | None = None) -> dict:
        line_rows = []
        for n, (pid, qty) in enumerate(lines, 1):
            p = self.products[pid]
            price = (price_override or {}).get(pid, p["list_price"])
            line_rows.append({"line_id": f"{inv_id}-L{n}", "invoice_id": inv_id, "product_id": pid, "quantity": qty,
                              "unit": (unit_override or {}).get(pid, p["unit"]), "unit_price": price})
        amount = round(sum(l["quantity"] * l["unit_price"] for l in line_rows), 2)
        number = invoice_number or self.next_invoice_number()
        inv_date = self.day(day)
        row = {"invoice_id": inv_id, "supplier_id": supplier_id, "po_id": po_id or "", "invoice_number": number,
               "amount": amount, "currency": "USD", "invoice_date": inv_date, "status": status,
               "fingerprint": fingerprint(number, amount, "USD", inv_date, line_rows)}
        self.t["invoices"].append(row)
        self.t["invoice_lines"].extend(line_rows)
        if status == "paid":
            self.t["payments"].append({"payment_id": f"PAY-{self._pay:05d}", "invoice_id": inv_id, "supplier_id": supplier_id,
                                       "amount": amount, "currency": "USD", "paid_at": self.day(day + 14), "status": "settled"})
            self._pay += 1
        return row

    def random_route(self) -> list[str]:
        nxt = defaultdict(list)
        for a, b in APPROVED_ROUTES:
            nxt[a].append(b)
        cur = self.rnd.choice(["WH-01", "WH-02", "WH-06"])
        route = [cur]
        for _ in range(self.rnd.randint(1, 2)):
            if not nxt[cur]:
                break
            cur = self.rnd.choice(nxt[cur])
            route.append(cur)
        return route

    def truth_row(self, case_id, rule_id, expected, subject_key, description) -> None:
        self.truth.append({"case_id": case_id, "rule_id": rule_id, "expected": expected,
                           "subject_key": subject_key, "description": description})

    # ---------- master data ----------
    def master_data(self) -> None:
        r = self.rnd
        nouns = ["Components", "Industrial", "Supply", "Logistics", "Metals", "Plastics", "Electronics", "Tools",
                 "Packaging", "Chemicals"]
        prefixes = ["Apex", "Blue", "Cedar", "Delta", "Ember", "Falcon", "Granite", "Harbor", "Iris", "Juniper",
                    "Kestrel", "Lumen", "Maple", "Nova", "Onyx", "Pioneer", "Quarry", "Ridge", "Summit", "Tidal"]
        for i in range(1, N_PRODUCTS + 1):
            pid = f"PRD-{i:03d}"
            self.products[pid] = {"product_id": pid, "name": f"Part {chr(64 + (i % 26) + 1)}{i:03d}",
                                  "unit": UNITS[i % len(UNITS)], "list_price": round(r.uniform(2, 120), 2)}
        self.products["PRD-007"].update(name="Hydraulic Valve HV-7", unit="each", list_price=12.50)
        self.t["products"] = [{k: v for k, v in p.items()} for p in self.products.values()]

        for i in range(1, 11):
            self.t["warehouses"].append({"warehouse_id": f"WH-{i:02d}", "name": f"Warehouse {i:02d}",
                                         "region": REGIONS[i % len(REGIONS)]})
        self.t["warehouse_routes"] = [{"from_warehouse": a, "to_warehouse": b} for a, b in APPROVED_ROUTES]

        special_names = {10: "Northwind Components", 11: "Northwind Comp. Ltd", 12: "NW Industrial Supply",
                         20: "Granite Metals", 21: "Granite Metalworks", 30: "Atlas Fasteners",
                         31: "Cedar Plastics", 32: "Harbor Tools", 33: "Iris Packaging"}
        for i in range(1, N_SUPPLIERS + 1):
            sid = f"SUP-{i:03d}"
            name = special_names.get(i, f"{prefixes[i % 20]} {nouns[i % 10]} {i:03d}")
            self.t["suppliers"].append({"supplier_id": sid, "name": name, "status": "active",
                                        "created_at": self.day(-r.randint(60, 900))})
            # Every supplier has its own account and owner, except planted network members (handled below).
            if i not in (10, 11, 12, 20, 21):
                acc = f"ACC-{i:03d}"
                self.t["bank_accounts"].append({"account_ref": acc, "bank_code": f"BK{r.randint(10, 99)}",
                                                "account_status": "active", "registered_intermediary": False})
                self.t["supplier_accounts"].append({"supplier_id": sid, "account_ref": acc})
            if i not in (10, 11):
                self.t["owners"].append({"owner_id": f"OWN-{i:03d}", "name": f"Owner {i:03d}"})
                self.t["supplier_owners"].append({"supplier_id": sid, "owner_id": f"OWN-{i:03d}"})

    # ---------- planted cases ----------
    def planted(self) -> None:
        # P1: shared-account network, corroborated by common ownership (SUP-010/011) .
        self.t["bank_accounts"].append({"account_ref": "ACC-900", "bank_code": "BK77", "account_status": "active",
                                        "registered_intermediary": False})
        for s in ("SUP-010", "SUP-011", "SUP-012"):
            self.t["supplier_accounts"].append({"supplier_id": s, "account_ref": "ACC-900"})
        self.t["owners"].append({"owner_id": "OWN-900", "name": "R. Castellan"})
        self.t["supplier_owners"] += [{"supplier_id": "SUP-010", "owner_id": "OWN-900"},
                                      {"supplier_id": "SUP-011", "owner_id": "OWN-900"}]
        self.truth_row("P1", "R1_SHARED_ACCOUNT", "anomaly", "ACC-900",
                       "SUP-010, SUP-011, SUP-012 share payout account ACC-900; SUP-010/011 share owner OWN-900")

        # P2: shared account without corroborating ownership.
        self.t["bank_accounts"].append({"account_ref": "ACC-901", "bank_code": "BK31", "account_status": "active",
                                        "registered_intermediary": False})
        self.t["supplier_accounts"] += [{"supplier_id": "SUP-020", "account_ref": "ACC-901"},
                                        {"supplier_id": "SUP-021", "account_ref": "ACC-901"}]
        self.truth_row("P2", "R1_SHARED_ACCOUNT", "anomaly", "ACC-901", "SUP-020 and SUP-021 share payout account ACC-901")

        # L1: legitimate shared account - registered factoring intermediary.
        self.t["bank_accounts"].append({"account_ref": "ACC-950", "bank_code": "BK12", "account_status": "active",
                                        "registered_intermediary": True})
        for s in ("SUP-030", "SUP-031", "SUP-032", "SUP-033"):
            self.t["supplier_accounts"].append({"supplier_id": s, "account_ref": "ACC-950"})
        self.truth_row("L1", "R1_SHARED_ACCOUNT", "legitimate", "ACC-950",
                       "Registered factoring intermediary account shared by 4 suppliers")

        # P3: the demo invoice. INV-1043 bills 100 x PRD-007, only 60 delivered.
        self.add_po("PO-5043", "SUP-010", [("PRD-007", 100)], 20)
        self.add_shipment("SHP-7043", "PO-5043", [("PRD-007", 60)], 25, ["WH-01", "WH-02", "WH-03"])
        self.add_invoice("INV-1043", "SUP-010", "PO-5043", [("PRD-007", 100)], 30, invoice_number="A-7781")
        self.truth_row("P3", "R3_RECONCILIATION", "anomaly", "PO-5043:PRD-007:quantity_mismatch",
                       "INV-1043 bills 100 units of PRD-007; 60 delivered")

        # P4: exact duplicate of INV-1043 submitted by SUP-011 without a PO.
        self.add_invoice("INV-1044", "SUP-011", None, [("PRD-007", 100)], 30, status="pending", invoice_number="A-7781")
        self.truth_row("P4", "R2_DUPLICATE_INVOICE", "anomaly", "INV-1043|INV-1044",
                       "Exact duplicate of INV-1043 submitted under SUP-011")
        self.truth_row("P4b", "R3_RECONCILIATION", "anomaly", "INV-1044:unresolved_purchase_order_link",
                       "INV-1044 references no purchase order")

        # P5: second duplicate pair across SUP-020 / SUP-021.
        self.add_po("PO-5090", "SUP-020", [("PRD-012", 40), ("PRD-013", 10)], 40)
        self.add_shipment("SHP-7095", "PO-5090", [("PRD-012", 40), ("PRD-013", 10)], 44, ["WH-01", "WH-06", "WH-07"])
        self.add_invoice("INV-1090", "SUP-020", "PO-5090", [("PRD-012", 40), ("PRD-013", 10)], 46, status="paid",
                         invoice_number="GM-2231")
        self.add_invoice("INV-1091", "SUP-021", None, [("PRD-012", 40), ("PRD-013", 10)], 46, invoice_number="GM-2231")
        self.truth_row("P5", "R2_DUPLICATE_INVOICE", "anomaly", "INV-1090|INV-1091", "INV-1091 duplicates INV-1090")
        self.truth_row("P5b", "R3_RECONCILIATION", "anomaly", "INV-1091:unresolved_purchase_order_link",
                       "INV-1091 references no purchase order")

        # P6: over-billing vs order and delivery.
        self.add_po("PO-5060", "SUP-040", [("PRD-015", 50)], 50)
        self.add_shipment("SHP-7060", "PO-5060", [("PRD-015", 50)], 53, ["WH-02", "WH-03"])
        self.add_invoice("INV-1060", "SUP-040", "PO-5060", [("PRD-015", 75)], 55)
        self.truth_row("P6", "R3_RECONCILIATION", "anomaly", "PO-5060:PRD-015:quantity_mismatch",
                       "INV-1060 bills 75 units; 50 ordered and delivered")

        # P7: only shipment was cancelled.
        self.add_po("PO-5070", "SUP-041", [("PRD-018", 30)], 60)
        self.add_shipment("SHP-7070", "PO-5070", [("PRD-018", 30)], 62, ["WH-01", "WH-06"], status="cancelled")
        self.add_invoice("INV-1070", "SUP-041", "PO-5070", [("PRD-018", 30)], 65)
        self.truth_row("P7", "R3_RECONCILIATION", "anomaly", "PO-5070:PRD-018:missing_shipment_evidence",
                       "Only shipment for PO-5070 was cancelled")

        # P8: unit mismatch (invoice in box, delivered in each).
        pid = "PRD-021"  # product unit is 'box' (21 % 5 == 1)
        self.add_po("PO-5075", "SUP-042", [(pid, 20)], 70)
        self.add_shipment("SHP-7075", "PO-5075", [(pid, 20)], 72, ["WH-02", "WH-06"], unit_override={pid: "each"})
        self.add_invoice("INV-1075", "SUP-042", "PO-5075", [(pid, 20)], 74)
        self.truth_row("P8", "R3_RECONCILIATION", "anomaly", f"PO-5075:{pid}:unit_mismatch",
                       "Invoice unit 'box' vs delivered unit 'each'")

        # L2: legitimate partial deliveries with matching partial invoices.
        self.add_po("PO-5080", "SUP-043", [("PRD-025", 100)], 80)
        self.add_shipment("SHP-7080", "PO-5080", [("PRD-025", 60)], 82, ["WH-01", "WH-02"])
        self.add_shipment("SHP-7081", "PO-5080", [("PRD-025", 40)], 90, ["WH-01", "WH-02"])
        self.add_invoice("INV-1080", "SUP-043", "PO-5080", [("PRD-025", 60)], 84, status="paid")
        self.add_invoice("INV-1081", "SUP-043", "PO-5080", [("PRD-025", 40)], 92)
        self.truth_row("L2", "R3_RECONCILIATION", "legitimate", "PO-5080",
                       "Two partial deliveries each invoiced separately")

        # L3: partial delivery, partial invoice, remainder outstanding.
        self.add_po("PO-5081", "SUP-043", [("PRD-026", 100)], 85)
        self.add_shipment("SHP-7082", "PO-5081", [("PRD-026", 60)], 88, ["WH-06", "WH-07"])
        self.add_invoice("INV-1082", "SUP-043", "PO-5081", [("PRD-026", 60)], 89)
        self.truth_row("L3", "R3_RECONCILIATION", "legitimate", "PO-5081",
                       "60 of 100 delivered and 60 invoiced; remainder outstanding")

        # L4: recurring identical monthly orders (same amount, distinct invoices).
        for m in range(3):
            po, shp, inv = f"PO-510{m}", f"SHP-710{m}", f"INV-110{m}"
            self.add_po(po, "SUP-044", [("PRD-030", 25)], 30 * m + 5)
            self.add_shipment(shp, po, [("PRD-030", 25)], 30 * m + 8, ["WH-01", "WH-06"])
            self.add_invoice(inv, "SUP-044", po, [("PRD-030", 25)], 30 * m + 10, status="paid")
        self.truth_row("L4", "R2_DUPLICATE_INVOICE", "legitimate", "INV-1100|INV-1101|INV-1102",
                       "Recurring monthly invoices with identical amounts but distinct numbers and dates")

        # P9/P10: unapproved warehouse transitions.
        self.add_po("PO-5091", "SUP-045", [("PRD-033", 12)], 95)
        self.add_shipment("SHP-7090", "PO-5091", [("PRD-033", 12)], 97, ["WH-01", "WH-02", "WH-09"])
        self.add_invoice("INV-1092", "SUP-045", "PO-5091", [("PRD-033", 12)], 99)
        self.truth_row("P9", "R4_ROUTE_ANOMALY", "anomaly", "SHP-7090:3:WH-02->WH-09", "WH-02 -> WH-09 not approved")
        self.add_po("PO-5092", "SUP-046", [("PRD-034", 8)], 96)
        self.add_shipment("SHP-7091", "PO-5092", [("PRD-034", 8)], 98, ["WH-03", "WH-07"])
        self.add_invoice("INV-1093", "SUP-046", "PO-5092", [("PRD-034", 8)], 100)
        self.truth_row("P10", "R4_ROUTE_ANOMALY", "anomaly", "SHP-7091:2:WH-03->WH-07", "WH-03 -> WH-07 not approved")

    # ---------- clean background data ----------
    def normal(self) -> None:
        r = self.rnd
        planted_suppliers = {"SUP-010", "SUP-011", "SUP-012", "SUP-020", "SUP-021"}
        suppliers = [s["supplier_id"] for s in self.t["suppliers"] if s["supplier_id"] not in planted_suppliers]
        inv_n, shp_n = 2000, 8000
        for k in range(N_NORMAL_POS):
            po_id = f"PO-{6000 + k}"
            sid = r.choice(suppliers)
            pids = r.sample(sorted(self.products), r.randint(1, 3))
            lines = [(p, r.randint(5, 200)) for p in pids]
            day = r.randint(0, 250)
            self.add_po(po_id, sid, lines, day)
            mode = r.random()
            if mode < 0.12:  # in transit, not yet invoiced
                self.add_shipment(f"SHP-{shp_n}", po_id, lines, day + 3, self.random_route(), status="in_transit")
                shp_n += 1
            elif mode < 0.30:  # two partial deliveries, each invoiced
                first = [(p, q // 2) for p, q in lines]
                second = [(p, q - q // 2) for p, q in lines]
                for part, off in ((first, 3), (second, 12)):
                    self.add_shipment(f"SHP-{shp_n}", po_id, part, day + off, self.random_route())
                    self.add_invoice(f"INV-{inv_n}", sid, po_id, part, day + off + 2,
                                     status=r.choice(["paid", "approved"]))
                    shp_n += 1
                    inv_n += 1
            else:  # single full delivery and invoice
                self.add_shipment(f"SHP-{shp_n}", po_id, lines, day + 3, self.random_route())
                self.add_invoice(f"INV-{inv_n}", sid, po_id, lines, day + 5,
                                 status=r.choice(["paid", "paid", "approved", "pending"]))
                shp_n += 1
                inv_n += 1

    def validate(self) -> None:
        fps = defaultdict(list)
        for inv in self.t["invoices"]:
            fps[inv["fingerprint"]].append(inv["invoice_id"])
        collisions = sorted(tuple(sorted(v)) for v in fps.values() if len(v) > 1)
        assert collisions == [("INV-1043", "INV-1044"), ("INV-1090", "INV-1091")], collisions

    def write(self) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        for name, data in self.t.items():
            with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
                w.writeheader()
                w.writerows(data)
        with open(GROUND_TRUTH, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(self.truth[0].keys()))
            w.writeheader()
            w.writerows(self.truth)


def generate() -> dict[str, int]:
    ds = Dataset()
    ds.master_data()
    ds.planted()
    ds.normal()
    ds.validate()
    ds.write()
    return {k: len(v) for k, v in ds.t.items()}


if __name__ == "__main__":
    for table, n in generate().items():
        print(f"{table:20s} {n}")
