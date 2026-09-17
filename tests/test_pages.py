from __future__ import annotations

import pytest

from worksection_mcp.pages import account_page, project_page, subtask_page, task_page


def test_account_page_is_empty() -> None:
    assert account_page() == ""


def test_project_page_format() -> None:
    assert project_page(12) == "/project/12/"


def test_task_page_format() -> None:
    assert task_page(12, 345) == "/project/12/345/"


def test_subtask_page_format() -> None:
    assert subtask_page(12, 345, 678) == "/project/12/345/678/"


@pytest.mark.parametrize("bad", [0, -1, "12/../"])
def test_ids_must_be_positive_integers(bad: object) -> None:
    with pytest.raises(ValueError):
        project_page(bad)  # type: ignore[arg-type]
