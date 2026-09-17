"""Turn tool arguments into flat string params.

Encoding is deliberately *not* done here: the resulting mapping is handed to
httpx as ``params=``, which performs correct percent-encoding. Never build a
query string by concatenation anywhere in this codebase.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def normalize_params(params: Mapping[str, Any] | None) -> dict[str, str]:
    """Flatten a parameter mapping to ``str -> str``, dropping ``None`` values."""
    if not params:
        return {}
    flat: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            flat[key] = "1" if value else "0"
        elif isinstance(value, (str, bytes)):
            flat[key] = value.decode() if isinstance(value, bytes) else value
        elif isinstance(value, Sequence):
            flat[key] = ",".join(str(item) for item in value)
        else:
            flat[key] = str(value)
    return flat
