from __future__ import annotations

from pathlib import Path

from worksection_mcp.config import load_settings
from worksection_mcp.preflight import CheckResult, check_configuration, summarise


def _settings(**overrides: object) -> object:
    base: dict[str, object] = {
        "auth_mode": "admin_key",
        "worksection_account": "acme",
        "worksection_api_key": "secret-key",
    }
    base.update(overrides)
    return load_settings(**base)


def test_healthy_admin_configuration_passes_every_check(tmp_path: Path) -> None:
    results = check_configuration(_settings(state_dir=str(tmp_path)))  # type: ignore[arg-type]
    assert results
    assert all(result.ok for result in results), summarise(results)


def test_missing_workspace_dir_is_reported_but_not_fatal(tmp_path: Path) -> None:
    results = check_configuration(
        _settings(state_dir=str(tmp_path), file_workspace_dir=str(tmp_path / "nope"))  # type: ignore[arg-type]
    )
    workspace = next(r for r in results if r.name == "file_workspace_dir")
    assert workspace.ok is False
    assert "does not exist" in workspace.detail


def test_state_dir_is_created_with_private_permissions(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    check_configuration(_settings(state_dir=str(state_dir)))  # type: ignore[arg-type]
    assert state_dir.is_dir()
    assert state_dir.stat().st_mode & 0o777 == 0o700


def test_summary_marks_failures(tmp_path: Path) -> None:
    text = summarise([CheckResult("a", True, "fine"), CheckResult("b", False, "broken")])
    assert "PASS" in text
    assert "FAIL" in text
    assert "broken" in text


def test_no_secret_value_appears_in_the_summary(tmp_path: Path) -> None:
    results = check_configuration(_settings(state_dir=str(tmp_path)))  # type: ignore[arg-type]
    assert "secret-key" not in summarise(results)
