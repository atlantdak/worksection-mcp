from __future__ import annotations

from datetime import date

from worksection_mcp.filtering import filter_tasks, parse_wire_date

ROWS = [
    {
        "id": 1,
        "name": "Fix login bug",
        "text": "users cannot sign in",
        "priority": "9",
        "date_end": "20.09.2026",
    },
    {"id": 2, "name": "Write docs", "text": "", "priority": "2", "date_end": "01.10.2026"},
    {"id": 3, "name": "Login rate limit", "text": None, "priority": "5", "date_end": None},
]


def test_parse_wire_date() -> None:
    assert parse_wire_date("20.09.2026") == date(2026, 9, 20)
    assert parse_wire_date("2026-09-20") == date(2026, 9, 20)
    assert parse_wire_date(None) is None
    assert parse_wire_date("whenever") is None


def test_text_search_matches_title_and_body_case_insensitively() -> None:
    assert [row["id"] for row in filter_tasks(ROWS, text="LOGIN")] == [1, 3]
    assert [row["id"] for row in filter_tasks(ROWS, text="sign in")] == [1]


def test_priority_minimum() -> None:
    assert [row["id"] for row in filter_tasks(ROWS, priority_min=5)] == [1, 3]


def test_due_before_ignores_rows_without_a_due_date() -> None:
    assert [row["id"] for row in filter_tasks(ROWS, due_before="30.09.2026")] == [1]


def test_due_after() -> None:
    assert [row["id"] for row in filter_tasks(ROWS, due_after="25.09.2026")] == [2]


def test_filters_still_combine_with_status() -> None:
    rows = [{"id": 1, "name": "a", "status": "done", "priority": "9"}]
    assert filter_tasks(rows, status="done", priority_min=8)[0]["id"] == 1
    assert filter_tasks(rows, status="active", priority_min=8) == []
