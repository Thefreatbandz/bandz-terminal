"""Tests for the Google-Finance-style detail chart helpers."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))

from marketpulse.charts import (GF_RANGE_LABEL, GF_TIMEFRAMES,  # noqa: E402
                                gf_chart_svg, timeframe_change)


def test_gf_timeframes_match_screenshot_set():
    assert list(GF_TIMEFRAMES) == ["1D", "5D", "1M", "6M", "YTD"]
    for label in GF_TIMEFRAMES:
        assert label in GF_RANGE_LABEL


def test_timeframe_change_math():
    up, pct = timeframe_change([100.0, 110.0])
    assert up == 10.0
    assert pct == 10.0


def test_timeframe_change_down():
    down, pct = timeframe_change([200.0, 190.0])
    assert down == -10.0
    assert round(pct, 2) == -5.0


def test_timeframe_change_bad_input():
    assert timeframe_change([]) == (None, None)
    assert timeframe_change([5.0]) == (None, None)
    assert timeframe_change([0.0, 10.0]) == (None, None)


def test_gf_chart_svg_structure():
    closes = [100 + i for i in range(20)]
    svg = gf_chart_svg(closes)
    assert "<svg" in svg
    assert "linearGradient" in svg  # gradient fill under the line
    assert "<circle" in svg  # end dot
    assert svg.count("<text") >= 4  # y-axis labels


def test_gf_chart_svg_trend_colors():
    up_svg = gf_chart_svg([100.0, 120.0])
    down_svg = gf_chart_svg([120.0, 100.0])
    assert "#34d399" in up_svg
    assert "#f87171" in down_svg


def test_gf_chart_svg_dates():
    closes = [100 + i for i in range(10)]
    dates = [1754000000 + i * 86400 for i in range(10)]
    svg = gf_chart_svg(closes, dates=dates)
    assert "Jul" in svg or "Aug" in svg  # some month label rendered


def test_gf_chart_svg_bad_input():
    assert gf_chart_svg([]) == ""
    assert gf_chart_svg([42.0]) == ""
    # Mismatched dates degrade to no date labels, not a crash.
    svg = gf_chart_svg([100.0, 101.0, 102.0], dates=[1, 2])
    assert "<svg" in svg
