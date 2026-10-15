"""R1: suppliers reachable through a shared payout account (graph traversal in FalkorDB)."""
from __future__ import annotations

from collections import defaultdict

from app.detection.base import RULES, Signal
from app.graph.queries import run_named

RULE = RULES["R1_SHARED_ACCOUNT"]


def detect_shared_accounts(supplier_id: str | None = None) -> list[Signal]:
    pairs = run_named("shared_accounts", supplier_id=supplier_id)
    by_account: dict[str, list[dict]] = defaultdict(list)
    for p in pairs:
        by_account[p["account_ref"]].append(p)

    signals = []
    for acct, rows in sorted(by_account.items()):
        if RULE.config["exclude_registered_intermediaries"] and rows[0]["registered_intermediary"]:
            continue
        suppliers = sorted({r["supplier_a"] for r in rows} | {r["supplier_b"] for r in rows})
        owners = sorted({o for r in rows for o in r["shared_owners"]})
        corroborated = [(r["supplier_a"], r["supplier_b"], o) for r in rows for o in r["shared_owners"]]
        points = RULE.config["points"] + (RULE.config["corroboration_points"] if corroborated else 0)
        paths = [f"(Supplier {r['supplier_a']})-[:USES_ACCOUNT]->(BankAccount {acct})<-[:USES_ACCOUNT]-(Supplier {r['supplier_b']})"
                 for r in rows]
        paths += [f"(Supplier {a})-[:CONTROLLED_BY]->(Owner {o})<-[:CONTROLLED_BY]-(Supplier {b})" for a, b, o in corroborated]
        summary = f"{len(suppliers)} supplier records ({', '.join(suppliers)}) pay out to account {acct}"
        if owners:
            summary += f"; corroborated by shared owner {', '.join(owners)}"
        signals.append(Signal(
            rule_id=RULE.rule_id, subject_key=acct, category="shared_account", points=points, summary=summary,
            values={"account_ref": acct, "supplier_count": len(suppliers), "suppliers": suppliers,
                    "supplier_names": {r["supplier_a"]: r["supplier_a_name"] for r in rows}
                    | {r["supplier_b"]: r["supplier_b_name"] for r in rows},
                    "shared_owners": owners, "corroborated": bool(corroborated)},
            record_ids={"Supplier": suppliers, "BankAccount": [acct], "Owner": owners},
            evidence_paths=paths,
            query={"name": "shared_accounts", "params": {"supplier_id": supplier_id}},
        ))
    return signals
