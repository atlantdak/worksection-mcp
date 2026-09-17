from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from tests.support import make_context
from worksection_mcp.tooling import dispatch

ROWS = [
    {
        "id": 1,
        "name": "Fix login bug",
        "priority": "9",
        "status": "active",
        "date_end": "20.09.2026",
        "user_to": {"email": "a@b.co"},
    },
    {
        "id": 2,
        "name": "Write docs",
        "priority": "2",
        "status": "done",
        "date_end": "01.10.2026",
        "user_to": {"email": "c@d.co"},
    },
]


async def test_search_across_the_account() -> None:
    context, requests = make_context([{"status": "ok", "data": ROWS}])
    result: Any = await dispatch(context, "search_tasks", {"text": "login"})
    assert [row["id"] for row in result["tasks"]] == [1]
    assert result["matched"] == 1
    assert result["scanned"] == 2
    assert requests[0].url.params["action"] == "get_all_tasks"


async def test_search_inside_one_project() -> None:
    context, requests = make_context([{"status": "ok", "data": ROWS}])
    await dispatch(context, "search_tasks", {"project_id": 7, "text": "docs"})
    assert requests[0].url.params["action"] == "get_tasks"
    assert requests[0].url.params["page"] == "/project/7/"


async def test_search_combines_filters() -> None:
    context, _ = make_context([{"status": "ok", "data": ROWS}])
    result: Any = await dispatch(
        context,
        "search_tasks",
        {"status": "active", "priority_min": 8, "assignee_email": "a@b.co"},
    )
    assert [row["id"] for row in result["tasks"]] == [1]


async def test_search_respects_the_result_limit() -> None:
    context, _ = make_context([{"status": "ok", "data": ROWS}])
    # priority_min=0 matches every row here; it exists only to satisfy the
    # "needs at least one criterion" rule while leaving both rows in scope.
    result: Any = await dispatch(context, "search_tasks", {"priority_min": 0, "limit": 1})
    assert len(result["tasks"]) == 1
    assert result["matched"] == 2
    assert result["truncated"] is True


async def test_search_requires_at_least_one_criterion() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(context, "search_tasks", {"limit": 10})


async def test_search_rejects_blank_text() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(context, "search_tasks", {"text": "   "})
