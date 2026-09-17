from __future__ import annotations

import httpx
import pytest

from worksection_mcp.errors import (
    AuthenticationError,
    ConfigurationError,
    DestructiveOperationDisabled,
    RateLimitError,
    TransientHTTPError,
    WorksectionAPIError,
    WorksectionError,
    is_retryable,
)


def test_all_errors_share_a_base() -> None:
    for cls in (
        ConfigurationError,
        AuthenticationError,
        RateLimitError,
        TransientHTTPError,
        WorksectionAPIError,
        DestructiveOperationDisabled,
    ):
        assert issubclass(cls, WorksectionError)


def test_api_error_carries_status_and_action() -> None:
    err = WorksectionAPIError(status="error", api_message="no access", action="get_task")
    assert err.status == "error"
    assert err.api_message == "no access"
    assert err.action == "get_task"
    assert "get_task" in str(err)


def test_rate_limit_error_keeps_retry_after() -> None:
    assert RateLimitError(retry_after=2.5).retry_after == 2.5
    assert RateLimitError().retry_after is None


def test_destructive_error_names_the_tool() -> None:
    err = DestructiveOperationDisabled("delete_task")
    assert err.tool_name == "delete_task"
    assert "ALLOW_DESTRUCTIVE_OPERATIONS" in str(err)


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (RateLimitError(), True),
        (TransientHTTPError("boom", status_code=503), True),
        (httpx.ConnectError("down"), True),
        (httpx.ReadTimeout("slow"), True),
        (ConfigurationError("bad"), False),
        (WorksectionAPIError(status="error", api_message="nope", action="get_task"), False),
        (ValueError("unrelated"), False),
    ],
)
def test_is_retryable_classification(exc: BaseException, expected: bool) -> None:
    assert is_retryable(exc) is expected
