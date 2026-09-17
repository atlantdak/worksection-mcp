"""Builders for the ``page`` path that scopes an API action.

The page string is part of the request signature, so ids are validated as
positive integers before they reach it.
"""

from __future__ import annotations


def _require_id(value: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer, got {value!r}")
    return value


def account_page() -> str:
    """Account-wide scope."""
    return ""


def project_page(project_id: int) -> str:
    return f"/project/{_require_id(project_id, 'project_id')}/"


def task_page(project_id: int, task_id: int) -> str:
    return f"/project/{_require_id(project_id, 'project_id')}/{_require_id(task_id, 'task_id')}/"


def subtask_page(project_id: int, task_id: int, subtask_id: int) -> str:
    return (
        f"/project/{_require_id(project_id, 'project_id')}"
        f"/{_require_id(task_id, 'task_id')}"
        f"/{_require_id(subtask_id, 'subtask_id')}/"
    )
