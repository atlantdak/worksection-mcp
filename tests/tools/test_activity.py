from __future__ import annotations

from typing import Any

from tests.support import make_context
from worksection_mcp.tooling import dispatch

TASKS = [
    {"id": 1, "status": "active", "priority": "9", "date_end": "01.01.2020"},
    {"id": 2, "status": "done", "priority": "2", "date_end": "01.01.2020"},
]


async def test_get_activity_log_uses_the_events_action() -> None:
    context, requests = make_context([{"status": "ok", "data": [{"id": 1, "type": "comment"}]}])
    result: Any = await dispatch(context, "get_activity_log", {"date_from": "2026-09-01"})
    assert [row["type"] for row in result] == ["comment"]
    assert requests[0].url.params["action"] == "get_events"
    assert requests[0].url.params["datestart"] == "01.09.2026"


async def test_get_activity_log_can_scope_to_a_project() -> None:
    context, requests = make_context([{"status": "ok", "data": []}])
    await dispatch(context, "get_activity_log", {"project_id": 7})
    assert requests[0].url.params["page"] == "/project/7/"


async def test_get_overdue_tasks_filters_and_sorts() -> None:
    context, requests = make_context([{"status": "ok", "data": TASKS}])
    result: Any = await dispatch(context, "get_overdue_tasks", {})
    assert [row["id"] for row in result["tasks"]] == [1]
    assert result["count"] == 1
    assert requests[0].url.params["action"] == "get_all_tasks"


async def test_get_tasks_by_status_groups_rows() -> None:
    context, _ = make_context([{"status": "ok", "data": TASKS}])
    result: Any = await dispatch(context, "get_tasks_by_status", {"project_id": 7})
    assert result["summary"]["by_status"] == {"active": 1, "done": 1}
    assert [row["id"] for row in result["groups"]["active"]] == [1]


async def test_get_tasks_by_priority_groups_rows() -> None:
    context, _ = make_context([{"status": "ok", "data": TASKS}])
    result: Any = await dispatch(context, "get_tasks_by_priority", {})
    assert [row["id"] for row in result["groups"]["high"]] == [1]
    assert result["summary"]["by_priority"]["high"] == 1
