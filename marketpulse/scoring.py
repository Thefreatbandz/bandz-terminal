"""Transparent scoring and filtering.

Every rule is spelled out here in plain code so a user can read exactly
why an asset ranked where it did. Scores describe *observed* signals
(movement + news presence) -- never a prediction of future returns.
"""

from .config import PENNY_MAX_PRICE, PENNY_MIN_MOVE


def calculate_score(quote, news):
    """Score 0-100 from a quote dict and a news list."""
    if not quote:
        return 0

    change = abs(quote.get("change_percent", 0))
    score = 0

    # Movement signal
    if change >= 5:
        score += 30
    elif change >= 3:
        score += 20
    elif change >= 1:
        score += 10

    # News availability
    if news:
        score += 25

    # Data quality
    if quote.get("price") is not None:
        score += 10

    return min(score, 100)


def penny_qualifies(price, change_percent,
                    max_price=PENNY_MAX_PRICE, min_move=PENNY_MIN_MOVE):
    """True when a stock passes the PennyPulse filters.

    Filters describe the *current* price and movement only. They say
    nothing about liquidity, legitimacy, or future performance.
    """
    if price is None or change_percent is None:
        return False
    return price <= max_price and abs(change_percent) >= min_move
