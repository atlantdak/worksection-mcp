"""Turn handler return values into MCP content blocks."""

from __future__ import annotations

import json
from typing import Any

import mcp.types as types


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False, default=repr)


def render_result(value: Any) -> list[types.TextContent]:
    """Render a tool result as a single text block."""
    text = value if isinstance(value, str) else _dumps(value)
    return [types.TextContent(type="text", text=text)]


def render_error(exc: Exception) -> list[types.TextContent]:
    """Render a failure as a structured, machine-readable text block."""
    payload = {"error": {"type": type(exc).__name__, "message": str(exc)}}
    return [types.TextContent(type="text", text=_dumps(payload))]
