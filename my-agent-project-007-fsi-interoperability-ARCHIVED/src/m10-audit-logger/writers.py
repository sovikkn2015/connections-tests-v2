"""
M10 Tier-specific writers for the three-tier audit architecture.

Tier 1: LangfuseWriter — operational observability (90-day retention)
Tier 2: WormWriter — S3 Object Lock WORM (6-year, SEC 17a-4, Compliance mode)
Tier 3: CrmWriter — business-accessible (Salesforce IR_Audit_Log__c)

Each writer implements a common protocol. Production backends are injected
via dependency injection — no credentials in code (Rule 9).

For testing/dev, writers operate against in-memory stores.
"""

from __future__ import annotations

import calendar
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from m10_audit_logger.models import AuditEntry, TierWriteResult

logger = logging.getLogger("m10.writers")


# ── Abstract Writer Protocol ─────────────────────────────────────


class AuditTierWriter(ABC):
    """Base protocol for all tier writers."""

    @abstractmethod
    async def write(self, entry: AuditEntry) -> TierWriteResult:
        """Write audit entry to this tier. Returns success/failure."""
        ...

    @abstractmethod
    async def query_by_trace_id(self, trace_id: str) -> list[dict[str, Any]]:
        """Query entries by trace_id from this tier."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if this tier is reachable and writable."""
        ...


# ── Tier 1: Langfuse (Operational Observability) ────────────────


class LangfuseWriter(AuditTierWriter):
    """
    Writes audit entries to Langfuse for LLM observability.
    90-day retention. NOT the regulatory record.

    Production: uses langfuse SDK (client injected, credentials from Vault).
    Dev/test: in-memory store.
    """

    def __init__(self, client: Optional[Any] = None) -> None:
        self._client = client  # langfuse.Langfuse instance (injected)
        self._store: dict[str, list[dict[str, Any]]] = {}  # in-memory for dev

    async def write(self, entry: AuditEntry) -> TierWriteResult:
        try:
            trace_url: Optional[str] = None
            if self._client is not None:
                # Production: write to Langfuse via SDK
                trace = self._client.trace(
                    id=entry.trace_id,
                    name=f"audit:{entry.action}",
                    metadata={
                        "canonical_id": entry.canonical_id,
                        "module": entry.module.value,
                        "decision": entry.decision.value,
                        "sha256_integrity": entry.sha256_integrity,
                        "firm_id": entry.firm_id,
                    },
                )
                trace_url = getattr(trace, "url", None)
            else:
                # Dev/test: in-memory
                record = entry.model_dump(mode="json")
                self._store.setdefault(entry.trace_id, []).append(record)
                trace_url = f"http://langfuse.local/trace/{entry.trace_id}"

            return TierWriteResult(
                tier="langfuse",
                success=True,
                record_id=trace_url or entry.trace_id,
            )
        except Exception as exc:
            logger.error("Langfuse write failed: %s", exc)
            return TierWriteResult(
                tier="langfuse", success=False, error=str(exc),
            )

    async def query_by_trace_id(self, trace_id: str) -> list[dict[str, Any]]:
        return self._store.get(trace_id, [])

    async def health_check(self) -> bool:
        if self._client is not None:
            try:
                self._client.auth_check()
                return True
            except Exception:
                return False
        return True  # in-memory always healthy


# ── Tier 2: S3 Object Lock WORM (Regulatory Record of Truth) ───


class WormWriter(AuditTierWriter):
    """
    Writes audit entries to S3 Object Lock in Compliance mode.
    6-year retention minimum per SEC Rule 17a-4.
    SHA-256 integrity hash included in every record.
    Object Lock configuration is immutable once set (Rule 4).

    Production: uses boto3 S3 client (injected, credentials from Vault).
    Dev/test: in-memory store.
    """

    def __init__(
        self,
        s3_client: Optional[Any] = None,
        bucket: str = "007-worm-audit",
        retention_years: int = 6,
    ) -> None:
        self._s3 = s3_client  # boto3 S3 client (injected)
        self._bucket = bucket
        self._retention_years = retention_years
        self._store: dict[str, dict[str, Any]] = {}  # in-memory for dev

    def _build_key(self, entry: AuditEntry) -> str:
        """S3 key pattern: {firm_id}/audit/{year}/{month}/{canonical_id}.json"""
        ts = entry.timestamp
        return (
            f"{entry.firm_id}/audit/{ts.year}/{ts.month:02d}"
            f"/{entry.canonical_id}.json"
        )

    async def write(self, entry: AuditEntry) -> TierWriteResult:
        key = self._build_key(entry)
        body = entry.model_dump_json(indent=None)

        try:
            if self._s3 is not None:
                # Production: S3 Object Lock Compliance mode
                # BLOCKER 6 fix: safe leap year handling.
                # Feb 29 + 6 years may land on a non-leap year.
                # Clamp day to last valid day of the target month.
                target_year = entry.timestamp.year + self._retention_years
                target_month = entry.timestamp.month
                max_day = calendar.monthrange(target_year, target_month)[1]
                target_day = min(entry.timestamp.day, max_day)
                retain_until = datetime(
                    target_year,
                    target_month,
                    target_day,
                    tzinfo=timezone.utc,
                )
                self._s3.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=body.encode("utf-8"),
                    ContentType="application/json",
                    ObjectLockMode="COMPLIANCE",
                    ObjectLockRetainUntilDate=retain_until,
                    ChecksumAlgorithm="SHA256",
                )
            else:
                # Dev/test: in-memory
                self._store[key] = json.loads(body)

            entry.worm_record_id = f"s3://{self._bucket}/{key}"
            return TierWriteResult(
                tier="worm",
                success=True,
                record_id=entry.worm_record_id,
            )
        except Exception as exc:
            logger.error("WORM write failed: %s", exc)
            return TierWriteResult(
                tier="worm", success=False, error=str(exc),
            )

    async def query_by_trace_id(self, trace_id: str) -> list[dict[str, Any]]:
        return [
            v for v in self._store.values()
            if v.get("trace_id") == trace_id
        ]

    async def health_check(self) -> bool:
        if self._s3 is not None:
            try:
                self._s3.head_bucket(Bucket=self._bucket)
                return True
            except Exception:
                return False
        return True


# ── Tier 3: CRM (Business-Accessible Audit Trail) ──────────────


class CrmWriter(AuditTierWriter):
    """
    Writes audit entries to CRM (Salesforce IR_Audit_Log__c or equivalent).
    Business-accessible for advisors and compliance officers.
    NOT the regulatory record — that's WORM.

    Production: uses httpx client for Salesforce REST API (injected).
    Dev/test: in-memory store.
    """

    def __init__(self, client: Optional[Any] = None) -> None:
        self._client = client  # httpx.AsyncClient for SF REST (injected)
        self._store: dict[str, list[dict[str, Any]]] = {}  # in-memory

    async def write(self, entry: AuditEntry) -> TierWriteResult:
        try:
            crm_id: str
            if self._client is not None:
                # Production: POST to Salesforce REST API
                payload = {
                    "Canonical_ID__c": entry.canonical_id,
                    "Trace_ID__c": entry.trace_id,
                    "Actor_ID__c": entry.actor_id,
                    "Action__c": entry.action,
                    "Module__c": entry.module.value,
                    "Decision__c": entry.decision.value,
                    "SHA256_Integrity__c": entry.sha256_integrity,
                    "WORM_Record_ID__c": entry.worm_record_id,
                    "Firm_ID__c": entry.firm_id,
                    "Timestamp__c": entry.timestamp.isoformat(),
                }
                resp = await self._client.post(
                    "/services/data/v62.0/sobjects/IR_Audit_Log__c",
                    json=payload,
                )
                resp.raise_for_status()
                crm_id = resp.json().get("id", str(uuid4()))
            else:
                # Dev/test: in-memory
                crm_id = f"a0B{uuid4().hex[:15]}"
                record = entry.model_dump(mode="json")
                record["crm_record_id"] = crm_id
                self._store.setdefault(entry.trace_id, []).append(record)

            entry.crm_record_id = crm_id
            return TierWriteResult(
                tier="crm", success=True, record_id=crm_id,
            )
        except Exception as exc:
            logger.error("CRM write failed: %s", exc)
            return TierWriteResult(
                tier="crm", success=False, error=str(exc),
            )

    async def query_by_trace_id(self, trace_id: str) -> list[dict[str, Any]]:
        return self._store.get(trace_id, [])

    async def health_check(self) -> bool:
        if self._client is not None:
            try:
                resp = await self._client.get("/services/data/v62.0/limits")
                return resp.status_code == 200
            except Exception:
                return False
        return True
