"""Tests for the watchlist-benchmark averaging helper."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))

from marketpulse.charts import equal_weight_rebased  # noqa: E402


def test_equal_weight_two_series():
    # [100->110] and [200->220]: both +10%, average stays +10%.
    avg = equal_weight_rebased([[100.0, 110.0], [200.0, 220.0]])
    assert len(avg) == 2
    assert avg[0] == 100.0
    assert round(avg[1], 6) == 110.0


def test_equal_weight_averages_divergence():
    # One +20%, one -20% -> flat at 100.
    avg = equal_weight_rebased([[100.0, 120.0], [100.0, 80.0]])
    assert round(avg[-1], 6) == 100.0


def test_tail_alignment_to_shortest():
    avg = equal_weight_rebased([[50.0, 100.0, 110.0], [200.0, 220.0]])
    assert len(avg) == 2  # truncated to the shorter series


def test_single_series():
    avg = equal_weight_rebased([[100.0, 105.0, 110.0]])
    assert [round(v, 6) for v in avg] == [100.0, 105.0, 110.0]


def test_bad_input():
    assert equal_weight_rebased([]) == []
    assert equal_weight_rebased([[100.0]]) == []
    assert equal_weight_rebased([[], []]) == []
