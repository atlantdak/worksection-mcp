from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.support import make_context
from worksection_mcp.tooling import dispatch


async def test_create_project_posts_at_account_scope() -> None:
    context, requests = make_context([{"status": "ok", "id": 42}])
    await dispatch(
        context,
        "create_project",
        {
            "title": "Website relaunch",
            "text": "Q4 initiative",
            "manager_email": "pm@acme.co",
            "due_date": "2026-12-01",
        },
    )
    params = requests[0].url.params
    assert params["action"] == "post_project"
    assert "page" not in params
    assert params["title"] == "Website relaunch"
    assert params["email_manager"] == "pm@acme.co"
    assert params["date_end"] == "01.12.2026"


async def test_create_project_rejects_blank_titles() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(context, "create_project", {"title": ""})


async def test_update_project_scopes_to_the_project() -> None:
    context, requests = make_context([{"status": "ok"}])
    await dispatch(context, "update_project", {"project_id": 42, "title": "Renamed"})
    assert requests[0].url.params["page"] == "/project/42/"
    assert requests[0].url.params["action"] == "update_project"


async def test_update_project_requires_a_change() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(context, "update_project", {"project_id": 42})


async def test_archive_and_activate_use_their_actions() -> None:
    context, requests = make_context([{"status": "ok"}, {"status": "ok"}])
    await dispatch(context, "archive_project", {"project_id": 42})
    await dispatch(context, "activate_project", {"project_id": 42})
    assert requests[0].url.params["action"] == "close_project"
    assert requests[1].url.params["action"] == "activate_project"


async def test_get_project_groups_lists_folders() -> None:
    context, requests = make_context([{"status": "ok", "data": [{"id": 1, "name": "Design"}]}])
    result = await dispatch(context, "get_project_groups", {"project_id": 42})
    assert result == [{"id": 1, "name": "Design"}]
    assert requests[0].url.params["action"] == "get_project_groups"
