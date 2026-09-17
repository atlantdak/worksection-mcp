"""Keep oversized tool results out of the protocol response.

A response larger than the configured threshold is written to a private file
and replaced by a short summary carrying a ``worksection://offload/<key>``
URI. The client reads it back in bounded chunks, either as an MCP resource or
through the read_offloaded_response tool.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from worksection_mcp.errors import OffloadNotFoundError
from worksection_mcp.logging_setup import get_logger
from worksection_mcp.secure_io import ensure_private_dir, write_secret_file

logger = get_logger("offload")

OFFLOAD_URI_PREFIX = "worksection://offload/"
PREVIEW_CHARS = 300
PAYLOAD_SUFFIX = ".json"
META_SUFFIX = ".meta.json"

# Offload keys are always generated internally as uuid4 hex strings. A key
# read back from a resource URI or tool argument must match this shape
# before it ever reaches the filesystem, so a caller cannot smuggle a path
# (``../../etc/passwd`` and the like) through what looks like an opaque id.
_KEY_RE = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True)
class OffloadRecord:
    """Where an offloaded response lives and how to read it back."""

    key: str
    uri: str
    path: Path
    size_bytes: int
    total_chunks: int
    created_at: float
    preview: str

    def to_summary(self) -> dict[str, Any]:
        return {
            "offloaded": True,
            "reason": "response exceeded the inline size threshold",
            "resource_uri": self.uri,
            "size_bytes": self.size_bytes,
            "total_chunks": self.total_chunks,
            "preview": self.preview,
            "how_to_read": (
                "call read_offloaded_response with this resource_uri and chunk_index "
                "0..total_chunks-1, or read the resource URI directly"
            ),
        }


class ResponseOffloader:
    """Writes, indexes and serves back large responses."""

    def __init__(
        self,
        directory: Path,
        *,
        threshold_bytes: int,
        chunk_bytes: int,
        time_source: Callable[[], float] = time.time,
    ) -> None:
        self._directory = directory
        self._threshold = threshold_bytes
        self._chunk = max(1, chunk_bytes)
        self._time = time_source

    @staticmethod
    def key_from_uri(uri: str) -> str:
        if not uri.startswith(OFFLOAD_URI_PREFIX):
            raise OffloadNotFoundError(f"{uri!r} is not an offloaded-response URI")
        key = uri[len(OFFLOAD_URI_PREFIX) :].strip("/")
        if not key:
            raise OffloadNotFoundError("offload URI carries no key")
        return key

    def _require_valid_key(self, key: str) -> str:
        """Reject anything that is not a bare, generated offload key.

        This is the one gate every lookup passes through, so a caller can
        never turn a key into a path that escapes ``self._directory`` -
        there is simply no character in the allowed shape that a path
        separator or a ``..`` segment could hide behind.
        """
        if not _KEY_RE.match(key):
            raise OffloadNotFoundError(f"no offloaded response with key {key!r}")
        return key

    def _payload_path(self, key: str) -> Path:
        return self._directory / f"{key}{PAYLOAD_SUFFIX}"

    def _meta_path(self, key: str) -> Path:
        return self._directory / f"{key}{META_SUFFIX}"

    def maybe_offload(self, text: str) -> OffloadRecord | None:
        """Offload ``text`` if it is over the threshold; otherwise return None."""
        encoded = text.encode("utf-8")
        size = len(encoded)
        if size <= self._threshold:
            return None

        ensure_private_dir(self._directory)
        key = uuid.uuid4().hex
        payload_path = self._payload_path(key)
        write_secret_file(payload_path, encoded)

        total_chunks = max(1, -(-len(text) // self._chunk))
        record = OffloadRecord(
            key=key,
            uri=f"{OFFLOAD_URI_PREFIX}{key}",
            path=payload_path,
            size_bytes=size,
            total_chunks=total_chunks,
            created_at=self._time(),
            preview=text[:PREVIEW_CHARS],
        )
        meta_path = self._meta_path(key)
        meta_bytes = json.dumps(
            {
                "key": key,
                "size_bytes": size,
                "total_chunks": total_chunks,
                "created_at": record.created_at,
                "preview": record.preview,
            }
        ).encode("utf-8")
        write_secret_file(meta_path, meta_bytes)
        logger.info("offloaded a %d byte response to %s", size, record.uri)
        return record

    def get_record(self, key: str) -> OffloadRecord:
        key = self._require_valid_key(key)
        meta_path = self._meta_path(key)
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            raise OffloadNotFoundError(f"no offloaded response with key {key!r}") from exc
        return OffloadRecord(
            key=key,
            uri=f"{OFFLOAD_URI_PREFIX}{key}",
            path=self._payload_path(key),
            size_bytes=int(meta["size_bytes"]),
            total_chunks=int(meta["total_chunks"]),
            created_at=float(meta["created_at"]),
            preview=str(meta.get("preview", "")),
        )

    def read_chunk(self, key: str, index: int) -> dict[str, Any]:
        """Return one bounded slice of an offloaded response."""
        record = self.get_record(key)
        if index < 0 or index >= record.total_chunks:
            raise OffloadNotFoundError(
                f"chunk {index} is out of range; this response has {record.total_chunks} chunks"
            )
        text = record.path.read_text(encoding="utf-8")
        start = index * self._chunk
        return {
            "resource_uri": record.uri,
            "chunk_index": index,
            "total_chunks": record.total_chunks,
            "has_more": index < record.total_chunks - 1,
            "text": text[start : start + self._chunk],
        }

    def read_all(self, key: str) -> str:
        return self.get_record(key).path.read_text(encoding="utf-8")

    def list_records(self) -> list[OffloadRecord]:
        if not self._directory.is_dir():
            return []
        records: list[OffloadRecord] = []
        for meta_path in sorted(self._directory.glob(f"*{META_SUFFIX}")):
            key = meta_path.name[: -len(META_SUFFIX)]
            try:
                records.append(self.get_record(key))
            except OffloadNotFoundError:  # pragma: no cover - torn write
                continue
        return records
