"""Market data layer: HTTP helper + Finnhub client.

Nothing here knows about Discord or the web. It takes a session, returns
plain dicts. That is what lets both UIs share it.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import aiohttp

from . import cache
from . import config

logger = logging.getLogger("MarketPulse")


async def fetch_json(session, url, params=None):
    """Fetch JSON with retries: backoff on 5xx/timeouts, obey Retry-After."""
    for attempt in range(3):
        try:
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT),
                # Skip brotli: some proxies serve "br" even when the client
                # can't decode it. gzip/deflate are always safe.
                headers={"Accept-Encoding": "gzip, deflate"},
            ) as response:
                if response.status == 429:
                    retry_after = response.headers.get("Retry-After", "5")
                    try:
                        delay = min(float(retry_after), 30)
                    except ValueError:
                        delay = 5
                    logger.warning("Rate limited. Waiting %.1f seconds.", delay)
                    await asyncio.sleep(delay)
                    continue

                if response.status >= 500:
                    await asyncio.sleep(2 ** attempt)
                    continue

                if response.status != 200:
                    logger.warning("API returned status %s", response.status)
                    return None

                return await response.json()

        except asyncio.TimeoutError:
            logger.warning("Request timed out. Attempt %s", attempt + 1)
        except aiohttp.ClientError as error:
            logger.warning("Network error: %s", error)

        if attempt < 2:
            await asyncio.sleep(2 ** attempt)

    return None


class FinnhubClient:
    """Finnhub market data. Caches quotes and news to respect rate limits."""

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, session, api_key=None):
        self.session = session
        # api_key is a parameter (not a module global) so tests can inject
        # a fake key and the web app can pass its own config.
        self.api_key = api_key or config.FINNHUB_API_KEY

    async def quote(self, symbol):
        cache_key = f"quote:{symbol}"
        cached = cache.get_cached(cache_key)
        if cached is not None:
            return cached

        data = await fetch_json(
            self.session,
            f"{self.BASE_URL}/quote",
            params={"symbol": symbol, "token": self.api_key},
        )

        if not isinstance(data, dict):
            return None

        price = data.get("c")
        previous_close = data.get("pc")

        if not isinstance(price, (int, float)) or price <= 0:
            return None
        if not isinstance(previous_close, (int, float)):
            previous_close = 0

        change_percent = (
            ((price - previous_close) / previous_close) * 100
            if previous_close > 0
            else 0
        )

        result = {
            "symbol": symbol,
            "price": price,
            "previous_close": previous_close,
            "change_percent": change_percent,
            "high": data.get("h"),
            "low": data.get("l"),
            "open": data.get("o"),
            "timestamp": data.get("t"),
        }

        cache.set_cached(cache_key, result, config.QUOTE_CACHE_SECONDS)
        return result

    async def company_news(self, symbol):
        cache_key = f"news:{symbol}"
        cached = cache.get_cached(cache_key)
        if cached is not None:
            return cached

        from datetime import timedelta

        today = datetime.now(timezone.utc).date()
        start = (today - timedelta(days=3)).strftime("%Y-%m-%d")

        data = await fetch_json(
            self.session,
            f"{self.BASE_URL}/company-news",
            params={
                "symbol": symbol,
                "from": start,
                "to": today.strftime("%Y-%m-%d"),
                "token": self.api_key,
            },
        )

        if not isinstance(data, list):
            return []

        news = []
        for item in data[:10]:
            if not isinstance(item, dict):
                continue
            headline = item.get("headline")
            if not headline:
                continue
            news.append({
                "headline": headline,
                "summary": item.get("summary", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "timestamp": item.get("datetime"),
            })

        cache.set_cached(cache_key, news, config.NEWS_CACHE_SECONDS)
        return news

    async def candles(self, symbol, resolution="5", days=1):
        """Recent intraday closes, for sparklines. Returns [float] or []."""
        cache_key = f"candles:{symbol}:{resolution}:{days}"
        cached = cache.get_cached(cache_key)
        if cached is not None:
            return cached

        now = int(datetime.now(timezone.utc).timestamp())
        data = await fetch_json(
            self.session,
            f"{self.BASE_URL}/stock/candle",
            params={
                "symbol": symbol,
                "resolution": resolution,
                "from": now - days * 86400,
                "to": now,
                "token": self.api_key,
            },
        )

        closes = []
        if isinstance(data, dict) and data.get("s") == "ok":
            raw = data.get("c") or []
            closes = [c for c in raw if isinstance(c, (int, float))]

        cache.set_cached(cache_key, closes, config.QUOTE_CACHE_SECONDS)
        return closes

    async def metrics_52w(self, symbol):
        """52-week high/low. Returns (high, low) or (None, None)."""
        cache_key = f"metric52:{symbol}"
        cached = cache.get_cached(cache_key)
        if cached is not None:
            return cached

        data = await fetch_json(
            self.session,
            f"{self.BASE_URL}/stock/metric",
            params={"symbol": symbol, "metric": "all",
                    "token": self.api_key},
        )

        high = low = None
        if isinstance(data, dict):
            m = data.get("metric", {}) or {}
            high = m.get("52WeekHigh")
            low = m.get("52WeekLow")
            if not isinstance(high, (int, float)):
                high = None
            if not isinstance(low, (int, float)):
                low = None

        result = (high, low)
        cache.set_cached(cache_key, result, 86400)
        return result

    async def insider_transactions(self, symbol, days=30):
        """Recent insider buys/sells, newest first. Zero-change rows skipped."""
        cache_key = f"insider:{symbol}:{days}"
        cached = cache.get_cached(cache_key)
        if cached is not None:
            return cached

        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=days)
        data = await fetch_json(
            self.session,
            f"{self.BASE_URL}/stock/insider-transactions",
            params={"symbol": symbol,
                    "from": start.isoformat(), "to": today.isoformat(),
                    "token": self.api_key},
        )

        out = []
        if isinstance(data, dict):
            for row in data.get("data", []) or []:
                try:
                    change = int(row.get("change") or 0)
                except (TypeError, ValueError):
                    change = 0
                if change == 0:
                    continue
                out.append({
                    "name": row.get("name") or "Insider",
                    "shares": abs(change),
                    "side": "bought" if change > 0 else "sold",
                    "price": row.get("transactionPrice"),
                    "date": (row.get("transactionDate") or "")[:10],
                })
        out.sort(key=lambda r: r["date"], reverse=True)

        cache.set_cached(cache_key, out, 21600)
        return out

    async def earnings_calendar(self, days_ahead=30):
        """symbol -> next earnings date (YYYY-MM-DD) within days_ahead."""
        cache_key = f"earnings:{days_ahead}"
        cached = cache.get_cached(cache_key)
        if cached is not None:
            return cached

        today = datetime.now(timezone.utc).date()
        end = today + timedelta(days=days_ahead)
        data = await fetch_json(
            self.session,
            f"{self.BASE_URL}/calendar/earnings",
            params={"from": today.isoformat(), "to": end.isoformat(),
                    "token": self.api_key},
        )

        out = {}
        if isinstance(data, dict):
            for row in data.get("earningsCalendar", []) or []:
                sym = (row.get("symbol") or "").upper()
                date = (row.get("date") or "")[:10]
                if sym and date and sym not in out:
                    out[sym] = date

        cache.set_cached(cache_key, out, 86400)
        return out
