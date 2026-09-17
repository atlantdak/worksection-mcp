from __future__ import annotations

from pathlib import Path

import pytest

from worksection_mcp.auth.admin_key import AdminKeyAuth
from worksection_mcp.auth.factory import build_auth_provider
from worksection_mcp.auth.oauth_provider import OAuthAuth
from worksection_mcp.auth.token_store import generate_fernet_key
from worksection_mcp.config import load_settings
from worksection_mcp.errors import ConfigurationError


def test_admin_mode_builds_the_admin_provider() -> None:
    settings = load_settings(
        auth_mode="admin_key", worksection_account="acme", worksection_api_key="k"
    )
    assert isinstance(build_auth_provider(settings), AdminKeyAuth)


def test_oauth_mode_builds_the_oauth_provider(tmp_path: Path) -> None:
    settings = load_settings(
        auth_mode="oauth",
        oauth_client_id="cid",
        oauth_client_secret="csecret",
        fernet_key=generate_fernet_key(),
        state_dir=str(tmp_path),
    )
    provider = build_auth_provider(settings)
    assert isinstance(provider, OAuthAuth)
    assert provider.mode == "oauth"


def test_an_invalid_fernet_key_is_reported_as_configuration_error(tmp_path: Path) -> None:
    settings = load_settings(
        auth_mode="oauth",
        oauth_client_id="cid",
        oauth_client_secret="csecret",
        fernet_key="not-a-key",
        state_dir=str(tmp_path),
    )
    with pytest.raises(ConfigurationError):
        build_auth_provider(settings)
