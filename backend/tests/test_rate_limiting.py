"""Tests for the async rate limiter used by real market-data/news providers."""
from __future__ import annotations

import asyncio
import time

import pytest

from app.services.market_data.rate_limiter import AsyncRateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_allows_burst_up_to_max_calls():
    limiter = AsyncRateLimiter(max_calls=3, period_seconds=1.0)
    start = time.monotonic()
    for _ in range(3):
        await limiter.acquire()
    elapsed = time.monotonic() - start
    # First `max_calls` acquisitions should not need to wait.
    assert elapsed < 0.2


@pytest.mark.asyncio
async def test_rate_limiter_throttles_beyond_max_calls():
    limiter = AsyncRateLimiter(max_calls=2, period_seconds=0.3)
    start = time.monotonic()
    for _ in range(4):
        await limiter.acquire()
    elapsed = time.monotonic() - start
    # The 3rd/4th call must wait for the window to free up.
    assert elapsed >= 0.25


@pytest.mark.asyncio
async def test_rate_limiter_is_safe_under_concurrency():
    limiter = AsyncRateLimiter(max_calls=5, period_seconds=0.5)

    async def worker():
        await limiter.acquire()
        return time.monotonic()

    results = await asyncio.gather(*(worker() for _ in range(10)))
    assert len(results) == 10
