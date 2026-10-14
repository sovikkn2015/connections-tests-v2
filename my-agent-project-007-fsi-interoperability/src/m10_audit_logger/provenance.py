"""
M10 Audit Logger — Provenance chain (ARCH-06 Gap 2).

Per-stage SHA-256 hash chain for liability attribution. Each stage's
hash binds to the previous stage's hash, producing an immutable linked
record of data lineage across the 007 trust pipeline.

Stage hash formula:
    sha256(previous_hash + "|" + stage + "|" + module + "|"
           + sha256(canonical_json(payload)) + "|" + timestamp.isoformat())

The empty string is used as ``previous_hash`` for the first stage.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any

from m3_schema_registry import ProvenanceStage

from m10_audit_logger.logger import _canonical_json

_MODULE_PATTERN = re.compile(r"^m(1[0-3]|[1-9])$")


def _stage_hash(
    *,
    previous_hash: str,
    stage: str,
    module: str,
    payload_hash: str,
    timestamp: datetime,
) -> str:
    """Compute the SHA-256 hash for a single provenance stage.

    Note: takes ``payload_hash`` (pre-computed) rather than the raw
    payload so ``verify`` can rebuild the outer hash without
    re-serialising the payload.
    """
    components = "|".join(
        [
            previous_hash or "",
            stage,
            module,
            payload_hash,
            timestamp.isoformat(),
        ]
    )
    return hashlib.sha256(components.encode("utf-8")).hexdigest()


def _compute_payload_hash(payload: Any) -> str:
    """SHA-256 of canonical-JSON-encoded payload."""
    return hashlib.sha256(
        _canonical_json(payload).encode("utf-8")
    ).hexdigest()


class ProvenanceChainBuilder:
    """Per-stage SHA-256 chain for liability attribution (Gap 2).

    NOT thread-safe. Callers serialize per-trace.

    Typical usage:
        builder = ProvenanceChainBuilder()
        builder.append(stage="m1.verify", module="m1",
                       payload={...}, timestamp=utc_now)
        builder.append(stage="m2.authority", module="m2",
                       payload={...}, timestamp=utc_now)
        entry = AuditEntry(..., provenance_chain=builder.chain())
    """

    def __init__(self) -> None:
        self._stages: list[ProvenanceStage] = []
        # Retained payload hashes parallel to _stages — same length,
        # same order. Enables verify() to recompute the outer hash
        # without retaining raw payloads.
        self._payload_hashes: list[str] = []

    def append(
        self,
        *,
        stage: str,
        module: str,
        payload: Any,
        timestamp: datetime,
    ) -> ProvenanceStage:
        """Append a new stage, linking to the previous stage's hash.

        Args:
            stage: Non-empty stage name (e.g., "m1.verify").
            module: One of m1..m13 (validated by regex).
            payload: Arbitrary JSON-serializable payload for this stage.
            timestamp: Timezone-aware datetime (naive raises ValueError).

        Raises:
            ValueError: on any input validation failure.
        """
        if not isinstance(stage, str) or not stage:
            raise ValueError("stage must be a non-empty string")
        if not isinstance(module, str) or not module:
            raise ValueError("module must be a non-empty string")
        if not _MODULE_PATTERN.fullmatch(module):
            raise ValueError(
                f"module must match m1..m13 pattern, got {module!r}"
            )
        if not isinstance(timestamp, datetime):
            raise ValueError("timestamp must be a datetime")
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")

        previous_hash = self._stages[-1].hash if self._stages else ""
        payload_hash = _compute_payload_hash(payload)
        stage_hash = _stage_hash(
            previous_hash=previous_hash,
            stage=stage,
            module=module,
            payload_hash=payload_hash,
            timestamp=timestamp,
        )

        provenance_stage = ProvenanceStage(
            stage=stage,
            module=module,
            hash=stage_hash,
            timestamp=timestamp,
        )
        self._stages.append(provenance_stage)
        self._payload_hashes.append(payload_hash)
        return provenance_stage

    def chain(self) -> list[ProvenanceStage]:
        """Return a shallow copy of the current chain."""
        return list(self._stages)

    def head_hash(self) -> str:
        """Return the last stage's hash, or "" if the chain is empty."""
        return self._stages[-1].hash if self._stages else ""

    def verify(self) -> bool:
        """Recompute every stage hash and verify the full chain.

        Uses retained payload hashes (captured at ``append`` time) to
        rebuild each stage's outer hash. Tampering with ``stage``,
        ``module``, ``hash``, or ``timestamp`` on any stage causes
        recomputation to diverge and ``verify`` returns False.

        Returns False if the internal retained-hash list has drifted
        from the stage list (shouldn't happen through normal use).
        """
        if len(self._stages) != len(self._payload_hashes):
            return False

        previous_hash = ""
        for stage_entry, payload_hash in zip(
            self._stages, self._payload_hashes
        ):
            if stage_entry.hash == "":
                return False
            expected = _stage_hash(
                previous_hash=previous_hash,
                stage=stage_entry.stage,
                module=stage_entry.module,
                payload_hash=payload_hash,
                timestamp=stage_entry.timestamp,
            )
            if expected != stage_entry.hash:
                return False
            previous_hash = stage_entry.hash
        return True
