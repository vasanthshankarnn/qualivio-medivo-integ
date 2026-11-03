import threading
from contextlib import contextmanager
from pathlib import Path

import psycopg2
import psycopg2.extras
import psycopg2.pool

from app.config import CALL_TIMEZONE, DATABASE_URL, DB_SCHEMA

psycopg2.extras.register_uuid()

# Opening a connection to the Azure Postgres costs ~2 s, and the pool opens new ones one at a time under its lock,
# so a few connections are opened up front (POOL_READY) and reused; parallel reads stay within that number.
POOL_READY = 4
_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                if not DATABASE_URL:
                    raise ValueError("DATABASE_URL is not configured")
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    POOL_READY, 12, DATABASE_URL, connect_timeout=30,
                    options=f'-c statement_timeout=60000 -c search_path="{DB_SCHEMA}" -c timezone={CALL_TIMEZONE}',
                    keepalives=1, keepalives_idle=60, keepalives_interval=10, keepalives_count=3,
                )
    return _pool


@contextmanager
def get_conn():
    """Pooled connection with search_path set to Qualivio's schema (hyphenated, so always quoted)."""
    pool = _get_pool()
    conn = pool.getconn()
    broken = False
    try:
        if conn.closed:
            raise psycopg2.InterfaceError("pooled connection closed")
        yield conn
        conn.commit()
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        broken = True
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn, close=broken or bool(conn.closed))


def fetch_all(sql, params=None):
    """Read query in autocommit mode: one network round trip instead of two (query + commit)."""
    pool = _get_pool()
    conn = pool.getconn()
    broken = False
    try:
        conn.autocommit = True
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return [dict(r) for r in cur.fetchall()]
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        broken = True
        raise
    finally:
        if not conn.closed:
            conn.autocommit = False
        pool.putconn(conn, close=broken or bool(conn.closed))


def fetch_one(sql, params=None):
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def init_schema():
    sql = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql)
