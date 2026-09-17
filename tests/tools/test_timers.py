from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from tests.support import make_context
from worksection_mcp.tooling import dispatch


async def test_start_timer_targets_the_task() -> None:
    context, requests = make_context([{"status": "ok"}])
    await dispatch(context, "start_timer", {"project_id": 7, "task_id": 55})
    assert requests[0].url.params["action"] == "start_timer"
    assert requests[0].url.params["page"] == "/project/7/55/"


async def test_start_timer_can_name_the_person() -> None:
    context, requests = make_context([{"status": "ok"}])
    await dispatch(
        context, "start_timer", {"project_id": 7, "task_id": 55, "user_email": "dev@acme.co"}
    )
    assert requests[0].url.params["email_user_from"] == "dev@acme.co"


async def test_stop_timer_can_attach_a_comment() -> None:
    context, requests = make_context([{"status": "ok", "time": "0.75"}])
    result: Any = await dispatch(
        context, "stop_timer", {"project_id": 7, "task_id": 55, "comment": "Fixed the bug"}
    )
    assert result == {"time": "0.75"}
    assert requests[0].url.params["action"] == "stop_timer"
    assert requests[0].url.params["comment"] == "Fixed the bug"


async def test_stop_timer_rejects_a_blank_comment() -> None:
    context, requests = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(context, "stop_timer", {"project_id": 7, "task_id": 55, "comment": "   "})
    assert requests == []


async def test_get_running_timers_lists_rows() -> None:
    context, requests = make_context([{"status": "ok", "data": [{"id": 1, "task": 55}]}])
    result: Any = await dispatch(context, "get_running_timers", {})
    assert [row["task"] for row in result] == [55]
    assert requests[0].url.params["action"] == "get_timers"
    assert "page" not in requests[0].url.params
