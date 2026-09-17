"""Exception hierarchy shared by every layer of the server."""

from __future__ import annotations

import httpx

RETRYABLE_HTTPX_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
)


class WorksectionError(Exception):
    """Base class for every error raised by this package."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message


class ConfigurationError(WorksectionError):
    """Settings are missing, malformed, or mutually inconsistent."""


class AuthenticationError(WorksectionError):
    """Credentials are absent, rejected, or an OAuth exchange failed."""


class RateLimitError(WorksectionError):
    """The API answered 429 (or its own rate-limit status)."""

    def __init__(self, message: str = "rate limited", retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class TransientHTTPError(WorksectionError):
    """A 5xx or network-level failure that is worth retrying."""

    def __init__(self, message: str = "", status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class WorksectionAPIError(WorksectionError):
    """The API answered with a non-ok status payload."""

    def __init__(self, *, status: str, api_message: str, action: str) -> None:
        super().__init__(f"{action} failed: {status}: {api_message}")
        self.status = status
        self.api_message = api_message
        self.action = action


class DestructiveOperationDisabled(WorksectionError):
    """A destructive tool was invoked while destructive operations are disabled."""

    def __init__(self, tool_name: str) -> None:
        super().__init__(
            f"{tool_name} is disabled. Set ALLOW_DESTRUCTIVE_OPERATIONS=true to enable "
            "destructive tools."
        )
        self.tool_name = tool_name


class PathNotAllowedError(WorksectionError):
    """A filesystem path resolved outside the configured workspace directory."""


class OffloadNotFoundError(WorksectionError):
    """An offloaded response was requested but is no longer on disk."""


def is_retryable(exc: BaseException) -> bool:
    """Return True when retrying the same request could plausibly succeed."""
    if isinstance(exc, (RateLimitError, TransientHTTPError)):
        return True
    return isinstance(exc, RETRYABLE_HTTPX_ERRORS)
