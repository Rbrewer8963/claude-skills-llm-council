"""Structured logging and an audit trail.

Two concerns, deliberately separated:

* the **application logger** (``atlas``) — operational logs, JSON or text.
* the **audit logger** (``atlas.audit``) — an append-only record of every risk
  calculation served, which is a hard requirement for any system that produces
  numbers people act on. Each audit line is a self-contained JSON object.

Neither pulls in a dependency; both use the standard ``logging`` module.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, Dict

from .config import Config


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Attach any structured fields passed via ``extra={"fields": {...}}``.
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure(config: Config) -> logging.Logger:
    """Idempotently configure application and audit loggers; return the app logger."""
    root = logging.getLogger("atlas")
    root.setLevel(getattr(logging, config.log_level, logging.INFO))
    root.handlers.clear()
    root.propagate = False

    handler = logging.StreamHandler(sys.stdout)
    if config.log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)

    # Audit logger always emits JSON to stdout so a collector can ship it
    # somewhere durable (the app must never be the system of record for audit).
    audit = logging.getLogger("atlas.audit")
    audit.setLevel(logging.INFO)
    audit.handlers.clear()
    audit.propagate = False
    audit_handler = logging.StreamHandler(sys.stdout)
    audit_handler.setFormatter(JsonFormatter())
    audit.addHandler(audit_handler)

    return root


def audit_event(event: str, **fields: Any) -> None:
    """Emit one structured audit record."""
    logging.getLogger("atlas.audit").info(event, extra={"fields": {"event": event, **fields}})
