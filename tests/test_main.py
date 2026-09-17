from __future__ import annotations

import pytest

from worksection_mcp.__main__ import main
from worksection_mcp.errors import ConfigurationError


def test_main_returns_zero_on_a_clean_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    import worksection_mcp.__main__ as main_module

    monkeypatch.setattr(main_module, "serve", lambda: None)
    assert main() == 0


def test_main_reports_configuration_errors_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import worksection_mcp.__main__ as main_module

    def _raise() -> None:
        raise ConfigurationError("missing WORKSECTION_API_KEY")

    monkeypatch.setattr(main_module, "serve", _raise)
    assert main() == 1
    assert "missing WORKSECTION_API_KEY" in capsys.readouterr().err


def test_main_maps_keyboard_interrupt_to_the_conventional_signal_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import worksection_mcp.__main__ as main_module

    def _raise() -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(main_module, "serve", _raise)
    assert main() == 130
