"""Heuristic news-sentiment classifier. No API calls.

Lexicon-based: counts bullish vs bearish cue words in a headline and
tags it bullish / bearish / neutral. Fast enough to run on every
headline in the News room. It is a rough heuristic, not a model --
labels describe word choice, not verified market direction.
"""

BULLISH_WORDS = {
    "surge", "surges", "surging", "soar", "soars", "soaring", "rally",
    "rallies", "rallying", "jump", "jumps", "jumping", "spike", "spikes",
    "spiking", "beat", "beats", "beating", "upgrade", "upgrades",
    "upgraded", "outperform", "outperforms", "record", "highs",
    "gain", "gains", "gaining", "bullish", "raise", "raises", "raised",
    "growth", "profit", "profits", "profitable", "strong", "stronger",
    "breakthrough", "approval", "approved", "win", "wins", "rebound",
    "rebounds", "rebounding", "climb", "climbs", "climbing", "rise",
    "rises", "rising", "pop", "pops", "popping", "boom", "booming",
    "optimistic", "confidence", "upgrade", "buyback", "dividend hike",
    "blowout", "tops", "exceeds",
}

BEARISH_WORDS = {
    "plunge", "plunges", "plunging", "crash", "crashes", "crashing",
    "tumble", "tumbles", "tumbling", "fall", "falls", "falling",
    "drop", "drops", "dropping", "downgrade", "downgrades",
    "downgraded", "miss", "misses", "missing", "loss", "losses",
    "losing", "bearish", "cut", "cuts", "cutting", "layoff", "layoffs",
    "probe", "lawsuit", "warning", "warns", "weak", "weaker",
    "weakness", "decline", "declines", "declining", "slump", "slumps",
    "slumping", "sink", "sinks", "sinking", "dive", "dives", "diving",
    "selloff", "sell-off", "fraud", "bankruptcy", "recall",
    "investigation", "scandal", "short", "downgraded", "plummet",
    "plummets", "crater", "craters", "bleed", "bleeding", "fear",
    "risk", "risks", "tariff hit", "guidance cut",
}


def classify_sentiment(headline):
    """Return 'bullish', 'bearish', or 'neutral' for a headline."""
    if not headline:
        return "neutral"
    text = str(headline).lower()
    bull = sum(1 for w in BULLISH_WORDS if w in text)
    bear = sum(1 for w in BEARISH_WORDS if w in text)
    if bull > bear:
        return "bullish"
    if bear > bull:
        return "bearish"
    return "neutral"


def sentiment_pill(label):
    """Small colored pill HTML for a sentiment label (inline styles, theme-proof)."""
    styles = {
        "bullish": ("#39ff88", "rgba(57,255,136,0.10)",
                    "rgba(57,255,136,0.45)", "▲ BULLISH"),
        "bearish": ("#ff3b5c", "rgba(255,59,92,0.10)",
                    "rgba(255,59,92,0.45)", "▼ BEARISH"),
        "neutral": ("#8b93a7", "rgba(139,147,167,0.10)",
                    "rgba(139,147,167,0.40)", "● NEUTRAL"),
    }
    color, bg, border, text = styles.get(label, styles["neutral"])
    return (
        f'<span style="display:inline-block;font-family:monospace;'
        f'font-size:9px;font-weight:700;letter-spacing:1px;'
        f'color:{color};background:{bg};border:1px solid {border};'
        f'border-radius:3px;padding:2px 6px;margin-left:6px;'
        f'vertical-align:2px;white-space:nowrap;">{text}</span>'
    )
