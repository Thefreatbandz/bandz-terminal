"""Tests for the custom watchlist storage."""

from marketpulse import watchlist


def test_add_and_load_roundtrip(tmp_path):
    path = str(tmp_path / "watchlist.json")
    made = watchlist.add_symbol("nvda", path=path)
    assert made and made["symbol"] == "NVDA" and made["starred"] is False
    loaded = watchlist.load_watchlist(path=path)
    assert len(loaded) == 1 and loaded[0]["symbol"] == "NVDA"


def test_add_rejects_blank_and_duplicates(tmp_path):
    path = str(tmp_path / "watchlist.json")
    assert watchlist.add_symbol("", path=path) is None
    assert watchlist.add_symbol("NVDA", path=path)
    assert watchlist.add_symbol("nvda", path=path) is None
    assert len(watchlist.load_watchlist(path=path)) == 1


def test_starred_sorts_first(tmp_path):
    path = str(tmp_path / "watchlist.json")
    watchlist.add_symbol("ZZZ", path=path)
    watchlist.add_symbol("AAA", path=path)
    watchlist.toggle_star("ZZZ", path=path)
    loaded = watchlist.load_watchlist(path=path)
    assert [w["symbol"] for w in loaded] == ["ZZZ", "AAA"]


def test_toggle_star_flips(tmp_path):
    path = str(tmp_path / "watchlist.json")
    watchlist.add_symbol("NVDA", path=path)
    assert watchlist.toggle_star("NVDA", path=path) is True
    assert watchlist.toggle_star("NVDA", path=path) is False
    assert watchlist.toggle_star("NOPE", path=path) is None


def test_remove_symbol(tmp_path):
    path = str(tmp_path / "watchlist.json")
    watchlist.add_symbol("NVDA", path=path)
    assert watchlist.remove_symbol("nvda", path=path) is True
    assert watchlist.load_watchlist(path=path) == []
    assert watchlist.remove_symbol("NVDA", path=path) is False


def test_load_missing_file_returns_empty(tmp_path):
    assert watchlist.load_watchlist(
        path=str(tmp_path / "missing.json")) == []
