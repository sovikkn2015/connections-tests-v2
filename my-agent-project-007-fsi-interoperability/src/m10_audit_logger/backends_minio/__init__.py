"""
M10 Audit Logger -- MinIO WORM backend package.

Isolated in a sibling package so callers that don't need the MinIO
backend (unit tests, Langfuse-only wiring, the orchestrator itself)
do NOT pay the `minio` SDK import cost. The backend is re-exported
lazily from ``m10_audit_logger`` via PEP 562 ``__getattr__``; see
``m10_audit_logger.__init__``.

Public symbols:
    MinIOWormBackend   -- the AuditBackend(tier="worm") implementation.
    MinIOWormConfigProtocol -- duck-typed config shape consumed by
        the backend constructor (the concrete Pydantic model lives
        in M5 to satisfy Rule 10 module boundaries).
    VaultClient        -- narrow Vault read-only Protocol.
"""

from __future__ import annotations

from m10_audit_logger.backends_minio.minio_worm import (
    MinIOWormBackend,
    MinIOWormConfigProtocol,
    VaultClient,
)

__all__ = [
    "MinIOWormBackend",
    "MinIOWormConfigProtocol",
    "VaultClient",
]
