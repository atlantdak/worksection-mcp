from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep real credentials out of the test process."""
    for name in (
        "AUTH_MODE",
        "WORKSECTION_ACCOUNT",
        "WORKSECTION_API_KEY",
        "OAUTH_CLIENT_ID",
        "OAUTH_CLIENT_SECRET",
        "FERNET_KEY",
        "ALLOW_DESTRUCTIVE_OPERATIONS",
        "FILE_WORKSPACE_DIR",
    ):
        monkeypatch.delenv(name, raising=False)
