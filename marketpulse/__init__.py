"""MarketPulse AI engine: market data, scoring, AI explanations.

This package has NO Discord code and NO web code in it.
Both the Discord bot and the future browser dashboard import from here.
That separation is what makes the browser move possible.
"""

from .engine import scan_stock, scan_universe

__all__ = ["scan_stock", "scan_universe"]
