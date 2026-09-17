"""Tools for inspecting and establishing authentication.

In admin_key mode there is nothing to log into, so worksection_login reports
that plainly instead of failing.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from worksection_mcp.tooling import ToolContext, tool


class NoArguments(BaseModel):
    """Tool that takes no arguments."""


class LoginInput(BaseModel):
    timeout_seconds: float = Field(
        default=300.0,
        gt=0,
        le=900.0,
        description="How long to wait for the browser login to complete.",
    )


@tool(
    name="auth_status",
    description=(
        "Report the active authentication mode and, in oauth mode, whether the server "
        "has stored login credentials. This reflects whether credentials are on file, "
        "not whether the access token happens to be fresh right now - an expired token "
        "is refreshed automatically as long as a refresh token is stored. Never returns "
        "token values."
    ),
    input_model=NoArguments,
)
async def auth_status(context: ToolContext, _args: NoArguments) -> dict[str, Any]:
    if context.settings.auth_mode == "admin_key":
        return {
            "auth_mode": "admin_key",
            "authenticated": True,
            "login_required": False,
            "detail": "using the account admin API key; no browser login is needed",
        }
    provider = context.auth
    if provider is not None and hasattr(provider, "status"):
        status = provider.status()
    else:
        status = {"authenticated": False}
    return {"auth_mode": "oauth", "login_required": not status.get("authenticated"), **status}


@tool(
    name="worksection_login",
    description=(
        "Start the OAuth2 browser login. Opens the authorization page, waits for the "
        "loopback redirect, and stores the resulting tokens encrypted on disk. Has "
        "nothing to do in admin_key mode and reports that instead of failing."
    ),
    input_model=LoginInput,
)
async def worksection_login(context: ToolContext, args: LoginInput) -> dict[str, Any]:
    if context.settings.auth_mode == "admin_key":
        return {
            "ok": False,
            "detail": (
                "this server is configured for admin_key mode, which needs no login; "
                "set AUTH_MODE=oauth to use the browser flow"
            ),
        }
    provider = context.auth
    if provider is None or not hasattr(provider, "login"):
        return {"ok": False, "detail": "no OAuth provider is configured"}
    tokens = await provider.login(timeout=args.timeout_seconds)
    return {
        "ok": True,
        "expires_at": tokens.expires_at,
        "scope": tokens.scope,
        "detail": "authorization complete; tokens stored encrypted",
    }


@tool(
    name="worksection_logout",
    description=(
        "Delete the stored OAuth tokens from disk. Only local credentials are removed; "
        "nothing in Worksection itself is affected."
    ),
    input_model=NoArguments,
)
async def worksection_logout(context: ToolContext, _args: NoArguments) -> dict[str, Any]:
    provider = context.auth
    if context.settings.auth_mode == "admin_key" or provider is None:
        return {"cleared": False, "detail": "admin_key mode stores no tokens"}
    if not hasattr(provider, "logout"):
        return {"cleared": False, "detail": "the active provider stores no tokens"}
    return {"cleared": provider.logout(), "detail": "stored credentials removed"}
