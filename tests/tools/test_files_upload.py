from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from tests.support import make_context
from worksection_mcp.errors import PathNotAllowedError
from worksection_mcp.tooling import dispatch
from worksection_mcp.tools.files import MAX_UPLOAD_BYTES


async def test_upload_from_base64_posts_multipart() -> None:
    context, requests = make_context([{"status": "ok", "id": 12}])
    result: Any = await dispatch(
        context,
        "upload_file",
        {
            "project_id": 7,
            "task_id": 55,
            "filename": "note.txt",
            "content_base64": base64.b64encode(b"hello").decode("ascii"),
        },
    )
    request = requests[0]
    assert result == {"id": 12}
    assert request.method == "POST"
    assert request.url.params["action"] == "upload_file"
    assert request.url.params["page"] == "/project/7/55/"
    assert b"note.txt" in request.content
    assert b"hello" in request.content


async def test_upload_from_the_workspace_directory(tmp_path: Path) -> None:
    (tmp_path / "report.txt").write_text("contents", encoding="utf-8")
    context, requests = make_context([{"status": "ok", "id": 13}], file_workspace_dir=str(tmp_path))
    await dispatch(
        context,
        "upload_file",
        {"project_id": 7, "task_id": 55, "workspace_filename": "report.txt"},
    )
    assert b"report.txt" in requests[0].content
    assert b"contents" in requests[0].content


async def test_upload_refuses_paths_outside_the_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (tmp_path / "secret.txt").write_text("nope", encoding="utf-8")
    context, requests = make_context([], file_workspace_dir=str(workspace))
    with pytest.raises(PathNotAllowedError):
        await dispatch(
            context,
            "upload_file",
            {"project_id": 7, "task_id": 55, "workspace_filename": "../secret.txt"},
        )
    assert requests == []


async def test_upload_refuses_absolute_paths() -> None:
    context, _ = make_context([])
    with pytest.raises(PathNotAllowedError):
        await dispatch(
            context,
            "upload_file",
            {"project_id": 7, "task_id": 55, "workspace_filename": "/etc/passwd"},
        )


async def test_upload_requires_exactly_one_source() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(context, "upload_file", {"project_id": 7, "task_id": 55})
    with pytest.raises(ValidationError):
        await dispatch(
            context,
            "upload_file",
            {
                "project_id": 7,
                "task_id": 55,
                "filename": "a.txt",
                "content_base64": "aGk=",
                "workspace_filename": "a.txt",
            },
        )


async def test_upload_rejects_invalid_base64() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(
            context,
            "upload_file",
            {"project_id": 7, "task_id": 55, "filename": "a.txt", "content_base64": "!!!!"},
        )


async def test_upload_rejects_a_filename_with_a_directory_component() -> None:
    context, _ = make_context([])
    with pytest.raises(ValidationError):
        await dispatch(
            context,
            "upload_file",
            {"project_id": 7, "task_id": 55, "filename": "../a.txt", "content_base64": "aGk="},
        )


async def test_upload_rejects_a_traversal_filename_paired_with_workspace_filename(
    tmp_path: Path,
) -> None:
    (tmp_path / "report.txt").write_text("contents", encoding="utf-8")
    context, requests = make_context([], file_workspace_dir=str(tmp_path))
    with pytest.raises(ValidationError):
        await dispatch(
            context,
            "upload_file",
            {
                "project_id": 7,
                "task_id": 55,
                "workspace_filename": "report.txt",
                "filename": "../../etc/passwd",
            },
        )
    assert requests == []


async def test_upload_refuses_an_oversized_file_from_the_workspace(tmp_path: Path) -> None:
    (tmp_path / "huge.bin").write_bytes(b"x" * (MAX_UPLOAD_BYTES + 1))
    context, requests = make_context([], file_workspace_dir=str(tmp_path))
    with pytest.raises(ValueError, match="exceeds"):
        await dispatch(
            context,
            "upload_file",
            {"project_id": 7, "task_id": 55, "workspace_filename": "huge.bin"},
        )
    assert requests == []
