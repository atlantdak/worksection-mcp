"""Pure aggregation helpers over API rows. No I/O, no configuration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

HIGH_PRIORITY = 7
NORMAL_PRIORITY = 1
UNASSIGNED = "unassigned"


def to_float(value: Any) -> float:
    """Best-effort numeric conversion; unparsable values count as zero."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _email(row: Mapping[str, Any], key: str) -> str:
    user = row.get(key)
    if isinstance(user, Mapping):
        return str(user.get("email") or UNASSIGNED)
    return str(user or UNASSIGNED)


def _priority_bucket(value: Any) -> str:
    priority = to_float(value)
    if priority >= HIGH_PRIORITY:
        return "high"
    if priority >= NORMAL_PRIORITY:
        return "normal"
    return "low"


def summarise_costs(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Total hours and money, overall and per person."""
    by_user: dict[str, dict[str, float]] = {}
    total_hours = 0.0
    total_money = 0.0
    for row in rows:
        hours = to_float(row.get("time"))
        money = to_float(row.get("money"))
        total_hours += hours
        total_money += money
        bucket = by_user.setdefault(
            _email(row, "user_from"), {"hours": 0.0, "money": 0.0, "entries": 0}
        )
        bucket["hours"] = round(bucket["hours"] + hours, 4)
        bucket["money"] = round(bucket["money"] + money, 4)
        bucket["entries"] += 1
    return {
        "entries": len(rows),
        "total_hours": round(total_hours, 4),
        "total_money": round(total_money, 4),
        "by_user": {
            email: {
                "hours": values["hours"],
                "money": values["money"],
                "entries": int(values["entries"]),
            }
            for email, values in by_user.items()
        },
    }


def summarise_tasks(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Counts by status and priority bucket, plus how many are unassigned."""
    by_status: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    unassigned = 0
    for row in rows:
        status = str(row.get("status") or "unknown").lower()
        by_status[status] = by_status.get(status, 0) + 1
        bucket = _priority_bucket(row.get("priority"))
        by_priority[bucket] = by_priority.get(bucket, 0) + 1
        if _email(row, "user_to") == UNASSIGNED:
            unassigned += 1
    return {
        "total": len(rows),
        "by_status": by_status,
        "by_priority": by_priority,
        "unassigned": unassigned,
    }


def group_tasks_by_assignee(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-person task counts with open/done splits."""
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        email = _email(row, "user_to")
        bucket = grouped.setdefault(email, {"total": 0, "open": 0, "done": 0, "task_ids": []})
        bucket["total"] += 1
        if str(row.get("status", "")).lower() == "done":
            bucket["done"] += 1
        else:
            bucket["open"] += 1
        bucket["task_ids"].append(row.get("id"))
    return grouped
