from __future__ import annotations

from worksection_mcp.http.rate_limiter import AdaptiveRateLimiter


class FakeClock:
    """Monotonic clock whose only way to advance is an awaited sleep."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _limiter(clock: FakeClock, rate: float = 2.0, **kwargs: object) -> AdaptiveRateLimiter:
    return AdaptiveRateLimiter(
        rate,
        time_source=clock.time,
        sleeper=clock.sleep,
        **kwargs,  # type: ignore[arg-type]
    )


async def test_first_acquire_does_not_sleep() -> None:
    clock = FakeClock()
    await _limiter(clock).acquire()
    assert clock.sleeps == []


async def test_second_acquire_waits_for_the_interval() -> None:
    clock = FakeClock()
    limiter = _limiter(clock, rate=2.0)
    await limiter.acquire()
    await limiter.acquire()
    assert clock.sleeps == [0.5]


async def test_rate_limited_halves_the_rate() -> None:
    clock = FakeClock()
    limiter = _limiter(clock, rate=4.0)
    limiter.record_rate_limited()
    assert limiter.current_rate == 2.0


async def test_rate_never_drops_below_the_floor() -> None:
    clock = FakeClock()
    limiter = _limiter(clock, rate=1.0, min_rate=0.5)
    for _ in range(10):
        limiter.record_rate_limited()
    assert limiter.current_rate == 0.5


async def test_retry_after_forces_a_wait_of_at_least_that_long() -> None:
    clock = FakeClock()
    limiter = _limiter(clock, rate=100.0)
    limiter.record_rate_limited(retry_after=3.0)
    await limiter.acquire()
    assert clock.sleeps == [3.0]


async def test_successes_recover_the_rate_up_to_the_configured_maximum() -> None:
    clock = FakeClock()
    limiter = _limiter(clock, rate=4.0, recovery_successes=2)
    limiter.record_rate_limited()
    assert limiter.current_rate == 2.0
    limiter.record_success()
    limiter.record_success()
    assert limiter.current_rate > 2.0
    for _ in range(50):
        limiter.record_success()
    assert limiter.current_rate == 4.0


async def test_explicit_max_rate_caps_recovery() -> None:
    clock = FakeClock()
    limiter = _limiter(clock, rate=4.0, max_rate=6.0, recovery_successes=1)
    for _ in range(100):
        limiter.record_success()
    assert limiter.current_rate == 6.0
