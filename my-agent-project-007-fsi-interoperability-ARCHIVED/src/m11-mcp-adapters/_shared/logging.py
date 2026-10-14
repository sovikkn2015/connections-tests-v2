"""
Structured JSON logging for M11 MCP adapters (Rule 17).
Uses structlog. No print() statements.
Fields: timestamp, level, adapter_name, vendor, tool_name, request_id, duration_ms.
"""

from __future__ import annotations

import structlog


def get_logger(adapter_name: str, vendor: str) -> structlog.stdlib.BoundLogger:
    """Return a structured logger bound with adapter metadata."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger(adapter_name=adapter_name, vendor=vendor)
