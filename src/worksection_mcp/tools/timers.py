"""Timer tools for live time tracking."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from worksection_mcp import api_actions
from worksection_mcp.filtering import as_rows
from worksection_mcp.pages import account_page, task_page
from worksection_mcp.tooling import ToolContext, tool
from worksection_mcp.validators import require_text


class StartTimerInput(BaseModel):
    project_id: int = Field(gt=0, description="Project the task belongs to.")
    task_id: int = Field(gt=0, description="Task to time.")
    user_email: str | None = Field(default=None, description="Person the timer belongs to.")


class StopTimerInput(BaseModel):
    project_id: int = Field(gt=0, description="Project the task belongs to.")
    task_id: int = Field(gt=0, description="Task whose timer to stop.")
    comment: str | None = Field(default=None, description="Comment to store with the entry.")
    user_email: str | None = Field(default=None, description="Person the timer belongs to.")

    @model_validator(mode="after")
    def _check_comment(self) -> StopTimerInput:
        if self.comment is not None:
            object.__setattr__(self, "comment", require_text(self.comment, "comment"))
        return self


class NoArguments(BaseModel):
    """Tool that takes no arguments."""


@tool(
    name="start_timer",
    description="Start a running timer on a task.",
    input_model=StartTimerInput,
)
async def start_timer(context: ToolContext, args: StartTimerInput) -> Any:
    return await context.client.call(
        api_actions.START_TIMER,
        page=task_page(args.project_id, args.task_id),
        params={"email_user_from": args.user_email},
    )


@tool(
    name="stop_timer",
    description="Stop the running timer on a task and store the elapsed time.",
    input_model=StopTimerInput,
)
async def stop_timer(context: ToolContext, args: StopTimerInput) -> Any:
    return await context.client.call(
        api_actions.STOP_TIMER,
        page=task_page(args.project_id, args.task_id),
        params={"comment": args.comment, "email_user_from": args.user_email},
    )


@tool(
    name="get_running_timers",
    description="List every timer currently running in the account.",
    input_model=NoArguments,
)
async def get_running_timers(context: ToolContext, _args: NoArguments) -> Any:
    payload = await context.client.call(api_actions.GET_TIMERS, page=account_page())
    return as_rows(payload)
