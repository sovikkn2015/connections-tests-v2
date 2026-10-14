"""Structured JSON logger (Rule 17).

The adapter family uses structured JSON for every log line. We keep a
dependency-light implementation here — stdlib only — so pure unit tests don't
need structlog installed. Production images install `structlog` in the
Dockerfile and can swap in :func:`get_structlog_logger` without changing the
call sites (same `info(mapping)` / `warning(mapping)` / `error(mapping)`
shape).
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, Mapping, Protocol


class StructuredLogger(Protocol):
    def info(self, event_dict: Mapping[str, Any]) -> None: ...
    def warning(self, event_dict: Mapping[str, Any]) -> None: ...
    def error(self, event_dict: Mapping[str, Any]) -> None: ...


class _StdlibJsonLogger:
    """Minimal JSON-line logger wrapping ``logging.Logger``.

    Writes to stderr by default so stdout is reserved for audit events. Each
    call serialises the event dict as a compact JSON object.
    """

    def __init__(
        self,
        name: str,
        *,
        adapter_name: str,
        vendor: str,
        level: int = logging.INFO,
        stream: Any = None,
    ) -> None:
        self._adapter_name = adapter_name
        self._vendor = vendor
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)
        # Avoid duplicate handlers if get_logger() is called repeatedly.
        if not self._logger.handlers:
            handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
            self._logger.propagate = False

    def _emit(self, level: int, event_dict: Mapping[str, Any]) -> None:
        payload: dict[str, Any] = {
            "adapter_name": self._adapter_name,
            "vendor": self._vendor,
            "level": logging.getLevelName(level).lower(),
        }
        for k, v in event_dict.items():
            payload[k] = v
        try:
            line = json.dumps(payload, separators=(",", ":"), default=str)
        except Exception:  # pragma: no cover — JSON-safe fallback
            line = json.dumps(
                {"adapter_name": self._adapter_name, "vendor": self._vendor,
                 "level": "error", "event": "log_serialization_failed"}
            )
        self._logger.log(level, line)

    def info(self, event_dict: Mapping[str, Any]) -> None:
        self._emit(logging.INFO, event_dict)

    def warning(self, event_dict: Mapping[str, Any]) -> None:
        self._emit(logging.WARNING, event_dict)

    def error(self, event_dict: Mapping[str, Any]) -> None:
        self._emit(logging.ERROR, event_dict)


def get_logger(
    *,
    adapter_name: str,
    vendor: str,
    level: str = "info",
    stream: Any = None,
) -> StructuredLogger:
    """Return a stdlib-backed structured logger.

    In production, operators can replace this call with a structlog-backed
    version — the Protocol shape is stable.
    """
    numeric = getattr(logging, level.upper(), logging.INFO)
    return _StdlibJsonLogger(
        name=f"007.{adapter_name}",
        adapter_name=adapter_name,
        vendor=vendor,
        level=numeric,
        stream=stream,
    )
