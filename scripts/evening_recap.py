#!/usr/bin/env python3
"""Evening recap -- weekdays 6:30 PM ET via cron.

Prints notification lines following the same stdout contract as
check_alerts.py / morning_brief.py (the scheduled runner consumes these):
  MARKET_CLOSED  -> nothing to report / not a recap day
  NO_ALERTS      -> ran fine, nothing notable
  TRIGGERED:...  -> recap lines the runner messages to the user

Contents: today's biggest movers (Core 25), today's + tomorrow's
earnings, and a one-paragraph Gemini recap of the session.
Research/watch-only -- not financial advice.

Runtime: one Core-25 scan with light pacing, same as morning_brief.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))

from dotenv import load_dotenv

load_dotenv()

import aiohttp  # noqa: E402

from marketpulse.ai import generate_market_brief  # noqa: E402
from marketpulse.config import CORE_STOCKS, FINNHUB_API_KEY  # noqa: E402
from marketpulse.data import FinnhubClient  # noqa: E402
from marketpulse.engine import scan_universe  # noqa: E402

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
    asyncio.run(_recap(now))


async def _recap(now):
    today = now.date().isoformat()
    tomorrow = (now.date() + timedelta(days=1)).isoformat()
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

    by_abs = sorted(scored,
                    key=lambda r: abs(r["quote"]["change_percent"]),
                    reverse=True)
    movers = by_abs[:5]

    def leg(r):
        q = r["quote"]
        return f"{r['symbol']} {q['change_percent']:+.2f}%"

    print(f"TRIGGERED: Evening recap {today} -- biggest movers: "
          f"{', '.join(leg(r) for r in movers)}")

    todays = sorted(s for s, d in earnings.items() if d == today)
    tmrs = sorted(s for s, d in earnings.items() if d == tomorrow)
    if todays:
        print(f"TRIGGERED: Earnings today: {', '.join(todays)}")
    else:
        print("TRIGGERED: No earnings reports today.")
    if tmrs:
        print(f"TRIGGERED: Earnings tomorrow: {', '.join(tmrs)}")

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
