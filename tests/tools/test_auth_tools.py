from __future__ import annotations

from typing import Any

from tests.support import make_context
from worksection_mcp.auth.base import PreparedRequest
from worksection_mcp.auth.token_store import TokenSet
from worksection_mcp.tooling import dispatch


class FakeOAuth:
    mode = "oauth"

    def __init__(self) -> None:
        self.logged_in = False
        self.cleared = False

    async def prepare(self, action: str, page: str, params: Any) -> PreparedRequest:
        return PreparedRequest(url="https://worksection.com/api/oauth2/", params=dict(params))

    async def login(self, *, timeout: float = 300.0) -> TokenSet:  # noqa: ASYNC109
        self.logged_in = True
        return TokenSet(access_token="at", refresh_token="rt", expires_at=123.0, scope="all")

    def status(self) -> dict[str, Any]:
        return {"authenticated": self.logged_in, "has_refresh_token": True}

    def logout(self) -> bool:
        self.cleared = True
        return True


async def test_auth_status_in_admin_mode_reports_the_mode() -> None:
    context, _ = make_context([])
    result: Any = await dispatch(context, "auth_status", {})
    assert result["auth_mode"] == "admin_key"
    assert result["authenticated"] is True
    assert result["login_required"] is False


async def test_login_is_refused_in_admin_mode() -> None:
    context, _ = make_context([])
    result: Any = await dispatch(context, "worksection_login", {})
    assert result["ok"] is False
    assert "admin_key" in result["detail"]


async def test_login_runs_the_oauth_flow() -> None:
    auth = FakeOAuth()
    context, _ = make_context([], auth=auth)
    result: Any = await dispatch(context, "worksection_login", {})
    assert auth.logged_in is True
    assert result["ok"] is True
    assert "access_token" not in repr(result)


async def test_auth_status_in_oauth_mode_delegates_to_the_provider() -> None:
    auth = FakeOAuth()
    auth.logged_in = True
    context, _ = make_context([], auth=auth)
    result: Any = await dispatch(context, "auth_status", {})
    assert result["authenticated"] is True
    assert result["auth_mode"] == "oauth"


async def test_logout_clears_credentials() -> None:
    auth = FakeOAuth()
    context, _ = make_context([], auth=auth)
    result: Any = await dispatch(context, "worksection_logout", {})
    assert auth.cleared is True
    assert result["cleared"] is True
