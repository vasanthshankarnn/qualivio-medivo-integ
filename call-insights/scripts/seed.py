"""Create the ci_ tables and load master data + Atul's signal library from qa/docs/demo-data (idempotent upserts).

    uv run python -m scripts.seed
"""
import csv
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import get_conn, init_schema  # noqa: E402

DEMO = Path(__file__).resolve().parents[2] / "docs" / "demo-data"


def rows(name):
    with open(DEMO / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def upsert(cur, table, key, data: list[dict]):
    if not data:
        return 0
    cols = list(data[0].keys())
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != key)
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) " \
          f"ON CONFLICT ({key}) DO UPDATE SET {updates}"
    for r in data:
        cur.execute(sql, [r[c] if r[c] != "" else None for c in cols])
    return len(data)


def seed_baseline(cur) -> int:
    """'Normal' values the screens compare against (synthetic 13-week baseline for the demo)."""
    data = rows("baseline.csv")
    for r in data:
        cur.execute("""INSERT INTO ci_baseline (metric, key, normal, unit, source) VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (metric, key) DO UPDATE SET normal = EXCLUDED.normal, unit = EXCLUDED.unit,
                         source = EXCLUDED.source""", (r["metric"], r["key"], r["normal"], r["unit"], r["source"]))
    return len(data)


def main():
    init_schema()
    if "--baseline-only" in sys.argv:
        with get_conn() as conn, conn.cursor() as cur:
            print("Seeded: ci_baseline", seed_baseline(cur))
        return
    patients = []
    for p in rows("patients.csv"):
        patients.append({
            "patient_id": p["patient_id"], "case_id": p["case_id"], "patient_name": p["patient_name"],
            "dob": datetime.strptime(p["dob"], "%B %d, %Y").date().isoformat() if p["dob"] else "",
            "program_id": p["program_id"], "practice_id": p["practice_id"], "prescriber_id": p["prescriber_id"],
            "payer_id": p["payer_id"],
        })
    signals = [{
        "signal_id": s["Signal ID"], "insight_type": s["Insight type"], "journey_stage": s["Journey stage"],
        "signal_name": s["Signal"], "meaning": s["What it means"], "who_says": s["Who says it"],
        "keywords": s["Keywords & phrases (pipe-separated)"], "example_line": s["Example line from demo calls"],
        "use_cases": s["Use case"], "rule_based": s["Keywords & phrases (pipe-separated)"].lower().startswith("rule"),
    } for s in rows("signal_library.csv")]
    rules = [{
        "rule_id": r["Rule"], "name": r["Name"], "use_cases": r["Use case"], "level": r["Level"],
        "inputs": r["Inputs (signals)"], "logic": r["Logic"], "output": r["Output / insight"], "data_needed": r["Data needed"],
    } for r in rows("cross_call_rules.csv")]

    with get_conn() as conn, conn.cursor() as cur:
        counts = {
            "ci_programs": upsert(cur, "ci_programs", "program_id", rows("programs.csv")),
            "ci_practices": upsert(cur, "ci_practices", "practice_id", rows("practices.csv")),
            "ci_prescribers": upsert(cur, "ci_prescribers", "prescriber_id", rows("prescribers.csv")),
            "ci_payers": upsert(cur, "ci_payers", "payer_id", rows("payers.csv")),
            "ci_staff": upsert(cur, "ci_staff", "staff_id", rows("staff.csv")),
            "ci_patients": upsert(cur, "ci_patients", "patient_id", patients),
            "ci_signals": upsert(cur, "ci_signals", "signal_id", signals),
            "ci_rules": upsert(cur, "ci_rules", "rule_id", rules),
            "ci_baseline": seed_baseline(cur),
        }
    print("Seeded:", counts)


if __name__ == "__main__":
    main()
