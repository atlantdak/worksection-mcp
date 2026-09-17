"""Importing this package registers every tool with the registry.

Each module is imported for its decorator side effects; keep this list in
sync when adding a module, and keep the imports alphabetical.
"""

from __future__ import annotations

from worksection_mcp.tools import projects, system

__all__ = ["projects", "system"]
