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
    YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart"

    def __init__(self, session, api_key=None):
        self.session = session
        # api_key is a parameter (not a module global) so tests can inject
        # a fake key and the web app can pass its own config.
        self.api_key = api_key or config.FINNHUB_API_KEY

    @staticmethod
    def _yahoo_symbol(symbol):
        """Map our symbol format to Yahoo's: BINANCE:BTCUSDT -> BTC-USD."""
        if ":" in symbol:
            symbol = symbol.split(":")[-1].replace("USDT", "-USD")
        return symbol.replace(".", "-")

    async def _yahoo_quote(self, symbol):
        """Quote via Yahoo's free chart API (no key).

        Fallback for when Finnhub is unreachable, rate-limited, or the
        plan doesn't cover the symbol -- the FX strip and sparklines
        already rely on this same endpoint, so it's proven reachable.
        Returns the same dict shape as quote(), tagged source="yahoo".
        """
        url = f"{self.YAHOO_CHART}/{self._yahoo_symbol(symbol)}"
        try:
            async with self.session.get(
                url,
                params={"interval": "1d", "range": "5d"},
                headers={"User-Agent": "Mozilla/5.0",
                         "Accept-Encoding": "gzip, deflate"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status != 200:
                    return None
                data = await response.json()
        except Exception:
            return None
        result = (data.get("chart", {}).get("result") or [None])[0]
        meta = (result or {}).get("meta") or {}
        price = meta.get("regularMarketPrice")
        previous_close = (meta.get("chartPreviousClose")
                          or meta.get("previousClose"))
        if not isinstance(price, (int, float)) or price <= 0:
            return None
        if not isinstance(previous_close, (int, float)) \
                or previous_close <= 0:
            previous_close = 0
        change_percent = (
            ((price - previous_close) / previous_close) * 100
            if previous_close > 0
            else 0
        )
        return {
            "symbol": symbol,
            "price": float(price),
            "previous_close": float(previous_close),
            "change_percent": change_percent,
            "high": meta.get("regularMarketDayHigh"),
            "low": meta.get("regularMarketDayLow"),
            "open": meta.get("regularMarketOpen"),
            "timestamp": meta.get("regularMarketTime"),
            "source": "yahoo",
        }

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

        result = None
        if isinstance(data, dict):
            price = data.get("c")
            previous_close = data.get("pc")
            if isinstance(price, (int, float)) and price > 0:
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
                    "source": "finnhub",
                }

        if result is None:
            # Finnhub missed (blocked IP, bad key, rate limit, unknown
            # symbol). Try Yahoo before giving up so one provider's
            # outage can't blank the whole board.
            result = await self._yahoo_quote(symbol)

        if result is None:
            return None

        cache.set_cached(cache_key, result, config.QUOTE_CACHE_SECONDS)
        return result

    async def company_news(self, symbol):
        cache_key = f"news:{symbol}"
        cached = cache.get_cached(cache_key)
        if cached is not None:
            return cached

        from datetime import timedelta

        today = datetime.now(timezone.utc).date()
        start = (today - timedelta(days=7)).strftime("%Y-%m-%d")

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

        news = []
        if isinstance(data, list):
            for item in data[:15]:
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

        if not news:
            # Finnhub news empty or blocked (e.g. from Streamlit Cloud) --
            # fall back to Yahoo's free search API so the wire never blanks.
            news = await self._yahoo_news(symbol)

        cache.set_cached(cache_key, news, config.NEWS_CACHE_SECONDS)
        return news

    async def _yahoo_news(self, symbol):
        """Headlines from Yahoo's free search API. Same dict shape as
        company_news. Empty list when unreachable."""
        ysym = self._yahoo_symbol(symbol)
        try:
            async with self.session.get(
                "https://query1.finance.yahoo.com/v1/finance/search",
                params={"q": ysym},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
        except Exception:
            return []
        items = data.get("news") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return []
        news = []
        for item in items[:10]:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            if not title:
                continue
            ts = item.get("providerPublishTime")
            if isinstance(ts, (int, float)) and ts > 1e12:
                ts = ts / 1000  # ms -> s
            news.append({
                "headline": title,
                "summary": "",
                "url": item.get("link", ""),
                "source": item.get("publisher") or "Yahoo",
                "timestamp": ts,
            })
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

    async def recommendation(self, symbol):
        """Analyst consensus from the most recent recommendation period.

        Returns {"label": "STRONG BUY", "analysts": 28, "buy": 65, ...}
        or None when unavailable (e.g. plan doesn't cover the endpoint).
        Cached 24h.
        """
        cache_key = f"reco:{symbol}"
        cached = cache.get_cached(cache_key)
        if cached is not None:
            return cached

        data = await fetch_json(
            self.session,
            f"{self.BASE_URL}/stock/recommendation",
            params={"symbol": symbol, "token": self.api_key},
        )

        result = None
        if isinstance(data, list) and data:
            latest = max(data, key=lambda r: r.get("period") or "")
            counts = {
                "STRONG BUY": latest.get("strongBuy") or 0,
                "BUY": latest.get("buy") or 0,
                "HOLD": latest.get("hold") or 0,
                "SELL": latest.get("sell") or 0,
                "STRONG SELL": latest.get("strongSell") or 0,
            }
            total = sum(counts.values())
            if total > 0:
                label = max(counts, key=counts.get)
                result = {"label": label, "analysts": total, **counts}

        cache.set_cached(cache_key, result, 86400)
        return result

    async def forex_rates(self, base="USD"):
        """Fiat FX rates vs base currency. Returns {code: rate} or {}.

        Uses Yahoo's free chart API (Finnhub's forex endpoints aren't on
        this plan). Rate = units of `code` per 1 `base`.
        """
        cache_key = f"fx:{base}"
        cached = cache.get_cached(cache_key)
        if cached is not None:
            return cached

        pairs = {"EUR": "EURUSD=X", "GBP": "GBPUSD=X", "JPY": "USDJPY=X"}
        out = {}
        for code, ysym in pairs.items():
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}"
            try:
                async with self.session.get(
                    url,
                    params={"interval": "1d", "range": "2d"},
                    headers={"User-Agent": "Mozilla/5.0",
                             "Accept-Encoding": "gzip, deflate"},
                    timeout=15,
                ) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                result = (data.get("chart", {}).get("result") or [None])[0]
                if not result:
                    continue
                quote = (result.get("indicators", {}).get("quote") or [{}])[0]
                closes = [c for c in (quote.get("close") or [])
                          if isinstance(c, (int, float))]
                if len(closes) >= 2:
                    out[code] = {"rate": closes[-1], "prev": closes[-2]}
            except Exception:
                continue

        cache.set_cached(cache_key, out, 600)
        return out
