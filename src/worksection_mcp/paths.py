"""The single gate between caller-supplied text and the filesystem.

No tool accepts a free-form path. A caller may name a file *relative to* the
configured workspace directory, and only if it resolves inside that directory
without following a symlink out of it.
"""

from __future__ import annotations

from pathlib import Path

from worksection_mcp.errors import PathNotAllowedError


def resolve_within_workspace(name: str, workspace: Path | None) -> Path:
    """Resolve ``name`` inside ``workspace`` or raise PathNotAllowedError."""
    if workspace is None:
        raise PathNotAllowedError(
            "no workspace directory is configured; set FILE_WORKSPACE_DIR to allow "
            "uploading files by name"
        )
    if "\x00" in name:
        raise PathNotAllowedError("file name contains a null byte")
    if not name.strip():
        raise PathNotAllowedError("file name must not be empty")

    candidate = Path(name)
    if candidate.is_absolute():
        raise PathNotAllowedError("file name must be relative to the workspace directory")
    if any(part == ".." for part in candidate.parts):
        raise PathNotAllowedError("file name must not contain '..'")

    if not workspace.is_dir():
        raise PathNotAllowedError(
            f"the configured workspace directory {str(workspace)!r} does not exist"
        )
    root = workspace.resolve(strict=True)
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root):
        raise PathNotAllowedError(f"{name!r} resolves outside the workspace directory")
    if (root / candidate).is_symlink() or resolved != (root / candidate):
        raise PathNotAllowedError(f"{name!r} is a symlink, which is not allowed")
    if not resolved.is_file():
        raise PathNotAllowedError(f"{name!r} is not a regular file inside the workspace")
    return resolved


def list_workspace_files(workspace: Path | None) -> list[str]:
    """Names, relative to the workspace, of every regular non-symlink file in it."""
    if workspace is None or not workspace.is_dir():
        return []
    root = workspace.resolve()
    names: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            names.append(path.relative_to(root).as_posix())
    return names
