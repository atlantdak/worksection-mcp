from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from worksection_mcp.auth.oauth_flow import (
    build_authorization_url,
    exchange_code,
    refresh_tokens,
    verify_state,
)
from worksection_mcp.errors import AuthenticationError

AUTHORIZE = "https://worksection.com/oauth2/authorize"
TOKEN = "https://worksection.com/oauth2/token"


def test_authorization_url_contains_every_required_parameter() -> None:
    request = build_authorization_url(
        authorize_url=AUTHORIZE,
        client_id="cid",
        redirect_uri="https://127.0.0.1:18030/callback",
        scope="all",
    )
    query = parse_qs(urlparse(request.url).query)
    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["cid"]
    assert query["redirect_uri"] == ["https://127.0.0.1:18030/callback"]
    assert query["scope"] == ["all"]
    assert query["state"] == [request.state]


def test_redirect_uri_is_encoded_not_concatenated() -> None:
    request = build_authorization_url(
        authorize_url=AUTHORIZE,
        client_id="cid",
        redirect_uri="https://127.0.0.1:18030/callback?x=1&y=2",
        scope="all",
    )
    assert "%3Fx%3D1%26y%3D2" in request.url


def test_state_is_long_and_unpredictable() -> None:
    first = build_authorization_url(
        authorize_url=AUTHORIZE, client_id="c", redirect_uri="https://127.0.0.1/cb", scope="all"
    )
    second = build_authorization_url(
        authorize_url=AUTHORIZE, client_id="c", redirect_uri="https://127.0.0.1/cb", scope="all"
    )
    assert len(first.state) >= 32
    assert first.state != second.state


def test_verify_state_accepts_a_match() -> None:
    verify_state("abc", "abc")


@pytest.mark.parametrize("received", [None, "", "different"])
def test_verify_state_rejects_a_mismatch(received: str | None) -> None:
    with pytest.raises(AuthenticationError, match="state"):
        verify_state("abc", received)


async def test_exchange_code_posts_form_data_and_builds_a_token_set() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["content"] = request.content.decode()
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "access_token": "at",
                "refresh_token": "rt",
                "expires_in": 3600,
                "scope": "all",
                "token_type": "Bearer",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        tokens = await exchange_code(
            http,
            token_url=TOKEN,
            client_id="cid",
            client_secret="csecret",
            code="the-code",
            redirect_uri="https://127.0.0.1:18030/callback",
            now=1_000.0,
        )

    assert tokens.access_token == "at"
    assert tokens.refresh_token == "rt"
    assert tokens.expires_at == 4_600.0
    assert "grant_type=authorization_code" in str(captured["content"])
    assert "code=the-code" in str(captured["content"])
    assert "csecret" not in str(captured["url"])


async def test_exchange_code_raises_on_an_error_payload() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(AuthenticationError, match="invalid_grant"):
            await exchange_code(
                http,
                token_url=TOKEN,
                client_id="cid",
                client_secret="csecret",
                code="bad",
                redirect_uri="https://127.0.0.1:18030/callback",
            )


async def test_refresh_keeps_the_old_refresh_token_when_none_is_returned() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "at2", "expires_in": 60})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        tokens = await refresh_tokens(
            http,
            token_url=TOKEN,
            client_id="cid",
            client_secret="csecret",
            refresh_token="rt",
            now=10.0,
        )

    assert tokens.access_token == "at2"
    assert tokens.refresh_token == "rt"
    assert tokens.expires_at == 70.0


async def test_refresh_reports_a_revoked_grant() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid_token"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(AuthenticationError):
            await refresh_tokens(
                http, token_url=TOKEN, client_id="c", client_secret="s", refresh_token="rt"
            )
