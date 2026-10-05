"""Simple async rate limiter (token bucket) shared by real data providers.

Keeps outbound calls to third-party free APIs within their published rate
limits so the scanner never gets banned/blocked when scanning hundreds of
symbols.
"""
from __future__ import annotations

import asyncio
import time


class AsyncRateLimiter:
    def __init__(self, max_calls: int, period_seconds: float) -> None:
        self.max_calls = max(1, max_calls)
        self.period_seconds = max(0.001, period_seconds)
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            window_start = now - self.period_seconds
            self._timestamps = [t for t in self._timestamps if t >= window_start]

            if len(self._timestamps) >= self.max_calls:
                sleep_for = self._timestamps[0] + self.period_seconds - now
                if sleep_for > 0:
                    await asyncio.sleep(sleep_for)
                now = time.monotonic()
                window_start = now - self.period_seconds
                self._timestamps = [t for t in self._timestamps if t >= window_start]

            self._timestamps.append(time.monotonic())

    async def __aenter__(self) -> "AsyncRateLimiter":
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None
