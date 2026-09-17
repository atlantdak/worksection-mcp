from __future__ import annotations

from typing import Any

import pytest

from tests.support import make_context
from worksection_mcp.tooling import dispatch


async def test_get_projects_calls_the_right_action() -> None:
    context, requests = make_context([{"status": "ok", "data": [{"id": 1, "name": "Site"}]}])
    result: Any = await dispatch(context, "get_projects", {})
    assert result == [{"id": 1, "name": "Site"}]
    assert requests[0].url.params["action"] == "get_projects"
    assert "page" not in requests[0].url.params


async def test_get_projects_passes_filter_and_extra_flags() -> None:
    context, requests = make_context([{"status": "ok", "data": []}])
    await dispatch(context, "get_projects", {"status": "active", "include_extra": True})
    params = requests[0].url.params
    assert params["filter"] == "active"
    assert params["extra"] == "text,users"


async def test_get_project_scopes_the_page() -> None:
    context, requests = make_context([{"status": "ok", "data": {"id": 12}}])
    result = await dispatch(context, "get_project", {"project_id": 12})
    assert result == {"id": 12}
    assert requests[0].url.params["page"] == "/project/12/"
    assert requests[0].url.params["action"] == "get_project"


async def test_get_project_rejects_a_non_positive_id() -> None:
    context, _ = make_context([])
    with pytest.raises(Exception):
        await dispatch(context, "get_project", {"project_id": 0})


async def test_health_check_reports_reachability() -> None:
    context, requests = make_context([{"status": "ok", "data": [{"id": 1}]}])
    result: Any = await dispatch(context, "health_check", {})
    assert result["api_reachable"] is True
    assert result["auth_mode"] == "admin_key"
    assert requests[0].url.params["action"] == "get_projects"


async def test_health_check_reports_failure_without_raising() -> None:
    import httpx

    context, _ = make_context([httpx.Response(401, text="nope")])
    result: Any = await dispatch(context, "health_check", {})
    assert result["api_reachable"] is False
    assert "AuthenticationError" in result["detail"]
