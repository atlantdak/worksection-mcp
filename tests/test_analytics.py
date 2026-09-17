from __future__ import annotations

from typing import Any

from worksection_mcp.analytics import (
    group_tasks_by_assignee,
    summarise_costs,
    summarise_tasks,
    to_float,
)

COSTS: list[dict[str, Any]] = [
    {"time": "1.50", "money": "30", "user_from": {"email": "a@b.co"}},
    {"time": "2", "money": "40", "user_from": {"email": "a@b.co"}},
    {"time": "bad", "money": None, "user_from": {"email": "c@d.co"}},
]

TASKS: list[dict[str, Any]] = [
    {"id": 1, "status": "active", "priority": "8", "user_to": {"email": "a@b.co"}},
    {"id": 2, "status": "done", "priority": "3", "user_to": {"email": "a@b.co"}},
    {"id": 3, "status": "active", "priority": "0", "user_to": None},
]


def test_to_float_is_forgiving() -> None:
    assert to_float("1.5") == 1.5
    assert to_float(2) == 2.0
    assert to_float("bad") == 0.0
    assert to_float(None) == 0.0


def test_summarise_costs_totals_and_groups() -> None:
    summary = summarise_costs(COSTS)
    assert summary["entries"] == 3
    assert summary["total_hours"] == 3.5
    assert summary["total_money"] == 70.0
    assert summary["by_user"]["a@b.co"] == {"hours": 3.5, "money": 70.0, "entries": 2}


def test_summarise_costs_handles_no_rows() -> None:
    assert summarise_costs([]) == {
        "entries": 0,
        "total_hours": 0.0,
        "total_money": 0.0,
        "by_user": {},
    }


def test_summarise_tasks_counts_by_status_and_priority() -> None:
    summary = summarise_tasks(TASKS)
    assert summary["total"] == 3
    assert summary["by_status"] == {"active": 2, "done": 1}
    assert summary["by_priority"] == {"high": 1, "normal": 1, "low": 1}
    assert summary["unassigned"] == 1


def test_group_tasks_by_assignee() -> None:
    grouped = group_tasks_by_assignee(TASKS)
    assert grouped["a@b.co"]["total"] == 2
    assert grouped["a@b.co"]["open"] == 1
    assert grouped["unassigned"]["total"] == 1
