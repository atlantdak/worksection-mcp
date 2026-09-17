"""Console entry point: ``worksection-mcp`` or ``python -m worksection_mcp``."""

from __future__ import annotations

import sys

from worksection_mcp.errors import ConfigurationError
from worksection_mcp.server import serve


def main() -> int:
    try:
        serve()
    except ConfigurationError as exc:
        print(exc.message, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised only via `python -m`, not import
    sys.exit(main())
