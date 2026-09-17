from __future__ import annotations

import sys
from pathlib import Path

import pytest

from worksection_mcp.auth.token_store import TokenSet, TokenStore, generate_fernet_key
from worksection_mcp.errors import AuthenticationError


def _tokens(expires_at: float = 2_000_000_000.0) -> TokenSet:
    return TokenSet(
        access_token="at-123",
        refresh_token="rt-456",
        expires_at=expires_at,
        scope="all",
        token_type="Bearer",
    )


def test_generate_fernet_key_is_usable() -> None:
    key = generate_fernet_key()
    assert isinstance(key, str)
    assert len(key) == 44


def test_round_trip(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "tokens.enc", generate_fernet_key())
    assert store.load() is None
    store.save(_tokens())
    loaded = store.load()
    assert loaded is not None
    assert loaded.access_token == "at-123"
    assert loaded.refresh_token == "rt-456"
    assert loaded.scope == "all"


def test_tokens_are_not_stored_in_plaintext(tmp_path: Path) -> None:
    path = tmp_path / "tokens.enc"
    TokenStore(path, generate_fernet_key()).save(_tokens())
    blob = path.read_bytes()
    assert b"at-123" not in blob
    assert b"rt-456" not in blob


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits only")
def test_token_file_is_owner_only(tmp_path: Path) -> None:
    path = tmp_path / "state" / "tokens.enc"
    TokenStore(path, generate_fernet_key()).save(_tokens())
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700


def test_a_different_key_cannot_decrypt(tmp_path: Path) -> None:
    path = tmp_path / "tokens.enc"
    TokenStore(path, generate_fernet_key()).save(_tokens())
    with pytest.raises(AuthenticationError, match="could not be decrypted"):
        TokenStore(path, generate_fernet_key()).load()


def test_corrupt_file_raises_a_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "tokens.enc"
    path.write_bytes(b"not fernet")
    with pytest.raises(AuthenticationError):
        TokenStore(path, generate_fernet_key()).load()


def test_clear_removes_the_file(tmp_path: Path) -> None:
    path = tmp_path / "tokens.enc"
    store = TokenStore(path, generate_fernet_key())
    store.save(_tokens())
    assert store.clear() is True
    assert store.load() is None
    assert store.clear() is False


def test_expiry_check_uses_a_leeway() -> None:
    assert _tokens(expires_at=1_000.0).is_expired(now=2_000.0) is True
    assert _tokens(expires_at=1_000.0).is_expired(now=500.0) is False
    assert _tokens(expires_at=1_000.0).is_expired(now=970.0, leeway=60.0) is True


def test_dict_round_trip() -> None:
    tokens = _tokens()
    assert TokenSet.from_dict(tokens.to_dict()) == tokens


def test_repr_does_not_leak_tokens() -> None:
    assert "at-123" not in repr(_tokens())
