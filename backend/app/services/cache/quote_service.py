"""Shared, bounded quote cache with request coalescing and stale fallback."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict
from datetime import datetime, timezone

from app.services.market_data.base import MarketDataProvider
from app.utils.market_hours import is_market_open

logger = logging.getLogger(__name__)


class QuoteService:
    def __init__(self):
        self._cache: dict[tuple[str, str], dict] = {}
        self._lock = asyncio.Lock()

    async def get_quote(self, provider: MarketDataProvider, symbol: str) -> dict:
        key = (provider.name, symbol)
        async with self._lock:
            cached = self._cache.get(key)
            if cached is None or time.monotonic() - cached["checked"] >= 60:
                try:
                    quote = await provider.get_stock_quote(symbol)
                except Exception:
                    logger.exception("Quote request failed for %s", symbol)
                    quote = None
                cached = {
                    "checked": time.monotonic(),
                    "quote": asdict(quote) if quote else cached["quote"] if cached else None,
                    "fetched_at": datetime.now(timezone.utc).isoformat() if quote else cached["fetched_at"] if cached else None,
                    "failed": quote is None,
                }
                if key not in self._cache and len(self._cache) >= 500:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[key] = cached
        quote = cached["quote"]
        now = datetime.now(timezone.utc)
        timestamp = datetime.fromisoformat(quote["timestamp"]) if quote else None
        age = max(0, (now - timestamp.replace(tzinfo=timestamp.tzinfo or timezone.utc)).total_seconds()) if timestamp else None
        market_open = is_market_open(now)
        stale = cached["failed"] or (age is not None and age > (120 if market_open else 4 * 86400))
        return {
            "symbol": symbol, "price": quote["price"] if quote else None,
            "change_pct": quote["change_pct"] if quote else None,
            "source": provider.name, "is_delayed": provider.is_delayed,
            "timestamp": quote["timestamp"] if quote else None,
            "fetched_at": cached["fetched_at"], "age_seconds": round(age) if age is not None else None,
            "is_stale": stale, "market_open": market_open, "refresh_seconds": 60,
            "error": "Latest quote unavailable from provider." if cached["failed"] else None,
        }