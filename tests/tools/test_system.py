from __future__ import annotations

from pathlib import Path
from typing import Any

from worksection_mcp.config import Settings, load_settings
from worksection_mcp.tooling import ToolContext, dispatch


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    base: dict[str, object] = {
        "auth_mode": "admin_key",
        "worksection_account": "acme",
        "worksection_api_key": "k",
        "state_dir": str(tmp_path),
    }
    base.update(overrides)
    return load_settings(**base)


async def test_validate_configuration_reports_checks(tmp_path: Path) -> None:
    import worksection_mcp.tools  # noqa: F401 - registers every tool

    context = ToolContext(settings=_settings(tmp_path), client=object())  # type: ignore[arg-type]
    result: Any = await dispatch(context, "validate_configuration", {})
    assert result["ok"] is True
    assert result["auth_mode"] == "admin_key"
    assert result["destructive_operations_enabled"] is False
    assert any(check["name"] == "state_dir" for check in result["checks"])


async def test_validate_configuration_never_leaks_the_api_key(tmp_path: Path) -> None:
    import worksection_mcp.tools  # noqa: F401

    context = ToolContext(
        settings=_settings(tmp_path, worksection_api_key="super-secret-token"),
        client=object(),  # type: ignore[arg-type]
    )
    result = await dispatch(context, "validate_configuration", {})
    assert "super-secret-token" not in repr(result)
