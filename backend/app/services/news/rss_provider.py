"""Free public news provider using Google News RSS search feeds.

This uses only a public RSS endpoint (no API key). It is best-effort and
unofficial - treat headlines as a convenience pointer to public news, not a
verified/complete feed. If the request fails or returns nothing, the caller
receives an "unavailable" result rather than fabricated data.
"""
from __future__ import annotations

import datetime as dt
import logging
import urllib.parse

import feedparser
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.services.market_data.rate_limiter import AsyncRateLimiter
from app.services.news.base import NewsHeadline, NewsProvider, NewsResult
from app.services.news.sentiment import aggregate_sentiment, classify_headline

logger = logging.getLogger(__name__)
settings = get_settings()

RSS_BASE_URL = "https://news.google.com/rss/search"


class RetryableNewsError(Exception):
    pass


class RssNewsProvider(NewsProvider):
    name = "rss"

    def __init__(self) -> None:
        self._limiter = AsyncRateLimiter(
            max_calls=settings.rate_limit_max_calls,
            period_seconds=settings.rate_limit_period_seconds,
        )

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(RetryableNewsError),
    )
    async def _fetch(self, query: str) -> bytes:
        await self._limiter.acquire()
        params = {"q": query, "hl": "en-IN", "gl": "IN", "ceid": "IN:en"}
        url = f"{RSS_BASE_URL}?{urllib.parse.urlencode(params)}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content
        except Exception as exc:
            raise RetryableNewsError(str(exc)) from exc

    async def get_news(self, symbol: str, company_name: str = "") -> NewsResult:
        query = f'"{company_name or symbol}" NSE'
        try:
            raw = await self._fetch(query)
        except Exception as exc:
            logger.warning("News fetch failed for %s: %s", symbol, exc)
            return NewsResult(headlines=[], aggregate_sentiment=None, provider=self.name)

        parsed = feedparser.parse(raw)
        headlines: list[NewsHeadline] = []
        for entry in parsed.entries[:8]:
            try:
                published = dt.datetime(*entry.published_parsed[:6]) if getattr(
                    entry, "published_parsed", None
                ) else dt.datetime.utcnow()
                title = entry.title
                headlines.append(
                    NewsHeadline(
                        headline=title,
                        source=getattr(entry, "source", {}).get("title", "Google News") if isinstance(
                            getattr(entry, "source", None), dict
                        ) else "Google News",
                        url=entry.link,
                        published_at=published,
                        sentiment=classify_headline(title),
                        provider=self.name,
                    )
                )
            except Exception:
                continue

        if not headlines:
            return NewsResult(headlines=[], aggregate_sentiment=None, provider=self.name)

        overall = aggregate_sentiment([h.sentiment for h in headlines])
        return NewsResult(headlines=headlines, aggregate_sentiment=overall, provider=self.name)
