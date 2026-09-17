"""Shared helpers for tool tests: a context wired to a scripted transport."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

import worksection_mcp.tools  # noqa: F401 - registers every tool
from worksection_mcp.auth.admin_key import AdminKeyAuth
from worksection_mcp.config import load_settings
from worksection_mcp.http.client import WorksectionClient
from worksection_mcp.tooling import ToolContext


def make_context(
    responses: Sequence[Any],
    **setting_overrides: object,
) -> tuple[ToolContext, list[httpx.Request]]:
    """Return a ToolContext whose client replays ``responses`` in order.

    Each entry is either a JSON-serialisable body (wrapped in HTTP 200) or a
    ready-made ``httpx.Response``. Captured requests are returned for asserting
    on the action, page and encoded query parameters.
    """
    recorded: list[httpx.Request] = []
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        if not queue:
            raise AssertionError(f"unexpected extra request: {request.url}")
        item = queue.pop(0)
        return item if isinstance(item, httpx.Response) else httpx.Response(200, json=item)

    base: dict[str, object] = {
        "auth_mode": "admin_key",
        "worksection_account": "acme",
        "worksection_api_key": "k",
        "rate_limit_rps": 50.0,
    }
    base.update(setting_overrides)
    settings = load_settings(**base)
    client = WorksectionClient(
        settings,
        AdminKeyAuth(account="acme", api_key="k"),
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    return ToolContext(settings=settings, client=client), recorded
