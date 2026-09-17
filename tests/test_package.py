from __future__ import annotations

import worksection_mcp


def test_version_is_exposed() -> None:
    assert isinstance(worksection_mcp.__version__, str)
    assert worksection_mcp.__version__.count(".") == 2
