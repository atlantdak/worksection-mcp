from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from tests.support import make_context
from worksection_mcp.errors import DestructiveOperationDisabled
from worksection_mcp.tooling import dispatch


async def test_get_costs_at_account_scope() -> None:
    context, requests = make_context([{"status": "ok", "data": [{"id": 1, "time": "1.50"}]}])
    result: Any = await dispatch(context, "get_costs", {})
    assert [row["id"] for row in result] == [1]
    assert requests[0].url.params["action"] == "get_costs"
    assert "page" not in requests[0].url.params


async def test_get_costs_scoped_to_a_task_with_a_date_range() -> None:
    context, requests = make_context([{"status": "ok", "data": []}])
    await dispatch(
        context,
        "get_costs",
        {
            "project_id": 7,
            "task_id": 55,
            "date_from": "2026-09-01",
            "date_to": "2026-09-30",
            "user_email": "dev@acme.co",
        },
    )
    params = requests[0].url.params
    assert params["page"] == "/project/7/55/"
    assert params["datestart"] == "01.09.2026"
    assert params["dateend"] == "30.09.2026"
    assert params["email_user_from"] == "dev@acme.co"


async def test_get_costs_requires_a_project_when_a_task_is_given() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(context, "get_costs", {"task_id": 55})


async def test_add_costs_records_hours_and_a_comment() -> None:
    context, requests = make_context([{"status": "ok", "id": 5}])
    await dispatch(
        context,
        "add_costs",
        {
            "project_id": 7,
            "task_id": 55,
            "hours": 1.5,
            "comment": "Pairing on the release",
            "date": "2026-09-17",
            "user_email": "dev@acme.co",
        },
    )
    params = requests[0].url.params
    assert params["action"] == "add_costs"
    assert params["page"] == "/project/7/55/"
    assert params["time"] == "1.5"
    assert params["comment"] == "Pairing on the release"
    assert params["date"] == "17.09.2026"


async def test_add_costs_rejects_non_positive_hours() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(context, "add_costs", {"project_id": 7, "task_id": 55, "hours": 0})


async def test_add_costs_rejects_a_blank_comment() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(
            context,
            "add_costs",
            {"project_id": 7, "task_id": 55, "hours": 1.0, "comment": "   "},
        )


async def test_update_costs_identifies_the_entry() -> None:
    context, requests = make_context([{"status": "ok"}])
    await dispatch(
        context, "update_costs", {"project_id": 7, "task_id": 55, "cost_id": 5, "hours": 2.0}
    )
    params = requests[0].url.params
    assert params["action"] == "update_costs"
    assert params["id_cost"] == "5"
    assert params["time"] == "2.0"


async def test_update_costs_rejects_a_blank_comment() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(
            context,
            "update_costs",
            {"project_id": 7, "task_id": 55, "cost_id": 5, "comment": "   "},
        )


async def test_update_costs_requires_at_least_one_field_to_change() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(context, "update_costs", {"project_id": 7, "task_id": 55, "cost_id": 5})


async def test_delete_costs_is_gated() -> None:
    context, requests = make_context([])
    with pytest.raises(DestructiveOperationDisabled):
        await dispatch(context, "delete_costs", {"project_id": 7, "task_id": 55, "cost_id": 5})
    assert requests == []


async def test_delete_costs_runs_when_enabled() -> None:
    context, requests = make_context([{"status": "ok"}], allow_destructive_operations=True)
    await dispatch(
        context,
        "delete_costs",
        {"project_id": 7, "task_id": 55, "cost_id": 5, "confirm": True},
    )
    assert requests[0].url.params["action"] == "delete_costs"
    assert requests[0].url.params["id_cost"] == "5"
