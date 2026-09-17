from __future__ import annotations

import json
from pathlib import Path

from worksection_mcp.offload import ResponseOffloader
from worksection_mcp.serialization import render_result


def test_small_results_are_still_inline(tmp_path: Path) -> None:
    offloader = ResponseOffloader(tmp_path, threshold_bytes=1000, chunk_bytes=100)
    blocks = render_result({"id": 1}, offloader)
    assert json.loads(blocks[0].text) == {"id": 1}


def test_large_results_are_replaced_by_a_summary(tmp_path: Path) -> None:
    offloader = ResponseOffloader(tmp_path, threshold_bytes=100, chunk_bytes=50)
    blocks = render_result({"rows": list(range(500))}, offloader)
    payload = json.loads(blocks[0].text)
    assert payload["offloaded"] is True
    assert payload["resource_uri"].startswith("worksection://offload/")
    assert payload["total_chunks"] >= 1
    assert "preview" in payload


def test_without_an_offloader_nothing_changes(tmp_path: Path) -> None:
    blocks = render_result({"rows": list(range(500))})
    assert json.loads(blocks[0].text)["rows"][0] == 0
