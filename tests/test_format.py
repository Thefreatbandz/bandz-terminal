"""Formatting tests. Pure functions, no network, no keys."""

from marketpulse.format import fmt_change, fmt_price, move_emoji, score_band


def test_fmt_price():
    assert fmt_price(1234.5) == "$1,234.50"


def test_fmt_price_unknown():
    assert fmt_price(None) == "—"


def test_fmt_change_signed():
    assert fmt_change(-2.345) == "-2.35%"
    assert fmt_change(3.0) == "+3.00%"


def test_move_emoji():
    assert move_emoji(1.0) == "🟢"
    assert move_emoji(-0.1) == "🔴"
    assert move_emoji(None) == "⚪"


def test_score_band():
    assert score_band(70) == "High attention"
    assert score_band(50) == "Worth a look"
    assert score_band(10) == "No signal"
