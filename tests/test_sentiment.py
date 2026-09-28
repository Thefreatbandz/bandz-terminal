"""Tests for the heuristic news-sentiment classifier."""

from marketpulse import sentiment


def test_bullish_headline():
    label = sentiment.classify_sentiment(
        "Nvidia shares surge to record high on blowout earnings beat")
    assert label == "bullish"


def test_bearish_headline():
    label = sentiment.classify_sentiment(
        "Tesla shares plunge after delivery miss prompts downgrade")
    assert label == "bearish"


def test_neutral_headline():
    label = sentiment.classify_sentiment(
        "Apple announces quarterly earnings call scheduled for Thursday")
    assert label == "neutral"


def test_empty_headline_is_neutral():
    assert sentiment.classify_sentiment("") == "neutral"
    assert sentiment.classify_sentiment(None) == "neutral"


def test_more_bearish_words_wins():
    label = sentiment.classify_sentiment(
        "Stock drops on weak guidance despite deal win")
    assert label == "bearish"


def test_pill_html_contains_label_and_color():
    pill = sentiment.sentiment_pill("bullish")
    assert "BULLISH" in pill and "#39ff88" in pill
    pill = sentiment.sentiment_pill("bearish")
    assert "BEARISH" in pill and "#ff3b5c" in pill
    pill = sentiment.sentiment_pill("neutral")
    assert "NEUTRAL" in pill
    # unknown labels fall back to neutral styling, never crash
    assert "NEUTRAL" in sentiment.sentiment_pill("???")
