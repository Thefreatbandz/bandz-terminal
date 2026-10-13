"""Tests for the earnings week-ahead board helpers."""
import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))

from marketpulse.engine import (  # noqa: E402
    earnings_day_label,
    group_earnings,
)

TODAY = date(2026, 10, 13)  # a Tuesday


def _dstr(d):
    return d.strftime("%Y-%m-%d")


def test_week_grouping_and_sorting():
    earnings = {
        "AAPL": _dstr(TODAY + timedelta(days=2)),
        "MSFT": _dstr(TODAY),
        "NVDA": _dstr(TODAY + timedelta(days=2)),
        "TSLA": _dstr(TODAY + timedelta(days=6)),
    }
    week, rest = group_earnings(earnings, set(earnings), TODAY)
    assert len(week) == 7
    assert week[0] == (TODAY, ["MSFT"])
    assert week[2] == (TODAY + timedelta(days=2), ["AAPL", "NVDA"])
    assert week[6] == (TODAY + timedelta(days=6), ["TSLA"])
    assert week[1] == (TODAY + timedelta(days=1), [])
    assert rest == []


def test_rest_window_days_7_to_30():
    earnings = {
        "A": _dstr(TODAY + timedelta(days=7)),
        "B": _dstr(TODAY + timedelta(days=30)),
        "C": _dstr(TODAY + timedelta(days=31)),   # out of window
        "D": _dstr(TODAY - timedelta(days=1)),    # past
    }
    week, rest = group_earnings(earnings, set(earnings), TODAY)
    assert all(syms == [] for _, syms in week)
    assert rest == [(TODAY + timedelta(days=7), ["A"]),
                    (TODAY + timedelta(days=30), ["B"])]


def test_symbols_filtered_and_bad_dates_skipped():
    earnings = {
        "AAPL": _dstr(TODAY),
        "NOPE": _dstr(TODAY),          # not in universe
        "BAD": "not-a-date",
        "EMPTY": "",
        "NONE": None,
    }
    week, rest = group_earnings(earnings, {"AAPL"}, TODAY)
    assert week[0] == (TODAY, ["AAPL"])
    assert rest == []


def test_empty_input():
    week, rest = group_earnings({}, set(), TODAY)
    assert len(week) == 7
    assert all(syms == [] for _, syms in week)
    assert rest == []
    week, rest = group_earnings(None, set(), TODAY)
    assert rest == []


def test_day_labels():
    assert earnings_day_label(TODAY, TODAY) == "Today — Tue Oct 13"
    assert earnings_day_label(TODAY + timedelta(days=1), TODAY) == "Tomorrow"
    assert (earnings_day_label(TODAY + timedelta(days=2), TODAY)
            == "Thu Oct 15")
    assert (earnings_day_label(TODAY + timedelta(days=6), TODAY)
            == "Mon Oct 19")
