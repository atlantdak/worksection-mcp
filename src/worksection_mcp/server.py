"""MCP server wiring: tool listing, tool dispatch, and the stdio transport."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from worksection_mcp import __version__, tools  # noqa: F401 - import registers tools
from worksection_mcp.auth.admin_key import build_admin_auth
from worksection_mcp.config import Settings, load_settings
from worksection_mcp.errors import WorksectionError
from worksection_mcp.http.client import WorksectionClient
from worksection_mcp.logging_setup import configure_logging, get_logger
from worksection_mcp.serialization import render_error, render_result
from worksection_mcp.tooling import ToolContext, dispatch, enabled_tool_specs

logger = get_logger("server")

SERVER_NAME = "worksection-mcp"


class UnknownToolError(WorksectionError):
    """A client asked for a tool this server does not expose."""


async def list_tools_payload(context: ToolContext) -> list[types.Tool]:
    """Every tool the current configuration exposes."""
    return [
        types.Tool(
            name=spec.name,
            description=spec.description,
            input_schema=spec.input_schema(),
        )
        for spec in enabled_tool_specs(context.settings)
    ]


async def call_tool_payload(
    context: ToolContext, name: str, arguments: Mapping[str, Any] | None
) -> list[types.TextContent]:
    """Run one tool, converting every failure into a structured text block."""
    try:
        result = await dispatch(context, name, arguments)
    except KeyError:
        return render_error(UnknownToolError(f"unknown tool: {name}"))
    except WorksectionError as exc:
        logger.warning("tool %s failed: %s", name, type(exc).__name__)
        return render_error(exc)
    except Exception as exc:  # surfaced to the client as a text block, not swallowed
        logger.exception("tool %s raised an unexpected error", name)
        return render_error(exc)
    return render_result(result)


def build_server(context: ToolContext) -> Server[Any]:
    """Create the MCP server bound to a tool context.

    Tool listing and dispatch live in ``list_tools_payload`` and
    ``call_tool_payload`` above; these callbacks just satisfy the lowlevel
    server's request/response envelopes around them.
    """

    async def _on_list_tools(
        _ctx: Any, _params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        return types.ListToolsResult(tools=await list_tools_payload(context))

    async def _on_call_tool(_ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        blocks = await call_tool_payload(context, params.name, params.arguments)
        content: list[types.ContentBlock] = [block for block in blocks]
        return types.CallToolResult(content=content)

    return Server(
        SERVER_NAME,
        version=__version__,
        on_list_tools=_on_list_tools,
        on_call_tool=_on_call_tool,
    )


async def create_context(settings: Settings) -> ToolContext:
    """Build the runtime context for the configured auth mode."""
    auth = build_admin_auth(settings)
    client = WorksectionClient(settings, auth)
    return ToolContext(settings=settings, client=client)


async def run_stdio(settings: Settings | None = None) -> None:
    """Serve MCP over stdio until the client disconnects."""
    resolved = settings or load_settings()
    configure_logging(resolved)
    context = await create_context(resolved)
    server = build_server(context)
    logger.info("starting %s in %s mode", SERVER_NAME, resolved.auth_mode)
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        await context.client.aclose()


def serve() -> None:
    """Synchronous wrapper used by the console script."""
    asyncio.run(run_stdio())
