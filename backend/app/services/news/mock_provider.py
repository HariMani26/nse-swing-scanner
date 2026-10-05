"""Deterministic mock news provider - clearly labeled demo data.

Produces a small, repeatable set of sample headlines per symbol so the UI and
scoring pipeline can be exercised without any external news API. Roughly 1 in
6 symbols deterministically has no headlines, exercising the
"News data unavailable" path.
"""
from __future__ import annotations

import datetime as dt
import hashlib

from app.services.news.base import NewsHeadline, NewsProvider, NewsResult
from app.services.news.sentiment import aggregate_sentiment, classify_headline

_SAMPLE_TEMPLATES = [
    ("{company} reports quarterly profit growth, beats estimates", "positive"),
    ("{company} wins large order from public sector client", "positive"),
    ("{company} announces new plant expansion", "positive"),
    ("{company} stock falls after weak quarterly guidance", "negative"),
    ("{company} under regulatory investigation over compliance lapse", "negative"),
    ("{company} board approves dividend, growth steady", "neutral"),
    ("Analysts maintain neutral stance on {company}", "neutral"),
]


def _seed(symbol: str) -> int:
    return int(hashlib.md5(symbol.encode("utf-8")).hexdigest(), 16)


class MockNewsProvider(NewsProvider):
    name = "mock"

    async def get_news(self, symbol: str, company_name: str = "") -> NewsResult:
        seed = _seed(symbol)
        if seed % 6 == 0:
            return NewsResult(headlines=[], aggregate_sentiment=None, provider=self.name)

        display_name = company_name or symbol
        count = 1 + (seed % 3)
        headlines: list[NewsHeadline] = []
        now = dt.datetime.utcnow()

        for i in range(count):
            template, _hint = _SAMPLE_TEMPLATES[(seed + i) % len(_SAMPLE_TEMPLATES)]
            headline_text = template.format(company=display_name)
            headlines.append(
                NewsHeadline(
                    headline=headline_text,
                    source="Demo News Wire (mock)",
                    url="",
                    published_at=now - dt.timedelta(hours=i * 7 + 1),
                    sentiment=classify_headline(headline_text),
                    provider=self.name,
                )
            )

        overall = aggregate_sentiment([h.sentiment for h in headlines])
        return NewsResult(headlines=headlines, aggregate_sentiment=overall, provider=self.name)
