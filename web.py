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
import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import aiohttp
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from marketpulse import alerts as alert_store
from marketpulse import cache, calibration, config
from marketpulse import sentiment as sentiment_mod
from marketpulse.ai import (generate_ai_analysis, generate_market_brief,
                            generate_mover_explanation)
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


# ---------------- blotter styling ----------------

st.markdown("""
<style>
/* CYBERTECH theme -- neon cyan/magenta HUD on near-black */
.block-container { padding-top: 1rem; max-width: 1100px; }
.up { color: #39ff88; } .down { color: #ff3b5c; }
.flat { color: #8b93a7; } .gold { color: #00e5ff; }

/* backdrop: faint neon grid */
.stApp { background-color: #04060c;
  background-image:
    linear-gradient(rgba(0,229,255,0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,229,255,0.05) 1px, transparent 1px);
  background-size: 44px 44px; }
[data-testid="stSidebar"] { background-color: #060a12; }
[data-testid="stHeader"] { background-color: rgba(4,6,12,0); }

/* command strip */
.bz-strip { display: flex; align-items: center; gap: 10px;
  background: rgba(6,12,22,0.9); border: 1px solid rgba(0,229,255,0.4);
  padding: 10px 16px; margin-bottom: 10px;
  box-shadow: 0 0 20px rgba(0,229,255,0.14), inset 0 0 28px rgba(0,229,255,0.05);
  clip-path: polygon(0 0, calc(100% - 16px) 0, 100% 16px,
                     100% 100%, 16px 100%, 0 calc(100% - 16px)); }
.bz-title { font-family: monospace; font-size: 16px; font-weight: 800;
  letter-spacing: 2px; color: #00e5ff; white-space: nowrap;
  text-shadow: 0 0 14px rgba(0,229,255,0.9); }
.bz-badge { font-family: monospace; font-size: 10px; font-weight: 700;
  letter-spacing: 1px; padding: 4px 10px; border-radius: 3px;
  white-space: nowrap; }
.bz-badge.open { color: #39ff88; background: rgba(57,255,136,0.08);
  border: 1px solid rgba(57,255,136,0.5);
  box-shadow: 0 0 10px rgba(57,255,136,0.25); }
.bz-badge.shut { color: #ff3b5c; background: rgba(255,59,92,0.08);
  border: 1px solid rgba(255,59,92,0.5);
  box-shadow: 0 0 10px rgba(255,59,92,0.25); }
.bz-disc { color: #8b93a7; font-size: 11px; margin: 0 0 10px 2px; }

/* index strip */
.bz-idx { display: grid; grid-template-columns: repeat(4, 1fr);
  gap: 8px; margin: 0 0 10px 0; }
.bz-idxc { background: rgba(6,12,22,0.9);
  border: 1px solid rgba(0,229,255,0.28);
  padding: 8px 6px; text-align: center;
  box-shadow: inset 0 0 18px rgba(0,229,255,0.05);
  clip-path: polygon(0 0, calc(100% - 10px) 0, 100% 10px,
                     100% 100%, 10px 100%, 0 calc(100% - 10px)); }
.bz-idxc .s { font-family: monospace; font-size: 10px; font-weight: 700;
  color: #8b93a7; letter-spacing: 2px; }
.bz-idxc .p { font-family: monospace; font-size: 15px; font-weight: 700;
  margin-top: 4px; font-variant-numeric: tabular-nums; color: #e8f6ff; }
.bz-idxc .c { font-family: monospace; font-size: 11px; font-weight: 700;
  margin-top: 2px; }

/* ticker tape: neon news ticker */
.tape-wrap { overflow: hidden; white-space: nowrap;
  border-top: 1px solid rgba(255,43,214,0.55);
  border-bottom: 1px solid rgba(255,43,214,0.55);
  background: rgba(255,43,214,0.04);
  padding: 7px 0; margin-bottom: 6px; }
.tape-inner { display: inline-block; animation: tape-scroll 45s linear infinite; }
@keyframes tape-scroll { from { transform: translateX(0); }
  to { transform: translateX(-50%); } }
.tape-item { font-family: monospace; font-size: 13px; margin-right: 26px;
  color: #ffd7f4; text-shadow: 0 0 8px rgba(255,43,214,0.6); }

/* numbered sections */
.bz-sec { display: flex; align-items: center; gap: 12px; margin: 26px 0 4px; }
.bz-num { display: grid; place-items: center; width: 30px; height: 30px;
  background: rgba(0,229,255,0.1); color: #00e5ff;
  border: 1px solid rgba(0,229,255,0.6);
  box-shadow: 0 0 12px rgba(0,229,255,0.35);
  font-family: monospace; font-size: 11px; font-weight: 800; flex: none;
  clip-path: polygon(0 0, calc(100% - 8px) 0, 100% 8px,
                     100% 100%, 8px 100%, 0 calc(100% - 8px)); }
.bz-sec h2 { margin: 0; font-size: 19px; letter-spacing: 1px;
  font-family: monospace; color: #e8f6ff;
  text-shadow: 0 0 10px rgba(0,229,255,0.35); }
.bz-sub { color: #8b93a7; font-size: 12px; margin: 4px 0 14px 42px; }

/* watch cards: HUD panels */
.bz-card { background: linear-gradient(180deg, rgba(10,18,32,0.95),
            rgba(5,9,18,0.95));
  border: 1px solid rgba(0,229,255,0.28); padding: 16px; margin-bottom: 12px;
  box-shadow: 0 0 22px rgba(0,229,255,0.10), inset 0 0 30px rgba(0,229,255,0.04);
  clip-path: polygon(0 0, calc(100% - 20px) 0, 100% 20px,
                     100% 100%, 20px 100%, 0 calc(100% - 20px)); }
.bz-top { display: flex; justify-content: space-between; align-items: center; }
.bz-sym { font-family: monospace; font-size: 16px; font-weight: 800;
  letter-spacing: 1px; color: #e8f6ff;
  text-shadow: 0 0 10px rgba(0,229,255,0.5); }
.bz-chip { font-family: monospace; font-size: 9px; font-weight: 700;
  color: #00e5ff; border: 1px solid rgba(0,229,255,0.45);
  padding: 3px 8px; margin-left: 8px; text-transform: uppercase;
  letter-spacing: 1px; vertical-align: 2px; background: rgba(0,229,255,0.06); }
.bz-chg { font-family: monospace; font-size: 15px; font-weight: 800;
  padding: 5px 10px; }
.bz-chg.up { color: #39ff88; background: rgba(57,255,136,0.10);
  border: 1px solid rgba(57,255,136,0.45);
  box-shadow: 0 0 12px rgba(57,255,136,0.25); }
.bz-chg.down { color: #ff3b5c; background: rgba(255,59,92,0.10);
  border: 1px solid rgba(255,59,92,0.45);
  box-shadow: 0 0 12px rgba(255,59,92,0.25); }
.bz-chg.flat { color: #8b93a7; background: rgba(139,147,167,0.10);
  border: 1px solid rgba(139,147,167,0.4); }
.bz-price { font-family: monospace; font-size: 32px; font-weight: 800;
  letter-spacing: -1px; margin-top: 10px; color: #ffffff;
  font-variant-numeric: tabular-nums;
  text-shadow: 0 0 16px rgba(0,229,255,0.45); }
.bz-spark { width: 100%; height: 60px; margin-top: 10px;
  background: rgba(0,10,20,0.7); border: 1px solid rgba(0,229,255,0.15);
  display: block; }
.bz-label { display: block; color: #8b93a7; font-family: monospace;
  font-size: 9px; font-weight: 700; letter-spacing: 2px; margin-top: 12px; }
.bz-bar { height: 6px; background: #0d1626; border-radius: 3px;
  margin-top: 6px; overflow: hidden;
  border: 1px solid rgba(0,229,255,0.15); }
.bz-bar > div { height: 100%; border-radius: 3px;
  box-shadow: 0 0 8px rgba(0,229,255,0.7); }
.bz-meta { color: #8b93a7; font-family: monospace; font-size: 11px;
  margin-top: 10px; line-height: 1.7; }
.bz-news { margin-top: 12px; border-top: 1px solid rgba(255,43,214,0.3);
  padding-top: 10px; }
.bz-news .bz-item { margin-bottom: 8px; }
.bz-news a { color: #e8f6ff; font-size: 13px; line-height: 1.5;
  text-decoration: none; }
.bz-news a:hover { color: #00e5ff; text-shadow: 0 0 8px rgba(0,229,255,0.6); }
.bz-src { display: block; color: #8b93a7; font-family: monospace;
  font-size: 10px; font-weight: 600; margin-top: 3px; }

/* news wire */
.bz-wire { border: 1px solid rgba(0,229,255,0.28);
  background: rgba(6,12,22,0.9); overflow: hidden;
  box-shadow: 0 0 18px rgba(0,229,255,0.08); }
.bz-witem { display: grid; grid-template-columns: 60px 1fr; gap: 10px;
  padding: 12px 14px; border-bottom: 1px solid rgba(0,229,255,0.12); }
.bz-witem:last-child { border-bottom: 0; }
.bz-witem:hover { background: rgba(0,229,255,0.05); }
.bz-wsym { color: #00e5ff; font-family: monospace; font-size: 11px;
  font-weight: 800; line-height: 1.5;
  text-shadow: 0 0 8px rgba(0,229,255,0.7); }
.bz-witem p { margin: 0; font-size: 12.5px; line-height: 1.45; color: #e8f6ff; }
.bz-witem p a { color: #e8f6ff; text-decoration: none; }
.bz-witem p a:hover { color: #00e5ff; }
.bz-witem small { color: #8b93a7; font-family: monospace; font-size: 10px;
  font-weight: 600; }

/* heatmap */
.heat { display: grid; grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
  gap: 6px; margin: 8px 0 16px 0; }
.tile { padding: 10px 4px; text-align: center; font-family: monospace;
  border: 1px solid rgba(0,229,255,0.18); }
.tile b { display: block; font-size: 14px; color: #e8f6ff; }
.tile span { font-size: 12px; }
.heat-label { font-family: monospace; font-size: 11px; color: #00e5ff;
  margin: 12px 0 2px 0; letter-spacing: 2px; text-transform: uppercase;
  text-shadow: 0 0 8px rgba(0,229,255,0.5); }

/* streamlit controls: neon */
[data-testid="stBaseButton-primary"] { background: #00e5ff !important;
  color: #04060c !important; font-weight: 800 !important;
  border: none !important; border-radius: 4px !important;
  box-shadow: 0 0 18px rgba(0,229,255,0.5) !important;
  clip-path: polygon(0 0, calc(100% - 10px) 0, 100% 10px,
                     100% 100%, 10px 100%, 0 calc(100% - 10px)); }
[data-testid="stBaseButton-secondary"] { background: transparent !important;
  color: #00e5ff !important; border: 1px solid rgba(0,229,255,0.5) !important;
  border-radius: 4px !important; }
[data-testid="stExpander"] { border: 1px solid rgba(0,229,255,0.25) !important;
  background: rgba(6,12,22,0.85) !important; border-radius: 4px !important; }
[data-testid="stTabs"] button[aria-selected="true"] { color: #00e5ff !important;
  text-shadow: 0 0 10px rgba(0,229,255,0.7); }
a { color: #00e5ff !important; }
a:hover { text-shadow: 0 0 8px rgba(0,229,255,0.6); }
</style>
""", unsafe_allow_html=True)


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


def spark_svg(closes, w=320, h=56):
    """Tiny hand-rolled sparkline -- no widget weight, blotter style."""
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
    color = "#39ff88" if closes[-1] >= closes[0] else "#ff3b5c"
    return (
        f'<svg class="bz-spark" viewBox="0 0 {w} {h}" '
        f'preserveAspectRatio="none"><polyline points="{" ".join(pts)}" '
        f'fill="none" stroke="{color}" stroke-width="2"/></svg>'
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


def market_is_open():
    et = datetime.now(ZoneInfo("America/New_York"))
    mins = et.hour * 60 + et.minute
    return et.weekday() < 5 and 570 <= mins < 960


def session_label():
    """Pre-market / after-hours framing for the stock tab."""
    et = datetime.now(ZoneInfo("America/New_York"))
    mins = et.hour * 60 + et.minute
    if et.weekday() >= 5:
        return "Weekend — showing last close 🌙"
    if mins < 240:
        return "Overnight — showing last close 🌙"
    if mins < 570:
        return "Pre-market movers 🌅"
    if mins >= 960:
        return "After-hours movers 🌙"
    return None


def section(num, title, sub=""):
    st.markdown(
        f'<div class="bz-sec"><span class="bz-num">{num}</span>'
        f"<h2>{html.escape(title)}</h2></div>",
        unsafe_allow_html=True,
    )
    if sub:
        st.markdown(f'<div class="bz-sub">{html.escape(sub)}</div>',
                    unsafe_allow_html=True)


def command_strip():
    is_open = market_is_open()
    badge = ("open\">🟢 MARKET OPEN" if is_open
             else "shut\">🔴 MARKET CLOSED")
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
            f'<div class="p">{fmt_price(q["price"])}</div>'
            f'<div class="c {cls}">{fmt_change(chg)}</div></div>'
        )
    st.markdown(f'<div class="bz-idx">{"".join(cards)}</div>',
                unsafe_allow_html=True)


def ticker_tape(results):
    """Scrolling marquee of every scanned symbol."""
    items = []
    for r in results:
        chg = r["quote"]["change_percent"]
        cls = "up" if chg > 0 else "down" if chg < 0 else "flat"
        items.append(
            f'<span class="tape-item"><b>{html.escape(r["symbol"])}</b> '
            f'<span class="{cls}">{chg:+.2f}%</span></span>'
        )
    half = "".join(items)
    st.markdown(f'<div class="tape-wrap"><div class="tape-inner">'
                f"{half}{half}</div></div>", unsafe_allow_html=True)


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
    st.markdown("".join(rows), unsafe_allow_html=True)


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
                f"<b>{html.escape(r['symbol'])}</b>"
                f'<span class="{cls}">{chg:+.2f}%</span></div>'
            )
        parts.append(
            f'<div class="heat-label">{html.escape(sector)}</div>'
            f'<div class="heat">{"".join(tiles)}</div>'
        )
    st.markdown("".join(parts), unsafe_allow_html=True)


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
    st.markdown(f'<div class="bz-wire">{body}</div>', unsafe_allow_html=True)


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


async def _yahoo_closes(session, symbol):
    """Sparkline closes via Yahoo's free chart API (no key).

    Fallback for when the Finnhub plan doesn't cover /stock/candle.
    """
    if ":" in symbol:  # "BINANCE:BTCUSDT" -> "BTC-USD"
        ysym = symbol.split(":")[-1].replace("USDT", "-USD")
    else:
        ysym = symbol
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}"
    try:
        async with session.get(
            url,
            params={"interval": "5m", "range": "1d"},
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
        return [float(c) for c in closes if isinstance(c, (int, float))]
    except Exception:
        return []


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


@st.cache_data(ttl=86400, show_spinner=False)
def cached_recommendation(symbol):
    """Analyst consensus for a card pill. None when the endpoint is blocked."""
    async def _go():
        async with aiohttp.ClientSession(trust_env=True) as session:
            client = FinnhubClient(session)
            return await client.recommendation(symbol)
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

def watch_card(result, key_prefix=""):
    """One watched asset, blotter style: price, spark, score, news."""
    quote = result["quote"]
    symbol = result["symbol"]
    price, change = quote["price"], quote["change_percent"]
    score = result["score"]
    chg_cls = "up" if change > 0 else "down" if change < 0 else "flat"

    closes = cached_candles(symbol)
    spark = spark_svg(closes)

    hi52, lo52 = cached_52w(symbol)
    range_html = ""
    if hi52 and lo52 and hi52 > lo52:
        pos = max(0.0, min(1.0, (price - lo52) / (hi52 - lo52)))
        range_html = (
            f'<span class="bz-label">52W ${lo52:.2f} – ${hi52:.2f} · '
            f"AT {pos:.0%}</span>"
            f'<div class="bz-bar"><div style="width:{pos * 100:.0f}%;'
            f'background:#00e5ff;"></div></div>'
        )

    meta_lines = []
    edate = cached_earnings().get(symbol)
    if edate:
        meta_lines.append(f"📅 Earnings {fmt_earnings(edate)}")
    ins = cached_insider(symbol)
    if ins:
        t = ins[0]
        px = (f" @ ${t['price']:.2f}"
              if isinstance(t["price"], (int, float)) else "")
        meta_lines.append(
            f"🧑‍💼 {html.escape(t['name'].split(',')[0])} "
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
        news_html = (
            f'<div class="bz-news"><span class="bz-label" '
            f'style="margin-top:0;">NEWS</span>{items_html}</div>'
        )
    else:
        news_html = ('<div class="bz-news"><span class="bz-src">'
                     "No fresh news retrieved.</span></div>")

    reco = cached_recommendation(symbol)
    reco_html = ""
    if reco:
        reco_html = (
            f'<span class="bz-chip">{html.escape(reco["label"])} · '
            f'{reco["analysts"]}</span>')

    st.markdown(
        f'<div class="bz-card">'
        f'<div class="bz-top"><div>'
        f'<span class="bz-sym">{move_emoji(change)} '
        f"{html.escape(symbol)}</span>"
        f'<span class="bz-chip">{html.escape(result.get("sector", "Other"))}'
        f"</span>{reco_html}</div>"
        f'<div class="bz-chg {chg_cls}">{fmt_change(change)}</div></div>'
        f'<div class="bz-price">{fmt_price(price)}</div>'
        f"{spark}"
        f'<span class="bz-label">SCORE {score}/100 · '
        f"{html.escape(score_band(score)).upper()}</span>"
        f'<div class="bz-bar"><div style="width:{min(score, 100)}%;'
        f'background:#00e5ff;"></div></div>'
        f"{range_html}{meta_html}{news_html}"
        f"</div>",
        unsafe_allow_html=True,
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
                    st.markdown(line, unsafe_allow_html=True)
                    meta = " · ".join(
                        x for x in [item.get("source") or "",
                                    time_ago(item.get("timestamp"))] if x)
                    if meta:
                        st.caption(meta)
    with c2:
        btn_key = f"{key_prefix}explain-{symbol}"
        if st.button("🤖 Explain", key=btn_key):
            with st.spinner("Asking Gemini..."):
                st.session_state[f"analysis-{symbol}"] = explain(
                    symbol, quote, news)
    analysis = st.session_state.get(f"analysis-{symbol}")
    if analysis:
        st.markdown(analysis)


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

command_strip()

missing = config.missing_keys()
if missing:
    st.error(f"Missing API keys: {', '.join(missing)}. "
             "Copy .env.example to .env and fill it in.")
    st.stop()

index_strip()

tab_stocks, tab_news, tab_penny, tab_crypto = st.tabs(
    ["🔥 Stocks", "📰 News", "🟣 Penny", "🪙 Crypto"])

# --- shared stock scan (MarketPulse + News tabs) ---
news_top_n = None
scan_delay = None
if universe == "Custom":
    symbols = tuple(s.strip().upper() for s in custom.split(",") if s.strip())
elif universe == "Everything 🌐":
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
if universe == "Everything 🌐":
    sector_filter = st.selectbox("Sector", ["All"] + list(config.SECTORS))
shown = [r for r in stock_results
         if sector_filter == "All" or r.get("sector") == sector_filter]

# --- MarketPulse ---
with tab_stocks:
    if st.button("🔄 Run scan", type="primary"):
        cached_universe_scan.clear()

    if not symbols:
        st.info("Enter at least one symbol.")
    else:
        label = session_label()
        if label:
            st.caption(f"{label} Quotes reflect extended-hours trading.")
        st.caption(
            f"Last scan {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')} • "
            f"{len(stock_results)} results • showing top {config.TOP_N}")

        if stock_results:
            ticker_tape(stock_results)

        # 01 — watchlist
        section("01", "Watchlist", "Top movers in this universe right now.")
        for res in shown[:config.TOP_N]:
            watch_card(res)

        # 02 — why is it moving? (top 6 by |day change|, min 2%)
        movers = sorted(shown,
                        key=lambda r: abs(r["quote"]["change_percent"]),
                        reverse=True)
        movers = [r for r in movers
                  if abs(r["quote"]["change_percent"]) >= 2.0][:6]
        if movers:
            section("02", "Why is it moving?",
                    "Biggest |day moves| in this scan — tap for a 1-2 "
                    "sentence AI read on the headlines.")
            for r in movers:
                sym = r["symbol"]
                chg = r["quote"]["change_percent"]
                with st.expander(f"❓ {sym} ({chg:+.2f}%) — why?"):
                    key = f"why-{sym}"
                    if st.button("Ask Gemini", key=f"{key}-btn"):
                        with st.spinner("Reading the headlines..."):
                            st.session_state[key] = mover_explanation(
                                sym, r["quote"], r.get("news", []))
                    if st.session_state.get(key):
                        st.markdown(st.session_state[key])

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
            st.caption("No scored samples yet — check back after more scans.")

        # 04 — news wire
        section("04", "News wire", "Freshest headlines across the scan. "
                "The 📰 News tab has every story, per symbol.")
        news_wire(shown)

        # AI brief
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

        # 05 — sectors
        if shown and universe == "Everything 🌐":
            section("05", "Sectors today", "Average move per sector.")
            sector_board(sector_summary(shown))

        # 06 — heatmap
        section("06", "Heatmap", "Every symbol, colored by today's move.")
        heatmap(shown)

        if universe == "Everything 🌐":
            section("07", "All results", "The full scan table.")
            st.dataframe(
                [{
                    "Symbol": r["symbol"],
                    "Sector": r.get("sector", "Other"),
                    "Price": fmt_price(r["quote"]["price"]),
                    "Change": fmt_change(r["quote"]["change_percent"]),
                    "Score": r["score"],
                } for r in shown],
                width="stretch",
            )

# --- News (expandable, per symbol) ---
with tab_news:
    with_news = [r for r in shown if r.get("news")]
    total_heads = sum(len(r["news"]) for r in with_news)
    section("📰", "News room",
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
            st.markdown(
                f"**{html.escape(sym)}** · {link}{pill}  \n"
                f"<small style='color:#aaa69a'>{html.escape(meta)}</small>",
                unsafe_allow_html=True)
            if n.get("summary"):
                st.caption(n["summary"][:220])
        st.divider()
        # Per-symbol expanders
        st.subheader("By symbol")
        for r in with_news:
            sym = r["symbol"]
            chg = r["quote"]["change_percent"]
            with st.expander(
                    f"{move_emoji(chg)} {sym} — "
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
                    st.markdown(line, unsafe_allow_html=True)
                    meta = " · ".join(
                        x for x in [n.get("source") or "",
                                    time_ago(n.get("timestamp"))] if x)
                    if meta:
                        st.caption(meta)
                    if n.get("summary"):
                        st.caption(n["summary"][:220])

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
            "Price": fmt_price(q["price"]),
            "Change": fmt_change(q["change_percent"]),
            "Passes": "✅" if ok else "❌",
        })
    st.dataframe(rows, width="stretch")

# --- CryptoPulse ---
with tab_crypto:
    section("01", "Crypto watch", "Spot prices via Finnhub. "
            "Change is vs. prior close.")
    if st.button("🔄 Refresh crypto"):
        cached_universe_scan.clear()
    crypto_results = cached_universe_scan(tuple(CRYPTO_MAP.values()))
    for res in crypto_results:
        base = res["symbol"].split(":")[-1].replace("USDT", "")
        watch_card({**res, "symbol": base, "sector": "Crypto"},
                   key_prefix="crypto-")

st.divider()
st.caption("Bandz Terminal • Data: Finnhub + Yahoo (charts) • "
           "Explanations: Gemini • Not financial advice.")
