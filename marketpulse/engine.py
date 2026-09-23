"""The research pipeline: scan assets, rank them, optionally explain.

This is the heart of MarketPulse. The Discord bot calls these functions,
and the future browser dashboard will call the *same* functions.
UI code lives elsewhere; it only formats what these return.
"""

import asyncio

from . import config
from .ai import generate_ai_analysis
from .scoring import calculate_score


async def scan_stock(client, symbol, include_ai=True, include_news=True):
    """Research one symbol.

    Returns a plain dict (symbol, sector, quote, news, score, analysis)
    or None when no valid market data exists. Never raises for bad data.

    include_news=False skips the news call (cheaper). The universe scan
    uses this for its first pass, then fetches news for movers only.
    """
    quote = await client.quote(symbol)
    if not quote:
        return None

    news = await client.company_news(symbol) if include_news else []
    score = calculate_score(quote, news)

    analysis = None
    # AI_MIN_SCORE gates the expensive AI call: only explain results
    # worth a human's attention. (V1 defined this setting but never used it.)
    if include_ai and score >= config.AI_MIN_SCORE:
        analysis = await generate_ai_analysis(
            client.session, symbol, quote, news
        )

    return {
        "symbol": symbol,
        "sector": config.sector_of(symbol),
        "quote": quote,
        "news": news,
        "score": score,
        "analysis": analysis,
    }


async def scan_universe(client, symbols, include_ai=False, news_top_n=None,
                      delay=None):
    """Scan many symbols, return them ranked by score, highest first.

    This is the logic that used to live inside the Discord !top command.
    Moving it here means the web dashboard can run the exact same scan.

    news_top_n: when set, do a cheap two-pass scan -- quotes for every
    symbol first, then news only for the top N movers. Use this for big
    lists (like the Everything board) to respect API rate limits.
    When None, every symbol gets quotes + news (original behavior).

    delay: seconds between API calls. Defaults to config.SCAN_DELAY.
    Pass a larger value for very large universes (105+ symbols) to stay
    under the 60 calls/minute free-tier limit.
    """
    pause = config.SCAN_DELAY if delay is None else delay
    if news_top_n is None:
        results = []
        for symbol in symbols:
            result = await scan_stock(client, symbol, include_ai=include_ai)
            if result is not None:
                results.append(result)
            await asyncio.sleep(pause)
        results.sort(key=lambda item: item["score"], reverse=True)
        return results

    # --- two-pass scan for big universes ---
    # Pass 1: quotes for everyone (cheap), no AI yet.
    results = []
    for symbol in symbols:
        result = await scan_stock(client, symbol, include_ai=False,
                                  include_news=False)
        if result is not None:
            results.append(result)
        await asyncio.sleep(pause)
    results.sort(key=lambda item: item["score"], reverse=True)

    # Pass 2: news (+ optional AI) for the biggest movers only.
    for result in results[:news_top_n]:
        full = await scan_stock(client, result["symbol"],
                                include_ai=include_ai, include_news=True)
        if full is not None:
            result.update(full)
        await asyncio.sleep(pause)
    results.sort(key=lambda item: item["score"], reverse=True)
    return results


def sector_summary(results):
    """Average % change per sector -> [(sector, avg_change, count)].

    Best-performing sector first. Feeds the "Sectors today" board.
    """
    from collections import defaultdict
    moves = defaultdict(list)
    for r in results:
        moves[r.get("sector", "Other")].append(r["quote"]["change_percent"])
    summary = [(s, sum(v) / len(v), len(v)) for s, v in moves.items()]
    summary.sort(key=lambda item: item[1], reverse=True)
    return summary
