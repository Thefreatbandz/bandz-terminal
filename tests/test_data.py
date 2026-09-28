"""Data-layer tests with a STUB session -- no network, no API keys."""

import asyncio

import pytest

from marketpulse import cache
from marketpulse.data import FinnhubClient, fetch_json


class StubResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status
        self.headers = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self):
        return self._payload


class StubSession:
    def __init__(self, payload, status=200):
        self._payload = payload
        self._status = status

    def get(self, url, **kwargs):
        return StubResponse(self._payload, self._status)


def _run(coro):
    return asyncio.run(coro)


def setup_function():
    cache.clear()


def test_candles_returns_closes():
    session = StubSession({"s": "ok", "c": [10.0, 10.5, 11.0], "t": [1, 2, 3]})
    client = FinnhubClient(session, api_key="fake")
    assert _run(client.candles("AAA")) == [10.0, 10.5, 11.0]


def test_candles_empty_when_no_data():
    session = StubSession({"s": "no_data"})
    client = FinnhubClient(session, api_key="fake")
    assert _run(client.candles("AAA")) == []


def test_candles_skips_bad_values():
    session = StubSession({"s": "ok", "c": [10.0, None, "x", 11.0]})
    client = FinnhubClient(session, api_key="fake")
    assert _run(client.candles("AAA")) == [10.0, 11.0]


def test_fetch_json_returns_none_on_http_error():
    session = StubSession({}, status=400)
    assert _run(fetch_json(session, "http://x")) is None


def test_metrics_52w_parses_high_low():
    session = StubSession({"metric": {"52WeekHigh": 200.0, "52WeekLow": 100.0}})
    client = FinnhubClient(session, api_key="fake")
    assert _run(client.metrics_52w("AAA")) == (200.0, 100.0)


def test_metrics_52w_none_when_missing():
    session = StubSession({"metric": {}})
    client = FinnhubClient(session, api_key="fake")
    assert _run(client.metrics_52w("AAA")) == (None, None)


def test_insider_skips_zero_change_and_sorts():
    payload = {"data": [
        {"name": "Smith, Jane", "change": 0, "transactionPrice": 10.0,
         "transactionDate": "2026-09-20T00:00:00"},
        {"name": "Doe, John", "change": 5000, "transactionPrice": 12.5,
         "transactionDate": "2026-09-18T00:00:00"},
        {"name": "Roe, Ann", "change": -2000, "transactionPrice": 13.0,
         "transactionDate": "2026-09-21T00:00:00"},
    ]}
    client = FinnhubClient(StubSession(payload), api_key="fake")
    out = _run(client.insider_transactions("AAA"))
    assert len(out) == 2
    assert out[0]["name"] == "Roe, Ann" and out[0]["side"] == "sold"
    assert out[1]["side"] == "bought" and out[1]["shares"] == 5000


def test_earnings_calendar_maps_symbol_to_date():
    payload = {"earningsCalendar": [
        {"symbol": "aapl", "date": "2026-10-28T00:00:00"},
        {"symbol": "", "date": "2026-10-29T00:00:00"},
    ]}
    client = FinnhubClient(StubSession(payload), api_key="fake")
    assert _run(client.earnings_calendar()) == {"AAPL": "2026-10-28"}


class UrlStubSession:
    """Stub that serves different payloads per URL substring."""

    def __init__(self, routes):
        # routes: list of (url_substring, payload, status)
        self._routes = routes

    def get(self, url, **kwargs):
        for sub, payload, status in self._routes:
            if sub in url:
                return StubResponse(payload, status)
        return StubResponse({}, 404)


YAHOO_CHART_PAYLOAD = {
    "chart": {"result": [{
        "meta": {
            "regularMarketPrice": 150.0,
            "chartPreviousClose": 145.0,
            "regularMarketDayHigh": 152.0,
            "regularMarketDayLow": 144.0,
            "regularMarketOpen": 146.0,
            "regularMarketTime": 1720000000,
        },
    }]},
}


def test_quote_uses_finnhub_when_healthy():
    session = UrlStubSession([
        ("finnhub.io", {"c": 100.0, "pc": 95.0, "h": 101.0, "l": 94.0,
                        "o": 96.0, "t": 1720000000}, 200),
    ])
    client = FinnhubClient(session, api_key="fake")
    q = _run(client.quote("AAA"))
    assert q["price"] == 100.0
    assert q["change_percent"] == pytest.approx(100.0 * 5.0 / 95.0)
    assert q["source"] == "finnhub"


def test_quote_falls_back_to_yahoo_when_finnhub_fails():
    session = UrlStubSession([
        ("finnhub.io", {}, 403),
        ("yahoo", YAHOO_CHART_PAYLOAD, 200),
    ])
    client = FinnhubClient(session, api_key="fake")
    q = _run(client.quote("AAA"))
    assert q is not None
    assert q["price"] == 150.0
    assert q["previous_close"] == 145.0
    assert q["change_percent"] == pytest.approx(100.0 * 5.0 / 145.0)
    assert q["high"] == 152.0
    assert q["source"] == "yahoo"


def test_quote_falls_back_to_yahoo_on_bad_finnhub_data():
    session = UrlStubSession([
        ("finnhub.io", {"c": 0, "pc": 0}, 200),  # invalid quote
        ("yahoo", YAHOO_CHART_PAYLOAD, 200),
    ])
    client = FinnhubClient(session, api_key="fake")
    q = _run(client.quote("AAA"))
    assert q is not None and q["source"] == "yahoo"


def test_quote_none_when_both_providers_fail():
    session = UrlStubSession([
        ("finnhub.io", {}, 500),
        ("yahoo", {}, 404),
    ])
    client = FinnhubClient(session, api_key="fake")
    assert _run(client.quote("AAA")) is None


def test_yahoo_symbol_mapping():
    assert FinnhubClient._yahoo_symbol("BINANCE:BTCUSDT") == "BTC-USD"
    assert FinnhubClient._yahoo_symbol("BRK.B") == "BRK-B"
    assert FinnhubClient._yahoo_symbol("AAPL") == "AAPL"


def test_company_news_uses_finnhub_when_available():
    cache.clear()
    payload = [{"headline": "Finnhub story", "summary": "s",
                "url": "http://fh", "source": "FH", "datetime": 1720000000}]
    session = UrlStubSession([("finnhub.io", payload, 200)])
    client = FinnhubClient(session, api_key="fake")
    news = _run(client.company_news("AAA"))
    assert len(news) == 1
    assert news[0]["headline"] == "Finnhub story"
    assert news[0]["source"] == "FH"


def test_company_news_falls_back_to_yahoo():
    cache.clear()
    yahoo_payload = {"news": [
        {"title": "Yahoo story", "link": "http://yh",
         "publisher": "Yahoo Finance", "providerPublishTime": 1720000000},
    ]}
    session = UrlStubSession([
        ("finnhub.io", {}, 401),
        ("yahoo", yahoo_payload, 200),
    ])
    client = FinnhubClient(session, api_key="fake")
    news = _run(client.company_news("AAA"))
    assert len(news) == 1
    assert news[0]["headline"] == "Yahoo story"
    assert news[0]["url"] == "http://yh"
    assert news[0]["source"] == "Yahoo Finance"
    assert news[0]["timestamp"] == 1720000000


def test_company_news_empty_when_both_fail():
    cache.clear()
    session = UrlStubSession([
        ("finnhub.io", {}, 500),
        ("yahoo", {}, 404),
    ])
    client = FinnhubClient(session, api_key="fake")
    assert _run(client.company_news("AAA")) == []


def test_yahoo_news_maps_crypto_symbol():
    assert FinnhubClient._yahoo_symbol("BINANCE:ETHUSDT") == "ETH-USD"
