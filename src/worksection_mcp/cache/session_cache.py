"""A small TTL cache for read responses within one server session."""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping
from typing import Any


def cache_key(action: str, page: str, params: Mapping[str, str]) -> str:
    """Stable key for one API read, independent of parameter ordering."""
    rendered = "&".join(f"{key}={params[key]}" for key in sorted(params) if key != "hash")
    return hashlib.sha256(f"{action}|{page}|{rendered}".encode()).hexdigest()


class SessionCache:
    """Least-recently-inserted TTL cache. Not shared between processes."""

    def __init__(
        self,
        ttl_seconds: int,
        *,
        max_entries: int = 512,
        time_source: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._time = time_source
        self._entries: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    @property
    def enabled(self) -> bool:
        return self._ttl > 0

    def get(self, key: str) -> Any | None:
        if not self.enabled:
            return None
        entry = self._entries.get(key)
        if entry is None:
            self._misses += 1
            return None
        stored_at, value = entry
        if self._time() - stored_at > self._ttl:
            del self._entries[key]
            self._misses += 1
            return None
        self._hits += 1
        return value

    def set(self, key: str, value: Any) -> None:
        if not self.enabled:
            return
        self._entries[key] = (self._time(), value)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def invalidate_all(self) -> None:
        self._entries.clear()

    def stats(self) -> dict[str, int]:
        return {"entries": len(self._entries), "hits": self._hits, "misses": self._misses}
