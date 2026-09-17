"""Drive the server the way a real MCP client does, over an in-memory stream pair.

The installed SDK does not ship the ``create_connected_server_and_client_session``
convenience helper some ``mcp`` releases provide, so ``_connected_session`` below
wires the same thing by hand: a pair of in-memory streams, the server's ``run``
loop started as a background task, and a client session layered on top.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp.client.session import ClientSession
from mcp.server.lowlevel import Server
from mcp.shared.memory import create_client_server_memory_streams

from tests.support import make_context
from worksection_mcp.offload import ResponseOffloader
from worksection_mcp.server import build_server


@asynccontextmanager
async def _connected_session(server: Server[Any]) -> AsyncGenerator[ClientSession, None]:
    async with create_client_server_memory_streams() as (client_streams, server_streams):
        client_read, client_write = client_streams
        server_read, server_write = server_streams

        async with anyio.create_task_group() as task_group:

            async def run_server() -> None:
                await server.run(
                    server_read,
                    server_write,
                    server.create_initialization_options(),
                )

            task_group.start_soon(run_server)

            async with ClientSession(client_read, client_write) as session:
                await session.initialize()
                yield session

            task_group.cancel_scope.cancel()


@pytest.mark.anyio
async def test_client_can_list_and_call_tools(tmp_path: Path) -> None:
    context, _requests = make_context(
        [{"status": "ok", "data": [{"id": 1, "name": "Site"}]}], state_dir=str(tmp_path)
    )
    server = build_server(context)
    async with _connected_session(server) as session:
        listed = await session.list_tools()
        names = {tool.name for tool in listed.tools}
        assert {"get_projects", "get_project", "validate_configuration"} <= names
        assert "delete_task" not in names

        called = await session.call_tool("get_projects", {})
        assert "Site" in called.content[0].text  # type: ignore[union-attr]


@pytest.mark.anyio
async def test_client_can_list_and_read_offloaded_resources(tmp_path: Path) -> None:
    context, _requests = make_context(
        [{"status": "ok", "data": [{"id": i} for i in range(500)]}],
        state_dir=str(tmp_path / "state"),
    )
    context.offloader = ResponseOffloader(
        tmp_path / "offload", threshold_bytes=200, chunk_bytes=100
    )
    server = build_server(context)
    async with _connected_session(server) as session:
        called = await session.call_tool("get_projects", {})
        payload = json.loads(called.content[0].text)  # type: ignore[union-attr]
        assert payload["offloaded"] is True

        listed = await session.list_resources()
        assert len(listed.resources) == 1
        uri = str(listed.resources[0].uri)
        assert uri == payload["resource_uri"]

        read = await session.read_resource(uri)
        contents = read.contents
        assert json.loads(contents[0].text)[0] == {"id": 0}  # type: ignore[union-attr]
