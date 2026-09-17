"""The stateless half of the OAuth2 authorization-code flow."""

from __future__ import annotations

import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from worksection_mcp.auth.token_store import TokenSet
from worksection_mcp.errors import AuthenticationError

STATE_BYTES = 32
DEFAULT_EXPIRES_IN = 3600.0


@dataclass(frozen=True)
class AuthorizationRequest:
    """The URL to open in a browser, plus the state to check on the way back."""

    url: str
    state: str


def build_authorization_url(
    *,
    authorize_url: str,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str | None = None,
) -> AuthorizationRequest:
    """Build the authorization URL with a fresh CSRF state."""
    chosen_state = state or secrets.token_urlsafe(STATE_BYTES)
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": chosen_state,
        }
    )
    separator = "&" if "?" in authorize_url else "?"
    return AuthorizationRequest(url=f"{authorize_url}{separator}{query}", state=chosen_state)


def verify_state(expected: str, received: str | None) -> None:
    """Constant-time CSRF state check."""
    if not received or not hmac.compare_digest(expected, received):
        raise AuthenticationError(
            "OAuth callback state did not match the value this process generated; "
            "the login attempt was rejected"
        )


def _token_set(payload: dict[str, Any], now: float, fallback_refresh: str | None) -> TokenSet:
    access_token = payload.get("access_token")
    if not access_token:
        raise AuthenticationError(f"token endpoint returned no access_token: {payload!r}")
    expires_in = float(payload.get("expires_in") or DEFAULT_EXPIRES_IN)
    return TokenSet(
        access_token=str(access_token),
        refresh_token=payload.get("refresh_token") or fallback_refresh,
        expires_at=now + expires_in,
        scope=payload.get("scope"),
        token_type=str(payload.get("token_type", "Bearer")),
    )


async def _post_token_request(
    http: httpx.AsyncClient, token_url: str, form: dict[str, str]
) -> dict[str, Any]:
    response = await http.post(
        token_url,
        data=form,
        headers={"Accept": "application/json"},
    )
    try:
        payload = response.json()
    except ValueError as exc:
        raise AuthenticationError(
            f"token endpoint returned a non-JSON body (HTTP {response.status_code})"
        ) from exc
    if response.status_code >= 400 or "error" in payload:
        detail = payload.get("error_description") or payload.get("error") or response.text[:200]
        raise AuthenticationError(f"token request failed: {detail}")
    return dict(payload)


async def exchange_code(
    http: httpx.AsyncClient,
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    now: float | None = None,
) -> TokenSet:
    """Trade an authorization code for tokens. Credentials go in the POST body."""
    payload = await _post_token_request(
        http,
        token_url,
        {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        },
    )
    return _token_set(payload, time.time() if now is None else now, None)


async def refresh_tokens(
    http: httpx.AsyncClient,
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    now: float | None = None,
) -> TokenSet:
    """Exchange a refresh token for a new access token."""
    payload = await _post_token_request(
        http,
        token_url,
        {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        },
    )
    return _token_set(payload, time.time() if now is None else now, refresh_token)
