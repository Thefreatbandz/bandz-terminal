"""Squarified treemap layout (Bruls et al.). Pure, no dependencies.

Treemap/scan approach adapted from OpenTerminal (MIT).
"""
from __future__ import annotations


def _is_valid_weight(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) \
        and value == value and value > 0  # NaN fails both checks


def _worst(row_areas, side):
    """Aspect-ratio penalty of a candidate row of areas against the short side."""
    if not row_areas:
        return float("inf")
    s = sum(row_areas)
    mx = max(row_areas)
    mn = min(row_areas)
    # s > 0 and mn > 0 are guaranteed by the weight filter in layout().
    return max(side * side * mx / (s * s), (s * s) / (side * side * mn))


def _layout_row(row, cx, cy, cw, ch, last=False):
    """Lay one row into rect (cx, cy, cw, ch). Returns (tiles, new rect).

    The last tile in each row snaps to the rect's far edge, and when this is
    the final row the strip itself spans the remaining rect exactly, so float
    drift can neither leave a sliver nor poke outside the rect.
    """
    row_sum = sum(area for _, area in row)
    if cw <= ch:
        # Vertical strip on the left.
        strip_w = cw if last else (row_sum / ch if ch > 0 else 0.0)
        tiles = []
        y = cy
        for n, (item, area) in enumerate(row):
            if n == len(row) - 1:
                h = (cy + ch) - y  # snap to the bottom edge
            else:
                h = area / strip_w if strip_w > 0 else 0.0
            tiles.append((item, cx, y, strip_w, h))
            y += h
        return tiles, (cx + strip_w, cy, cw - strip_w, ch)
    # Horizontal strip on top.
    strip_h = ch if last else (row_sum / cw if cw > 0 else 0.0)
    tiles = []
    x = cx
    for n, (item, area) in enumerate(row):
        if n == len(row) - 1:
            w = (cx + cw) - x  # snap to the right edge
        else:
            w = area / strip_h if strip_h > 0 else 0.0
        tiles.append((item, x, cy, w, strip_h))
        x += w
    return tiles, (cx, cy + strip_h, cw, ch - strip_h)


def _clamp01ish(value):
    # Clamp float-drift artifacts to exact zero; keep negatives from real
    # errors visible so callers notice something genuinely wrong.
    if -1e-9 < value < 0:
        return 0.0
    return value


def layout(items, width=1000, height=1000):
    """Squarified treemap layout for a list of {'weight': n, ...} dicts.

    Returns a NEW list of dict copies with float x, y, w, h in the
    0..width / 0..height space. Items with missing/non-numeric/<=0
    weights are filtered out; width/height <= 0 yields [].
    """
    if width <= 0 or height <= 0:
        return []

    valid = [item for item in items if _is_valid_weight(item.get("weight"))]
    if not valid:
        return []

    ordered = sorted(valid, key=lambda d: d["weight"], reverse=True)
    total = sum(d["weight"] for d in ordered)
    scale = (width * height) / total
    areas = [d["weight"] * scale for d in ordered]

    cx, cy, cw, ch = 0.0, 0.0, float(width), float(height)
    row = []  # list of (item_dict, area)
    placed = []  # list of (item_dict, x, y, w, h)

    for item, area in zip(ordered, areas):
        side = min(cw, ch)
        if not row:
            row.append((item, area))
            continue
        cur = _worst([a for _, a in row], side)
        cand = _worst([a for _, a in row] + [area], side)
        if cand <= cur:
            row.append((item, area))
        else:
            # Mid-loop: there is always at least one pending area, so this
            # row is never the final one.
            tiles, (cx, cy, cw, ch) = _layout_row(row, cx, cy, cw, ch)
            placed.extend(tiles)
            row = [(item, area)]

    if row:
        tiles, _ = _layout_row(row, cx, cy, cw, ch, last=True)
        placed.extend(tiles)

    result = []
    for item, x, y, w, h in placed:
        tile = dict(item)
        tile["x"] = _clamp01ish(x)
        tile["y"] = _clamp01ish(y)
        tile["w"] = _clamp01ish(w)
        tile["h"] = _clamp01ish(h)
        result.append(tile)
    return result
