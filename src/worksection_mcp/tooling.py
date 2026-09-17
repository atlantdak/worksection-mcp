"""Tool registry, shared handler context, and argument dispatch.

Destructive tools are filtered out of :func:`enabled_tool_specs` so they never
appear in ``list_tools``, and :func:`dispatch` checks the same flag again in
case a client calls a name it remembered from an earlier session.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeAlias

from pydantic import BaseModel

from worksection_mcp.config import Settings
from worksection_mcp.errors import DestructiveOperationDisabled

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from worksection_mcp.auth.base import AuthProvider
    from worksection_mcp.cache.session_cache import SessionCache
    from worksection_mcp.http.client import WorksectionClient


@dataclass
class ToolContext:
    """Everything a tool handler is allowed to reach for."""

    settings: Settings
    client: WorksectionClient
    auth: AuthProvider | None = None
    cache: SessionCache | None = None


ToolHandler: TypeAlias = Callable[[ToolContext, Any], Awaitable[Any]]


@dataclass(frozen=True)
class ToolSpec:
    """One registered tool."""

    name: str
    description: str
    input_model: type[BaseModel]
    handler: ToolHandler
    destructive: bool = False

    def input_schema(self) -> dict[str, Any]:
        return self.input_model.model_json_schema()


_REGISTRY: dict[str, ToolSpec] = {}


def tool(
    *,
    name: str,
    description: str,
    input_model: type[BaseModel],
    destructive: bool = False,
) -> Callable[[ToolHandler], ToolHandler]:
    """Register a handler under ``name``. Returns the handler unchanged."""

    def decorator(handler: ToolHandler) -> ToolHandler:
        if name in _REGISTRY:
            raise ValueError(f"tool {name!r} is already registered")
        _REGISTRY[name] = ToolSpec(
            name=name,
            description=description,
            input_model=input_model,
            handler=handler,
            destructive=destructive,
        )
        return handler

    return decorator


def clear_registry() -> None:
    """Reset the registry. Intended for tests only."""
    _REGISTRY.clear()


def all_tool_specs() -> list[ToolSpec]:
    return [_REGISTRY[name] for name in sorted(_REGISTRY)]


def enabled_tool_specs(settings: Settings) -> list[ToolSpec]:
    """Specs a client may see, honouring ALLOW_DESTRUCTIVE_OPERATIONS."""
    return [
        spec
        for spec in all_tool_specs()
        if settings.allow_destructive_operations or not spec.destructive
    ]


def get_tool_spec(name: str) -> ToolSpec:
    return _REGISTRY[name]


async def dispatch(context: ToolContext, name: str, arguments: Mapping[str, Any] | None) -> Any:
    """Validate arguments against the tool's model and run its handler."""
    spec = get_tool_spec(name)
    if spec.destructive and not context.settings.allow_destructive_operations:
        raise DestructiveOperationDisabled(name)
    args = spec.input_model.model_validate(dict(arguments or {}))
    return await spec.handler(context, args)
