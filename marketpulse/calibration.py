"""Signal calibration: does a high score actually precede green days?

Every scan appends (date, symbol, score, day_change_pct) to a JSONL log
in the gitignored data/ directory. The dashboard's "Signal calibration"
section then reports, for scores >= 70: how many samples, what % were
positive, and the average day change. The log grows one day at a time,
so early stats carry an honest "N samples" caveat.

This is descriptive, not predictive: it measures past score behavior,
not future returns. Not financial advice.
"""

import json
import os
from datetime import date

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CALIBRATION_LOG = os.path.join(DATA_DIR, "calibration.jsonl")


def _read_entries(path=CALIBRATION_LOG):
    entries = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return entries


def log_scan(results, day=None, path=CALIBRATION_LOG):
    """Append one entry per result. Skips (date, symbol) pairs already logged.

    results: iterable of dicts with symbol, score, quote.change_percent.
    Returns the number of new entries written.
    """
    day = day or date.today().isoformat()
    seen = {(e.get("date"), e.get("symbol")) for e in _read_entries(path)}
    new_lines = []
    for r in results:
        symbol = r.get("symbol")
        score = r.get("score")
        change = (r.get("quote") or {}).get("change_percent")
        if not symbol or score is None or not isinstance(change, (int, float)):
            continue
        if (day, symbol) in seen:
            continue
        seen.add((day, symbol))
        new_lines.append(json.dumps({
            "date": day,
            "symbol": symbol,
            "score": score,
            "change_pct": round(change, 4),
        }))
    if new_lines:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a") as f:
            f.write("\n".join(new_lines) + "\n")
    return len(new_lines)


def summarize(min_score=70, path=CALIBRATION_LOG):
    """Stats for entries with score >= min_score.

    Returns dict: count, positive_pct, avg_change, first_date, last_date.
    Deduplicates on (date, symbol) so re-logged scans don't double-count.
    """
    unique = {}
    for e in _read_entries(path):
        key = (e.get("date"), e.get("symbol"))
        if key[0] and key[1]:
            unique[key] = e
    hits = [e for e in unique.values()
            if isinstance(e.get("score"), (int, float))
            and e["score"] >= min_score
            and isinstance(e.get("change_pct"), (int, float))]
    if not hits:
        return {"count": 0, "positive_pct": 0.0, "avg_change": 0.0,
                "first_date": None, "last_date": None}
    positive = sum(1 for e in hits if e["change_pct"] > 0)
    dates = sorted(e["date"] for e in hits)
    return {
        "count": len(hits),
        "positive_pct": round(positive / len(hits) * 100, 1),
        "avg_change": round(sum(e["change_pct"] for e in hits) / len(hits), 2),
        "first_date": dates[0],
        "last_date": dates[-1],
    }
