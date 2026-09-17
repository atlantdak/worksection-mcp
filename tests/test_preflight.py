from __future__ import annotations

from pathlib import Path

import pytest

from worksection_mcp.config import load_settings
from worksection_mcp.preflight import CheckResult, check_configuration, run_preflight, summarise


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


def test_oauth_configuration_reports_client_and_redirect_checks(tmp_path: Path) -> None:
    settings = load_settings(
        auth_mode="oauth",
        oauth_client_id="client",
        oauth_client_secret="secret",
        fernet_key="fernet",
        state_dir=str(tmp_path),
    )
    results = check_configuration(settings)
    names = {result.name for result in results}
    assert {"oauth_client", "fernet_key", "redirect_uri"} <= names
    assert all(result.ok for result in results), summarise(results)


def test_existing_workspace_dir_is_reported_ok(tmp_path: Path) -> None:
    results = check_configuration(
        _settings(state_dir=str(tmp_path), file_workspace_dir=str(tmp_path))  # type: ignore[arg-type]
    )
    workspace = next(r for r in results if r.name == "file_workspace_dir")
    assert workspace.ok is True
    assert workspace.detail == str(tmp_path)


def test_state_dir_creation_failure_is_reported(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    results = check_configuration(_settings(state_dir=str(blocker)))  # type: ignore[arg-type]
    state = next(r for r in results if r.name == "state_dir")
    assert state.ok is False
    assert "cannot create" in state.detail


def test_run_preflight_prints_a_report_and_succeeds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AUTH_MODE", "admin_key")
    monkeypatch.setenv("WORKSECTION_ACCOUNT", "acme")
    monkeypatch.setenv("WORKSECTION_API_KEY", "secret-key")
    monkeypatch.setenv("STATE_DIR", str(tmp_path))
    exit_code = run_preflight()
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "configuration OK" in out
    assert "secret-key" not in out


def test_run_preflight_reports_invalid_configuration(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("AUTH_MODE", "admin_key")
    monkeypatch.delenv("WORKSECTION_ACCOUNT", raising=False)
    monkeypatch.delenv("WORKSECTION_API_KEY", raising=False)
    exit_code = run_preflight()
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "WORKSECTION_ACCOUNT" in err
