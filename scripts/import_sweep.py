"""Compile every source file and import every module in the package.

A syntax error or import-time crash in a module that no test happens to
import must fail the build, so this runs in CI before the test suite.

Usage: uv run python scripts/import_sweep.py
"""

from __future__ import annotations

import importlib
import pkgutil
import py_compile
import sys
from collections.abc import Sequence
from pathlib import Path

DEFAULT_ROOTS = (Path("src"), Path("tests"), Path("scripts"))


def compile_tree(roots: Sequence[Path]) -> list[tuple[str, str]]:
    """Byte-compile every ``*.py`` beneath each root. Returns (path, error) pairs."""
    failures: list[tuple[str, str]] = []
    for root in roots:
        if not root.exists():
            continue
        for source in sorted(root.rglob("*.py")):
            try:
                py_compile.compile(str(source), doraise=True, quiet=1)
            except py_compile.PyCompileError as exc:
                failures.append((str(source), str(exc)))
    return failures


def sweep(package_name: str = "worksection_mcp") -> list[tuple[str, str]]:
    """Import the package and every submodule. Returns (module, error) pairs."""
    failures: list[tuple[str, str]] = []
    try:
        package = importlib.import_module(package_name)
    except Exception as exc:
        return [(package_name, f"{type(exc).__name__}: {exc}")]

    search_paths = getattr(package, "__path__", None)
    if search_paths is None:
        return failures

    for module_info in pkgutil.walk_packages(search_paths, prefix=f"{package_name}."):
        try:
            importlib.import_module(module_info.name)
        except Exception as exc:
            failures.append((module_info.name, f"{type(exc).__name__}: {exc}"))
    return failures


def main() -> int:
    compile_failures = compile_tree(DEFAULT_ROOTS)
    import_failures = sweep()
    for path, error in compile_failures:
        print(f"compile failed: {path}: {error}", file=sys.stderr)
    for module, error in import_failures:
        print(f"import failed: {module}: {error}", file=sys.stderr)
    if compile_failures or import_failures:
        return 1
    print("compile + import sweep clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
