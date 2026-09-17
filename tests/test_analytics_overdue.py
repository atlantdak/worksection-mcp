from __future__ import annotations

from datetime import date

from worksection_mcp.analytics import overdue_tasks

ROWS = [
    {"id": 1, "status": "active", "date_end": "10.09.2026"},
    {"id": 2, "status": "done", "date_end": "10.09.2026"},
    {"id": 3, "status": "active", "date_end": "30.09.2026"},
    {"id": 4, "status": "active", "date_end": None},
    {"id": 5, "status": "active", "date_end": "nonsense"},
]


def test_only_open_tasks_past_their_due_date_are_overdue() -> None:
    result = overdue_tasks(ROWS, today=date(2026, 9, 17))
    assert [row["id"] for row in result] == [1]


def test_days_overdue_is_reported() -> None:
    assert overdue_tasks(ROWS, today=date(2026, 9, 17))[0]["days_overdue"] == 7


def test_nothing_is_overdue_before_the_due_dates() -> None:
    assert overdue_tasks(ROWS, today=date(2026, 9, 1)) == []


def test_results_are_sorted_most_overdue_first() -> None:
    rows = [
        {"id": 1, "status": "active", "date_end": "15.09.2026"},
        {"id": 2, "status": "active", "date_end": "01.09.2026"},
    ]
    assert [row["id"] for row in overdue_tasks(rows, today=date(2026, 9, 17))] == [2, 1]
