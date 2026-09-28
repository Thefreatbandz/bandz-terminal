"""Alerts: storage helpers.

Alerts live in alerts.json next to this file. Three types:

  price:   {"id", "type": "price", "symbol": "NVDA", "pct": 3.0,
            "baseline": 187.5 | null, "created": ...}
           Fires when |move| vs baseline reaches pct, then re-arms.
           (Legacy alerts without "type" are treated as price alerts.)

  pct:     {"id", "type": "pct", "symbol": "NVDA", "threshold": 3.0,
            "last_fired": "2026-09-28" | null, "created": ...}
           Fires when |day change| >= threshold. Fires at most once per
           day so the 30-min cron doesn't spam.

  keyword: {"id", "type": "keyword", "keyword": "FDA",
            "seen": ["NVDA|headline..."], "created": ...}
           Fires when a fresh headline in the scanned news contains the
           keyword. Notifies once per headline.

The web dashboard manages these; check_alerts.py (run by cron) fires them.
"""

import json
import os
import uuid
from datetime import datetime, timezone

ALERTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "alerts.json")


def load_alerts(path=ALERTS_FILE):
    try:
        with open(path) as f:
            data = json.load(f)
        alerts = data.get("alerts", [])
        return [a for a in alerts if a.get("id")]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_alerts(alerts, path=ALERTS_FILE):
    with open(path, "w") as f:
        json.dump({"alerts": alerts}, f, indent=2)


def add_alert(symbol, pct, path=ALERTS_FILE):
    """Add a price-move alert. Returns the new alert dict, or None if invalid."""
    symbol = (symbol or "").strip().upper()
    try:
        pct = float(pct)
    except (TypeError, ValueError):
        return None
    if not symbol or pct <= 0:
        return None
    alerts = load_alerts(path)
    if any(a.get("type", "price") == "price" and a.get("symbol") == symbol
           and a.get("pct") == pct for a in alerts):
        return None
    alert = {
        "id": uuid.uuid4().hex[:8],
        "type": "price",
        "symbol": symbol,
        "pct": pct,
        "baseline": None,
        "created": datetime.now(timezone.utc).isoformat(),
    }
    alerts.append(alert)
    save_alerts(alerts, path)
    return alert


def add_pct_alert(symbol, threshold, path=ALERTS_FILE):
    """Add a day-change-% alert. Fires at most once per day."""
    symbol = (symbol or "").strip().upper()
    try:
        threshold = float(threshold)
    except (TypeError, ValueError):
        return None
    if not symbol or threshold <= 0:
        return None
    alerts = load_alerts(path)
    if any(a.get("type") == "pct" and a.get("symbol") == symbol
           and a.get("threshold") == threshold for a in alerts):
        return None
    alert = {
        "id": uuid.uuid4().hex[:8],
        "type": "pct",
        "symbol": symbol,
        "threshold": threshold,
        "last_fired": None,
        "created": datetime.now(timezone.utc).isoformat(),
    }
    alerts.append(alert)
    save_alerts(alerts, path)
    return alert


def add_keyword_alert(keyword, path=ALERTS_FILE):
    """Add a news-keyword alert. Returns the alert, or None if invalid."""
    keyword = (keyword or "").strip()
    if len(keyword) < 2:
        return None
    alerts = load_alerts(path)
    if any(a.get("type") == "keyword"
           and (a.get("keyword") or "").lower() == keyword.lower()
           for a in alerts):
        return None
    alert = {
        "id": uuid.uuid4().hex[:8],
        "type": "keyword",
        "keyword": keyword,
        "seen": [],
        "created": datetime.now(timezone.utc).isoformat(),
    }
    alerts.append(alert)
    save_alerts(alerts, path)
    return alert


def remove_alert(alert_id, path=ALERTS_FILE):
    alerts = load_alerts(path)
    kept = [a for a in alerts if a["id"] != alert_id]
    if len(kept) != len(alerts):
        save_alerts(kept, path)
        return True
    return False
