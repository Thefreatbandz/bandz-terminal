"""All configuration lives here. Secrets come from environment variables.

Why a separate file? Every part of the project (bot, web, tests) needs the
same settings. One source of truth means you change a value once.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# --- Secrets: never hardcode these, never commit a .env file ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")      # only needed for bot mode
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")  # required: market data
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")    # optional: AI degrades gracefully
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# --- Scan universes ---
CORE_STOCKS = [
    "NVDA", "AMD", "TSLA", "AAPL", "MSFT",
    "AMZN", "GOOGL", "META", "AVGO", "PLTR",
    "SMCI", "COIN", "MRNA", "LLY", "BA",
    "NFLX", "MSTR", "CRWD", "RIVN", "NIO",
    "INTC", "MU", "ARM", "SOFI", "HOOD",
]

# The "Robinhood board": everything in one watchlist, grouped by sector.
# Scan cost matters here: the engine fetches quotes for all of these but
# only pulls news for the biggest movers (see scan_universe).
SECTORS = {
    "ETFs": ["SPY", "QQQ", "DIA", "IWM", "VTI", "ARKK", "SMH", "XLF",
             "XLE", "XLK", "XLV", "XBI", "VOO", "SCHD"],
    "Mega-Cap Tech": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META",
                      "TSLA", "AVGO", "AMD", "ORCL", "CRM", "ADBE",
                      "IBM", "NOW", "INTU"],
    "Chips": ["INTC", "MU", "ARM", "QCOM", "MRVL", "AMAT", "LRCX",
              "MPWR", "SNDK", "NXPI", "ON", "TSM", "KLAC", "GFS",
              "ADI", "TXN"],
    "AI & Cloud": ["PLTR", "SMCI", "CRWD", "SNOW", "NET", "SHOP",
                   "MDB", "DDOG", "ZS", "OKTA", "AI", "SOUN", "TEM",
                   "ANET", "PANW", "GTLB"],
    "Crypto-Linked": ["COIN", "MSTR", "HOOD", "MARA", "RIOT", "SQ",
                      "PYPL", "IREN", "CLSK", "GLXY"],
    "Healthcare": ["LLY", "UNH", "JNJ", "MRNA", "AMGN", "ISRG",
                   "PFE", "ABBV", "TMO", "DHR", "GILD", "REGN",
                   "VRTX", "ZTS", "BIIB", "BMY", "HCA", "MDT"],
    "Banks & Finance": ["JPM", "BAC", "GS", "AXP", "V", "MA",
                        "BRK.B", "SCHW", "C", "WFC", "MS", "COF",
                        "PNC", "USB", "IBKR", "CME", "BLK", "SPGI"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "OXY", "MPC",
               "DVN", "PSX", "EQT", "KMI"],
    "Consumer": ["WMT", "HD", "MCD", "NFLX", "DIS", "NKE", "TGT",
                 "LOW", "SBUX", "BKNG", "ABNB", "COST", "LULU",
                 "EBAY", "CMG", "YUM"],
    "EV & Meme": ["RIVN", "NIO", "GME", "AMC", "SOFI", "LCID",
                  "XPEV", "LI", "RKLB", "ASTS", "JOBY", "ACHR"],
    "Industrials": ["BA", "CAT", "GE", "HON", "LMT", "UNP", "UPS",
                    "RTX", "DE", "ETN"],
    "Telecom & Media": ["T", "VZ", "CMCSA", "WBD", "EA", "TTWO", "CHTR"],
    "Airlines & Travel": ["DAL", "UAL", "AAL", "LUV", "JBLU", "MAR",
                          "HLT", "CCL", "RCL", "EXPE", "ALK"],
}

EVERYTHING_STOCKS = [s for tickers in SECTORS.values() for s in tickers]


def sector_of(symbol):
    """Which sector a symbol belongs to, or 'Other'."""
    for sector, tickers in SECTORS.items():
        if symbol in tickers:
            return sector
    return "Other"

CRYPTO_ASSETS = ["BTC", "ETH", "SOL", "XRP"]

# --- PennyPulse filters ---
PENNY_MAX_PRICE = 1.00
PENNY_MIN_MOVE = 5.0  # percent

# --- Ranking ---
TOP_N = 6
AI_MIN_SCORE = 45  # only explain results scoring at least this

# --- Caching (seconds) ---
QUOTE_CACHE_SECONDS = 120
NEWS_CACHE_SECONDS = 900

# --- Networking ---
REQUEST_TIMEOUT = 15
SCAN_DELAY = 0.25  # pause between symbols so we don't hammer the API


def missing_keys():
    """Names of required env vars that are not set (engine needs these)."""
    missing = []
    if not FINNHUB_API_KEY:
        missing.append("FINNHUB_API_KEY")
    return missing
