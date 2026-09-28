#!/usr/bin/env python3
"""Check alerts and report any that fired.

Run by cron every 30 minutes on weekdays. Output contract:
  MARKET_CLOSED  -> market shut, nothing to do (stay silent)
  NO_ALERTS      -> checked, nothing fired (stay silent)
  TRIGGERED: ... -> one line per fired alert (message the user)

Alert types:
  price   -- |move| vs armed baseline reaches pct, then re-arms.
  pct     -- |day change| reaches threshold. Fires at most once per day.
  keyword -- a fresh headline in the scanned news contains the keyword.
             Notifies once per headline.

No alerts configured yet? Prints NO_ALERTS (price baselines get armed).
"""

import asyncio
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from marketpulse import alerts as alert_store
from marketpulse import config
from marketpulse import watchlist as watchlist_store
from marketpulse.data import FinnhubClient


def market_open():
    et = datetime.now(ZoneInfo("America/New_York"))
    mins = et.hour * 60 + et.minute
    return et.weekday() < 5 and 9 * 60 <= mins < 16 * 60 + 30


async def _check_price(client, alert):
    """Original price-move alert. Returns (fired_lines, changed)."""
    quote = await client.quote(alert["symbol"])
    if not quote:
        return [], False
    price = quote["price"]
    if alert.get("baseline") is None:
        alert["baseline"] = price
        return [], True  # armed, not fired
    base = alert["baseline"]
    move = (price - base) / base * 100 if base else 0
    if abs(move) >= alert["pct"]:
        alert["baseline"] = price  # re-arm at the new price
        line = (f"TRIGGERED: {alert['symbol']} moved {move:+.2f}% "
                f"to ${price:.2f} (was ${base:.2f}, "
                f"threshold ±{alert['pct']:g}%)")
        return [line], True
    return [], False


async def _check_pct(client, alert):
    """Day-change-% alert. Fires at most once per calendar day (ET)."""
    quote = await client.quote(alert.get("symbol"))
    if not quote:
        return [], False
    today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    if alert.get("last_fired") == today:
        return [], False
    change = quote.get("change_percent") or 0
    if abs(change) >= alert["threshold"]:
        alert["last_fired"] = today
        line = (f"TRIGGERED: {alert['symbol']} moved {change:+.2f}% today "
                f"(threshold ±{alert['threshold']:g}%) — "
                f"now ${quote['price']:.2f}")
        return [line], True
    return [], False


async def _check_keyword(client, alert, news_cache):
    """News-keyword alert over Core 25 + custom watchlist news."""
    keyword = (alert.get("keyword") or "").strip().lower()
    if not keyword:
        return [], False
    symbols = list(config.CORE_STOCKS)
    for entry in watchlist_store.load_watchlist():
        if entry["symbol"] not in symbols:
            symbols.append(entry["symbol"])
    seen = set(alert.get("seen") or [])
    matches = []
    for symbol in symbols:
        if symbol not in news_cache:
            news_cache[symbol] = await client.company_news(symbol) or []
        for item in news_cache[symbol]:
            head = (item.get("headline") or "").strip()
            if keyword in head.lower():
                key = f"{symbol}|{head[:80]}"
                if key not in seen:
                    seen.add(key)
                    matches.append((symbol, head))
    if not matches:
        return [], False
    alert["seen"] = sorted(seen)[-100:]
    lines = [f"TRIGGERED: keyword '{alert['keyword']}' in {sym}: "
             f"{head[:140]}" for sym, head in matches[:5]]
    if len(matches) > 5:
        lines.append(f"TRIGGERED: ... and {len(matches) - 5} more "
                     f"'{alert['keyword']}' headlines")
    return lines, True


async def check():
    stored = alert_store.load_alerts()
    if not stored:
        print("NO_ALERTS")
        return

    async with aiohttp.ClientSession(trust_env=True) as session:
        client = FinnhubClient(session)
        fired = []
        changed = False
        news_cache = {}
        for alert in stored:
            atype = alert.get("type", "price")
            if atype == "pct":
                lines, touched = await _check_pct(client, alert)
            elif atype == "keyword":
                lines, touched = await _check_keyword(client, alert,
                                                      news_cache)
            else:
                lines, touched = await _check_price(client, alert)
            fired.extend(lines)
            changed = changed or touched
        if changed:
            alert_store.save_alerts(stored)
        if fired:
            print("\n".join(fired))
        else:
            print("NO_ALERTS")


if __name__ == "__main__":
    if not market_open():
        print("MARKET_CLOSED")
    else:
        asyncio.run(check())
