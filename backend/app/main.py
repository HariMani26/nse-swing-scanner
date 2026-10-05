"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_dashboard, routes_market, routes_scan, routes_stocks, routes_trading
from app.config import get_settings
from app.database import init_db, session_scope
from app.scheduler import start_scheduler, stop_scheduler
from app.seed import seed_universe_if_empty

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with session_scope() as db:
        await seed_universe_if_empty(db, settings)
    start_scheduler()
    logger.info("NSE Swing Scanner backend started (market_data=%s, news=%s)", settings.market_data_provider, settings.news_provider)
    yield
    stop_scheduler()


app = FastAPI(
    title="NSE Swing Scanner API",
    description=(
        "Personal-use technical screening tool for NSE swing trading. "
        "This is NOT financial advice and does NOT predict the market."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_dashboard.router)
app.include_router(routes_stocks.router)
app.include_router(routes_scan.router)
app.include_router(routes_market.router)
app.include_router(routes_trading.router)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "market_data_provider": settings.market_data_provider,
        "news_provider": settings.news_provider,
    }
