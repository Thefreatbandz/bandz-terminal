"""Tests for the signal calibration log."""

from marketpulse import calibration


def _results():
    return [
        {"symbol": "NVDA", "score": 80,
         "quote": {"change_percent": 2.5}},
        {"symbol": "AAPL", "score": 75,
         "quote": {"change_percent": -1.0}},
        {"symbol": "TSLA", "score": 40,
         "quote": {"change_percent": 5.0}},  # below threshold
        {"symbol": "BAD", "score": 90,
         "quote": {"change_percent": "n/a"}},  # bad data skipped
    ]


def test_log_and_summarize(tmp_path):
    path = str(tmp_path / "cal.jsonl")
    written = calibration.log_scan(_results(), day="2026-09-28", path=path)
    assert written == 3
    stats = calibration.summarize(min_score=70, path=path)
    assert stats["count"] == 2
    assert stats["positive_pct"] == 50.0
    assert stats["avg_change"] == 0.75
    assert stats["first_date"] == "2026-09-28"
    assert stats["last_date"] == "2026-09-28"


def test_log_dedupes_same_day_symbol(tmp_path):
    path = str(tmp_path / "cal.jsonl")
    assert calibration.log_scan(_results(), day="2026-09-28", path=path) == 3
    # second log for the same day adds nothing
    assert calibration.log_scan(_results(), day="2026-09-28", path=path) == 0
    # a new day logs again
    assert calibration.log_scan(_results(), day="2026-09-29", path=path) == 3
    stats = calibration.summarize(min_score=70, path=path)
    assert stats["count"] == 4


def test_summarize_empty_log(tmp_path):
    path = str(tmp_path / "cal.jsonl")
    stats = calibration.summarize(path=path)
    assert stats["count"] == 0
    assert stats["first_date"] is None


def test_summarize_custom_threshold(tmp_path):
    path = str(tmp_path / "cal.jsonl")
    calibration.log_scan(_results(), day="2026-09-28", path=path)
    stats = calibration.summarize(min_score=40, path=path)
    assert stats["count"] == 3  # TSLA (40) now included
