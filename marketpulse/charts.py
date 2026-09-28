"""Pure SVG chart helpers -- no network, no streamlit, fully testable."""

from datetime import datetime
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")


def _tick_label(ts):
    """Unix ts -> 'Jul 6' in Eastern time. None-safe."""
    if ts is None:
        return None
    try:
        d = datetime.fromtimestamp(ts, tz=_ET)
    except (OSError, OverflowError, ValueError):
        return None
    return f"{d:%b} {d.day}"


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


def big_chart_svg(closes, w=680, h=220, price_fmt=None, dates=None):
    """Full-size line chart with min/max dashed guides, labels,
    start/end values, and a date axis. Returns an empty string for
    bad input.

    price_fmt: callable formatting a price for the corner labels
    (defaults to plain 1,234.50). Any $ it emits is escaped as \\$
    because this SVG is rendered through st.markdown, where $...$
    would be parsed as LaTeX math and mangle the markup.

    dates: optional list of unix timestamps, one per close, drawn as
    ~5 evenly spaced tick labels ("Jul 6") along the bottom.
    """
    closes = [c for c in closes if c]
    if len(closes) < 2:
        return ""
    closes = closes[-90:]
    if dates is not None:
        dates = list(dates)[-len(closes):]
        if len(dates) != len(closes):
            dates = None
    fmt = price_fmt or (lambda c: f"{c:,.2f}")

    def _label(value):
        return fmt(value).replace("$", "\\$")

    mn, mx = min(closes), max(closes)
    rng = (mx - mn) or 1.0
    pad, top, bottom = 10, 26, 30
    pts = []
    for i, c in enumerate(closes):
        x = pad + i / (len(closes) - 1) * (w - 2 * pad)
        y = top + (1 - (c - mn) / rng) * (h - top - bottom)
        pts.append(f"{x:.1f},{y:.1f}")
    color = "#39ff88" if closes[-1] >= closes[0] else "#ff3b5c"
    line = " ".join(pts)
    y_min = top + (h - top - bottom)
    y_max = top

    ticks = ""
    if dates:
        n = len(closes)
        k = min(5, n)
        idxs = sorted({round(i * (n - 1) / (k - 1)) for i in range(k)}
                      ) if k > 1 else [0]
        for i in idxs:
            lab = _tick_label(dates[i])
            if not lab:
                continue
            x = pad + i / (n - 1) * (w - 2 * pad)
            ticks += (
                f'<text x="{x:.1f}" y="{h - 8}" text-anchor="middle" '
                f'fill="#8b93a7" font-size="10" font-family="monospace">'
                f'{lab}</text>'
            )

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
        f'high {_label(mx)}</text>'
        f'<text x="{w - pad}" y="{y_min + 14:.1f}" text-anchor="end" '
        f'fill="#8b93a7" font-size="11" font-family="monospace">'
        f'low {_label(mn)}</text>'
        f'<text x="{pad}" y="16" fill="#8b93a7" font-size="11" '
        f'font-family="monospace">start {_label(closes[0])}</text>'
        f'<text x="{pad}" y="{y_min + 14:.1f}" fill="{color}" '
        f'font-size="11" font-weight="bold" font-family="monospace">'
        f'end {_label(closes[-1])}</text>'
        f'{ticks}'
        f'<polyline points="{line}" fill="none" stroke="{color}" '
        f'stroke-width="2"/>'
        f'</svg>'
    )
