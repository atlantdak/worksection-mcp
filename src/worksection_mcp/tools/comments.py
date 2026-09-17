"""Comment tools: reading, posting, editing and deleting task comments."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from worksection_mcp import api_actions
from worksection_mcp.filtering import as_rows
from worksection_mcp.pages import task_page
from worksection_mcp.tooling import ToolContext, tool
from worksection_mcp.validators import require_text


class TaskCommentsInput(BaseModel):
    project_id: int = Field(gt=0, description="Project the task belongs to.")
    task_id: int = Field(gt=0, description="Task id.")


class PostCommentInput(TaskCommentsInput):
    text: str = Field(description="Comment body.")
    author_email: str | None = Field(
        default=None, description="Account email to post the comment as."
    )
    hidden: bool = Field(default=False, description="Post as an internal comment.")

    @model_validator(mode="after")
    def _check_text(self) -> PostCommentInput:
        object.__setattr__(self, "text", require_text(self.text, "text"))
        return self


class UpdateCommentInput(TaskCommentsInput):
    comment_id: int = Field(gt=0, description="Comment to edit.")
    text: str = Field(description="Replacement comment body.")

    @model_validator(mode="after")
    def _check_text(self) -> UpdateCommentInput:
        object.__setattr__(self, "text", require_text(self.text, "text"))
        return self


class DeleteCommentInput(TaskCommentsInput):
    comment_id: int = Field(gt=0, description="Comment to delete permanently.")
    confirm: bool = Field(default=False, description="Must be true. Deletion is permanent.")

    @model_validator(mode="after")
    def _require_confirmation(self) -> DeleteCommentInput:
        if not self.confirm:
            raise ValueError("delete_comment requires confirm=true")
        return self


@tool(
    name="get_comments",
    description="List the comments on a task, oldest first.",
    input_model=TaskCommentsInput,
)
async def get_comments(context: ToolContext, args: TaskCommentsInput) -> Any:
    payload = await context.client.call(
        api_actions.GET_COMMENTS, page=task_page(args.project_id, args.task_id)
    )
    return as_rows(payload)


@tool(
    name="post_comment",
    description="Add a comment to a task.",
    input_model=PostCommentInput,
)
async def post_comment(context: ToolContext, args: PostCommentInput) -> Any:
    return await context.client.call(
        api_actions.POST_COMMENT,
        page=task_page(args.project_id, args.task_id),
        params={
            "text": args.text,
            "email_user_from": args.author_email,
            "hidden": args.hidden or None,
        },
    )


@tool(
    name="update_comment",
    description="Replace the text of an existing comment.",
    input_model=UpdateCommentInput,
)
async def update_comment(context: ToolContext, args: UpdateCommentInput) -> Any:
    return await context.client.call(
        api_actions.UPDATE_COMMENT,
        page=task_page(args.project_id, args.task_id),
        params={"id_comment": args.comment_id, "text": args.text},
    )


@tool(
    name="delete_comment",
    description=(
        "Permanently delete a comment. Only available when ALLOW_DESTRUCTIVE_OPERATIONS=true, "
        "and requires confirm=true."
    ),
    input_model=DeleteCommentInput,
    destructive=True,
)
async def delete_comment(context: ToolContext, args: DeleteCommentInput) -> Any:
    return await context.client.call(
        api_actions.DELETE_COMMENT,
        page=task_page(args.project_id, args.task_id),
        params={"id_comment": args.comment_id},
    )
