"""Tests for the news service: mock provider, sentiment classification, and
the "News data unavailable" contract (never fabricate a sentiment score).
"""
from __future__ import annotations

import asyncio

from app.services.news.mock_provider import MockNewsProvider
from app.services.news.sentiment import aggregate_sentiment, classify_headline


def test_classify_headline_positive():
    assert classify_headline("Company reports record profit growth") == "strongly_positive"
    assert classify_headline("Company wins new contract") == "positive"


def test_classify_headline_negative():
    assert classify_headline("Company under fraud investigation") == "strongly_negative"
    assert classify_headline("Company reports loss this quarter") == "negative"


def test_classify_headline_neutral_when_no_keywords_match():
    assert classify_headline("Company holds annual general meeting") == "neutral"


def test_aggregate_sentiment_rounds_to_nearest_label():
    assert aggregate_sentiment(["positive", "positive"]) == "positive"
    assert aggregate_sentiment(["strongly_positive", "negative"]) == "neutral"
    assert aggregate_sentiment([]) == "neutral"


def test_mock_news_provider_is_deterministic_across_calls():
    provider = MockNewsProvider()

    async def _fetch():
        r1 = await provider.get_news("RELIANCE", "Reliance Industries")
        r2 = await provider.get_news("RELIANCE", "Reliance Industries")
        return r1, r2

    r1, r2 = asyncio.run(_fetch())
    assert [h.headline for h in r1.headlines] == [h.headline for h in r2.headlines]
    assert r1.aggregate_sentiment == r2.aggregate_sentiment


def test_mock_news_provider_reports_unavailable_for_some_symbols():
    provider = MockNewsProvider()

    async def _find_unavailable():
        for i in range(50):
            symbol = f"TESTSYM{i}"
            result = await provider.get_news(symbol, symbol)
            if result.aggregate_sentiment is None:
                return result
        return None

    result = asyncio.run(_find_unavailable())
    assert result is not None
    assert result.headlines == []
    assert result.aggregate_sentiment is None
