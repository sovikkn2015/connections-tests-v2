"""
M6 MCP Gateway — TrustAwareGateway orchestrator.

Defines the trust pipeline core:

    M1 identity -> M2 authority -> M4 request MNPI filter -> vendor
    -> M4 response MNPI filter -> Gap 6 leakage scan -> M10 audit

Plus:
- GatewayRequest / GatewayResponse frozen dataclasses.
- GatewayError + VALID_GATEWAY_REASONS frozen vocabulary.

Fail-closed at every stage. See `.kiro/specs/m6-mcp-gateway.md`.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Literal, Mapping, Optional

from pydantic import BaseModel

from m1_identity import AidClaims, IdentityService
from m2_m4_policy_engine import (
    AuthorityPolicy,
    Decision,
    MnpiPolicy,
    PolicyDecision,
    PolicyInput,
)
from m10_audit_logger import AuditLogger, AuditWriteError, ProvenanceChainBuilder
from compliance.gap2_liability_provenance import (
    ErrorAttribution,
    ErrorCategory,
    LiabilityReport,
    WarrantyBoundary,
)
from compliance.gap6_mnpi_leakage_scan import MnpiLeakageScanner, ScanDecision

from m6_mcp_gateway.adapters import VendorAdapter, VendorAdapterError  # noqa: F401
from m6_mcp_gateway.canonicalize import (
    Canonicalizer,
    TranslationError as _CanonicalizeError,
    default_canonicalizer,
)
from m6_mcp_gateway.audit_builder import (
    REASON_TO_ERROR_CATEGORY,
    build_audit_entry,
    canonical_json,
    canonical_text,
    h as _h,
)
from m6_mcp_gateway.policy_adapter import (
    evaluate_authority,
    filter_request,
    filter_response,
    verify_identity,
)
from m6_mcp_gateway.resilience import CircuitBreaker, RateLimiter


# =============================================================================
# GatewayError + frozen vocabulary (spec R2).
# =============================================================================

VALID_GATEWAY_REASONS: frozenset[str] = frozenset(
    {
        "invalid_identity",
        "authority_denied",
        "authority_escalated",
        "mnpi_filter_error",
        "circuit_open",
        "rate_limited",
        "vendor_unavailable",
        "vendor_error",
        "mnpi_leakage_scan",
        "audit_failed",
        "invalid_request",
    }
)


class GatewayError(Exception):
    """Gateway pipeline failure.

    Reason drawn from VALID_GATEWAY_REASONS. str(exc) == exc.reason.
    """

    def __init__(self, reason: str) -> None:
        if reason not in VALID_GATEWAY_REASONS:
            raise ValueError(
                f"reason must be one of VALID_GATEWAY_REASONS, got {reason!r}"
            )
        super().__init__(reason)
        self.reason = reason


# =============================================================================
# GatewayRequest + GatewayResponse (spec R1).
# =============================================================================


_ACTION_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]+)+$")
_TOOL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.\-]*$")
_SERVER_RE = re.compile(r"^[a-z][a-z0-9_\-]*$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

_MAX_TOKEN_LEN = 8192
_MAX_TOOL_LEN = 200
_MAX_SERVER_LEN = 100
_MIN_TRACE_LEN = 8
_MAX_TRACE_LEN = 200
_MAX_FIRM_LEN = 100
_MAX_PAYLOAD_BYTES = 1 * 1024 * 1024  # 1 MiB


@dataclass(frozen=True)
class GatewayRequest:
    """Immutable gateway call input.

    __repr__ redacts token and omits payload (SI-4).
    """

    token: str
    action: str
    tool_name: str
    mcp_server: str
    payload: Any
    trace_id: str
    firm_id: str
    target: Mapping[str, Any]
    context: Mapping[str, Any]
    session_id: Optional[str]
    vendor_adapter: Any  # VendorAdapter-shaped

    def __post_init__(self) -> None:
        # token
        if not isinstance(self.token, str) or not self.token:
            raise ValueError("token must be a non-empty string")
        if len(self.token) > _MAX_TOKEN_LEN:
            raise ValueError("token_too_long")
        # action
        if not isinstance(self.action, str) or not self.action:
            raise ValueError("action must be a non-empty string")
        if not _ACTION_RE.fullmatch(self.action):
            raise ValueError("invalid_action_format")
        # tool_name
        if not isinstance(self.tool_name, str) or not self.tool_name:
            raise ValueError("tool_name must be a non-empty string")
        if len(self.tool_name) > _MAX_TOOL_LEN:
            raise ValueError("tool_name_too_long")
        if not _TOOL_RE.fullmatch(self.tool_name):
            raise ValueError("invalid_tool_name_format")
        # mcp_server
        if not isinstance(self.mcp_server, str) or not self.mcp_server:
            raise ValueError("mcp_server must be a non-empty string")
        if len(self.mcp_server) > _MAX_SERVER_LEN:
            raise ValueError("mcp_server_too_long")
        if not _SERVER_RE.fullmatch(self.mcp_server):
            raise ValueError("invalid_mcp_server_format")
        # trace_id
        if not isinstance(self.trace_id, str):
            raise ValueError("trace_id must be a string")
        if len(self.trace_id) < _MIN_TRACE_LEN:
            raise ValueError("trace_id_too_short")
        if len(self.trace_id) > _MAX_TRACE_LEN:
            raise ValueError("trace_id_too_long")
        # firm_id
        if not isinstance(self.firm_id, str) or not self.firm_id:
            raise ValueError("firm_id must be a non-empty string")
        if len(self.firm_id) > _MAX_FIRM_LEN:
            raise ValueError("firm_id_too_long")
        # target, context
        if not isinstance(self.target, Mapping):
            raise ValueError("target must be a mapping")
        if not isinstance(self.context, Mapping):
            raise ValueError("context must be a mapping")
        # session_id
        if self.session_id is not None and not isinstance(self.session_id, str):
            raise ValueError("session_id must be a string or None")
        # payload type
        if self.payload is not None and not isinstance(
            self.payload, (dict, list, BaseModel)
        ):
            raise TypeError("invalid_payload_type")
        # payload size
        try:
            size = len(canonical_json(self.payload).encode("utf-8"))
        except TypeError:
            raise TypeError("invalid_payload_type")
        if size > _MAX_PAYLOAD_BYTES:
            raise ValueError("payload_too_large")
        # vendor adapter
        if self.vendor_adapter is None:
            raise ValueError("vendor_adapter must not be None")
        if not hasattr(self.vendor_adapter, "call") or not callable(
            self.vendor_adapter.call
        ):
            raise ValueError("vendor_adapter must have callable .call")
        if not hasattr(self.vendor_adapter, "name") or not isinstance(
            self.vendor_adapter.name, str
        ):
            raise ValueError("vendor_adapter must have str .name")

    def __repr__(self) -> str:
        return (
            f"GatewayRequest(action={self.action!r}, "
            f"tool_name={self.tool_name!r}, "
            f"mcp_server={self.mcp_server!r}, trace_id={self.trace_id!r}, "
            f"firm_id={self.firm_id!r}, token=<redacted>, "
            f"payload=<omitted>, session_id={self.session_id!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass(frozen=True)
class GatewayResponse:
    """Immutable gateway call result. __repr__ omits result (SI-4)."""

    decision: Literal["ALLOW", "DENY", "ESCALATE"]
    result: Any
    liability_report: Optional[LiabilityReport]
    trace_id: str
    latency_ms: int
    provenance_head: str
    rule_applied: Optional[str]
    wsp_section: Optional[str]
    reason: Optional[str]

    def __post_init__(self) -> None:
        if self.decision not in ("ALLOW", "DENY", "ESCALATE"):
            raise ValueError(f"invalid decision: {self.decision!r}")
        if not isinstance(self.latency_ms, int) or self.latency_ms < 0:
            raise ValueError("latency_ms must be a non-negative int")
        if not _HEX64_RE.fullmatch(self.provenance_head):
            raise ValueError(
                "provenance_head must be 64-char lowercase hex"
            )
        if not isinstance(self.trace_id, str) or not self.trace_id:
            raise ValueError("trace_id must be a non-empty string")

    def __repr__(self) -> str:
        head = (
            self.provenance_head[:16] + "..."
            if self.provenance_head
            else ""
        )
        return (
            f"GatewayResponse(decision={self.decision!r}, "
            f"trace_id={self.trace_id!r}, latency_ms={self.latency_ms}, "
            f"provenance_head={head!r}, result=<omitted>, "
            f"rule_applied={self.rule_applied!r}, "
            f"wsp_section={self.wsp_section!r})"
        )

    def __str__(self) -> str:
        return self.__repr__()


# =============================================================================
# Utilities.
# =============================================================================


def _default_utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _short(match_codes: Any) -> list[str]:
    try:
        seq = list(match_codes)
    except TypeError:
        return []
    return [str(x) for x in seq[:10]]


# =============================================================================
# TrustAwareGateway (spec R6).
# =============================================================================


class TrustAwareGateway:
    """Central trust hub. Every MCP call passes through `.call(...)`.

    All dependencies are injected. Phase 1 is single-threaded.
    See `.kiro/specs/m6-mcp-gateway.md` for the contract.
    """

    def __init__(
        self,
        *,
        identity: IdentityService,
        authority: AuthorityPolicy,
        mnpi: MnpiPolicy,
        audit: AuditLogger,
        leakage_scanner: MnpiLeakageScanner,
        circuit_breaker: CircuitBreaker,
        rate_limiter: RateLimiter,
        warranty_boundary: Optional[WarrantyBoundary] = None,
        canonicalizer: Optional[Canonicalizer] = None,
        clock: Callable[[], datetime] = _default_utcnow,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        for name, dep in (
            ("identity", identity),
            ("authority", authority),
            ("mnpi", mnpi),
            ("audit", audit),
            ("leakage_scanner", leakage_scanner),
            ("circuit_breaker", circuit_breaker),
            ("rate_limiter", rate_limiter),
        ):
            if dep is None:
                raise ValueError(
                    f"gateway_missing_dependency: {name} is None"
                )
        self._identity = identity
        self._authority = authority
        self._mnpi = mnpi
        self._audit = audit
        self._scanner = leakage_scanner
        self._circuit = circuit_breaker
        self._rate = rate_limiter
        self._warranty_boundary = warranty_boundary or WarrantyBoundary()
        self._canonicalizer = canonicalizer or default_canonicalizer()
        self._clock = clock
        self._monotonic = monotonic

    # -------------------------------------------------------------------
    # Health
    # -------------------------------------------------------------------

    def health(self) -> dict:
        try:
            audit_h = self._audit.health()
            audit_ok = audit_h.get("status") == "ok"
        except Exception:
            audit_ok = False
        return {
            "status": "ok",
            "circuit_states": {
                k: self._circuit.state(k) for k in self._circuit.keys()
            },
            "dependencies_ready": audit_ok,
        }

    # -------------------------------------------------------------------
    # Main pipeline
    # -------------------------------------------------------------------

    def call(self, request: GatewayRequest) -> GatewayResponse:
        """Execute the full trust pipeline."""
        start = self._monotonic()
        builder = ProvenanceChainBuilder()
        claims: Optional[AidClaims] = None
        policy_decision: Optional[PolicyDecision] = None

        try:
            # ---------- Stage 1: M1 identity ----------
            try:
                claims = verify_identity(self._identity, request.token)
                builder.append(
                    stage="m6.identity",
                    module="m6",
                    payload={
                        "verified": True,
                        "sub": claims.sub,
                        "jti": claims.jti,
                        "firm_id": claims.firm_id,
                    },
                    timestamp=self._clock(),
                )
            except GatewayError as exc:
                builder.append(
                    stage="m6.identity",
                    module="m6",
                    payload={
                        "verified": False,
                        "error_reason": exc.reason,
                    },
                    timestamp=self._clock(),
                )
                raise

            # ---------- Stage 2: M2 authority ----------
            policy_input = PolicyInput(
                identity=claims,
                action=request.action,
                target=dict(request.target),
                context=dict(request.context),
            )
            policy_decision = evaluate_authority(
                self._authority, policy_input
            )
            builder.append(
                stage="m6.authority",
                module="m6",
                payload={
                    "decision": policy_decision.decision.value,
                    "rule": policy_decision.rule_applied,
                    "wsp": policy_decision.wsp_section,
                },
                timestamp=self._clock(),
            )
            if policy_decision.decision is Decision.DENY:
                raise GatewayError("authority_denied")
            if policy_decision.decision is Decision.ESCALATE:
                raise GatewayError("authority_escalated")

            # ---------- Stage 3: M4 request filter ----------
            raw_payload = request.payload
            strict_req = isinstance(raw_payload, BaseModel)
            filtered_request = filter_request(
                self._mnpi, claims, raw_payload
            )
            builder.append(
                stage="m6.mnpi_request_filter",
                module="m6",
                payload={
                    "input_hash": _h(raw_payload),
                    "output_hash": _h(filtered_request),
                    "strict": strict_req,
                },
                timestamp=self._clock(),
            )

            # ---------- Stage 4: Resilience ----------
            rl_key = f"{claims.firm_id}:{claims.sub}:{request.tool_name}"
            try:
                self._circuit.check(request.mcp_server)
                self._rate.check(rl_key)
                builder.append(
                    stage="m6.resilience",
                    module="m6",
                    payload={
                        "circuit": self._circuit.state(request.mcp_server),
                        "key": rl_key,
                    },
                    timestamp=self._clock(),
                )
            except GatewayError as exc:
                builder.append(
                    stage="m6.resilience",
                    module="m6",
                    payload={
                        "circuit": self._circuit.state(request.mcp_server),
                        "key": rl_key,
                        "error": exc.reason,
                    },
                    timestamp=self._clock(),
                )
                raise

            # ---------- Stage 5: Vendor call ----------
            try:
                vendor_response = request.vendor_adapter.call(
                    tool_name=request.tool_name,
                    payload=filtered_request,
                )
                self._circuit.record_success(request.mcp_server)
                builder.append(
                    stage="m6.vendor_call",
                    module="m6",
                    payload={
                        "tool": request.tool_name,
                        "server": request.mcp_server,
                        "ok": True,
                    },
                    timestamp=self._clock(),
                )
            except VendorAdapterError as vexc:
                self._circuit.record_failure(request.mcp_server)
                reason = (
                    "vendor_unavailable"
                    if vexc.kind == "unavailable"
                    else "vendor_error"
                )
                builder.append(
                    stage="m6.vendor_call",
                    module="m6",
                    payload={
                        "tool": request.tool_name,
                        "server": request.mcp_server,
                        "ok": False,
                        "error": reason,
                    },
                    timestamp=self._clock(),
                )
                raise GatewayError(reason)

            # ---------- Stage 6: Translate via M7 canonicalizer ----------
            # Rule 33: adapters stay vendor-pure. M6 owns canonicalization.
            # Pass-through when no (vendor, tool_name) translator registered.
            try:
                canon_result = self._canonicalizer.translate(
                    vendor=request.mcp_server,
                    tool_name=request.tool_name,
                    raw_payload=vendor_response,
                )
                translated_response = canon_result.payload
                builder.append(
                    stage="m6.translate",
                    module="m6",
                    payload={
                        "translated": bool(canon_result.translated),
                        "source_system": canon_result.source_system,
                        "canonical_type": canon_result.canonical_type,
                        "pass_through": not canon_result.translated,
                    },
                    timestamp=self._clock(),
                )
            except _CanonicalizeError as texc:
                builder.append(
                    stage="m6.translate",
                    module="m6",
                    payload={
                        "translated": False,
                        "error": "translation_error",
                        "reason_code": texc.reason_code,
                    },
                    timestamp=self._clock(),
                )
                # Fail-closed: vendor returned a shape M7 couldn't translate.
                # Surface as vendor_error so the caller sees the failure.
                raise GatewayError("vendor_error")

            # ---------- Stage 7: M4 response filter ----------
            strict_resp = isinstance(translated_response, BaseModel)
            filtered_response = filter_response(
                self._mnpi, claims, translated_response
            )
            builder.append(
                stage="m6.mnpi_response_filter",
                module="m6",
                payload={
                    "input_hash": _h(translated_response),
                    "output_hash": _h(filtered_response),
                    "strict": strict_resp,
                },
                timestamp=self._clock(),
            )

            # ---------- Stage 8: Gap 6 leakage scan ----------
            scan_text = canonical_text(filtered_response)
            scan_result = self._scanner.scan(scan_text)
            if scan_result.decision is ScanDecision.DENY:
                builder.append(
                    stage="m6.leakage_scan",
                    module="m6",
                    payload={
                        "layer": scan_result.layer,
                        "decision": scan_result.decision.value,
                        "match_codes": _short(scan_result.match_codes),
                    },
                    timestamp=self._clock(),
                )
                raise GatewayError("mnpi_leakage_scan")
            builder.append(
                stage="m6.leakage_scan",
                module="m6",
                payload={
                    "layer": scan_result.layer,
                    "decision": scan_result.decision.value,
                },
                timestamp=self._clock(),
            )

            # ---------- Stage 9: LiabilityReport (ALLOW) ----------
            now = self._clock()
            report = LiabilityReport.build(
                trace_id=request.trace_id,
                chain=builder.chain(),
                chain_verified=builder.verify(),
                generated_at=now,
                error=None,
                boundary=self._warranty_boundary,
            )

            # ---------- Stage 10: Audit write (ALLOW) ----------
            latency_ms = int((self._monotonic() - start) * 1000)
            entry = build_audit_entry(
                request=request,
                claims=claims,
                token=request.token,
                decision="allow",
                reason=(
                    policy_decision.reason if policy_decision else "allow"
                ),
                policy_decision=policy_decision,
                input_payload=request.payload,
                output_payload=filtered_response,
                provenance_chain=builder.chain(),
                latency_ms=latency_ms,
                now=now,
                session_id=request.session_id,
            )
            try:
                self._audit.write(entry)
            except AuditWriteError:
                builder.append(
                    stage="m6.audit_attempt",
                    module="m6",
                    payload={
                        "decision": "allow",
                        "original_reason": "allow",
                    },
                    timestamp=self._clock(),
                )
                raise GatewayError("audit_failed")

            # ---------- Stage 11: Return ----------
            return GatewayResponse(
                decision="ALLOW",
                result=filtered_response,
                liability_report=report,
                trace_id=request.trace_id,
                latency_ms=latency_ms,
                provenance_head=builder.head_hash(),
                rule_applied=(
                    policy_decision.rule_applied
                    if policy_decision
                    else None
                ),
                wsp_section=(
                    policy_decision.wsp_section
                    if policy_decision
                    else None
                ),
                reason=(
                    policy_decision.reason if policy_decision else None
                ),
            )

        except GatewayError as exc:
            self._handle_failure(
                request=request,
                claims=claims,
                policy_decision=policy_decision,
                builder=builder,
                reason=exc.reason,
                start=start,
            )
            # _handle_failure always raises; control should never reach here
            raise  # pragma: no cover
        except Exception:
            self._handle_failure(
                request=request,
                claims=claims,
                policy_decision=policy_decision,
                builder=builder,
                reason="invalid_request",
                start=start,
            )
            raise  # pragma: no cover

    # -------------------------------------------------------------------
    # Failure handler
    # -------------------------------------------------------------------

    def _handle_failure(
        self,
        *,
        request: GatewayRequest,
        claims: Optional[AidClaims],
        policy_decision: Optional[PolicyDecision],
        builder: ProvenanceChainBuilder,
        reason: str,
        start: float,
    ) -> None:
        """Build LiabilityReport + AuditEntry + raise GatewayError.

        Always raises. Either GatewayError(reason) or
        GatewayError('audit_failed') if the audit write failed.
        """
        decision_label = (
            "escalate" if reason == "authority_escalated" else "deny"
        )

        chain = builder.chain()
        now = self._clock()
        error_attr: Optional[ErrorAttribution] = None
        if chain:
            failing_stage = chain[-1].stage
            category = REASON_TO_ERROR_CATEGORY.get(
                reason, ErrorCategory.policy_evaluation_error
            )
            try:
                error_attr = ErrorAttribution.attribute_from_chain(
                    chain=chain,
                    failing_stage_name=failing_stage,
                    category=category,
                    reason=reason,
                    occurred_at=now,
                )
            except ValueError:
                error_attr = None

        # Build (but do not return) a LiabilityReport so attribution is
        # validated. The report is referenced only via AuditEntry's
        # provenance chain. In Phase 2 the report will be persisted
        # alongside the audit entry.
        if chain and error_attr is not None:
            try:
                LiabilityReport.build(
                    trace_id=request.trace_id,
                    chain=chain,
                    chain_verified=builder.verify(),
                    generated_at=now,
                    error=error_attr,
                    boundary=self._warranty_boundary,
                )
            except ValueError:
                pass

        latency_ms = int((self._monotonic() - start) * 1000)
        entry = build_audit_entry(
            request=request,
            claims=claims,
            token=request.token,
            decision=decision_label,
            reason=reason,
            policy_decision=policy_decision,
            input_payload=request.payload,
            output_payload=None,
            provenance_chain=chain,
            latency_ms=latency_ms,
            now=now,
            session_id=request.session_id,
        )
        try:
            self._audit.write(entry)
        except AuditWriteError:
            # Extend chain with audit_attempt, retry once, then raise
            # audit_failed regardless of the retry outcome.
            builder.append(
                stage="m6.audit_attempt",
                module="m6",
                payload={
                    "decision": decision_label,
                    "original_reason": reason,
                },
                timestamp=self._clock(),
            )
            entry2 = build_audit_entry(
                request=request,
                claims=claims,
                token=request.token,
                decision=decision_label,
                reason=reason,
                policy_decision=policy_decision,
                input_payload=request.payload,
                output_payload=None,
                provenance_chain=builder.chain(),
                latency_ms=latency_ms,
                now=now,
                session_id=request.session_id,
            )
            try:
                self._audit.write(entry2)
            except AuditWriteError:
                pass
            raise GatewayError("audit_failed")

        raise GatewayError(reason)


__all__ = [
    "TrustAwareGateway",
    "GatewayRequest",
    "GatewayResponse",
    "GatewayError",
    "VALID_GATEWAY_REASONS",
]
