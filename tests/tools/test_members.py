from __future__ import annotations

from typing import Any

from tests.support import make_context
from worksection_mcp.tooling import dispatch

PEOPLE = [
    {"id": 1, "email": "a@b.co", "name": "Ann"},
    {"id": 2, "email": "c@d.co", "name": "Bob"},
]


async def test_get_members_lists_account_users() -> None:
    context, requests = make_context([{"status": "ok", "data": PEOPLE}])
    result: Any = await dispatch(context, "get_members", {})
    assert [row["name"] for row in result] == ["Ann", "Bob"]
    assert requests[0].url.params["action"] == "get_users"


async def test_get_member_finds_by_email_case_insensitively() -> None:
    context, _ = make_context([{"status": "ok", "data": PEOPLE}])
    result: Any = await dispatch(context, "get_member", {"email": "C@D.CO"})
    assert result["name"] == "Bob"


async def test_get_member_finds_by_id() -> None:
    context, _ = make_context([{"status": "ok", "data": PEOPLE}])
    result: Any = await dispatch(context, "get_member", {"member_id": 1})
    assert result["name"] == "Ann"


async def test_get_member_returns_a_clear_miss() -> None:
    context, _ = make_context([{"status": "ok", "data": PEOPLE}])
    result: Any = await dispatch(context, "get_member", {"email": "nobody@acme.co"})
    assert result == {"found": False, "detail": "no account member matches the given identifier"}


async def test_get_project_members_scopes_to_a_project() -> None:
    context, requests = make_context([{"status": "ok", "data": PEOPLE}])
    await dispatch(context, "get_project_members", {"project_id": 7})
    assert requests[0].url.params["page"] == "/project/7/"
    assert requests[0].url.params["action"] == "get_users"


async def test_get_contacts_and_groups_use_their_actions() -> None:
    context, requests = make_context([{"status": "ok", "data": []}, {"status": "ok", "data": []}])
    await dispatch(context, "get_contacts", {})
    await dispatch(context, "get_member_groups", {})
    assert requests[0].url.params["action"] == "get_contacts"
    assert requests[1].url.params["action"] == "get_groups"
