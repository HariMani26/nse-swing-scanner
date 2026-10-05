"""Utility to determine whether the NSE cash market is currently open (IST)."""
from __future__ import annotations

import datetime as dt

import pytz

from app.config import get_settings


def is_market_open(now: dt.datetime | None = None) -> bool:
    settings = get_settings()
    tz = pytz.timezone(settings.scan_timezone)
    current = (now or dt.datetime.now(tz)).astimezone(tz)

    if current.weekday() >= 5:  # Saturday/Sunday
        return False

    open_h, open_m = (int(x) for x in settings.market_open_time.split(":"))
    close_h, close_m = (int(x) for x in settings.market_close_time.split(":"))
    open_time = current.replace(hour=open_h, minute=open_m, second=0, microsecond=0)
    close_time = current.replace(hour=close_h, minute=close_m, second=0, microsecond=0)

    return open_time <= current <= close_time


def market_status_label(now: dt.datetime | None = None) -> str:
    return "OPEN" if is_market_open(now) else "CLOSED"
