"""Importing this package registers every tool with the registry.

Each module is imported for its decorator side effects; keep this list in
sync when adding a module, and keep the imports alphabetical.
"""

from __future__ import annotations

from worksection_mcp.tools import comments, projects, subtasks, system, tasks

__all__ = ["comments", "projects", "subtasks", "system", "tasks"]
