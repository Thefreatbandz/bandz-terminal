"""Pure SVG chart helpers -- no network, no streamlit, fully testable."""

import html
from datetime import datetime
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")

#: Timeframe selector for the full-size chart. Label -> (Yahoo range,
#: Yahoo interval). Kept here (not web.py) so it stays unit-testable.
CHART_TIMEFRAMES = {
    "1D": ("1d", "5m"),
    "1W": ("5d", "15m"),
    "1M": ("1mo", "1d"),
    "3M": ("3mo", "1d"),
    "1Y": ("1y", "1wk"),
}
CHART_DEFAULT = "3M"

#: Intraday timeframes (tick labels show Eastern clock time, not dates).
INTRADAY_TIMEFRAMES = {"1D"}

#: Second color for the compare overlay line.
COMPARE_COLOR = "#b48cff"


def _tick_label(ts):
    """Unix ts -> 'Jul 6' in Eastern time. None-safe."""
    if ts is None:
        return None
    try:
        d = datetime.fromtimestamp(ts, tz=_ET)
    except (OSError, OverflowError, ValueError):
        return None
    return f"{d:%b} {d.day}"


def _time_label(ts):
    """Unix ts -> '9:30a' in Eastern time, for intraday axes. None-safe."""
    if ts is None:
        return None
    try:
        d = datetime.fromtimestamp(ts, tz=_ET)
    except (OSError, OverflowError, ValueError):
        return None
    hour = d.hour % 12 or 12
    ap = "a" if d.hour < 12 else "p"
    return f"{hour}:{d.minute:02d}{ap}"


def rebase_to_100(closes):
    """Rebase a series so its first point equals 100.

    Returns [] for unusable input (fewer than 2 points, or a zero
    first point).
    """
    closes = [c for c in closes if c]
    if len(closes) < 2 or not closes[0]:
        return []
    base = closes[0]
    return [c / base * 100.0 for c in closes]


def align_compare(base_closes, cmp_closes):
    """Align two series for a compare overlay.

    Both are rebased to 100 and truncated to the overlapping tail
    (last n points of each, n = shorter length) so the lines share an
    x-axis. Returns (base_rebased, cmp_rebased); cmp_rebased is None
    when the compare series is unusable, in which case the caller
    should draw a single series.
    """
    base = rebase_to_100(base_closes)
    if not base:
        return [], None
    cmp_rb = rebase_to_100(cmp_closes)
    if not cmp_rb:
        return base, None
    n = min(len(base), len(cmp_rb))
    return base[-n:], cmp_rb[-n:]


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


def big_chart_svg(closes, w=680, h=220, price_fmt=None, dates=None,
                  compare=None, label="", compare_label="",
                  intraday=False):
    """Full-size line chart with min/max dashed guides, labels,
    start/end values, and a date axis. Returns an empty string for
    bad input.

    price_fmt: callable formatting a price for the corner labels
    (defaults to plain 1,234.50). Any $ it emits is escaped as \\$
    because this SVG is rendered through st.markdown, where $...$
    would be parsed as LaTeX math and mangle the markup.

    dates: optional list of unix timestamps, one per close, drawn as
    ~5 evenly spaced tick labels ("Jul 6") along the bottom.
    intraday: tick labels show Eastern clock time ("9:30a") instead.

    compare: optional second raw close series. It is rebased to 100
    alongside the base series, drawn in a second color, and labeled
    with a small legend (label / compare_label). An unusable compare
    series silently degrades to a single line.
    """
    closes = [c for c in closes if c]
    if len(closes) < 2:
        return ""
    cmp_rb = None
    if compare is not None:
        # Only switch to rebased values when the compare series is
        # actually usable; otherwise keep the original single series.
        base_rb, maybe_cmp = align_compare(closes, compare)
        if maybe_cmp is not None:
            closes, cmp_rb = base_rb, maybe_cmp
    if len(closes) < 2:
        return ""
    closes = closes[-90:]
    if cmp_rb is not None:
        cmp_rb = cmp_rb[-90:]
    if dates is not None:
        dates = list(dates)[-len(closes):]
        if len(dates) != len(closes):
            dates = None
    fmt = price_fmt or (lambda c: f"{c:,.2f}")

    def _label(value):
        return fmt(value).replace("$", "\\$")

    series_all = closes + (cmp_rb or [])
    mn, mx = min(series_all), max(series_all)
    rng = (mx - mn) or 1.0
    pad, top, bottom = 10, 26, 30

    def _points(vals):
        pts = []
        for i, c in enumerate(vals):
            x = pad + i / (len(vals) - 1) * (w - 2 * pad)
            y = top + (1 - (c - mn) / rng) * (h - top - bottom)
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    color = "#39ff88" if closes[-1] >= closes[0] else "#ff3b5c"
    line = _points(closes)
    y_min = top + (h - top - bottom)
    y_max = top

    ticks = ""
    if dates:
        tick_fn = _time_label if intraday else _tick_label
        n = len(closes)
        k = min(5, n)
        idxs = sorted({round(i * (n - 1) / (k - 1)) for i in range(k)}
                      ) if k > 1 else [0]
        for i in idxs:
            lab = tick_fn(dates[i])
            if not lab:
                continue
            x = pad + i / (n - 1) * (w - 2 * pad)
            ticks += (
                f'<text x="{x:.1f}" y="{h - 8}" text-anchor="middle" '
                f'fill="#8b93a7" font-size="10" font-family="monospace">'
                f'{lab}</text>'
            )

    start_y = "42" if cmp_rb is not None else "16"
    legend = ""
    if cmp_rb is not None:
        legend = (
            f'<circle cx="{pad}" cy="10" r="4" fill="{color}"/>'
            f'<text x="{pad + 9}" y="14" fill="#8b93a7" font-size="11" '
            f'font-family="monospace">{html.escape(label)}</text>'
            f'<circle cx="{pad}" cy="24" r="4" fill="{COMPARE_COLOR}"/>'
            f'<text x="{pad + 9}" y="28" fill="#8b93a7" font-size="11" '
            f'font-family="monospace">'
            f'{html.escape(compare_label)}</text>'
            f'<polyline points="{_points(cmp_rb)}" fill="none" '
            f'stroke="{COMPARE_COLOR}" stroke-width="2"/>'
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
        f'<text x="{pad}" y="{start_y}" fill="#8b93a7" font-size="11" '
        f'font-family="monospace">start {_label(closes[0])}</text>'
        f'<text x="{pad}" y="{y_min + 14:.1f}" fill="{color}" '
        f'font-size="11" font-weight="bold" font-family="monospace">'
        f'end {_label(closes[-1])}</text>'
        f'{ticks}'
        f'{legend}'
        f'<polyline points="{line}" fill="none" stroke="{color}" '
        f'stroke-width="2"/>'
        f'</svg>'
    )


#: Google-Finance-style timeframe set for the detail panel.
#: Label -> (Yahoo range, Yahoo interval).
GF_TIMEFRAMES = {
    "1D": ("1d", "5m"),
    "5D": ("5d", "15m"),
    "1M": ("1mo", "1d"),
    "6M": ("6mo", "1d"),
    "YTD": ("ytd", "1d"),
}
GF_DEFAULT = "1M"

#: Human label for the change readout, e.g. "-11.40 (-5.32%) past month".
GF_RANGE_LABEL = {
    "1D": "today",
    "5D": "past week",
    "1M": "past month",
    "6M": "past 6 months",
    "YTD": "year to date",
}

GF_UP = "#34d399"
GF_DOWN = "#f87171"


def timeframe_change(closes):
    """(absolute, percent) change from first to last close.

    Returns (None, None) for unusable input.
    """
    closes = [c for c in closes if c]
    if len(closes) < 2 or not closes[0]:
        return None, None
    first, last = closes[0], closes[-1]
    return last - first, (last - first) / first * 100.0


def gf_chart_svg(closes, dates=None, w=680, h=240, line=None,
                 intraday=False):
    """Google-Finance-style area chart: gradient fill, axis labels,
    end dot. Returns "" for bad input.

    line: stroke color; defaults to GF_UP/GF_DOWN by trend.
    dates: unix timestamps, one per close, for the bottom axis.
    intraday: bottom labels show Eastern clock time ("9:30a").
    """
    closes = [c for c in closes if c]
    if len(closes) < 2:
        return ""
    closes = closes[-180:]
    if dates is not None:
        dates = list(dates)[-len(closes):]
        if len(dates) != len(closes):
            dates = None
    color = line or (GF_UP if closes[-1] >= closes[0] else GF_DOWN)
    mn, mx = min(closes), max(closes)
    rng = (mx - mn) or 1.0
    pad_l, pad_r, top, bottom = 44, 10, 12, 28

    def _x(i):
        return pad_l + i / (len(closes) - 1) * (w - pad_l - pad_r)

    def _y(c):
        return top + (1 - (c - mn) / rng) * (h - top - bottom)

    pts = " ".join(f"{_x(i):.1f},{_y(c):.1f}"
                   for i, c in enumerate(closes))
    area = (f"M{pad_l:.1f},{_y(closes[0]):.1f} L"
            + " L".join(f"{_x(i):.1f},{_y(c):.1f}"
                        for i, c in enumerate(closes))
            + f" L{_x(len(closes) - 1):.1f},{h - bottom:.1f}"
            + f" L{pad_l:.1f},{h - bottom:.1f} Z")

    # 4 y-axis labels + gridlines.
    ylab = ""
    for k in range(4):
        v = mn + rng * k / 3
        y = _y(v)
        ylab += (
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w - pad_r}" '
            f'y2="{y:.1f}" stroke="#232b40" stroke-width="1"/>'
            f'<text x="{pad_l - 6}" y="{y + 3.5:.1f}" text-anchor="end" '
            f'fill="#8b93a7" font-size="10" font-family="monospace">'
            f'{v:,.0f}</text>'
        )

    # ~4 date labels along the bottom.
    xlab = ""
    if dates:
        tick_fn = _time_label if intraday else _tick_label
        n = len(closes)
        k = min(4, n)
        idxs = sorted({round(i * (n - 1) / (k - 1)) for i in range(k)}
                      ) if k > 1 else [0]
        for i in idxs:
            lab = tick_fn(dates[i])
            if not lab:
                continue
            xlab += (
                f'<text x="{_x(i):.1f}" y="{h - 8}" text-anchor="middle" '
                f'fill="#8b93a7" font-size="10" font-family="monospace">'
                f'{lab}</text>'
            )

    ex, ey = _x(len(closes) - 1), _y(closes[-1])
    gid = f"gfa{abs(hash(pts)) % 100000}"
    return (
        f'<svg width="100%" viewBox="0 0 {w} {h}" '
        f'style="display:block">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{color}" stop-opacity="0.28"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0.02"/>'
        f'</linearGradient></defs>'
        f'{ylab}'
        f'<path d="{area}" fill="url(#{gid})"/>'
        f'<polyline points="{pts}" fill="none" stroke="{color}" '
        f'stroke-width="2.5" stroke-linejoin="round"/>'
        f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="5" fill="{color}"/>'
        f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="9" fill="{color}" '
        f'fill-opacity="0.18"/>'
        f'{xlab}'
        f'</svg>'
    )
