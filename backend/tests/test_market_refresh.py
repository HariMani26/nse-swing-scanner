import asyncio
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app.config import Settings
from app.models import PriceBar
from app.services.cache.market_data_service import MarketDataService
from app.services.cache.quote_service import QuoteService
from app.services.market_data.base import Quote
from app.services.market_data.mock_provider import MockMarketDataProvider
from app.services.market_data.yfinance_provider import YFinanceMarketDataProvider
from app.schemas import DailyAnalysisOut, StockQuoteOut
from app.services.scanner.trend import analyze_daily_trend


class QuoteProvider(MockMarketDataProvider):
    calls = 0
    fail = False

    async def get_stock_quote(self, symbol):
        self.calls += 1
        if self.fail:
            return None
        return Quote(symbol, 100, 1, self.name, True, datetime.now(timezone.utc).isoformat())


@pytest.mark.asyncio
async def test_quotes_coalesce_and_preserve_stale_value():
    provider = QuoteProvider()
    service = QuoteService()
    quotes = await asyncio.gather(*(service.get_quote(provider, "TEST") for _ in range(4)))
    assert provider.calls == 1
    assert all(quote["price"] == 100 for quote in quotes)
    provider.fail = True
    service._cache[(provider.name, "TEST")]["checked"] -= 61
    stale = await service.get_quote(provider, "TEST")
    assert stale["price"] == 100
    assert stale["is_stale"]
    assert stale["timestamp"] == quotes[0]["timestamp"]
    assert stale["fetched_at"] == quotes[0]["fetched_at"]
    await service.get_quote(provider, "TEST")
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_unavailable_quote_does_not_invent_price():
    provider = QuoteProvider()
    provider.fail = True
    result = await QuoteService().get_quote(provider, "TEST")
    assert result["price"] is None
    assert result["is_stale"]
    assert result["error"]
    assert StockQuoteOut.model_validate(result).price is None
    assert DailyAnalysisOut.model_validate(analyze_daily_trend(pd.DataFrame())).signal == "WAIT"


def test_daily_cache_respects_provider_and_ttl(db_session):
    db_session.add(PriceBar(symbol="TEST", date=datetime.now().date().isoformat(),
                            open=100, high=101, low=99, close=100, volume=1000,
                            source="mock", fetched_at=datetime.utcnow() - timedelta(hours=1)))
    db_session.commit()
    mock = MarketDataService(MockMarketDataProvider(), Settings(cache_ttl_seconds=60))
    assert not mock._cached_symbols_fresh(db_session, ["TEST"])["TEST"]
    yahoo = MarketDataService(YFinanceMarketDataProvider(), Settings())
    assert yahoo._load_from_cache(db_session, "TEST") is None
    assert not yahoo._cached_symbols_fresh(db_session, ["TEST"])["TEST"]


@pytest.mark.asyncio
async def test_yahoo_single_symbol_multiindex(monkeypatch):
    provider = YFinanceMarketDataProvider()
    columns = pd.MultiIndex.from_product([["TEST.NS"], ["Open", "High", "Low", "Close", "Volume"]])
    raw = pd.DataFrame([[100, 101, 99, 100, 1000]], columns=columns,
                       index=pd.to_datetime(["2026-09-30"]))

    async def download(*args):
        return raw

    monkeypatch.setattr(provider, "_download_batch", download)
    history = await provider.get_daily_history(["TEST"])
    assert history["TEST"]["close"].iloc[-1] == 100