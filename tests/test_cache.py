"""Cache tests. No waiting on real time: ttl=0 expires immediately."""

from marketpulse import cache


def setup_function():
    cache.clear()


def test_set_and_get():
    cache.set_cached("k", "v", ttl=60)
    assert cache.get_cached("k") == "v"


def test_missing_key_returns_none():
    assert cache.get_cached("nope") is None


def test_expired_entry_returns_none():
    cache.set_cached("k", "v", ttl=0)
    assert cache.get_cached("k") is None


def test_clear_empties_cache():
    cache.set_cached("k", "v", ttl=60)
    cache.clear()
    assert cache.size() == 0
