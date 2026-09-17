"""Project tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from worksection_mcp import api_actions
from worksection_mcp.filtering import as_rows
from worksection_mcp.pages import account_page, project_page
from worksection_mcp.tooling import ToolContext, tool
from worksection_mcp.validators import DateString, require_text

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


class CreateProjectInput(BaseModel):
    title: str = Field(description="Project title.")
    text: str | None = Field(default=None, description="Project description.")
    manager_email: str | None = Field(default=None, description="Account email of the manager.")
    author_email: str | None = Field(default=None, description="Account email of the author.")
    start_date: DateString | None = Field(default=None, description="Project start date.")
    due_date: DateString | None = Field(default=None, description="Project due date.")

    @model_validator(mode="after")
    def _check_title(self) -> CreateProjectInput:
        object.__setattr__(self, "title", require_text(self.title, "title", max_length=500))
        return self


class UpdateProjectInput(BaseModel):
    project_id: int = Field(gt=0, description="Project to update.")
    title: str | None = Field(default=None, description="New title.")
    text: str | None = Field(default=None, description="New description.")
    manager_email: str | None = Field(default=None, description="New manager email.")
    start_date: DateString | None = Field(default=None, description="New start date.")
    due_date: DateString | None = Field(default=None, description="New due date.")

    @model_validator(mode="after")
    def _check_title(self) -> UpdateProjectInput:
        if self.title is not None:
            object.__setattr__(self, "title", require_text(self.title, "title", max_length=500))
        return self

    @model_validator(mode="after")
    def _require_a_change(self) -> UpdateProjectInput:
        changes = (self.title, self.text, self.manager_email, self.start_date, self.due_date)
        if all(value is None for value in changes):
            raise ValueError("update_project needs at least one field to change")
        return self


class ProjectRefInput(BaseModel):
    project_id: int = Field(gt=0, description="Project id.")


@tool(
    name="create_project",
    description="Create a project, optionally with a manager, description and dates.",
    input_model=CreateProjectInput,
)
async def create_project(context: ToolContext, args: CreateProjectInput) -> Any:
    return await context.client.call(
        api_actions.POST_PROJECT,
        page=account_page(),
        params={
            "title": args.title,
            "text": args.text,
            "email_manager": args.manager_email,
            "email_user_from": args.author_email,
            "date_start": args.start_date,
            "date_end": args.due_date,
        },
    )


@tool(
    name="update_project",
    description="Change a project's title, description, manager or dates.",
    input_model=UpdateProjectInput,
)
async def update_project(context: ToolContext, args: UpdateProjectInput) -> Any:
    return await context.client.call(
        api_actions.UPDATE_PROJECT,
        page=project_page(args.project_id),
        params={
            "title": args.title,
            "text": args.text,
            "email_manager": args.manager_email,
            "date_start": args.start_date,
            "date_end": args.due_date,
        },
    )


@tool(
    name="archive_project",
    description="Close a project and move it to the archive. Reversible with activate_project.",
    input_model=ProjectRefInput,
)
async def archive_project(context: ToolContext, args: ProjectRefInput) -> Any:
    return await context.client.call(api_actions.CLOSE_PROJECT, page=project_page(args.project_id))


@tool(
    name="activate_project",
    description="Restore an archived project to active status.",
    input_model=ProjectRefInput,
)
async def activate_project(context: ToolContext, args: ProjectRefInput) -> Any:
    return await context.client.call(
        api_actions.ACTIVATE_PROJECT, page=project_page(args.project_id)
    )


@tool(
    name="get_project_groups",
    description="List the task groups (folders) configured inside a project.",
    input_model=ProjectRefInput,
)
async def get_project_groups(context: ToolContext, args: ProjectRefInput) -> Any:
    payload = await context.client.call(
        api_actions.GET_PROJECT_GROUPS, page=project_page(args.project_id)
    )
    return as_rows(payload)
