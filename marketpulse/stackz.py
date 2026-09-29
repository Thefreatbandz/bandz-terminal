"""Stackz paper-trading snapshot: fetch + parse helpers.

The snapshot is a public gist (paper-trade data only, no secrets)
refreshed every 15 minutes by the Stackz runner. web.py fetches it
inside an st.cache_data(ttl=900) wrapper; everything here is pure so
it stays unit-testable.

Every function is defensive: a dead network, bad JSON, or a weird
payload yields None/empty instead of raising, so the dashboard shows
an honest empty state rather than crashing.
"""

import json
import logging
import urllib.request
from datetime import datetime, timezone

logger = logging.getLogger("MarketPulse")

#: Public gist with the latest Stackz paper-trading snapshot.
STACKZ_SNAPSHOT_URL = (
    "https://gist.githubusercontent.com/Thefreatbandz/"
    "bbb49c338076ecf51509c3b08410bd3a/raw/stackz.json"
)

#: Snapshots older than this are treated as stale (empty state).
STALE_MINUTES = 90


def _default_fetch(url, timeout=20):
    """Read raw bytes from url. Raises on network failure."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "BandzTerminal/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_stackz_snapshot(url=STACKZ_SNAPSHOT_URL, fetcher=None):
    """Fetch + parse the snapshot. Never raises; None on any failure."""
    try:
        raw = (fetcher or _default_fetch)(url, timeout=20)
        payload = json.loads(raw)
    except Exception:
        logger.debug("Stackz snapshot fetch failed", exc_info=True)
        return None
    return parse_stackz_snapshot(payload)


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_stackz_snapshot(payload):
    """Validate + normalize a decoded snapshot dict.

    Returns None for anything that isn't a plausible snapshot.
    """
    if not isinstance(payload, dict):
        return None
    run_at = payload.get("run_at")
    if not isinstance(run_at, str) or not run_at:
        return None
    equity = payload.get("equity")
    if not isinstance(equity, dict):
        return None
    positions = []
    for p in payload.get("positions") or []:
        if not isinstance(p, dict) or not p.get("symbol"):
            continue
        positions.append({
            "symbol": str(p["symbol"]),
            "qty": _num(p.get("qty")),
            "avg": _num(p.get("avg")),
            "last": _num(p.get("last")),
            "pnl": _num(p.get("pnl")),
            "stop": _num(p.get("stop")),
            "target": _num(p.get("target")),
        })
    trades = []
    for t in payload.get("trades") or []:
        if not isinstance(t, dict):
            continue
        trades.append({
            "time": t.get("time"),
            "symbol": t.get("symbol"),
            "side": t.get("side"),
            "qty": _num(t.get("qty")),
            "price": _num(t.get("price")),
            "strategy": t.get("strategy"),
            "realized_pnl": _num(t.get("realized_pnl")),
            "reason": t.get("reason"),
        })
    ks = payload.get("kill_switch") or {}
    return {
        "run_at": run_at,
        "equity": {
            "paper": _num(equity.get("paper")),
            "effective": _num(equity.get("effective")),
            "day_pnl_pct": _num(equity.get("day_pnl_pct")),
        },
        "positions": positions,
        "trades": trades,
        "kill_switch": {
            "status": ks.get("status"),
            "daily_pnl_pct": _num(ks.get("daily_pnl_pct")),
        },
        "day_stats": payload.get("day_stats") or {},
    }


def snapshot_age_minutes(snapshot):
    """Minutes since run_at. None when run_at is missing/unparseable."""
    try:
        run_at = (snapshot or {}).get("run_at")
        dt = datetime.fromisoformat(run_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return delta.total_seconds() / 60.0
    except (TypeError, ValueError, AttributeError):
        return None


def is_fresh(snapshot, max_minutes=STALE_MINUTES):
    """True when the snapshot exists and run_at is recent enough."""
    age = snapshot_age_minutes(snapshot)
    return age is not None and 0 <= age <= max_minutes


def paper_positions(snapshot):
    """Normalized open positions (may be empty)."""
    return list((snapshot or {}).get("positions") or [])


def recent_trades(snapshot, n=10):
    """Last n trades, newest first."""
    trades = list((snapshot or {}).get("trades") or [])
    return trades[-n:][::-1]


def effective_equity(snapshot):
    """Paper equity scaled to the $1,000 effective book."""
    return (snapshot or {}).get("equity", {}).get("effective")


def day_pnl_pct(snapshot):
    """Today's P&L in percent of the effective book."""
    return (snapshot or {}).get("equity", {}).get("day_pnl_pct")


def kill_switch(snapshot):
    """(status, daily_pnl_pct) for the kill-switch pill."""
    ks = (snapshot or {}).get("kill_switch", {})
    return ks.get("status"), ks.get("daily_pnl_pct")


def signed_dollars(value):
    """+$0.19 / -$0.19 style for P&L figures, em dash when unknown."""
    if not isinstance(value, (int, float)):
        return "—"
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.2f}"
