"""Per-user OAuth2 authentication with automatic refresh."""

from __future__ import annotations

import webbrowser
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from worksection_mcp.auth.base import PreparedRequest
from worksection_mcp.auth.callback import LocalCallbackServer, ensure_self_signed_cert
from worksection_mcp.auth.oauth_flow import (
    build_authorization_url,
    exchange_code,
    refresh_tokens,
    verify_state,
)
from worksection_mcp.auth.token_store import TokenSet, TokenStore
from worksection_mcp.config import Settings
from worksection_mcp.errors import AuthenticationError, ConfigurationError
from worksection_mcp.logging_setup import get_logger

logger = get_logger("auth.oauth")

LOGIN_HINT = "no valid credentials; run the worksection_login tool to authorize this server"


class OAuthAuth:
    """Adds a bearer token to each request, refreshing it when it has expired."""

    mode = "oauth"

    def __init__(
        self,
        settings: Settings,
        store: TokenStore,
        http: httpx.AsyncClient,
        *,
        opener: Callable[[str], None] | None = None,
    ) -> None:
        if settings.oauth_client_id is None or settings.oauth_client_secret is None:
            raise ConfigurationError("oauth mode requires OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET")
        self._settings = settings
        self._store = store
        self._http = http
        self._open = opener or webbrowser.open
        self._client_id = settings.oauth_client_id
        self._client_secret = settings.oauth_client_secret.get_secret_value()

    async def ensure_tokens(self) -> TokenSet:
        """Return usable tokens, refreshing them if needed."""
        tokens = self._store.load()
        if tokens is None:
            raise AuthenticationError(LOGIN_HINT)
        if not tokens.is_expired():
            return tokens
        if not tokens.refresh_token:
            raise AuthenticationError(f"access token expired and {LOGIN_HINT}")
        logger.info("access token expired; refreshing")
        refreshed = await refresh_tokens(
            self._http,
            token_url=self._settings.oauth_token_url,
            client_id=self._client_id,
            client_secret=self._client_secret,
            refresh_token=tokens.refresh_token,
        )
        self._store.save(refreshed)
        return refreshed

    async def prepare(self, action: str, page: str, params: Mapping[str, str]) -> PreparedRequest:
        tokens = await self.ensure_tokens()
        query: dict[str, str] = dict(params)
        query["action"] = action
        if page:
            query["page"] = page
        return PreparedRequest(
            url=self._settings.oauth_api_base_url,
            params=query,
            headers={"Authorization": f"{tokens.token_type} {tokens.access_token}"},
        )

    async def login(self, *, timeout: float = 300.0) -> TokenSet:  # noqa: ASYNC109
        """Run the browser authorization-code flow and store the result."""
        cert_path, key_path = ensure_self_signed_cert(self._settings.cert_dir)
        async with LocalCallbackServer(
            port=self._settings.oauth_redirect_port, cert_path=cert_path, key_path=key_path
        ) as server:
            # Captured while the listener is still up: the property reads the
            # bound socket, which is gone once the `async with` block exits.
            redirect_uri = server.redirect_uri
            request = build_authorization_url(
                authorize_url=self._settings.oauth_authorize_url,
                client_id=self._client_id,
                redirect_uri=redirect_uri,
                scope=self._settings.oauth_scope,
            )
            self._open(request.url)
            result = await server.wait_for_callback(timeout=timeout)

        if result.error:
            raise AuthenticationError(f"authorization was refused: {result.error}")
        verify_state(request.state, result.state)
        if not result.code:
            raise AuthenticationError("authorization callback carried no code")

        tokens = await exchange_code(
            self._http,
            token_url=self._settings.oauth_token_url,
            client_id=self._client_id,
            client_secret=self._client_secret,
            code=result.code,
            redirect_uri=redirect_uri,
        )
        self._store.save(tokens)
        logger.info("authorization complete; tokens stored")
        return tokens

    def status(self) -> dict[str, Any]:
        """Describe the stored credentials without revealing any of them."""
        try:
            tokens = self._store.load()
        except AuthenticationError as exc:
            return {"authenticated": False, "detail": str(exc)}
        if tokens is None:
            return {"authenticated": False, "detail": LOGIN_HINT}
        # Credentials are on file, which is what "authenticated" reports here;
        # an expired access token is refreshed transparently on the next
        # prepare() call as long as a refresh token is present, so expiry by
        # itself does not mean the user needs to log in again.
        return {
            "authenticated": True,
            "expires_at": tokens.expires_at,
            "has_refresh_token": bool(tokens.refresh_token),
            "scope": tokens.scope,
            "token_file": str(self._store.path),
        }

    def logout(self) -> bool:
        """Delete the stored tokens. Returns True when something was removed."""
        return self._store.clear()
