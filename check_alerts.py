#!/usr/bin/env python3
"""Check price alerts and report any that fired.

Run by cron every 30 minutes on weekdays. Output contract:
  MARKET_CLOSED  -> market shut, nothing to do (stay silent)
  NO_ALERTS      -> checked, nothing fired (stay silent)
  TRIGGERED: ... -> one line per fired alert (message the user)

No alerts configured yet? Prints NO_ALERTS (baselines get armed).
"""

import asyncio
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from marketpulse import alerts as alert_store
from marketpulse.data import FinnhubClient


def market_open():
    et = datetime.now(ZoneInfo("America/New_York"))
    mins = et.hour * 60 + et.minute
    return et.weekday() < 5 and 9 * 60 <= mins < 16 * 60 + 30


async def check():
    stored = alert_store.load_alerts()
    if not stored:
        print("NO_ALERTS")
        return

    async with aiohttp.ClientSession(trust_env=True) as session:
        client = FinnhubClient(session)
        fired = []
        changed = False
        for alert in stored:
            quote = await client.quote(alert["symbol"])
            if not quote:
                continue
            price = quote["price"]
            if alert.get("baseline") is None:
                alert["baseline"] = price
                changed = True
                continue
            base = alert["baseline"]
            move = (price - base) / base * 100 if base else 0
            if abs(move) >= alert["pct"]:
                fired.append(
                    f"TRIGGERED: {alert['symbol']} moved {move:+.2f}% "
                    f"to ${price:.2f} (was ${base:.2f}, "
                    f"threshold ±{alert['pct']:g}%)"
                )
                alert["baseline"] = price  # re-arm at the new price
                changed = True
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
