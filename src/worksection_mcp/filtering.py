"""Client-side shaping of API payloads.

The API's own filters are inconsistent for some combinations (see
docs/API-LIMITATIONS.md), so several tools re-apply the filter locally.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

WIRE_DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d")


def as_rows(payload: Any) -> list[dict[str, Any]]:
    """Coerce any of the shapes the API returns into a list of row dicts."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, Mapping):
        if not payload:
            # The API represents an empty result set as `{}` as often as `[]`;
            # treat both the same rather than surfacing a single bogus row.
            return []
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


def parse_wire_date(value: Any) -> date | None:
    """Parse a date the API returned, tolerating both formats and junk."""
    if not isinstance(value, str) or not value.strip():
        return None
    for fmt in WIRE_DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _haystack(row: Mapping[str, Any]) -> str:
    parts = [row.get("name"), row.get("title"), row.get("text")]
    return " ".join(str(part) for part in parts if part).lower()


def filter_tasks(
    rows: Sequence[Mapping[str, Any]],
    *,
    status: str | None = None,
    assignee_email: str | None = None,
    text: str | None = None,
    priority_min: int | None = None,
    due_before: str | None = None,
    due_after: str | None = None,
) -> list[dict[str, Any]]:
    """Apply every supported filter locally. Unset filters are ignored."""
    wanted_email = assignee_email.lower() if assignee_email else None
    needle = text.lower().strip() if text else None
    before = parse_wire_date(due_before)
    after = parse_wire_date(due_after)

    result: list[dict[str, Any]] = []
    for row in rows:
        if status is not None and str(row.get("status", "")).lower() != status.lower():
            continue
        if wanted_email is not None and _assignee_email(row).lower() != wanted_email:
            continue
        if needle is not None and needle not in _haystack(row):
            continue
        if priority_min is not None:
            try:
                priority = float(row.get("priority") or 0)
            except (TypeError, ValueError):
                priority = 0.0
            if priority < priority_min:
                continue
        if before is not None or after is not None:
            due = parse_wire_date(row.get("date_end"))
            if due is None:
                continue
            if before is not None and due > before:
                continue
            if after is not None and due < after:
                continue
        result.append(dict(row))
    return result
