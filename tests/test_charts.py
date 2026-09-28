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
