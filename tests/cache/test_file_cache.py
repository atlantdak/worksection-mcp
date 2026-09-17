from __future__ import annotations

from pathlib import Path

from worksection_mcp.cache.file_cache import FileCache, file_cache_key


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def time(self) -> float:
        return self.now


def test_key_is_derived_from_the_url() -> None:
    assert file_cache_key("https://a.test/1") == file_cache_key("https://a.test/1")
    assert file_cache_key("https://a.test/1") != file_cache_key("https://a.test/2")
    assert len(file_cache_key("https://a.test/1")) == 64


def test_round_trip(tmp_path: Path) -> None:
    cache = FileCache(tmp_path, ttl_seconds=60, max_bytes=1024)
    assert cache.get("k") is None
    cache.put("k", b"bytes")
    assert cache.get("k") == b"bytes"


def test_entries_expire(tmp_path: Path) -> None:
    clock = FakeClock()
    cache = FileCache(tmp_path, ttl_seconds=10, max_bytes=1024, time_source=clock.time)
    cache.put("k", b"x")
    clock.now += 11
    assert cache.get("k") is None


def test_purge_expired_removes_files(tmp_path: Path) -> None:
    clock = FakeClock()
    cache = FileCache(tmp_path, ttl_seconds=10, max_bytes=1024, time_source=clock.time)
    cache.put("a", b"x")
    clock.now += 11
    assert cache.purge_expired() == 1
    assert list(tmp_path.glob("*.bin")) == []


def test_prune_to_limit_drops_the_oldest(tmp_path: Path) -> None:
    clock = FakeClock()
    cache = FileCache(tmp_path, ttl_seconds=600, max_bytes=10, time_source=clock.time)
    cache.put("a", b"12345")
    clock.now += 1
    cache.put("b", b"12345")
    clock.now += 1
    cache.put("c", b"12345")
    assert cache.get("a") is None
    assert cache.get("c") == b"12345"


def test_cache_directory_is_private(tmp_path: Path) -> None:
    import sys

    if sys.platform == "win32":
        return
    directory = tmp_path / "files"
    FileCache(directory, ttl_seconds=60, max_bytes=1024).put("k", b"x")
    assert directory.stat().st_mode & 0o777 == 0o700


def test_zero_ttl_disables_caching(tmp_path: Path) -> None:
    cache = FileCache(tmp_path, ttl_seconds=0, max_bytes=1024)
    cache.put("k", b"x")
    assert cache.get("k") is None
