from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from worksection_mcp.errors import OffloadNotFoundError
from worksection_mcp.offload import OFFLOAD_URI_PREFIX, ResponseOffloader


def _offloader(tmp_path: Path, threshold: int = 100, chunk: int = 40) -> ResponseOffloader:
    return ResponseOffloader(tmp_path, threshold_bytes=threshold, chunk_bytes=chunk)


def test_small_payloads_are_not_offloaded(tmp_path: Path) -> None:
    assert _offloader(tmp_path).maybe_offload("short") is None
    assert list(tmp_path.glob("*")) == []


def test_large_payloads_are_written_to_disk(tmp_path: Path) -> None:
    record = _offloader(tmp_path).maybe_offload("x" * 250)
    assert record is not None
    assert record.path.is_file()
    assert record.size_bytes == 250
    assert record.total_chunks == 7
    assert record.uri == f"{OFFLOAD_URI_PREFIX}{record.key}"
    assert record.preview.startswith("xxx")


def test_chunks_reassemble_into_the_original(tmp_path: Path) -> None:
    offloader = _offloader(tmp_path)
    payload = json.dumps({"rows": list(range(200))})
    record = offloader.maybe_offload(payload)
    assert record is not None
    rebuilt = "".join(
        offloader.read_chunk(record.key, index)["text"] for index in range(record.total_chunks)
    )
    assert rebuilt == payload


def test_chunk_metadata_describes_position(tmp_path: Path) -> None:
    offloader = _offloader(tmp_path)
    record = offloader.maybe_offload("y" * 250)
    assert record is not None
    chunk = offloader.read_chunk(record.key, 0)
    assert chunk["chunk_index"] == 0
    assert chunk["total_chunks"] == record.total_chunks
    assert chunk["has_more"] is True
    assert offloader.read_chunk(record.key, record.total_chunks - 1)["has_more"] is False


def test_out_of_range_chunk_is_rejected(tmp_path: Path) -> None:
    offloader = _offloader(tmp_path)
    record = offloader.maybe_offload("z" * 250)
    assert record is not None
    with pytest.raises(OffloadNotFoundError):
        offloader.read_chunk(record.key, 99)


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(OffloadNotFoundError):
        _offloader(tmp_path).read_chunk("nope", 0)


def test_list_records_reports_what_is_stored(tmp_path: Path) -> None:
    offloader = _offloader(tmp_path)
    offloader.maybe_offload("a" * 200)
    offloader.maybe_offload("b" * 300)
    assert len(offloader.list_records()) == 2


def test_key_from_uri(tmp_path: Path) -> None:
    assert ResponseOffloader.key_from_uri(f"{OFFLOAD_URI_PREFIX}abc123") == "abc123"
    with pytest.raises(OffloadNotFoundError):
        ResponseOffloader.key_from_uri("https://example.test/abc")


def test_reading_one_chunk_does_not_read_the_whole_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A chunk request must only ever pull its own bytes off disk.

    Reading the whole payload just to hand back one slice would defeat the
    entire point of chunking a large response: memory use and disk IO would
    scale with the total payload size instead of the chunk size.
    """
    chunk_size = 1024
    offloader = _offloader(tmp_path, threshold=100, chunk=chunk_size)
    payload = "a" * (5 * 1024 * 1024)  # 5 MiB, far larger than one chunk
    record = offloader.maybe_offload(payload)
    assert record is not None
    assert record.total_chunks > 1

    bytes_read_from_payload_file: list[int] = []
    real_open: Any = Path.open

    def spy_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        handle = real_open(self, *args, **kwargs)
        if self == record.path:
            original_read = handle.read

            def spy_read(size: int = -1, /) -> bytes:
                data: bytes = original_read(size)
                bytes_read_from_payload_file.append(len(data))
                return data

            handle.read = spy_read
        return handle

    monkeypatch.setattr(Path, "open", spy_open)

    chunk = offloader.read_chunk(record.key, 2)

    assert chunk["chunk_index"] == 2
    assert len(chunk["text"]) <= chunk_size
    # Only the requested chunk's bytes were ever pulled off the payload
    # file - nowhere near the 5 MiB the naive "read the whole file" approach
    # would have to load.
    assert bytes_read_from_payload_file, "expected the payload file to be read at least once"
    assert sum(bytes_read_from_payload_file) <= chunk_size
