"""The single place this server talks to Worksection over HTTP."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from types import TracebackType
from typing import Any

import httpx

from worksection_mcp.auth.base import AuthProvider
from worksection_mcp.cache.session_cache import SessionCache, cache_key
from worksection_mcp.config import Settings
from worksection_mcp.errors import (
    AuthenticationError,
    RateLimitError,
    TransientHTTPError,
    WorksectionAPIError,
    is_retryable,
)
from worksection_mcp.http.params import normalize_params
from worksection_mcp.http.rate_limiter import AdaptiveRateLimiter
from worksection_mcp.logging_setup import get_logger

logger = get_logger("http.client")

OK_STATUSES = frozenset({"ok", "success"})
READ_ACTION_PREFIX = "get_"


def extract_payload(body: Mapping[str, Any], action: str) -> Any:
    """Unwrap a Worksection response envelope or raise WorksectionAPIError."""
    status = str(body.get("status", "")).lower()
    if status not in OK_STATUSES:
        raise WorksectionAPIError(
            status=status or "unknown",
            api_message=str(body.get("message") or body.get("error") or "no message"),
            action=action,
        )
    if "data" in body:
        return body["data"]
    return {key: value for key, value in body.items() if key != "status"}


def _retry_after(response: httpx.Response) -> float | None:
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


class WorksectionClient:
    """Authenticated, rate-limited, retrying access to the Worksection API."""

    def __init__(
        self,
        settings: Settings,
        auth: AuthProvider,
        *,
        http: httpx.AsyncClient | None = None,
        limiter: AdaptiveRateLimiter | None = None,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
        cache: SessionCache | None = None,
    ) -> None:
        self._settings = settings
        self._auth = auth
        self._owns_http = http is None
        self._http = http or httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "worksection-mcp"},
        )
        self._limiter = limiter or AdaptiveRateLimiter(settings.rate_limit_rps)
        self._sleep = sleeper
        self._cache = cache

    async def __aenter__(self) -> WorksectionClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def call(
        self,
        action: str,
        *,
        page: str = "",
        params: Mapping[str, Any] | None = None,
        method: str = "GET",
        files: Mapping[str, tuple[str, bytes, str]] | None = None,
    ) -> Any:
        """Issue one API action and return its unwrapped payload."""
        flat = normalize_params(params)
        is_read = action.startswith(READ_ACTION_PREFIX)
        key = cache_key(action, page, flat)
        if is_read and self._cache is not None:
            cached = self._cache.get(key)
            if cached is not None:
                logger.debug("cache hit for %s", action)
                return cached
        attempts = self._settings.max_retries + 1
        last_error: BaseException | None = None

        for attempt in range(attempts):
            prepared = await self._auth.prepare(action, page, flat)
            await self._limiter.acquire()
            try:
                response = await self._http.request(
                    method,
                    prepared.url,
                    params=prepared.params,
                    headers=prepared.headers,
                    files=files,
                )
                result = self._handle_response(response, action)
                if self._cache is not None:
                    if is_read:
                        self._cache.set(key, result)
                    else:
                        self._cache.invalidate_all()
                return result
            except Exception as exc:
                last_error = exc
                if not is_retryable(exc) or attempt == attempts - 1:
                    raise
                delay = self._backoff_delay(attempt, exc)
                logger.info(
                    "retrying %s after %s (attempt %d/%d, sleeping %.1fs)",
                    action,
                    type(exc).__name__,
                    attempt + 1,
                    attempts,
                    delay,
                )
                await self._sleep(delay)

        raise last_error if last_error else RuntimeError("unreachable retry state")

    def _backoff_delay(self, attempt: int, exc: BaseException) -> float:
        if isinstance(exc, RateLimitError) and exc.retry_after is not None:
            return exc.retry_after
        return float(2**attempt)

    def _handle_response(self, response: httpx.Response, action: str) -> Any:
        if response.status_code == 429:
            retry_after = _retry_after(response)
            self._limiter.record_rate_limited(retry_after)
            raise RateLimitError(f"{action} was rate limited", retry_after=retry_after)
        if response.status_code in (401, 403):
            raise AuthenticationError(
                f"{action} was rejected with HTTP {response.status_code}; check credentials"
            )
        if response.status_code >= 500:
            raise TransientHTTPError(
                f"{action} failed with HTTP {response.status_code}",
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise WorksectionAPIError(
                status=str(response.status_code),
                api_message=response.text[:200],
                action=action,
            )

        self._limiter.record_success()
        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise WorksectionAPIError(
                status="invalid_json",
                api_message=f"response body was not JSON: {response.text[:120]!r}",
                action=action,
            ) from exc
        if not isinstance(body, Mapping):
            return body
        return extract_payload(body, action)

    async def download(self, url: str) -> bytes:
        """Fetch a binary resource (attachment) and return its bytes."""
        await self._limiter.acquire()
        response = await self._http.get(url)
        if response.status_code >= 400:
            raise WorksectionAPIError(
                status=str(response.status_code),
                api_message=f"download failed for {url}",
                action="download",
            )
        self._limiter.record_success()
        return response.content
