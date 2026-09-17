"""Executable versions of the project's non-negotiable security rules."""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import worksection_mcp.tools  # noqa: F401 - registers every tool
from worksection_mcp.config import load_settings
from worksection_mcp.tooling import all_tool_specs, enabled_tool_specs

SRC = Path(__file__).resolve().parents[1] / "src" / "worksection_mcp"
SOURCES = sorted(SRC.rglob("*.py"))
EXPECTED_DESTRUCTIVE = {"delete_task", "delete_comment", "delete_costs"}

# The naming convention every destructive tool in this codebase actually
# follows (delete_task, delete_comment, delete_costs), plus the near
# synonyms a future addition is likely to use. Anything matching this that
# is *not* in EXPECTED_DESTRUCTIVE, or not marked destructive=True, should
# fail loudly rather than ship fully exposed by accident.
DESTRUCTIVE_NAME_PATTERN = re.compile(r"^(delete_|remove_|purge_)")

LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}
FORBIDDEN_LOG_NAMES = {"settings", "self._settings", "tokens", "token", "api_key", "self._api_key"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _mentions_forbidden_name(node: ast.AST, forbidden: set[str]) -> bool:
    """True if a ``Name``/``Attribute`` anywhere inside ``node`` renders to a forbidden name.

    Walking the whole subtree - not just unparsing the top-level argument -
    is what lets this catch a forbidden name hidden inside an f-string
    (``ast.JoinedStr``/``ast.FormattedValue``), a ``.format()`` call, string
    concatenation, or any other expression shape, instead of only a bare
    ``logger.info(token)`` positional argument.
    """
    for sub in ast.walk(node):
        if isinstance(sub, (ast.Name, ast.Attribute)) and ast.unparse(sub) in forbidden:
            return True
    return False


def _forbidden_logging_calls(
    source_text: str, source_name: str = "<source>", forbidden: set[str] | None = None
) -> list[str]:
    """Return one description per ``logger.*`` call that mentions a forbidden name.

    Every positional and keyword argument of the call is walked (not merely
    unparsed as a whole), so a forbidden name buried inside an f-string or a
    ``%s``/``.format()``-style call is caught just as reliably as a bare
    argument.
    """
    names = FORBIDDEN_LOG_NAMES if forbidden is None else forbidden
    offenders: list[str] = []
    tree = ast.parse(source_text, filename=source_name)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in LOG_METHODS:
            continue
        call_arguments: list[ast.expr] = list(node.args) + [kw.value for kw in node.keywords]
        if any(_mentions_forbidden_name(argument, names) for argument in call_arguments):
            offenders.append(f"{source_name}: {ast.unparse(node)}")
    return offenders


def _destructive_sounding_specs_without_the_flag(specs: Iterable[Any]) -> list[str]:
    """Names of any spec that looks destructive by naming convention but isn't marked as such."""
    return [
        spec.name
        for spec in specs
        if DESTRUCTIVE_NAME_PATTERN.match(spec.name) and not spec.destructive
    ]


@dataclass
class _FakeSpec:
    """Just enough of a ToolSpec to drive the naming-convention check in isolation."""

    name: str
    destructive: bool


def test_sources_were_found() -> None:
    assert len(SOURCES) > 20


def test_no_module_binds_a_wildcard_interface() -> None:
    offenders = [path.name for path in SOURCES if "0.0.0.0" in _read(path)]  # noqa: S104
    assert offenders == []


def test_no_query_string_is_built_by_concatenation() -> None:
    pattern = re.compile(r"""["']\?[a-z_]+=|\+\s*["']&[a-z_]+=""")
    offenders = [path.name for path in SOURCES if pattern.search(_read(path))]
    assert offenders == []


def test_destructive_tools_are_exactly_the_expected_set() -> None:
    marked = {spec.name for spec in all_tool_specs() if spec.destructive}
    assert marked == EXPECTED_DESTRUCTIVE


def test_every_destructive_sounding_tool_is_marked_destructive() -> None:
    """Catches what the exact-set check above cannot: an unmarked new tool.

    The exact-set assertion only notices a *removed* flag on a tool already
    in EXPECTED_DESTRUCTIVE; it stays green if a brand-new destructive-
    sounding tool is registered without ever being flagged, because the
    marked set and EXPECTED_DESTRUCTIVE would then simply need editing to
    "fix" the failure - without necessarily adding the flag. This check
    looks at names directly, so it fails independently of that hardcoded set.
    """
    assert _destructive_sounding_specs_without_the_flag(all_tool_specs()) == []


def test_destructive_naming_check_catches_an_unmarked_delete_tool() -> None:
    """Proves the check above is load-bearing against a fake unmarked spec."""
    offenders = _destructive_sounding_specs_without_the_flag(
        [_FakeSpec(name="delete_widget", destructive=False)]
    )
    assert offenders == ["delete_widget"]


@pytest.mark.parametrize("prefix", ["delete_", "remove_", "purge_"])
def test_destructive_naming_check_covers_every_naming_convention(prefix: str) -> None:
    offenders = _destructive_sounding_specs_without_the_flag(
        [_FakeSpec(name=f"{prefix}widget", destructive=False)]
    )
    assert offenders == [f"{prefix}widget"]


def test_destructive_naming_check_allows_a_properly_marked_tool() -> None:
    offenders = _destructive_sounding_specs_without_the_flag(
        [_FakeSpec(name="delete_widget", destructive=True)]
    )
    assert offenders == []


def test_destructive_tools_are_hidden_under_default_settings() -> None:
    settings = load_settings(
        auth_mode="admin_key", worksection_account="acme", worksection_api_key="k"
    )
    visible = {spec.name for spec in enabled_tool_specs(settings)}
    assert visible & EXPECTED_DESTRUCTIVE == set()


def test_every_destructive_tool_requires_explicit_confirmation() -> None:
    for spec in all_tool_specs():
        if not spec.destructive:
            continue
        schema = spec.input_schema()
        assert "confirm" in schema["properties"], spec.name


def test_no_tool_input_field_accepts_a_free_form_path() -> None:
    allowed = {"workspace_filename"}
    for spec in all_tool_specs():
        for field in spec.input_schema()["properties"]:
            if field in allowed:
                continue
            assert not re.search(r"(^|_)(path|filepath|dir|directory)$", field), (
                f"{spec.name}.{field} looks like a filesystem path parameter"
            )


def test_no_logging_call_passes_a_settings_or_credential_object() -> None:
    offenders: list[str] = []
    for path in SOURCES:
        offenders.extend(_forbidden_logging_calls(_read(path), path.name))
    assert offenders == []


def test_forbidden_logging_check_catches_a_credential_inside_an_f_string() -> None:
    """Proves the check is not fooled by an f-string, unlike a bare-argument-only check."""
    offenders = _forbidden_logging_calls('logger.info(f"token={token}")\n', "scratch.py")
    assert offenders != []


def test_forbidden_logging_check_catches_a_percent_style_settings_dump() -> None:
    """Proves the check is not fooled by a %s-style call passing settings.__dict__."""
    offenders = _forbidden_logging_calls(
        'logger.info("settings=%s", settings.__dict__)\n', "scratch.py"
    )
    assert offenders != []


def test_forbidden_logging_check_allows_a_benign_percent_style_call() -> None:
    """Negative control: an ordinary %s call with no credential-shaped argument stays clean."""
    offenders = _forbidden_logging_calls('logger.debug("cache hit for %s", action)\n', "scratch.py")
    assert offenders == []


def test_secret_files_are_only_written_through_secure_io() -> None:
    for path in SOURCES:
        if path.name in {"secure_io.py", "offload.py", "file_cache.py"}:
            continue
        text = _read(path)
        assert "write_bytes(" not in text, f"{path.name} writes bytes outside secure_io"


def test_every_tool_input_field_documents_itself() -> None:
    for spec in all_tool_specs():
        schema = spec.input_schema()
        for name, field in schema.get("properties", {}).items():
            assert field.get("description"), f"{spec.name}.{name} has no description"


def test_lockfile_is_committed() -> None:
    assert (Path(__file__).resolve().parents[1] / "uv.lock").is_file()


@pytest.mark.parametrize("marker", ["TODO", "FIXME", "XXX"])
def test_no_unfinished_markers_in_shipped_code(marker: str) -> None:
    offenders = [path.name for path in SOURCES if marker in _read(path)]
    assert offenders == []
