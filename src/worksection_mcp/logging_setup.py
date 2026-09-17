"""Logging that writes to stderr and scrubs known secrets as a safety net.

Redaction is a backstop, not a licence: no call site may pass a settings
object, credential, or token to a logging call.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterable

from worksection_mcp.config import Settings

REDACTED = "***redacted***"
MIN_SECRET_LENGTH = 6
LOGGER_NAME = "worksection_mcp"


class SecretRedactingFilter(logging.Filter):
    """Replace known secret values anywhere in a record's message or args."""

    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__()
        self._secrets: set[str] = set()
        for secret in secrets:
            self.add_secret(secret)

    def add_secret(self, value: str) -> None:
        if value and len(value) >= MIN_SECRET_LENGTH:
            self._secrets.add(value)

    def _scrub(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, REDACTED)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._secrets:
            return True
        if isinstance(record.msg, str):
            record.msg = self._scrub(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    key: self._scrub(value) if isinstance(value, str) else value
                    for key, value in record.args.items()
                }
            else:
                record.args = tuple(
                    self._scrub(arg) if isinstance(arg, str) else arg for arg in record.args
                )
        return True


def _collect_secrets(settings: Settings) -> list[str]:
    values: list[str] = []
    for secret in (settings.worksection_api_key, settings.oauth_client_secret, settings.fernet_key):
        if secret is not None:
            values.append(secret.get_secret_value())
    return values


def configure_logging(settings: Settings) -> logging.Logger:
    """Attach a single stderr handler with redaction to the package logger."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(settings.log_level)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    for existing in list(logger.filters):
        logger.removeFilter(existing)

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s %(message)s"))
    logger.addHandler(handler)

    redactor = SecretRedactingFilter(_collect_secrets(settings))
    logger.addFilter(redactor)
    handler.addFilter(redactor)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child of the package logger, e.g. ``get_logger("http.client")``."""
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
