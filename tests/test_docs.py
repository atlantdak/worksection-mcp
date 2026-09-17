from __future__ import annotations

from pathlib import Path

import worksection_mcp.tools  # noqa: F401 - registers every tool
from worksection_mcp.tooling import all_tool_specs

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_api_limitations_document_exists_and_covers_the_known_quirks() -> None:
    text = (REPO_ROOT / "docs" / "API-LIMITATIONS.md").read_text(encoding="utf-8")
    for topic in ("Pagination", "status", "Rate limiting", "Dates", "Verification status"):
        assert topic in text


def test_every_documented_quirk_says_whether_it_was_verified() -> None:
    text = (REPO_ROOT / "docs" / "API-LIMITATIONS.md").read_text(encoding="utf-8")
    assert text.count("Verified:") >= 5


def test_no_tool_is_missing_a_description() -> None:
    for spec in all_tool_specs():
        assert spec.description.strip()
        assert len(spec.description) > 20
