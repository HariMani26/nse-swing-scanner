"""Determines overall market trend from NIFTY 50 / NIFTY 500 index quotes."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from app.services.market_data.base import MarketDataProvider

BULLISH_THRESHOLD = 0.4
BEARISH_THRESHOLD = -0.4


@dataclass
class MarketContext:
    nifty50_value: float
    nifty50_change_pct: float
    nifty500_value: float
    nifty500_change_pct: float
    trend: str
    source: str
    fetched_at: dt.datetime


async def get_market_context(provider: MarketDataProvider) -> MarketContext:
    n50 = await provider.get_index_quote("NIFTY50")
    n500 = await provider.get_index_quote("NIFTY500")

    n50_change = n50.change_pct if n50 else 0.0
    n500_change = n500.change_pct if n500 else 0.0
    avg_change = (n50_change + n500_change) / 2

    if avg_change >= BULLISH_THRESHOLD:
        trend = "bullish"
    elif avg_change <= BEARISH_THRESHOLD:
        trend = "bearish"
    else:
        trend = "neutral"

    return MarketContext(
        nifty50_value=n50.price if n50 else 0.0,
        nifty50_change_pct=n50_change,
        nifty500_value=n500.price if n500 else 0.0,
        nifty500_change_pct=n500_change,
        trend=trend,
        source=provider.name,
        fetched_at=dt.datetime.utcnow(),
    )
