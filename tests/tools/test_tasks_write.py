from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from tests.support import make_context
from worksection_mcp.tooling import dispatch


async def test_create_task_posts_to_the_project_page() -> None:
    context, requests = make_context([{"status": "ok", "id": 101}])
    result: Any = await dispatch(
        context,
        "create_task",
        {
            "project_id": 7,
            "title": "Ship the release",
            "text": "Cut a tag and publish",
            "assignee_email": "dev@acme.co",
            "due_date": "2026-10-01",
            "priority": 8,
        },
    )
    params = requests[0].url.params
    assert result == {"id": 101}
    assert params["action"] == "post_task"
    assert params["page"] == "/project/7/"
    assert params["title"] == "Ship the release"
    assert params["email_user_to"] == "dev@acme.co"
    assert params["date_end"] == "01.10.2026"
    assert params["priority"] == "8"


async def test_create_task_rejects_an_empty_title() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(context, "create_task", {"project_id": 7, "title": "   "})


async def test_create_task_rejects_a_bad_date() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(context, "create_task", {"project_id": 7, "title": "x", "due_date": "soon"})


async def test_create_task_rejects_an_out_of_range_priority() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(context, "create_task", {"project_id": 7, "title": "x", "priority": 42})


async def test_create_task_omits_unset_optional_fields() -> None:
    context, requests = make_context([{"status": "ok", "id": 1}])
    await dispatch(context, "create_task", {"project_id": 7, "title": "x"})
    params = requests[0].url.params
    assert "date_end" not in params
    assert "priority" not in params
    assert "email_user_to" not in params


async def test_create_task_encodes_hostile_titles() -> None:
    context, requests = make_context([{"status": "ok", "id": 1}])
    await dispatch(context, "create_task", {"project_id": 7, "title": "a&action=delete_task&x=1"})
    assert requests[0].url.params["action"] == "post_task"
    assert requests[0].url.params["title"] == "a&action=delete_task&x=1"


async def test_update_task_targets_the_task_page() -> None:
    context, requests = make_context([{"status": "ok"}])
    await dispatch(context, "update_task", {"project_id": 7, "task_id": 55, "title": "New title"})
    assert requests[0].url.params["page"] == "/project/7/55/"
    assert requests[0].url.params["action"] == "update_task"
    assert requests[0].url.params["title"] == "New title"


async def test_update_task_requires_at_least_one_change() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(context, "update_task", {"project_id": 7, "task_id": 55})


async def test_update_task_rejects_a_whitespace_only_title() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(context, "update_task", {"project_id": 7, "task_id": 55, "title": "   "})


async def test_update_task_allows_an_omitted_title() -> None:
    context, requests = make_context([{"status": "ok"}])
    await dispatch(context, "update_task", {"project_id": 7, "task_id": 55, "priority": 3})
    assert "title" not in requests[0].url.params
    assert requests[0].url.params["priority"] == "3"


async def test_complete_and_reopen_use_their_actions() -> None:
    context, requests = make_context([{"status": "ok"}, {"status": "ok"}])
    await dispatch(context, "complete_task", {"project_id": 7, "task_id": 55})
    await dispatch(context, "reopen_task", {"project_id": 7, "task_id": 55})
    assert requests[0].url.params["action"] == "complete_task"
    assert requests[1].url.params["action"] == "reopen_task"
    assert requests[1].url.params["page"] == "/project/7/55/"
