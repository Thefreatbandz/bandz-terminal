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
