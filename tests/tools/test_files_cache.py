from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from tests.support import make_context
from worksection_mcp.cache.file_cache import FileCache
from worksection_mcp.tooling import dispatch


async def test_second_download_is_served_from_the_cache(tmp_path: Path) -> None:
    files = [{"id": 3, "title": "a.txt", "url": "https://files.test/3"}]
    context, requests = make_context(
        [
            {"status": "ok", "data": files},
            httpx.Response(200, content=b"hello"),
            {"status": "ok", "data": files},
        ]
    )
    context.file_cache = FileCache(tmp_path / "files", ttl_seconds=60, max_bytes=1_000_000)

    first: Any = await dispatch(
        context, "download_file", {"project_id": 7, "task_id": 55, "file_id": 3}
    )
    second: Any = await dispatch(
        context, "download_file", {"project_id": 7, "task_id": 55, "file_id": 3}
    )

    assert first["content_base64"] == second["content_base64"]
    assert second["from_cache"] is True
    assert first["from_cache"] is False
    download_requests = [r for r in requests if r.url.host == "files.test"]
    assert len(download_requests) == 1
