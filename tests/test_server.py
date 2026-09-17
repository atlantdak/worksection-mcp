from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from worksection_mcp.config import Settings, load_settings
from worksection_mcp.errors import OffloadNotFoundError
from worksection_mcp.server import (
    build_server,
    call_tool_payload,
    create_context,
    list_resources_payload,
    list_tools_payload,
    read_resource_payload,
    run_stdio,
    serve,
)
from worksection_mcp.tooling import ToolContext


def _context(tmp_path: Path, **overrides: object) -> ToolContext:
    base: dict[str, object] = {
        "auth_mode": "admin_key",
        "worksection_account": "acme",
        "worksection_api_key": "k",
        "state_dir": str(tmp_path),
    }
    base.update(overrides)
    settings: Settings = load_settings(**base)
    return ToolContext(settings=settings, client=object())  # type: ignore[arg-type]


async def test_list_tools_exposes_registered_tools(tmp_path: Path) -> None:
    tools = await list_tools_payload(_context(tmp_path))
    names = [item.name for item in tools]
    assert "validate_configuration" in names
    schema = next(item for item in tools if item.name == "validate_configuration").input_schema
    assert schema["type"] == "object"


async def test_call_tool_returns_a_text_block(tmp_path: Path) -> None:
    blocks = await call_tool_payload(_context(tmp_path), "validate_configuration", {})
    assert blocks[0].type == "text"
    assert json.loads(blocks[0].text)["auth_mode"] == "admin_key"


async def test_unknown_tool_returns_a_structured_error(tmp_path: Path) -> None:
    blocks = await call_tool_payload(_context(tmp_path), "no_such_tool", {})
    payload = json.loads(blocks[0].text)
    assert payload["error"]["type"] == "UnknownToolError"


async def test_invalid_arguments_return_a_structured_error(tmp_path: Path) -> None:
    blocks = await call_tool_payload(_context(tmp_path), "validate_configuration", {"x": object()})
    assert "error" in json.loads(blocks[0].text)


def test_build_server_names_the_server(tmp_path: Path) -> None:
    server = build_server(_context(tmp_path))
    assert server.name == "worksection-mcp"


async def test_list_resources_is_empty_without_an_offloader(tmp_path: Path) -> None:
    assert await list_resources_payload(_context(tmp_path)) == []


async def test_reading_a_resource_without_an_offloader_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(OffloadNotFoundError):
        await read_resource_payload(_context(tmp_path), "worksection://offload/anything")


async def test_create_context_wires_every_collaborator(tmp_path: Path) -> None:
    settings: Settings = load_settings(
        auth_mode="admin_key",
        worksection_account="acme",
        worksection_api_key="k",
        state_dir=str(tmp_path),
    )
    context = await create_context(settings)
    try:
        assert context.settings is settings
        assert context.auth is not None
        assert context.cache is not None
        assert context.file_cache is not None
        assert context.offloader is not None
    finally:
        await context.client.aclose()


async def test_run_stdio_closes_the_client_even_if_the_server_run_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings: Settings = load_settings(
        auth_mode="admin_key",
        worksection_account="acme",
        worksection_api_key="k",
        state_dir=str(tmp_path),
    )
    context = await create_context(settings)
    aclose = AsyncMock(wraps=context.client.aclose)
    monkeypatch.setattr(context.client, "aclose", aclose)

    class _FakeServer:
        def create_initialization_options(self) -> object:
            return object()

        async def run(self, *_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("boom")

    @asynccontextmanager
    async def _fake_stdio_server() -> Any:
        yield object(), object()

    import worksection_mcp.server as server_module

    monkeypatch.setattr(server_module, "build_server", lambda _ctx: _FakeServer())
    monkeypatch.setattr(server_module, "create_context", AsyncMock(return_value=context))
    monkeypatch.setattr(server_module, "stdio_server", _fake_stdio_server)

    with pytest.raises(RuntimeError, match="boom"):
        await run_stdio(settings)
    aclose.assert_awaited_once()


def test_serve_runs_the_stdio_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    run_stdio_mock = AsyncMock()
    import worksection_mcp.server as server_module

    monkeypatch.setattr(server_module, "run_stdio", run_stdio_mock)
    serve()
    run_stdio_mock.assert_awaited_once()
