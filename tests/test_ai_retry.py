"""Tests for Gemini retry/backoff in _gemini_text."""
import asyncio
import sys
import os

import pytest  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))

from marketpulse import ai  # noqa: E402


def _payload(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


class _Resp:
    def __init__(self, status, headers=None, payload=None):
        self.status = status
        self.headers = headers or {}
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self):
        return self._payload


class _Session:
    """Fake aiohttp session yielding scripted outcomes.

    Each outcome is ("status", code[, headers][, payload]),
    ("timeout",), or ("boom",).
    """

    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls = 0

    def post(self, *args, **kwargs):
        self.calls += 1
        kind = self._outcomes.pop(0)
        if kind[0] == "timeout":
            raise asyncio.TimeoutError()
        if kind[0] == "boom":
            raise RuntimeError("network down")
        _, code = kind[0], kind[1]
        headers = kind[2] if len(kind) > 2 else {}
        payload = kind[3] if len(kind) > 3 else None
        return _Resp(code, headers, payload)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    real_sleep = asyncio.sleep
    monkeypatch.setattr(asyncio, "sleep", lambda s: real_sleep(0))


def test_retry_503_then_success(monkeypatch):
    s = _Session([("status", 503),
                  ("status", 200, {}, _payload("hello ai"))])
    assert _run(ai._gemini_text(s, "hi", tries=3)) == "hello ai"
    assert s.calls == 2


def test_gives_up_after_tries_with_rate_limit_note(monkeypatch):
    s = _Session([("status", 429), ("status", 429)])
    out = _run(ai._gemini_text(s, "hi", tries=2))
    assert "rate-limited" in out
    assert s.calls == 2


def test_timeout_then_success(monkeypatch):
    s = _Session([("timeout",),
                  ("status", 200, {}, _payload("back"))])
    assert _run(ai._gemini_text(s, "hi", tries=3)) == "back"
    assert s.calls == 2


def test_non_retryable_error_returns_immediately():
    s = _Session([("status", 400)])
    assert _run(ai._gemini_text(s, "hi", tries=3)) == "AI analysis failed."
    assert s.calls == 1


def test_hard_exception_returns_immediately():
    s = _Session([("boom",)])
    assert _run(ai._gemini_text(s, "hi", tries=3)) == "AI analysis unavailable."
    assert s.calls == 1
