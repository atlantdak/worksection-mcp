"""Encrypted-at-rest storage for OAuth2 tokens.

Run ``python -m worksection_mcp.auth.token_store`` to print a fresh key for
FERNET_KEY.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from worksection_mcp.errors import AuthenticationError, ConfigurationError
from worksection_mcp.secure_io import read_secret_file, remove_secret_file, write_secret_file

DEFAULT_LEEWAY_SECONDS = 60.0


@dataclass(frozen=True)
class TokenSet:
    """One user's OAuth2 credentials. ``repr`` deliberately hides the values."""

    access_token: str = field(repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    expires_at: float = 0.0
    scope: str | None = None
    token_type: str = "Bearer"  # noqa: S105 (token category, not a secret)

    def is_expired(self, now: float | None = None, leeway: float = DEFAULT_LEEWAY_SECONDS) -> bool:
        current = time.time() if now is None else now
        return current + leeway >= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "scope": self.scope,
            "token_type": self.token_type,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TokenSet:
        return cls(
            access_token=str(data["access_token"]),
            refresh_token=data.get("refresh_token"),
            expires_at=float(data.get("expires_at", 0.0)),
            scope=data.get("scope"),
            token_type=str(data.get("token_type", "Bearer")),
        )


def generate_fernet_key() -> str:
    """Return a new base64 Fernet key suitable for FERNET_KEY."""
    return Fernet.generate_key().decode("ascii")


class TokenStore:
    """Reads and writes a single Fernet-encrypted token file."""

    def __init__(self, path: Path, fernet_key: str) -> None:
        try:
            self._fernet = Fernet(fernet_key.encode("ascii"))
        except (ValueError, TypeError) as exc:
            raise ConfigurationError(
                "FERNET_KEY is not a valid Fernet key; generate one with "
                "`python -m worksection_mcp.auth.token_store`"
            ) from exc
        self.path = path

    def load(self) -> TokenSet | None:
        blob = read_secret_file(self.path)
        if blob is None:
            return None
        try:
            payload = json.loads(self._fernet.decrypt(blob).decode("utf-8"))
        except (InvalidToken, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise AuthenticationError(
                f"stored tokens at {self.path} could not be decrypted; "
                "remove the file and log in again"
            ) from exc
        return TokenSet.from_dict(payload)

    def save(self, tokens: TokenSet) -> None:
        blob = self._fernet.encrypt(json.dumps(tokens.to_dict()).encode("utf-8"))
        write_secret_file(self.path, blob)

    def clear(self) -> bool:
        return remove_secret_file(self.path)


def _main() -> None:  # pragma: no cover - developer convenience
    print(generate_fernet_key())


if __name__ == "__main__":  # pragma: no cover
    _main()
