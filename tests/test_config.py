from __future__ import annotations

from pathlib import Path

import pytest

from worksection_mcp.config import Settings, load_settings
from worksection_mcp.errors import ConfigurationError


def _admin_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "auth_mode": "admin_key",
        "worksection_account": "acme",
        "worksection_api_key": "secret-key",
    }
    base.update(overrides)
    return base


def test_admin_mode_builds_base_url() -> None:
    settings = load_settings(**_admin_kwargs())
    assert settings.admin_api_base_url == "https://acme.worksection.com/api/admin/v2/"


def test_destructive_operations_default_to_disabled() -> None:
    assert load_settings(**_admin_kwargs()).allow_destructive_operations is False


def test_admin_mode_requires_account_and_key() -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        load_settings(auth_mode="admin_key", worksection_account="acme")
    assert "WORKSECTION_API_KEY" in str(excinfo.value)


def test_oauth_mode_requires_client_credentials_and_fernet_key() -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        load_settings(auth_mode="oauth")
    message = str(excinfo.value)
    assert "OAUTH_CLIENT_ID" in message
    assert "FERNET_KEY" in message


def test_account_slug_is_validated() -> None:
    with pytest.raises(ConfigurationError):
        load_settings(**_admin_kwargs(worksection_account="acme.worksection.com"))


def test_secrets_are_not_rendered_in_repr() -> None:
    settings = load_settings(**_admin_kwargs())
    assert "secret-key" not in repr(settings)


def test_redirect_uri_is_loopback_https() -> None:
    settings = load_settings(**_admin_kwargs(oauth_redirect_port=18030))
    assert settings.redirect_uri == "https://127.0.0.1:18030/callback"


def test_offload_threshold_must_stay_under_the_mcp_response_cap() -> None:
    with pytest.raises(ConfigurationError):
        load_settings(**_admin_kwargs(offload_threshold_bytes=5_000_000))


def test_file_workspace_dir_must_be_absolute() -> None:
    with pytest.raises(ConfigurationError):
        load_settings(**_admin_kwargs(file_workspace_dir="relative/dir"))


def test_derived_paths_hang_off_state_dir(tmp_path: Path) -> None:
    settings = load_settings(**_admin_kwargs(state_dir=str(tmp_path)))
    assert settings.token_path == tmp_path / "tokens.enc"
    assert settings.offload_dir == tmp_path / "offload"
    assert settings.file_cache_dir == tmp_path / "files"
    assert settings.cert_dir == tmp_path / "certs"


def test_environment_variables_are_read_without_a_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WORKSECTION_ACCOUNT", "envco")
    monkeypatch.setenv("WORKSECTION_API_KEY", "env-key")
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_OPERATIONS", "true")
    settings = load_settings()
    assert settings.worksection_account == "envco"
    assert settings.allow_destructive_operations is True
    assert isinstance(settings, Settings)
