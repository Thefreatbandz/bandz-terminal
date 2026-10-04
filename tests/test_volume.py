"""Tests for the unusual-volume helpers in marketpulse.data."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))

from marketpulse.data import (parse_yahoo_volumes,  # noqa: E402
                              unusual_volume_ratio)


def _payload(volumes):
    return {"chart": {"result": [{"indicators": {"quote": [
        {"volume": volumes}]}}]}}


def test_parse_yahoo_volumes_basic():
    assert parse_yahoo_volumes(_payload([100, 200, 300])) == [100, 200, 300]


def test_parse_yahoo_volumes_drops_junk():
    # None, zero, and non-numeric entries are dropped.
    assert parse_yahoo_volumes(
        _payload([100, None, 0, "x", 250.5])) == [100, 250.5]


def test_parse_yahoo_volumes_empty_payload():
    assert parse_yahoo_volumes({}) == []
    assert parse_yahoo_volumes({"chart": {"result": []}}) == []
    assert parse_yahoo_volumes(None) == []


def test_ratio_normal():
    vols = [100] * 20 + [250]  # 2.5x the 20-day average
    assert unusual_volume_ratio(vols) == 2.5


def test_ratio_below_threshold_math():
    vols = [100] * 20 + [150]
    assert unusual_volume_ratio(vols) == 1.5


def test_ratio_needs_lookback_plus_one():
    assert unusual_volume_ratio([100] * 20) is None  # exactly lookback
    assert unusual_volume_ratio([100] * 21) == 1.0  # lookback + 1


def test_ratio_empty_or_zero_baseline():
    assert unusual_volume_ratio([]) is None
    assert unusual_volume_ratio([0] * 20 + [500]) is None


def test_ratio_ignores_older_history():
    vols = [9999] * 50 + [100] * 20 + [200]
    assert unusual_volume_ratio(vols) == 2.0
