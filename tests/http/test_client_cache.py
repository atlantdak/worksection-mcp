from __future__ import annotations

import httpx

from worksection_mcp.auth.admin_key import AdminKeyAuth
from worksection_mcp.cache.session_cache import SessionCache
from worksection_mcp.config import load_settings
from worksection_mcp.http.client import WorksectionClient


def _client(handler: httpx.MockTransport, cache: SessionCache) -> WorksectionClient:
    settings = load_settings(
        auth_mode="admin_key",
        worksection_account="acme",
        worksection_api_key="k",
        rate_limit_rps=50.0,
    )
    return WorksectionClient(
        settings,
        AdminKeyAuth(account="acme", api_key="k"),
        http=httpx.AsyncClient(transport=handler),
        cache=cache,
    )


async def test_repeated_reads_hit_the_cache() -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"status": "ok", "data": [1]})

    async with _client(httpx.MockTransport(handler), SessionCache(60)) as client:
        assert await client.call("get_projects") == [1]
        assert await client.call("get_projects") == [1]
    assert calls["n"] == 1


async def test_different_parameters_are_cached_separately() -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"status": "ok", "data": []})

    async with _client(httpx.MockTransport(handler), SessionCache(60)) as client:
        await client.call("get_tasks", page="/project/1/")
        await client.call("get_tasks", page="/project/2/")
    assert calls["n"] == 2


async def test_a_write_clears_the_cache() -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"status": "ok", "data": []})

    async with _client(httpx.MockTransport(handler), SessionCache(60)) as client:
        await client.call("get_tasks")
        await client.call("post_task", params={"title": "x"})
        await client.call("get_tasks")
    assert calls["n"] == 3


async def test_no_cache_means_every_call_goes_out() -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"status": "ok", "data": []})

    async with _client(httpx.MockTransport(handler), SessionCache(0)) as client:
        await client.call("get_projects")
        await client.call("get_projects")
    assert calls["n"] == 2
