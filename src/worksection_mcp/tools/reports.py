"""Reporting tools built by aggregating raw API rows locally."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from worksection_mcp import api_actions
from worksection_mcp.analytics import group_tasks_by_assignee, summarise_costs, summarise_tasks
from worksection_mcp.filtering import as_rows
from worksection_mcp.pages import account_page, project_page, task_page
from worksection_mcp.tooling import ToolContext, tool
from worksection_mcp.validators import DateString


class TimeReportInput(BaseModel):
    project_id: int | None = Field(default=None, gt=0, description="Limit to one project.")
    task_id: int | None = Field(
        default=None, gt=0, description="Limit to one task. Requires project_id."
    )
    date_from: DateString | None = Field(default=None, description="Inclusive start date.")
    date_to: DateString | None = Field(default=None, description="Inclusive end date.")
    user_email: str | None = Field(default=None, description="Limit to one person.")
    include_entries: bool = Field(
        default=False, description="Include every raw entry alongside the totals."
    )

    @model_validator(mode="after")
    def _task_needs_project(self) -> TimeReportInput:
        if self.task_id is not None and self.project_id is None:
            raise ValueError("task_id requires project_id")
        return self


class ProjectStatsInput(BaseModel):
    project_id: int = Field(gt=0, description="Project to summarise.")


class TeamWorkloadInput(BaseModel):
    project_id: int | None = Field(
        default=None, gt=0, description="Limit the workload view to one project."
    )


@tool(
    name="get_time_report",
    description=(
        "Summarise logged time and money for an account, project or task over a date "
        "range, totalled per person."
    ),
    input_model=TimeReportInput,
)
async def get_time_report(context: ToolContext, args: TimeReportInput) -> dict[str, Any]:
    if args.project_id is None:
        page = account_page()
    elif args.task_id is None:
        page = project_page(args.project_id)
    else:
        page = task_page(args.project_id, args.task_id)

    payload = await context.client.call(
        api_actions.GET_COSTS,
        page=page,
        params={
            "datestart": args.date_from,
            "dateend": args.date_to,
            "email_user_from": args.user_email,
        },
    )
    rows = as_rows(payload)
    summary = summarise_costs(rows)
    if args.include_entries:
        summary["entries_detail"] = rows
    return summary


@tool(
    name="get_project_stats",
    description="Count a project's tasks by status and priority bucket.",
    input_model=ProjectStatsInput,
)
async def get_project_stats(context: ToolContext, args: ProjectStatsInput) -> dict[str, Any]:
    payload = await context.client.call(api_actions.GET_TASKS, page=project_page(args.project_id))
    return summarise_tasks(as_rows(payload))


@tool(
    name="get_team_workload",
    description="Group open and completed tasks by assignee across the account or one project.",
    input_model=TeamWorkloadInput,
)
async def get_team_workload(context: ToolContext, args: TeamWorkloadInput) -> dict[str, Any]:
    if args.project_id is None:
        payload = await context.client.call(api_actions.GET_ALL_TASKS, page=account_page())
    else:
        payload = await context.client.call(
            api_actions.GET_TASKS, page=project_page(args.project_id)
        )
    return group_tasks_by_assignee(as_rows(payload))
