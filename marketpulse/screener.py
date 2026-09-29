"""Screener: pure filter/sort over an already-fetched universe scan.

No network, no streamlit -- unit-testable. web.py feeds it the current
stock_results so filtering never triggers a rescan.
"""


def apply_filters(results, price_min=None, price_max=None,
                  min_abs_change=0.0, sector="All", min_score=0):
    """Filter scan results. Rows missing price/change are skipped.

    results: engine.scan_universe dicts (symbol, quote{price,
    change_percent}, score, sector).
    """
    out = []
    for r in results or []:
        q = r.get("quote") or {}
        price = q.get("price")
        chg = q.get("change_percent")
        if not isinstance(price, (int, float)):
            continue
        if not isinstance(chg, (int, float)):
            continue
        if price_min is not None and price < price_min:
            continue
        if price_max is not None and price > price_max:
            continue
        if abs(chg) < (min_abs_change or 0.0):
            continue
        if sector != "All" and r.get("sector") != sector:
            continue
        if (r.get("score") or 0) < (min_score or 0):
            continue
        out.append(r)
    return out


def sort_results(results, sort_by="score"):
    """Sort filtered rows. sort_by: 'score' or 'change' (|day %|)."""
    rows = list(results or [])
    if sort_by == "change":
        return sorted(rows,
                      key=lambda r: abs(r["quote"]["change_percent"]),
                      reverse=True)
    return sorted(rows, key=lambda r: r.get("score", 0), reverse=True)
