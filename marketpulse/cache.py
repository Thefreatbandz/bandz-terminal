"""Tiny in-memory TTL cache.

Each entry is (value, saved_at, ttl_seconds). Expired entries are dropped
on read. This keeps API calls (and rate-limit risk) down.

Note: it resets when the program restarts. A persistent cache (saved to
disk) is a planned later upgrade -- the function signatures won't change.
"""

import time

_cache = {}


def get_cached(key):
    """Return the cached value, or None if missing/expired."""
    item = _cache.get(key)
    if not item:
        return None
    value, saved_at, ttl = item
    if time.time() - saved_at > ttl:
        _cache.pop(key, None)
        return None
    return value


def set_cached(key, value, ttl):
    """Store a value that expires after ttl seconds."""
    _cache[key] = (value, time.time(), ttl)


def clear():
    """Empty the cache (used by tests and the reset command later)."""
    _cache.clear()


def size():
    """How many entries are currently stored."""
    return len(_cache)
