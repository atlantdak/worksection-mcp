from __future__ import annotations

import hashlib

import httpx
import pytest

from worksection_mcp.auth.admin_key import AdminKeyAuth, build_admin_auth, compute_admin_hash
from worksection_mcp.config import load_settings
from worksection_mcp.errors import ConfigurationError


def test_hash_matches_the_documented_scheme() -> None:
    expected = hashlib.md5(b"/project/12/get_taskAPIKEY", usedforsecurity=False).hexdigest()
    assert compute_admin_hash("/project/12/", "get_task", "APIKEY") == expected


def test_hash_handles_an_empty_page() -> None:
    expected = hashlib.md5(b"get_projectsAPIKEY", usedforsecurity=False).hexdigest()
    assert compute_admin_hash("", "get_projects", "APIKEY") == expected


async def test_prepare_returns_account_url_action_and_hash() -> None:
    auth = AdminKeyAuth(account="acme", api_key="APIKEY")
    prepared = await auth.prepare("get_projects", "", {})
    assert auth.mode == "admin_key"
    assert prepared.url == "https://acme.worksection.com/api/admin/v2/"
    assert prepared.params["action"] == "get_projects"
    assert prepared.params["hash"] == compute_admin_hash("", "get_projects", "APIKEY")
    assert "page" not in prepared.params
    assert prepared.headers == {}


async def test_prepare_includes_page_when_present() -> None:
    auth = AdminKeyAuth(account="acme", api_key="APIKEY")
    prepared = await auth.prepare("get_task", "/project/12/", {})
    assert prepared.params["page"] == "/project/12/"
    assert prepared.params["hash"] == compute_admin_hash("/project/12/", "get_task", "APIKEY")


async def test_caller_params_are_preserved_and_encoded_by_httpx() -> None:
    auth = AdminKeyAuth(account="acme", api_key="APIKEY")
    prepared = await auth.prepare("post_task", "/project/12/", {"title": "Ship it & tell Bob"})
    url = str(httpx.Request("GET", prepared.url, params=prepared.params).url)
    assert "Ship+it+%26+tell+Bob" in url or "Ship%20it%20%26%20tell%20Bob" in url
    assert "&tell" not in url.split("title=")[1].split("&")[0]


async def test_api_key_is_never_placed_in_the_query() -> None:
    auth = AdminKeyAuth(account="acme", api_key="APIKEY")
    prepared = await auth.prepare("get_projects", "", {})
    assert "APIKEY" not in str(prepared.params)


def test_build_admin_auth_reads_settings() -> None:
    settings = load_settings(
        auth_mode="admin_key", worksection_account="acme", worksection_api_key="APIKEY"
    )
    auth = build_admin_auth(settings)
    assert auth.account == "acme"


def test_rejects_an_account_with_a_slash() -> None:
    with pytest.raises(ConfigurationError):
        AdminKeyAuth(account="evil.com/../attacker", api_key="APIKEY")


def test_rejects_an_uppercase_account() -> None:
    with pytest.raises(ConfigurationError):
        AdminKeyAuth(account="ACME", api_key="APIKEY")


def test_build_admin_auth_rejects_oauth_settings() -> None:
    settings = load_settings(
        auth_mode="oauth",
        oauth_client_id="id",
        oauth_client_secret="secret",
        fernet_key="key",
    )
    with pytest.raises(ConfigurationError):
        build_admin_auth(settings)
