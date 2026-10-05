"""Caching layer in front of a NewsProvider (avoids re-fetching within TTL)."""
from __future__ import annotations

import datetime as dt
import logging
from typing import Optional

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import NewsItem
from app.services.news.base import NewsProvider, NewsResult, NewsHeadline
from app.services.news.sentiment import aggregate_sentiment

logger = logging.getLogger(__name__)


class NewsCacheService:
    def __init__(self, provider: NewsProvider, settings: Settings):
        self.provider = provider
        self.settings = settings

    def _is_fresh(self, db: Session, symbol: str) -> bool:
        latest = (
            db.query(NewsItem)
            .filter(NewsItem.symbol == symbol)
            .order_by(NewsItem.fetched_at.desc())
            .first()
        )
        if not latest:
            return False
        ttl = dt.timedelta(seconds=self.settings.cache_ttl_seconds)
        return (dt.datetime.utcnow() - latest.fetched_at) < ttl

    async def get_news(self, db: Session, symbol: str, company_name: str = "") -> NewsResult:
        if self._is_fresh(db, symbol):
            rows = db.query(NewsItem).filter(NewsItem.symbol == symbol).all()
            if not rows:
                return NewsResult(headlines=[], aggregate_sentiment=None, provider=self.provider.name)
            headlines = [
                NewsHeadline(
                    headline=r.headline,
                    source=r.source,
                    url=r.url,
                    published_at=r.published_at,
                    sentiment=r.sentiment,
                    provider=r.provider,
                )
                for r in rows
            ]
            return NewsResult(
                headlines=headlines,
                aggregate_sentiment=aggregate_sentiment([h.sentiment for h in headlines]),
                provider=self.provider.name,
            )

        try:
            result = await self.provider.get_news(symbol, company_name)
        except Exception as exc:
            logger.warning("News provider failed for %s: %s", symbol, exc)
            return NewsResult(headlines=[], aggregate_sentiment=None, provider=self.provider.name)

        db.execute(delete(NewsItem).where(NewsItem.symbol == symbol))
        now = dt.datetime.utcnow()
        for h in result.headlines:
            db.add(
                NewsItem(
                    symbol=symbol,
                    headline=h.headline,
                    source=h.source,
                    url=h.url,
                    published_at=h.published_at,
                    sentiment=h.sentiment,
                    provider=h.provider,
                    fetched_at=now,
                )
            )
        db.commit()
        return result
