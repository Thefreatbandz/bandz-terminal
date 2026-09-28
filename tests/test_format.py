"""Formatting tests. Pure functions, no network, no keys."""

import pytest

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


def test_fx_rates_from_strip():
    from marketpulse.format import fx_rates_from_strip
    pairs = [
        {"label": "EUR/USD", "price": 1.20},
        {"label": "GBP/USD", "price": 1.30},
        {"label": "USD/JPY", "price": 150.0},
        {"label": "USD/CAD", "price": 1.40},
        {"label": "AUD/USD", "price": 0.70},
        {"label": "EUR/USD", "price": None},  # bad row ignored
    ]
    rates = fx_rates_from_strip(pairs)
    assert rates["USD"] == 1.0
    assert rates["EUR"] == pytest.approx(1 / 1.20)
    assert rates["GBP"] == pytest.approx(1 / 1.30)
    assert rates["JPY"] == 150.0
    assert rates["CAD"] == 1.40
    assert rates["AUD"] == pytest.approx(1 / 0.70)


def test_convert_currency():
    from marketpulse.format import convert_currency
    rates = {"USD": 1.0, "EUR": 0.9, "JPY": 150.0}
    assert convert_currency(100.0, "USD", rates) == 100.0
    assert convert_currency(100.0, "EUR", rates) == pytest.approx(90.0)
    assert convert_currency(100.0, "JPY", rates) == pytest.approx(15000.0)
    assert convert_currency(100.0, "GBP", rates) is None  # no rate
    assert convert_currency(None, "EUR", rates) is None


def test_fmt_price_ccy():
    from marketpulse.format import fmt_price_ccy
    rates = {"USD": 1.0, "EUR": 0.9, "GBP": 0.8, "JPY": 150.0,
             "CAD": 1.4, "AUD": 1.5}
    assert fmt_price_ccy(100.0) == "$100.00"                      # USD default
    assert fmt_price_ccy(100.0, "EUR", rates) == "€90.00"
    assert fmt_price_ccy(100.0, "GBP", rates) == "£80.00"
    assert fmt_price_ccy(100.0, "JPY", rates) == "¥15,000"
    assert fmt_price_ccy(100.0, "CAD", rates) == "C$140.00"
    assert fmt_price_ccy(100.0, "AUD", rates) == "A$150.00"
    # missing rate falls back to USD honestly, never a wrong number
    assert fmt_price_ccy(100.0, "EUR", {}) == "$100.00"
    assert fmt_price_ccy(None, "EUR", rates) == "—"
