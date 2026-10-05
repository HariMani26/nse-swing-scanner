"""Factory that selects the configured market data provider implementation."""
from __future__ import annotations

from app.config import Settings
from app.services.market_data.base import MarketDataProvider
from app.services.market_data.mock_provider import MockMarketDataProvider


def get_market_data_provider(settings: Settings) -> MarketDataProvider:
    provider = settings.market_data_provider.lower().strip()
    if provider == "yfinance":
        from app.services.market_data.yfinance_provider import YFinanceMarketDataProvider

        return YFinanceMarketDataProvider()
    if provider != "mock":
        raise ValueError(f"Unknown MARKET_DATA_PROVIDER '{settings.market_data_provider}'")
    return MockMarketDataProvider()
