"""Pure SVG chart helpers -- no network, no streamlit, fully testable."""


def sparkline_points(closes, w=120, h=60):
    """Map closes to SVG polyline points. Returns (points_str, first, last)."""
    closes = [c for c in closes if c]
    if len(closes) < 2:
        return "", None, None
    mn, mx = min(closes), max(closes)
    rng = (mx - mn) or 1.0
    pts = []
    for i, c in enumerate(closes):
        x = 2 + i / (len(closes) - 1) * (w - 4)
        y = 4 + (1 - (c - mn) / rng) * (h - 8)
        pts.append(f"{x:.1f},{y:.1f}")
    return " ".join(pts), closes[0], closes[-1]


def big_chart_svg(closes, w=680, h=220):
    """Full-size line chart with min/max dashed guides, labels, and
    start/end values. Returns an empty string for bad input."""
    closes = [c for c in closes if c]
    if len(closes) < 2:
        return ""
    closes = closes[-90:]
    mn, mx = min(closes), max(closes)
    rng = (mx - mn) or 1.0
    pad, top, bottom = 10, 26, 16
    pts = []
    for i, c in enumerate(closes):
        x = pad + i / (len(closes) - 1) * (w - 2 * pad)
        y = top + (1 - (c - mn) / rng) * (h - top - bottom)
        pts.append(f"{x:.1f},{y:.1f}")
    color = "#39ff88" if closes[-1] >= closes[0] else "#ff3b5c"
    line = " ".join(pts)
    y_min = top + (h - top - bottom)
    y_max = top
    return (
        f'<svg width="100%" viewBox="0 0 {w} {h}" '
        f'style="background:#05070d;border:1px solid #1b2130;'
        f'border-radius:8px;display:block">'
        f'<line x1="{pad}" y1="{y_max:.1f}" x2="{w - pad}" y2="{y_max:.1f}" '
        f'stroke="#2a3350" stroke-dasharray="4 4" stroke-width="1"/>'
        f'<line x1="{pad}" y1="{y_min:.1f}" x2="{w - pad}" y2="{y_min:.1f}" '
        f'stroke="#2a3350" stroke-dasharray="4 4" stroke-width="1"/>'
        f'<text x="{w - pad}" y="{y_max - 6:.1f}" text-anchor="end" '
        f'fill="#8b93a7" font-size="11" font-family="monospace">'
        f'high ${mx:,.2f}</text>'
        f'<text x="{w - pad}" y="{y_min + 14:.1f}" text-anchor="end" '
        f'fill="#8b93a7" font-size="11" font-family="monospace">'
        f'low ${mn:,.2f}</text>'
        f'<text x="{pad}" y="16" fill="#8b93a7" font-size="11" '
        f'font-family="monospace">start ${closes[0]:,.2f}</text>'
        f'<text x="{w - pad}" y="16" text-anchor="end" fill="{color}" '
        f'font-size="11" font-weight="bold" font-family="monospace">'
        f'end ${closes[-1]:,.2f}</text>'
        f'<polyline points="{line}" fill="none" stroke="{color}" '
        f'stroke-width="2"/>'
        f'</svg>'
    )
