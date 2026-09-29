"""Stackz snapshot tests. No network -- the fetcher is injected."""

import json
from datetime import datetime, timedelta, timezone

from marketpulse import stackz


def _fixture(age_minutes=5):
    run_at = (datetime.now(timezone.utc)
              - timedelta(minutes=age_minutes)).isoformat()
    return {
        "run_at": run_at,
        "equity": {"paper": 99997.92, "effective": 999.99,
                   "day_pnl_pct": -0.001},
        "positions": [
            {"symbol": "AMD", "qty": 0.0486, "avg": 616.47, "last": 612.48,
             "pnl": -0.19, "stop": 585.65, "target": 678.12},
            {"symbol": "AMZN", "qty": 0.0814, "avg": 245.87, "last": 246.94,
             "pnl": 0.09, "stop": 233.58, "target": 270.46},
        ],
        "trades": [
            {"time": "2026-09-29T15:00:00+00:00", "symbol": "AMZN",
             "side": "buy", "qty": 0.08, "price": 245.87,
             "strategy": "atr_breakout", "realized_pnl": 0.0,
             "reason": "breakout"},
            {"time": "2026-09-29T16:00:00+00:00", "symbol": "AMD",
             "side": "sell", "qty": 0.05, "price": 612.48,
             "strategy": "williams_r", "realized_pnl": -0.19,
             "reason": "stop hit"},
        ],
        "kill_switch": {"status": "OK", "daily_pnl_pct": 0.0},
        "day_stats": {"trades": 7, "realized_pnl": -0.34},
    }


def _ok_fetcher(payload):
    def fetch(url, timeout=20):
        return json.dumps(payload).encode()
    return fetch


def test_fetch_ok_returns_snapshot():
    snap = stackz.fetch_stackz_snapshot(fetcher=_ok_fetcher(_fixture()))
    assert snap["equity"]["effective"] == 999.99
    assert len(snap["positions"]) == 2


def test_fetch_network_failure_returns_none():
    def boom(url, timeout=20):
        raise OSError("no route")
    assert stackz.fetch_stackz_snapshot(fetcher=boom) is None


def test_fetch_bad_json_returns_none():
    def bad(url, timeout=20):
        return b"not json {"
    assert stackz.fetch_stackz_snapshot(fetcher=bad) is None


def test_parse_rejects_garbage():
    assert stackz.parse_stackz_snapshot(None) is None
    assert stackz.parse_stackz_snapshot({}) is None
    assert stackz.parse_stackz_snapshot({"run_at": "x"}) is None
    assert stackz.parse_stackz_snapshot([]) is None


def test_age_and_freshness():
    fresh = stackz.parse_stackz_snapshot(_fixture(age_minutes=5))
    age = stackz.snapshot_age_minutes(fresh)
    assert 0 <= age < 90
    assert stackz.is_fresh(fresh)

    stale = stackz.parse_stackz_snapshot(_fixture(age_minutes=120))
    assert stackz.snapshot_age_minutes(stale) >= 120
    assert not stackz.is_fresh(stale)


def test_age_none_when_unparseable():
    assert stackz.snapshot_age_minutes(None) is None
    assert stackz.snapshot_age_minutes({}) is None
    assert not stackz.is_fresh(None)


def test_position_and_trade_helpers():
    snap = stackz.parse_stackz_snapshot(_fixture())
    poss = stackz.paper_positions(snap)
    assert [p["symbol"] for p in poss] == ["AMD", "AMZN"]
    assert poss[0]["pnl"] == -0.19

    trades = stackz.recent_trades(snap, n=10)
    assert len(trades) == 2
    # newest first
    assert trades[0]["symbol"] == "AMD"
    assert trades[1]["symbol"] == "AMZN"

    assert stackz.effective_equity(snap) == 999.99
    assert stackz.day_pnl_pct(snap) == -0.001
    assert stackz.kill_switch(snap) == ("OK", 0.0)


def test_signed_dollars():
    assert stackz.signed_dollars(0.09) == "+$0.09"
    assert stackz.signed_dollars(-1.5) == "-$1.50"
    assert stackz.signed_dollars(0) == "+$0.00"
    assert stackz.signed_dollars(None) == "—"
    assert stackz.signed_dollars("x") == "—"


def test_snapshot_url_constant():
    assert stackz.STACKZ_SNAPSHOT_URL.startswith("https://")
    assert "stackz.json" in stackz.STACKZ_SNAPSHOT_URL
