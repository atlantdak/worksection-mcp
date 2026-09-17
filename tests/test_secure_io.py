from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from worksection_mcp.secure_io import (
    ensure_private_dir,
    read_secret_file,
    remove_secret_file,
    write_secret_file,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX permission bits are not meaningful on Windows"
)


def test_private_dir_is_created_with_0700(tmp_path: Path) -> None:
    target = ensure_private_dir(tmp_path / "state" / "nested")
    assert target.is_dir()
    assert target.stat().st_mode & 0o777 == 0o700


def test_existing_dir_permissions_are_tightened(tmp_path: Path) -> None:
    loose = tmp_path / "loose"
    loose.mkdir(mode=0o755)
    assert ensure_private_dir(loose).stat().st_mode & 0o777 == 0o700


def test_secret_file_is_written_with_0600(tmp_path: Path) -> None:
    path = write_secret_file(tmp_path / "secrets" / "tokens.enc", b"payload")
    assert path.read_bytes() == b"payload"
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700


def test_write_is_atomic_and_leaves_no_temp_files(tmp_path: Path) -> None:
    path = write_secret_file(tmp_path / "tokens.enc", b"one")
    write_secret_file(path, b"two")
    assert path.read_bytes() == b"two"
    assert sorted(item.name for item in tmp_path.iterdir()) == ["tokens.enc"]


def test_umask_is_restored_after_writing(tmp_path: Path) -> None:
    before = os.umask(0o022)
    os.umask(before)
    write_secret_file(tmp_path / "tokens.enc", b"x")
    after = os.umask(0o022)
    os.umask(after)
    assert after == before


def test_read_and_remove(tmp_path: Path) -> None:
    path = tmp_path / "tokens.enc"
    assert read_secret_file(path) is None
    assert remove_secret_file(path) is False
    write_secret_file(path, b"data")
    assert read_secret_file(path) == b"data"
    assert remove_secret_file(path) is True
    assert not path.exists()
