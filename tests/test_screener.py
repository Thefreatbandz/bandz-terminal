"""Screener tests: pure filter/sort over scan-result dicts. No network."""

from marketpulse import screener


def _row(symbol, price, chg, score, sector):
    return {"symbol": symbol,
            "quote": {"price": price, "change_percent": chg},
            "score": score, "sector": sector}


ROWS = [
    _row("AAPL", 230.0, 1.5, 80, "Mega-Cap Tech"),
    _row("NVDA", 180.0, -4.2, 65, "Mega-Cap Tech"),
    _row("SOFI", 12.0, 6.0, 40, "Banks & Finance"),
    _row("NIO", 4.5, -8.0, 20, "EV"),
]


def test_price_range():
    out = screener.apply_filters(ROWS, price_min=10.0, price_max=200.0)
    assert {r["symbol"] for r in out} == {"NVDA", "SOFI"}


def test_min_abs_change():
    out = screener.apply_filters(ROWS, min_abs_change=5.0)
    assert {r["symbol"] for r in out} == {"SOFI", "NIO"}


def test_sector():
    out = screener.apply_filters(ROWS, sector="Mega-Cap Tech")
    assert {r["symbol"] for r in out} == {"AAPL", "NVDA"}


def test_min_score():
    out = screener.apply_filters(ROWS, min_score=50)
    assert {r["symbol"] for r in out} == {"AAPL", "NVDA"}


def test_combined_filters():
    out = screener.apply_filters(ROWS, price_min=100.0, min_abs_change=2.0,
                                 sector="Mega-Cap Tech", min_score=60)
    assert [r["symbol"] for r in out] == ["NVDA"]


def test_no_filters_returns_all():
    assert len(screener.apply_filters(ROWS)) == 4


def test_rows_missing_quote_skipped():
    rows = ROWS + [{"symbol": "BROKEN", "score": 99}]
    out = screener.apply_filters(rows)
    assert "BROKEN" not in {r["symbol"] for r in out}


def test_sort_by_score_default():
    out = screener.sort_results(ROWS)
    assert [r["symbol"] for r in out] == ["AAPL", "NVDA", "SOFI", "NIO"]


def test_sort_by_abs_change():
    out = screener.sort_results(ROWS, sort_by="change")
    assert [r["symbol"] for r in out] == ["NIO", "SOFI", "NVDA", "AAPL"]


def test_empty_input():
    assert screener.apply_filters([]) == []
    assert screener.apply_filters(None) == []
    assert screener.sort_results([]) == []
