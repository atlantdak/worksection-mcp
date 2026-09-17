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
    *,
    auth: Any | None = None,
    **setting_overrides: object,
) -> tuple[ToolContext, list[httpx.Request]]:
    """Return a ToolContext whose client replays ``responses`` in order.

    Each entry is either a JSON-serialisable body (wrapped in HTTP 200) or a
    ready-made ``httpx.Response``. Captured requests are returned for asserting
    on the action, page and encoded query parameters.

    Pass ``auth`` to exercise oauth-mode tools against a fake provider; the
    same object is used both by the client and on ``ToolContext.auth``. With
    no ``auth`` the context runs in admin_key mode, as most tool tests expect.
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
        "auth_mode": "oauth" if auth is not None else "admin_key",
        "worksection_account": "acme",
        "worksection_api_key": "k",
        "rate_limit_rps": 50.0,
    }
    if auth is not None:
        base.update(
            oauth_client_id="test-client",
            oauth_client_secret="test-secret",
            fernet_key="test-fernet-key",
        )
    base.update(setting_overrides)
    settings = load_settings(**base)
    provider = auth or AdminKeyAuth(account="acme", api_key="k")
    client = WorksectionClient(
        settings,
        provider,
        http=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    return ToolContext(settings=settings, client=client, auth=provider), recorded
