"""Caching layer in front of a MarketDataProvider.

Avoids re-requesting OHLCV history for a symbol more often than
``cache_ttl_seconds``, and isolates cached data by provider. This lets the
scanner process hundreds of symbols without hammering a free/rate-limited
API.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import PriceBar
from app.services.market_data.base import MarketDataProvider
from app.services.scanner.trend import completed_daily_candles

logger = logging.getLogger(__name__)


class MarketDataService:
    def __init__(self, provider: MarketDataProvider, settings: Settings):
        self.provider = provider
        self.settings = settings

    def _cached_symbols_fresh(self, db: Session, symbols: List[str]) -> Dict[str, bool]:
        ttl = dt.timedelta(seconds=self.settings.cache_ttl_seconds)
        now = dt.datetime.utcnow()
        freshness: Dict[str, bool] = {}

        rows = (
            db.query(PriceBar.symbol, PriceBar.date, PriceBar.fetched_at)
            .filter(PriceBar.symbol.in_(symbols), PriceBar.source == self.provider.name)
            .all()
        )
        latest_by_symbol: Dict[str, tuple] = {}
        for symbol, date_, fetched_at in rows:
            prev = latest_by_symbol.get(symbol)
            if prev is None or date_ > prev[0]:
                latest_by_symbol[symbol] = (date_, fetched_at)

        for symbol in symbols:
            latest = latest_by_symbol.get(symbol)
            if not latest:
                freshness[symbol] = False
                continue
            latest_date, fetched_at = latest
            freshness[symbol] = (now - fetched_at) < ttl
        return freshness

    def _load_from_cache(self, db: Session, symbol: str) -> Optional[pd.DataFrame]:
        rows = (
            db.query(PriceBar)
            .filter(PriceBar.symbol == symbol, PriceBar.source == self.provider.name)
            .order_by(PriceBar.date.asc())
            .all()
        )
        if not rows:
            return None
        df = pd.DataFrame(
            {
                "open": [r.open for r in rows],
                "high": [r.high for r in rows],
                "low": [r.low for r in rows],
                "close": [r.close for r in rows],
                "volume": [r.volume for r in rows],
            },
            index=pd.to_datetime([r.date for r in rows]),
        )
        return df

    def _store_in_cache(self, db: Session, symbol: str, df: pd.DataFrame) -> None:
        db.execute(delete(PriceBar).where(PriceBar.symbol == symbol))
        now = dt.datetime.utcnow()
        for idx, row in df.iterrows():
            db.add(
                PriceBar(
                    symbol=symbol,
                    date=idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                    source=self.provider.name,
                    fetched_at=now,
                )
            )
        db.commit()

    async def get_history(
        self, db: Session, symbols: List[str], lookback_days: int = 400
    ) -> Dict[str, Optional[pd.DataFrame]]:
        freshness = self._cached_symbols_fresh(db, symbols)
        stale_symbols = [s for s in symbols if not freshness.get(s, False)]
        result: Dict[str, Optional[pd.DataFrame]] = {}

        if stale_symbols:
            logger.info("Fetching fresh data for %d/%d symbols via %s", len(stale_symbols), len(symbols), self.provider.name)
            fresh_data = await self.provider.get_daily_history(stale_symbols, lookback_days=lookback_days)
            for symbol, df in fresh_data.items():
                if df is not None and not df.empty:
                    completed = completed_daily_candles(df)
                    if not completed.empty:
                        self._store_in_cache(db, symbol, completed)

        for symbol in symbols:
            result[symbol] = self._load_from_cache(db, symbol)

        return result
