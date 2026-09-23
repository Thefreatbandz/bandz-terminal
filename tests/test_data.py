"""Data-layer tests with a STUB session -- no network, no API keys."""

import asyncio

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
