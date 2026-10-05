"""Manual "Run Scan" trigger + scan history endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_market_provider_dep, get_news_provider_dep, get_settings_dep
from app.config import Settings
from app.database import get_db
from app.models import ScanRun
from app.schemas import ScanRunOut
from app.services.market_data.base import MarketDataProvider
from app.services.news.base import NewsProvider
from app.services.scanner.orchestrator import run_scan

router = APIRouter(prefix="/api/scan", tags=["scan"])


@router.post("/run", response_model=ScanRunOut)
async def trigger_scan(
    db: Session = Depends(get_db),
    market_provider: MarketDataProvider = Depends(get_market_provider_dep),
    news_provider: NewsProvider = Depends(get_news_provider_dep),
    settings: Settings = Depends(get_settings_dep),
):
    return await run_scan(db, market_provider, news_provider, settings, trigger="manual")


@router.get("/latest", response_model=Optional[ScanRunOut])
def latest_scan(db: Session = Depends(get_db)):
    return (
        db.query(ScanRun)
        .filter(ScanRun.status == "completed")
        .order_by(ScanRun.finished_at.desc())
        .first()
    )


@router.get("/history", response_model=list[ScanRunOut])
def scan_history(limit: int = 20, db: Session = Depends(get_db)):
    return (
        db.query(ScanRun)
        .order_by(ScanRun.started_at.desc())
        .limit(limit)
        .all()
    )
