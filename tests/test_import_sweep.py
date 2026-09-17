from __future__ import annotations

from pathlib import Path

import pytest
from scripts.import_sweep import compile_tree, sweep


def test_every_module_in_the_package_imports_cleanly() -> None:
    assert sweep("worksection_mcp") == []


def test_sweep_reports_a_broken_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = tmp_path / "broken_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "bad.py").write_text("raise RuntimeError('nope')\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    failures = sweep("broken_pkg")
    assert [name for name, _ in failures] == ["broken_pkg.bad"]


def test_compile_tree_catches_python_2_syntax(tmp_path: Path) -> None:
    source = tmp_path / "legacy.py"
    source.write_text("try:\n    pass\nexcept ValueError, exc:\n    pass\n", encoding="utf-8")
    failures = compile_tree([tmp_path])
    assert failures
    assert "legacy.py" in failures[0][0]


def test_compile_tree_is_quiet_for_valid_sources(tmp_path: Path) -> None:
    (tmp_path / "fine.py").write_text("x = 1\n", encoding="utf-8")
    assert compile_tree([tmp_path]) == []
