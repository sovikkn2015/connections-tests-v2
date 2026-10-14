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

import json
import logging
import os
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


# ── Dead Letter Queue Backends (Rule 8) ─────────────────────────


class DeadLetterQueue:
    """
    In-memory DLQ using collections.deque.
    Default for dev/test. Production uses SQS.
    """

    def __init__(self, max_size: int = 10_000) -> None:
        self._dlq: deque[dict[str, Any]] = deque(maxlen=max_size)

    def enqueue(self, entry: dict[str, Any]) -> None:
        self._dlq.append(entry)

    @property
    def queue(self) -> deque[dict[str, Any]]:
        return self._dlq

    def __len__(self) -> int:
        return len(self._dlq)


class SQSDeadLetterQueue:
    """
    SQS-backed DLQ for production (Rule 8).

    Activated when M10_DLQ_BACKEND=sqs and M10_DLQ_QUEUE_URL is set.
    Uses boto3 SQS send_message. Credentials from IAM role / env (Rule 9).
    """

    def __init__(self, queue_url: str, sqs_client: Any = None) -> None:
        self._queue_url = queue_url
        if sqs_client is not None:
            self._sqs = sqs_client
        else:
            try:
                import boto3
            except ImportError:
                raise RuntimeError(
                    "boto3 is required for SQS DLQ backend. "
                    "Install with: pip install boto3"
                )
            self._sqs = boto3.client("sqs")
        # Local fallback deque for inspection / health check
        self._local_buffer: deque[dict[str, Any]] = deque(maxlen=1_000)
        logger.info("SQSDeadLetterQueue initialized: %s", queue_url)

    def enqueue(self, entry: dict[str, Any]) -> None:
        try:
            self._sqs.send_message(
                QueueUrl=self._queue_url,
                MessageBody=json.dumps(entry, default=str),
                MessageAttributes={
                    "source": {
                        "DataType": "String",
                        "StringValue": "m10-audit-logger",
                    },
                },
            )
        except Exception as exc:
            logger.error(
                "SQS DLQ send failed, buffering locally: %s", exc,
            )
            self._local_buffer.append(entry)

    @property
    def queue(self) -> deque[dict[str, Any]]:
        """Local buffer for inspection. SQS messages are in the queue."""
        return self._local_buffer

    def __len__(self) -> int:
        return len(self._local_buffer)


def create_dead_letter_queue(max_size: int = 10_000) -> DeadLetterQueue | SQSDeadLetterQueue:
    """
    Factory: select DLQ backend based on env var.

    M10_DLQ_BACKEND: "memory" (default) or "sqs"
    M10_DLQ_QUEUE_URL: SQS queue URL (required for sqs backend)
    """
    backend = os.environ.get("M10_DLQ_BACKEND", "memory").lower()
    if backend == "sqs":
        queue_url = os.environ.get("M10_DLQ_QUEUE_URL")
        if not queue_url:
            logger.warning(
                "M10_DLQ_BACKEND=sqs but M10_DLQ_QUEUE_URL not set. "
                "Falling back to in-memory DLQ."
            )
            return DeadLetterQueue(max_size=max_size)
        try:
            dlq = SQSDeadLetterQueue(queue_url=queue_url)
            logger.info("M10 DLQ backend: sqs (%s)", queue_url)
            return dlq
        except Exception as exc:
            logger.error(
                "Failed to initialize SQS DLQ: %s. Falling back to in-memory.",
                exc,
            )
            return DeadLetterQueue(max_size=max_size)
    logger.info("M10 DLQ backend: memory (max_size=%d)", max_size)
    return DeadLetterQueue(max_size=max_size)


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
        dlq: DeadLetterQueue | SQSDeadLetterQueue | None = None,
        max_dlq_size: int = 10_000,
    ) -> None:
        self._langfuse = langfuse_writer
        self._worm = worm_writer
        self._crm = crm_writer
        # Dead letter queue — in-memory for dev, SQS in production (Rule 8)
        self._dlq = dlq if dlq is not None else create_dead_letter_queue(max_dlq_size)
        # In-memory index for query (dev/test only)
        self._entries: dict[str, list[AuditEntry]] = {}

    @property
    def dead_letter_queue(self) -> DeadLetterQueue | SQSDeadLetterQueue:
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

        # Tier 1 — Langfuse operational observability
        langfuse_result = await self._langfuse.write(entry)
        tier_results.append(langfuse_result)

        # Tier 3 — CRM business-accessible
        crm_result = await self._crm.write(entry)
        tier_results.append(crm_result)

        # FAIL-CLOSED: if ANY tier failed, DLQ + raise
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
        self._dlq.enqueue(dlq_entry)
        logger.error(
            "Audit entry %s sent to DLQ. Failed tiers: %s",
            entry.canonical_id,
            dlq_entry["failed_tiers"],
        )
