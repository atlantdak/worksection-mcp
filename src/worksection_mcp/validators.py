"""Normalisers shared by every tool input model."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Annotated, Any

from pydantic import BeforeValidator

WIRE_DATE_FORMAT = "%d.%m.%Y"
ACCEPTED_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y")
MAX_PRIORITY = 10


def normalize_date(value: str | None) -> str | None:
    """Return a date in the API's ``DD.MM.YYYY`` form, or None."""
    if value is None:
        return None
    text = value.strip()
    for fmt in ACCEPTED_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime(WIRE_DATE_FORMAT)
        except ValueError:
            continue
    raise ValueError(f"date must be YYYY-MM-DD or DD.MM.YYYY, got {value!r}")


def _coerce_date(value: Any) -> Any:
    return value if value is None else normalize_date(str(value))


DateString = Annotated[str, BeforeValidator(_coerce_date)]


def normalize_priority(value: int | None) -> int | None:
    if value is None:
        return None
    if not 0 <= value <= MAX_PRIORITY:
        raise ValueError(f"priority must be between 0 and {MAX_PRIORITY}, got {value}")
    return value


def join_ids(values: Sequence[int] | None) -> str | None:
    if not values:
        return None
    for item in values:
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise ValueError(f"ids must be positive integers, got {item!r}")
    return ",".join(str(item) for item in values)


def join_emails(values: Sequence[str] | None) -> str | None:
    if not values:
        return None
    for item in values:
        if "@" not in item:
            raise ValueError(f"expected an email address, got {item!r}")
    return ",".join(item.strip() for item in values)


def require_text(value: str, field: str, *, max_length: int = 20_000) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field} must not be empty")
    if len(text) > max_length:
        raise ValueError(f"{field} must be at most {max_length} characters")
    return text
