"""Tools that report on the server itself rather than on Worksection data."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from worksection_mcp import __version__, api_actions
from worksection_mcp.errors import OffloadNotFoundError
from worksection_mcp.offload import ResponseOffloader
from worksection_mcp.preflight import check_configuration
from worksection_mcp.tooling import ToolContext, tool


class NoArguments(BaseModel):
    """Tool that takes no arguments."""

    model_config = ConfigDict(extra="forbid")


@tool(
    name="validate_configuration",
    description=(
        "Report the server's effective configuration and the result of every local "
        "startup check. Contacts no external service and never returns secret values."
    ),
    input_model=NoArguments,
)
async def validate_configuration(context: ToolContext, _args: NoArguments) -> dict[str, Any]:
    results = check_configuration(context.settings)
    return {
        "version": __version__,
        "auth_mode": context.settings.auth_mode,
        "destructive_operations_enabled": context.settings.allow_destructive_operations,
        "ok": all(result.ok for result in results),
        "checks": [
            {"name": result.name, "ok": result.ok, "detail": result.detail} for result in results
        ],
    }


@tool(
    name="health_check",
    description=(
        "Verify that the configured credentials can reach the Worksection API. "
        "Returns a status report instead of raising when the call fails."
    ),
    input_model=NoArguments,
)
async def health_check(context: ToolContext, _args: NoArguments) -> dict[str, Any]:
    report: dict[str, Any] = {
        "version": __version__,
        "auth_mode": context.settings.auth_mode,
        "api_reachable": False,
        "detail": "",
    }
    try:
        await context.client.call(api_actions.GET_PROJECTS)
    except Exception as exc:  # reported to the caller, not propagated
        report["detail"] = f"{type(exc).__name__}: {exc}"
        return report
    report["api_reachable"] = True
    report["detail"] = "API responded successfully"
    return report


class ReadOffloadedInput(BaseModel):
    resource_uri: str = Field(
        description="The worksection://offload/... URI from an offloaded response."
    )
    chunk_index: int = Field(default=0, ge=0, description="Zero-based chunk to read.")


@tool(
    name="read_offloaded_response",
    description=(
        "Read one bounded chunk of a response that was too large to return inline. "
        "Use the resource_uri and total_chunks from the offload summary."
    ),
    input_model=ReadOffloadedInput,
)
async def read_offloaded_response(context: ToolContext, args: ReadOffloadedInput) -> dict[str, Any]:
    if context.offloader is None:
        raise OffloadNotFoundError("response offloading is not enabled")
    key = ResponseOffloader.key_from_uri(args.resource_uri)
    return context.offloader.read_chunk(key, args.chunk_index)
