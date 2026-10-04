#!/usr/bin/env python3
"""Morning briefing -- weekdays 8:30 AM ET via cron.

Prints notification lines following the same stdout contract as
check_alerts.py (the scheduled runner consumes these):
  MARKET_CLOSED  -> nothing to report / not a briefing day
  NO_ALERTS      -> ran fine, nothing notable
  TRIGGERED:...  -> briefing lines the runner messages to the user

Contents: top gainers/losers (Core 25), today's earnings, and a 2-3
sentence Gemini brief. Research/watch-only -- not financial advice.
"""

import asyncio
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))

from dotenv import load_dotenv

load_dotenv()

import aiohttp  # noqa: E402

from marketpulse.ai import generate_market_brief  # noqa: E402
from marketpulse.config import CORE_STOCKS, FINNHUB_API_KEY  # noqa: E402
from marketpulse.data import (FinnhubClient, unusual_volume_ratio,  # noqa: E402
                              yahoo_daily_volumes)
from marketpulse.engine import scan_universe  # noqa: E402

VOLUME_SPIKE_X = 2.0  # yesterday's volume vs 20-day avg

ET = ZoneInfo("America/New_York")


def main():
    now = datetime.now(ET)
    if now.weekday() >= 5:
        print("NO_ALERTS")
        return
    if not FINNHUB_API_KEY:
        print("NO_ALERTS", file=sys.stderr)
        print("NO_ALERTS")
        return
    asyncio.run(_brief(now))


async def _brief(now):
    today = now.date().isoformat()
    async with aiohttp.ClientSession(trust_env=True) as session:
        client = FinnhubClient(session)
        results = await scan_universe(client, list(CORE_STOCKS),
                                      include_ai=False, news_top_n=3,
                                      delay=0.25)
        earnings = await client.earnings_calendar()

    scored = [r for r in results if r.get("quote", {}).get("price")]
    if not scored:
        print("MARKET_CLOSED")
        return

    by_move = sorted(scored,
                     key=lambda r: r["quote"]["change_percent"],
                     reverse=True)
    gainers = by_move[:3]
    losers = by_move[-3:][::-1]

    def leg(r):
        q = r["quote"]
        return f"{r['symbol']} {q['change_percent']:+.2f}%"

    print(f"TRIGGERED: Morning brief {today} -- "
          f"top gainers: {', '.join(leg(r) for r in gainers)} | "
          f"top losers: {', '.join(leg(r) for r in losers)}")

    todays = sorted(s for s, d in earnings.items() if d == today)
    if todays:
        print(f"TRIGGERED: Earnings today: {', '.join(todays)}")
    else:
        print("TRIGGERED: No earnings reports scheduled today.")

    # Unusual volume: yesterday's volume vs 20-day average (Yahoo daily).
    spikes = []
    async with aiohttp.ClientSession(trust_env=True) as session:
        for r in scored:
            vols = await yahoo_daily_volumes(session, r["symbol"])
            ratio = unusual_volume_ratio(vols)
            if ratio is not None and ratio >= VOLUME_SPIKE_X:
                spikes.append((r["symbol"], ratio))
    if spikes:
        spikes.sort(key=lambda t: t[1], reverse=True)
        legs = ", ".join(f"{s} {x:.1f}x avg" for s, x in spikes[:5])
        print(f"TRIGGERED: Unusual volume last session: {legs}")

    movers = sorted(scored,
                    key=lambda r: abs(r["quote"]["change_percent"]),
                    reverse=True)[:8]
    items = []
    for r in movers:
        news = r.get("news") or []
        items.append({
            "symbol": r["symbol"],
            "price": r["quote"]["price"],
            "change_percent": r["quote"]["change_percent"],
            "headline": news[0]["headline"] if news else "no fresh headline",
        })
    async with aiohttp.ClientSession(trust_env=True) as session:
        brief = await generate_market_brief(session, items)
    print(f"TRIGGERED: {brief} (Not financial advice.)")


if __name__ == "__main__":
    main()
