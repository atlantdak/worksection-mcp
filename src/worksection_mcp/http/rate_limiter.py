"""Client-side pacing that backs off when the API says 429 and recovers slowly."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from worksection_mcp.logging_setup import get_logger

logger = get_logger("http.rate_limiter")


class AdaptiveRateLimiter:
    """Spaces outgoing requests, halving the rate on 429 and easing back on success."""

    def __init__(
        self,
        rate_per_second: float,
        *,
        min_rate: float = 0.2,
        max_rate: float | None = None,
        recovery_successes: int = 10,
        backoff_factor: float = 0.5,
        time_source: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be positive")
        self._rate = rate_per_second
        self._min_rate = min(min_rate, rate_per_second)
        self._max_rate = max_rate if max_rate is not None else rate_per_second
        self._recovery_successes = max(1, recovery_successes)
        self._backoff_factor = backoff_factor
        self._time = time_source
        self._sleep = sleeper
        self._lock = asyncio.Lock()
        self._next_allowed = float("-inf")
        self._successes = 0

    @property
    def current_rate(self) -> float:
        return self._rate

    async def acquire(self) -> None:
        """Block until the next request is allowed to go out."""
        async with self._lock:
            now = self._time()
            wait = self._next_allowed - now
            if wait > 0:
                await self._sleep(wait)
                now = self._time()
            self._next_allowed = now + 1.0 / self._rate

    def record_success(self) -> None:
        self._successes += 1
        if self._successes < self._recovery_successes or self._rate >= self._max_rate:
            return
        self._successes = 0
        self._rate = min(self._max_rate, self._rate * 1.25)

    def record_rate_limited(self, retry_after: float | None = None) -> None:
        """Halve the rate, and honour a server-supplied Retry-After."""
        self._successes = 0
        self._rate = max(self._min_rate, self._rate * self._backoff_factor)
        penalty = retry_after if retry_after is not None else 1.0 / self._rate
        self._next_allowed = max(self._next_allowed, self._time() + penalty)
        logger.warning("rate limited; pacing down to %.2f req/s for %.1fs", self._rate, penalty)
