"""Filesystem helpers for anything secret.

Every write happens under ``os.umask(0o077)`` so no intermediate state is
world- or group-readable, and the final file is chmod 0600 regardless.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

DIR_MODE = 0o700
FILE_MODE = 0o600
SECRET_UMASK = 0o077


def ensure_private_dir(path: Path) -> Path:
    """Create ``path`` (and parents) as a private directory and return it."""
    previous = os.umask(SECRET_UMASK)
    try:
        path.mkdir(mode=DIR_MODE, parents=True, exist_ok=True)
    finally:
        os.umask(previous)
    path.chmod(DIR_MODE)
    return path


def write_secret_file(path: Path, data: bytes) -> Path:
    """Atomically write ``data`` to ``path`` with owner-only permissions."""
    ensure_private_dir(path.parent)
    previous = os.umask(SECRET_UMASK)
    handle, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temp_path.chmod(FILE_MODE)
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    finally:
        os.umask(previous)
    path.chmod(FILE_MODE)
    return path


def read_secret_file(path: Path) -> bytes | None:
    """Read a secret file, or None when it does not exist."""
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def remove_secret_file(path: Path) -> bool:
    """Delete a secret file. Returns True when something was removed."""
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True
