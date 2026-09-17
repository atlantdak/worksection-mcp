"""Importing this package registers every tool with the registry.

Each module is imported for its decorator side effects; keep this list in
sync when adding a module, and keep the imports alphabetical.
"""

from __future__ import annotations

from worksection_mcp.tools import (
    activity,
    auth_tools,
    comments,
    costs,
    files,
    members,
    projects,
    reports,
    search,
    subtasks,
    system,
    tags,
    tasks,
    timers,
)

__all__ = [
    "activity",
    "auth_tools",
    "comments",
    "costs",
    "files",
    "members",
    "projects",
    "reports",
    "search",
    "subtasks",
    "system",
    "tags",
    "tasks",
    "timers",
]
