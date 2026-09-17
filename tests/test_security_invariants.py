"""Executable versions of the project's non-negotiable security rules."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import worksection_mcp.tools  # noqa: F401 - registers every tool
from worksection_mcp.config import load_settings
from worksection_mcp.tooling import all_tool_specs, enabled_tool_specs

SRC = Path(__file__).resolve().parents[1] / "src" / "worksection_mcp"
SOURCES = sorted(SRC.rglob("*.py"))
EXPECTED_DESTRUCTIVE = {"delete_task", "delete_comment", "delete_costs"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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
    forbidden = {"settings", "self._settings", "tokens", "token", "api_key", "self._api_key"}
    offenders: list[str] = []
    for path in SOURCES:
        tree = ast.parse(_read(path), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"debug", "info", "warning", "error", "exception", "critical"}:
                continue
            for arg in node.args:
                rendered = ast.unparse(arg)
                if rendered in forbidden:
                    offenders.append(f"{path.name}: {ast.unparse(node)}")
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
