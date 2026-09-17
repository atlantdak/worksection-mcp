"""Startup checks that turn configuration mistakes into readable messages."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass

from worksection_mcp.config import Settings, load_settings
from worksection_mcp.errors import ConfigurationError


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one preflight check. ``detail`` never contains secret values."""

    name: str
    ok: bool
    detail: str


def check_configuration(settings: Settings) -> list[CheckResult]:
    """Run every non-network check and return one result per check."""
    results: list[CheckResult] = [
        CheckResult("auth_mode", True, f"using {settings.auth_mode} mode"),
    ]

    if settings.auth_mode == "admin_key":
        results.append(
            CheckResult("account", True, f"account slug '{settings.worksection_account}' set")
        )
        results.append(CheckResult("api_key", True, "admin API key present"))
        results.append(CheckResult("api_base_url", True, settings.admin_api_base_url))
    else:
        results.append(CheckResult("oauth_client", True, "client id and secret present"))
        results.append(CheckResult("fernet_key", True, "token encryption key present"))
        results.append(CheckResult("redirect_uri", True, settings.redirect_uri))

    try:
        settings.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        settings.state_dir.chmod(0o700)
        results.append(CheckResult("state_dir", True, f"{settings.state_dir} ready (0700)"))
    except OSError as exc:
        results.append(
            CheckResult("state_dir", False, f"cannot create {settings.state_dir}: {exc}")
        )

    if settings.file_workspace_dir is None:
        results.append(
            CheckResult("file_workspace_dir", True, "not configured; file upload by path disabled")
        )
    elif not settings.file_workspace_dir.is_dir():
        results.append(
            CheckResult(
                "file_workspace_dir",
                False,
                f"{settings.file_workspace_dir} does not exist or is not a directory",
            )
        )
    else:
        results.append(CheckResult("file_workspace_dir", True, str(settings.file_workspace_dir)))

    results.append(
        CheckResult(
            "destructive_operations",
            True,
            "enabled" if settings.allow_destructive_operations else "disabled (default)",
        )
    )
    return results


def summarise(results: Sequence[CheckResult]) -> str:
    """Render results as an aligned, secret-free report."""
    width = max((len(result.name) for result in results), default=0)
    lines = [
        f"[{'PASS' if result.ok else 'FAIL'}] {result.name.ljust(width)}  {result.detail}"
        for result in results
    ]
    failures = sum(1 for result in results if not result.ok)
    lines.append("")
    lines.append("configuration OK" if failures == 0 else f"{failures} check(s) failed")
    return "\n".join(lines)


def run_preflight() -> int:
    """Entry point for the CLI script. Returns a process exit code."""
    try:
        settings = load_settings()
    except ConfigurationError as exc:
        print(exc.message, file=sys.stderr)
        return 1
    results = check_configuration(settings)
    print(summarise(results))
    return 0 if all(result.ok for result in results) else 1
