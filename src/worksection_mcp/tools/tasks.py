"""Task tools: reading, creating, updating and closing tasks."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from worksection_mcp import api_actions
from worksection_mcp.filtering import as_rows, filter_tasks
from worksection_mcp.pages import account_page, project_page, task_page
from worksection_mcp.tooling import ToolContext, tool
from worksection_mcp.validators import DateString, join_emails, require_text

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


class CreateTaskInput(BaseModel):
    project_id: int = Field(gt=0, description="Project to create the task in.")
    title: str = Field(description="Task title.")
    text: str | None = Field(default=None, description="Task description, plain text or HTML.")
    assignee_email: str | None = Field(default=None, description="Account email to assign to.")
    author_email: str | None = Field(
        default=None, description="Account email to record as the author."
    )
    start_date: DateString | None = Field(default=None, description="Start date.")
    due_date: DateString | None = Field(default=None, description="Due date.")
    priority: int | None = Field(default=None, ge=0, le=10, description="Priority from 0 to 10.")
    subscriber_emails: list[str] | None = Field(
        default=None, description="Account emails to subscribe to the task."
    )

    @model_validator(mode="after")
    def _check_title(self) -> CreateTaskInput:
        object.__setattr__(self, "title", require_text(self.title, "title", max_length=500))
        return self


class UpdateTaskInput(BaseModel):
    project_id: int = Field(gt=0, description="Project the task belongs to.")
    task_id: int = Field(gt=0, description="Task to update.")
    title: str | None = Field(default=None, description="New title.")
    text: str | None = Field(default=None, description="New description.")
    assignee_email: str | None = Field(default=None, description="New assignee email.")
    start_date: DateString | None = Field(default=None, description="New start date.")
    due_date: DateString | None = Field(default=None, description="New due date.")
    priority: int | None = Field(default=None, ge=0, le=10, description="New priority.")

    @model_validator(mode="after")
    def _require_a_change(self) -> UpdateTaskInput:
        changes = (self.title, self.text, self.assignee_email, self.start_date, self.due_date)
        if all(value is None for value in changes) and self.priority is None:
            raise ValueError("update_task needs at least one field to change")
        return self


class TaskRefInput(BaseModel):
    project_id: int = Field(gt=0, description="Project the task belongs to.")
    task_id: int = Field(gt=0, description="Task id.")


@tool(
    name="create_task",
    description="Create a task in a project, optionally assigned, dated and prioritised.",
    input_model=CreateTaskInput,
)
async def create_task(context: ToolContext, args: CreateTaskInput) -> Any:
    return await context.client.call(
        api_actions.POST_TASK,
        page=project_page(args.project_id),
        params={
            "title": args.title,
            "text": args.text,
            "email_user_to": args.assignee_email,
            "email_user_from": args.author_email,
            "date_start": args.start_date,
            "date_end": args.due_date,
            "priority": args.priority,
            "subscribe": join_emails(args.subscriber_emails),
        },
    )


@tool(
    name="update_task",
    description="Change the title, description, assignee, dates or priority of a task.",
    input_model=UpdateTaskInput,
)
async def update_task(context: ToolContext, args: UpdateTaskInput) -> Any:
    return await context.client.call(
        api_actions.UPDATE_TASK,
        page=task_page(args.project_id, args.task_id),
        params={
            "title": args.title,
            "text": args.text,
            "email_user_to": args.assignee_email,
            "date_start": args.start_date,
            "date_end": args.due_date,
            "priority": args.priority,
        },
    )


@tool(
    name="complete_task",
    description="Mark a task as done.",
    input_model=TaskRefInput,
)
async def complete_task(context: ToolContext, args: TaskRefInput) -> Any:
    return await context.client.call(
        api_actions.COMPLETE_TASK, page=task_page(args.project_id, args.task_id)
    )


@tool(
    name="reopen_task",
    description="Reopen a previously completed task.",
    input_model=TaskRefInput,
)
async def reopen_task(context: ToolContext, args: TaskRefInput) -> Any:
    return await context.client.call(
        api_actions.REOPEN_TASK, page=task_page(args.project_id, args.task_id)
    )
