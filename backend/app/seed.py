"""Synchronize the NSE equity universe from a public JSON instrument catalogue."""
from __future__ import annotations

import asyncio
import gzip
import json
import logging
import re
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Stock

logger = logging.getLogger(__name__)
CATALOGUE_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
CATALOGUE_SOURCE = "upstox_nse"


def parse_equity_catalogue(payload: object) -> dict[str, str]:
    if not isinstance(payload, list):
        raise ValueError("The online instrument catalogue is not a JSON array")
    equities = {}
    for row in payload:
        if not isinstance(row, dict) or row.get("segment") != "NSE_EQ" or row.get("instrument_type") not in ("EQ", "BE", "RR"):
            continue
        symbol = row.get("trading_symbol")
        name = row.get("name")
        if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z0-9&_.-]{1,32}", symbol):
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        equities[symbol] = name.strip()[:255]
    if not equities:
        raise ValueError("The online catalogue contains no valid NSE equities")
    return equities


def sync_equity_catalogue(db: Session, equities: dict[str, str]) -> int:
    existing = {stock.symbol: stock for stock in db.query(Stock).all()}
    for symbol, name in equities.items():
        stock = existing.get(symbol)
        if stock is None:
            db.add(Stock(symbol=symbol, company_name=name, sector="", source=CATALOGUE_SOURCE, is_active=True))
        elif stock.source != "manual":
            if stock.source == "csv_import":
                stock.is_active = True
            stock.company_name = name
            stock.sector = ""
            stock.source = CATALOGUE_SOURCE
    for symbol, stock in existing.items():
        if symbol not in equities and stock.source in ("csv_import", CATALOGUE_SOURCE):
            stock.is_active = False
    db.commit()
    return len(equities)


class OnlineUniverse:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._last_attempt = float("-inf")
        self._last_success = float("-inf")
        self.last_synced_at: str | None = None
        self.error: str | None = None
        self.instrument_count = 0

    def status(self) -> dict:
        return {
            "source": CATALOGUE_SOURCE, "source_url": CATALOGUE_URL,
            "last_synced_at": self.last_synced_at, "instrument_count": self.instrument_count,
            "error": self.error, "refresh_interval_seconds": 86400,
            "is_stale": self.last_synced_at is None or time.monotonic() - self._last_success >= 86400,
        }

    async def refresh(self, db: Session, force: bool = False) -> dict:
        async with self._lock:
            now = time.monotonic()
            if now - self._last_attempt < 300 or (not force and now - self._last_success < 86400):
                return self.status()
            self._last_attempt = now
            try:
                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                    response = await client.get(CATALOGUE_URL)
                    response.raise_for_status()
                content = response.content
                if content.startswith(b"\x1f\x8b"):
                    content = gzip.decompress(content)
                equities = parse_equity_catalogue(json.loads(content))
                if len(equities) < 500:
                    raise ValueError("Online NSE catalogue appears incomplete; previous universe retained")
                self.instrument_count = sync_equity_catalogue(db, equities)
                self._last_success = time.monotonic()
                self.last_synced_at = datetime.now(timezone.utc).isoformat()
                self.error = None
                logger.info("Synchronized %d equities from online NSE JSON catalogue", self.instrument_count)
            except Exception as exc:
                db.rollback()
                self.error = "Online stock catalogue unavailable; previous database universe retained."
                logger.warning("NSE catalogue refresh failed: %s", exc)
            return self.status()


online_universe = OnlineUniverse()


async def seed_universe_if_empty(db: Session, settings: Settings) -> None:
    await online_universe.refresh(db)
