"""Engine tests with a FAKE client -- no network, no API keys.

The fake implements the same two methods the real FinnhubClient has
(quote / company_news), so scan_stock can't tell the difference.
"""

import asyncio

from marketpulse import cache
from marketpulse.engine import scan_stock, scan_universe


class FakeClient:
    """Mock market data source. Clearly labeled: NOT live data."""

    session = None  # scan_stock only touches this when include_ai=True

    def __init__(self, quotes):
        self.quotes = quotes  # symbol -> quote dict (or None = no data)

    async def quote(self, symbol):
        return self.quotes.get(symbol)

    async def company_news(self, symbol):
        return [{"headline": f"Mock headline for {symbol}"}]


def _run(coro):
    return asyncio.run(coro)


def setup_function():
    cache.clear()


def test_scan_stock_returns_ranked_fields():
    client = FakeClient({"AAA": {
        "symbol": "AAA", "price": 10.0, "previous_close": 9.0,
        "change_percent": 11.1,
    }})
    result = _run(scan_stock(client, "AAA", include_ai=False))
    assert result["symbol"] == "AAA"
    assert result["score"] > 0
    assert result["analysis"] is None


def test_scan_stock_returns_none_without_data():
    client = FakeClient({"AAA": None})
    assert _run(scan_stock(client, "AAA", include_ai=False)) is None


def test_scan_universe_sorts_highest_first():
    client = FakeClient({
        "LOW": {"symbol": "LOW", "price": 10.0, "previous_close": 10.0,
                "change_percent": 0.1},
        "HIGH": {"symbol": "HIGH", "price": 10.0, "previous_close": 9.0,
                 "change_percent": 11.1},
    })
    results = _run(scan_universe(client, ["LOW", "HIGH"]))
    assert [r["symbol"] for r in results] == ["HIGH", "LOW"]


def test_scan_universe_skips_bad_symbols():
    client = FakeClient({"GOOD": {
        "symbol": "GOOD", "price": 10.0, "previous_close": 9.5,
        "change_percent": 5.2,
    }, "BAD": None})
    results = _run(scan_universe(client, ["GOOD", "BAD"]))
    assert [r["symbol"] for r in results] == ["GOOD"]


class CountingClient(FakeClient):
    """Fake client that records which symbols got news calls."""

    def __init__(self, quotes):
        super().__init__(quotes)
        self.news_calls = []

    async def company_news(self, symbol):
        self.news_calls.append(symbol)
        return await super().company_news(symbol)


def test_scan_stock_can_skip_news():
    client = CountingClient({"AAA": {
        "symbol": "AAA", "price": 10.0, "previous_close": 9.0,
        "change_percent": 11.1,
    }})
    result = _run(scan_stock(client, "AAA", include_ai=False,
                             include_news=False))
    assert result["news"] == []
    assert client.news_calls == []


def test_scan_universe_two_pass_only_news_for_top_movers():
    client = CountingClient({
        "BIG": {"symbol": "BIG", "price": 10.0, "previous_close": 9.0,
                "change_percent": 11.1},
        "SMALL": {"symbol": "SMALL", "price": 10.0, "previous_close": 9.9,
                  "change_percent": 1.0},
    })
    results = _run(scan_universe(client, ["BIG", "SMALL"], news_top_n=1))
    assert [r["symbol"] for r in results] == ["BIG", "SMALL"]
    # Only the top mover got the expensive news call.
    assert client.news_calls == ["BIG"]
    assert results[0]["news"] != []
    assert results[1]["news"] == []


def test_sector_of():
    from marketpulse.config import EVERYTHING_STOCKS, sector_of
    assert sector_of("NVDA") == "Mega-Cap Tech"
    assert sector_of("SPY") == "ETFs"
    assert sector_of("FAKE") == "Other"
    # No duplicates across sectors.
    assert len(EVERYTHING_STOCKS) == len(set(EVERYTHING_STOCKS))


def test_sector_summary_sorts_best_first():
    from marketpulse.engine import sector_summary
    results = [
        {"symbol": "A", "sector": "Chips", "quote": {"change_percent": 1.0}},
        {"symbol": "B", "sector": "Chips", "quote": {"change_percent": 3.0}},
        {"symbol": "C", "sector": "Banks", "quote": {"change_percent": -2.0}},
        {"symbol": "D", "quote": {"change_percent": 5.0}},
    ]
    out = sector_summary(results)
    assert out[0] == ("Other", 5.0, 1)
    assert out[1] == ("Chips", 2.0, 2)
    assert out[2] == ("Banks", -2.0, 1)
