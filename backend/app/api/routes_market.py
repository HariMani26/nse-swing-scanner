"""Standalone market context endpoint (NIFTY 50 / NIFTY 500 / trend)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_market_provider_dep
from app.schemas import MarketContextOut
from app.services.market_context.service import get_market_context
from app.services.market_data.base import MarketDataProvider
from app.utils.market_hours import is_market_open, market_status_label

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("", response_model=MarketContextOut)
async def get_market(market_provider: MarketDataProvider = Depends(get_market_provider_dep)):
    ctx = await get_market_context(market_provider)
    return MarketContextOut(
        nifty50_value=ctx.nifty50_value,
        nifty50_change_pct=ctx.nifty50_change_pct,
        nifty500_value=ctx.nifty500_value,
        nifty500_change_pct=ctx.nifty500_change_pct,
        trend=ctx.trend,
        source=ctx.source,
        fetched_at=ctx.fetched_at,
        is_market_open=is_market_open(),
    )


@router.get("/status")
def get_market_status():
    return {"status": market_status_label()}
