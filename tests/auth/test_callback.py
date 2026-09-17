from __future__ import annotations

import asyncio
import socket
import ssl
import sys
from pathlib import Path

import httpx
import pytest

from worksection_mcp.auth.callback import (
    CallbackResult,
    LocalCallbackServer,
    ensure_self_signed_cert,
    parse_callback_target,
)


def test_parse_callback_target_extracts_code_and_state() -> None:
    result = parse_callback_target("/callback?code=abc&state=xyz")
    assert result == CallbackResult(code="abc", state="xyz", error=None)


def test_parse_callback_target_decodes_percent_escapes() -> None:
    assert parse_callback_target("/callback?code=a%2Bb%2Fc&state=s").code == "a+b/c"


def test_parse_callback_target_reports_provider_errors() -> None:
    result = parse_callback_target("/callback?error=access_denied&state=xyz")
    assert result.error == "access_denied"
    assert result.code is None


def test_parse_callback_target_without_a_query() -> None:
    assert parse_callback_target("/callback") == CallbackResult(None, None, None)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits only")
def test_certificate_is_generated_once_and_kept_private(tmp_path: Path) -> None:
    cert, key = ensure_self_signed_cert(tmp_path)
    assert cert.is_file()
    assert key.stat().st_mode & 0o777 == 0o600
    first = cert.read_bytes()
    again_cert, _ = ensure_self_signed_cert(tmp_path)
    assert again_cert.read_bytes() == first


async def test_server_binds_loopback_only_and_receives_the_callback(tmp_path: Path) -> None:
    cert, key = ensure_self_signed_cert(tmp_path)
    async with LocalCallbackServer(port=0, cert_path=cert, key_path=key) as server:
        assert server.redirect_uri.startswith("https://127.0.0.1:")
        for socket in server.sockets:
            assert socket.getsockname()[0] == "127.0.0.1"

        context = ssl.create_default_context(cafile=str(cert))
        context.check_hostname = False
        waiter = asyncio.create_task(server.wait_for_callback(timeout=10.0))
        async with httpx.AsyncClient(verify=context) as client:
            response = await client.get(f"{server.redirect_uri}?code=the-code&state=the-state")
        assert response.status_code == 200
        assert "can close this window" in response.text.lower()
        result = await waiter

    assert result.code == "the-code"
    assert result.state == "the-state"


async def test_wait_for_callback_times_out(tmp_path: Path) -> None:
    cert, key = ensure_self_signed_cert(tmp_path)
    async with LocalCallbackServer(port=0, cert_path=cert, key_path=key) as server:
        with pytest.raises(TimeoutError):
            await server.wait_for_callback(timeout=0.2)


def test_non_loopback_host_is_rejected(tmp_path: Path) -> None:
    cert, key = ensure_self_signed_cert(tmp_path)
    for forbidden in ("0.0.0.0", "::", ""):  # noqa: S104
        with pytest.raises(ValueError, match="loopback"):
            LocalCallbackServer(port=0, cert_path=cert, key_path=key, host=forbidden)


async def test_binds_the_literal_loopback_address_even_if_localhost_is_requested(
    tmp_path: Path,
) -> None:
    cert, key = ensure_self_signed_cert(tmp_path)
    async with LocalCallbackServer(
        port=0, cert_path=cert, key_path=key, host="localhost"
    ) as server:
        assert server.redirect_uri.startswith("https://127.0.0.1:")
        assert server.sockets
        for sock in server.sockets:
            assert sock.getsockname()[0] == "127.0.0.1"
            assert sock.family in (socket.AF_INET,)
