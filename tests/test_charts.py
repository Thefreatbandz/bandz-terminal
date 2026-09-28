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
