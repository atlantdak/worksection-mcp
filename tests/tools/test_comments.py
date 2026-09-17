from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from tests.support import make_context
from worksection_mcp.errors import DestructiveOperationDisabled
from worksection_mcp.tooling import dispatch


async def test_get_comments_lists_task_comments() -> None:
    context, requests = make_context([{"status": "ok", "data": [{"id": 3, "text": "hi"}]}])
    result: Any = await dispatch(context, "get_comments", {"project_id": 7, "task_id": 55})
    assert [row["id"] for row in result] == [3]
    assert requests[0].url.params["action"] == "get_comments"
    assert requests[0].url.params["page"] == "/project/7/55/"


async def test_post_comment_sends_text_and_author() -> None:
    context, requests = make_context([{"status": "ok", "id": 9}])
    await dispatch(
        context,
        "post_comment",
        {"project_id": 7, "task_id": 55, "text": "Looks good", "author_email": "me@acme.co"},
    )
    params = requests[0].url.params
    assert params["action"] == "post_comment"
    assert params["text"] == "Looks good"
    assert params["email_user_from"] == "me@acme.co"


async def test_post_comment_rejects_empty_text() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(context, "post_comment", {"project_id": 7, "task_id": 55, "text": "  "})


async def test_post_comment_encodes_markup_safely() -> None:
    context, requests = make_context([{"status": "ok", "id": 9}])
    text = "see ?action=delete_task&hash=abc"
    await dispatch(context, "post_comment", {"project_id": 7, "task_id": 55, "text": text})
    assert requests[0].url.params["text"] == text
    assert requests[0].url.params["action"] == "post_comment"


async def test_update_comment_identifies_the_comment() -> None:
    context, requests = make_context([{"status": "ok"}])
    await dispatch(
        context,
        "update_comment",
        {"project_id": 7, "task_id": 55, "comment_id": 9, "text": "Edited"},
    )
    params = requests[0].url.params
    assert params["action"] == "update_comment"
    assert params["id_comment"] == "9"
    assert params["text"] == "Edited"


async def test_delete_comment_is_gated() -> None:
    context, requests = make_context([])
    with pytest.raises(DestructiveOperationDisabled):
        await dispatch(context, "delete_comment", {"project_id": 7, "task_id": 55, "comment_id": 9})
    assert requests == []


async def test_delete_comment_runs_when_enabled() -> None:
    context, requests = make_context([{"status": "ok"}], allow_destructive_operations=True)
    await dispatch(
        context,
        "delete_comment",
        {"project_id": 7, "task_id": 55, "comment_id": 9, "confirm": True},
    )
    assert requests[0].url.params["action"] == "delete_comment"
    assert requests[0].url.params["id_comment"] == "9"
