from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from tests.support import make_context
from worksection_mcp.tooling import dispatch


async def test_get_subtasks_lists_children_of_a_task() -> None:
    context, requests = make_context([{"status": "ok", "data": [{"id": 90}, {"id": 91}]}])
    result: Any = await dispatch(context, "get_subtasks", {"project_id": 7, "task_id": 55})
    assert [row["id"] for row in result] == [90, 91]
    assert requests[0].url.params["page"] == "/project/7/55/"
    assert requests[0].url.params["action"] == "get_tasks"


async def test_get_subtasks_returns_empty_list_for_an_empty_object_payload() -> None:
    context, _ = make_context([{"status": "ok", "data": {}}])
    result: Any = await dispatch(context, "get_subtasks", {"project_id": 7, "task_id": 55})
    assert result == []


async def test_create_subtask_posts_to_the_parent_task_page() -> None:
    context, requests = make_context([{"status": "ok", "id": 92}])
    await dispatch(
        context,
        "create_subtask",
        {"project_id": 7, "task_id": 55, "title": "Write changelog", "due_date": "2026-10-02"},
    )
    params = requests[0].url.params
    assert params["action"] == "post_task"
    assert params["page"] == "/project/7/55/"
    assert params["title"] == "Write changelog"
    assert params["date_end"] == "02.10.2026"


async def test_create_subtask_rejects_an_empty_title() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(context, "create_subtask", {"project_id": 7, "task_id": 55, "title": "   "})


async def test_update_subtask_targets_the_subtask_page() -> None:
    context, requests = make_context([{"status": "ok"}])
    await dispatch(
        context,
        "update_subtask",
        {"project_id": 7, "task_id": 55, "subtask_id": 92, "title": "Renamed"},
    )
    assert requests[0].url.params["page"] == "/project/7/55/92/"
    assert requests[0].url.params["action"] == "update_task"


async def test_update_subtask_requires_a_change() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(
            context, "update_subtask", {"project_id": 7, "task_id": 55, "subtask_id": 92}
        )


async def test_update_subtask_rejects_a_whitespace_only_title() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(
            context,
            "update_subtask",
            {"project_id": 7, "task_id": 55, "subtask_id": 92, "title": "   "},
        )


async def test_update_subtask_allows_an_omitted_title() -> None:
    context, requests = make_context([{"status": "ok"}])
    await dispatch(
        context,
        "update_subtask",
        {"project_id": 7, "task_id": 55, "subtask_id": 92, "priority": 3},
    )
    assert "title" not in requests[0].url.params
    assert requests[0].url.params["priority"] == "3"
