from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support import make_context
from worksection_mcp.offload import ResponseOffloader
from worksection_mcp.server import (
    call_tool_payload,
    list_resources_payload,
    read_resource_payload,
)
from worksection_mcp.tooling import dispatch


def _context_with_offloader(tmp_path: Path):  # type: ignore[no-untyped-def]
    context, requests = make_context([{"status": "ok", "data": [{"id": i} for i in range(500)]}])
    context.offloader = ResponseOffloader(tmp_path, threshold_bytes=200, chunk_bytes=100)
    return context, requests


async def test_a_large_tool_result_is_offloaded(tmp_path: Path) -> None:
    context, _ = _context_with_offloader(tmp_path)
    blocks = await call_tool_payload(context, "get_projects", {})
    payload = json.loads(blocks[0].text)
    assert payload["offloaded"] is True


async def test_offloaded_responses_are_listed_as_resources(tmp_path: Path) -> None:
    context, _ = _context_with_offloader(tmp_path)
    await call_tool_payload(context, "get_projects", {})
    resources = await list_resources_payload(context)
    assert len(resources) == 1
    assert str(resources[0].uri).startswith("worksection://offload/")


async def test_reading_the_resource_returns_the_whole_payload(tmp_path: Path) -> None:
    context, _ = _context_with_offloader(tmp_path)
    blocks = await call_tool_payload(context, "get_projects", {})
    uri = json.loads(blocks[0].text)["resource_uri"]
    text = await read_resource_payload(context, uri)
    assert json.loads(text)[0] == {"id": 0}


async def test_read_offloaded_response_tool_returns_bounded_chunks(tmp_path: Path) -> None:
    context, _ = _context_with_offloader(tmp_path)
    blocks = await call_tool_payload(context, "get_projects", {})
    uri = json.loads(blocks[0].text)["resource_uri"]
    chunk = await dispatch(
        context, "read_offloaded_response", {"resource_uri": uri, "chunk_index": 0}
    )
    assert chunk["chunk_index"] == 0
    assert len(chunk["text"]) <= 100
    assert chunk["has_more"] is True


async def test_reading_an_unknown_resource_is_an_error(tmp_path: Path) -> None:
    context, _ = _context_with_offloader(tmp_path)
    with pytest.raises(Exception):
        await read_resource_payload(context, "worksection://offload/missing")
