"""Tools that report on the server itself rather than on Worksection data."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from worksection_mcp import __version__
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
