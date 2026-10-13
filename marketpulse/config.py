"""All configuration lives here. Secrets come from environment variables.

Why a separate file? Every part of the project (bot, web, tests) needs the
same settings. One source of truth means you change a value once.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# --- Secrets: never hardcode these, never commit a .env file ---
DISCORD_TOKEN = (os.getenv("DISCORD_TOKEN") or "").strip() or None
FINNHUB_API_KEY = (os.getenv("FINNHUB_API_KEY") or "").strip() or None
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip() or None
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# --- Scan universes ---
CORE_STOCKS = [
    "NVDA", "AMD", "TSLA", "AAPL", "MSFT",
    "AMZN", "GOOGL", "META", "AVGO", "PLTR",
    "SMCI", "COIN", "MRNA", "LLY", "BA",
    "NFLX", "MSTR", "CRWD", "RIVN", "NIO",
    "INTC", "MU", "ARM", "SOFI", "HOOD",
    "TTWO",
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
    "Telecom & Media": ["T", "VZ", "CMCSA", "WBD", "CHTR"],
    "Gaming": ["TTWO", "EA", "RBLX", "SONY", "NTES"],
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


# Company names for instant ticker search (suggest-as-you-type).
# Generated 2026-10-13 from Finnhub profile2 (162 names); ETF/crypto
# names filled manually. Static so search is instant and offline.
COMPANY_NAMES = {
    "AAL": "American Airlines Group Inc",
    "AAPL": "Apple Inc",
    "ABBV": "AbbVie Inc",
    "ABNB": "Airbnb Inc",
    "ACHR": "Archer Aviation Inc",
    "ADBE": "Adobe Inc",
    "ADI": "Analog Devices Inc",
    "AI": "C3.ai Inc",
    "ALK": "Alaska Air Group Inc",
    "AMAT": "Applied Materials Inc",
    "AMC": "AMC Entertainment Holdings Inc",
    "AMD": "Advanced Micro Devices Inc",
    "AMGN": "Amgen Inc",
    "AMZN": "Amazon.com Inc",
    "ANET": "Arista Networks Inc",
    "ARKK": "ARK Innovation ETF",
    "ARM": "Arm Holdings PLC",
    "ASTS": "AST SpaceMobile Inc",
    "AVGO": "Broadcom Inc",
    "AXP": "American Express Co",
    "BA": "Boeing Co",
    "BAC": "Bank of America Corp",
    "BIIB": "Biogen Inc",
    "BKNG": "Booking Holdings Inc",
    "BLK": "BlackRock Inc",
    "BMY": "Bristol-Myers Squibb Co",
    "BRK.B": "Berkshire Hathaway Inc",
    "BTC": "Bitcoin",
    "C": "Citigroup Inc",
    "CAT": "Caterpillar Inc",
    "CCL": "Carnival Corp",
    "CHTR": "Charter Communications Inc",
    "CLSK": "CleanSpark Inc",
    "CMCSA": "Comcast Corp",
    "CME": "CME Group Inc",
    "CMG": "Chipotle Mexican Grill Inc",
    "COF": "Capital One Financial Corp",
    "COIN": "Coinbase Global Inc",
    "COP": "ConocoPhillips",
    "COST": "Costco Wholesale Corp",
    "CRM": "Salesforce Inc",
    "CRWD": "CrowdStrike Holdings Inc",
    "CVX": "Chevron Corp",
    "DAL": "Delta Air Lines Inc",
    "DDOG": "Datadog Inc",
    "DE": "Deere & Co",
    "DHR": "Danaher Corp",
    "DIA": "SPDR Dow Jones Industrial Average ETF",
    "DIS": "Walt Disney Co",
    "DVN": "Devon Energy Corp",
    "EA": "Electronic Arts Inc",
    "EBAY": "eBay Inc",
    "EOG": "EOG Resources Inc",
    "EQT": "EQT Corp",
    "ETH": "Ethereum",
    "ETN": "Eaton Corporation PLC",
    "EXPE": "Expedia Group Inc",
    "GE": "General Electric Co",
    "GFS": "GlobalFoundries Inc",
    "GILD": "Gilead Sciences, Inc",
    "GLXY": "Galaxy Digital Inc",
    "GME": "GameStop Corp",
    "GOOGL": "Alphabet Inc",
    "GS": "Goldman Sachs Group Inc",
    "GTLB": "GitLab Inc",
    "HCA": "HCA Healthcare Inc",
    "HD": "Home Depot Inc",
    "HLT": "Hilton Worldwide Holdings Inc",
    "HON": "Honeywell International Inc",
    "HOOD": "Robinhood Markets Inc",
    "IBKR": "Interactive Brokers Group Inc",
    "IBM": "International Business Machines Corp",
    "INTC": "Intel Corp",
    "INTU": "Intuit Inc",
    "IREN": "IREN Ltd",
    "ISRG": "Intuitive Surgical Inc",
    "IWM": "iShares Russell 2000 ETF",
    "JBLU": "JetBlue Airways Corp",
    "JNJ": "Johnson & Johnson",
    "JOBY": "Joby Aviation Inc",
    "JPM": "JPMorgan Chase & Co",
    "KLAC": "KLA Corp",
    "KMI": "Kinder Morgan Inc",
    "LCID": "Lucid Group Inc",
    "LI": "Li Auto Inc",
    "LLY": "Eli Lilly and Co",
    "LMT": "Lockheed Martin Corp",
    "LOW": "Lowe's Companies Inc",
    "LRCX": "Lam Research Corp",
    "LULU": "Lululemon Athletica Inc",
    "LUV": "Southwest Airlines Co",
    "MA": "Mastercard Inc",
    "MAR": "Marriott International Inc",
    "MARA": "MARA Holdings Inc",
    "MCD": "McDonald's Corp",
    "MDB": "MongoDB Inc",
    "MDT": "Medtronic PLC",
    "META": "Meta Platforms Inc",
    "MPC": "Marathon Petroleum Corp",
    "MPWR": "Monolithic Power Systems Inc",
    "MRNA": "Moderna Inc",
    "MRVL": "Marvell Technology Inc",
    "MS": "Morgan Stanley",
    "MSFT": "Microsoft Corp",
    "MSTR": "Strategy Inc",
    "MU": "Micron Technology Inc",
    "NET": "Cloudflare Inc",
    "NFLX": "Netflix Inc",
    "NIO": "NIO Inc",
    "NKE": "Nike Inc",
    "NOW": "ServiceNow Inc",
    "NTES": "NetEase Inc",
    "NVDA": "NVIDIA Corp",
    "NXPI": "NXP Semiconductors NV",
    "OKTA": "Okta Inc",
    "ON": "ON Semiconductor Corp",
    "ORCL": "Oracle Corp",
    "OXY": "Occidental Petroleum Corp",
    "PANW": "Palo Alto Networks Inc",
    "PFE": "Pfizer Inc",
    "PLTR": "Palantir Technologies Inc",
    "PNC": "PNC Financial Services Group Inc",
    "PSX": "Phillips 66",
    "PYPL": "PayPal Holdings Inc",
    "QCOM": "Qualcomm Inc",
    "QQQ": "Invesco QQQ Trust",
    "RBLX": "Roblox Corp",
    "RCL": "Royal Caribbean Cruises Ltd",
    "REGN": "Regeneron Pharmaceuticals Inc",
    "RIOT": "Riot Platforms Inc",
    "RIVN": "Rivian Automotive Inc",
    "RKLB": "Rocket Lab Corp",
    "RTX": "RTX Corp",
    "SBUX": "Starbucks Corp",
    "SCHD": "Schwab U.S. Dividend Equity ETF",
    "SCHW": "Charles Schwab Corp",
    "SHOP": "Shopify Inc",
    "SLB": "SLB NV",
    "SMCI": "Super Micro Computer Inc",
    "SMH": "VanEck Semiconductor ETF",
    "SNDK": "Sandisk Corp",
    "SNOW": "Snowflake Inc",
    "SOFI": "SoFi Technologies Inc",
    "SOL": "Solana",
    "SONY": "Sony Group Corp",
    "SOUN": "SoundHound AI Inc",
    "SPGI": "S&P Global Inc",
    "SPY": "SPDR S&P 500 ETF Trust",
    "SQ": "Block Inc",
    "T": "AT&T Inc",
    "TEM": "Tempus AI Inc",
    "TGT": "Target Corp",
    "TMO": "Thermo Fisher Scientific Inc",
    "TSLA": "Tesla Inc",
    "TSM": "Taiwan Semiconductor Manufacturing Co Ltd",
    "TTWO": "Take-Two Interactive Software Inc",
    "TXN": "Texas Instruments Inc",
    "UAL": "United Airlines Holdings Inc",
    "UNH": "UnitedHealth Group Inc",
    "UNP": "Union Pacific Corp",
    "UPS": "United Parcel Service Inc",
    "USB": "US Bancorp",
    "V": "Visa Inc",
    "VOO": "Vanguard S&P 500 ETF",
    "VRTX": "Vertex Pharmaceuticals Inc",
    "VTI": "Vanguard Total Stock Market ETF",
    "VZ": "Verizon Communications Inc",
    "WBD": "Warner Bros Discovery Inc",
    "WFC": "Wells Fargo & Co",
    "WMT": "Walmart Inc",
    "XBI": "SPDR S&P Biotech ETF",
    "XLE": "Energy Select Sector SPDR Fund",
    "XLF": "Financial Select Sector SPDR Fund",
    "XLK": "Technology Select Sector SPDR Fund",
    "XLV": "Health Care Select Sector SPDR Fund",
    "XOM": "Exxonmobil Holdings Corp",
    "XPEV": "Xpeng Inc",
    "XRP": "Ripple",
    "YUM": "Yum! Brands Inc",
    "ZS": "Zscaler Inc",
    "ZTS": "Zoetis Inc",
}
