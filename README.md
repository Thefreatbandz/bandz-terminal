# ⚡ Bandz Terminal

A dark, terminal-style stock market dashboard. 174 tickers across 12 sectors with a sector heatmap, ticker tape, index strip (SPY/QQQ/DIA/IWM), market-status badge, sparklines, AI market brief, 52-week range bars, earnings dates, insider activity, sidebar price alerts, multi-timeframe charts (1D–1Y) with a compare overlay, a results screener, an on-demand AI watchlist digest, and a Stackz paper-trading tab.

> **Disclaimer:** For research and education only — not financial advice.

## Local setup

```bash
# Python 3.10+
python -m venv ~/workspace/venvs/marketpulse
~/workspace/venvs/marketpulse/bin/pip install -r requirements.txt

# Add your keys (never commit this file — it's gitignored)
cp .env.example .env
# edit .env and paste your FINNHUB_API_KEY and GEMINI_API_KEY
```

Run the dashboard:

```bash
~/workspace/venvs/marketpulse/bin/streamlit run web.py
```

Run the tests:

```bash
~/workspace/venvs/marketpulse/bin/python -m pytest
```

## Price alerts

Set alerts in the dashboard sidebar. A scheduled checker (`check_alerts.py`, every
15 minutes on weekdays 9:00a–4:30p ET) arms a baseline on first successful quote
and fires when the price moves the configured % from baseline.

## Scheduled scripts

- `scripts/morning_brief.py` — weekday 8:30 AM ET briefing: top gainers/losers, today's earnings, one AI brief.
- `scripts/evening_recap.py` — weekday 6:30 PM ET recap: biggest movers, today's + tomorrow's earnings, one AI recap paragraph.

Both follow the same stdout contract as `check_alerts.py`: `MARKET_CLOSED` / `NO_ALERTS` / `TRIGGERED:` lines.

## Deploy to Streamlit Community Cloud (free)

1. Push this repo to GitHub (`.env` is gitignored — it will not be committed).
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app → connect the repo.
3. Set the main file to `web.py`.
4. In the app's **Secrets** settings, add:
   ```toml
   FINNHUB_API_KEY = "your-fresh-key"
   GEMINI_API_KEY = "your-fresh-key"
   ```
5. Deploy — then open the app URL on your phone.

**Rotate both API keys before going public** if they were ever pasted anywhere
(e.g. chat). Generate fresh keys from Finnhub and Google AI Studio, and store
them only in the host's secret manager — never in the repo.
