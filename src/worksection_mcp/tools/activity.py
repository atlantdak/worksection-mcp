"""Activity log and task-distribution tools."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from worksection_mcp import api_actions
from worksection_mcp.analytics import HIGH_PRIORITY, NORMAL_PRIORITY, overdue_tasks, summarise_tasks
from worksection_mcp.filtering import as_rows
from worksection_mcp.pages import account_page, project_page
from worksection_mcp.tooling import ToolContext, tool
from worksection_mcp.validators import DateString


class ActivityLogInput(BaseModel):
    project_id: int | None = Field(default=None, gt=0, description="Limit to one project.")
    date_from: DateString | None = Field(default=None, description="Inclusive start date.")
    date_to: DateString | None = Field(default=None, description="Inclusive end date.")


class ScopeInput(BaseModel):
    project_id: int | None = Field(
        default=None, gt=0, description="Limit to one project; omit for the whole account."
    )


async def _fetch_tasks(context: ToolContext, project_id: int | None) -> list[dict[str, Any]]:
    if project_id is None:
        payload = await context.client.call(api_actions.GET_ALL_TASKS, page=account_page())
    else:
        payload = await context.client.call(api_actions.GET_TASKS, page=project_page(project_id))
    return as_rows(payload)


def _priority_bucket(value: Any) -> str:
    try:
        priority = float(value or 0)
    except (TypeError, ValueError):
        priority = 0.0
    if priority >= HIGH_PRIORITY:
        return "high"
    if priority >= NORMAL_PRIORITY:
        return "normal"
    return "low"


@tool(
    name="get_activity_log",
    description="List recent account or project activity events over a date range.",
    input_model=ActivityLogInput,
)
async def get_activity_log(context: ToolContext, args: ActivityLogInput) -> Any:
    page = account_page() if args.project_id is None else project_page(args.project_id)
    payload = await context.client.call(
        api_actions.GET_EVENTS,
        page=page,
        params={"datestart": args.date_from, "dateend": args.date_to},
    )
    return as_rows(payload)


@tool(
    name="get_overdue_tasks",
    description="List open tasks whose due date has passed, most overdue first.",
    input_model=ScopeInput,
)
async def get_overdue_tasks(context: ToolContext, args: ScopeInput) -> dict[str, Any]:
    rows = await _fetch_tasks(context, args.project_id)
    overdue = overdue_tasks(rows, today=date.today())
    return {"count": len(overdue), "tasks": overdue}


@tool(
    name="get_tasks_by_status",
    description="Group tasks by status, with counts and the tasks in each group.",
    input_model=ScopeInput,
)
async def get_tasks_by_status(context: ToolContext, args: ScopeInput) -> dict[str, Any]:
    rows = await _fetch_tasks(context, args.project_id)
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row.get("status") or "unknown").lower(), []).append(row)
    return {"summary": summarise_tasks(rows), "groups": groups}


@tool(
    name="get_tasks_by_priority",
    description="Group tasks into high, normal and low priority buckets.",
    input_model=ScopeInput,
)
async def get_tasks_by_priority(context: ToolContext, args: ScopeInput) -> dict[str, Any]:
    rows = await _fetch_tasks(context, args.project_id)
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(_priority_bucket(row.get("priority")), []).append(row)
    return {"summary": summarise_tasks(rows), "groups": groups}
