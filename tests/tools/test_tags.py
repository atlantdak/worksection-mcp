from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from tests.support import make_context
from worksection_mcp.tooling import dispatch


async def test_get_tags_lists_account_tag_groups() -> None:
    context, requests = make_context([{"status": "ok", "data": [{"id": 1, "title": "Priority"}]}])
    result: Any = await dispatch(context, "get_tags", {})
    assert [row["title"] for row in result] == ["Priority"]
    assert requests[0].url.params["action"] == "get_tags"
    assert "page" not in requests[0].url.params


async def test_get_tags_returns_empty_list_for_an_empty_object_payload() -> None:
    context, _ = make_context([{"status": "ok", "data": {}}])
    result: Any = await dispatch(context, "get_tags", {})
    assert result == []


async def test_get_task_tags_returns_empty_list_when_the_task_has_none() -> None:
    context, _ = make_context([{"status": "ok", "data": {"id": 55, "tags": {}}}])
    result: Any = await dispatch(context, "get_task_tags", {"project_id": 7, "task_id": 55})
    assert result == []


async def test_get_task_tags_reads_them_from_the_task() -> None:
    context, requests = make_context(
        [{"status": "ok", "data": {"id": 55, "tags": {"3": "urgent", "4": "backend"}}}]
    )
    result: Any = await dispatch(context, "get_task_tags", {"project_id": 7, "task_id": 55})
    assert sorted(result) == ["backend", "urgent"]
    assert requests[0].url.params["action"] == "get_task"


async def test_add_task_tags_appends() -> None:
    context, requests = make_context([{"status": "ok"}])
    await dispatch(context, "add_task_tags", {"project_id": 7, "task_id": 55, "tags": ["a", "b"]})
    params = requests[0].url.params
    assert params["action"] == "add_tags"
    assert params["tags"] == "a,b"
    assert params["page"] == "/project/7/55/"


async def test_set_task_tags_replaces() -> None:
    context, requests = make_context([{"status": "ok"}])
    await dispatch(context, "set_task_tags", {"project_id": 7, "task_id": 55, "tags": ["only"]})
    assert requests[0].url.params["action"] == "set_tags"
    assert requests[0].url.params["tags"] == "only"


async def test_tags_must_not_be_empty() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(context, "add_task_tags", {"project_id": 7, "task_id": 55, "tags": []})


async def test_tag_values_with_commas_are_rejected() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(context, "set_task_tags", {"project_id": 7, "task_id": 55, "tags": ["a,b"]})
