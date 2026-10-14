"""
M6 MCP Gateway — canonical JSON + audit entry construction.

Defines the canonical JSON serializer used by M6 for:
- `input_hash` / `output_hash` on AuditEntry.
- Provenance-stage payload hashing (via M10's ProvenanceChainBuilder).
- Gap 6 input text construction for non-BaseModel responses.
- GatewayRequest payload-size measurement.

M6 self-defines this serializer. It does NOT import any M10 private
helper. Tests reconcile via a golden-hex fixture.

See `.kiro/specs/m6-mcp-gateway.md` section R12.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel

from m1_identity import AidClaims
from m2_m4_policy_engine import PolicyDecision
from m3_schema_registry import AuditEntry, ProvenanceStage
from compliance.gap2_liability_provenance import ErrorCategory


# =============================================================================
# Canonical JSON (spec R12).
# =============================================================================


def _json_default(v: Any) -> Any:
    """Fallback serializer for JSON-uncoercible Python values.

    Decimal -> str(v) preserves trailing-zero precision (AC-R12-2).
    NEVER convert Decimal to float.
    """
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, Enum):
        return v.value
    if isinstance(v, BaseModel):
        return v.model_dump(mode="json")
    raise TypeError(f"not serializable: {type(v).__name__}")


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, compact separators, UTF-8."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )


def canonical_text(obj: Any) -> str:
    """Stable text for Gap 6 leakage-scan input.

    BaseModel -> model_dump_json().
    dict/list -> canonical_json(obj).
    str       -> obj.
    None      -> "null".
    other     -> TypeError.
    """
    if isinstance(obj, str):
        return obj
    if isinstance(obj, BaseModel):
        return obj.model_dump_json()
    if isinstance(obj, (dict, list)):
        return canonical_json(obj)
    if obj is None:
        return "null"
    raise TypeError(
        f"canonical_text: unsupported type {type(obj).__name__}"
    )


def h(obj: Any) -> str:
    """SHA-256 hex of canonical_json(obj). 64-char lowercase."""
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


# =============================================================================
# Reason -> ErrorCategory (spec R8.1).
# =============================================================================

REASON_TO_ERROR_CATEGORY: dict[str, ErrorCategory] = {
    "invalid_identity": ErrorCategory.policy_evaluation_error,
    "authority_denied": ErrorCategory.policy_evaluation_error,
    "authority_escalated": ErrorCategory.policy_evaluation_error,
    "mnpi_filter_error": ErrorCategory.compliance_rule_error,
    "mnpi_leakage_scan": ErrorCategory.compliance_rule_error,
    "circuit_open": ErrorCategory.source_data_error,
    "rate_limited": ErrorCategory.policy_evaluation_error,
    "vendor_unavailable": ErrorCategory.source_data_error,
    "vendor_error": ErrorCategory.source_data_error,
    "audit_failed": ErrorCategory.compliance_rule_error,
    "invalid_request": ErrorCategory.policy_evaluation_error,
}


WSP_FALLBACK: str = "WSP-M6-1"


# =============================================================================
# AuditEntry builder (spec R7).
# =============================================================================


_REASON_MAX = 200


def _clip(s: Optional[str], n: int = _REASON_MAX) -> Optional[str]:
    if s is None:
        return None
    return s[:n]


def _actor_id_from_claims(claims: AidClaims) -> str:
    payload = f"{claims.sub}:{claims.firm_id}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _actor_id_unverified(token: str) -> str:
    fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    payload = f"unverified:{fingerprint}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_audit_entry(
    *,
    request: Any,
    claims: Optional[AidClaims],
    token: str,
    decision: str,
    reason: str,
    policy_decision: Optional[PolicyDecision],
    input_payload: Any,
    output_payload: Any,
    provenance_chain: list[ProvenanceStage],
    latency_ms: int,
    now: datetime,
    session_id: Optional[str],
) -> AuditEntry:
    """Build a sealed-ready AuditEntry.

    `sha256_integrity` is left as "" for M10 to attach on write.
    """
    if decision not in {"allow", "deny", "escalate"}:
        raise ValueError(f"invalid decision: {decision!r}")
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)

    if claims is not None:
        actor_id = _actor_id_from_claims(claims)
    else:
        actor_id = _actor_id_unverified(token)

    target_type = None
    target_id = None
    if request.target:
        target_type = request.target.get("target_type")
        target_id = request.target.get("target_id")
    if target_id is None and session_id:
        target_id = f"session:{session_id}"

    if policy_decision is not None:
        rule_applied = policy_decision.rule_applied
        wsp_section = policy_decision.wsp_section
    else:
        rule_applied = f"m6/gateway/{reason}"
        wsp_section = WSP_FALLBACK

    archetype = claims.archetype if claims is not None else None
    role = claims.role.value if claims is not None else None
    firm_id = request.firm_id

    entry = AuditEntry(
        canonical_id=uuid4(),
        trace_id=request.trace_id,
        timestamp=now,
        actor_id=actor_id,
        action=request.action,
        module="m6",
        target_type=target_type,
        target_id=target_id,
        decision=decision,
        reason=_clip(reason),
        input_hash=h(input_payload),
        output_hash=h(output_payload),
        policy_bundle_version=None,
        rule_applied=rule_applied,
        wsp_section=wsp_section,
        data_sources_used=[request.mcp_server],
        latency_ms=max(0, int(latency_ms)),
        archetype=archetype,
        role=role,
        firm_id=firm_id,
        jurisdiction=None,
        provenance_chain=list(provenance_chain),
        worm_record_id=request.trace_id,
        sha256_integrity="",
        langfuse_trace_url=None,
        crm_record_id=None,
        retention_years=6,
    )
    return entry


__all__ = [
    "canonical_json",
    "canonical_text",
    "h",
    "REASON_TO_ERROR_CATEGORY",
    "WSP_FALLBACK",
    "build_audit_entry",
]
