from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from worksection_mcp.errors import PathNotAllowedError
from worksection_mcp.paths import list_workspace_files, resolve_within_workspace


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    (root / "sub").mkdir(parents=True)
    (root / "ok.txt").write_text("fine", encoding="utf-8")
    (root / "sub" / "nested.txt").write_text("nested", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("secret", encoding="utf-8")
    return root


def test_resolves_a_simple_name(workspace: Path) -> None:
    assert resolve_within_workspace("ok.txt", workspace) == (workspace / "ok.txt").resolve()


def test_resolves_a_nested_name(workspace: Path) -> None:
    assert resolve_within_workspace("sub/nested.txt", workspace).name == "nested.txt"


def test_rejects_parent_traversal(workspace: Path) -> None:
    with pytest.raises(PathNotAllowedError):
        resolve_within_workspace("../outside.txt", workspace)


def test_rejects_absolute_paths(workspace: Path) -> None:
    with pytest.raises(PathNotAllowedError):
        resolve_within_workspace(str(workspace.parent / "outside.txt"), workspace)


def test_rejects_when_no_workspace_is_configured() -> None:
    with pytest.raises(PathNotAllowedError, match="FILE_WORKSPACE_DIR"):
        resolve_within_workspace("ok.txt", None)


def test_rejects_a_missing_file(workspace: Path) -> None:
    with pytest.raises(PathNotAllowedError):
        resolve_within_workspace("nope.txt", workspace)


def test_rejects_a_directory(workspace: Path) -> None:
    with pytest.raises(PathNotAllowedError):
        resolve_within_workspace("sub", workspace)


@pytest.mark.skipif(sys.platform == "win32", reason="symlink creation needs privileges on Windows")
def test_rejects_a_symlink_escaping_the_workspace(workspace: Path) -> None:
    link = workspace / "escape.txt"
    os.symlink(workspace.parent / "outside.txt", link)
    with pytest.raises(PathNotAllowedError):
        resolve_within_workspace("escape.txt", workspace)


def test_rejects_null_bytes(workspace: Path) -> None:
    with pytest.raises(PathNotAllowedError):
        resolve_within_workspace("ok.txt\x00.png", workspace)


def test_rejects_an_empty_name(workspace: Path) -> None:
    with pytest.raises(PathNotAllowedError):
        resolve_within_workspace("", workspace)


def test_rejects_a_whitespace_only_name(workspace: Path) -> None:
    with pytest.raises(PathNotAllowedError):
        resolve_within_workspace("   ", workspace)


def test_list_workspace_files_is_relative_and_sorted(workspace: Path) -> None:
    assert list_workspace_files(workspace) == ["ok.txt", "sub/nested.txt"]
    assert list_workspace_files(None) == []
