from __future__ import annotations

import json

from worksection_mcp.errors import WorksectionAPIError
from worksection_mcp.serialization import render_error, render_result


def test_dict_is_rendered_as_pretty_json() -> None:
    blocks = render_result({"id": 1, "title": "x"})
    assert len(blocks) == 1
    assert blocks[0].type == "text"
    assert json.loads(blocks[0].text) == {"id": 1, "title": "x"}


def test_plain_string_is_passed_through() -> None:
    assert render_result("done")[0].text == "done"


def test_none_becomes_an_explicit_marker() -> None:
    assert render_result(None)[0].text == "null"


def test_non_serialisable_values_fall_back_to_repr() -> None:
    blocks = render_result({"when": object()})
    assert "object object" in blocks[0].text


def test_render_error_reports_type_and_message() -> None:
    payload = json.loads(
        render_error(WorksectionAPIError(status="error", api_message="denied", action="get_task"))[
            0
        ].text
    )
    assert payload["error"]["type"] == "WorksectionAPIError"
    assert "denied" in payload["error"]["message"]
