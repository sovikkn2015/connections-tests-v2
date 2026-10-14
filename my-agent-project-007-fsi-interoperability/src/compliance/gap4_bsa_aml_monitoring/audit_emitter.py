"""
Gap 4 — M10 AuditEmitter.

Builds and writes an AuditEntry for every BsaAmlAlert via the real
M10 AuditLogger. Preserves anti-tipping-off invariants by using a
uniform action string across CTR/SAR alerts (R7.3).

See .kiro/specs/gap4-bsa-aml-monitoring.md R7.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from m10_audit_logger import AuditLogger, AuditWriteError
from m3_schema_registry import AuditEntry

from compliance.gap4_bsa_aml_monitoring.models import (
    BsaAmlAlert,
    CashTransaction,
)


# =============================================================================
# Exceptions
# =============================================================================


class AlertEmitFailed(Exception):
    """Raised when the M10 audit write fails. reason is one of:
    `audit_write_failed`, `invalid_inputs`.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


_VALID_REASONS: frozenset[str] = frozenset(
    {"audit_write_failed", "invalid_inputs"}
)


# =============================================================================
# AuditEmitter (spec R7)
# =============================================================================


_POLICY_BUNDLE_VERSION: str = "bsa-aml/1.0.0"


class AuditEmitter:
    """Emits one AuditEntry per BsaAmlAlert via the M10 AuditLogger.

    Anti-tipping-off invariants (R7.3):
      - action string is ALWAYS "bsa_aml.alert_emitted", regardless
        of alert_type. Log observers cannot tell CTR from SAR from
        the action alone.
      - target_type is ALWAYS "cash_transaction" — never
        "sar_filing".
      - reason is alert.reason_code (frozen vocab, no free-form text).
    """

    ACTION: str = "bsa_aml.alert_emitted"
    TARGET_TYPE: str = "cash_transaction"

    def __init__(self, *, audit: AuditLogger, firm_id: str) -> None:
        if not isinstance(audit, AuditLogger):
            raise TypeError("audit must be AuditLogger")
        if not isinstance(firm_id, str) or not firm_id:
            raise ValueError("firm_id must be non-empty string")
        self._audit = audit
        self._firm_id = firm_id

    def emit(
        self,
        *,
        alert: BsaAmlAlert,
        actor_id: str,
        cash_txn: CashTransaction,
        canonical_id: Optional[UUID] = None,
    ) -> AuditEntry:
        """Build an AuditEntry and write through M10.

        Raises AlertEmitFailed("audit_write_failed") if M10 raises.
        Raises AlertEmitFailed("invalid_inputs") on type errors.
        """
        if not isinstance(alert, BsaAmlAlert):
            raise AlertEmitFailed("invalid_inputs")
        if not isinstance(cash_txn, CashTransaction):
            raise AlertEmitFailed("invalid_inputs")
        if not isinstance(actor_id, str) or not actor_id:
            raise AlertEmitFailed("invalid_inputs")

        entry = _build_entry(
            alert=alert,
            actor_id=actor_id,
            cash_txn=cash_txn,
            firm_id=self._firm_id,
            canonical_id=canonical_id,
        )

        try:
            sealed = self._audit.write(entry)
        except AuditWriteError:
            # Fail-closed: do NOT silently drop a compliance alert.
            raise AlertEmitFailed("audit_write_failed") from None
        except Exception:
            raise AlertEmitFailed("audit_write_failed") from None

        return sealed


# =============================================================================
# Entry builder (spec R7.2)
# =============================================================================


def _sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _build_entry(
    *,
    alert: BsaAmlAlert,
    actor_id: str,
    cash_txn: CashTransaction,
    firm_id: str,
    canonical_id: Optional[UUID],
) -> AuditEntry:
    """Assemble AuditEntry per spec R7.2. sha256_integrity left as ""
    (M10 attaches on write)."""
    cid = canonical_id if canonical_id is not None else uuid4()
    input_hash = _sha256_hex(cash_txn.model_dump_json())
    output_hash = _sha256_hex(alert.model_dump_json())
    return AuditEntry(
        canonical_id=cid,
        trace_id=cash_txn.trace_id,
        timestamp=alert.detected_at,
        actor_id=actor_id,
        action=AuditEmitter.ACTION,
        module="m10",
        target_type=AuditEmitter.TARGET_TYPE,
        target_id=str(cash_txn.txn_id),
        decision="ESCALATE",
        reason=alert.reason_code,
        input_hash=input_hash,
        output_hash=output_hash,
        policy_bundle_version=_POLICY_BUNDLE_VERSION,
        rule_applied=alert.rule_applied,
        wsp_section=alert.wsp_section,
        data_sources_used=[],
        latency_ms=0,
        archetype=None,
        role=None,
        firm_id=firm_id,
        jurisdiction=None,
        provenance_chain=[],
        worm_record_id=f"bsa-aml/{alert.alert_id}",
        sha256_integrity="",
        retention_years=6,
    )


__all__ = [
    "AuditEmitter",
    "AlertEmitFailed",
    "_VALID_REASONS",
]
