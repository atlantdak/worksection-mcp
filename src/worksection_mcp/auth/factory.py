"""Pick the authentication provider the configuration asks for."""

from __future__ import annotations

import httpx

from worksection_mcp.auth.admin_key import build_admin_auth
from worksection_mcp.auth.base import AuthProvider
from worksection_mcp.auth.oauth_provider import OAuthAuth
from worksection_mcp.auth.token_store import TokenStore
from worksection_mcp.config import Settings
from worksection_mcp.errors import ConfigurationError


def build_auth_provider(
    settings: Settings, *, http: httpx.AsyncClient | None = None
) -> AuthProvider:
    """Build the provider for the configured AUTH_MODE."""
    if settings.auth_mode == "admin_key":
        return build_admin_auth(settings)
    if settings.fernet_key is None:
        raise ConfigurationError("oauth mode requires FERNET_KEY")
    store = TokenStore(settings.token_path, settings.fernet_key.get_secret_value())
    client = http or httpx.AsyncClient(timeout=settings.request_timeout_seconds)
    return OAuthAuth(settings, store, client)
