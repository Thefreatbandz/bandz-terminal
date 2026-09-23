"""Price alerts: storage helpers.

Alerts live in alerts.json next to this file:
  {"alerts": [{"id": ..., "symbol": "NVDA", "pct": 3.0,
               "baseline": 187.5 | null, "created": "2026-09-22T..."}]}

baseline is null until the first check arms it. When |move| vs baseline
reaches pct, the checker fires and re-arms at the new price.

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
        return [a for a in alerts if a.get("symbol") and a.get("pct")]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_alerts(alerts, path=ALERTS_FILE):
    with open(path, "w") as f:
        json.dump({"alerts": alerts}, f, indent=2)


def add_alert(symbol, pct, path=ALERTS_FILE):
    """Add an alert. Returns the new alert dict, or None if invalid."""
    symbol = (symbol or "").strip().upper()
    try:
        pct = float(pct)
    except (TypeError, ValueError):
        return None
    if not symbol or pct <= 0:
        return None
    alerts = load_alerts(path)
    if any(a["symbol"] == symbol and a["pct"] == pct for a in alerts):
        return None
    alert = {
        "id": uuid.uuid4().hex[:8],
        "symbol": symbol,
        "pct": pct,
        "baseline": None,
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
