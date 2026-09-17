from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from worksection_mcp.validators import (
    DateString,
    join_emails,
    join_ids,
    normalize_date,
    normalize_priority,
    require_text,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("2026-09-17", "17.09.2026"), ("17.09.2026", "17.09.2026"), (None, None)],
)
def test_normalize_date_accepts_both_formats(value: str | None, expected: str | None) -> None:
    assert normalize_date(value) == expected


@pytest.mark.parametrize("bad", ["17/09/2026", "next tuesday", "2026-13-01", ""])
def test_normalize_date_rejects_garbage(bad: str) -> None:
    with pytest.raises(ValueError):
        normalize_date(bad)


def test_date_string_field_type_normalises_inside_a_model() -> None:
    class Model(BaseModel):
        due: DateString | None = None

    assert Model(due="2026-09-17").due == "17.09.2026"
    assert Model().due is None
    with pytest.raises(ValidationError):
        Model(due="tomorrow")


@pytest.mark.parametrize("value", [0, 5, 10, None])
def test_priority_accepts_the_documented_range(value: int | None) -> None:
    assert normalize_priority(value) == value


@pytest.mark.parametrize("bad", [-1, 11, 100])
def test_priority_rejects_out_of_range(bad: int) -> None:
    with pytest.raises(ValueError):
        normalize_priority(bad)


def test_join_ids() -> None:
    assert join_ids([3, 1, 2]) == "3,1,2"
    assert join_ids([]) is None
    assert join_ids(None) is None
    with pytest.raises(ValueError):
        join_ids([1, 0])


def test_join_emails() -> None:
    assert join_emails(["a@b.co", "c@d.co"]) == "a@b.co,c@d.co"
    assert join_emails(None) is None
    with pytest.raises(ValueError):
        join_emails(["not-an-email"])


def test_require_text() -> None:
    assert require_text(" hello ", "text") == "hello"
    with pytest.raises(ValueError):
        require_text("   ", "text")
    with pytest.raises(ValueError):
        require_text("x" * 10, "text", max_length=5)
