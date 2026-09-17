from __future__ import annotations

from worksection_mcp.filtering import as_rows, filter_tasks

ROWS = [
    {"id": 1, "status": "active", "user_to": {"email": "a@b.co"}},
    {"id": 2, "status": "done", "user_to": {"email": "c@d.co"}},
    {"id": 3, "status": "done", "user_to": None},
]


def test_as_rows_passes_a_list_through() -> None:
    assert as_rows([{"id": 1}]) == [{"id": 1}]


def test_as_rows_wraps_a_single_object() -> None:
    assert as_rows({"id": 1}) == [{"id": 1}]


def test_as_rows_unwraps_an_id_keyed_mapping() -> None:
    assert as_rows({"10": {"id": 10}, "11": {"id": 11}}) == [{"id": 10}, {"id": 11}]


def test_as_rows_handles_none_and_scalars() -> None:
    assert as_rows(None) == []
    assert as_rows("oops") == []


def test_filter_by_status() -> None:
    assert [row["id"] for row in filter_tasks(ROWS, status="done")] == [2, 3]


def test_filter_by_assignee_email_is_case_insensitive() -> None:
    assert [row["id"] for row in filter_tasks(ROWS, assignee_email="A@B.CO")] == [1]


def test_filters_combine() -> None:
    assert filter_tasks(ROWS, status="done", assignee_email="c@d.co")[0]["id"] == 2


def test_no_filters_returns_everything() -> None:
    assert len(filter_tasks(ROWS)) == 3
