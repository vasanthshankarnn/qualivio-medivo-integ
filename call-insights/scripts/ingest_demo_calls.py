"""Register and process Atul's demo calls (qa/docs/demo-data/calls.csv).

Only phone-system style metadata is passed (date, direction, agent, case id, which channel is the hub agent).
Practice, payer, patient name, party type and stage are left for the pipeline to work out from the call.

    uv run python -m scripts.ingest_demo_calls                    # audio -> Azure transcription (default)
    uv run python -m scripts.ingest_demo_calls --with-transcript  # use the cleaned reference transcripts instead
    uv run python -m scripts.ingest_demo_calls --only ST01,DR03 --reset
"""
import argparse
import csv
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import fetch_all, get_conn  # noqa: E402
from app.pipeline import process_call, register_call, relabel_call  # noqa: E402
from app.rules import recompute  # noqa: E402

DOCS = Path(__file__).resolve().parents[2] / "docs"
DEMO = DOCS / "demo-data"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-transcript", action="store_true", help="attach the cleaned transcript (skips transcription)")
    ap.add_argument("--only", help="comma-separated call ids, e.g. ST01,DR03")
    ap.add_argument("--reset", action="store_true", help="delete earlier runs of these calls first")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--relabel", action="store_true",
                    help="re-run only the label matching on the stored AI output (no transcription, no AI call)")
    ap.add_argument("--reprocess", action="store_true",
                    help="re-run processing on the latest stored record of each call (keeps its transcript)")
    args = ap.parse_args()

    with open(DEMO / "calls.csv", encoding="utf-8") as f:
        calls = list(csv.DictReader(f))
    if args.only:
        wanted = {c.strip() for c in args.only.split(",")}
        calls = [c for c in calls if c["call_id"] in wanted]

    if args.relabel:
        rows = fetch_all("""SELECT DISTINCT ON (external_call_id) external_call_id, call_id FROM ci_calls
                            WHERE external_call_id = ANY(%s) ORDER BY external_call_id, created_at DESC""",
                         ([c["call_id"] for c in calls],))
        for r in rows:
            print(r["external_call_id"], relabel_call(r["call_id"])["status"])
        print("Insights:", recompute())
        return

    if args.reprocess:
        latest = {r["external_call_id"]: r["call_id"] for r in fetch_all(
            """SELECT DISTINCT ON (external_call_id) external_call_id, call_id FROM ci_calls
               WHERE external_call_id = ANY(%s) ORDER BY external_call_id, created_at DESC""",
            ([c["call_id"] for c in calls],))}
        calls = [c for c in calls if c["call_id"] in latest]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(process_call, [latest[c["call_id"]] for c in calls]))
        for c, r in zip(calls, results):
            print(f"{c['call_id']}: {r['status']}" + (f" - {r.get('error')}" if r["status"] == "failed" else f" ({r['signals']} signals)"))
        print("Insights:", recompute())
        return

    if args.reset:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM ci_calls WHERE external_call_id = ANY(%s)", ([c["call_id"] for c in calls],))
            print(f"Removed {cur.rowcount} earlier call records")

    ids = []
    for c in calls:
        transcript = None
        if args.with_transcript:
            transcript = (DEMO / "transcripts_clean" / f"{c['call_id']}.txt").read_text(encoding="utf-8")
        ids.append(register_call(str(DOCS / c["audio_file"]), {
            "external_call_id": c["call_id"],
            "call_datetime": f"{c['call_datetime_et']} America/New_York",
            "direction": c["direction"],
            "staff_id": c["staff_id"],
            "case_id": c["case_id"],
            # The phone system knows which channel is its own agent, not who the other party is.
            "channel_layout": {"0": "hub staff", "1": "other party"},
        }, transcript_text=transcript))

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(process_call, ids))
    for c, r in zip(calls, results):
        print(f"{c['call_id']}: {r['status']}" + (f" - {r.get('error')}" if r["status"] == "failed" else f" ({r['signals']} signals)"))
    print("Insights:", recompute())


if __name__ == "__main__":
    main()
