"""File tools.

No tool here accepts a free-form filesystem path: downloads are returned
inline as base64 with a size cap, and the workspace listing only ever
reports names relative to the single configured directory.
"""

from __future__ import annotations

import base64
from typing import Any

from pydantic import BaseModel, Field

from worksection_mcp import api_actions
from worksection_mcp.filtering import as_rows
from worksection_mcp.pages import task_page
from worksection_mcp.paths import list_workspace_files as _list_workspace_files
from worksection_mcp.tooling import ToolContext, tool

DEFAULT_MAX_DOWNLOAD_BYTES = 5 * 1024 * 1024


class NoArguments(BaseModel):
    """Tool that takes no arguments."""


class TaskFilesInput(BaseModel):
    project_id: int = Field(gt=0, description="Project the task belongs to.")
    task_id: int = Field(gt=0, description="Task id.")


class DownloadFileInput(TaskFilesInput):
    file_id: int = Field(gt=0, description="Attachment id, from get_task_files.")
    max_bytes: int = Field(
        default=DEFAULT_MAX_DOWNLOAD_BYTES,
        gt=0,
        le=DEFAULT_MAX_DOWNLOAD_BYTES,
        description="Refuse to inline content larger than this many bytes.",
    )


async def _find_attachment(
    context: ToolContext, project_id: int, task_id: int, file_id: int
) -> dict[str, Any] | None:
    payload = await context.client.call(api_actions.GET_FILES, page=task_page(project_id, task_id))
    for row in as_rows(payload):
        if str(row.get("id")) == str(file_id):
            return row
    return None


@tool(
    name="get_task_files",
    description="List the files attached to a task, with their ids, names and sizes.",
    input_model=TaskFilesInput,
)
async def get_task_files(context: ToolContext, args: TaskFilesInput) -> Any:
    payload = await context.client.call(
        api_actions.GET_FILES, page=task_page(args.project_id, args.task_id)
    )
    return as_rows(payload)


@tool(
    name="download_file",
    description=(
        "Fetch one attachment and return it inline as base64. Refuses files larger "
        "than max_bytes instead of writing anywhere on disk."
    ),
    input_model=DownloadFileInput,
)
async def download_file(context: ToolContext, args: DownloadFileInput) -> dict[str, Any]:
    attachment = await _find_attachment(context, args.project_id, args.task_id, args.file_id)
    if attachment is None:
        return {"found": False, "detail": f"no attachment with id {args.file_id} on this task"}

    url = str(attachment.get("url") or "")
    if not url.startswith("https://"):
        return {"found": False, "detail": "attachment has no downloadable https URL"}

    content = await context.client.download(url)
    if len(content) > args.max_bytes:
        return {
            "found": True,
            "truncated": True,
            "filename": attachment.get("title"),
            "size_bytes": len(content),
            "content_base64": "",
            "detail": f"file is {len(content)} bytes, above the {args.max_bytes} byte limit",
        }
    return {
        "found": True,
        "truncated": False,
        "filename": attachment.get("title"),
        "size_bytes": len(content),
        "content_base64": base64.b64encode(content).decode("ascii"),
    }


@tool(
    name="list_workspace_files",
    description=(
        "List the files available in the configured workspace directory. "
        "Returns an empty list when FILE_WORKSPACE_DIR is not set."
    ),
    input_model=NoArguments,
)
async def list_workspace_files(context: ToolContext, _args: NoArguments) -> dict[str, Any]:
    workspace = context.settings.file_workspace_dir
    return {
        "workspace_configured": workspace is not None,
        "workspace": str(workspace) if workspace else None,
        "files": _list_workspace_files(workspace),
    }
