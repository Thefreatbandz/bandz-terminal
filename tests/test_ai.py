"""AI fallback tests. No network, no keys -- the stub session fails the
Gemini call so we exercise the degraded (headline-fallback) path."""

import asyncio

import pytest

from marketpulse.ai import (DEGRADED_PREFIX, _ai_failed, _headline_fallback,
                            generate_ai_analysis, generate_market_brief,
                            generate_mover_explanation)


def _run(coro):
    return asyncio.run(coro)


class FailPostResponse:
    status = 400
    headers = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self):
        return {}


class FailSession:
    def post(self, *args, **kwargs):
        return FailPostResponse()


NEWS = [{"headline": "Acme beats earnings, shares jump"},
        {"headline": "Analysts raise price target"}]
QUOTE = {"price": 123.45, "change_percent": 5.67}


def test_ai_failed_detects_graceful_fallbacks():
    assert _ai_failed("AI analysis failed.")
    assert _ai_failed("AI analysis unavailable. Configure GEMINI_API_KEY.")
    assert not _ai_failed("Acme beat earnings because of strong demand.")


def test_headline_fallback_uses_headlines():
    text = _headline_fallback("ACME", NEWS)
    assert text.startswith(DEGRADED_PREFIX)
    assert "Acme beats earnings" in text
    assert "Analysts raise" in text


def test_headline_fallback_no_news():
    text = _headline_fallback("ACME", [])
    assert text.startswith(DEGRADED_PREFIX)
    assert "no headlines" in text


def test_mover_explanation_falls_back_to_headlines():
    text = _run(generate_mover_explanation(FailSession(), "ACME", QUOTE,
                                           NEWS))
    assert text.startswith(DEGRADED_PREFIX)
    assert "Acme beats earnings" in text
    assert "Couldn't pull an explanation" not in text


def test_card_explanation_falls_back_to_headlines():
    text = _run(generate_ai_analysis(FailSession(), "ACME", QUOTE, NEWS))
    assert text.startswith(DEGRADED_PREFIX)
    assert "Acme beats earnings" in text
    # Never the raw internal error message.
    assert "AI analysis failed." not in text


def test_market_brief_degrades_to_mover_list():
    items = [{"symbol": "ACME", "price": 1.0, "change_percent": 5.0,
              "headline": "h"}]
    text = _run(generate_market_brief(FailSession(), items))
    assert text.startswith(DEGRADED_PREFIX)
    assert "ACME" in text


# --- gemini_probe / classify_gemini_status ---

from marketpulse.ai import classify_gemini_status, gemini_probe


class _Resp:
    def __init__(self, status, payload=None):
        self.status = status
        self._payload = payload or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self):
        return self._payload

    async def text(self):
        return ""


class _Session:
    def __init__(self, resp):
        self._resp = resp

    def post(self, *args, **kwargs):
        return self._resp


class _TimeoutSession:
    def post(self, *args, **kwargs):
        raise asyncio.TimeoutError()


_OK = {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}
_BADKEY = {"error": {"message": "API key not valid. Please pass a valid API key."}}


def test_probe_live():
    ok, detail = _run(gemini_probe(_Session(_Resp(200, _OK))))
    assert ok and detail == "live"
    assert classify_gemini_status(ok, detail) == "live"


def test_probe_bad_key_classifies_key_rejected():
    ok, detail = _run(gemini_probe(_Session(_Resp(400, _BADKEY))))
    assert not ok
    assert "400" in detail and "API key not valid" in detail
    # the key itself must never leak into detail
    assert "AIza" not in detail
    assert classify_gemini_status(ok, detail) == "key-rejected"


def test_probe_timeout_classifies_network():
    ok, detail = _run(gemini_probe(_TimeoutSession()))
    assert not ok and detail == "timeout"
    assert classify_gemini_status(ok, detail) == "network"


def test_probe_empty_body():
    ok, detail = _run(gemini_probe(_Session(_Resp(200, {"candidates": []}))))
    assert not ok


def test_classify_gemini_status_cases():
    assert classify_gemini_status(False, "HTTP 404: models/x is not found") == "model-not-found"
    assert classify_gemini_status(False, "network unreachable") == "network"
    assert classify_gemini_status(False, "HTTP 500: backend error") == "error"


# --- generate_watchlist_digest ---

from marketpulse.ai import generate_watchlist_digest

DIGEST_ITEMS = [
    {"symbol": "NVDA", "price": 180.0, "change_pct": 4.2,
     "headlines": ["Nvidia beats earnings, shares jump"]},
    {"symbol": "SOFI", "price": 12.0, "change_pct": -3.1, "headlines": []},
]


def test_watchlist_digest_success_path(monkeypatch):
    async def fake_gemini(session, prompt):
        assert "NVDA" in prompt and "SOFI" in prompt
        return "Digest: NVDA up on earnings."
    monkeypatch.setattr("marketpulse.ai._gemini_text", fake_gemini)
    text = _run(generate_watchlist_digest(FailSession(), DIGEST_ITEMS))
    assert text == "Digest: NVDA up on earnings."


def test_watchlist_digest_falls_back_labeled():
    text = _run(generate_watchlist_digest(FailSession(), DIGEST_ITEMS))
    assert text.startswith(DEGRADED_PREFIX)
    assert "NVDA" in text
    # never the raw internal error message
    assert "AI analysis failed." not in text


def test_watchlist_digest_empty_items_fallback():
    text = _run(generate_watchlist_digest(FailSession(), []))
    assert text.startswith(DEGRADED_PREFIX)
    assert "empty" in text
