"""The contract every authentication provider implements."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class PreparedRequest:
    """Everything the HTTP client needs to issue one authenticated call."""

    url: str
    params: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class AuthProvider(Protocol):
    """Adds credentials to an outgoing request without touching the URL string."""

    @property
    def mode(self) -> str: ...

    async def prepare(
        self, action: str, page: str, params: Mapping[str, str]
    ) -> PreparedRequest: ...
