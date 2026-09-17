"""Task tools: reading, creating, updating and closing tasks."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from worksection_mcp import api_actions
from worksection_mcp.filtering import as_rows, filter_tasks
from worksection_mcp.pages import account_page, project_page, task_page
from worksection_mcp.tooling import ToolContext, tool

TaskStatus = Literal["active", "done", "all"]
TASK_EXTRA_FIELDS = "text,files,subtasks"


class GetAllTasksInput(BaseModel):
    status: TaskStatus | None = Field(
        default=None, description="Filter by task status; applied again locally."
    )
    assignee_email: str | None = Field(
        default=None, description="Only tasks assigned to this account email."
    )


class GetTasksInput(BaseModel):
    project_id: int = Field(gt=0, description="Project to list tasks from.")
    status: TaskStatus | None = Field(default=None, description="Filter by task status.")
    assignee_email: str | None = Field(default=None, description="Filter by assignee email.")


class GetTaskInput(BaseModel):
    project_id: int = Field(gt=0, description="Project the task belongs to.")
    task_id: int = Field(gt=0, description="Task id.")
    include_extra: bool = Field(
        default=False, description="Include description text, files and subtasks."
    )


@tool(
    name="get_all_tasks",
    description=(
        "List tasks across every project the account can see. Status and assignee "
        "filters are re-applied locally because the API's own filtering is unreliable "
        "for some combinations."
    ),
    input_model=GetAllTasksInput,
)
async def get_all_tasks(context: ToolContext, args: GetAllTasksInput) -> Any:
    payload = await context.client.call(
        api_actions.GET_ALL_TASKS,
        page=account_page(),
        params={"status": args.status, "email_user_to": args.assignee_email},
    )
    return filter_tasks(
        as_rows(payload),
        status=None if args.status in (None, "all") else args.status,
        assignee_email=args.assignee_email,
    )


@tool(
    name="get_tasks",
    description="List tasks inside one project, with local status and assignee filtering.",
    input_model=GetTasksInput,
)
async def get_tasks(context: ToolContext, args: GetTasksInput) -> Any:
    payload = await context.client.call(
        api_actions.GET_TASKS,
        page=project_page(args.project_id),
        params={"status": args.status, "email_user_to": args.assignee_email},
    )
    return filter_tasks(
        as_rows(payload),
        status=None if args.status in (None, "all") else args.status,
        assignee_email=args.assignee_email,
    )


@tool(
    name="get_task",
    description="Fetch one task, optionally with its description text, files and subtasks.",
    input_model=GetTaskInput,
)
async def get_task(context: ToolContext, args: GetTaskInput) -> Any:
    return await context.client.call(
        api_actions.GET_TASK,
        page=task_page(args.project_id, args.task_id),
        params={"extra": TASK_EXTRA_FIELDS if args.include_extra else None},
    )
