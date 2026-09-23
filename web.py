#!/usr/bin/env python3
"""MarketPulse AI -- browser dashboard.

Run:  streamlit run web.py
Then open the URL it prints. On your phone, use your laptop's
local address, e.g. http://192.168.1.5:8501 (same Wi-Fi).
Or deploy free to share.streamlit.io and open it anywhere.

Every number on this page comes from the same engine the Discord
bot used: scan -> score -> news -> (on-demand) AI explanation.
"""

import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import aiohttp
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from marketpulse import alerts as alert_store
from marketpulse import cache, config
from marketpulse.ai import generate_ai_analysis, generate_market_brief
from marketpulse.data import FinnhubClient
from marketpulse.engine import scan_stock, scan_universe, sector_summary
from marketpulse.format import fmt_change, fmt_price, move_emoji, score_band
from marketpulse.scoring import penny_qualifies

st.set_page_config(page_title="Bandz Terminal", page_icon="⚡", layout="wide")

# Finnhub crypto tickers for the CryptoPulse tab.
CRYPTO_MAP = {
    "BTC": "BINANCE:BTCUSDT",
    "ETH": "BINANCE:ETHUSDT",
    "SOL": "BINANCE:SOLUSDT",
    "XRP": "BINANCE:XRPUSDT",
}

ETF_STRIP = ["SPY", "QQQ", "DIA", "IWM"]


def _run(coro):
    return asyncio.run(coro)


# ---------------- custom styling ----------------

st.markdown("""
<style>
/* tighter top padding, terminal feel */
.block-container { padding-top: 1.2rem; }
/* ticker tape */
.tape-wrap { overflow: hidden; white-space: nowrap;
             border-top: 1px solid #1d2635; border-bottom: 1px solid #1d2635;
             padding: 6px 0; margin-bottom: 12px; }
.tape-inner { display: inline-block; animation: tape-scroll 40s linear infinite; }
@keyframes tape-scroll { from { transform: translateX(0); }
                         to { transform: translateX(-50%); } }
.tape-item { font-family: monospace; font-size: 13px; margin-right: 26px; }
.up { color: #00e07f; } .down { color: #ff4d5e; } .flat { color: #8b93a7; }
/* heatmap */
.heat { display: grid; grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
        gap: 6px; margin: 8px 0 16px 0; }
.tile { border-radius: 8px; padding: 10px 4px; text-align: center;
        font-family: monospace; }
.tile b { display: block; font-size: 14px; color: #f2f4f8; }
.tile span { font-size: 12px; }
.heat-label { font-family: monospace; font-size: 12px; color: #8b93a7;
              margin: 12px 0 2px 0; letter-spacing: 2px; text-transform: uppercase; }
.status-dot { font-size: 13px; font-family: monospace; }
</style>
""", unsafe_allow_html=True)


def heat_color(pct):
    """Red -> dark -> green tile background for a % change."""
    t = max(-1.0, min(1.0, pct / 5.0))
    base = (17, 23, 34)
    if t >= 0:
        target = (0, 150, 80)
    else:
        target = (190, 40, 55)
        t = -t
    r = int(base[0] + (target[0] - base[0]) * t)
    g = int(base[1] + (target[1] - base[1]) * t)
    b = int(base[2] + (target[2] - base[2]) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def market_status():
    """🟢/🔴 badge based on NYSE hours (9:30-16:00 ET, weekdays)."""
    et = datetime.now(ZoneInfo("America/New_York"))
    mins = et.hour * 60 + et.minute
    is_open = et.weekday() < 5 and 570 <= mins < 960
    return "🟢 MARKET OPEN" if is_open else "🔴 MARKET CLOSED"


def session_label():
    """Pre-market / after-hours framing for the stock tab."""
    et = datetime.now(ZoneInfo("America/New_York"))
    mins = et.hour * 60 + et.minute
    if et.weekday() >= 5:
        return "Weekend — showing last close 🌙"
    if mins < 570:
        return "Pre-market movers 🌅"
    if mins >= 960:
        return "After-hours movers 🌙"
    return None


def sector_board(summary):
    """Sectors today: average % move per sector, best at top."""
    rows = []
    for sector, avg, count in summary:
        width = min(abs(avg) / 3 * 100, 100)  # 3% move = full bar
        color = "#00e07f" if avg > 0 else "#ff4d5e" if avg < 0 else "#8b93a7"
        cls = "up" if avg > 0 else "down" if avg < 0 else "flat"
        rows.append(
            f'<div style="display:flex;align-items:center;gap:8px;'
            f'margin:4px 0;">'
            f'<div style="width:130px;font-size:12px;color:#8b93a7;'
            f'white-space:nowrap;overflow:hidden;">{sector}</div>'
            f'<div style="flex:1;background:#1a2230;border-radius:4px;'
            f'height:14px;">'
            f'<div style="height:14px;border-radius:4px;width:{width:.0f}%;'
            f'background:{color};opacity:0.85;"></div></div>'
            f'<div class="{cls}" style="width:70px;text-align:right;'
            f'font-family:monospace;font-size:12px;">{avg:+.2f}%</div>'
            f'</div>'
        )
    st.markdown("".join(rows), unsafe_allow_html=True)


def fmt_earnings(date_str):
    """YYYY-MM-DD -> 'Oct 28'."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %d")
    except (TypeError, ValueError):
        return date_str


def ticker_tape(results):
    """Scrolling marquee of every scanned symbol. Very stock-app."""
    items = []
    for r in results:
        chg = r["quote"]["change_percent"]
        cls = "up" if chg > 0 else "down" if chg < 0 else "flat"
        items.append(
            f'<span class="tape-item"><b>{r["symbol"]}</b> '
            f'<span class="{cls}">{chg:+.2f}%</span></span>'
        )
    half = "".join(items)
    st.markdown(f'<div class="tape-wrap"><div class="tape-inner">'
                f'{half}{half}</div></div>', unsafe_allow_html=True)


def heatmap(results):
    """Sector-grouped heatmap: every symbol a tile, colored by % change."""
    by_sector = {}
    for r in results:
        by_sector.setdefault(r.get("sector", "Other"), []).append(r)
    ordered = [s for s in list(config.SECTORS) + ["Other"] if s in by_sector]
    parts = []
    for sector in ordered:
        tiles = []
        for r in by_sector[sector]:
            chg = r["quote"]["change_percent"]
            cls = "up" if chg > 0 else "down" if chg < 0 else "flat"
            tiles.append(
                f'<div class="tile" style="background:{heat_color(chg)}">'
                f'<b>{r["symbol"]}</b>'
                f'<span class="{cls}">{chg:+.2f}%</span></div>'
            )
        parts.append(
            f'<div class="heat-label">{sector}</div>'
            f'<div class="heat">{"".join(tiles)}</div>'
        )
    st.markdown("".join(parts), unsafe_allow_html=True)


# ---------------- cached data fetching ----------------

@st.cache_data(ttl=120, show_spinner="Scanning markets...")
def cached_universe_scan(symbols, include_ai=False, news_top_n=None,
                         scan_delay=None):
    """Scan a universe of symbols. Cached 2 min (matches quote cache)."""
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            client = FinnhubClient(session)
            return await scan_universe(client, list(symbols),
                                       include_ai=include_ai,
                                       news_top_n=news_top_n,
                                       delay=scan_delay)
    return _run(_go())


@st.cache_data(ttl=120, show_spinner=False)
def cached_stock_scan(symbol):
    """Scan one symbol (PennyPulse tab)."""
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            client = FinnhubClient(session)
            return await scan_stock(client, symbol, include_ai=False)
    return _run(_go())


@st.cache_data(ttl=120, show_spinner=False)
def cached_candles(symbol):
    """Intraday closes for the sparkline on each card."""
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            client = FinnhubClient(session)
            return await client.candles(symbol)
    return _run(_go())


@st.cache_data(ttl=86400, show_spinner=False)
def cached_52w(symbol):
    """52-week high/low for the range bar on each card."""
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            client = FinnhubClient(session)
            return await client.metrics_52w(symbol)
    return _run(_go())


@st.cache_data(ttl=21600, show_spinner=False)
def cached_insider(symbol):
    """Recent insider buys/sells for a card."""
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            client = FinnhubClient(session)
            return await client.insider_transactions(symbol)
    return _run(_go())


@st.cache_data(ttl=86400, show_spinner=False)
def cached_earnings():
    """symbol -> next earnings date. One API call for the whole board."""
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            client = FinnhubClient(session)
            return await client.earnings_calendar()
    return _run(_go())


@st.cache_data(ttl=900, show_spinner="Writing market brief...")
def cached_brief(items):
    """AI briefing over the day's movers. items = tuple of 4-tuples."""
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            dicts = [dict(zip(("symbol", "price", "change_percent",
                               "headline"), t)) for t in items]
            return await generate_market_brief(session, dicts)
    return _run(_go())


def explain(symbol, quote, news):
    """On-demand AI explanation for one result."""
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            return await generate_ai_analysis(session, symbol, quote, news)
    return _run(_go())


# ---------------- UI pieces ----------------

def result_card(result, key_prefix=""):
    """One ranked asset: price, move, sparkline, score, news, on-demand AI."""
    quote = result["quote"]
    symbol = result["symbol"]
    price, change = quote["price"], quote["change_percent"]
    score = result["score"]

    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 2, 3])
        c1.markdown(f"### {move_emoji(change)} {symbol}")
        c1.caption(f"{fmt_price(price)} • {result.get('sector', 'Other')}")
        c2.metric("Change", fmt_change(change))
        c3.progress(min(score, 100) / 100,
                    text=f"Score {score}/100 • {score_band(score)}")

        closes = cached_candles(symbol)
        if len(closes) > 1:
            st.line_chart(closes)

        # 52-week range: where today's price sits in the year's range.
        hi52, lo52 = cached_52w(symbol)
        if hi52 and lo52 and hi52 > lo52:
            pos = max(0.0, min(1.0, (price - lo52) / (hi52 - lo52)))
            st.caption(f"52w ${lo52:.2f} – ${hi52:.2f}")
            st.progress(pos, text=f"At {pos:.0%} of 52-week range")

        # Earnings + insider activity: the "why it might move next".
        earnings = cached_earnings()
        edate = earnings.get(symbol)
        extra = []
        if edate:
            extra.append(f"📅 Earnings {fmt_earnings(edate)}")
        ins = cached_insider(symbol)
        if ins:
            t = ins[0]
            px = f" @ ${t['price']:.2f}" if isinstance(
                t["price"], (int, float)) else ""
            extra.append(f"🧑‍💼 {t['name'].split(',')[0]} {t['side']} "
                         f"{t['shares']:,} sh{px} ({t['date']})")
        for line in extra:
            st.caption(line)

        news = result["news"]
        if news:
            # Top headline lives on the card itself: the "what happened"
            # is visible without opening anything.
            top = news[0]
            if top["url"]:
                st.markdown(f"📰 [{top['headline']}]({top['url']})")
            else:
                st.markdown(f"📰 {top['headline']}")
            if top["source"]:
                st.caption(f"via {top['source']}")
            if len(news) > 1:
                with st.expander(f"More news ({len(news) - 1})"):
                    for item in news[1:5]:
                        head = item["headline"]
                        line = (f"- [{head}]({item['url']})"
                                if item["url"] else f"- {head}")
                        st.markdown(line)
                        if item["source"]:
                            st.caption(item["source"])
        else:
            st.caption("No fresh news retrieved.")

        btn_key = f"{key_prefix}explain-{symbol}"
        if st.button("🤖 Explain", key=btn_key):
            with st.spinner("Asking Gemini..."):
                st.session_state[f"analysis-{symbol}"] = explain(
                    symbol, quote, news)

        analysis = st.session_state.get(f"analysis-{symbol}")
        if analysis:
            st.markdown(analysis)


def index_strip():
    """SPY / QQQ / DIA / IWM across the top, like a broker app."""
    results = cached_universe_scan(tuple(ETF_STRIP))
    cols = st.columns(4)
    for col, res in zip(cols, results):
        q = res["quote"]
        col.metric(res["symbol"], fmt_price(q["price"]),
                   fmt_change(q["change_percent"]))


# ---------------- sidebar ----------------

with st.sidebar:
    st.header("Controls")
    universe = st.radio("Universe", ["Core 25", "Everything 🌐", "Custom"])
    custom = ""
    if universe == "Custom":
        custom = st.text_input("Symbols (comma separated)", "NVDA, TSLA")
    st.divider()
    auto = st.checkbox("Auto-refresh", value=False)
    minutes = 5
    if auto:
        minutes = st.slider("Refresh every (minutes)", 2, 60, 5)
    st.divider()
    st.subheader("🔔 Price alerts")
    st.caption("Checked every 30 min during market hours. "
               "A push lands on your phone when one fires.")
    a_sym = st.text_input("Symbol", key="alert-sym", placeholder="NVDA")
    a_pct = st.slider("Move %", 1.0, 20.0, 3.0, 0.5, key="alert-pct")
    if st.button("Add alert"):
        made = alert_store.add_alert(a_sym, a_pct)
        if made:
            st.success(f"Alert set: {made['symbol']} ±{made['pct']:g}%")
        else:
            st.warning("Need a symbol and a % above 0 "
                       "(or that alert already exists).")
    for a in alert_store.load_alerts():
        base = (f"${a['baseline']:.2f}" if a.get("baseline")
                else "arming…")
        c1, c2 = st.columns([4, 1])
        c1.caption(f"{a['symbol']} ±{a['pct']:g}% • from {base}")
        if c2.button("❌", key=f"del-{a['id']}"):
            alert_store.remove_alert(a["id"])
            st.rerun()
    st.divider()
    st.subheader("Connections")
    st.write("Finnhub:", "✅" if config.FINNHUB_API_KEY else "❌ missing")
    st.write("Gemini:", "✅" if config.GEMINI_API_KEY else "❌ missing (AI off)")
    st.divider()
    if st.button("Clear cache"):
        cache.clear()
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Cache entries: {cache.size()}")
    st.caption("AI runs on demand per result, keeping scans fast.")

if auto:
    st_autorefresh(interval=minutes * 60 * 1000, key="mp-refresh")

# ---------------- main ----------------

st.title("⚡ Bandz Terminal")
st.markdown(f'<span class="status-dot">{market_status()}</span>',
            unsafe_allow_html=True)
st.caption("Research only — verify independently. "
           "Scores describe observed signals, not future returns.")

missing = config.missing_keys()
if missing:
    st.error(f"Missing API keys: {', '.join(missing)}. "
             "Copy .env.example to .env and fill it in.")
    st.stop()

index_strip()

tab_stocks, tab_penny, tab_crypto = st.tabs(
    ["🔥 MarketPulse", "🟣 PennyPulse", "🪙 CryptoPulse"])

# --- MarketPulse ---
with tab_stocks:
    news_top_n = None
    scan_delay = None
    if universe == "Custom":
        symbols = tuple(s.strip().upper() for s in custom.split(",") if s.strip())
    elif universe == "Everything 🌐":
        symbols = tuple(config.EVERYTHING_STOCKS)
        # Big list: quotes for all, news only for the 12 biggest movers.
        # Slower per-call delay keeps us under 60 calls/min on 105 symbols.
        news_top_n = 12
        scan_delay = 0.7
    else:
        symbols = tuple(config.CORE_STOCKS)
        scan_delay = None

    if st.button("🔄 Run scan", type="primary"):
        cached_universe_scan.clear()

    if not symbols:
        st.info("Enter at least one symbol.")
    else:
        results = cached_universe_scan(symbols, news_top_n=news_top_n,
                                       scan_delay=scan_delay)
        label = session_label()
        if label:
            st.subheader(label)
            st.caption("Quotes reflect extended-hours trading.")
        st.caption(
            f"Last scan {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')} • "
            f"{len(results)} results • showing top {config.TOP_N}")

        if results:
            ticker_tape(results)

        shown = results
        if universe == "Everything 🌐":
            sector = st.selectbox("Sector", ["All"] + list(config.SECTORS))
            if sector != "All":
                shown = [r for r in results
                         if r.get("sector") == sector]

        if shown and universe == "Everything 🌐":
            with st.expander("🏭 Sectors today", expanded=True):
                sector_board(sector_summary(shown))

        for res in shown[:config.TOP_N]:
            result_card(res)

        if shown:
            if st.button("✨ AI Market Brief"):
                items = tuple(
                    (r["symbol"], r["quote"]["price"],
                     r["quote"]["change_percent"],
                     r["news"][0]["headline"] if r["news"] else "")
                    for r in shown[:12]
                )
                st.session_state["brief"] = cached_brief(items)
            brief = st.session_state.get("brief")
            if brief:
                with st.expander("✨ Market Brief", expanded=True):
                    st.markdown(brief)

            st.subheader("Heatmap")
            heatmap(shown)

            if universe == "Everything 🌐":
                st.subheader("All results")
                st.dataframe(
                    [{
                        "Symbol": r["symbol"],
                        "Sector": r.get("sector", "Other"),
                        "Price": fmt_price(r["quote"]["price"]),
                        "Change": fmt_change(r["quote"]["change_percent"]),
                        "Score": r["score"],
                    } for r in shown],
                    use_container_width=True,
                )

# --- PennyPulse ---
with tab_penny:
    st.caption(
        f"Filters: price ≤ ${config.PENNY_MAX_PRICE:.2f}, "
        f"|move| ≥ {config.PENNY_MIN_MOVE:.0f}%. "
        "Passing a filter is not a buy signal.")
    penny_input = st.text_input("Symbols to check", "SOFI, HOOD, NIO")
    if st.button("Check filters"):
        cached_stock_scan.clear()
    syms = [s.strip().upper() for s in penny_input.split(",") if s.strip()][:10]
    rows = []
    for sym in syms:
        res = cached_stock_scan(sym)
        if not res:
            rows.append({"Symbol": sym, "Price": "—",
                         "Change": "—", "Passes": "no data"})
            continue
        q = res["quote"]
        ok = penny_qualifies(q["price"], q["change_percent"])
        rows.append({
            "Symbol": sym,
            "Price": fmt_price(q["price"]),
            "Change": fmt_change(q["change_percent"]),
            "Passes": "✅" if ok else "❌",
        })
    st.dataframe(rows, use_container_width=True)

# --- CryptoPulse ---
with tab_crypto:
    st.caption("Spot prices via Finnhub. Change is vs. prior close.")
    if st.button("🔄 Refresh crypto"):
        cached_universe_scan.clear()
    crypto_results = cached_universe_scan(tuple(CRYPTO_MAP.values()))
    for res in crypto_results:
        base = res["symbol"].split(":")[-1].replace("USDT", "")
        result_card({**res, "symbol": base}, key_prefix="crypto-")

st.divider()
st.caption("Bandz Terminal • Data: Finnhub • Explanations: Gemini • "
           "Not financial advice.")
