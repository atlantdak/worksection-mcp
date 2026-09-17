"""Time and money tracking tools (Worksection calls these "costs")."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from worksection_mcp import api_actions
from worksection_mcp.filtering import as_rows
from worksection_mcp.pages import account_page, project_page, task_page
from worksection_mcp.tooling import ToolContext, tool
from worksection_mcp.validators import DateString, require_text


def _scope(project_id: int | None, task_id: int | None) -> str:
    if project_id is None:
        return account_page()
    if task_id is None:
        return project_page(project_id)
    return task_page(project_id, task_id)


class GetCostsInput(BaseModel):
    project_id: int | None = Field(default=None, gt=0, description="Limit to one project.")
    task_id: int | None = Field(
        default=None, gt=0, description="Limit to one task. Requires project_id."
    )
    date_from: DateString | None = Field(default=None, description="Inclusive start date.")
    date_to: DateString | None = Field(default=None, description="Inclusive end date.")
    user_email: str | None = Field(default=None, description="Limit to one person's entries.")

    @model_validator(mode="after")
    def _task_needs_project(self) -> GetCostsInput:
        if self.task_id is not None and self.project_id is None:
            raise ValueError("task_id requires project_id")
        return self


class AddCostsInput(BaseModel):
    project_id: int = Field(gt=0, description="Project the task belongs to.")
    task_id: int = Field(gt=0, description="Task to log time against.")
    hours: float = Field(gt=0, le=24, description="Hours spent, e.g. 1.5.")
    comment: str | None = Field(default=None, description="What the time was spent on.")
    date: DateString | None = Field(default=None, description="Date of the work.")
    money: float | None = Field(default=None, ge=0, description="Cost amount, if tracked.")
    user_email: str | None = Field(default=None, description="Person the entry belongs to.")

    @model_validator(mode="after")
    def _check_comment(self) -> AddCostsInput:
        if self.comment is not None:
            object.__setattr__(self, "comment", require_text(self.comment, "comment"))
        return self


class UpdateCostsInput(BaseModel):
    project_id: int = Field(gt=0, description="Project the task belongs to.")
    task_id: int = Field(gt=0, description="Task the entry belongs to.")
    cost_id: int = Field(gt=0, description="Entry to update.")
    hours: float | None = Field(default=None, gt=0, le=24, description="New hours value.")
    comment: str | None = Field(default=None, description="New comment.")
    date: DateString | None = Field(default=None, description="New date.")
    money: float | None = Field(default=None, ge=0, description="New cost amount.")

    @model_validator(mode="after")
    def _check_comment(self) -> UpdateCostsInput:
        if self.comment is not None:
            object.__setattr__(self, "comment", require_text(self.comment, "comment"))
        return self

    @model_validator(mode="after")
    def _require_a_change(self) -> UpdateCostsInput:
        if self.hours is None and self.comment is None and self.date is None and self.money is None:
            raise ValueError("update_costs needs at least one field to change")
        return self


class DeleteCostsInput(BaseModel):
    project_id: int = Field(gt=0, description="Project the task belongs to.")
    task_id: int = Field(gt=0, description="Task the entry belongs to.")
    cost_id: int = Field(gt=0, description="Entry to delete permanently.")
    confirm: bool = Field(default=False, description="Must be true. Deletion is permanent.")

    @model_validator(mode="after")
    def _require_confirmation(self) -> DeleteCostsInput:
        if not self.confirm:
            raise ValueError("delete_costs requires confirm=true")
        return self


@tool(
    name="get_costs",
    description=(
        "List logged time and cost entries, optionally scoped to a project or task, "
        "a date range, or one person."
    ),
    input_model=GetCostsInput,
)
async def get_costs(context: ToolContext, args: GetCostsInput) -> Any:
    payload = await context.client.call(
        api_actions.GET_COSTS,
        page=_scope(args.project_id, args.task_id),
        params={
            "datestart": args.date_from,
            "dateend": args.date_to,
            "email_user_from": args.user_email,
        },
    )
    return as_rows(payload)


@tool(
    name="add_costs",
    description="Log time (and optionally money) against a task.",
    input_model=AddCostsInput,
)
async def add_costs(context: ToolContext, args: AddCostsInput) -> Any:
    return await context.client.call(
        api_actions.ADD_COSTS,
        page=task_page(args.project_id, args.task_id),
        params={
            "time": args.hours,
            "comment": args.comment,
            "date": args.date,
            "money": args.money,
            "email_user_from": args.user_email,
        },
    )


@tool(
    name="update_costs",
    description="Change the hours, comment, date or amount of an existing time entry.",
    input_model=UpdateCostsInput,
)
async def update_costs(context: ToolContext, args: UpdateCostsInput) -> Any:
    return await context.client.call(
        api_actions.UPDATE_COSTS,
        page=task_page(args.project_id, args.task_id),
        params={
            "id_cost": args.cost_id,
            "time": args.hours,
            "comment": args.comment,
            "date": args.date,
            "money": args.money,
        },
    )


@tool(
    name="delete_costs",
    description=(
        "Permanently delete a time entry. Only available when "
        "ALLOW_DESTRUCTIVE_OPERATIONS=true, and requires confirm=true."
    ),
    input_model=DeleteCostsInput,
    destructive=True,
)
async def delete_costs(context: ToolContext, args: DeleteCostsInput) -> Any:
    return await context.client.call(
        api_actions.DELETE_COSTS,
        page=task_page(args.project_id, args.task_id),
        params={"id_cost": args.cost_id},
    )
