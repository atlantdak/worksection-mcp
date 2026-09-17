"""Project tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from worksection_mcp import api_actions
from worksection_mcp.pages import account_page, project_page
from worksection_mcp.tooling import ToolContext, tool

EXTRA_FIELDS = "text,users"


class GetProjectsInput(BaseModel):
    status: Literal["active", "archive", "all"] | None = Field(
        default=None, description="Restrict to active or archived projects."
    )
    include_extra: bool = Field(
        default=False,
        description="Include project description text and member lists in each row.",
    )


class GetProjectInput(BaseModel):
    project_id: int = Field(gt=0, description="Numeric Worksection project id.")
    include_extra: bool = Field(default=False, description="Include description text and members.")


@tool(
    name="get_projects",
    description="List projects visible to the authenticated account.",
    input_model=GetProjectsInput,
)
async def get_projects(context: ToolContext, args: GetProjectsInput) -> Any:
    return await context.client.call(
        api_actions.GET_PROJECTS,
        page=account_page(),
        params={
            "filter": args.status,
            "extra": EXTRA_FIELDS if args.include_extra else None,
        },
    )


@tool(
    name="get_project",
    description="Fetch a single project by id, including its status and dates.",
    input_model=GetProjectInput,
)
async def get_project(context: ToolContext, args: GetProjectInput) -> Any:
    return await context.client.call(
        api_actions.GET_PROJECT,
        page=project_page(args.project_id),
        params={"extra": EXTRA_FIELDS if args.include_extra else None},
    )
