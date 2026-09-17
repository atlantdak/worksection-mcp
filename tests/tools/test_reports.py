from __future__ import annotations

from typing import Any

from tests.support import make_context
from worksection_mcp.tooling import dispatch


async def test_get_time_report_aggregates_costs() -> None:
    rows = [
        {"time": "1.5", "money": "0", "user_from": {"email": "a@b.co"}},
        {"time": "0.5", "money": "0", "user_from": {"email": "a@b.co"}},
    ]
    context, requests = make_context([{"status": "ok", "data": rows}])
    result: Any = await dispatch(
        context, "get_time_report", {"project_id": 7, "date_from": "2026-09-01"}
    )
    assert result["total_hours"] == 2.0
    assert result["by_user"]["a@b.co"]["entries"] == 2
    assert requests[0].url.params["page"] == "/project/7/"
    assert requests[0].url.params["datestart"] == "01.09.2026"


async def test_get_time_report_can_include_the_raw_entries() -> None:
    rows = [{"time": "1", "user_from": {"email": "a@b.co"}}]
    context, _ = make_context([{"status": "ok", "data": rows}])
    result: Any = await dispatch(context, "get_time_report", {"include_entries": True})
    assert result["entries_detail"] == rows


async def test_get_project_stats_summarises_tasks() -> None:
    rows = [
        {"id": 1, "status": "active", "priority": "9"},
        {"id": 2, "status": "done", "priority": "2"},
    ]
    context, requests = make_context([{"status": "ok", "data": rows}])
    result: Any = await dispatch(context, "get_project_stats", {"project_id": 7})
    assert result["total"] == 2
    assert result["by_status"] == {"active": 1, "done": 1}
    assert requests[0].url.params["action"] == "get_tasks"


async def test_get_team_workload_groups_by_assignee() -> None:
    rows = [
        {"id": 1, "status": "active", "user_to": {"email": "a@b.co"}},
        {"id": 2, "status": "done", "user_to": {"email": "a@b.co"}},
        {"id": 3, "status": "active", "user_to": None},
    ]
    context, requests = make_context([{"status": "ok", "data": rows}])
    result: Any = await dispatch(context, "get_team_workload", {})
    assert result["a@b.co"]["open"] == 1
    assert result["unassigned"]["total"] == 1
    assert requests[0].url.params["action"] == "get_all_tasks"
