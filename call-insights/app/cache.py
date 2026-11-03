"""Small in-process cache for dashboard reads.

Entries live until the data changes: every write the app makes (a processed call, a recompute, a status or review
update) calls clear(), which also re-warms the screens in the background so the next click is fast again. The long
TTL is only a safety net for changes made outside the API (e.g. running a script against the database).
"""
import threading
import time
from functools import wraps

_lock = threading.Lock()
_store: dict = {}
_on_clear = []
_building: dict = {}  # key -> lock held while one thread computes it (others wait instead of recomputing)
_generation = 0  # bumped by clear(): a build that started before a change is not stored
TTL_SECONDS = 6 * 3600


def cached(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        key = (fn.__name__, args, tuple(sorted(kwargs.items())))
        now = time.monotonic()
        with _lock:
            hit = _store.get(key)
            if hit and now - hit[0] < TTL_SECONDS:
                return hit[1]
        with _lock:
            build = _building.setdefault(key, threading.Lock())
        with build:
            with _lock:
                hit = _store.get(key)
                if hit and time.monotonic() - hit[0] < TTL_SECONDS:
                    return hit[1]
                gen = _generation
            value = fn(*args, **kwargs)
            with _lock:
                if gen == _generation:
                    _store[key] = (time.monotonic(), value)
            return value
    return wrapper


def on_clear(callback):
    """Register a function to run (in a background thread) after the cache is cleared, e.g. re-warming."""
    _on_clear.append(callback)


def clear():
    global _generation
    with _lock:
        _store.clear()
        _generation += 1
    for cb in _on_clear:
        threading.Thread(target=cb, daemon=True).start()
