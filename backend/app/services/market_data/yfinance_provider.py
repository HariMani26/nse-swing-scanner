"""Free/delayed real market data provider backed by Yahoo Finance (yfinance).

This is an unofficial, best-effort free data source with delayed quotes.
It is NOT real-time and NOT guaranteed to be reliable - use it only for
personal, non-commercial screening. Swap this module out for a licensed
provider by implementing ``MarketDataProvider`` and updating ``factory.py``.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import math
from typing import Dict, List, Optional

import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import get_settings
from app.services.market_data.base import MarketDataProvider, Quote
from app.services.market_data.rate_limiter import AsyncRateLimiter

logger = logging.getLogger(__name__)
settings = get_settings()

_NSE_INDEX_MAP = {
    "NIFTY50": "^NSEI",
    "NIFTY500": "^CRSLDX",
}


def _to_yahoo_symbol(symbol: str) -> str:
    if symbol.startswith("^"):
        return symbol
    return f"{symbol}.NS"


class RetryableProviderError(Exception):
    """Raised for transient errors that should be retried with backoff."""


class YFinanceMarketDataProvider(MarketDataProvider):
    name = "yfinance"
    is_delayed = True

    def __init__(self) -> None:
        self._limiter = AsyncRateLimiter(
            max_calls=settings.rate_limit_max_calls,
            period_seconds=settings.rate_limit_period_seconds,
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(RetryableProviderError),
    )
    async def _download_batch(self, yahoo_symbols: List[str], lookback_days: int) -> pd.DataFrame:
        await self._limiter.acquire()
        try:
            import yfinance as yf

            period_days = max(lookback_days + 10, 60)

            def _run() -> pd.DataFrame:
                return yf.download(
                    tickers=yahoo_symbols,
                    start=(dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=period_days)).date().isoformat(),
                    interval="1d",
                    group_by="ticker",
                    auto_adjust=False,
                    threads=True,
                    progress=False,
                    timeout=10,
                )

            return await asyncio.to_thread(_run)
        except Exception as exc:  # network / provider hiccup -> retry
            raise RetryableProviderError(str(exc)) from exc

    async def get_daily_history(
        self, symbols: List[str], lookback_days: int = 400
    ) -> Dict[str, Optional[pd.DataFrame]]:
        result: Dict[str, Optional[pd.DataFrame]] = {s: None for s in symbols}
        if not symbols:
            return result

        yahoo_symbols = [_to_yahoo_symbol(s) for s in symbols]
        batch_size = 50  # Yahoo tolerates reasonably large batches
        for i in range(0, len(symbols), batch_size):
            chunk = symbols[i : i + batch_size]
            yahoo_chunk = yahoo_symbols[i : i + batch_size]
            try:
                raw = await self._download_batch(yahoo_chunk, lookback_days)
            except Exception as exc:  # give up on this batch, mark all as unavailable
                logger.warning("yfinance batch failed after retries: %s", exc)
                continue

            for symbol, yahoo_symbol in zip(chunk, yahoo_chunk):
                try:
                    if isinstance(raw.columns, pd.MultiIndex):
                        df = raw[yahoo_symbol]
                    else:
                        df = raw
                    df = df.rename(
                        columns={
                            "Open": "open",
                            "High": "high",
                            "Low": "low",
                            "Close": "close",
                            "Volume": "volume",
                        }
                    )[["open", "high", "low", "close", "volume"]].dropna()
                    if df.empty:
                        result[symbol] = None
                    else:
                        result[symbol] = df
                except Exception as exc:
                    logger.info("No data for %s: %s", symbol, exc)
                    result[symbol] = None
        return result

    async def get_stock_quote(self, symbol: str) -> Optional[Quote]:
        await self._limiter.acquire()
        try:
            import yfinance as yf

            def download() -> pd.DataFrame:
                return yf.Ticker(_to_yahoo_symbol(symbol)).history(
                    period="5d", interval="1m", auto_adjust=False, timeout=10,
                    raise_errors=True,
                )

            history = await asyncio.wait_for(asyncio.to_thread(download), timeout=20)
            history = history.dropna(subset=["Close"])
            if history.empty or history.index.tz is None:
                return None
            dates = history.index.tz_convert("Asia/Kolkata").date
            previous = history.loc[dates < dates[-1]]
            if previous.empty:
                return None
            price = float(history["Close"].iloc[-1])
            previous_close = float(previous["Close"].iloc[-1])
            if not math.isfinite(price) or not math.isfinite(previous_close) or min(price, previous_close) <= 0:
                return None
            return Quote(
                symbol=symbol, price=round(price, 2),
                change_pct=round((price / previous_close - 1) * 100, 2),
                source=self.name, is_delayed=True,
                timestamp=history.index[-1].tz_convert("UTC").isoformat(),
            )
        except Exception as exc:
            logger.warning("Yahoo quote unavailable for %s: %s", symbol, exc)
            return None

    async def get_timeframe_history(self, symbols: List[str], interval: str) -> Dict[str, Optional[pd.DataFrame]]:
        periods = {"1d": "5y", "60m": "2y", "15m": "60d", "5m": "60d", "1m": "5d"}
        if interval not in periods or not symbols:
            return {symbol: None for symbol in symbols}
        await self._limiter.acquire()
        result = {symbol: None for symbol in symbols}
        try:
            import yfinance as yf

            def download():
                return yf.download([_to_yahoo_symbol(symbol) for symbol in symbols],
                                   period=periods[interval], interval=interval, group_by="ticker",
                                   auto_adjust=True, threads=4, progress=False, timeout=12)

            raw = await asyncio.wait_for(asyncio.to_thread(download), timeout=40)
            for symbol in symbols:
                try:
                    frame = raw[_to_yahoo_symbol(symbol)] if isinstance(raw.columns, pd.MultiIndex) else raw
                    frame = frame.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
                    if not frame.empty:
                        result[symbol] = frame
                except (KeyError, ValueError):
                    continue
        except Exception as exc:
            logger.warning("%s candle request unavailable: %s", interval, exc)
        return result

    async def get_stock_metadata(self, symbol: str) -> dict:
        await self._limiter.acquire()
        try:
            import yfinance as yf

            info = await asyncio.wait_for(asyncio.to_thread(lambda: yf.Ticker(_to_yahoo_symbol(symbol)).get_info()), timeout=15)
            return {"sector": info.get("sector"), "industry": info.get("industry"),
                    "bid": info.get("bid"), "ask": info.get("ask")}
        except Exception:
            return {}

    async def get_index_quote(self, index_symbol: str) -> Optional[Quote]:
        yahoo_symbol = _NSE_INDEX_MAP.get(index_symbol, index_symbol)
        history = await self.get_daily_history([yahoo_symbol], lookback_days=5)
        df = history.get(yahoo_symbol)
        if df is None or df.empty or len(df) < 2:
            return None
        last = df.iloc[-1]
        prev = df.iloc[-2]
        change_pct = (last["close"] - prev["close"]) / prev["close"] * 100
        return Quote(
            symbol=index_symbol,
            price=round(float(last["close"]), 2),
            change_pct=round(float(change_pct), 2),
            source="yfinance",
            is_delayed=True,
            timestamp=dt.datetime.utcnow().isoformat(),
        )
