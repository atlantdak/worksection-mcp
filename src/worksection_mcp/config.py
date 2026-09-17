"""Validated runtime configuration.

Environment variables are read without a prefix, so ``WORKSECTION_API_KEY``
maps to :attr:`Settings.worksection_api_key` and ``ALLOW_DESTRUCTIVE_OPERATIONS``
to :attr:`Settings.allow_destructive_operations`.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from worksection_mcp.errors import ConfigurationError

AuthMode = Literal["admin_key", "oauth"]

ACCOUNT_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
MCP_RESPONSE_CAP_BYTES = 1_000_000


class Settings(BaseSettings):
    """Every knob the server exposes, validated at load time."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    auth_mode: AuthMode = "admin_key"

    worksection_account: str = ""
    worksection_api_key: SecretStr | None = None

    oauth_client_id: str | None = None
    oauth_client_secret: SecretStr | None = None
    oauth_authorize_url: str = "https://worksection.com/oauth2/authorize"
    oauth_token_url: str = "https://worksection.com/oauth2/token"  # noqa: S105 (URL, not a secret)
    oauth_api_base_url: str = "https://worksection.com/api/oauth2/"
    oauth_scope: str = "all"
    oauth_redirect_port: int = Field(default=18030, ge=1024, le=65535)
    fernet_key: SecretStr | None = None

    state_dir: Path = Path.home() / ".worksection-mcp"

    allow_destructive_operations: bool = False
    file_workspace_dir: Path | None = None

    request_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    max_retries: int = Field(default=3, ge=0, le=10)
    rate_limit_rps: float = Field(default=3.0, gt=0, le=50)

    cache_enabled: bool = True
    cache_ttl_seconds: int = Field(default=60, ge=0, le=3600)
    file_cache_max_bytes: int = Field(default=256 * 1024 * 1024, ge=0)

    offload_threshold_bytes: int = Field(default=50_000, ge=1_024)
    offload_chunk_bytes: int = Field(default=32_000, ge=1_024, le=200_000)

    log_level: str = "INFO"

    @field_validator("worksection_account")
    @classmethod
    def _validate_account(cls, value: str) -> str:
        normalised = value.strip().lower()
        if normalised and not ACCOUNT_SLUG_RE.match(normalised):
            raise ValueError(
                "WORKSECTION_ACCOUNT must be the bare account slug, for example 'acme' "
                "(not a full hostname or URL)"
            )
        return normalised

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        level = value.strip().upper()
        if level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError("LOG_LEVEL must be one of CRITICAL, ERROR, WARNING, INFO, DEBUG")
        return level

    @field_validator("state_dir", "file_workspace_dir")
    @classmethod
    def _expand(cls, value: Path | None) -> Path | None:
        return None if value is None else value.expanduser()

    @model_validator(mode="after")
    def _validate_combination(self) -> Settings:
        problems: list[str] = []
        if self.auth_mode == "admin_key":
            if not self.worksection_account:
                problems.append("WORKSECTION_ACCOUNT is required in admin_key mode")
            if self.worksection_api_key is None:
                problems.append("WORKSECTION_API_KEY is required in admin_key mode")
        else:
            if not self.oauth_client_id:
                problems.append("OAUTH_CLIENT_ID is required in oauth mode")
            if self.oauth_client_secret is None:
                problems.append("OAUTH_CLIENT_SECRET is required in oauth mode")
            if self.fernet_key is None:
                problems.append(
                    "FERNET_KEY is required in oauth mode (generate one with "
                    "`python -m worksection_mcp.auth.token_store`)"
                )
        if self.offload_threshold_bytes >= MCP_RESPONSE_CAP_BYTES:
            problems.append(
                "OFFLOAD_THRESHOLD_BYTES must stay below the 1 MB protocol response cap"
            )
        if self.file_workspace_dir is not None and not self.file_workspace_dir.is_absolute():
            problems.append("FILE_WORKSPACE_DIR must be an absolute path")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def admin_api_base_url(self) -> str:
        return f"https://{self.worksection_account}.worksection.com/api/admin/v2/"

    @property
    def api_base_url(self) -> str:
        return self.admin_api_base_url if self.auth_mode == "admin_key" else self.oauth_api_base_url

    @property
    def redirect_uri(self) -> str:
        return f"https://127.0.0.1:{self.oauth_redirect_port}/callback"

    @property
    def token_path(self) -> Path:
        return self.state_dir / "tokens.enc"

    @property
    def offload_dir(self) -> Path:
        return self.state_dir / "offload"

    @property
    def file_cache_dir(self) -> Path:
        return self.state_dir / "files"

    @property
    def cert_dir(self) -> Path:
        return self.state_dir / "certs"


def _format_validation_error(exc: ValidationError) -> str:
    parts: list[str] = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error["loc"]) or "settings"
        parts.append(f"{location}: {error['msg']}")
    return "Invalid configuration -> " + " | ".join(parts)


def load_settings(**overrides: object) -> Settings:
    """Build :class:`Settings`, converting validation failures into ConfigurationError."""
    try:
        return Settings(**overrides)  # type: ignore[arg-type]
    except ValidationError as exc:
        raise ConfigurationError(_format_validation_error(exc)) from exc


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide settings singleton. Call ``get_settings.cache_clear()`` in tests."""
    return load_settings()
