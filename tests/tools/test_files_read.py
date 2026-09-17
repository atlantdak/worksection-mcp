from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import httpx

from tests.support import make_context
from worksection_mcp.tooling import dispatch


async def test_get_task_files_lists_attachments() -> None:
    files = [{"id": 3, "title": "spec.pdf", "url": "https://files.test/3"}]
    context, requests = make_context([{"status": "ok", "data": files}])
    result: Any = await dispatch(context, "get_task_files", {"project_id": 7, "task_id": 55})
    assert [row["title"] for row in result] == ["spec.pdf"]
    assert requests[0].url.params["action"] == "get_files"
    assert requests[0].url.params["page"] == "/project/7/55/"


async def test_download_file_returns_base64_content() -> None:
    files = [{"id": 3, "title": "a.txt", "url": "https://files.test/3"}]
    context, requests = make_context(
        [{"status": "ok", "data": files}, httpx.Response(200, content=b"hello")]
    )
    result: Any = await dispatch(
        context, "download_file", {"project_id": 7, "task_id": 55, "file_id": 3}
    )
    assert result["filename"] == "a.txt"
    assert result["size_bytes"] == 5
    assert base64.b64decode(result["content_base64"]) == b"hello"
    assert str(requests[1].url) == "https://files.test/3"


async def test_download_file_reports_an_unknown_id() -> None:
    context, _ = make_context([{"status": "ok", "data": []}])
    result: Any = await dispatch(
        context, "download_file", {"project_id": 7, "task_id": 55, "file_id": 99}
    )
    assert result["found"] is False


async def test_download_file_refuses_oversized_attachments() -> None:
    files = [{"id": 3, "title": "big.bin", "url": "https://files.test/3", "size": "99999999"}]
    context, _ = make_context(
        [{"status": "ok", "data": files}, httpx.Response(200, content=b"x" * 2048)]
    )
    result: Any = await dispatch(
        context,
        "download_file",
        {"project_id": 7, "task_id": 55, "file_id": 3, "max_bytes": 1024},
    )
    assert result["truncated"] is True
    assert result["content_base64"] == ""


async def test_list_workspace_files_reports_configured_files(tmp_path: Path) -> None:
    (tmp_path / "doc.txt").write_text("x", encoding="utf-8")
    context, _ = make_context([], file_workspace_dir=str(tmp_path))
    result: Any = await dispatch(context, "list_workspace_files", {})
    assert result["files"] == ["doc.txt"]
    assert result["workspace_configured"] is True


async def test_list_workspace_files_when_unconfigured() -> None:
    context, _ = make_context([])
    result: Any = await dispatch(context, "list_workspace_files", {})
    assert result["workspace_configured"] is False
    assert result["files"] == []
