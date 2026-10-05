"""Watchlist/stock universe management + stock detail endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.converters import scan_result_to_out
from app.api.deps import get_market_provider_dep, get_news_provider_dep, get_settings_dep
from app.config import Settings
from app.database import get_db
from app.models import ScanResult, ScanRun, Stock
from app.seed import online_universe
from app.schemas import CandleOut, NewsItemOut, StockCreate, StockDetailOut, StockOut, StockQuoteOut
from app.services.cache.market_data_service import MarketDataService
from app.services.cache.news_cache_service import NewsCacheService
from app.services.cache.quote_service import QuoteService
from app.services.indicators.calculator import add_indicators
from app.services.market_data.base import MarketDataProvider
from app.services.news.base import NewsProvider
from app.services.scanner.trend import analyze_daily_trend, completed_daily_candles

import pandas as pd

router = APIRouter(prefix="/api/stocks", tags=["stocks"])
quote_service = QuoteService()


@router.get("", response_model=list[StockOut])
async def list_stocks(active_only: bool = True, db: Session = Depends(get_db)):
    await online_universe.refresh(db)
    query = db.query(Stock).filter(Stock.source != "csv_import")
    if active_only:
        query = query.filter(Stock.is_active.is_(True))
    return query.order_by(Stock.symbol.asc()).all()


@router.get("/universe/status")
def universe_status():
    return online_universe.status()


@router.post("/universe/refresh")
async def refresh_universe(db: Session = Depends(get_db)):
    return await online_universe.refresh(db, force=True)


@router.post("", response_model=StockOut)
def add_stock(payload: StockCreate, db: Session = Depends(get_db)):
    symbol = payload.symbol.strip().upper()
    if not symbol:
        raise HTTPException(400, "Symbol is required")

    existing = db.query(Stock).filter(Stock.symbol == symbol).first()
    if existing:
        existing.is_active = True
        if payload.company_name:
            existing.company_name = payload.company_name
        db.commit()
        db.refresh(existing)
        return existing

    stock = Stock(
        symbol=symbol,
        company_name=payload.company_name,
        sector=payload.sector,
        source="manual",
        is_active=True,
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


@router.delete("/{symbol}")
def remove_stock(symbol: str, db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.symbol == symbol.upper()).first()
    if not stock:
        raise HTTPException(404, "Stock not found")
    stock.is_active = False
    db.commit()
    return {"symbol": symbol.upper(), "removed": True}


@router.get("/{symbol}/quote", response_model=StockQuoteOut)
async def get_stock_quote(
    symbol: str,
    db: Session = Depends(get_db),
    market_provider: MarketDataProvider = Depends(get_market_provider_dep),
):
    symbol = symbol.upper()
    if not db.query(Stock).filter(Stock.symbol == symbol, Stock.is_active.is_(True)).first():
        raise HTTPException(404, "Stock not found in active watchlist")
    return await quote_service.get_quote(market_provider, symbol)


@router.get("/{symbol}/detail", response_model=StockDetailOut)
async def get_stock_detail(
    symbol: str,
    db: Session = Depends(get_db),
    market_provider: MarketDataProvider = Depends(get_market_provider_dep),
    news_provider: NewsProvider = Depends(get_news_provider_dep),
    settings: Settings = Depends(get_settings_dep),
):
    symbol = symbol.upper()
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        raise HTTPException(404, "Stock not found in watchlist")

    latest_result = (
        db.query(ScanResult)
        .join(ScanRun, ScanResult.scan_run_id == ScanRun.id)
        .filter(ScanResult.symbol == symbol, ScanRun.status == "completed", ScanResult.data_source == market_provider.name)
        .order_by(ScanRun.finished_at.desc())
        .first()
    )

    market_data_service = MarketDataService(market_provider, settings)
    history = await market_data_service.get_history(db, [symbol], lookback_days=400)
    df = history.get(symbol)
    df = completed_daily_candles(df) if df is not None else pd.DataFrame()
    daily_analysis = analyze_daily_trend(df)

    candles: list[CandleOut] = []
    if df is not None and not df.empty:
        enriched = add_indicators(df)
        for idx, row in enriched.iterrows():
            candles.append(
                CandleOut(
                    date=idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                    ema20=None if row["ema20"] != row["ema20"] else float(row["ema20"]),
                    ema50=None if row["ema50"] != row["ema50"] else float(row["ema50"]),
                    rsi14=None if row["rsi14"] != row["rsi14"] else float(row["rsi14"]),
                    macd=None if row["macd"] != row["macd"] else float(row["macd"]),
                    macd_signal=None if row["macd_signal"] != row["macd_signal"] else float(row["macd_signal"]),
                    macd_hist=None if row["macd_hist"] != row["macd_hist"] else float(row["macd_hist"]),
                )
            )

    news_cache_service = NewsCacheService(news_provider, settings)
    news_result = await news_cache_service.get_news(db, symbol, stock.company_name)
    news_out = [
        NewsItemOut(
            headline=h.headline,
            source=h.source,
            url=h.url,
            published_at=h.published_at,
            sentiment=h.sentiment,
            provider=h.provider,
        )
        for h in news_result.headlines
    ]

    return StockDetailOut(
        stock=StockOut.model_validate(stock),
        latest_result=scan_result_to_out(latest_result) if latest_result else None,
        news=news_out,
        candles=candles,
        daily_analysis=daily_analysis,
        data_source=market_provider.name,
    )
