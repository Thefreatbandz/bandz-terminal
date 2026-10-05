"""Tests for the market-breadth helper."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))

from marketpulse.engine import breadth_counts  # noqa: E402


def _r(chg):
    return {"quote": {"change_percent": chg}}


def test_breadth_basic():
    assert breadth_counts([_r(1.5), _r(-0.5), _r(0.0), _r(2.0)]) == (2, 1, 1)


def test_breadth_empty():
    assert breadth_counts([]) == (0, 0, 0)
    assert breadth_counts(None) == (0, 0, 0)


def test_breadth_missing_quote():
    assert breadth_counts([{}, {"quote": {}}]) == (0, 0, 2)
