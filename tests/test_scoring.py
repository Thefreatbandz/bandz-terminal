"""Tests use MOCK data only -- no API keys, no network, no cost.

Run:  python -m pytest tests/ -v   (from the folder containing marketpulse/)
"""

from marketpulse.scoring import calculate_score, penny_qualifies


def _quote(change_percent, price=100.0):
    # Fake quote shaped like the real FinnhubClient output.
    return {
        "symbol": "TEST",
        "price": price,
        "previous_close": 100.0,
        "change_percent": change_percent,
    }


def test_big_mover_with_news_scores_high():
    score = calculate_score(_quote(6.5), [{"headline": "x"}])
    assert score == 30 + 25 + 10  # movement + news + data quality


def test_small_mover_no_news_scores_low():
    score = calculate_score(_quote(0.5), [])
    assert score == 10  # data quality only


def test_missing_quote_scores_zero():
    assert calculate_score(None, []) == 0


def test_score_never_exceeds_100():
    assert calculate_score(_quote(50.0), [{"headline": "x"}]) <= 100


def test_penny_filter_matches():
    assert penny_qualifies(0.85, 7.5) is True


def test_penny_filter_rejects_expensive():
    assert penny_qualifies(1.50, 20.0) is False


def test_penny_filter_rejects_calm():
    assert penny_qualifies(0.50, 2.0) is False


def test_penny_filter_handles_missing_data():
    assert penny_qualifies(None, 10.0) is False
