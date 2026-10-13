#!/usr/bin/env python3
"""Bandz Terminal -- stock-watching terminal, Stackz-blotter style.

Run:  streamlit run web.py

Gold-on-charcoal watch terminal: watchlist cards with sparklines, a stock
news wire, sector board, heatmap, and price alerts. Watching only --
no trading here. Every number comes from the same engine the Discord
bot used: scan -> score -> news -> (on-demand) AI explanation.
"""

import asyncio
import html
import itertools
import json
import os
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import aiohttp
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from marketpulse import alerts as alert_store
from marketpulse import cache, calibration, config
from marketpulse import screener as screener_mod
from marketpulse import sentiment as sentiment_mod
from marketpulse import stackz as stackz_mod
from marketpulse import themes as theme_mod
from marketpulse import watchlist as watchlist_store
from marketpulse.ai import (DEGRADED_PREFIX, _gemini_text,
                            classify_gemini_status, gemini_probe,
                            generate_ai_analysis, generate_market_brief,
                            generate_mover_explanation,
                            generate_watchlist_digest)
from marketpulse import indicators as ind
from marketpulse import treemap as tm
from marketpulse.search import suggest_symbols
from marketpulse.charts import (GF_DEFAULT, GF_RANGE_LABEL, GF_TIMEFRAMES,
                                INTRADAY_TIMEFRAMES, big_chart_svg,
                                candles_svg, equal_weight_rebased,
                                gf_chart_svg, rebase_to_100,
                                timeframe_change)
from marketpulse.data import (FinnhubClient, coingecko_board,
                              coingecko_dominance, tv_heatmap_scan,
                              yahoo_macro, yahoo_ohlc, yahoo_simple_quote)
from marketpulse.engine import (breadth_counts, earnings_day_label,
                                group_earnings, scan_stock, scan_universe,
                                sector_summary)
from marketpulse.format import (CCY_SYMBOLS, fmt_change, fmt_price,
                                fmt_price_ccy, fx_rates_from_strip,
                                score_band)
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


# ---------------- theme ----------------
# CSS lives in marketpulse/themes.py. The sidebar radio switches themes
# and persists the choice to marketpulse/theme.json (gitignored).

THEME = theme_mod.load_theme()
st.markdown(theme_mod.THEME_CSS[THEME], unsafe_allow_html=True)
# getattr guard: shared CSS is progressive enhancement -- a missing
# constant must never crash the app (e.g. partial deploy sync).
st.markdown(getattr(theme_mod, "SHARED_CSS", ""), unsafe_allow_html=True)


def heat_color(pct):
    """Charcoal -> green/red tile background for a % change."""
    t = max(-1.0, min(1.0, pct / 5.0))
    base = (28, 28, 30)
    if t >= 0:
        target = (18, 90, 60)
    else:
        target = (110, 35, 35)
        t = -t
    r = int(base[0] + (target[0] - base[0]) * t)
    g = int(base[1] + (target[1] - base[1]) * t)
    b = int(base[2] + (target[2] - base[2]) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


_spark_ids = itertools.count(1)


def spark_svg(closes, w=320, h=56):
    """Tiny hand-rolled sparkline -- no widget weight, blotter style.

    Line plus a soft gradient area fill and an end dot for depth.
    """
    if len(closes) < 2:
        return ""
    closes = closes[-60:]
    mn, mx = min(closes), max(closes)
    rng = (mx - mn) or 1.0
    pts = []
    for i, c in enumerate(closes):
        x = i / (len(closes) - 1) * w
        y = h - 4 - (c - mn) / rng * (h - 8)
        pts.append(f"{x:.1f},{y:.1f}")
    color = "#34d399" if closes[-1] >= closes[0] else "#f87171"
    gid = f"sg{next(_spark_ids)}"
    url = f"#{gid}"  # built outside braces: # starts a comment in f-strings
    line = " ".join(pts)
    x0 = pts[0].split(",")[0]
    xn, yn = pts[-1].split(",")
    area = f"{x0},{h} {line} {xn},{h}"
    return (
        f'<svg class="bz-spark" viewBox="0 0 {w} {h}" '
        f'preserveAspectRatio="none">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{color}" stop-opacity=".22"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/>'
        f"</linearGradient></defs>"
        f'<polygon points="{area}" fill="url({url})"/>'
        f'<polyline points="{line}" fill="none" stroke="{color}" '
        f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{xn}" cy="{yn}" r="3" fill="{color}"/>'
        "</svg>"
    )


def time_ago(ts):
    """Unix timestamp -> '2h ago'."""
    try:
        dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        mins = int((datetime.now(timezone.utc) - dt).total_seconds() // 60)
        if mins < 1:
            return "just now"
        if mins < 60:
            return f"{mins}m ago"
        if mins < 1440:
            return f"{mins // 60}h {mins % 60}m ago"
        return f"{mins // 1440}d ago"
    except (TypeError, ValueError):
        return ""


def stackz_time_et(iso):
    """ISO timestamp -> 'Sep 29 · 12:31p' in Eastern time."""
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        et = dt.astimezone(ZoneInfo("America/New_York"))
        hour = et.hour % 12 or 12
        ap = "a" if et.hour < 12 else "p"
        return f"{et:%b} {et.day} · {hour}:{et.minute:02d}{ap}"
    except (TypeError, ValueError):
        return ""


def market_is_open():
    et = datetime.now(ZoneInfo("America/New_York"))
    mins = et.hour * 60 + et.minute
    return et.weekday() < 5 and 570 <= mins < 960


@st.cache_data(ttl=600, show_spinner=False)
def ccy_rates():
    """Units-per-USD for each display currency (memoized 10 min)."""
    return fx_rates_from_strip(cached_fx())


def disp_price(price_usd):
    """Format a USD price in the sidebar-selected display currency."""
    return fmt_price_ccy(price_usd,
                         st.session_state.get("bz-ccy", "USD"),
                         ccy_rates())


def esc_dollar(text):
    """Escape $ for st.markdown.

    Streamlit renders $...$ as LaTeX math, so any two $ figures in one
    markdown block (prices, 52W ranges, $5B headlines) get mangled into
    math output. Escaping keeps the literal $ visible.

    Uses an HTML entity instead of a backslash: &#36; renders as $ in
    every markdown/HTML context (a backslash shows literally inside
    HTML blocks) and never triggers LaTeX.
    """
    return text.replace("$", "&#36;") if isinstance(text, str) else text


def smd(html_text):
    """st.markdown(unsafe_allow_html=True) with $ escaped (see esc_dollar)."""
    st.markdown(esc_dollar(html_text), unsafe_allow_html=True)


def dir_glyph(change):
    """Text direction glyph for titles (▲/▼/•) — no emoji."""
    if not isinstance(change, (int, float)):
        return "•"
    return "▲" if change > 0 else "▼" if change < 0 else "•"


def session_label():
    """Pre-market / after-hours framing for the stock tab."""
    et = datetime.now(ZoneInfo("America/New_York"))
    mins = et.hour * 60 + et.minute
    if et.weekday() >= 5:
        return "Weekend — showing last close"
    if mins < 240:
        return "Overnight — showing last close"
    if mins < 570:
        return "Pre-market movers"
    if mins >= 960:
        return "After-hours movers"
    return None


def section(num, title, sub=""):
    smd(
        f'<div class="bz-sec"><span class="bz-num">{num}</span>'
        f"<h2>{html.escape(title)}</h2></div>",
    )
    if sub:
        st.markdown(f'<div class="bz-sub">{html.escape(sub)}</div>',
                    unsafe_allow_html=True)


#: Symbols shown per page in the News tab's per-symbol list.
NEWS_SYMS_PER_PAGE = 8


def paginate(items, page, per_page):
    """1-based pagination helper. Returns (visible, remaining)."""
    per_page = max(1, int(per_page or 1))
    page = max(1, int(page or 1))
    visible = list(items)[:page * per_page]
    return visible, list(items)[len(visible):]


def command_strip():
    is_open = market_is_open()
    badge = ("open\"><span class=\"dot\"></span>MARKET OPEN" if is_open
             else "shut\"><span class=\"dot\"></span>MARKET CLOSED")
    st.markdown(
        f'<div class="bz-strip"><div class="bz-title">⚡ BANDZ TERMINAL</div>'
        f'<div style="margin-left:auto">'
        f'<span class="bz-badge {badge}</span></div></div>'
        f'<div class="bz-disc">Research only — verify independently. '
        f"Scores describe observed signals, not future returns. "
        f"Not financial advice.</div>",
        unsafe_allow_html=True,
    )


def index_strip():
    """SPY / QQQ / DIA / IWM as blotter stat chips."""
    results = cached_universe_scan(tuple(ETF_STRIP))
    cards = []
    for res in results:
        q = res["quote"]
        chg = q["change_percent"]
        cls = "up" if chg > 0 else "down" if chg < 0 else "flat"
        cards.append(
            f'<div class="bz-idxc"><div class="s">{res["symbol"]}</div>'
            f'<div class="p">{disp_price(q["price"])}</div>'
            f'<div class="c {cls}">{fmt_change(chg)}</div></div>'
        )
    smd(f'<div class="bz-idx">{"".join(cards)}</div>')


@st.cache_data(ttl=300, show_spinner=False)
def cached_fx():
    """EUR/USD, GBP/USD, USD/JPY via Yahoo's free chart API.

    Finnhub's forex endpoints are blocked on this plan, so the FX strip
    is Yahoo-backed (same chart API as the sparklines). Two daily closes
    give the day-over-day change.
    """
    pairs = [("EUR/USD", "EURUSD=X"), ("GBP/USD", "GBPUSD=X"),
             ("USD/JPY", "USDJPY=X"), ("USD/CAD", "USDCAD=X"),
             ("AUD/USD", "AUDUSD=X")]

    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            out = []
            for label, ysym in pairs:
                closes = await _yahoo_closes(session, ysym, rng="2d",
                                             interval="1d")
                if len(closes) >= 2:
                    price, prev = closes[-1], closes[-2]
                    chg = (price - prev) / prev * 100 if prev else 0.0
                    out.append({"label": label, "price": price,
                                "change": chg})
            return out

    return _run(_go())


def fx_strip():
    """Currency strip next to the ETF strip: EUR/USD, GBP/USD, USD/JPY."""
    pairs = cached_fx()
    if not pairs:
        return
    cards = []
    for p in pairs:
        chg = p["change"]
        cls = "up" if chg > 0 else "down" if chg < 0 else "flat"
        price = p["price"]
        px = f"{price:,.4f}" if price < 10 else f"{price:,.2f}"
        cards.append(
            f'<div class="bz-idxc"><div class="s">{p["label"]}</div>'
            f'<div class="p">{px}</div>'
            f'<div class="c {cls}">{fmt_change(chg)}</div></div>'
        )
    smd(f'<div class="bz-idx">{"".join(cards)}</div>')


def ticker_tape(results):
    """Ticker strip: every scanned symbol as a swipeable chip row.

    Native horizontal scroll instead of the old infinite CSS marquee --
    zero constant GPU cost, and touch momentum scrolling works on phones.
    """
    if not results:
        return
    items = []
    for r in results:
        chg = r["quote"]["change_percent"]
        cls = "up" if chg > 0 else "down" if chg < 0 else "flat"
        items.append(
            f'<span class="tape-chip"><b>{html.escape(r["symbol"])}</b> '
            f'<span class="{cls}">{chg:+.2f}%</span></span>'
        )
    smd(f'<div class="tape-hint">All symbols — swipe</div>'
        f'<div class="tape-strip">{"".join(items)}</div>')


def sector_board(summary):
    """Sectors today: average % move per sector, best at top."""
    rows = []
    for sector, avg, count in summary:
        width = min(abs(avg) / 3 * 100, 100)  # 3% move = full bar
        color = "#48d597" if avg > 0 else "#ff6b63" if avg < 0 else "#aaa69a"
        cls = "up" if avg > 0 else "down" if avg < 0 else "flat"
        rows.append(
            f'<div style="display:flex;align-items:center;gap:8px;'
            f'margin:5px 0;">'
            f'<div style="width:130px;font-size:12px;color:#aaa69a;'
            f'white-space:nowrap;overflow:hidden;">'
            f"{html.escape(sector)}</div>"
            f'<div style="flex:1;background:#2c2c2e;border-radius:4px;'
            f'height:14px;">'
            f'<div style="height:14px;border-radius:4px;width:{width:.0f}%;'
            f'background:{color};opacity:0.9;"></div></div>'
            f'<div class="{cls}" style="width:70px;text-align:right;'
            f'font-family:monospace;font-size:12px;">{avg:+.2f}%</div>'
            f"</div>"
        )
    smd("".join(rows))


def heatmap(results):
    """Market-cap-weighted treemap (TradingView's free scanner).

    Tiles sized by market cap, colored by day change, grouped by
    sector. Falls back to the equal-tile board when the scan is down.
    """
    tv = cached_tv_heatmap()
    if tv:
        parts = []
        for sector, tiles in tv:
            tds = []
            for t in tiles:
                chg = t["change"]
                if t["w"] > 90 and t["h"] > 90:
                    label = (f"<b>{html.escape(t['symbol'])}</b>"
                             f"<span>{chg:+.2f}%</span>")
                elif t["w"] > 45:
                    label = f"<b>{html.escape(t['symbol'])}</b>"
                else:
                    label = ""
                tds.append(
                    f'<div class="tmt" '
                    f'style="left:{t["x"] / 10:.2f}%;'
                    f'top:{t["y"] / 10:.2f}%;'
                    f'width:{t["w"] / 10:.2f}%;'
                    f'height:{t["h"] / 10:.2f}%;'
                    f'background:{heat_color(chg)}">{label}</div>')
            parts.append(
                f'<div class="heat-label">{html.escape(sector)}</div>'
                f'<div class="tm">{"".join(tds)}</div>')
        smd(
            '<div class="bz-tm-note">Top 400 US stocks by market cap · '
            "tile size = market cap · color = day change</div>"
            + "".join(parts),
        )
        return
    _heatmap_tiles(results)


@st.cache_data(ttl=120, show_spinner=False)
def cached_tv_heatmap():
    """[(sector, treemap tiles)] for the top 400 US names by market cap.

    Tiles carry symbol/name/change/mcap plus x,y,w,h in 0..1000 space
    from marketpulse.treemap (squarified). None when the TradingView
    scan is unavailable — heatmap() then falls back to equal tiles.
    """
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            return await tv_heatmap_scan(session, limit=400)
    rows = _run(_go())
    if not rows:
        return None
    by_sector = {}
    for r in rows:
        by_sector.setdefault(r["sector"], []).append(r)
    out = []
    for sector in sorted(by_sector):
        tiles = tm.layout([{"weight": r["mcap"], **r}
                           for r in by_sector[sector]])
        if tiles:
            out.append((sector, tiles))
    return out or None


def _heatmap_tiles(results):
    """Equal-tile fallback: the original sector-grouped heatmap."""
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
                f"<b>{html.escape(r['symbol'])}</b>"
                f'<span class="{cls}">{chg:+.2f}%</span></div>'
            )
        parts.append(
            f'<div class="heat-label">{html.escape(sector)}</div>'
            f'<div class="heat">{"".join(tiles)}</div>'
        )
    smd("".join(parts))


def fmt_earnings(date_str):
    """YYYY-MM-DD -> 'Oct 28'."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%b %d")
    except (TypeError, ValueError):
        return date_str


def news_wire(results, limit=30):
    """Aggregated stock news wire: newest headlines across the scan."""
    seen, items = set(), []
    for r in results:
        for n in r.get("news", []):
            head = (n.get("headline") or "").strip()
            if not head or head in seen:
                continue
            seen.add(head)
            items.append((n.get("timestamp") or 0, r["symbol"], n))
    items.sort(key=lambda x: x[0], reverse=True)
    rows = []
    for ts, sym, n in items[:limit]:
        head = html.escape(n["headline"])
        url = n.get("url") or ""
        link = (f'<a href="{html.escape(url)}" target="_blank">{head}</a>'
                if url else head)
        meta = " · ".join(x for x in [n.get("source") or "",
                                      time_ago(ts)] if x)
        pill = sentiment_mod.sentiment_pill(
            sentiment_mod.classify_sentiment(n.get("headline")))
        rows.append(
            f'<div class="bz-witem"><span class="bz-wsym">'
            f"{html.escape(sym)}</span>"
            f"<div><p>{link}{pill}</p>"
            f"<small>{html.escape(meta)}</small></div></div>"
        )
    body = "".join(rows) or (
        '<div class="bz-witem"><span class="bz-wsym">—</span>'
        "<div><p>No fresh headlines in this scan.</p></div></div>")
    smd(f'<div class="bz-wire">{body}</div>')


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


@st.cache_data(ttl=3600, show_spinner=False)
def cached_gf_series(symbol, tf_key):
    """(unix_ts, close) pairs for the detail panel (GF timeframes).

    Yahoo-first; no Finnhub fallback (its /stock/candle isn't covered
    by this plan). [] when unavailable.
    """
    rng, interval = GF_TIMEFRAMES.get(tf_key,
                                      GF_TIMEFRAMES[GF_DEFAULT])
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            return await _yahoo_series(session, symbol, rng=rng,
                                       interval=interval)
    return _run(_go())


@st.cache_data(ttl=600, show_spinner=False)
def cached_ohlc(symbol, tf_key):
    """OHLCV candles for the detail panel's candle view (GF timeframes).

    Yahoo's free chart API, no key. [] when unavailable.
    """
    rng, interval = GF_TIMEFRAMES.get(tf_key,
                                      GF_TIMEFRAMES[GF_DEFAULT])
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            return await yahoo_ohlc(session, symbol, range_=rng,
                                    interval=interval)
    return _run(_go())


def _candle_indicators(ohlc, selected):
    """(overlays, subpanels) for candles_svg from indicator names.

    selected: subset of {"SMA20","EMA20","BB","RSI","MACD"}.
    """
    closes = [c["c"] for c in ohlc]
    overlays, subs = {}, []
    if "SMA20" in selected:
        overlays["sma20"] = ind.sma(closes, 20)
    if "EMA20" in selected:
        overlays["ema20"] = ind.ema(closes, 20)
    if "BB" in selected:
        _, upper, lower = ind.bollinger(closes, 20, 2)
        overlays["bb_upper"] = upper
        overlays["bb_lower"] = lower
    if "RSI" in selected:
        overlays["rsi"] = ind.rsi(closes, 14)
        subs.append("rsi")
    if "MACD" in selected:
        ml, sl, hs = ind.macd(closes)
        overlays["macd_line"] = ml
        overlays["macd_signal"] = sl
        overlays["macd_hist"] = hs
        subs.append("macd")
    return overlays, tuple(subs)


@st.cache_data(ttl=600, show_spinner=False)
def cached_cg_board():
    """CoinGecko top-crypto snapshot with 7-day sparklines (no key).

    One call, cached 10 min to respect the free rate limit.
    [] when unavailable.
    """
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            return await coingecko_board(session)
    return _run(_go())


@st.cache_data(ttl=600, show_spinner=False)
def cached_cg_dominance():
    """BTC/ETH market-cap dominance via CoinGecko's free /global.

    None when unavailable.
    """
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            return await coingecko_dominance(session)
    return _run(_go())


@st.cache_data(ttl=300, show_spinner=False)
def cached_macro():
    """VIX + 10Y Treasury yield via Yahoo's free chart API (no key).

    {} when unavailable.
    """
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            return await yahoo_macro(session)
    return _run(_go())


@st.cache_data(ttl=300, show_spinner=False)
def cached_glance():
    """S&P / Nasdaq futures snapshot for the at-a-glance strip.

    [(label, change_pct)] via Yahoo, no key. [] when unavailable.
    """
    async def _go():
        out = []
        async with aiohttp.ClientSession(trust_env=True) as session:
            for sym, label in (("ES=F", "S&P fut"), ("NQ=F", "Nas fut")):
                _, chg = await yahoo_simple_quote(session, sym)
                if chg is not None:
                    out.append((label, chg))
        return out
    return _run(_go())


def watchlist_benchmark(symbols, tf_key):
    """Equal-weighted watchlist vs SPY, rebased to 100.

    Returns (wl_pct, spy_pct, wl_rebased, spy_rebased) or None when
    there isn't enough history.
    """
    closes_map = {}
    for sym in list(symbols) + ["SPY"]:
        closes = [c for _, c in cached_gf_series(sym, tf_key) if c]
        if len(closes) >= 2:
            closes_map[sym] = closes
    spy = closes_map.get("SPY")
    wl_lists = [closes_map[s] for s in symbols if s in closes_map]
    if not spy or not wl_lists:
        return None
    avg = equal_weight_rebased(wl_lists)
    spy_rb = rebase_to_100(spy)[-len(avg):]
    if len(avg) < 2 or len(spy_rb) < 2:
        return None
    wl_pct = (avg[-1] - avg[0]) / avg[0] * 100
    spy_pct = (spy_rb[-1] - spy_rb[0]) / spy_rb[0] * 100
    return wl_pct, spy_pct, avg, spy_rb


@st.cache_data(ttl=900, show_spinner=False)
def cached_stackz():
    """Stackz paper-trading snapshot (public gist, refreshed ~15 min).

    Never raises; None means the honest empty state in the Stackz tab.
    """
    return stackz_mod.fetch_stackz_snapshot()


# --- Bot City tab: the paper-trading strategies as a neon city ---
# LEARN: the full strategy roster is a constant because the snapshot
# only lists strategies that already have fills — quiet ones still
# get a gray "standby" tower so the skyline stays complete.
_BOT_CITY_ROSTER = [
    "adx_system", "atr_breakout", "bollinger_reversion", "donchian_breakout",
    "earnings_drift", "ema_cross", "ichimoku", "keltner_breakout", "macd",
    "news_sentiment", "obv_trend", "parabolic_sar", "rsi2_meanrev",
    "sma_cross", "stoch_oscillator", "supertrend", "vwap_meanrev",
    "williams_r",
]
_BOT_CITY_GOAL = 100  # Tbandz's gate: 100 paper trades before live money


def _short_strategy(name):
    """Compact tower label: 'bollinger_reversion' -> 'BOLLINGER'."""
    return (name.replace("_meanrev", "").replace("_system", "")
                .replace("_oscillator", "").upper()[:8])


def bot_city_html(snap):
    """Build the Bot City page HTML from a Stackz snapshot.

    Towers come from the snapshot's trade list (strategy + realized
    P&L per close); the canvas renderer is the vendored bot_city.js.
    Returns None when there's no trade data or the renderer is missing
    — the tab then shows the honest empty state instead of a guess.
    """
    trades = (snap or {}).get("trades") or []
    if not trades:
        return None
    now = datetime.now(timezone.utc)
    per = {}
    for t in trades:
        s = t.get("strategy") or "?"
        pnl = t.get("realized_pnl") or 0
        d = per.setdefault(s, {"closed": 0, "wins": 0, "pnl": 0.0,
                               "recent": [], "freshest": None})
        # LEARN: a close is a sell side or any line carrying realized P&L.
        if t.get("side") in ("sell", "close") or pnl != 0:
            d["closed"] += 1
            d["pnl"] += pnl
            if pnl > 0:
                d["wins"] += 1
            # LEARN: trades arrive oldest-first, so appending keeps
            # recent chronological — the card takes the last 3.
            d["recent"].append({
                "s": str(t.get("symbol") or "?"),
                "p": round(pnl, 2),
                "t": stackz_time_et(t.get("time")),
            })
            try:
                dt = datetime.fromisoformat(t.get("time"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age = (now - dt).total_seconds()
                if age >= 0 and (d["freshest"] is None or age < d["freshest"]):
                    d["freshest"] = age
            except (TypeError, ValueError):
                pass
    towers = []
    for s in _BOT_CITY_ROSTER:
        v = per.get(s, {"closed": 0, "wins": 0, "pnl": 0.0,
                        "recent": [], "freshest": None})
        # LEARN: "strat" rides along so the pulse list can find the
        # tower's index after the sort below — JS only needs the index.
        if v["closed"] == 0:
            towers.append({"name": "", "color": "#5a5f6e",
                           "value": 0, "sub": "", "strat": s})
        else:
            color = ("#3ddc84" if v["pnl"] > 0
                     else "#ff5f5f" if v["pnl"] < 0 else "#d9a441")
            sign = "+" if v["pnl"] >= 0 else "-"
            towers.append({"name": _short_strategy(s), "color": color,
                           "value": v["closed"],
                           "sub": f"{sign}${abs(v['pnl']):.2f}",
                           "strat": s,
                           "stats": {
                               "closed": v["closed"], "wins": v["wins"],
                               "pnl": round(v["pnl"], 2),
                               "recent": v["recent"][-3:][::-1],
                           }})
    # LEARN: busiest skyline reads best — most closed trades first.
    towers.sort(key=lambda t: -t["value"])
    # LEARN: pulses are honest replays, not live sockets — the page is
    # a static snapshot, so any close in the last 2h gets a looping
    # beam until the next snapshot lands. One pulse per strategy.
    idx_of = {t["strat"]: i for i, t in enumerate(towers) if t["strat"]}
    pulses = []
    for s, v in per.items():
        if (s in idx_of and v["freshest"] is not None
                and v["freshest"] <= 7200):
            pulses.append({"i": idx_of[s], "age": int(v["freshest"])})
    total_pnl = sum(v["pnl"] for v in per.values())
    total_closed = sum(v["closed"] for v in per.values())
    psign = "+" if total_pnl >= 0 else "-"
    config = {
        "accent": "#d9a441",
        "towers": towers,
        "pulses": pulses,
        "dome": {
            "title": "PAPER P&L — NOT REAL MONEY",
            "shortTitle": "PAPER P&L",
            "value": f"{psign}${abs(total_pnl):.2f}",
            "sub": f"{total_closed}/{_BOT_CITY_GOAL} closed · paper",
        },
    }
    js_path = os.path.join(os.path.dirname(__file__),
                           "marketpulse", "bot_city.js")
    try:
        with open(js_path, encoding="utf-8") as f:
            city_js = f.read()
    except OSError:
        return None
    active = [t for t in towers if t["name"]]
    legend_rows = "\n".join(
        f'<div class="lrow"><span class="dot" style="background:{t["color"]}">'
        f'</span><span class="lname">{html.escape(t["name"])}</span>'
        f'<span class="lsub">{html.escape(t["sub"])}</span></div>'
        for t in active)
    # LEARN: the footer only claims pulses when at least one close is
    # fresh enough to actually pulse — no phantom promises.
    pulse_note = " · ✦ PULSE = REAL CLOSE · LAST 2H" if pulses else ""
    # LEARN: the config rides inside a <script> block, and json.dumps
    # does NOT escape </script> — a hostile string in trade data could
    # break out of the block and run. \u-escaping < > & keeps the JSON
    # identical once JS parses it, with no breakout possible. (The
    # legend is html.escape'd and the tap card uses textContent, so
    # this is the only injection surface.)
    cfg_json = (json.dumps(config).replace("&", "\\u0026")
                .replace("<", "\\u003c").replace(">", "\\u003e"))
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#07080b;color:#ece9df;
font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}
.hd{{padding:12px 16px;border-bottom:1px solid #1c1f2a;display:flex;
justify-content:space-between;align-items:center}}
.hd h1{{font-size:14px;letter-spacing:3px;color:#d9a441}}
.paper{{font-size:10px;letter-spacing:2px;color:#ff5f5f;
border:1px solid #ff5f5f;border-radius:4px;padding:4px 8px}}
#city{{width:100%;height:420px;display:block}}
#stage{{position:relative}}
/* LEARN: the tap card lives inside #stage so it overlays the canvas
   bottom; translateY(120%) parks it off-screen until .show slides it up. */
#tcard{{position:absolute;left:10px;right:10px;bottom:10px;z-index:5;
background:rgba(10,16,32,.96);border:1px solid #d9a441;border-radius:10px;
padding:10px 12px;transform:translateY(130%);transition:transform .32s ease;
box-shadow:0 6px 24px rgba(0,0,0,.5)}}
#tcard.show{{transform:translateY(0)}}
#tclose{{position:absolute;top:6px;right:10px;background:none;border:none;
color:#8a8fa3;font-size:14px;cursor:pointer;padding:4px}}
#ttitle{{font-size:13px;font-weight:800;letter-spacing:2px;color:#d9a441;
margin-bottom:6px;padding-right:24px}}
#tstats{{display:flex;gap:14px;font-size:11px;color:#8a8fa3;margin-bottom:8px}}
#tstats b{{color:#ece9df;font-size:13px;display:block}}
.up{{color:#3ddc84}} .dn{{color:#ff5f5f}}
#trecent{{font-size:11px;color:#8a8fa3}}
#trecent .rrow{{display:flex;justify-content:space-between;padding:3px 0;
border-top:1px dashed #1c1f2a}}
.legendwrap{{padding:10px 16px 4px}}
.lhead{{font-size:10px;letter-spacing:2px;color:#8a8fa3;margin-bottom:6px}}
.lrow{{display:flex;align-items:center;gap:10px;padding:6px 0;
border-bottom:1px dashed #1c1f2a;font-size:12px}}
.dot{{width:9px;height:9px;border-radius:50%;flex:none}}
.lname{{font-weight:700;letter-spacing:1px}}
.lsub{{margin-left:auto;color:#8a8fa3;font-size:11px}}
.ft{{padding:8px 16px;font-size:10px;letter-spacing:2px;color:#8a8fa3;
border-top:1px solid #1c1f2a;text-align:center}}
</style></head><body>
<div class="hd"><h1>⚡ BOT CITY</h1><span class="paper">PAPER ONLY</span></div>
<div id="stage"><canvas id="city"></canvas>
<div id="tcard"><button id="tclose" aria-label="close">✕</button>
<div id="ttitle"></div><div id="tstats"></div><div id="trecent"></div></div>
</div>
<div class="legendwrap"><div class="lhead">ACTIVE STRATEGIES · PAPER · TAP A TOWER</div>
{legend_rows}</div>
<div class="ft">EACH TOWER IS A STRATEGY · HEIGHT = CLOSED TRADES{pulse_note} · PAPER ONLY</div>
<script>{city_js}</script>
<script>initCity('city', {cfg_json});</script>
</body></html>"""


@st.cache_data(ttl=120, show_spinner=False)
def cached_stock_scan(symbol):
    """Scan one symbol (PennyPulse tab)."""
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            client = FinnhubClient(session)
            return await scan_stock(client, symbol, include_ai=False)
    return _run(_go())


async def _yahoo_series(session, symbol, rng="1d", interval="5m"):
    """(unix_ts, close) pairs via Yahoo's free chart API (no key).

    Timestamps come from the chart payload so the 3-month chart can draw
    a real date axis. Pairs with missing closes are dropped.
    """
    if ":" in symbol:  # "BINANCE:BTCUSDT" -> "BTC-USD"
        ysym = symbol.split(":")[-1].replace("USDT", "-USD")
    else:
        ysym = symbol
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}"
    try:
        async with session.get(
            url,
            params={"interval": interval, "range": rng},
            headers={"User-Agent": "Mozilla/5.0",
                     "Accept-Encoding": "gzip, deflate"},
            timeout=15,
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
        result = (data.get("chart", {}).get("result") or [None])[0]
        if not result:
            return []
        quote = (result.get("indicators", {}).get("quote") or [{}])[0]
        closes = quote.get("close") or []
        stamps = result.get("timestamp") or []
        pairs = []
        for i, c in enumerate(closes):
            if isinstance(c, (int, float)):
                ts = stamps[i] if i < len(stamps) else None
                pairs.append((ts, float(c)))
        return pairs
    except Exception:
        return []


async def _yahoo_closes(session, symbol, rng="1d", interval="5m"):
    """Closes via Yahoo's free chart API (no key).

    Fallback for when the Finnhub plan doesn't cover /stock/candle.
    """
    return [c for _, c in await _yahoo_series(session, symbol, rng, interval)]


@st.cache_data(ttl=120, show_spinner=False)
def cached_candles(symbol):
    """Intraday closes for the sparkline on each card.

    Yahoo's free chart API first -- this Finnhub plan doesn't cover
    /stock/candle, so asking it first just spams 403s in the logs.
    Finnhub stays as the fallback.
    """
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            closes = await _yahoo_closes(session, symbol)
            if len(closes) < 2:
                client = FinnhubClient(session)
                closes = await client.candles(symbol)
            return closes
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


@st.cache_data(ttl=300, show_spinner=False)
def gemini_source():
    """(status, detail) based on a real minimal Gemini call.

    status: live | key-rejected | model-not-found | network | error | None.
    Key presence alone can't be trusted (a bad pasted key looks
    'connected'), so the sidebar reports what this probe finds.
    """
    if not config.GEMINI_API_KEY:
        return None, "no key configured"

    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            return await gemini_probe(session)
    try:
        ok, detail = _run(_go())
        return classify_gemini_status(ok, detail), detail
    except Exception:
        return "error", "probe crashed"


@st.cache_data(ttl=300, show_spinner=False)
def finnhub_source():
    """Where live quotes are actually coming from right now.

    "finnhub" = Finnhub API healthy, "yahoo" = Finnhub failing and the
    Yahoo fallback is carrying quotes, None = neither is reachable.
    """
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            client = FinnhubClient(session)
            q = await client.quote("AAPL")
            return (q or {}).get("source")
    try:
        return _run(_go())
    except Exception:
        return None


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


def watchlist_digest(items):
    """On-demand AI digest over the user's watchlist. Never auto-runs."""
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            return await generate_watchlist_digest(session, items)
    return _run(_go())


@st.cache_data(ttl=86400, show_spinner=False)
def cached_recommendation(symbol):
    """Analyst consensus for a card pill. None when the endpoint is blocked."""
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            client = FinnhubClient(session)
            return await client.recommendation(symbol)
    return _run(_go())


def validate_symbol(symbol):
    """Finnhub quote lookup; None when the symbol has no market data."""
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return None

    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            client = FinnhubClient(session)
            return await client.quote(symbol)
    return _run(_go())


def _mover_cache_file():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "data", "why_moving.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def mover_explanation(symbol, quote, news):
    """1-2 sentence Gemini explanation of today's move.

    Cached per symbol per day on disk (data/why_moving.json), so repeat
    views don't burn extra Gemini calls.
    """
    path = _mover_cache_file()
    key = f"{symbol}:{datetime.now(timezone.utc).date().isoformat()}"
    try:
        with open(path) as f:
            disk = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        disk = {}
    if key in disk:
        return disk[key]

    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            return await generate_mover_explanation(session, symbol,
                                                  quote, news)
    text = _run(_go())
    # Don't cache degraded (headline-fallback) answers on disk -- a real
    # AI answer may succeed later the same day.
    if not text.startswith(DEGRADED_PREFIX):
        disk[key] = text
        if len(disk) > 200:  # keep the file small
            disk = dict(list(disk.items())[-200:])
        try:
            with open(path, "w") as f:
                json.dump(disk, f)
        except OSError:
            pass
    return text


# ---------------- watch cards ----------------

def detail_panel(result, key_prefix=""):
    """Google-Finance-style detail view for one asset.

    Big price + timeframe change, 1D/5D/1M/6M/YTD pills, gradient
    area chart, key stats grid. Lazy: nothing renders until the user
    taps "Show details", keeping the initial page light on phones.
    """
    quote = result["quote"]
    symbol = result["symbol"]
    price = quote["price"]

    det_key = f"{key_prefix}dtl-{symbol}"
    if not st.session_state.get(det_key):
        if st.button("Show details", key=f"{key_prefix}dshow-{symbol}"):
            st.session_state[det_key] = True
            st.rerun()
        st.caption("Price, chart & key stats — loads on tap.")
        return

    tf_opts = list(GF_TIMEFRAMES.keys())
    tf = (st.pills("Timeframe", tf_opts, default=GF_DEFAULT,
                   label_visibility="collapsed",
                   key=f"{key_prefix}dtf-{symbol}")
          or GF_DEFAULT)
    chart_kind = (st.pills("Chart type", ["Area", "Candles"],
                           default="Area", label_visibility="collapsed",
                           key=f"{key_prefix}dct-{symbol}")
                  or "Area")
    series = cached_gf_series(symbol, tf)
    closes = [c for _, c in series]
    dates = [ts for ts, _ in series]
    chg_abs, chg_pct = timeframe_change(closes)
    up = (chg_abs or 0) >= 0
    chg_cls = "up" if up else "down"
    arrow = "▲" if up else "▼"
    if chg_abs is None:
        chg_html = '<div class="bz-gf-chg">—</div>'
    else:
        chg_html = (
            f'<div class="bz-gf-chg {chg_cls}">{arrow} '
            f'{disp_price(abs(chg_abs))} '
            f'({chg_pct:+.2f}%) {GF_RANGE_LABEL.get(tf, "")}</div>')
    src = html.escape(quote.get("source") or "")
    ago = time_ago(quote.get("timestamp"))
    asof = f"As of {ago}" if ago else "Quote"
    smd(
        f'<div class="bz-gf-head">'
        f'<div class="bz-gf-price">{disp_price(price)}</div>'
        f'{chg_html}'
        f'<div class="bz-gf-asof">{asof}'
        f'{" · " + src if src else ""}</div>'
        f'</div>',
    )

    if chart_kind == "Candles":
        ind_sel = (st.pills("Indicators",
                            ["SMA20", "EMA20", "BB", "RSI", "MACD"],
                            default=["SMA20", "RSI"],
                            selection_mode="multi",
                            label_visibility="collapsed",
                            key=f"{key_prefix}dind-{symbol}")
                   or [])
        ohlc = cached_ohlc(symbol, tf)
        if len(ohlc) >= 2:
            overlays, subs = _candle_indicators(ohlc, ind_sel)
            smd(candles_svg(ohlc, overlays=overlays, subpanels=subs))
        else:
            st.caption("Candle data unavailable right now.")
    elif len(closes) >= 2:
        smd(
            gf_chart_svg(closes, dates=dates,
                         intraday=tf in INTRADAY_TIMEFRAMES),
        )
    else:
        st.caption("Chart data unavailable right now.")

    hi52, lo52 = cached_52w(symbol)

    def _cell(label, value):
        txt = (disp_price(value)
               if isinstance(value, (int, float)) and value else "—")
        return (f'<div class="bz-stat"><span>{label}</span>'
                f'<b>{txt}</b></div>')

    smd(
        '<div class="bz-stats">'
        + _cell("Open", quote.get("open"))
        + _cell("High", quote.get("high"))
        + _cell("Low", quote.get("low"))
        + _cell("Prev close", quote.get("previous_close"))
        + _cell("52-wk high", hi52)
        + _cell("52-wk low", lo52)
        + '</div>',
    )


def watch_card(result, key_prefix="", spark=None):
    """One watched asset, blotter style: price, spark, score, news.

    spark: optional pre-fetched close series (e.g. CoinGecko 7-day)
    used for the sparkline instead of the intraday closes.
    """
    quote = result["quote"]
    symbol = result["symbol"]
    price, change = quote["price"], quote["change_percent"]
    score = result["score"]
    chg_cls = "up" if change > 0 else "down" if change < 0 else "flat"

    closes = (spark if spark and len(spark) >= 2
              else cached_candles(symbol))
    spark = spark_svg(closes)

    hi52, lo52 = cached_52w(symbol)
    range_html = ""
    if hi52 and lo52 and hi52 > lo52:
        pos = max(0.0, min(1.0, (price - lo52) / (hi52 - lo52)))
        range_html = (
            f'<span class="bz-label">52W {disp_price(lo52)} – {disp_price(hi52)} · '
            f"AT {pos:.0%}</span>"
            f'<div class="bz-bar"><div style="width:{pos * 100:.0f}%;"></div></div>'
        )

    meta_lines = []
    edate = cached_earnings().get(symbol)
    if edate:
        meta_lines.append(f"Earnings {fmt_earnings(edate)}")
    ins = cached_insider(symbol)
    if ins:
        t = ins[0]
        px = (f" @ ${t['price']:.2f}"
              if isinstance(t["price"], (int, float)) else "")
        meta_lines.append(
            f"{html.escape(t['name'].split(',')[0])} "
            f"{html.escape(t['side'])} {t['shares']:,} sh{px} "
            f"({html.escape(t['date'])})")
    meta_html = (f'<div class="bz-meta">{" · ".join(meta_lines)}</div>'
                 if meta_lines else "")

    news = result.get("news", [])
    items_html = ""
    for top in news[:2]:
        head = html.escape(top["headline"])
        url = top.get("url") or ""
        link = (f'<a href="{html.escape(url)}" target="_blank">{head}</a>'
                if url else head)
        src = top.get("source") or ""
        ago = time_ago(top.get("timestamp"))
        src_line = " · ".join(x for x in [src, ago] if x)
        items_html += (
            f'<div class="bz-item">{link}'
            f'<span class="bz-src">{html.escape(src_line)}</span></div>'
        )
    if items_html:
        news_html = f'<div class="bz-news">{items_html}</div>'
    else:
        news_html = ('<div class="bz-news"><span class="bz-src">'
                     "No fresh news retrieved.</span></div>")

    reco = cached_recommendation(symbol)
    reco_html = ""
    if reco:
        reco_html = (
            f'<span class="bz-chip">{html.escape(reco["label"])} · '
            f'{reco["analysts"]}</span>')

    smd(
        f'<div class="bz-card {chg_cls}">'
        f'<div class="bz-top"><div>'
        f'<span class="bz-sym">{html.escape(symbol)}</span>'
        f'<span class="bz-chip">{html.escape(result.get("sector", "Other"))}'
        f"</span>{reco_html}</div>"
        f'<div class="bz-chg {chg_cls}">{fmt_change(change)}</div></div>'
        f'<div class="bz-price">{disp_price(price)}</div>'
        f"{spark}"
        f'<span class="bz-label">SCORE {score}/100 · '
        f"{html.escape(score_band(score)).upper()}</span>"
        f"{range_html}{meta_html}{news_html}"
        f"</div>",
    )

    c1, c2 = st.columns(2)
    if len(news) > 2:
        with c1:
            with st.expander(f"More news ({len(news) - 2})"):
                for item in news[2:15]:
                    head = html.escape(item["headline"])
                    url = item.get("url") or ""
                    line = (f'- <a href="{html.escape(url)}" '
                            f'target="_blank">{head}</a>'
                            if url else f"- {head}")
                    smd(line)
                    meta = " · ".join(
                        x for x in [item.get("source") or "",
                                    time_ago(item.get("timestamp"))] if x)
                    if meta:
                        st.caption(meta)
    with c2:
        btn_key = f"{key_prefix}explain-{symbol}"
        if st.button("Explain", key=btn_key):
            with st.spinner("Asking Gemini..."):
                st.session_state[f"analysis-{symbol}"] = explain(
                    symbol, quote, news)
    with st.expander("Details"):
        detail_panel(result, key_prefix=key_prefix)
    analysis = st.session_state.get(f"analysis-{symbol}")
    if analysis:
        st.markdown(esc_dollar(analysis))


# ---------------- sidebar ----------------

with st.sidebar:
    st.header("Controls")
    universe = st.radio("Universe", ["Core", "Everything", "Custom"])

    theme_label = st.radio(
        "Theme", ["Cyber", "Gold", "Retro CRT", "Space"],
        index=["cyber", "gold", "retro", "space"].index(THEME),
    )
    theme_key = {"Cyber": "cyber", "Gold": "gold",
                 "Retro CRT": "retro", "Space": "space"}[theme_label]
    if theme_key != THEME:
        theme_mod.save_theme(theme_key)
        st.rerun()
    st.selectbox(
        "Display currency", list(CCY_SYMBOLS),
        key="bz-ccy",
        help="Converts all prices from USD using live FX rates. "
             "USD is the default.",
    )
    custom = ""
    if universe == "Custom":
        custom = st.text_input("Symbols (comma separated)", "NVDA, TSLA")
    st.divider()
    auto = st.checkbox("Auto-refresh", value=False)
    minutes = 5
    if auto:
        minutes = st.slider("Refresh every (minutes)", 2, 60, 5)
    st.divider()
    st.subheader("My watchlist")
    st.caption("Your tickers — validated against live market data.")
    w_sym = st.text_input("Add ticker", key="wl-sym", placeholder="NVDA")
    if st.button("Add ticker", key="wl-add"):
        quote = validate_symbol(w_sym)
        if not quote:
            st.warning(f"No market data for "
                       f"'{(w_sym or '').strip().upper()}' — check the symbol.")
        elif watchlist_store.add_symbol(w_sym):
            st.success(f"Added {(w_sym or '').strip().upper()}")
            st.rerun()
        else:
            st.warning("Already on your watchlist.")
    for w in watchlist_store.load_watchlist():
        star = "★" if w.get("starred") else "☆"
        c1, c2, c3 = st.columns([3, 1, 1])
        c1.caption(f"{star} {w['symbol']}")
        if c2.button("★" if not w.get("starred") else "☆",
                     key=f"wl-star-{w['symbol']}"):
            watchlist_store.toggle_star(w["symbol"])
            st.rerun()
        if c3.button("\u2715", key=f"wl-del-{w['symbol']}"):
            watchlist_store.remove_symbol(w["symbol"])
            st.rerun()
    st.divider()
    st.subheader("Alerts")
    st.caption("Checked every 15 min during market hours. "
               "A push lands on your phone when one fires.")
    alert_kind = st.radio("Alert type",
                          ["Price move", "Day change %", "News keyword"],
                          key="alert-kind")
    if alert_kind == "News keyword":
        kw = st.text_input("Keyword", key="alert-kw", placeholder="FDA approval")
        if st.button("Add alert", key="alert-add-kw"):
            made = alert_store.add_keyword_alert(kw)
            if made:
                st.success(f"Keyword alert: '{made['keyword']}'")
            else:
                st.warning("Need a keyword (2+ chars), "
                           "or that alert already exists.")
    else:
        a_sym = st.text_input("Symbol", key="alert-sym", placeholder="NVDA")
        if alert_kind == "Price move":
            a_pct = st.slider("Move %", 1.0, 20.0, 3.0, 0.5, key="alert-pct")
            if st.button("Add alert", key="alert-add-price"):
                made = alert_store.add_alert(a_sym, a_pct)
                if made:
                    st.success(f"Alert set: {made['symbol']} ±{made['pct']:g}%")
                else:
                    st.warning("Need a symbol and a % above 0 "
                               "(or that alert already exists).")
        else:
            a_thr = st.slider("Day change %", 1.0, 20.0, 3.0, 0.5,
                              key="alert-thr")
            if st.button("Add alert", key="alert-add-pct"):
                made = alert_store.add_pct_alert(a_sym, a_thr)
                if made:
                    st.success(f"Alert set: {made['symbol']} "
                               f"|day| ≥ {made['threshold']:g}%")
                else:
                    st.warning("Need a symbol and a % above 0 "
                               "(or that alert already exists).")
    for a in alert_store.load_alerts():
        atype = a.get("type", "price")
        if atype == "pct":
            label = (f"{a.get('symbol')} |day change| ≥ "
                     f"{a.get('threshold'):g}%")
        elif atype == "keyword":
            label = f"keyword '{a.get('keyword')}'"
        else:
            base = (f"${a['baseline']:.2f}" if a.get("baseline")
                    else "arming…")
            label = f"{a.get('symbol')} ±{a.get('pct'):g}% • from {base}"
        c1, c2 = st.columns([4, 1])
        c1.caption(label)
        if c2.button("\u2715", key=f"del-{a['id']}"):
            alert_store.remove_alert(a["id"])
            st.rerun()
    st.divider()
    st.subheader("Connections")
    fh_src = finnhub_source()
    fh_label = {"finnhub": "live",
                "yahoo": "degraded (Yahoo fallback)"}.get(fh_src,
                                                         "error — check key")
    st.write("Finnhub:", fh_label if config.FINNHUB_API_KEY else "missing")
    g_status, g_detail = gemini_source()
    g_label = {"live": "live",
               "key-rejected": "key rejected — re-paste it in Secrets",
               "model-not-found": "model not found — check GEMINI_MODEL",
               "network": "network issue — retrying",
               "error": "error — check key"}.get(
        g_status, "missing (AI off)")
    st.write("Gemini:", g_label)
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

command_strip()

missing = config.missing_keys()
if missing:
    st.error(f"Missing API keys: {', '.join(missing)}. "
             "Copy .env.example to .env and fill it in.")
    st.stop()

index_strip()
fx_strip()

# --- ticker search: look up any symbol on demand ---
search_sym = st.text_input("Search any ticker", key="bz-search",
                           placeholder="Symbol or company — e.g. NVDA or NVIDIA")
query = (search_sym or "").strip()


def _fill_search(sym):
    # Runs as the button's on_click callback (before the next script run),
    # which is the only legal time to set a widget's session state.
    st.session_state["bz-search"] = sym


if query and query.upper() not in config.COMPANY_NAMES:
    # Instant suggestions; tapping one fills the box and runs the lookup.
    # (Streamlit refreshes these when you hit Go/Search on the keyboard.)
    for sug_sym, sug_name in suggest_symbols(query, config.COMPANY_NAMES):
        st.button(f"{sug_sym} — {sug_name}", key=f"bz-sug-{sug_sym}",
                  on_click=_fill_search, args=(sug_sym,))
if query:
    sym = query.upper()
    sym = CRYPTO_MAP.get(sym, sym)  # BTC -> BINANCE:BTCUSDT
    with st.spinner(f"Looking up {sym}..."):
        hit = cached_stock_scan(sym)
    if hit:
        watch_card(hit, key_prefix="search-")
        if st.button(f"Add {sym} to watchlist", key="search-add"):
            if watchlist_store.add_symbol(sym):
                st.success(f"Added {sym}")
                st.rerun()
            else:
                st.caption(f"{sym} is already on your watchlist.")
    else:
        st.warning(f"No market data for '{sym}' — check the symbol.")
    st.divider()

tab_stocks, tab_news, tab_penny, tab_crypto, tab_stackz, tab_city, tab_screener = st.tabs(
    ["Stocks", "News", "Penny", "Crypto", "Stackz", "🏙 Bot City", "Screener"])

# --- shared stock scan (MarketPulse + News tabs) ---
news_top_n = None
scan_delay = None
if universe == "Custom":
    symbols = tuple(s.strip().upper() for s in custom.split(",") if s.strip())
elif universe == "Everything":
    symbols = tuple(config.EVERYTHING_STOCKS)
    # Big list: quotes for all, news only for the 20 biggest movers.
    # 0.7s pacing keeps us under 60 calls/min on 150+ symbols.
    news_top_n = 20
    scan_delay = 0.7
else:
    symbols = tuple(config.CORE_STOCKS)
    scan_delay = None

stock_results = []
if symbols:
    stock_results = cached_universe_scan(symbols, news_top_n=news_top_n,
                                         scan_delay=scan_delay)

sector_filter = "All"
if universe == "Everything":
    sector_filter = st.selectbox("Sector", ["All"] + list(config.SECTORS))
shown = [r for r in stock_results
         if sector_filter == "All" or r.get("sector") == sector_filter]

# --- MarketPulse ---
with tab_stocks:
    if st.button("Run scan", type="primary"):
        cached_universe_scan.clear()

    if not symbols:
        st.info("Enter at least one symbol.")
    else:
        label = session_label()
        if label:
            extra = (" Quotes reflect extended-hours trading."
                     if "movers" in label else "")
            st.caption(f"{label}.{extra}")
        st.caption(
            f"Last scan {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')} • "
            f"{len(stock_results)} results • showing top {config.TOP_N}")
        # At-a-glance: futures + market breadth, first thing on the page.
        glance_bits = []
        for label, chg in cached_glance():
            cls = "up" if chg > 0 else "down" if chg < 0 else "flat"
            glance_bits.append(
                f'<span class="bz-gitem">{label} '
                f'<b class="{cls}">{chg:+.2f}%</b></span>')
        if stock_results:
            up, down, _ = breadth_counts(stock_results)
            glance_bits.append(
                f'<span class="bz-gitem">Breadth '
                f'<b class="up">{up}▲</b> '
                f'<b class="down">{down}▼</b></span>')
        macro = cached_macro()
        if isinstance(macro.get("vix"), (int, float)):
            # VIX up = fear up: color it red, the market convention.
            vchg = macro.get("vix_chg") or 0
            vcls = "down" if vchg > 0 else "up" if vchg < 0 else "flat"
            glance_bits.append(
                f'<span class="bz-gitem">VIX '
                f'<b class="{vcls}">{macro["vix"]:.2f}</b></span>')
        if isinstance(macro.get("yield10"), (int, float)):
            glance_bits.append(
                f'<span class="bz-gitem">10Y '
                f'<b>{macro["yield10"]:.2f}%</b></span>')
        if glance_bits:
            smd(
                f'<div class="bz-glance">{"".join(glance_bits)}</div>',
            )
        if not stock_results:
            st.warning("The scan came back empty — live quotes aren't "
                       "loading right now. Check Connections in the sidebar; "
                       "the board fills in once market data is flowing.")

        my_wl = watchlist_store.load_watchlist()
        if my_wl:
            section("", "My watchlist",
                    "Your tickers — ★ starred pin to the top.")
            for w in my_wl:
                res = cached_stock_scan(w["symbol"])
                if res:
                    watch_card({**res, "sector": "Watchlist"},
                               key_prefix=f"wl-{w['symbol']}-")
                else:
                    st.caption(f"{w['symbol']}: no data right now.")

            # Benchmark: equal-weighted watchlist vs SPY, rebased to 100.
            btf = (st.pills("Benchmark", ["1M", "6M", "YTD"], default="1M",
                            label_visibility="collapsed",
                            key="wl-bench-tf") or "1M")
            with st.spinner("Benchmarking your watchlist..."):
                bench = watchlist_benchmark(
                    [w["symbol"] for w in my_wl], btf)
            if bench:
                wl_pct, spy_pct, wl_rb, spy_rb = bench
                wl_cls = "up" if wl_pct >= spy_pct else "down"
                smd(
                    f'<div class="bz-bench">'
                    f'<span>Watchlist '
                    f'<b class="bz-bench-num {wl_cls}">'
                    f'{wl_pct:+.2f}%</b></span>'
                    f'<span class="bz-bench-vs">vs</span>'
                    f'<span>SPY <b class="bz-bench-num">'
                    f'{spy_pct:+.2f}%</b></span>'
                    f'<span class="bz-bench-tf">{btf}</span>'
                    f'</div>',
                )
                smd(
                    big_chart_svg(wl_rb, price_fmt=lambda c: f"{c:.1f}",
                                  compare=spy_rb, label="Watchlist",
                                  compare_label="SPY"),
                )
                st.caption("Equal-weighted, rebased to 100. "
                           "Research only.")
            else:
                st.caption("Not enough history to benchmark right now.")

            # Watchlist digest: on-demand AI, never auto-runs.
            if st.button("Generate watchlist digest", key="wl-digest-btn"):
                with st.spinner("Reading your watchlist..."):
                    items = []
                    for w in my_wl:
                        res = cached_stock_scan(w["symbol"])
                        if not res:
                            continue
                        q = res.get("quote") or {}
                        items.append({
                            "symbol": w["symbol"],
                            "price": q.get("price"),
                            "change_pct": q.get("change_percent"),
                            "headlines": [n.get("headline", "")
                                          for n in res.get("news", [])[:3]],
                        })
                    st.session_state["wl_digest"] = watchlist_digest(items)
            digest = st.session_state.get("wl_digest")
            if digest:
                with st.expander("Watchlist digest", expanded=True):
                    st.markdown(esc_dollar(digest))

        # Earnings: 7-day board up top, rest of the 30-day window below.
        section("", "Earnings this week",
                "Reports landing in the next 7 days — Eastern.")
        with st.spinner("Loading earnings dates..."):
            earnings = cached_earnings()
        universe_syms = {r["symbol"] for r in stock_results}
        et_today = datetime.now(ZoneInfo("America/New_York")).date()
        week, rest = group_earnings(earnings, universe_syms, et_today)
        if any(syms for _, syms in week):
            parts = []
            for d, syms in week:
                chip_html = []
                for s in syms:
                    name = config.COMPANY_NAMES.get(s)
                    if name:
                        label = (f'{html.escape(s)} '
                                 f'<span class="bz-econame">· '
                                 f'{html.escape(name)}</span>')
                    else:
                        label = html.escape(s)
                    chip_html.append(
                        f'<span class="bz-chip bz-echip">{label}</span>')
                chips = "".join(chip_html)
                if not chips:
                    chips = '<span class="bz-enone">—</span>'
                parts.append(
                    f'<div class="bz-eday"><div class="bz-eday-h">'
                    f"{html.escape(earnings_day_label(d, et_today))}</div>"
                    f'<div class="bz-echips">{chips}</div></div>')
            smd(f'<div class="bz-eweek">{"".join(parts)}</div>')
        else:
            st.caption("No reports this week for this universe.")
        if rest:
            n_rest = sum(len(s) for _, s in rest)
            with st.expander(f"Later this month — {n_rest} more",
                             expanded=False):
                rows = []
                for d, syms in rest:
                    delta = (d - et_today).days
                    for sym in syms:
                        rows.append(
                            f'<div class="bz-witem"><div class="bz-wsym">'
                            f"{html.escape(sym)}</div>"
                            f"<p>{fmt_earnings(d.strftime('%Y-%m-%d'))} "
                            f'<span class="gold">· in {delta} days</span>'
                            f"</p></div>")
                smd(f'<div class="bz-wire">{"".join(rows)}</div>')
        elif not any(syms for _, syms in week):
            st.caption("No earnings dates in the next 30 days "
                       "for this universe.")

        if stock_results:
            ticker_tape(stock_results)

        # 01 — watchlist
        section("01", "Watchlist", "Top movers in this universe right now.")
        for res in shown[:config.TOP_N]:
            watch_card(res)

        # 02 — why is it moving? (top 6 by |day change|, min 2%)
        # Auto-read: the AI line renders inline, no tap needed. Reads
        # are cached per symbol per day on disk, so repeat views cost
        # nothing and the spinner only works on the first load.
        movers = sorted(shown,
                        key=lambda r: abs(r["quote"]["change_percent"]),
                        reverse=True)
        movers = [r for r in movers
                  if abs(r["quote"]["change_percent"]) >= 2.0][:6]
        if movers:
            section("02", "Why is it moving?",
                    "Biggest day moves in this scan — AI read on "
                    "the headlines.")
            with st.spinner("Reading the headlines..."):
                reads = [(r, mover_explanation(r["symbol"], r["quote"],
                                               r.get("news", [])))
                         for r in movers]
            for r, text in reads:
                sym = r["symbol"]
                chg = r["quote"]["change_percent"]
                chg_cls = ("up" if chg > 0 else
                           "down" if chg < 0 else "flat")
                if text.startswith(DEGRADED_PREFIX):
                    line = "AI read unavailable right now."
                else:
                    line = text
                smd(
                    f'<div class="bz-why">'
                    f'<span class="bz-sym">{html.escape(sym)}</span>'
                    f'<span class="bz-chg {chg_cls}">'
                    f'{html.escape(fmt_change(chg))}</span>'
                    f'<p>{html.escape(line)}</p></div>',
                )

        # 03 — signal calibration
        section("03", "Signal calibration",
                "Do high scores precede green days? Descriptive only — "
                "the log grows with each day's scan. Not financial advice.")
        calibration.log_scan(stock_results)
        stats = calibration.summarize(min_score=70)
        if stats["count"]:
            st.caption(
                f"Scores ≥ 70: **{stats['count']}** samples • "
                f"{stats['positive_pct']:.0f}% positive • "
                f"avg day {stats['avg_change']:+.2f}% • "
                f"{stats['first_date']} → {stats['last_date']}")
        else:
            st.caption(
                "No scored samples yet — the log fills as scans run with "
                "live quotes. Note: this free host wipes the log whenever "
                "the app sleeps, so it restarts often.")

        # 04 — news wire
        section("04", "News wire", "Freshest headlines across the scan. "
                "The News tab has every story, per symbol.")
        news_wire(shown)

        # AI brief
        if shown:
            if st.button("AI Market Brief"):
                items = tuple(
                    (r["symbol"], r["quote"]["price"],
                     r["quote"]["change_percent"],
                     r["news"][0]["headline"] if r["news"] else "")
                    for r in shown[:12]
                )
                st.session_state["brief"] = cached_brief(items)
            brief = st.session_state.get("brief")
            if brief:
                with st.expander("Market Brief", expanded=True):
                    st.markdown(esc_dollar(brief))

        # 05 — sectors
        if shown and universe == "Everything 🌐":
            section("05", "Sectors today", "Average move per sector.")
            sector_board(sector_summary(shown))

        # 06 — heatmap
        section("06", "Heatmap", "Every symbol, colored by today's move.")
        heatmap(shown)

        if universe == "Everything":
            section("07", "All results", "The full scan table.")
            st.dataframe(
                [{
                    "Symbol": r["symbol"],
                    "Sector": r.get("sector", "Other"),
                    "Price": disp_price(r["quote"]["price"]),
                    "Change": fmt_change(r["quote"]["change_percent"]),
                    "Score": r["score"],
                } for r in shown],
                width="stretch",
            )

# --- News (expandable, per symbol) ---
with tab_news:
    with_news = [r for r in shown if r.get("news")]
    total_heads = sum(len(r["news"]) for r in with_news)
    section("", "News room",
            f"{total_heads} headlines across {len(with_news)} symbols "
            f"from the last 7 days. Newest first.")
    if not with_news:
        st.info("No headlines in this scan yet. Run a scan first.")
    else:
        # Top stories: the 10 freshest across everything
        fresh = []
        seen = set()
        for r in with_news:
            for n in r["news"]:
                head = (n.get("headline") or "").strip()
                if head and head not in seen:
                    seen.add(head)
                    fresh.append((n.get("timestamp") or 0, r["symbol"], n))
        fresh.sort(key=lambda x: x[0], reverse=True)
        st.subheader("Top stories")
        for ts, sym, n in fresh[:10]:
            head = html.escape(n["headline"])
            url = n.get("url") or ""
            link = (f'<a href="{html.escape(url)}" target="_blank">{head}</a>'
                    if url else head)
            pill = sentiment_mod.sentiment_pill(
                sentiment_mod.classify_sentiment(n.get("headline")))
            meta = " · ".join(x for x in [n.get("source") or "",
                                          time_ago(ts)] if x)
            smd(
                f"**{html.escape(sym)}** · {link}{pill}  \n"
                f"<small style='color:#aaa69a'>{html.escape(meta)}</small>",)
            if n.get("summary"):
                st.caption(n["summary"][:220])
        st.divider()
        # Per-symbol expanders, paginated: 24 symbols x ~8 stories each
        # is a lot of DOM on a phone, so load 8 symbols at a time.
        st.subheader("By symbol")
        news_page = st.session_state.get("news-sym-page", 1)
        visible_syms, remaining_syms = paginate(
            with_news, news_page, NEWS_SYMS_PER_PAGE)
        for r in visible_syms:
            sym = r["symbol"]
            chg = r["quote"]["change_percent"]
            with st.expander(
                    f"{dir_glyph(chg)} {sym} — "
                    f"{fmt_change(chg)} ({len(r['news'])} stories)",
                    expanded=False):
                for n in r["news"]:
                    head = html.escape(n["headline"])
                    url = n.get("url") or ""
                    pill = sentiment_mod.sentiment_pill(
                        sentiment_mod.classify_sentiment(n.get("headline")))
                    line = (f'- <a href="{html.escape(url)}" '
                            f'target="_blank">{head}</a>{pill}'
                            if url else f"- {head}{pill}")
                    smd(line)
                    meta = " · ".join(
                        x for x in [n.get("source") or "",
                                    time_ago(n.get("timestamp"))] if x)
                    if meta:
                        st.caption(meta)
                    if n.get("summary"):
                        st.caption(n["summary"][:220])
        if remaining_syms:
            if st.button(f"Show more symbols ({len(remaining_syms)} more)",
                         key="news-sym-more"):
                st.session_state["news-sym-page"] = news_page + 1
                st.rerun()

# --- PennyPulse ---
with tab_penny:
    section("01", "Penny filters",
            f"Price ≤ ${config.PENNY_MAX_PRICE:.2f}, "
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
            "Price": disp_price(q["price"]),
            "Change": fmt_change(q["change_percent"]),
            "Passes": "Yes" if ok else "No",
        })
    st.dataframe(rows, width="stretch")

# --- CryptoPulse ---
with tab_crypto:
    section("01", "Crypto watch", "Spot prices via Finnhub. "
            "Change is vs. prior close.")
    dom = cached_cg_dominance()
    if dom:
        smd(
            f'<div class="bz-glance">'
            f'<span class="bz-gitem">BTC dom '
            f'<b>{dom["btc"]:.1f}%</b></span>'
            f'<span class="bz-gitem">ETH dom '
            f'<b>{dom["eth"]:.1f}%</b></span>'
            f"</div>",
        )
    if st.button("Refresh crypto"):
        cached_universe_scan.clear()
    cg_sparks = {r["symbol"]: r["spark7"] for r in cached_cg_board()}
    crypto_results = cached_universe_scan(tuple(CRYPTO_MAP.values()))
    for res in crypto_results:
        base = res["symbol"].split(":")[-1].replace("USDT", "")
        watch_card({**res, "symbol": base, "sector": "Crypto"},
                   key_prefix="crypto-", spark=cg_sparks.get(base))

# --- Stackz (paper trading) ---
with tab_stackz:
    section("", "Stackz — paper trading",
            "Live snapshot from the Stackz paper-trading bot. "
            "Paper trading only — no real money. Research only.")
    snap = cached_stackz()
    if not snap or not stackz_mod.is_fresh(snap):
        st.caption("Paper-trading sync hasn't landed yet — it refreshes "
                   "after each Stackz run.")
    else:
        eq = stackz_mod.effective_equity(snap)
        pnl = stackz_mod.day_pnl_pct(snap)
        poss = stackz_mod.paper_positions(snap)
        trades = stackz_mod.recent_trades(snap, 10)
        ks_status, ks_pnl = stackz_mod.kill_switch(snap)
        age = stackz_mod.snapshot_age_minutes(snap)

        c1, c2, c3 = st.columns(3)
        c1.metric("Paper equity",
                  f"${eq:,.2f}" if isinstance(eq, (int, float)) else "—")
        c2.metric("Day P&L",
                  fmt_change(pnl) if isinstance(pnl, (int, float)) else "—")
        c3.metric("Open positions", str(len(poss)))

        ks_ok = (ks_status or "").upper() == "OK"
        dot = "#39ff88" if ks_ok else "#ff3b5c"
        ks_note = (f" · day {fmt_change(ks_pnl)}"
                   if isinstance(ks_pnl, (int, float)) else "")
        smd(f'<span style="display:inline-block;width:10px;height:10px;'
            f'border-radius:50%;background:{dot};margin-right:6px;"></span>'
            f'<b>Kill switch:</b> {html.escape(str(ks_status or "unknown"))}'
            f'{ks_note}')
        if isinstance(age, (int, float)):
            st.caption(f"Snapshot from {int(age)} min ago.")

        st.subheader("Positions")
        if not poss:
            st.caption("No open positions right now.")
        for p in poss:
            pnl_v = p.get("pnl")
            pnl_col = "#39ff88" if (pnl_v or 0) >= 0 else "#ff3b5c"

            def _usd(v):
                return f"${v:,.2f}" if isinstance(v, (int, float)) else "—"

            qty = (f"{p['qty']:.6g}"
                   if isinstance(p.get("qty"), (int, float)) else "—")
            smd(f'<div class="bz-witem"><div class="bz-wsym">'
                f'{html.escape(p["symbol"])}</div>'
                f'<p>{qty} @ {_usd(p.get("avg"))} → {_usd(p.get("last"))} · '
                f'<span style="color:{pnl_col}">'
                f'{stackz_mod.signed_dollars(pnl_v)}</span> · '
                f'stop {_usd(p.get("stop"))} / target {_usd(p.get("target"))}'
                f'</p></div>')

        st.subheader("Recent trades")
        if not trades:
            st.caption("No trades in this snapshot.")
        for t in trades:
            sym = html.escape(str(t.get("symbol") or "?"))
            side = html.escape(str(t.get("side") or "?").upper())
            strat = html.escape(str(t.get("strategy") or ""))
            price = (f"${t['price']:,.2f}"
                     if isinstance(t.get("price"), (int, float)) else "—")
            rpnl = stackz_mod.signed_dollars(t.get("realized_pnl"))
            reason = html.escape(str(t.get("reason") or ""))
            smd(f'<div class="bz-witem"><div class="bz-wsym">{sym} {side}'
                f'</div><p>{stackz_time_et(t.get("time"))} · {price} · '
                f'{strat} · realized {rpnl}</p>'
                f'<p>{reason}</p></div>')

# --- Bot City ---
with tab_city:
    section("", "Bot City — paper strategies as a skyline",
            "Each tower is a strategy; height is closed trades. "
            "Paper trading only — no real money.")
    snap = cached_stackz()
    if not snap or not stackz_mod.is_fresh(snap):
        st.caption("Paper-trading sync hasn't landed yet — the city "
                   "appears after the next Stackz run.")
    else:
        city_doc = bot_city_html(snap)
        if not city_doc:
            st.caption("No paper trades in this snapshot yet — the city "
                       "appears after the first closes.")
        else:
            st.components.v1.html(city_doc, height=780, scrolling=False)

# --- Screener ---
with tab_screener:
    section("", "Screener",
            "Filter this scan's results — no rescan needed. "
            "Passing a filter is not a buy signal.")
    if not stock_results:
        st.caption("Run a scan first — the screener filters the latest "
                   "results.")
    else:
        f1, f2 = st.columns(2)
        pmin = f1.number_input("Min price", min_value=0.0, value=0.0,
                               step=1.0, key="scr-pmin")
        pmax = f2.number_input("Max price", min_value=0.0, value=0.0,
                               step=1.0, key="scr-pmax", help="0 = no cap")
        min_move = st.slider("Min |day %|", 0.0, 20.0, 0.0, 0.5,
                             key="scr-move")
        min_score = st.slider("Min score", 0, 100, 0, key="scr-score")
        sector = st.selectbox("Sector", ["All"] + list(config.SECTORS),
                              key="scr-sector")
        sort_by = st.radio("Sort by", ["Score", "Day %"], horizontal=True,
                           key="scr-sort")
        rows = screener_mod.apply_filters(
            stock_results,
            price_min=pmin or None,
            price_max=pmax or None,
            min_abs_change=min_move,
            sector=sector,
            min_score=min_score)
        rows = screener_mod.sort_results(
            rows, sort_by="change" if sort_by == "Day %" else "score")
        if not rows:
            st.caption("No matches — loosen the filters.")
        else:
            st.caption(f"{len(rows)} matches.")
            st.dataframe(
                [{
                    "Symbol": r["symbol"],
                    "Sector": r.get("sector", "Other"),
                    "Price": disp_price(r["quote"]["price"]),
                    "Change": fmt_change(r["quote"]["change_percent"]),
                    "Score": r["score"],
                } for r in rows],
                width="stretch",
            )

st.divider()
st.caption("Bandz Terminal • Data: Finnhub + Yahoo (charts) • "
           "Explanations: Gemini • Not financial advice.")
