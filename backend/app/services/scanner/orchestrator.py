"""Orchestrates a full scan run: fetch data -> compute indicators -> score ->
risk/reward -> persist results. A failure for one symbol never aborts the
whole scan - it is recorded as "Data unavailable" and scanning continues.
"""
from __future__ import annotations

import json
import logging
from typing import List

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import ScanResult, ScanRun, Stock
from app.seed import online_universe
from app.services.cache.market_data_service import MarketDataService
from app.services.cache.news_cache_service import NewsCacheService
from app.services.indicators.calculator import summarize_latest, validate_ohlcv
from app.services.market_context.service import MarketContext, get_market_context
from app.services.market_data.base import MarketDataProvider
from app.services.news.base import NewsProvider
from app.services.scanner.breakout import detect_setup
from app.services.scanner.risk_reward import compute_risk_reward
from app.services.scanner.scoring import compute_score

logger = logging.getLogger(__name__)

MIN_BARS_REQUIRED = 60


async def run_scan(
    db: Session,
    market_provider: MarketDataProvider,
    news_provider: NewsProvider,
    settings: Settings,
    trigger: str = "manual",
) -> ScanRun:
    if market_provider.name == "yfinance":
        await online_universe.refresh(db)
    stocks: List[Stock] = db.query(Stock).filter(Stock.is_active.is_(True), Stock.source != "csv_import").all()

    scan_run = ScanRun(status="running", trigger=trigger)
    db.add(scan_run)
    db.commit()
    db.refresh(scan_run)

    market_data_service = MarketDataService(market_provider, settings)
    news_cache_service = NewsCacheService(news_provider, settings)

    market_context: MarketContext = await get_market_context(market_provider)

    symbols = [s.symbol for s in stocks]
    history = await market_data_service.get_history(db, symbols, lookback_days=400)

    scanned, failed = 0, 0

    for stock in stocks:
        df = history.get(stock.symbol)
        try:
            if df is None or not validate_ohlcv(df) or len(df) < MIN_BARS_REQUIRED:
                failed += 1
                db.add(
                    ScanResult(
                        scan_run_id=scan_run.id,
                        symbol=stock.symbol,
                        company_name=stock.company_name,
                        sector=stock.sector,
                        data_available=False,
                        error_message="Data unavailable",
                        status_label="AVOID / WEAK SETUP",
                        reasons_json="[]",
                        warnings_json=json.dumps(["Data unavailable for this symbol"]),
                        news_sentiment="unavailable",
                        data_source=market_provider.name,
                    )
                )
                continue

            ind = summarize_latest(df)
            news_result = await news_cache_service.get_news(db, stock.symbol, stock.company_name)
            setup = detect_setup(ind)
            rr = compute_risk_reward(setup.setup_type, ind)
            score = compute_score(
                ind,
                news_result.aggregate_sentiment,
                market_context.trend,
                market_context.nifty50_change_pct,
            )

            reasons = score.reasons + setup.reasons
            warnings = score.warnings + rr.warnings
            news_sentiment = news_result.aggregate_sentiment or "unavailable"

            db.add(
                ScanResult(
                    scan_run_id=scan_run.id,
                    symbol=stock.symbol,
                    company_name=stock.company_name,
                    sector=stock.sector,
                    data_available=True,
                    error_message="",
                    price=ind.price,
                    daily_change_pct=ind.daily_change_pct,
                    ema20=ind.ema20,
                    ema50=ind.ema50,
                    rsi14=ind.rsi14,
                    macd=ind.macd,
                    macd_signal=ind.macd_signal,
                    macd_hist=ind.macd_hist,
                    volume=ind.volume,
                    avg_volume20=ind.avg_volume20,
                    atr14=ind.atr14,
                    high_52w=ind.high_52w,
                    distance_from_high_pct=ind.distance_from_high_pct,
                    recent_support=ind.recent_support,
                    recent_resistance=ind.recent_resistance,
                    technical_score=score.technical_score,
                    news_score=score.news_score,
                    market_score=score.market_score,
                    total_score=score.total_score,
                    status_label=score.status_label,
                    setup_type=setup.setup_type,
                    entry=rr.entry,
                    stop_loss=rr.stop_loss,
                    target1=rr.target1,
                    target2=rr.target2,
                    risk_reward=rr.risk_reward,
                    reasons_json=json.dumps(reasons),
                    warnings_json=json.dumps(warnings),
                    news_sentiment=news_sentiment,
                    data_source=market_provider.name,
                )
            )
            scanned += 1
        except Exception as exc:  # never let one bad symbol kill the whole scan
            logger.exception("Scan failed for %s", stock.symbol)
            failed += 1
            db.add(
                ScanResult(
                    scan_run_id=scan_run.id,
                    symbol=stock.symbol,
                    company_name=stock.company_name,
                    sector=stock.sector,
                    data_available=False,
                    error_message=f"Data unavailable ({exc})"[:255],
                    status_label="AVOID / WEAK SETUP",
                    reasons_json="[]",
                    warnings_json=json.dumps(["Data unavailable for this symbol"]),
                    news_sentiment="unavailable",
                    data_source=market_provider.name,
                )
            )

    scan_run.stocks_scanned = scanned
    scan_run.stocks_failed = failed
    scan_run.status = "completed"
    import datetime as dt

    scan_run.finished_at = dt.datetime.utcnow()
    db.commit()
    db.refresh(scan_run)
    return scan_run
