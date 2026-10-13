"""Tests for marketpulse.indicators (pure, None-padded technical indicators)."""

import math

import pytest

from marketpulse.indicators import bollinger, ema, macd, rsi, sma, vwap


# ---------------------------------------------------------------------------
# sma
# ---------------------------------------------------------------------------

class TestSMA:
    def test_spec_example(self):
        assert sma([1, 2, 3, 4], 2) == [None, 1.5, 2.5, 3.5]

    def test_n1_is_identity(self):
        assert sma([1.0, 2.0, 3.0], 1) == [1.0, 2.0, 3.0]

    def test_first_n_minus_1_none(self):
        out = sma([1, 2, 3, 4, 5], 3)
        assert out[:2] == [None, None]
        assert out[2] == pytest.approx(2.0)
        assert out[4] == pytest.approx(4.0)

    def test_rolling(self):
        assert sma([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]

    def test_n_larger_than_input_all_none(self):
        assert sma([1, 2], 5) == [None, None]

    def test_empty(self):
        assert sma([], 3) == []

    def test_n_zero_raises(self):
        with pytest.raises(ValueError):
            sma([1, 2, 3], 0)

    def test_n_negative_raises(self):
        with pytest.raises(ValueError):
            sma([1, 2, 3], -2)


# ---------------------------------------------------------------------------
# ema
# ---------------------------------------------------------------------------

class TestEMA:
    def test_spec_example(self):
        # NOTE: the task spec claimed ema[3] ≈ 3.1667, but the stated formula
        # (k = 2/(n+1) = 2/3) gives 4*(2/3) + 2.5*(1/3) = 3.5. Test follows
        # the formula, not the spec's arithmetic slip.
        out = ema([1, 2, 3, 4], 2)
        assert out[0] is None
        assert out[1] == pytest.approx(1.5)
        assert out[2] == pytest.approx(2.5)
        assert out[3] == pytest.approx(3.5)

    def test_seed_is_window_mean(self):
        out = ema([2.0, 4.0, 6.0, 8.0], 3)
        assert out[:2] == [None, None]
        assert out[2] == pytest.approx(4.0)  # mean(2,4,6)

    def test_recursion(self):
        # n=2 -> k=2/3, seed=mean(10,20)=15
        out = ema([10.0, 20.0, 30.0], 2)
        assert out[2] == pytest.approx(30 * (2 / 3) + 15 * (1 / 3))

    def test_flat_series_stays_flat(self):
        assert ema([5.0] * 10, 4)[-1] == pytest.approx(5.0)

    def test_n1_is_identity(self):
        assert ema([1.0, 2.0, 3.0], 1) == [1.0, 2.0, 3.0]

    def test_empty(self):
        assert ema([], 5) == []

    def test_n_zero_raises(self):
        with pytest.raises(ValueError):
            ema([1, 2, 3], 0)


# ---------------------------------------------------------------------------
# rsi
# ---------------------------------------------------------------------------

class TestRSI:
    def test_strictly_rising_last_is_100(self):
        out = rsi(list(range(1, 21)))
        assert len(out) == 20
        assert out[:14] == [None] * 14
        assert out[-1] == 100.0

    def test_strictly_falling_last_is_0(self):
        out = rsi(list(range(20, 0, -1)))
        assert out[-1] == 0.0

    def test_flat_series_is_50(self):
        out = rsi([42.0] * 20)
        assert all(v == 50.0 for v in out if v is not None)
        assert out[14] == 50.0

    def test_first_n_entries_none(self):
        closes = [float(i) for i in range(30)]
        out = rsi(closes, n=14)
        assert out[:14] == [None] * 14
        assert out[14] is not None

    def test_bounds(self):
        closes = [10 + (i % 5) - (i % 3) for i in range(60)]
        out = rsi(closes, n=14)
        for v in out:
            if v is not None:
                assert 0.0 <= v <= 100.0

    def test_custom_n(self):
        out = rsi(list(range(1, 11)), n=5)
        assert out[:5] == [None] * 5
        assert out[-1] == 100.0

    def test_empty(self):
        assert rsi([]) == []

    def test_n_zero_raises(self):
        with pytest.raises(ValueError):
            rsi([1, 2, 3], 0)

    def test_needs_more_than_n_points(self):
        # exactly n closes -> only n-1 changes -> all None
        assert rsi([1.0, 2.0, 3.0], n=5) == [None, None, None]


# ---------------------------------------------------------------------------
# macd
# ---------------------------------------------------------------------------

class TestMACD:
    def test_returns_three_lists_of_input_length(self):
        closes = [float(i) for i in range(1, 60)]
        m, s, h = macd(closes)
        assert len(m) == len(s) == len(h) == 59

    def test_none_padding_at_start(self):
        closes = [float(i) for i in range(1, 60)]
        m, s, h = macd(closes)
        # macd defined only where both emas defined -> first 25 None
        assert m[:25] == [None] * 25
        assert m[25] is not None
        # signal needs 9 macd values -> first 25+8=33 None
        assert s[:33] == [None] * 33
        assert s[33] is not None
        assert h[:33] == [None] * 33

    def test_last_hist_is_float_on_rising_series(self):
        closes = [float(i) for i in range(1, 80)]
        m, s, h = macd(closes)
        assert isinstance(h[-1], float)
        assert h[-1] == m[-1] - s[-1]

    def test_hist_equals_macd_minus_signal(self):
        closes = [50 + 2 * math.sin(i / 5) + i * 0.1 for i in range(80)]
        m, s, h = macd(closes)
        for i in range(len(closes)):
            if m[i] is not None and s[i] is not None:
                assert h[i] == pytest.approx(m[i] - s[i])
            else:
                assert h[i] is None

    def test_flat_series_converges_to_zero(self):
        closes = [10.0] * 80
        m, s, h = macd(closes)
        assert abs(h[-1]) < 1e-9

    def test_custom_params(self):
        closes = [float(i) for i in range(1, 40)]
        m, s, h = macd(closes, fast=5, slow=10, signal=4)
        assert m[:9] == [None] * 9
        assert s[:9 + 3] == [None] * 12
        assert len(m) == 39

    def test_empty(self):
        assert macd([]) == ([], [], [])

    def test_bad_params_raise(self):
        with pytest.raises(ValueError):
            macd([1.0, 2.0], fast=0)
        with pytest.raises(ValueError):
            macd([1.0, 2.0], slow=0)
        with pytest.raises(ValueError):
            macd([1.0, 2.0], signal=-1)


# ---------------------------------------------------------------------------
# bollinger
# ---------------------------------------------------------------------------

class TestBollinger:
    def test_first_n_minus_1_none(self):
        closes = [float(i) for i in range(30)]
        mid, upper, lower = bollinger(closes, n=20, k=2)
        for band in (mid, upper, lower):
            assert len(band) == 30
            assert band[:19] == [None] * 19
            assert band[19] is not None

    def test_width_symmetry(self):
        closes = [100 + 3 * math.sin(i / 4) + i * 0.2 for i in range(40)]
        mid, upper, lower = bollinger(closes, n=20, k=2)
        for i in range(19, 40):
            assert (upper[i] - mid[i]) == pytest.approx(mid[i] - lower[i])
            assert upper[i] >= mid[i] >= lower[i]

    def test_mid_is_sma(self):
        closes = [float(i) for i in range(30)]
        mid, _, _ = bollinger(closes, n=20, k=2)
        assert mid == sma(closes, 20)

    def test_population_stdev(self):
        closes = [1.0, 2.0, 3.0, 4.0]
        mid, upper, lower = bollinger(closes, n=4, k=1)
        mean = 2.5
        var = ((1 - 2.5) ** 2 + (2 - 2.5) ** 2
               + (3 - 2.5) ** 2 + (4 - 2.5) ** 2) / 4
        sd = math.sqrt(var)
        assert mid[-1] == pytest.approx(mean)
        assert upper[-1] == pytest.approx(mean + sd)
        assert lower[-1] == pytest.approx(mean - sd)

    def test_flat_series_zero_width(self):
        closes = [7.0] * 25
        mid, upper, lower = bollinger(closes, n=20, k=2)
        assert upper[-1] == lower[-1] == mid[-1] == 7.0

    def test_empty(self):
        assert bollinger([]) == ([], [], [])

    def test_n_zero_raises(self):
        with pytest.raises(ValueError):
            bollinger([1.0, 2.0], n=0)


# ---------------------------------------------------------------------------
# vwap
# ---------------------------------------------------------------------------

class TestVWAP:
    def test_single_bar_is_typical_price(self):
        assert vwap([10.0], [8.0], [9.0], [100.0]) == [pytest.approx(9.0)]

    def test_cumulative(self):
        highs = [10.0, 12.0]
        lows = [8.0, 10.0]
        closes = [9.0, 11.0]
        vols = [100.0, 100.0]
        t1 = (10 + 8 + 9) / 3
        t2 = (12 + 10 + 11) / 3
        expected = [(t1 * 100) / 100, (t1 * 100 + t2 * 100) / 200]
        out = vwap(highs, lows, closes, vols)
        assert out == [pytest.approx(expected[0]), pytest.approx(expected[1])]

    def test_zero_volumes_all_none(self):
        out = vwap([1.0, 2.0], [0.5, 1.5], [0.75, 1.75], [0.0, 0.0])
        assert out == [None, None]

    def test_zero_cumulative_volume_stays_none_until_volume(self):
        out = vwap([1.0, 2.0], [1.0, 2.0], [1.0, 2.0], [0.0, 10.0])
        assert out[0] is None
        assert out[1] == pytest.approx(2.0)

    def test_mismatched_lengths_raise(self):
        with pytest.raises(ValueError):
            vwap([1.0, 2.0], [1.0], [1.0, 2.0], [1.0, 2.0])
        with pytest.raises(ValueError):
            vwap([1.0], [1.0], [1.0], [1.0, 2.0])

    def test_empty(self):
        assert vwap([], [], [], []) == []

    def test_never_raises_on_dirty_data(self):
        out = vwap([1.0, None, 2.0], [1.0, 1.0, 2.0],
                   [1.0, 1.0, 2.0], [10.0, 10.0, 10.0])
        assert len(out) == 3
        assert out[1] is None  # dirty bar skipped, cumulative untouched
        assert out[2] == pytest.approx(((1.0) * 10 + (2.0) * 10) / 20)


# ---------------------------------------------------------------------------
# cleaning / robustness shared behavior
# ---------------------------------------------------------------------------

class TestCleaning:
    def test_none_and_nan_dropped(self):
        nan = float("nan")
        out = sma([1.0, None, nan, 2.0, 3.0], 2)
        # cleaned = [1,2,3] -> [None, 1.5, 2.5], re-anchored to length 5
        assert out == [None, None, None, 1.5, 2.5]

    def test_non_numeric_dropped(self):
        out = sma([1.0, "junk", 2.0, 3.0], 2)
        assert out == [None, None, 1.5, 2.5]

    def test_length_always_matches_input(self):
        closes = [1.0, None, 2.0, "x", 3.0, float("inf"), 4.0, 5.0]
        for fn in (lambda v: sma(v, 2), lambda v: ema(v, 3),
                   lambda v: rsi(v, 5)):
            assert len(fn(closes)) == len(closes)
        m, s, h = macd(closes)
        assert len(m) == len(s) == len(h) == len(closes)
        mid, upper, lower = bollinger(closes, n=5)
        assert len(mid) == len(upper) == len(lower) == len(closes)
        vw = vwap(closes, closes, closes, [1.0] * len(closes))
        assert len(vw) == len(closes)

    def test_rsi_no_crash_short_dirty(self):
        assert rsi([None, float("nan"), "bad"], 14) == [None, None, None]

    def test_bool_is_rejected_as_n(self):
        with pytest.raises(ValueError):
            sma([1, 2, 3], True)
