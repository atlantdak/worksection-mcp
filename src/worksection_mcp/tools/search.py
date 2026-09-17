"""Task search.

The API cannot combine every filter reliably, so the server fetches the
relevant scope once and filters locally. ``limit`` bounds the response size.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from worksection_mcp import api_actions
from worksection_mcp.filtering import as_rows, filter_tasks
from worksection_mcp.pages import account_page, project_page
from worksection_mcp.tooling import ToolContext, tool
from worksection_mcp.validators import DateString, require_text


class SearchTasksInput(BaseModel):
    text: str | None = Field(default=None, description="Substring to look for in title or body.")
    project_id: int | None = Field(
        default=None, gt=0, description="Search inside one project instead of the whole account."
    )
    status: Literal["active", "done"] | None = Field(default=None, description="Task status.")
    assignee_email: str | None = Field(default=None, description="Assignee's account email.")
    priority_min: int | None = Field(
        default=None, ge=0, le=10, description="Minimum priority, inclusive."
    )
    due_before: DateString | None = Field(default=None, description="Due on or before this date.")
    due_after: DateString | None = Field(default=None, description="Due on or after this date.")
    limit: int = Field(default=50, ge=1, le=500, description="Maximum tasks to return.")

    @model_validator(mode="after")
    def _check_text(self) -> SearchTasksInput:
        if self.text is not None:
            object.__setattr__(self, "text", require_text(self.text, "text", max_length=500))
        return self

    @model_validator(mode="after")
    def _need_a_criterion(self) -> SearchTasksInput:
        criteria = (
            self.text,
            self.status,
            self.assignee_email,
            self.priority_min,
            self.due_before,
            self.due_after,
            self.project_id,
        )
        if all(value is None for value in criteria):
            raise ValueError("search_tasks needs at least one search criterion")
        return self


@tool(
    name="search_tasks",
    description=(
        "Search tasks by text, status, assignee, priority and due date, across the "
        "account or inside one project. Filtering is applied locally for reliability."
    ),
    input_model=SearchTasksInput,
)
async def search_tasks(context: ToolContext, args: SearchTasksInput) -> dict[str, Any]:
    if args.project_id is None:
        payload = await context.client.call(api_actions.GET_ALL_TASKS, page=account_page())
    else:
        payload = await context.client.call(
            api_actions.GET_TASKS, page=project_page(args.project_id)
        )

    rows = as_rows(payload)
    matched = filter_tasks(
        rows,
        status=args.status,
        assignee_email=args.assignee_email,
        text=args.text,
        priority_min=args.priority_min,
        due_before=args.due_before,
        due_after=args.due_after,
    )
    return {
        "scanned": len(rows),
        "matched": len(matched),
        "truncated": len(matched) > args.limit,
        "tasks": matched[: args.limit],
    }
