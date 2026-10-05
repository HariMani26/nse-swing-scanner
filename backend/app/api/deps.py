"""Shared FastAPI dependencies."""
from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings
from app.services.market_data.base import MarketDataProvider
from app.services.market_data.factory import get_market_data_provider
from app.services.news.base import NewsProvider
from app.services.news.factory import get_news_provider


@lru_cache
def get_market_provider_dep() -> MarketDataProvider:
    return get_market_data_provider(get_settings())


def get_news_provider_dep() -> NewsProvider:
    return get_news_provider(get_settings())


def get_settings_dep() -> Settings:
    return get_settings()
