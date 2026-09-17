"""MCP server wiring: tool listing, tool dispatch, and the stdio transport."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from worksection_mcp import __version__, tools  # noqa: F401 - import registers tools
from worksection_mcp.auth.factory import build_auth_provider
from worksection_mcp.cache.file_cache import FileCache
from worksection_mcp.cache.session_cache import SessionCache
from worksection_mcp.config import Settings, load_settings
from worksection_mcp.errors import OffloadNotFoundError, WorksectionError
from worksection_mcp.http.client import WorksectionClient
from worksection_mcp.logging_setup import configure_logging, get_logger
from worksection_mcp.offload import ResponseOffloader
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
    return render_result(result, context.offloader)


async def list_resources_payload(context: ToolContext) -> list[types.Resource]:
    """Expose every offloaded response as a readable resource."""
    if context.offloader is None:
        return []
    return [
        types.Resource(
            name=f"Offloaded response {record.key[:8]}",
            uri=record.uri,
            description=f"{record.size_bytes} bytes in {record.total_chunks} chunks",
            mime_type="application/json",
        )
        for record in context.offloader.list_records()
    ]


async def read_resource_payload(context: ToolContext, uri: str) -> str:
    """Return the full text of an offloaded response."""
    if context.offloader is None:
        raise OffloadNotFoundError("response offloading is not enabled")
    return context.offloader.read_all(ResponseOffloader.key_from_uri(str(uri)))


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

    async def _on_list_resources(
        _ctx: Any, _params: types.PaginatedRequestParams | None
    ) -> types.ListResourcesResult:
        return types.ListResourcesResult(resources=await list_resources_payload(context))

    async def _on_read_resource(
        _ctx: Any, params: types.ReadResourceRequestParams
    ) -> types.ReadResourceResult:
        text = await read_resource_payload(context, params.uri)
        return types.ReadResourceResult(
            contents=[
                types.TextResourceContents(uri=params.uri, mime_type="application/json", text=text)
            ]
        )

    return Server(
        SERVER_NAME,
        version=__version__,
        on_list_tools=_on_list_tools,
        on_call_tool=_on_call_tool,
        on_list_resources=_on_list_resources,
        on_read_resource=_on_read_resource,
    )


async def create_context(settings: Settings) -> ToolContext:
    """Build the runtime context for the configured auth mode."""
    auth = build_auth_provider(settings)
    cache = SessionCache(settings.cache_ttl_seconds if settings.cache_enabled else 0)
    client = WorksectionClient(settings, auth, cache=cache)
    file_cache = FileCache(
        settings.file_cache_dir,
        ttl_seconds=settings.cache_ttl_seconds if settings.cache_enabled else 0,
        max_bytes=settings.file_cache_max_bytes,
    )
    offloader = ResponseOffloader(
        settings.offload_dir,
        threshold_bytes=settings.offload_threshold_bytes,
        chunk_bytes=settings.offload_chunk_bytes,
    )
    return ToolContext(
        settings=settings,
        client=client,
        auth=auth,
        cache=cache,
        file_cache=file_cache,
        offloader=offloader,
    )


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
