"""AI explanations via Gemini. Evidence-grounded, never invented.

The prompt forces the model to distinguish verified information from
interpretation, admit uncertainty, and never guarantee profits.
If the API key is missing or the call fails, we return a plain message --
the rest of the pipeline keeps working.
"""

import asyncio
import logging

import aiohttp

from . import config

logger = logging.getLogger("MarketPulse")

#: Prefix of every degraded-mode response below. web.py uses it to avoid
#: caching fallbacks on disk as if they were real AI answers.
DEGRADED_PREFIX = "Gemini isn't responding"


def _ai_failed(text):
    """True when _gemini_text returned one of its graceful fallbacks."""
    return isinstance(text, str) and text.startswith("AI ")


def _headline_fallback(symbol, news):
    """Degraded-mode explanation: the headlines themselves, honestly labeled.

    Used when the Gemini API is unreachable (bad key, outage). Never blank,
    never invented.
    """
    heads = [n.get("headline", "") for n in (news or [])[:3]]
    heads = [h for h in heads if h]
    if not heads:
        return (f"{DEGRADED_PREFIX} right now, and no headlines came "
                "through — check the News tab or try again in a bit.")
    lines = "\n".join(f"- {h}" for h in heads)
    return (f"{DEGRADED_PREFIX} right now — here's what the latest "
            f"headlines for {symbol} say:\n{lines}")


async def _gemini_text(session, prompt):
    """POST a prompt to Gemini, return the text or a fallback message."""
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{config.GEMINI_MODEL}:generateContent"
    )
    try:
        async with session.post(
            url,
            params={"key": config.GEMINI_API_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if response.status != 200:
                logger.warning("Gemini API error: %s", response.status)
                return "AI analysis failed."

            data = await response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return "AI returned no analysis."

            parts = candidates[0].get("content", {}).get("parts", [])
            text = "\n".join(part.get("text", "") for part in parts).strip()
            return text or "AI returned no text."

    except Exception:
        logger.exception("AI analysis error")
        return "AI analysis unavailable."


async def gemini_probe(session):
    """Minimal live probe. Returns (ok, detail) -- never raises.

    ok=True means the key, model, and network path all work. On failure
    detail carries the real reason (HTTP status + API error message, or
    timeout/network) so the UI can tell the user exactly what to fix
    instead of a bare "error". The key itself is never in detail.
    """
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{config.GEMINI_MODEL}:generateContent"
    )
    try:
        async with session.post(
            url,
            params={"key": config.GEMINI_API_KEY},
            json={"contents": [{"parts": [{"text": "Reply with exactly: OK"}]}]},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as response:
            if response.status != 200:
                detail = f"HTTP {response.status}"
                try:
                    data = await response.json()
                    msg = (data.get("error") or {}).get("message", "")
                    if msg:
                        detail += f": {msg[:160]}"
                except Exception:
                    pass
                return False, detail
            try:
                data = await response.json()
            except Exception:
                return False, "bad response body"
            parts = ((data.get("candidates") or [{}])[0]
                     .get("content", {}).get("parts", []))
            text = "\n".join(p.get("text", "") for p in parts).strip()
            if text:
                return True, "live"
            return False, "empty response"
    except asyncio.TimeoutError:
        return False, "timeout"
    except aiohttp.ClientError:
        return False, "network unreachable"
    except Exception:
        logger.exception("Gemini probe error")
        return False, "request failed"


def classify_gemini_status(ok, detail):
    """Probe result -> short status for the sidebar.

    live | key-rejected | model-not-found | network | error
    """
    if ok:
        return "live"
    d = (detail or "").lower()
    if "api key not valid" in d or "api_key_invalid" in d:
        return "key-rejected"
    if "not found" in d or "is not supported" in d:
        return "model-not-found"
    if "timeout" in d or "network" in d or "connect" in d:
        return "network"
    return "error"


async def generate_ai_analysis(session, symbol, quote, news):
    """Return a structured research explanation, or a fallback message."""
    if not config.GEMINI_API_KEY:
        return "AI analysis unavailable. Configure GEMINI_API_KEY."

    news_text = "\n".join(f"- {item['headline']}" for item in news[:5])
    if not news_text:
        news_text = "No relevant news was retrieved."

    price = quote.get("price", "Unknown")
    change = quote.get("change_percent", "Unknown")

    prompt = f"""
You are the research assistant for MarketPulse AI.

Analyze the following market information.

Symbol: {symbol}
Price: {price}
Percentage change: {change}%

Retrieved news:
{news_text}

Requirements:
1. Explain what the available information shows.
2. Identify any relevant reported catalyst.
3. Clearly distinguish verified information from interpretation.
4. If no catalyst is confirmed, say that.
5. Mention important uncertainty.
6. Do not guarantee profits or predict a guaranteed outcome.
7. Do not invent news or data.

Use these headings:

WHAT HAPPENED
POTENTIAL CATALYST
WHY IT MAY MATTER
WHAT TO WATCH
UNCERTAINTY

Keep the answer concise and readable.
"""
    text = await _gemini_text(session, prompt)
    if _ai_failed(text):
        return _headline_fallback(symbol, news)
    return text


async def generate_mover_explanation(session, symbol, quote, news):
    """1-2 sentence explanation of why a symbol moved today.

    Grounded only in the provided quote + headlines. Returns a short
    string, or a graceful fallback when the AI is unavailable.
    """
    if not config.GEMINI_API_KEY:
        return "AI explanation unavailable. Configure GEMINI_API_KEY."
    price = quote.get("price", "?")
    change = quote.get("change_percent", 0)
    news_text = "\n".join(f"- {item['headline']}" for item in news[:5])
    if not news_text:
        news_text = "No fresh headlines were retrieved."
    prompt = f"""
You are the research assistant for Bandz Terminal, a stock-watching app.

Symbol: {symbol}
Price: ${price}
Day change: {change:+.2f}%

Recent headlines:
{news_text}

In 1-2 sentences, explain what likely drove today's move, citing the
reported headlines. If no clear catalyst appears, say so plainly.
Do not invent news or prices. Do not predict what happens next.
This is research, not financial advice.
"""
    text = await _gemini_text(session, prompt)
    if _ai_failed(text):
        return _headline_fallback(symbol, news)
    return text


async def generate_watchlist_digest(session, items):
    """On-demand digest: what moved in the user's watchlist today and why.

    items: list of dicts with symbol, price, change_pct, headlines[].
    One Gemini call, grounded ONLY in the provided prices + headlines.
    Degraded path is labeled with DEGRADED_PREFIX, never blank.
    """
    if not config.GEMINI_API_KEY:
        return "AI digest unavailable. Configure GEMINI_API_KEY."

    def _chg(it):
        c = it.get("change_pct")
        return f"{c:+.2f}%" if isinstance(c, (int, float)) else "n/a"

    lines = []
    for it in items[:15]:
        heads = [h for h in (it.get("headlines") or []) if h]
        head = heads[0] if heads else "no fresh headline"
        lines.append(f"{it.get('symbol')}: {_chg(it)} @ {it.get('price')} "
                     f"— {head}")
    board = "\n".join(lines) if lines else "Watchlist is empty."

    prompt = f"""
You are the research assistant for Bandz Terminal, a stock-watching app.
The user asked: what moved in my watchlist today, and why?

Today's watchlist:
{board}

Write a short digest based ONLY on the data above. Do not invent news,
prices, or catalysts. For each symbol that moved notably, give the size
of the move and the reported headline behind it if there is one; if no
clear catalyst appears, say so plainly. End with one line on what to
watch next. Keep it tight and readable on a phone. This is research,
not financial advice.
"""
    text = await _gemini_text(session, prompt)
    if _ai_failed(text):
        rows = [f"- {it.get('symbol')}: {_chg(it)}" for it in items[:15]]
        if not rows:
            return (f"{DEGRADED_PREFIX} right now — your watchlist is "
                    "empty or has no data.")
        return (f"{DEGRADED_PREFIX} right now — your watchlist today:\n"
                + "\n".join(rows))
    return text


async def generate_market_brief(session, items):
    """One-shot briefing over the day's movers.

    items: list of dicts with symbol, price, change_percent, headline.
    One Gemini call, grounded only in the provided data.
    """
    if not config.GEMINI_API_KEY:
        return "AI briefing unavailable. Configure GEMINI_API_KEY."

    lines = []
    for item in items[:12]:
        head = item.get("headline") or "no fresh headline"
        lines.append(
            f"{item['symbol']}: {item['change_percent']:+.2f}% "
            f"@ {item['price']} — {head}"
        )
    movers = "\n".join(lines) if lines else "No movers scanned."

    prompt = f"""
You are the research assistant for MarketPulse AI. Write a short market
briefing based ONLY on the data below. Do not invent news, prices, or
catalysts. Distinguish what the data shows from interpretation. Do not
predict outcomes or guarantee profits.

Today's movers:
{movers}

Format: at most 5 bullets. Each bullet: what moved, the size of the move,
and the reported headline if there is one. End with one line on what to
watch next. Keep it tight and readable on a phone.
"""
    text = await _gemini_text(session, prompt)
    if _ai_failed(text):
        # Degraded: plain mover list, no invented commentary.
        rows = [f"- {i['symbol']}: {i['change_percent']:+.2f}%"
                for i in items[:12]]
        if not rows:
            return f"{DEGRADED_PREFIX} right now — no movers scanned."
        return (f"{DEGRADED_PREFIX} right now — today's biggest movers:\n"
                + "\n".join(rows))
    return text
