"""AI explanations via Gemini. Evidence-grounded, never invented.

The prompt forces the model to distinguish verified information from
interpretation, admit uncertainty, and never guarantee profits.
If the API key is missing or the call fails, we return a plain message --
the rest of the pipeline keeps working.
"""

import logging

import aiohttp

from . import config

logger = logging.getLogger("MarketPulse")


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
    return await _gemini_text(session, prompt)


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
    if text.startswith("AI "):  # _gemini_text fallback messages
        return ("Couldn't pull an explanation right now — "
                "check the headlines below instead.")
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
    return await _gemini_text(session, prompt)
