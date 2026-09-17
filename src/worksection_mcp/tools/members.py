"""Tools for people: account members, contacts and groups."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from worksection_mcp import api_actions
from worksection_mcp.filtering import as_rows
from worksection_mcp.pages import account_page, project_page
from worksection_mcp.tooling import ToolContext, tool


class NoArguments(BaseModel):
    """Tool that takes no arguments."""


class GetMemberInput(BaseModel):
    email: str | None = Field(default=None, description="Account email to look up.")
    member_id: int | None = Field(default=None, gt=0, description="Numeric member id.")

    @model_validator(mode="after")
    def _need_one_identifier(self) -> GetMemberInput:
        if self.email is None and self.member_id is None:
            raise ValueError("get_member needs either email or member_id")
        return self


class ProjectRefInput(BaseModel):
    project_id: int = Field(gt=0, description="Project id.")


@tool(
    name="get_members",
    description="List the people in the account with their ids, emails and roles.",
    input_model=NoArguments,
)
async def get_members(context: ToolContext, _args: NoArguments) -> Any:
    payload = await context.client.call(api_actions.GET_MEMBERS, page=account_page())
    return as_rows(payload)


@tool(
    name="get_member",
    description="Find one account member by email or id.",
    input_model=GetMemberInput,
)
async def get_member(context: ToolContext, args: GetMemberInput) -> Any:
    payload = await context.client.call(api_actions.GET_MEMBERS, page=account_page())
    wanted_email = args.email.lower() if args.email else None
    for row in as_rows(payload):
        if wanted_email is not None and str(row.get("email", "")).lower() == wanted_email:
            return row
        if args.member_id is not None and str(row.get("id")) == str(args.member_id):
            return row
    return {"found": False, "detail": "no account member matches the given identifier"}


@tool(
    name="get_project_members",
    description="List the people who have access to one project.",
    input_model=ProjectRefInput,
)
async def get_project_members(context: ToolContext, args: ProjectRefInput) -> Any:
    payload = await context.client.call(api_actions.GET_MEMBERS, page=project_page(args.project_id))
    return as_rows(payload)


@tool(
    name="get_member_groups",
    description="List the member groups (teams) configured for the account.",
    input_model=NoArguments,
)
async def get_member_groups(context: ToolContext, _args: NoArguments) -> Any:
    payload = await context.client.call(api_actions.GET_MEMBER_GROUPS, page=account_page())
    return as_rows(payload)


@tool(
    name="get_contacts",
    description="List external contacts (clients) registered in the account.",
    input_model=NoArguments,
)
async def get_contacts(context: ToolContext, _args: NoArguments) -> Any:
    payload = await context.client.call(api_actions.GET_CONTACTS, page=account_page())
    return as_rows(payload)
