"""Tests for the OpenTerminal-gap data helpers (pure functions only).

No network: fixtures shaped like the real payloads.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))

from marketpulse.data import (  # noqa: E402
    TV_SCAN_COLUMNS,
    parse_coingecko_board,
    parse_stooq_csv,
    parse_tv_scan,
    parse_yahoo_ohlc,
    tv_scan_body,
)


def test_tv_scan_body_shape():
    body = tv_scan_body(400)
    assert body["columns"] == list(TV_SCAN_COLUMNS)
    assert body["sort"] == {"sortBy": "market_cap_basic",
                            "sortOrder": "desc"}
    assert body["range"] == [0, 400]
    assert body["symbols"]["tickers"] == []


def _tv_payload():
    return {"totalCount": 4, "data": [
        {"s": "NASDAQ:NVDA",
         "d": ["NVIDIA Corporation", 226.32, -1.29, 5.45e12,
               "Electronic Technology"]},
        {"s": "NYSE:BRK.B",
         "d": ["Berkshire Hathaway", 500.0, 0.5, 1.1e12, "Finance"]},
        # zero mcap -> skipped
        {"s": "NASDAQ:ZERO", "d": ["Zero", 1.0, 0.1, 0, "Other"]},
        # missing change -> skipped
        {"s": "NASDAQ:NOCHG", "d": ["NoChg", 1.0, None, 1e9, "Other"]},
        {"s": "BROKEN"},
    ]}


def test_parse_tv_scan():
    rows = parse_tv_scan(_tv_payload())
    assert [r["symbol"] for r in rows] == ["NVDA", "BRK.B"]
    nvda = rows[0]
    assert nvda["name"] == "NVIDIA Corporation"
    assert nvda["price"] == 226.32
    assert nvda["change"] == -1.29
    assert nvda["mcap"] == 5.45e12
    assert nvda["sector"] == "Electronic Technology"


def test_parse_tv_scan_bad_input():
    assert parse_tv_scan({}) == []
    assert parse_tv_scan(None) == []
    assert parse_tv_scan({"data": "nope"}) == []


def _yahoo_payload():
    return {"chart": {"result": [{
        "timestamp": [1000, 2000, 3000],
        "indicators": {"quote": [{
            "open": [10.0, 11.0, None],
            "high": [12.0, 11.5, 12.5],
            "low": [9.5, 10.5, 11.0],
            "close": [11.0, 11.2, 12.0],
            "volume": [100, 200, 300],
        }]},
    }]}}


def test_parse_yahoo_ohlc():
    candles = parse_yahoo_ohlc(_yahoo_payload())
    # third candle has a null open -> skipped
    assert len(candles) == 2
    assert candles[0] == {"t": 1000, "o": 10.0, "h": 12.0,
                          "l": 9.5, "c": 11.0, "v": 100.0}
    assert candles[1]["t"] == 2000


def test_parse_yahoo_ohlc_bad_input():
    assert parse_yahoo_ohlc({}) == []
    assert parse_yahoo_ohlc(None) == []


def _cg_payload():
    return [
        {"id": "bitcoin", "symbol": "btc", "current_price": 80000.0,
         "price_change_percentage_24h": 2.5,
         "sparkline_in_7d": {"price": [79000.0, 79500.0, 80000.0]}},
        {"id": "ethereum", "symbol": "eth", "current_price": 2400.0,
         "price_change_percentage_24h": -1.0,
         "sparkline_in_7d": {}},
    ]


def test_parse_coingecko_board():
    rows = parse_coingecko_board(_cg_payload())
    assert len(rows) == 2
    btc = rows[0]
    assert btc["symbol"] == "BTC"
    assert btc["price"] == 80000.0
    assert btc["change_24h"] == 2.5
    assert btc["spark7"] == [79000.0, 79500.0, 80000.0]
    assert rows[1]["spark7"] == []


def test_parse_coingecko_board_bad_input():
    assert parse_coingecko_board({}) == []
    assert parse_coingecko_board(None) == []


_STOOQ_CSV = """Symbol,Date,Time,Open,High,Low,Close,Volume
^VIX,2026-10-09,22:00:00,18.10,18.55,17.90,18.42,0
10USY.B,2026-10-09,22:00:00,4.20,4.23,4.19,4.22,0
"""


def test_parse_stooq_csv():
    out = parse_stooq_csv(_STOOQ_CSV)
    assert out["vix"] == 18.42
    assert abs(out["vix_chg"] - (18.42 - 18.10) / 18.10 * 100) < 1e-9
    assert out["yield10"] == 4.22


def test_parse_stooq_csv_bad_input():
    assert parse_stooq_csv("") == {}
    assert parse_stooq_csv(None) == {}
    assert parse_stooq_csv("Symbol,Date\n") == {}


def test_pills_selection_mode_values():
    """Regression: st.pills selection_mode must be 'single' or 'multi'.

    'multiple' raises StreamlitValueError at runtime (broke Candles mode).
    """
    import re
    src = open("web.py").read()
    for m in re.finditer(r'selection_mode="([^"]+)"', src):
        assert m.group(1) in ("single", "multi"), m.group(0)
