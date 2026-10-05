"""Abstract interface for news providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import datetime as dt
from typing import List, Optional


@dataclass
class NewsHeadline:
    headline: str
    source: str
    url: str
    published_at: dt.datetime
    sentiment: str  # strongly_positive/positive/neutral/negative/strongly_negative
    provider: str


@dataclass
class NewsResult:
    headlines: List[NewsHeadline]
    aggregate_sentiment: Optional[str]  # None => "News data unavailable"
    provider: str


class NewsProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def get_news(self, symbol: str, company_name: str = "") -> NewsResult:
        """Fetch recent news for a symbol. Must never fabricate headlines."""
