from __future__ import annotations

import asyncio
import ssl
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from worksection_mcp.auth import oauth_provider as oauth_provider_module
from worksection_mcp.auth.oauth_flow import verify_state as real_verify_state
from worksection_mcp.auth.oauth_provider import OAuthAuth
from worksection_mcp.auth.token_store import TokenSet, TokenStore, generate_fernet_key
from worksection_mcp.config import Settings, load_settings
from worksection_mcp.errors import AuthenticationError


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    base: dict[str, object] = {
        "auth_mode": "oauth",
        "oauth_client_id": "cid",
        "oauth_client_secret": "csecret",
        "fernet_key": generate_fernet_key(),
        "state_dir": str(tmp_path),
    }
    base.update(overrides)
    return load_settings(**base)


def _store(settings: Settings) -> TokenStore:
    assert settings.fernet_key is not None
    return TokenStore(settings.token_path, settings.fernet_key.get_secret_value())


async def test_prepare_sets_a_bearer_header_and_the_oauth_base_url(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = _store(settings)
    store.save(TokenSet(access_token="at", refresh_token="rt", expires_at=time.time() + 3600))

    async with httpx.AsyncClient() as http:
        auth = OAuthAuth(settings, store, http)
        prepared = await auth.prepare("get_projects", "", {})

    assert auth.mode == "oauth"
    assert prepared.headers["Authorization"] == "Bearer at"
    assert prepared.url == settings.oauth_api_base_url
    assert prepared.params["action"] == "get_projects"
    assert "hash" not in prepared.params


async def test_prepare_refreshes_an_expired_token_and_persists_it(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = _store(settings)
    store.save(TokenSet(access_token="old", refresh_token="rt", expires_at=time.time() - 10))

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.content.decode())
        return httpx.Response(200, json={"access_token": "new", "expires_in": 3600})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        auth = OAuthAuth(settings, store, http)
        prepared = await auth.prepare("get_projects", "", {})

    assert prepared.headers["Authorization"] == "Bearer new"
    assert "grant_type=refresh_token" in calls[0]
    reloaded = store.load()
    assert reloaded is not None
    assert reloaded.access_token == "new"
    assert reloaded.refresh_token == "rt"


async def test_prepare_without_stored_tokens_tells_the_user_to_log_in(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    async with httpx.AsyncClient() as http:
        auth = OAuthAuth(settings, _store(settings), http)
        with pytest.raises(AuthenticationError, match="worksection_login"):
            await auth.prepare("get_projects", "", {})


async def test_expired_token_without_a_refresh_token_requires_a_new_login(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    store = _store(settings)
    store.save(TokenSet(access_token="old", refresh_token=None, expires_at=time.time() - 10))
    async with httpx.AsyncClient() as http:
        auth = OAuthAuth(settings, store, http)
        with pytest.raises(AuthenticationError, match="worksection_login"):
            await auth.prepare("get_projects", "", {})


async def test_status_reports_without_revealing_tokens(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = _store(settings)
    # Deliberately not "at"/"rt": those two letters are a substring of the
    # word "authenticated", which the status payload always contains, so a
    # value that short would make the leak check below meaningless.
    store.save(
        TokenSet(
            access_token="secret-access-value",
            refresh_token="secret-refresh-value",
            expires_at=1_700_000_000.0,
        )
    )
    async with httpx.AsyncClient() as http:
        status: dict[str, Any] = OAuthAuth(settings, store, http).status()
    assert status["authenticated"] is True
    assert status["has_refresh_token"] is True
    assert "secret-access-value" not in repr(status)
    assert "secret-refresh-value" not in repr(status)


async def test_logout_clears_stored_tokens(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = _store(settings)
    store.save(TokenSet(access_token="at", refresh_token="rt", expires_at=1.0))
    async with httpx.AsyncClient() as http:
        auth = OAuthAuth(settings, store, http)
        assert auth.logout() is True
        assert auth.status()["authenticated"] is False


async def test_login_runs_the_full_loopback_flow(tmp_path: Path) -> None:
    """Open the authorization URL by driving the loopback listener directly."""
    import asyncio
    import ssl
    from urllib.parse import parse_qs, urlparse

    settings = _settings(tmp_path, oauth_redirect_port=0)
    store = _store(settings)

    def token_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"access_token": "fresh", "refresh_token": "rt", "expires_in": 3600}
        )

    opened: list[str] = []

    async def drive_browser(url: str) -> None:
        query = parse_qs(urlparse(url).query)
        redirect = query["redirect_uri"][0]
        state = query["state"][0]
        context = ssl.create_default_context(cafile=str(settings.cert_dir / "callback-cert.pem"))
        context.check_hostname = False
        async with httpx.AsyncClient(verify=context) as browser:
            await browser.get(f"{redirect}?code=the-code&state={state}")

    def opener(url: str) -> None:
        opened.append(url)
        asyncio.get_running_loop().create_task(drive_browser(url))

    async with httpx.AsyncClient(transport=httpx.MockTransport(token_handler)) as http:
        auth = OAuthAuth(settings, store, http, opener=opener)
        tokens = await auth.login(timeout=15.0)

    assert tokens.access_token == "fresh"
    assert opened and opened[0].startswith(settings.oauth_authorize_url)
    stored = store.load()
    assert stored is not None
    assert stored.access_token == "fresh"


def _sslcontext(settings: Settings) -> ssl.SSLContext:
    context = ssl.create_default_context(cafile=str(settings.cert_dir / "callback-cert.pem"))
    context.check_hostname = False
    return context


async def test_login_calls_verify_state_with_the_sent_and_received_state(tmp_path: Path) -> None:
    """The exact two values compared must be the state this process generated and
    the state the callback reported -- not some other pair."""
    settings = _settings(tmp_path, oauth_redirect_port=0)
    store = _store(settings)

    captured: list[tuple[str, str | None]] = []

    def spy(expected: str, received: str | None) -> None:
        captured.append((expected, received))
        real_verify_state(expected, received)

    def token_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "fresh", "expires_in": 3600})

    sent_state: dict[str, str] = {}

    async def drive_browser(url: str) -> None:
        query = parse_qs(urlparse(url).query)
        redirect = query["redirect_uri"][0]
        sent_state["value"] = query["state"][0]
        async with httpx.AsyncClient(verify=_sslcontext(settings)) as browser:
            await browser.get(f"{redirect}?code=the-code&state={sent_state['value']}")

    def opener(url: str) -> None:
        asyncio.get_running_loop().create_task(drive_browser(url))

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(oauth_provider_module, "verify_state", spy)
        async with httpx.AsyncClient(transport=httpx.MockTransport(token_handler)) as http:
            auth = OAuthAuth(settings, store, http, opener=opener)
            await auth.login(timeout=15.0)

    assert len(captured) == 1
    expected, received = captured[0]
    assert received == sent_state["value"]
    assert expected == received


async def test_login_aborts_and_never_exchanges_the_code_on_a_state_mismatch(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, oauth_redirect_port=0)
    store = _store(settings)

    exchange_calls: list[str] = []

    def token_handler(request: httpx.Request) -> httpx.Response:
        exchange_calls.append(request.content.decode())
        return httpx.Response(200, json={"access_token": "should-not-be-used", "expires_in": 3600})

    async def drive_browser(url: str) -> None:
        query = parse_qs(urlparse(url).query)
        redirect = query["redirect_uri"][0]
        async with httpx.AsyncClient(verify=_sslcontext(settings)) as browser:
            # A state that does not match the one the authorization request
            # carried -- as if an attacker completed their own flow and fed
            # the victim this redirect (a CSRF login attempt).
            await browser.get(f"{redirect}?code=attacker-code&state=not-the-real-state")

    def opener(url: str) -> None:
        asyncio.get_running_loop().create_task(drive_browser(url))

    async with httpx.AsyncClient(transport=httpx.MockTransport(token_handler)) as http:
        auth = OAuthAuth(settings, store, http, opener=opener)
        with pytest.raises(AuthenticationError, match="state"):
            await auth.login(timeout=15.0)

    assert exchange_calls == []
    assert store.load() is None


async def test_login_saves_the_freshly_exchanged_tokens(tmp_path: Path) -> None:
    settings = _settings(tmp_path, oauth_redirect_port=0)
    store = _store(settings)

    saved: list[TokenSet] = []
    real_save = TokenStore.save

    def spy_save(self: TokenStore, tokens: TokenSet) -> None:
        saved.append(tokens)
        real_save(self, tokens)

    def token_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "brand-new",
                "refresh_token": "brand-new-rt",
                "expires_in": 3600,
            },
        )

    async def drive_browser(url: str) -> None:
        query = parse_qs(urlparse(url).query)
        redirect = query["redirect_uri"][0]
        state = query["state"][0]
        async with httpx.AsyncClient(verify=_sslcontext(settings)) as browser:
            await browser.get(f"{redirect}?code=the-code&state={state}")

    def opener(url: str) -> None:
        asyncio.get_running_loop().create_task(drive_browser(url))

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(TokenStore, "save", spy_save)
        async with httpx.AsyncClient(transport=httpx.MockTransport(token_handler)) as http:
            auth = OAuthAuth(settings, store, http, opener=opener)
            await auth.login(timeout=15.0)

    assert len(saved) == 1
    assert saved[0].access_token == "brand-new"


async def test_refresh_saves_the_new_tokens_not_the_stale_ones(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = _store(settings)
    store.save(TokenSet(access_token="stale", refresh_token="rt", expires_at=time.time() - 10))

    saved: list[TokenSet] = []
    real_save = TokenStore.save

    def spy_save(self: TokenStore, tokens: TokenSet) -> None:
        saved.append(tokens)
        real_save(self, tokens)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "rotated", "expires_in": 3600})

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(TokenStore, "save", spy_save)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            auth = OAuthAuth(settings, store, http)
            await auth.prepare("get_projects", "", {})

    assert len(saved) == 1
    assert saved[0].access_token == "rotated"
    assert saved[0].access_token != "stale"


async def test_prepare_refreshes_a_token_that_is_near_expiry_not_only_a_fully_expired_one(
    tmp_path: Path,
) -> None:
    """A token inside the leeway window is treated as unusable, so the caller
    never sends a request with an access token seconds away from rejection."""
    settings = _settings(tmp_path)
    store = _store(settings)
    store.save(
        TokenSet(access_token="about-to-expire", refresh_token="rt", expires_at=time.time() + 30)
    )

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.content.decode())
        return httpx.Response(200, json={"access_token": "refreshed-in-time", "expires_in": 3600})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        auth = OAuthAuth(settings, store, http)
        prepared = await auth.prepare("get_projects", "", {})

    assert calls, "expected a refresh request for a near-expiry token"
    assert prepared.headers["Authorization"] == "Bearer refreshed-in-time"
