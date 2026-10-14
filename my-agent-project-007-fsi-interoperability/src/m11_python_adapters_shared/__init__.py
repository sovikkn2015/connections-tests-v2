"""
M11 Python Adapters — Shared Infrastructure
===========================================

Shared building blocks for the Python half of the M11 polyglot adapter family
(BLPAPI, gRPC, SFTP per Steering Rule 10). Parallels the TypeScript shared SDK
(`@project-007/mcp-sdk`) used by the REST adapters.

This module is deliberately narrow:
* `clock` — deterministic clock abstraction (SystemClock + FakeClock).
* `vendor_session` — abstract base class for a long-lived vendor connection
  (BLPAPI Session, gRPC channel, SFTP client). Subclasses implement
  `open()` / `close()` / `healthy()` and are re-used per pod.
* `audit_emitter` — writes one structured JSON event to stdout per tool call.
  Parallels the TypeScript `emitAudit` callback wiring in the REST family.
* `circuit_breaker` — 3-state breaker (CLOSED / OPEN / HALF_OPEN) ported from
  the TypeScript SDK. Same thresholds, same semantics.
* `rate_limiter` — token-bucket with per-firm scope + per-adapter default.
* `fake_vault_client` — in-memory secrets store for tests.
* `errors` — canonical AdapterError with stable error-code vocabulary.

Rule boundaries enforced here:
* No imports from M6 (gateway), M10 (audit writer), or any other project module
  except `m3_schema_registry` (which itself imports only pydantic). Steering
  Rule 33.
* No vendor SDK imports at this level — each adapter binds its own SDK. Shared
  module stays lightweight so `fastapi`, `structlog`, and `pydantic` are the
  full runtime footprint for in-tree tests.
"""

from __future__ import annotations

from m11_python_adapters_shared.audit_emitter import AuditEmitter, AuditEvent
from m11_python_adapters_shared.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)
from m11_python_adapters_shared.clock import Clock, FakeClock, SystemClock
from m11_python_adapters_shared.errors import (
    ADAPTER_ERROR_CODES,
    AdapterError,
    is_retryable_code,
)
from m11_python_adapters_shared.fake_vault_client import (
    FakeVaultClient,
    SecretsClientProtocol,
    VaultNotFound,
)
from m11_python_adapters_shared.logger import StructuredLogger, get_logger
from m11_python_adapters_shared.mcp_server import (
    HealthStatus,
    ServerInfo,
    ToolDefinition,
    build_app,
)
from m11_python_adapters_shared.rate_limiter import RateLimiter, RateLimitExceeded
from m11_python_adapters_shared.vendor_session import (
    SessionNotOpenError,
    VendorSession,
)

__all__ = [
    # audit
    "AuditEmitter",
    "AuditEvent",
    # breaker
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "CircuitState",
    # clock
    "Clock",
    "FakeClock",
    "SystemClock",
    # errors
    "ADAPTER_ERROR_CODES",
    "AdapterError",
    "is_retryable_code",
    # vault
    "FakeVaultClient",
    "SecretsClientProtocol",
    "VaultNotFound",
    # logger
    "StructuredLogger",
    "get_logger",
    # mcp server
    "HealthStatus",
    "ServerInfo",
    "ToolDefinition",
    "build_app",
    # rate limit
    "RateLimiter",
    "RateLimitExceeded",
    # session
    "SessionNotOpenError",
    "VendorSession",
]
