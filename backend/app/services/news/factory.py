"""Factory that selects the configured news provider implementation."""
from __future__ import annotations

from app.config import Settings
from app.services.news.base import NewsProvider
from app.services.news.mock_provider import MockNewsProvider


def get_news_provider(settings: Settings) -> NewsProvider:
    provider = settings.news_provider.lower().strip()
    if provider == "rss":
        from app.services.news.rss_provider import RssNewsProvider

        return RssNewsProvider()
    if provider != "mock":
        raise ValueError(f"Unknown NEWS_PROVIDER '{settings.news_provider}'")
    return MockNewsProvider()
