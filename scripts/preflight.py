"""Check the local configuration without contacting the API.

Usage: uv run python scripts/preflight.py
"""

from __future__ import annotations

import sys

from worksection_mcp.preflight import run_preflight

if __name__ == "__main__":
    sys.exit(run_preflight())
