"""Pure technical indicators for the Bandz Terminal stock app.

All functions return None-padded outputs of the same length as the (cleaned)
input, and never raise on data — only ValueError for bad parameters (n<1,
mismatched input lengths).

Cleaning rule: every input is first filtered to finite floats. ``None`` and
NaN/inf entries are dropped, and any non-numeric entry is coerced with
``float()``; entries that fail coercion are dropped too. All math then runs on
the cleaned list, and the result is padded/re-aligned back onto the original
input length where applicable. This keeps the functions pure, deterministic,
and impossible to crash on dirty tape data.

Example
-------
>>> from marketpulse.indicators import sma, ema, rsi, macd, bollinger, vwap
>>> prices = [100.0, 101.5, 102.0, 103.5, 104.0, 105.0]
>>> sma(prices, 3)
[None, None, 101.16666666666667, 102.33333333333333, 103.16666666666667, 104.16666666666667]
>>> rsi([45.0]*20)  # flat series -> neutral
[None, None, None, None, None, None, None, None, None, None, None, None, None, None, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0]
>>> m, s, h = macd(prices); len(m) == len(s) == len(h) == len(prices)
True
"""

import math


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _clean(values):
    """Filter *values* to finite floats, dropping None/NaN/inf/non-numeric."""
    out = []
    for v in values:
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            out.append(f)
    return out


def _validate_n(n):
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ValueError("n must be a positive integer, got %r" % (n,))


def _none_pad(leading_nones, computed):
    """Build a result list: *leading_nones* Nones followed by *computed*."""
    return [None] * leading_nones + list(computed)


# ---------------------------------------------------------------------------
# indicators
# ---------------------------------------------------------------------------

def sma(values, n):
    """Simple moving average. First n-1 entries None, then rolling n-mean."""
    _validate_n(n)
    if not values:
        return []
    cleaned = _clean(values)
    out = []
    window_sum = 0.0
    for i, v in enumerate(cleaned):
        window_sum += v
        if i >= n:
            window_sum -= cleaned[i - n]
        out.append(window_sum / n if i >= n - 1 else None)
    # re-align onto original length: padding is anchored to the raw input
    return [None] * (len(values) - len(out)) + out


def ema(values, n):
    """Exponential moving average.

    First n-1 entries None; ema[n-1] = mean(values[0:n]), then the standard
    k = 2/(n+1) recursion.
    """
    _validate_n(n)
    if not values:
        return []
    cleaned = _clean(values)
    if not cleaned:
        return [None] * len(values)
    out = [None] * min(n - 1, len(cleaned))
    if len(cleaned) >= n:
        seed = sum(cleaned[:n]) / n
        out.append(seed)
        k = 2.0 / (n + 1)
        prev = seed
        for v in cleaned[n:]:
            prev = v * k + prev * (1.0 - k)
            out.append(prev)
    # else: fewer than n cleaned points -> all None for those
    return [None] * (len(values) - len(out)) + out


def rsi(closes, n=14):
    """Wilder's RSI. First n entries None (needs n price changes)."""
    _validate_n(n)
    if not closes:
        return []
    cleaned = _clean(closes)
    out = []
    for _ in cleaned:
        out.append(None)  # placeholder; replaced below
    out = [None] * len(cleaned)
    if len(cleaned) > n:
        gains = []
        losses = []
        for i in range(1, n + 1):
            change = cleaned[i] - cleaned[i - 1]
            gains.append(max(change, 0.0))
            losses.append(max(-change, 0.0))
        avg_gain = sum(gains) / n
        avg_loss = sum(losses) / n
        for i in range(n, len(cleaned)):
            if i > n:
                change = cleaned[i] - cleaned[i - 1]
                gain = max(change, 0.0)
                loss = max(-change, 0.0)
                avg_gain = (avg_gain * (n - 1) + gain) / n
                avg_loss = (avg_loss * (n - 1) + loss) / n
            if avg_gain == 0.0 and avg_loss == 0.0:
                out[i] = 50.0
            elif avg_loss == 0.0:
                out[i] = 100.0
            else:
                rs = avg_gain / avg_loss
                out[i] = 100.0 - 100.0 / (1.0 + rs)
    return [None] * (len(closes) - len(out)) + out


def macd(closes, fast=12, slow=26, signal=9):
    """MACD. Returns (macd_line, signal_line, hist), each input-length."""
    for name, p in (("fast", fast), ("slow", slow), ("signal", signal)):
        if not isinstance(p, int) or isinstance(p, bool) or p < 1:
            raise ValueError("%s must be a positive integer, got %r" % (name, p))
    if not closes:
        return [], [], []
    n = len(closes)
    cleaned = _clean(closes)
    # map cleaned index -> original index
    raw_index = []
    for i, v in enumerate(closes):
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if math.isfinite(f):
            raw_index.append(i)

    macd_clean = [None] * len(cleaned)
    if cleaned:
        ef = ema(cleaned, fast)
        es = ema(cleaned, slow)
        for i in range(len(cleaned)):
            if ef[i] is not None and es[i] is not None:
                macd_clean[i] = ef[i] - es[i]

    defined = [(i, m) for i, m in enumerate(macd_clean) if m is not None]
    sig_clean = [None] * len(cleaned)
    if defined:
        first_def = defined[0][0]
        vals = [m for _, m in defined]
        # signal EMA over the defined macd values; needs `signal` points
        sig_vals = ema(vals, signal)
        for (ci, _), s in zip(defined, sig_vals):
            sig_clean[ci] = s

    # scatter back onto original positions
    macd_line = [None] * n
    signal_line = [None] * n
    hist = [None] * n
    for ci, ri in enumerate(raw_index):
        m = macd_clean[ci]
        s = sig_clean[ci]
        macd_line[ri] = m
        signal_line[ri] = s
        if m is not None and s is not None:
            hist[ri] = m - s
    return macd_line, signal_line, hist


def bollinger(closes, n=20, k=2):
    """Bollinger Bands. Returns (mid, upper, lower); first n-1 None."""
    _validate_n(n)
    if not closes:
        return [], [], []
    cleaned = _clean(closes)
    mid_c = [None] * len(cleaned)
    upper_c = [None] * len(cleaned)
    lower_c = [None] * len(cleaned)
    for i in range(len(cleaned)):
        if i >= n - 1:
            window = cleaned[i - n + 1:i + 1]
            mean = sum(window) / n
            var = sum((x - mean) ** 2 for x in window) / n  # population stdev
            sd = math.sqrt(var)
            mid_c[i] = mean
            upper_c[i] = mean + k * sd
            lower_c[i] = mean - k * sd
    pad = [None] * (len(closes) - len(cleaned))
    return pad + mid_c, pad + upper_c, pad + lower_c


def vwap(highs, lows, closes, volumes):
    """Cumulative volume-weighted average price of the typical price.

    Returns None where cumulative volume is 0. All lengths must match.
    """
    lens = [len(highs), len(lows), len(closes), len(volumes)]
    if not (lens[0] == lens[1] == lens[2] == lens[3]):
        raise ValueError("lengths must match, got %s" % (lens,))
    if not highs:
        return []
    cum_pv = 0.0
    cum_vol = 0.0
    out = []
    for h, l, c, v in zip(highs, lows, closes, volumes):
        try:
            h, l, c, v = float(h), float(l), float(c), float(v)
        except (TypeError, ValueError):
            out.append(None)
            continue
        if not (math.isfinite(h) and math.isfinite(l)
                and math.isfinite(c) and math.isfinite(v)):
            out.append(None)
            continue
        typical = (h + l + c) / 3.0
        cum_pv += typical * v
        cum_vol += v
        out.append(cum_pv / cum_vol if cum_vol != 0.0 else None)
    return out
