from __future__ import annotations

import logging
import sys

import pytest

from worksection_mcp.config import load_settings
from worksection_mcp.logging_setup import (
    REDACTED,
    SecretRedactingFilter,
    configure_logging,
    get_logger,
)


def _record(message: str, *args: object) -> logging.LogRecord:
    return logging.LogRecord("t", logging.INFO, __file__, 1, message, args, None)


def test_filter_replaces_secret_in_message() -> None:
    log_filter = SecretRedactingFilter(["hunter2"])
    record = _record("token is hunter2")
    assert log_filter.filter(record) is True
    assert record.getMessage() == f"token is {REDACTED}"


def test_filter_replaces_secret_in_args() -> None:
    log_filter = SecretRedactingFilter(["hunter2"])
    record = _record("token is %s", "hunter2")
    log_filter.filter(record)
    assert record.getMessage() == f"token is {REDACTED}"


def test_filter_ignores_empty_and_short_secrets() -> None:
    log_filter = SecretRedactingFilter(["", "ab"])
    record = _record("nothing to hide here")
    log_filter.filter(record)
    assert record.getMessage() == "nothing to hide here"


def test_add_secret_is_applied_to_later_records() -> None:
    log_filter = SecretRedactingFilter([])
    log_filter.add_secret("later-secret")
    record = _record("value later-secret")
    log_filter.filter(record)
    assert "later-secret" not in record.getMessage()


def test_configure_logging_seeds_the_api_key_and_writes_to_stderr(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = load_settings(
        auth_mode="admin_key", worksection_account="acme", worksection_api_key="top-secret-value"
    )
    logger = configure_logging(settings)
    assert logger.name == "worksection_mcp"
    assert all(
        getattr(handler, "stream", None) is sys.stderr
        for handler in logger.handlers
        if isinstance(handler, logging.StreamHandler)
    )
    record = _record("leaking top-secret-value")
    for log_filter in logger.filters:
        assert isinstance(log_filter, logging.Filter)
        log_filter.filter(record)
    assert "top-secret-value" not in record.getMessage()


def test_get_logger_returns_a_package_child() -> None:
    assert get_logger("http.client").name == "worksection_mcp.http.client"
