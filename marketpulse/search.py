"""Instant ticker search: rank symbols against a typed query.

Tiers, best first:
  0. exact symbol match            ("nvda" -> NVDA)
  1. symbol startswith query       ("nv" -> NVDA, NVDA... )
  2. symbol contains query         ("oo" -> GOOGL)
  3. name word starts with query   ("nvid" -> NVIDIA Corp)
  4. name contains query           ("electric" -> General Electric)
  5. difflib close matches        ("ndva" -> NVDA, typo tolerance)

Pure function, no network. Case-insensitive; whitespace stripped.
"""
import difflib


def suggest_symbols(query, names, limit=8):
    """Rank (symbol, display name) suggestions for a query.

    names: {SYMBOL: company name}. Returns at most `limit` items,
    best match first. [] for empty queries or no matches.
    """
    q = (query or "").strip().upper()
    if not q or not names:
        return []
    seen = set()
    ranked = []

    def add(sym):
        if sym not in seen:
            seen.add(sym)
            ranked.append((sym, names.get(sym, sym)))

    symbols = list(names)
    # 0. exact symbol
    if q in names:
        add(q)
    # 1. symbol prefix
    for sym in sorted(symbols):
        if sym.startswith(q):
            add(sym)
    # 2. symbol substring
    for sym in sorted(symbols):
        if q in sym:
            add(sym)
    # 3. name word-start
    ql = q.lower()
    for sym in sorted(symbols):
        words = str(names.get(sym, "")).lower().split()
        if any(w.startswith(ql) for w in words):
            add(sym)
    # 4. name substring
    for sym in sorted(symbols):
        if ql in str(names.get(sym, "")).lower():
            add(sym)
    # 5. typo tolerance on symbols
    for sym in difflib.get_close_matches(q, symbols, n=limit, cutoff=0.6):
        add(sym)
    return ranked[:limit]
