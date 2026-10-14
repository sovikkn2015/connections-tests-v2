"""
M10 Core Audit Service — write_audit() orchestrates all 3 tiers.

FAIL-CLOSED (Rule 2): If ANY tier write fails, the entire request fails.
DEAD LETTER QUEUE (Rule 8): Failed writes go to DLQ for retry/investigation.
  But the originating request still fails immediately.
SHA-256 INTEGRITY (Rule 3): Every entry includes sha256_integrity hash.
PROVENANCE CHAIN (Rule 13): Per-stage SHA-256 hash chain preserved.

Zero credentials in code (Rule 9). All backends injected.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

from m10_audit_logger.models import (
    AuditEntry,
    TierWriteResult,
    WriteAuditRequest,
    WriteAuditResponse,
)
from m10_audit_logger.writers import AuditTierWriter

logger = logging.getLogger("m10.service")


class AuditWriteError(Exception):
    """Raised when any tier write fails (fail-closed)."""

    def __init__(self, message: str, tier_results: list[TierWriteResult]) -> None:
        super().__init__(message)
        self.tier_results = tier_results


class AuditService:
    """
    Orchestrates three-tier audit writes with fail-closed semantics.

    Write order: WORM first (regulatory record of truth), then Langfuse,
    then CRM. WORM is written first because it's the immutable record —
    if it fails, nothing else should proceed.

    If ANY tier fails:
      1. Entry goes to dead letter queue (for retry/investigation)
      2. AuditWriteError is raised (originating request fails)
    """

    def __init__(
        self,
        langfuse_writer: AuditTierWriter,
        worm_writer: AuditTierWriter,
        crm_writer: AuditTierWriter,
        max_dlq_size: int = 10_000,
    ) -> None:
        self._langfuse = langfuse_writer
        self._worm = worm_writer
        self._crm = crm_writer
        # Dead letter queue — in-memory for dev, SQS/RabbitMQ in production
        self._dlq: deque[dict[str, Any]] = deque(maxlen=max_dlq_size)
        # In-memory index for query (dev/test only)
        self._entries: dict[str, list[AuditEntry]] = {}

    @property
    def dead_letter_queue(self) -> deque[dict[str, Any]]:
        """Access DLQ for inspection/retry. Production uses SQS."""
        return self._dlq

    async def write_audit(self, request: WriteAuditRequest) -> WriteAuditResponse:
        """
        Write audit entry to all 3 tiers. Fail-closed.

        1. Build AuditEntry from request (SHA-256 computed automatically)
        2. Write to WORM (Tier 2) — regulatory record of truth, first
        3. Write to Langfuse (Tier 1) — operational observability
        4. Write to CRM (Tier 3) — business-accessible
        5. If ANY tier fails: DLQ + raise AuditWriteError
        6. Return success with all tier results
        """
        # Build entry — sha256_integrity computed by model_validator
        entry = AuditEntry(
            trace_id=request.trace_id,
            actor_id=request.actor_id,
            action=request.action,
            module=request.module,
            target_type=request.target_type,
            target_id=request.target_id,
            decision=request.decision,
            reason=request.reason,
            input_hash=request.input_hash,
            output_hash=request.output_hash,
            policy_bundle_version=request.policy_bundle_version,
            rule_applied=request.rule_applied,
            wsp_section=request.wsp_section,
            data_sources_used=request.data_sources_used,
            latency_ms=request.latency_ms,
            archetype=request.archetype,
            role=request.role,
            firm_id=request.firm_id,
            jurisdiction=request.jurisdiction,
            provenance_chain=request.provenance_chain,
            retention_years=request.retention_years,
        )

        tier_results: list[TierWriteResult] = []

        # Tier 2 first — WORM is the regulatory record of truth
        worm_result = await self._worm.write(entry)
        tier_results.append(worm_result)

        # SHORT-CIRCUIT: if WORM fails, do NOT write to other tiers.
        # WORM is the immutable regulatory record — orphaned Langfuse/CRM
        # records without a WORM backing are a compliance liability.
        if not worm_result.success:
            self._enqueue_dlq(entry, tier_results)
            raise AuditWriteError(
                f"Audit write failed on WORM tier. "
                f"Request denied (fail-closed). Entry queued to DLQ.",
                tier_results=tier_results,
            )

        # Tier 1 — Langfuse operational observability
        langfuse_result = await self._langfuse.write(entry)
        tier_results.append(langfuse_result)

        # Tier 3 — CRM business-accessible
        crm_result = await self._crm.write(entry)
        tier_results.append(crm_result)

        # FAIL-CLOSED: if Langfuse or CRM failed, DLQ + raise
        failed = [r for r in tier_results if not r.success]
        if failed:
            self._enqueue_dlq(entry, tier_results)
            failed_tiers = ", ".join(r.tier for r in failed)
            raise AuditWriteError(
                f"Audit write failed on tier(s): {failed_tiers}. "
                f"Request denied (fail-closed). Entry queued to DLQ.",
                tier_results=tier_results,
            )

        # All tiers succeeded — index for query
        self._entries.setdefault(entry.trace_id, []).append(entry)

        return WriteAuditResponse(
            canonical_id=entry.canonical_id,
            sha256_integrity=entry.sha256_integrity,
            tier_results=tier_results,
            worm_record_id=entry.worm_record_id,
        )

    async def query_by_trace_id(self, trace_id: str) -> list[AuditEntry]:
        """Query audit entries by trace_id. Dev: in-memory. Prod: query WORM."""
        return self._entries.get(trace_id, [])

    async def health_check(self) -> dict[str, bool]:
        """Check health of all 3 tiers."""
        return {
            "langfuse": await self._langfuse.health_check(),
            "worm": await self._worm.health_check(),
            "crm": await self._crm.health_check(),
        }

    def _enqueue_dlq(
        self, entry: AuditEntry, results: list[TierWriteResult],
    ) -> None:
        """Send failed audit write to dead letter queue (Rule 8)."""
        dlq_entry = {
            "entry": entry.model_dump(mode="json"),
            "tier_results": [r.model_dump(mode="json") for r in results],
            "failed_tiers": [r.tier for r in results if not r.success],
        }
        self._dlq.append(dlq_entry)
        logger.error(
            "Audit entry %s sent to DLQ. Failed tiers: %s",
            entry.canonical_id,
            dlq_entry["failed_tiers"],
        )
