from __future__ import annotations

from typing import Any

import httpx
import pytest

from worksection_mcp.auth.base import PreparedRequest
from worksection_mcp.config import Settings, load_settings
from worksection_mcp.errors import (
    AuthenticationError,
    TransientHTTPError,
    WorksectionAPIError,
)
from worksection_mcp.http.client import WorksectionClient, extract_payload


class StubAuth:
    mode = "stub"

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def prepare(self, action: str, page: str, params: Any) -> PreparedRequest:
        self.calls.append((action, page))
        query = dict(params)
        query["action"] = action
        if page:
            query["page"] = page
        return PreparedRequest(url="https://acme.test/api/", params=query, headers={"X-T": "1"})


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "auth_mode": "admin_key",
        "worksection_account": "acme",
        "worksection_api_key": "k",
        "max_retries": 2,
        "rate_limit_rps": 50.0,
    }
    base.update(overrides)
    return load_settings(**base)


def _client(handler: httpx.MockTransport, **overrides: object) -> WorksectionClient:
    async def _no_sleep(_seconds: float) -> None:
        return None

    return WorksectionClient(
        _settings(**overrides),
        StubAuth(),
        http=httpx.AsyncClient(transport=handler),
        sleeper=_no_sleep,
    )


def test_extract_payload_returns_data() -> None:
    assert extract_payload({"status": "ok", "data": [1, 2]}, "get_projects") == [1, 2]


def test_extract_payload_returns_body_without_status_when_no_data_key() -> None:
    assert extract_payload({"status": "ok", "id": 7}, "post_task") == {"id": 7}


def test_extract_payload_raises_on_error_status() -> None:
    with pytest.raises(WorksectionAPIError) as excinfo:
        extract_payload({"status": "error", "message": "no access"}, "get_task")
    assert excinfo.value.api_message == "no access"
    assert excinfo.value.action == "get_task"


async def test_call_sends_encoded_params_and_returns_data() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["title"] = request.url.params.get("title")
        return httpx.Response(200, json={"status": "ok", "data": {"id": 5}})

    async with _client(httpx.MockTransport(handler)) as client:
        result = await client.call("post_task", page="/project/1/", params={"title": "a&b c"})

    assert result == {"id": 5}
    assert seen["title"] == "a&b c"
    assert "a%26b" in seen["url"]


async def test_none_params_are_dropped_before_sending() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["keys"] = sorted(request.url.params.keys())
        return httpx.Response(200, json={"status": "ok", "data": []})

    async with _client(httpx.MockTransport(handler)) as client:
        await client.call("get_tasks", params={"id_project": 3, "status": None})

    assert "status" not in seen["keys"]
    assert "id_project" in seen["keys"]


async def test_429_is_retried_and_then_succeeds() -> None:
    attempts = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "1"}, json={"status": "error"})
        return httpx.Response(200, json={"status": "ok", "data": "fine"})

    async with _client(httpx.MockTransport(handler)) as client:
        assert await client.call("get_projects") == "fine"
    assert attempts["n"] == 2


async def test_server_error_is_retried_then_raises() -> None:
    attempts = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(503, text="down")

    async with _client(httpx.MockTransport(handler), max_retries=2) as client:
        with pytest.raises(TransientHTTPError):
            await client.call("get_projects")
    assert attempts["n"] == 3


async def test_401_raises_authentication_error_without_retrying() -> None:
    attempts = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(401, text="nope")

    async with _client(httpx.MockTransport(handler)) as client:
        with pytest.raises(AuthenticationError):
            await client.call("get_projects")
    assert attempts["n"] == 1


async def test_non_json_body_raises_a_worksection_api_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>maintenance</html>")

    async with _client(httpx.MockTransport(handler)) as client:
        with pytest.raises(WorksectionAPIError):
            await client.call("get_projects")


async def test_download_returns_raw_bytes() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"\x89PNG binary")

    async with _client(httpx.MockTransport(handler)) as client:
        assert await client.download("https://files.test/a.png") == b"\x89PNG binary"
