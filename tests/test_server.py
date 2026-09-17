from __future__ import annotations

import json
from pathlib import Path

from worksection_mcp.config import Settings, load_settings
from worksection_mcp.server import build_server, call_tool_payload, list_tools_payload
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
