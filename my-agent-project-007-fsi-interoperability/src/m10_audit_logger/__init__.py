"""
M10 Audit Logger — Public API.

3-tier audit writes (Langfuse + S3 Object Lock WORM + CRM) with SHA-256
integrity hash, fail-closed semantics, dead letter queue, and per-stage
SHA-256 provenance chain (Gap 2).

Phase 1: library with pluggable Protocol backends. Dev/test uses
InMemoryAuditBackend. Phase 2 swaps in real Langfuse/boto3/Salesforce.

Usage:
    from m10_audit_logger import (
        AuditLogger, InMemoryAuditBackend, ProvenanceChainBuilder,
    )

See .kiro/specs/m10-audit-logger.md for the full contract.
"""

from __future__ import annotations

from m10_audit_logger.backends import (
    AuditBackend,
    AuditDLQ,
    InMemoryAuditBackend,
    InMemoryAuditDLQ,
    VALID_TIERS,
)
from m10_audit_logger.logger import (
    MIN_RETENTION_YEARS,
    VALID_REASONS,
    AuditLogger,
    AuditWriteError,
)
from m10_audit_logger.provenance import ProvenanceChainBuilder

__all__ = [
    # Logger
    "AuditLogger",
    "AuditWriteError",
    "MIN_RETENTION_YEARS",
    "VALID_REASONS",
    # Backends
    "AuditBackend",
    "AuditDLQ",
    "InMemoryAuditBackend",
    "InMemoryAuditDLQ",
    "VALID_TIERS",
    # Provenance (Gap 2)
    "ProvenanceChainBuilder",
]


# -----------------------------------------------------------------------------
# Lazy re-export for the MinIO WORM backend (v0.4.0, Ops Hardening Wave 3).
#
# The backend imports the `minio` SDK eagerly, which would make EVERY
# import of `m10_audit_logger` pay that cost (and fail hard in
# environments that don't ship `minio`). PEP 562 lets us defer the
# import until a caller actually asks for it.
#
# Deliberately NOT adding `MinIOWormBackend` to `__all__` above -- that
# tuple is pinned by the existing public-API unit test. Callers use
# `from m10_audit_logger import MinIOWormBackend` directly, which
# resolves via __getattr__ below. Same precedent as the `app` module
# deferral in DECISION-LOG v0.3.0.
# -----------------------------------------------------------------------------


def __getattr__(name: str):
    if name == "MinIOWormBackend":
        from m10_audit_logger.backends_minio.minio_worm import (
            MinIOWormBackend,
        )
        return MinIOWormBackend
    raise AttributeError(
        f"module 'm10_audit_logger' has no attribute {name!r}"
    )
