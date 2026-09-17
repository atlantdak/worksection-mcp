"""Admin API key authentication.

Worksection's admin API authenticates each call with
``md5(page + action + api_key)``. The key itself is never sent, and every
value is handed to httpx as a parameter mapping so it is percent-encoded.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

from worksection_mcp.auth.base import PreparedRequest
from worksection_mcp.config import ACCOUNT_SLUG_RE, Settings
from worksection_mcp.errors import ConfigurationError


def compute_admin_hash(page: str, action: str, api_key: str) -> str:
    """Return the request signature required by the admin API."""
    payload = f"{page}{action}{api_key}".encode()
    return hashlib.md5(payload, usedforsecurity=False).hexdigest()


class AdminKeyAuth:
    """Single-tenant authentication using the account's admin API key."""

    mode = "admin_key"

    def __init__(self, account: str, api_key: str) -> None:
        if not account:
            raise ConfigurationError("admin_key mode requires WORKSECTION_ACCOUNT")
        if not ACCOUNT_SLUG_RE.match(account):
            raise ConfigurationError(
                "account must be a bare Worksection account slug, for example 'acme' "
                "(not a hostname, path, or URL)"
            )
        if not api_key:
            raise ConfigurationError("admin_key mode requires WORKSECTION_API_KEY")
        self.account = account
        self._api_key = api_key

    @property
    def base_url(self) -> str:
        return f"https://{self.account}.worksection.com/api/admin/v2/"

    async def prepare(self, action: str, page: str, params: Mapping[str, str]) -> PreparedRequest:
        query: dict[str, str] = dict(params)
        query["action"] = action
        if page:
            query["page"] = page
        query["hash"] = compute_admin_hash(page, action, self._api_key)
        return PreparedRequest(url=self.base_url, params=query, headers={})


def build_admin_auth(settings: Settings) -> AdminKeyAuth:
    """Construct the provider from settings, failing loudly on the wrong mode."""
    if settings.auth_mode != "admin_key":
        raise ConfigurationError("build_admin_auth called while AUTH_MODE is not admin_key")
    if settings.worksection_api_key is None:
        raise ConfigurationError("WORKSECTION_API_KEY is not set")
    return AdminKeyAuth(
        account=settings.worksection_account,
        api_key=settings.worksection_api_key.get_secret_value(),
    )
