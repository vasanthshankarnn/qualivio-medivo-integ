"""Save or restore every ci_ table (calls, AI output, master data, rule results, statuses) as CSV files.

    uv run python scripts/checkpoint.py export checkpoints/v1-2026-10-16
    uv run python scripts/checkpoint.py restore checkpoints/v1-2026-10-16    # replaces all ci_ data - asks first

Only the ci_ tables in the configured schema are touched; Qualivio's own tables are never read or written.
The call audio lives in data/audio (copy that folder alongside if you need to replay calls).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import DB_SCHEMA  # noqa: E402
from app.db import fetch_all, get_conn  # noqa: E402


def tables_in_load_order() -> list[str]:
    """ci_ tables ordered so every table comes after the tables its foreign keys point to."""
    names = [r["table_name"] for r in fetch_all(
        """SELECT table_name FROM information_schema.tables
           WHERE table_schema = %s AND table_name LIKE %s AND table_type = 'BASE TABLE'""", (DB_SCHEMA, "ci\\_%"))]
    deps = {n: set() for n in names}
    for r in fetch_all(
            """SELECT tc.table_name AS child, ccu.table_name AS parent FROM information_schema.table_constraints tc
               JOIN information_schema.constraint_column_usage ccu
                 ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
               WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = %s""", (DB_SCHEMA,)):
        if r["child"] in deps and r["parent"] in deps and r["child"] != r["parent"]:
            deps[r["child"]].add(r["parent"])
    ordered = []
    while deps:
        ready = sorted(n for n, d in deps.items() if not d - set(ordered))
        if not ready:
            raise RuntimeError(f"Circular foreign keys between {sorted(deps)}")
        ordered += ready
        for n in ready:
            deps.pop(n)
    return ordered


def export(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    counts = {}
    with get_conn() as conn, conn.cursor() as cur:
        for t in tables_in_load_order():
            with open(folder / f"{t}.csv", "w", encoding="utf-8", newline="") as f:
                cur.copy_expert(f'COPY "{DB_SCHEMA}".{t} TO STDOUT WITH (FORMAT csv, HEADER)', f)
            cur.execute(f'SELECT count(*) FROM "{DB_SCHEMA}".{t}')
            counts[t] = cur.fetchone()[0]
    (folder / "manifest.json").write_text(json.dumps({
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "schema": DB_SCHEMA,
        "load_order": list(counts), "rows": counts}, indent=2), encoding="utf-8")
    print(f"Exported {len(counts)} tables, {sum(counts.values())} rows -> {folder}")


def restore(folder: Path):
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    order = manifest["load_order"]
    if input(f"Replace ALL data in {len(order)} ci_ tables of schema {DB_SCHEMA} with {folder}? Type yes: ") != "yes":
        print("Cancelled")
        return
    with get_conn() as conn, conn.cursor() as cur:  # one transaction: all or nothing
        cur.execute("TRUNCATE " + ", ".join(f'"{DB_SCHEMA}".{t}' for t in order) + " CASCADE")
        for t in order:
            with open(folder / f"{t}.csv", encoding="utf-8") as f:
                cur.copy_expert(f'COPY "{DB_SCHEMA}".{t} FROM STDIN WITH (FORMAT csv, HEADER)', f)
            # keep serial ids ahead of the restored rows
            cur.execute("""SELECT a.attname, pg_get_serial_sequence(%s, a.attname) AS seq FROM pg_attribute a
                           WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped""",
                        (f'"{DB_SCHEMA}".{t}', f'"{DB_SCHEMA}".{t}'))
            for col, seq in cur.fetchall():
                if seq:
                    cur.execute(f"SELECT setval(%s, COALESCE((SELECT max({col}) FROM \"{DB_SCHEMA}\".{t}), 0) + 1, false)", (seq,))
    print(f"Restored {len(order)} tables from {folder}. Restart the API so the screens reload.")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("export", "restore"):
        sys.exit(__doc__)
    (export if sys.argv[1] == "export" else restore)(Path(sys.argv[2]))
