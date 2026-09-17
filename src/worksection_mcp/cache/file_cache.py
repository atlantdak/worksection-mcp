"""A bounded, private on-disk cache for downloaded attachments."""

from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Callable
from pathlib import Path

from worksection_mcp.logging_setup import get_logger
from worksection_mcp.secure_io import ensure_private_dir

logger = get_logger("cache.file")

SUFFIX = ".bin"


def file_cache_key(url: str) -> str:
    """Opaque, filesystem-safe key for a download URL."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


class FileCache:
    """Stores attachment bytes under a private directory with TTL and size limits."""

    def __init__(
        self,
        directory: Path,
        *,
        ttl_seconds: int,
        max_bytes: int,
        time_source: Callable[[], float] = time.time,
    ) -> None:
        self._directory = directory
        self._ttl = ttl_seconds
        self._max_bytes = max_bytes
        self._time = time_source

    @property
    def enabled(self) -> bool:
        return self._ttl > 0 and self._max_bytes > 0

    def _path(self, key: str) -> Path:
        if not key or "/" in key or "\\" in key or key in {".", ".."}:
            raise ValueError("cache key must not contain path separators")
        return self._directory / f"{key}{SUFFIX}"

    def get(self, key: str) -> bytes | None:
        if not self.enabled:
            return None
        path = self._path(key)
        try:
            age = self._time() - path.stat().st_mtime
        except FileNotFoundError:
            return None
        if age > self._ttl:
            path.unlink(missing_ok=True)
            return None
        return path.read_bytes()

    def put(self, key: str, data: bytes) -> Path:
        ensure_private_dir(self._directory)
        path = self._path(key)
        if not self.enabled:
            return path
        path.write_bytes(data)
        path.chmod(0o600)
        now = self._time()
        os.utime(path, (now, now))
        self.purge_expired()
        self.prune_to_limit()
        return path

    def _entries(self) -> list[Path]:
        if not self._directory.is_dir():
            return []
        return sorted(self._directory.glob(f"*{SUFFIX}"), key=lambda item: item.stat().st_mtime)

    def purge_expired(self) -> int:
        removed = 0
        now = self._time()
        for path in self._entries():
            if now - path.stat().st_mtime > self._ttl:
                path.unlink(missing_ok=True)
                removed += 1
        return removed

    def prune_to_limit(self) -> int:
        entries = self._entries()
        total = sum(path.stat().st_size for path in entries)
        removed = 0
        for path in entries:
            if total <= self._max_bytes:
                break
            total -= path.stat().st_size
            path.unlink(missing_ok=True)
            removed += 1
        return removed

    def stats(self) -> dict[str, int]:
        entries = self._entries()
        return {
            "files": len(entries),
            "bytes": sum(path.stat().st_size for path in entries),
        }
