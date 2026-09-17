from __future__ import annotations

from typing import Any

from tests.support import make_context
from worksection_mcp.tooling import dispatch


async def test_get_all_tasks_uses_the_account_scope() -> None:
    context, requests = make_context([{"status": "ok", "data": [{"id": 1, "status": "active"}]}])
    result: Any = await dispatch(context, "get_all_tasks", {})
    assert result == [{"id": 1, "status": "active"}]
    assert requests[0].url.params["action"] == "get_all_tasks"
    assert "page" not in requests[0].url.params


async def test_get_all_tasks_refilters_status_client_side() -> None:
    payload = [
        {"id": 1, "status": "active"},
        {"id": 2, "status": "done"},
    ]
    context, requests = make_context([{"status": "ok", "data": payload}])
    result: Any = await dispatch(context, "get_all_tasks", {"status": "done"})
    assert [row["id"] for row in result] == [2]
    assert requests[0].url.params["status"] == "done"


async def test_get_all_tasks_filters_by_assignee() -> None:
    payload = [
        {"id": 1, "user_to": {"email": "a@b.co"}},
        {"id": 2, "user_to": {"email": "c@d.co"}},
    ]
    context, _ = make_context([{"status": "ok", "data": payload}])
    result: Any = await dispatch(context, "get_all_tasks", {"assignee_email": "c@d.co"})
    assert [row["id"] for row in result] == [2]


async def test_get_tasks_scopes_to_a_project() -> None:
    context, requests = make_context([{"status": "ok", "data": []}])
    await dispatch(context, "get_tasks", {"project_id": 7})
    assert requests[0].url.params["page"] == "/project/7/"
    assert requests[0].url.params["action"] == "get_tasks"


async def test_get_task_scopes_to_a_task() -> None:
    context, requests = make_context([{"status": "ok", "data": {"id": 55}}])
    result = await dispatch(context, "get_task", {"project_id": 7, "task_id": 55})
    assert result == {"id": 55}
    assert requests[0].url.params["page"] == "/project/7/55/"


async def test_get_task_requests_extra_fields_when_asked() -> None:
    context, requests = make_context([{"status": "ok", "data": {"id": 55}}])
    await dispatch(context, "get_task", {"project_id": 7, "task_id": 55, "include_extra": True})
    assert requests[0].url.params["extra"] == "text,files,subtasks"
