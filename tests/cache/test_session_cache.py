from __future__ import annotations

from worksection_mcp.cache.session_cache import SessionCache, cache_key


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        return self.now


def test_value_round_trips() -> None:
    cache = SessionCache(60)
    cache.set("k", [1, 2])
    assert cache.get("k") == [1, 2]


def test_missing_key_returns_none() -> None:
    assert SessionCache(60).get("nope") is None


def test_entries_expire() -> None:
    clock = FakeClock()
    cache = SessionCache(10, time_source=clock.time)
    cache.set("k", "v")
    clock.now = 9.0
    assert cache.get("k") == "v"
    clock.now = 11.0
    assert cache.get("k") is None


def test_zero_ttl_disables_the_cache() -> None:
    cache = SessionCache(0)
    cache.set("k", "v")
    assert cache.enabled is False
    assert cache.get("k") is None


def test_oldest_entries_are_evicted_at_the_limit() -> None:
    cache = SessionCache(60, max_entries=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert cache.get("a") is None
    assert cache.get("c") == 3


def test_invalidate_all_empties_the_cache() -> None:
    cache = SessionCache(60)
    cache.set("a", 1)
    cache.invalidate_all()
    assert cache.get("a") is None


def test_stats_count_hits_and_misses() -> None:
    cache = SessionCache(60)
    cache.set("a", 1)
    cache.get("a")
    cache.get("b")
    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["entries"] == 1


def test_cache_key_is_order_independent_and_scope_aware() -> None:
    first = cache_key("get_tasks", "/project/7/", {"a": "1", "b": "2"})
    second = cache_key("get_tasks", "/project/7/", {"b": "2", "a": "1"})
    assert first == second
    assert first != cache_key("get_tasks", "/project/8/", {"a": "1", "b": "2"})
    assert first != cache_key("get_task", "/project/7/", {"a": "1", "b": "2"})
