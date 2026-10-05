"""Deterministic synthetic market data provider.

Generates repeatable, realistic-looking OHLCV series per symbol so the whole
application (scanning, scoring, charts) can run end-to-end with zero external
dependencies and zero API keys. This data is clearly labeled as "mock" / demo
data everywhere it is surfaced to the user - it is NOT real market data.
"""
from __future__ import annotations

import hashlib
import datetime as dt
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from app.services.market_data.base import MarketDataProvider, Quote


def _seed_for(symbol: str) -> int:
    return int(hashlib.md5(symbol.encode("utf-8")).hexdigest(), 16) % (2**32)


def _business_day_index(days: int) -> pd.DatetimeIndex:
    end = pd.Timestamp(dt.date.today())
    return pd.bdate_range(end=end, periods=days)


def generate_symbol_history(symbol: str, days: int = 400) -> pd.DataFrame:
    """Build a deterministic random-walk OHLCV series seeded by the symbol name."""
    rng = np.random.default_rng(_seed_for(symbol))

    base_price = float(20 + rng.integers(0, 2500))
    drift = float(rng.uniform(-0.0008, 0.0014))
    vol = float(rng.uniform(0.012, 0.03))

    daily_returns = rng.normal(drift, vol, size=days)
    close = base_price * np.cumprod(1 + daily_returns)
    close = np.maximum(close, 1.0)

    intraday_range = np.abs(rng.normal(vol * 0.6, vol * 0.3, size=days)) * close
    open_ = close * (1 + rng.normal(0, vol * 0.3, size=days))
    high = np.maximum(open_, close) + intraday_range * rng.uniform(0.2, 0.8, size=days)
    low = np.minimum(open_, close) - intraday_range * rng.uniform(0.2, 0.8, size=days)
    low = np.maximum(low, 0.5)

    base_volume = float(rng.integers(50_000, 3_000_000))
    volume_noise = rng.lognormal(mean=0, sigma=0.4, size=days)
    volume = base_volume * volume_noise
    # Occasionally simulate a volume spike (helps exercise breakout scoring).
    spike_days = rng.choice(days, size=max(1, days // 40), replace=False)
    volume[spike_days] *= rng.uniform(1.8, 3.2, size=len(spike_days))

    idx = _business_day_index(days)
    df = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=idx,
    )
    return df.round(2)


class MockMarketDataProvider(MarketDataProvider):
    name = "mock"
    is_delayed = True

    async def get_daily_history(
        self, symbols: List[str], lookback_days: int = 400
    ) -> Dict[str, Optional[pd.DataFrame]]:
        result: Dict[str, Optional[pd.DataFrame]] = {}
        for symbol in symbols:
            if not symbol or not symbol.strip():
                result[symbol] = None
                continue
            try:
                result[symbol] = generate_symbol_history(symbol, days=lookback_days)
            except Exception:
                result[symbol] = None
        return result

    async def get_index_quote(self, index_symbol: str) -> Optional[Quote]:
        df = generate_symbol_history(index_symbol, days=30)
        last = df.iloc[-1]
        prev = df.iloc[-2]
        change_pct = (last["close"] - prev["close"]) / prev["close"] * 100
        return Quote(
            symbol=index_symbol,
            price=round(float(last["close"]), 2),
            change_pct=round(float(change_pct), 2),
            source="mock",
            is_delayed=True,
            timestamp=dt.datetime.utcnow().isoformat(),
        )
