"""Tests that the scanner never crashes on missing/partial market data."""
from __future__ import annotations

import pytest

from app.config import get_settings
from app.models import ScanResult, ScanRun, Stock
from app.services.market_data.base import MarketDataProvider, Quote
from app.services.news.base import NewsProvider, NewsResult
from app.services.scanner.orchestrator import run_scan
from tests.conftest import make_ohlcv


class PartialFailureMarketDataProvider(MarketDataProvider):
    name = "fake_partial"
    is_delayed = True

    async def get_daily_history(self, symbols, lookback_days: int = 400):
        result = {}
        for symbol in symbols:
            if symbol == "MISSING":
                result[symbol] = None
            elif symbol == "TOOSHORT":
                result[symbol] = make_ohlcv(5)
            else:
                result[symbol] = make_ohlcv(300)
        return result

    async def get_index_quote(self, index_symbol: str):
        return Quote(symbol=index_symbol, price=20000, change_pct=0.5, source="fake", is_delayed=True, timestamp="now")


class AlwaysUnavailableNewsProvider(NewsProvider):
    name = "fake_news"

    async def get_news(self, symbol: str, company_name: str = ""):
        return NewsResult(headlines=[], aggregate_sentiment=None, provider=self.name)


@pytest.mark.asyncio
async def test_scan_marks_missing_symbol_unavailable_and_continues(db_session):
    db_session.add_all(
        [
            Stock(symbol="GOOD", company_name="Good Co", is_active=True),
            Stock(symbol="MISSING", company_name="Missing Co", is_active=True),
            Stock(symbol="TOOSHORT", company_name="Too Short Co", is_active=True),
        ]
    )
    db_session.commit()

    settings = get_settings()
    scan_run = await run_scan(
        db_session,
        PartialFailureMarketDataProvider(),
        AlwaysUnavailableNewsProvider(),
        settings,
        trigger="manual",
    )

    assert scan_run.status == "completed"
    assert scan_run.stocks_scanned == 1
    assert scan_run.stocks_failed == 2

    results = {r.symbol: r for r in db_session.query(ScanResult).filter(ScanResult.scan_run_id == scan_run.id)}
    assert results["GOOD"].data_available is True
    assert results["MISSING"].data_available is False
    assert results["MISSING"].error_message == "Data unavailable"
    assert results["TOOSHORT"].data_available is False


class ExplodingMarketDataProvider(MarketDataProvider):
    name = "fake_exploding"
    is_delayed = True

    async def get_daily_history(self, symbols, lookback_days: int = 400):
        return {s: make_ohlcv(300) for s in symbols}

    async def get_index_quote(self, index_symbol: str):
        return Quote(symbol=index_symbol, price=20000, change_pct=0.5, source="fake", is_delayed=True, timestamp="now")


class ExplodingNewsProvider(NewsProvider):
    name = "fake_exploding_news"

    async def get_news(self, symbol: str, company_name: str = ""):
        raise RuntimeError("simulated news provider outage")


@pytest.mark.asyncio
async def test_scan_survives_unexpected_exception_per_symbol(db_session):
    db_session.add(Stock(symbol="GOOD", company_name="Good Co", is_active=True))
    db_session.commit()

    settings = get_settings()
    # News provider raising should be caught inside the cache layer, so the
    # scan should still complete successfully for this symbol.
    scan_run = await run_scan(
        db_session, ExplodingMarketDataProvider(), ExplodingNewsProvider(), settings, trigger="manual"
    )
    assert scan_run.status == "completed"
    assert scan_run.stocks_scanned + scan_run.stocks_failed == 1
