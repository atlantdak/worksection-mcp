from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, Field, ValidationError

from worksection_mcp.config import Settings, load_settings
from worksection_mcp.errors import DestructiveOperationDisabled
from worksection_mcp.tooling import (
    ToolContext,
    all_tool_specs,
    clear_registry,
    dispatch,
    enabled_tool_specs,
    get_tool_spec,
    tool,
)


class EchoInput(BaseModel):
    value: str = Field(description="text to echo")


@pytest.fixture(autouse=True)
def _clean_registry() -> Any:
    clear_registry()
    yield
    clear_registry()


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "auth_mode": "admin_key",
        "worksection_account": "acme",
        "worksection_api_key": "k",
    }
    base.update(overrides)
    return load_settings(**base)


def _context(settings: Settings) -> ToolContext:
    return ToolContext(settings=settings, client=object())  # type: ignore[arg-type]


def test_tool_decorator_registers_a_spec() -> None:
    @tool(name="echo", description="Echo a value", input_model=EchoInput)
    async def _echo(_ctx: ToolContext, args: EchoInput) -> str:
        return args.value

    spec = get_tool_spec("echo")
    assert spec.description == "Echo a value"
    assert spec.destructive is False
    assert spec.input_schema()["properties"]["value"]["description"] == "text to echo"


def test_duplicate_tool_names_are_rejected() -> None:
    @tool(name="echo", description="one", input_model=EchoInput)
    async def _a(_ctx: ToolContext, args: EchoInput) -> str:
        return args.value

    with pytest.raises(ValueError, match="already registered"):

        @tool(name="echo", description="two", input_model=EchoInput)
        async def _b(_ctx: ToolContext, args: EchoInput) -> str:
            return args.value


def test_destructive_tools_are_hidden_by_default() -> None:
    @tool(name="safe", description="s", input_model=EchoInput)
    async def _safe(_ctx: ToolContext, args: EchoInput) -> str:
        return args.value

    @tool(name="nuke", description="n", input_model=EchoInput, destructive=True)
    async def _nuke(_ctx: ToolContext, args: EchoInput) -> str:
        return args.value

    names = [spec.name for spec in enabled_tool_specs(_settings())]
    assert names == ["safe"]
    assert {spec.name for spec in all_tool_specs()} == {"safe", "nuke"}


def test_destructive_tools_appear_when_enabled() -> None:
    @tool(name="nuke", description="n", input_model=EchoInput, destructive=True)
    async def _nuke(_ctx: ToolContext, args: EchoInput) -> str:
        return args.value

    settings = _settings(allow_destructive_operations=True)
    assert [spec.name for spec in enabled_tool_specs(settings)] == ["nuke"]


async def test_dispatch_validates_and_calls_the_handler() -> None:
    @tool(name="echo", description="e", input_model=EchoInput)
    async def _echo(_ctx: ToolContext, args: EchoInput) -> str:
        return args.value.upper()

    assert await dispatch(_context(_settings()), "echo", {"value": "hi"}) == "HI"


async def test_dispatch_rejects_invalid_arguments() -> None:
    @tool(name="echo", description="e", input_model=EchoInput)
    async def _echo(_ctx: ToolContext, args: EchoInput) -> str:
        return args.value

    with pytest.raises(ValidationError):
        await dispatch(_context(_settings()), "echo", {"wrong": 1})


async def test_dispatch_blocks_destructive_tools_at_call_time() -> None:
    @tool(name="nuke", description="n", input_model=EchoInput, destructive=True)
    async def _nuke(_ctx: ToolContext, args: EchoInput) -> str:
        return "boom"

    with pytest.raises(DestructiveOperationDisabled):
        await dispatch(_context(_settings()), "nuke", {"value": "x"})


async def test_dispatch_raises_key_error_for_unknown_tools() -> None:
    with pytest.raises(KeyError):
        await dispatch(_context(_settings()), "missing", {})
