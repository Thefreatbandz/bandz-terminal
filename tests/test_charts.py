"""Tests for the pure SVG chart helpers (marketpulse/charts.py)."""

from marketpulse.charts import big_chart_svg, sparkline_points


def test_big_chart_uptrend_green():
    svg = big_chart_svg([100.0, 101.0, 103.0, 102.0, 105.0])
    assert "<svg" in svg and "</svg>" in svg
    assert "#39ff88" in svg  # uptrend color
    assert "high 105.00" in svg
    assert "low 100.00" in svg
    assert "start 100.00" in svg
    assert "end 105.00" in svg
    assert "polyline" in svg


def test_big_chart_downtrend_red():
    svg = big_chart_svg([105.0, 103.0, 101.0, 100.0])
    assert "#ff3b5c" in svg
    assert "high 105.00" in svg
    assert "low 100.00" in svg


def test_big_chart_bad_input_empty_string():
    assert big_chart_svg([]) == ""
    assert big_chart_svg([42.0]) == ""
    assert big_chart_svg([None, None]) == ""


def test_big_chart_skips_none_values():
    svg = big_chart_svg([100.0, None, 102.0])
    assert "polyline" in svg
    assert "end 102.00" in svg


def test_big_chart_flat_series_no_crash():
    svg = big_chart_svg([50.0, 50.0, 50.0])
    assert "polyline" in svg
    assert "high 50.00" in svg


def test_big_chart_truncates_to_90():
    closes = [float(i) for i in range(200)]
    svg = big_chart_svg(closes)
    # only the last 90 points rendered
    assert svg.count(",") < 200
    assert "start 110.00" in svg
    assert "end 199.00" in svg


def test_big_chart_custom_size():
    svg = big_chart_svg([1.0, 2.0, 3.0], w=400, h=150)
    assert 'viewBox="0 0 400 150"' in svg


def test_sparkline_points_basic():
    pts, first, last = sparkline_points([10.0, 20.0, 30.0])
    assert first == 10.0 and last == 30.0
    assert len(pts.split(" ")) == 3


def test_sparkline_points_bad_input():
    assert sparkline_points([]) == ("", None, None)
    assert sparkline_points([5.0]) == ("", None, None)


def test_big_chart_escapes_dollar_for_markdown():
    from marketpulse.charts import big_chart_svg
    svg = big_chart_svg([100.0, 105.5, 98.2],
                        price_fmt=lambda c: f"${c:,.2f}")
    # \$ renders as a literal $ in st.markdown; a bare $ would pair up
    # into LaTeX math and mangle the SVG (the production bug).
    assert "\\$105.50" in svg
    assert "$105.50" not in svg.replace("\\$", "")


def test_big_chart_default_labels_have_no_dollar():
    from marketpulse.charts import big_chart_svg
    svg = big_chart_svg([100.0, 105.5])
    assert "$" not in svg
    assert "high 105.50" in svg


def test_web_smd_calls_have_no_kwargs():
    """web.py: smd() takes exactly one positional arg. A stray kwarg
    (e.g. unsafe_allow_html) raises TypeError at runtime on Streamlit
    Cloud but is invisible to py_compile and the rest of the suite."""
    import ast
    from pathlib import Path
    tree = ast.parse(Path("web.py").read_text())
    bad = [n.lineno for n in ast.walk(tree)
           if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "smd"
           and (len(n.args) != 1 or n.keywords)]
    assert not bad, f"smd() calls with wrong signature at lines {bad}"


def _ts(y, m, d):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return int(datetime(y, m, d, 12, 0,
                       tzinfo=ZoneInfo("America/New_York")).timestamp())


def test_tick_label_formats_eastern():
    from marketpulse.charts import _tick_label
    assert _tick_label(_ts(2026, 7, 6)) == "Jul 6"
    assert _tick_label(_ts(2026, 9, 28)) == "Sep 28"
    assert _tick_label(None) is None


def test_big_chart_draws_date_axis():
    from marketpulse.charts import big_chart_svg
    closes = [100.0 + i * 0.5 for i in range(90)]
    dates = [_ts(2026, 7, 1) + i * 86400 for i in range(90)]
    svg = big_chart_svg(closes, dates=dates)
    # ~5 evenly spaced ticks, middle-anchored along the bottom
    assert svg.count('text-anchor="middle"') == 5
    assert "Jul 1" in svg
    assert "Sep" in svg


def test_big_chart_no_dates_no_ticks():
    from marketpulse.charts import big_chart_svg
    svg = big_chart_svg([100.0, 101.5, 99.2])
    assert 'text-anchor="middle"' not in svg
    svg2 = big_chart_svg([100.0, 101.5, 99.2],
                         dates=[None, None, None])
    assert 'text-anchor="middle"' not in svg2


def test_big_chart_end_label_moved_off_high():
    """Regression: 'end' and 'high' labels used to collide top-right."""
    from marketpulse.charts import big_chart_svg
    svg = big_chart_svg([100.0, 105.0, 104.9])  # end ~= high
    # end label is bottom-left now (x=pad), high stays top-right
    assert '<text x="10" y="' in svg  # pad == 10
    end_idx = svg.index("end ")
    high_idx = svg.index("high ")
    assert svg[end_idx - 60:end_idx].count('text-anchor="end"') == 0


def test_big_chart_dates_trim_with_closes():
    from marketpulse.charts import big_chart_svg
    closes = [float(i) for i in range(120)]
    dates = [_ts(2026, 4, 1) + i * 86400 for i in range(120)]
    svg = big_chart_svg(closes, dates=dates)
    # trimmed to last 90 -> first tick is ~May, not April
    assert "Apr" not in svg
    assert svg.count('text-anchor="middle"') == 5


# --- timeframe map / rebase / compare overlay / intraday ticks ---

def test_chart_timeframes_map():
    from marketpulse.charts import CHART_TIMEFRAMES, CHART_DEFAULT
    assert CHART_TIMEFRAMES == {
        "1D": ("1d", "5m"),
        "1W": ("5d", "15m"),
        "1M": ("1mo", "1d"),
        "3M": ("3mo", "1d"),
        "1Y": ("1y", "1wk"),
    }
    assert CHART_DEFAULT == "3M"


def test_rebase_to_100_math():
    from marketpulse.charts import rebase_to_100
    out = rebase_to_100([100.0, 110.0, 90.0])
    assert out[0] == 100.0
    assert abs(out[1] - 110.0) < 1e-9
    assert abs(out[2] - 90.0) < 1e-9


def test_rebase_to_100_bad_input():
    from marketpulse.charts import rebase_to_100
    assert rebase_to_100([]) == []
    assert rebase_to_100([5.0]) == []
    assert rebase_to_100([0.0, 5.0]) == []


def test_align_compare_rebases_and_truncates():
    from marketpulse.charts import align_compare
    base, cmp_rb = align_compare([100.0, 110.0, 120.0, 130.0],
                                 [50.0, 60.0])
    # rebased first (to each series' own start), then truncated to the
    # overlapping tail: last 2 points of each
    assert len(base) == len(cmp_rb) == 2
    assert base == [120.0, 130.0]
    assert cmp_rb[0] == 100.0 and cmp_rb[1] == 120.0


def test_align_compare_invalid_compare():
    from marketpulse.charts import align_compare
    base, cmp_rb = align_compare([100.0, 101.0], [7.0])
    assert cmp_rb is None
    assert base and base[0] == 100.0


def test_big_chart_compare_overlay():
    from marketpulse.charts import big_chart_svg, COMPARE_COLOR
    svg = big_chart_svg([100.0, 102.0, 104.0], compare=[50.0, 51.0, 52.5],
                        label="AAA", compare_label="BBB")
    assert svg.count("<polyline") == 2
    assert COMPARE_COLOR in svg
    assert "AAA" in svg and "BBB" in svg
    # rebased: high label is an index value (compare peaks at 105),
    # not a raw price
    assert "high 105.00" in svg


def test_big_chart_invalid_compare_degrades_to_single():
    from marketpulse.charts import big_chart_svg
    svg = big_chart_svg([100.0, 101.0, 102.0], compare=[5.0],
                        label="AAA", compare_label="BBB")
    assert svg.count("<polyline") == 1
    assert "high 102.00" in svg  # original scale, not rebased


def test_time_label_formats_eastern_clock():
    from marketpulse.charts import _time_label
    from datetime import datetime
    from zoneinfo import ZoneInfo
    ts = int(datetime(2026, 7, 6, 12, 0,
                      tzinfo=ZoneInfo("America/New_York")).timestamp())
    assert _time_label(ts) == "12:00p"
    ts2 = int(datetime(2026, 7, 6, 9, 30,
                       tzinfo=ZoneInfo("America/New_York")).timestamp())
    assert _time_label(ts2) == "9:30a"
    assert _time_label(None) is None


def test_big_chart_intraday_ticks_show_clock_time():
    from marketpulse.charts import big_chart_svg
    closes = [100.0 + i * 0.1 for i in range(78)]
    base = _ts(2026, 9, 29)
    dates = [base + i * 300 for i in range(78)]  # 5-min bars, one session
    svg = big_chart_svg(closes, dates=dates, intraday=True)
    assert ":" in svg  # clock-time ticks like 9:30a
    assert svg.count('text-anchor="middle"') == 5
