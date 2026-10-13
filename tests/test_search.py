"""Tests for the instant ticker-search matcher (pure, no network)."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))

from marketpulse.search import suggest_symbols  # noqa: E402

NAMES = {
    "NVDA": "NVIDIA Corp",
    "AAPL": "Apple Inc",
    "GOOGL": "Alphabet Inc",
    "MSFT": "Microsoft Corp",
    "TSLA": "Tesla Inc",
    "AMD": "Advanced Micro Devices Inc",
    "GE": "General Electric Co",
    "BTC": "Bitcoin",
}


def syms(q, limit=8):
    return [s for s, _ in suggest_symbols(q, NAMES, limit=limit)]


def test_exact_symbol_first():
    assert syms("nvda")[0] == "NVDA"


def test_case_insensitive_and_stripped():
    assert syms("  NvDa ")[0] == "NVDA"


def test_symbol_prefix_ranking():
    out = syms("a")
    # AAPL and AMD start with A; exact-first, then prefix tier, alphabetical
    assert out[0] in ("AAPL", "AMD")
    assert "AAPL" in out and "AMD" in out


def test_symbol_substring():
    assert "GOOGL" in syms("oog")


def test_name_word_start():
    out = syms("nvid")
    assert out[0] == "NVDA"


def test_name_substring():
    assert "GE" in syms("electric")


def test_crypto_name():
    assert syms("bitcoin")[0] == "BTC"


def test_typo_tolerance():
    assert "NVDA" in syms("ndva")


def test_empty_query():
    assert suggest_symbols("", NAMES) == []
    assert suggest_symbols("   ", NAMES) == []


def test_no_match():
    assert suggest_symbols("zzzqqq", NAMES) == []


def test_limit_respected():
    assert len(suggest_symbols("a", NAMES, limit=2)) == 2


def test_no_duplicates():
    out = syms("nvda")
    assert len(out) == len(set(out))


def test_suggestion_click_uses_callback():
    """Regression: tapping a suggestion must not assign widget session
    state after instantiation (StreamlitWidgetAlreadyInstantiatedError
    crashed the app). The sanctioned pattern is on_click=_fill_search.
    """
    src = open("web.py").read()
    assert 'st.session_state["bz-search"] = sug_sym' not in src
    assert "on_click=_fill_search" in src
