"""APScheduler-based daily automatic scan (default: after NSE market close IST)."""
from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import get_settings
from app.database import session_scope
from app.services.market_data.factory import get_market_data_provider
from app.services.news.factory import get_news_provider
from app.services.scanner.orchestrator import run_scan

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _scheduled_scan_job() -> None:
    settings = get_settings()
    market_provider = get_market_data_provider(settings)
    news_provider = get_news_provider(settings)
    logger.info("Running scheduled scan...")
    with session_scope() as db:
        try:
            scan_run = await run_scan(db, market_provider, news_provider, settings, trigger="scheduled")
            logger.info(
                "Scheduled scan completed: %s scanned, %s failed",
                scan_run.stocks_scanned,
                scan_run.stocks_failed,
            )
        except Exception:
            logger.exception("Scheduled scan failed")


def start_scheduler() -> AsyncIOScheduler | None:
    global _scheduler
    settings = get_settings()
    if not settings.enable_scheduler:
        logger.info("Scheduler disabled via ENABLE_SCHEDULER=false")
        return None

    scheduler = AsyncIOScheduler(timezone=settings.scan_timezone)
    scheduler.add_job(
        lambda: asyncio.create_task(_scheduled_scan_job()),
        trigger=CronTrigger(
            hour=settings.scan_schedule_hour,
            minute=settings.scan_schedule_minute,
            day_of_week="mon-fri",
        ),
        id="daily_swing_scan",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Scheduler started: daily scan at %02d:%02d %s (Mon-Fri)",
        settings.scan_schedule_hour,
        settings.scan_schedule_minute,
        settings.scan_timezone,
    )
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
