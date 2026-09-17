"""Tag tools.

Tag values are comma-joined on the wire, so a tag containing a comma is
rejected rather than silently split.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from worksection_mcp import api_actions
from worksection_mcp.filtering import as_rows
from worksection_mcp.pages import account_page, task_page
from worksection_mcp.tooling import ToolContext, tool


class NoArguments(BaseModel):
    """Tool that takes no arguments."""


class TaskRefInput(BaseModel):
    project_id: int = Field(gt=0, description="Project the task belongs to.")
    task_id: int = Field(gt=0, description="Task id.")


class TaskTagsInput(TaskRefInput):
    tags: list[str] = Field(description="Tag names. Must be non-empty and contain no commas.")

    @model_validator(mode="after")
    def _check_tags(self) -> TaskTagsInput:
        if not self.tags:
            raise ValueError("tags must contain at least one value")
        for value in self.tags:
            if not value.strip():
                raise ValueError("tag values must not be blank")
            if "," in value:
                raise ValueError(f"tag values must not contain commas: {value!r}")
        return self


@tool(
    name="get_tags",
    description="List the tag groups and tags configured for the account.",
    input_model=NoArguments,
)
async def get_tags(context: ToolContext, _args: NoArguments) -> Any:
    payload = await context.client.call(api_actions.GET_TAGS, page=account_page())
    return as_rows(payload)


@tool(
    name="get_task_tags",
    description="List the tag names currently applied to a task.",
    input_model=TaskRefInput,
)
async def get_task_tags(context: ToolContext, args: TaskRefInput) -> list[str]:
    payload = await context.client.call(
        api_actions.GET_TASK, page=task_page(args.project_id, args.task_id)
    )
    tags = payload.get("tags") if isinstance(payload, dict) else None
    if isinstance(tags, dict):
        return [str(value) for value in tags.values()]
    if isinstance(tags, list):
        return [str(value) for value in tags]
    return []


@tool(
    name="add_task_tags",
    description="Add tags to a task, keeping the tags it already has.",
    input_model=TaskTagsInput,
)
async def add_task_tags(context: ToolContext, args: TaskTagsInput) -> Any:
    return await context.client.call(
        api_actions.ADD_TAGS,
        page=task_page(args.project_id, args.task_id),
        params={"tags": args.tags},
    )


@tool(
    name="set_task_tags",
    description="Replace every tag on a task with the given list.",
    input_model=TaskTagsInput,
)
async def set_task_tags(context: ToolContext, args: TaskTagsInput) -> Any:
    return await context.client.call(
        api_actions.SET_TAGS,
        page=task_page(args.project_id, args.task_id),
        params={"tags": args.tags},
    )
