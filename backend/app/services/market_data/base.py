"""Abstract interface for market data providers.

Any new data source (paid real-time API, broker feed, etc.) should implement
this interface so the rest of the application never depends on a specific
vendor. See ``mock_provider.py`` for a zero-dependency implementation and
``yfinance_provider.py`` for a free/delayed real-data implementation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd


@dataclass
class Quote:
    symbol: str
    price: float
    change_pct: float
    source: str
    is_delayed: bool
    timestamp: str


class MarketDataProvider(ABC):
    """Base class all market data providers must implement."""

    #: short machine-readable identifier, e.g. "mock", "yfinance"
    name: str = "base"
    #: whether the data returned is free/delayed (as opposed to real-time/paid)
    is_delayed: bool = True
    supports_realtime: bool = False
    refresh_seconds: int = 60

    async def get_timeframe_history(self, symbols: List[str], interval: str) -> Dict[str, Optional[pd.DataFrame]]:
        return {symbol: None for symbol in symbols}

    async def get_stock_metadata(self, symbol: str) -> dict:
        return {}

    async def get_stock_quote(self, symbol: str) -> Optional[Quote]:
        return None

    @abstractmethod
    async def get_daily_history(
        self, symbols: List[str], lookback_days: int = 400
    ) -> Dict[str, Optional[pd.DataFrame]]:
        """Return a dict of symbol -> daily OHLCV DataFrame (or None if unavailable).

        The DataFrame must be indexed by date (ascending) with columns:
        open, high, low, close, volume.
        Implementations SHOULD batch requests where the underlying provider
        supports it, rather than issuing one request per symbol.
        """

    @abstractmethod
    async def get_index_quote(self, index_symbol: str) -> Optional[Quote]:
        """Return the latest quote for a market index such as NIFTY 50."""
