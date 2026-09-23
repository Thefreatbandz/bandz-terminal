"""Tiny presentation helpers.

Kept separate from the dashboard so formatting rules are testable
without any UI framework. The Discord bot can reuse these later too.
"""


def fmt_price(price):
    """$1,234.50 style, or an em dash when unknown."""
    if not isinstance(price, (int, float)):
        return "—"
    return f"${price:,.2f}"


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
