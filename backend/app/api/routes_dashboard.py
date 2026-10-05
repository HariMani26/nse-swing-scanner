"""Main dashboard endpoint: market summary + filterable top swing candidates."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.converters import scan_result_to_out
from app.api.deps import get_market_provider_dep
from app.database import get_db
from app.models import ScanResult, ScanRun
from app.schemas import DashboardOut, MarketContextOut, ScanRunOut
from app.services.market_context.service import get_market_context
from app.services.market_data.base import MarketDataProvider
from app.utils.market_hours import is_market_open

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
async def get_dashboard(
    min_score: Optional[float] = None,
    rsi_min: Optional[float] = None,
    rsi_max: Optional[float] = None,
    ema_bullish: Optional[bool] = None,
    macd_bullish: Optional[bool] = None,
    volume_breakout: Optional[bool] = None,
    near_52w_high: Optional[bool] = None,
    setup: Optional[str] = None,  # breakout | pullback
    sector: Optional[str] = None,
    db: Session = Depends(get_db),
    market_provider: MarketDataProvider = Depends(get_market_provider_dep),
):
    last_scan = (
        db.query(ScanRun)
        .filter(ScanRun.status == "completed")
        .order_by(ScanRun.finished_at.desc())
        .first()
    )

    candidates = []
    if last_scan:
        query = db.query(ScanResult).filter(
            ScanResult.scan_run_id == last_scan.id, ScanResult.data_available.is_(True)
        )
        if min_score is not None:
            query = query.filter(ScanResult.total_score >= min_score)
        if rsi_min is not None:
            query = query.filter(ScanResult.rsi14 >= rsi_min)
        if rsi_max is not None:
            query = query.filter(ScanResult.rsi14 <= rsi_max)
        if ema_bullish:
            query = query.filter(ScanResult.ema20 > ScanResult.ema50, ScanResult.price > ScanResult.ema20)
        if macd_bullish:
            query = query.filter(ScanResult.macd > ScanResult.macd_signal)
        if volume_breakout:
            query = query.filter(ScanResult.volume > ScanResult.avg_volume20 * 1.5)
        if near_52w_high:
            query = query.filter(ScanResult.distance_from_high_pct >= -7)
        if setup in ("breakout", "pullback"):
            query = query.filter(ScanResult.setup_type == setup)
        if sector:
            query = query.filter(ScanResult.sector.ilike(f"%{sector}%"))

        rows = query.order_by(ScanResult.total_score.desc()).all()
        candidates = [scan_result_to_out(r) for r in rows]

    market_context = await get_market_context(market_provider)
    market_out = MarketContextOut(
        nifty50_value=market_context.nifty50_value,
        nifty50_change_pct=market_context.nifty50_change_pct,
        nifty500_value=market_context.nifty500_value,
        nifty500_change_pct=market_context.nifty500_change_pct,
        trend=market_context.trend,
        source=market_context.source,
        fetched_at=market_context.fetched_at,
        is_market_open=is_market_open(),
    )

    return DashboardOut(
        last_scan=ScanRunOut.model_validate(last_scan) if last_scan else None,
        market=market_out,
        candidates=candidates,
    )
