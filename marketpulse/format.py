"""Tiny presentation helpers.

Kept separate from the dashboard so formatting rules are testable
without any UI framework. The Discord bot can reuse these later too.
"""


def fmt_price(price):
    """$1,234.50 style, or an em dash when unknown."""
    if not isinstance(price, (int, float)):
        return "—"
    return f"${price:,.2f}"


CCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "CAD": "C$",
    "AUD": "A$",
}


def fx_rates_from_strip(pairs):
    """Build {currency code: units per 1 USD} from FX strip pair dicts.

    The strip carries quotes like "EUR/USD" (USD per EUR) or "USD/JPY"
    (JPY per USD); both get normalized to units-per-USD here.
    """
    rates = {"USD": 1.0}
    for p in pairs or []:
        label = p.get("label")
        price = p.get("price")
        if not isinstance(price, (int, float)) or price <= 0:
            continue
        if label in ("EUR/USD", "GBP/USD", "AUD/USD"):
            rates[label.split("/")[0]] = 1.0 / price
        elif label in ("USD/JPY", "USD/CAD"):
            rates[label.split("/")[1]] = price
    return rates


def convert_currency(price_usd, code, rates):
    """Convert a USD price into another currency.

    rates: {code: units per 1 USD} as built by fx_rates_from_strip().
    Returns None when the price or the rate is unusable.
    """
    if not isinstance(price_usd, (int, float)):
        return None
    if code == "USD":
        return price_usd
    rate = (rates or {}).get(code)
    if not isinstance(rate, (int, float)) or rate <= 0:
        return None
    return price_usd * rate


def fmt_price_ccy(price_usd, code="USD", rates=None):
    """fmt_price in the requested display currency (USD default).

    Falls back to plain USD when the currency is unknown or its FX rate
    is unavailable, so a stale rate never shows a wrong number.
    """
    if code not in CCY_SYMBOLS or code == "USD":
        return fmt_price(price_usd)
    converted = convert_currency(price_usd, code, rates)
    if converted is None:
        return fmt_price(price_usd)
    if code == "JPY":
        return f"¥{converted:,.0f}"
    return f"{CCY_SYMBOLS[code]}{converted:,.2f}"


def fmt_change(change):
    """+2.35% style, or an em dash when unknown."""
    if not isinstance(change, (int, float)):
        return "—"
    return f"{change:+.2f}%"


def move_emoji(change):
    """Quick direction glyph for a percent change."""
    if not isinstance(change, (int, float)):
        return "⚪"
    return "🟢" if change >= 0 else "🔴"


def score_band(score):
    """Plain-English label for a research score.

    Bands describe *observed* signals (movement + news), never a
    prediction of future returns.
    """
    if score >= 65:
        return "High attention"
    if score >= 45:
        return "Worth a look"
    if score >= 20:
        return "Quiet"
    return "No signal"
