"""Subtask tools. A subtask is a task whose page is scoped to its parent task."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from worksection_mcp import api_actions
from worksection_mcp.filtering import as_rows
from worksection_mcp.pages import subtask_page, task_page
from worksection_mcp.tooling import ToolContext, tool
from worksection_mcp.validators import DateString, require_text


class SubtaskListInput(BaseModel):
    project_id: int = Field(gt=0, description="Project the parent task belongs to.")
    task_id: int = Field(gt=0, description="Parent task id.")


class CreateSubtaskInput(BaseModel):
    project_id: int = Field(gt=0, description="Project the parent task belongs to.")
    task_id: int = Field(gt=0, description="Parent task id.")
    title: str = Field(description="Subtask title.")
    text: str | None = Field(default=None, description="Subtask description.")
    assignee_email: str | None = Field(default=None, description="Account email to assign to.")
    due_date: DateString | None = Field(default=None, description="Due date.")
    priority: int | None = Field(default=None, ge=0, le=10, description="Priority from 0 to 10.")

    @model_validator(mode="after")
    def _check_title(self) -> CreateSubtaskInput:
        object.__setattr__(self, "title", require_text(self.title, "title", max_length=500))
        return self


class UpdateSubtaskInput(BaseModel):
    project_id: int = Field(gt=0, description="Project the parent task belongs to.")
    task_id: int = Field(gt=0, description="Parent task id.")
    subtask_id: int = Field(gt=0, description="Subtask id.")
    title: str | None = Field(default=None, description="New title.")
    text: str | None = Field(default=None, description="New description.")
    assignee_email: str | None = Field(default=None, description="New assignee email.")
    due_date: DateString | None = Field(default=None, description="New due date.")
    priority: int | None = Field(default=None, ge=0, le=10, description="New priority.")

    @model_validator(mode="after")
    def _check_title(self) -> UpdateSubtaskInput:
        if self.title is not None:
            object.__setattr__(self, "title", require_text(self.title, "title", max_length=500))
        return self

    @model_validator(mode="after")
    def _require_a_change(self) -> UpdateSubtaskInput:
        changes = (self.title, self.text, self.assignee_email, self.due_date)
        if all(value is None for value in changes) and self.priority is None:
            raise ValueError("update_subtask needs at least one field to change")
        return self


@tool(
    name="get_subtasks",
    description="List the subtasks of a task.",
    input_model=SubtaskListInput,
)
async def get_subtasks(context: ToolContext, args: SubtaskListInput) -> Any:
    payload = await context.client.call(
        api_actions.GET_TASKS, page=task_page(args.project_id, args.task_id)
    )
    return as_rows(payload)


@tool(
    name="create_subtask",
    description="Create a subtask under an existing task.",
    input_model=CreateSubtaskInput,
)
async def create_subtask(context: ToolContext, args: CreateSubtaskInput) -> Any:
    return await context.client.call(
        api_actions.POST_TASK,
        page=task_page(args.project_id, args.task_id),
        params={
            "title": args.title,
            "text": args.text,
            "email_user_to": args.assignee_email,
            "date_end": args.due_date,
            "priority": args.priority,
        },
    )


@tool(
    name="update_subtask",
    description="Change the title, description, assignee, due date or priority of a subtask.",
    input_model=UpdateSubtaskInput,
)
async def update_subtask(context: ToolContext, args: UpdateSubtaskInput) -> Any:
    return await context.client.call(
        api_actions.UPDATE_TASK,
        page=subtask_page(args.project_id, args.task_id, args.subtask_id),
        params={
            "title": args.title,
            "text": args.text,
            "email_user_to": args.assignee_email,
            "date_end": args.due_date,
            "priority": args.priority,
        },
    )
