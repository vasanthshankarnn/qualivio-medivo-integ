"""Score the latest processed run of the demo calls against the answer key (never shown to the AI).

    uv run python -m scripts.evaluate

Signals: recall per call against Atul's tags (after answer_key_corrections.csv). Extra signals the AI found are
listed for review - the library tags are not exhaustive, so extras are not automatically wrong.
Labels: patient / practice / payer / program resolution compared with demo-data/calls.csv.
"""
import csv
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DATA_DIR  # noqa: E402
from app.db import fetch_all  # noqa: E402

DEMO = Path(__file__).resolve().parents[2] / "docs" / "demo-data"


def load(name):
    with open(DEMO / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    expected = defaultdict(set)
    for r in load("answer_key_signals.csv"):
        expected[r["call_id"]].add(r["signal_id"])
    for r in load("answer_key_corrections.csv"):
        if r["action"] == "remove":
            expected[r["call_id"]].discard(r["signal_id"])
    # Rule-based signals (e.g. S16 asked-vs-told) are computed across calls in step 4, not per call.
    rule_based = {s["signal_id"] for s in fetch_all("SELECT signal_id FROM ci_signals WHERE rule_based")}
    for exp in expected.values():
        exp -= rule_based
    truth = {c["call_id"]: c for c in load("calls.csv")}

    calls = fetch_all("""
        SELECT DISTINCT ON (external_call_id) call_id, external_call_id, status, transcript_source,
               patient_id, practice_id, payer_id, program_id, other_party_type, journey_stage
        FROM ci_calls WHERE external_call_id IS NOT NULL ORDER BY external_call_id, created_at DESC""")
    found = defaultdict(set)
    for r in fetch_all("SELECT call_id, signal_id FROM ci_call_signals"):
        found[str(r["call_id"])].add(r["signal_id"])

    out, tot_exp, tot_hit = [], 0, 0
    label_ok = defaultdict(lambda: [0, 0])
    print(f"{'call':5} {'src':8} {'recall':>7}  missed / extra")
    for c in sorted(calls, key=lambda x: truth.get(x["external_call_id"], {}).get("call_datetime_et", "")):
        ext = c["external_call_id"]
        exp, got = expected.get(ext, set()), found.get(str(c["call_id"]), set())
        hit = exp & got
        tot_exp += len(exp)
        tot_hit += len(hit)
        rec = len(hit) / len(exp) if exp else 1.0
        t = truth.get(ext, {})
        for key in ("patient_id", "practice_id", "payer_id", "program_id"):
            if t.get(key) and t[key] != "PY99":
                label_ok[key][1] += 1
                label_ok[key][0] += int(c[key] == t[key])
        print(f"{ext:5} {c['transcript_source'] or c['status']:8} {rec:7.0%}  missed {sorted(exp - got) or '-'} | extra {sorted(got - exp) or '-'}")
        out.append({"call_id": ext, "status": c["status"], "source": c["transcript_source"], "expected": " ".join(sorted(exp)),
                    "found": " ".join(sorted(got)), "missed": " ".join(sorted(exp - got)), "extra": " ".join(sorted(got - exp)),
                    "recall": round(rec, 2), "patient_ok": c["patient_id"] == t.get("patient_id"),
                    "practice_ok": c["practice_id"] == t.get("practice_id"), "party": c["other_party_type"],
                    "stage": c["journey_stage"]})

    print(f"\nSignal recall: {tot_hit}/{tot_exp} = {tot_hit / tot_exp:.0%}" if tot_exp else "\nNo expected signals")
    for key, (ok, n) in label_ok.items():
        print(f"Label {key}: {ok}/{n} correct")
    (DATA_DIR / "eval").mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "eval" / f"eval_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print("Saved", path)


if __name__ == "__main__":
    main()
