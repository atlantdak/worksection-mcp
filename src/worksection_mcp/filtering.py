"""Client-side shaping of API payloads.

The API's own filters are inconsistent for some combinations (see
docs/API-LIMITATIONS.md), so several tools re-apply the filter locally.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def as_rows(payload: Any) -> list[dict[str, Any]]:
    """Coerce any of the shapes the API returns into a list of row dicts."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, Mapping):
        values = list(payload.values())
        if values and all(isinstance(value, Mapping) for value in values):
            return [dict(value) for value in values]
        return [dict(payload)]
    return []


def _assignee_email(row: Mapping[str, Any]) -> str:
    user = row.get("user_to")
    if isinstance(user, Mapping):
        return str(user.get("email", ""))
    return str(user or "")


def filter_tasks(
    rows: Sequence[Mapping[str, Any]],
    *,
    status: str | None = None,
    assignee_email: str | None = None,
) -> list[dict[str, Any]]:
    """Apply status and assignee filters locally."""
    result: list[dict[str, Any]] = []
    wanted_email = assignee_email.lower() if assignee_email else None
    for row in rows:
        if status is not None and str(row.get("status", "")).lower() != status.lower():
            continue
        if wanted_email is not None and _assignee_email(row).lower() != wanted_email:
            continue
        result.append(dict(row))
    return result
