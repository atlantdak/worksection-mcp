from __future__ import annotations

import json

import pytest

from tests.support import make_context
from worksection_mcp.errors import DestructiveOperationDisabled
from worksection_mcp.server import call_tool_payload, list_tools_payload
from worksection_mcp.tooling import dispatch


async def test_delete_task_is_absent_from_the_tool_list_by_default() -> None:
    context, _ = make_context([])
    names = {item.name for item in await list_tools_payload(context)}
    assert "delete_task" not in names
    assert "get_tasks" in names


async def test_delete_task_is_listed_when_explicitly_enabled() -> None:
    context, _ = make_context([], allow_destructive_operations=True)
    names = {item.name for item in await list_tools_payload(context)}
    assert "delete_task" in names


async def test_calling_delete_task_while_disabled_raises() -> None:
    context, requests = make_context([])
    with pytest.raises(DestructiveOperationDisabled):
        await dispatch(context, "delete_task", {"project_id": 7, "task_id": 55})
    assert requests == []


async def test_call_tool_payload_reports_the_gate_as_a_structured_error() -> None:
    context, _ = make_context([])
    blocks = await call_tool_payload(context, "delete_task", {"project_id": 7, "task_id": 55})
    payload = json.loads(blocks[0].text)
    assert payload["error"]["type"] == "DestructiveOperationDisabled"
    assert "ALLOW_DESTRUCTIVE_OPERATIONS" in payload["error"]["message"]


async def test_delete_task_calls_the_api_when_enabled() -> None:
    context, requests = make_context([{"status": "ok"}], allow_destructive_operations=True)
    await dispatch(context, "delete_task", {"project_id": 7, "task_id": 55, "confirm": True})
    assert requests[0].url.params["action"] == "delete_task"
    assert requests[0].url.params["page"] == "/project/7/55/"


async def test_delete_comment_is_absent_from_the_tool_list_by_default() -> None:
    context, _ = make_context([])
    names = {item.name for item in await list_tools_payload(context)}
    assert "delete_comment" not in names
    assert "get_comments" in names


async def test_delete_comment_is_listed_when_explicitly_enabled() -> None:
    context, _ = make_context([], allow_destructive_operations=True)
    names = {item.name for item in await list_tools_payload(context)}
    assert "delete_comment" in names
