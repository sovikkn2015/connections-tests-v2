"""
M10 — Audit Logger (Three-Tier Regulatory Audit System)

The regulatory backbone of Project 007. Every agent decision, policy
evaluation, and data access is recorded here for 6+ years.

Three-tier write architecture (ALL three required per Rule 7):
  Tier 1: Langfuse — operational observability, LLM tracing (90-day)
  Tier 2: S3 Object Lock WORM — regulatory record of truth (6-year, SEC 17a-4)
  Tier 3: CRM — business-accessible audit trail (Salesforce IR_Audit_Log__c)

Fail-closed: if ANY tier write fails, the entire request fails (Rule 2).
Dead letter queue: failed writes queued for retry, but request still fails (Rule 8).
SHA-256 integrity: every entry includes sha256_integrity hash (Rule 3).
Provenance chain: per-stage SHA-256 hash chain for liability (Rule 13 / ARCH-06 Gap 2).

Zero credentials in code — all secrets from Vault / Secrets Manager (Rule 9).
"""

from m10_audit_logger.models import AuditEntry, ProvenanceStage, TierWriteResult
from m10_audit_logger.audit_service import AuditService
from m10_audit_logger.writers import LangfuseWriter, WormWriter, CrmWriter

__all__ = [
    "AuditEntry",
    "ProvenanceStage",
    "TierWriteResult",
    "AuditService",
    "LangfuseWriter",
    "WormWriter",
    "CrmWriter",
]
