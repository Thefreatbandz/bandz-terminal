"""Custom watchlist: user-added tickers with star/favorite pins.

Stored in marketpulse/watchlist.json (gitignored).
Entry: {"symbol": "NVDA", "starred": False, "added": "2026-09-28T..."}.

Validation (does the symbol actually quote?) happens in the caller,
which has the API client -- this module is pure storage.
"""

import json
import os
from datetime import datetime, timezone

WATCHLIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "watchlist.json")


def load_watchlist(path=WATCHLIST_FILE):
    """Return the watchlist entries, starred first."""
    try:
        with open(path) as f:
            data = json.load(f)
        items = data.get("watchlist", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    items = [i for i in items if i.get("symbol")]
    items.sort(key=lambda i: (not i.get("starred"), i["symbol"]))
    return items


def save_watchlist(items, path=WATCHLIST_FILE):
    with open(path, "w") as f:
        json.dump({"watchlist": items}, f, indent=2)


def _raw(path):
    try:
        with open(path) as f:
            return json.load(f).get("watchlist", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def add_symbol(symbol, path=WATCHLIST_FILE):
    """Add a ticker. Returns the entry, or None if blank/duplicate."""
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return None
    items = _raw(path)
    if any(i.get("symbol") == symbol for i in items):
        return None
    entry = {"symbol": symbol, "starred": False,
             "added": datetime.now(timezone.utc).isoformat()}
    items.append(entry)
    save_watchlist(items, path)
    return entry


def remove_symbol(symbol, path=WATCHLIST_FILE):
    symbol = (symbol or "").strip().upper()
    items = _raw(path)
    kept = [i for i in items if i.get("symbol") != symbol]
    if len(kept) != len(items):
        save_watchlist(kept, path)
        return True
    return False


def toggle_star(symbol, path=WATCHLIST_FILE):
    """Flip the starred flag. Returns the new state, or None if missing."""
    symbol = (symbol or "").strip().upper()
    items = _raw(path)
    for i in items:
        if i.get("symbol") == symbol:
            i["starred"] = not i.get("starred", False)
            save_watchlist(items, path)
            return i["starred"]
    return None
