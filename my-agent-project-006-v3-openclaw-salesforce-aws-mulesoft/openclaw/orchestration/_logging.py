"""Structured JSON logging with correlation_id binding.

Uses structlog if available; otherwise falls back to stdlib logging with a
JSON formatter. Every log line carries `correlation_id`, `session_id`,
`persona`, and `agent_id` when available. MNPI scrubbing is the caller's
responsibility — this module never scrubs silently.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, Optional


try:
    import structlog  # type: ignore

    _HAS_STRUCTLOG = True
except ImportError:  # pragma: no cover - structlog optional at test time
    _HAS_STRUCTLOG = False


class _JSONFormatter(logging.Formatter):
    """Stdlib fallback JSON formatter used when structlog is unavailable."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
        }
        for attr in ("correlation_id", "session_id", "persona", "agent_id"):
            val = getattr(record, attr, None)
            if val is not None:
                payload[attr] = val
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_configured = False


def configure_logging(level: Optional[str] = None) -> None:
    """Idempotent: call once at process start."""
    global _configured
    if _configured:
        return
    level_str = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    log_level = getattr(logging, level_str, logging.INFO)

    if _HAS_STRUCTLOG:
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
        )
    else:
        root = logging.getLogger()
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JSONFormatter())
        root.handlers = [handler]
        root.setLevel(log_level)

    _configured = True


def get_logger(name: str = "openclaw") -> Any:
    """Return a logger instance (structlog if available, else stdlib)."""
    configure_logging()
    if _HAS_STRUCTLOG:
        return structlog.get_logger(name)
    return logging.getLogger(name)


def bind(logger: Any, **kwargs: Any) -> Any:
    """Uniform bind(): works with structlog and stdlib loggers."""
    if _HAS_STRUCTLOG and hasattr(logger, "bind"):
        return logger.bind(**kwargs)
    return logging.LoggerAdapter(logger, kwargs)
