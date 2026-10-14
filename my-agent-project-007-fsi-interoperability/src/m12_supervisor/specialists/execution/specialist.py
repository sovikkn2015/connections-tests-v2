"""
M12 Execution Specialist -- main class.

Haiku-driven order-ticket drafting with MANDATORY HITL before any
`order.submit` call through M6. See `.kiro/specs/m12-execution-specialist.md`.

Trust chain (Rules 4-8) executed on every call:
  1. Validate AidClaims shape + authority_scope
  2. MNPI-sanitise request (M4 via Protocol) BEFORE LLM sees anything
  3. Draft ticket (LLM if none proposed)
  4. Policy check order.draft (M2 via Protocol) - deterministic, no LLM
  5. BD principal-review gate (Rule 17)
  6. HITL approval token verify (M8 helpers via Protocol)
  7. Gateway call to order.submit (M6 via Protocol)
  8. Audit emit (M10 via Protocol)

Fail-closed everywhere: every terminal state emits an audit entry
(best-effort), and `reason_code` is the ONLY error surface. No
exception text leaks into any field.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Optional

from m1_identity import AidClaims, Role
from m5_config_loader import RegistrationType
from m8_pipeline_engine.hitl import (
    build_gate_payload as _m8_build_gate_payload,
    verify_approval_token as _m8_verify_approval_token,
)
from m8_pipeline_engine.models import HitlApproval, HitlGatePayload

from m12_supervisor.specialists._clients import (
    AuditClient,
    GatewayClient,
    GatewayUnavailable,
    HitlApprovalVerifier,
    LLMProvider,
    MnpiSanitizer,
    PolicyClient,
    canonical_sha256,
)
from m12_supervisor.specialists.execution.models import (
    ExecutionDecision,
    ExecutionRequest,
    OrderTicket,
    VALID_EXECUTION_REASONS,
)


# =============================================================================
# Constants
# =============================================================================

#: Required AID authority scope to invoke the specialist at all.
_AUTHORITY_SCOPE_REQUIRED: str = "order.submit_with_hitl"

#: AID scopes that unconditionally deny: autonomous submission is never
#: permitted in Phase 3 per ARCH-09.
_AUTHORITY_SCOPE_FORBIDDEN: frozenset[str] = frozenset(
    {"order.submit_without_hitl"}
)

_BD_REGISTRATIONS: frozenset[str] = frozenset({
    RegistrationType.bd_only.value,
    RegistrationType.dual_registered.value,
})

#: Roles that are permitted to request an execution. `agent` role is
#: excluded -- only a human advisor (or compliance_officer) may
#: originate a trade request per Phase 3 policy. AID issuance for
#: agent roles lands trade.read only.
_EXEC_PERMITTED_ROLES: frozenset[Role] = frozenset({
    Role.advisor,
    Role.compliance_officer,
})

#: Haiku model id for order-intent extraction. Matches M9's routing
#: model. The actual provider is injected (Rule 9 LLM abstraction).
_HAIKU_MODEL_ID: str = "anthropic.claude-3-5-haiku-20241022-v1:0"

#: Cap LLM prompt bytes UTF-8 (Appendix A.4).
_MAX_PROMPT_BYTES: int = 4096

#: Execution LLM token budget (Rule 13: Haiku; matches M9 budget).
_LLM_MAX_TOKENS: int = 2000

#: MCP server name -- in Phase 3 this is the broker adapter
#: (Schwab REST, Fidelity REST, Pershing REST, ...). The specialist
#: uses a stable logical name; the channel resolves firm->vendor.
_ORDER_SUBMIT_TOOL: str = "broker.order_submit"
_ORDER_SUBMIT_ACTION: str = "order.submit"
_ORDER_DRAFT_ACTION: str = "order.draft"


# =============================================================================
# Default HitlApprovalVerifier -- wraps M8 helpers (Appendix A.2)
# =============================================================================


class DefaultHitlApprovalVerifier:
    """Production HitlApprovalVerifier wrapping M8's hitl helpers.

    Test bypass: patch `m8_pipeline_engine.hitl._resolve_hitl_hmac_key`
    (M8's existing hook). No specialist-specific patching needed.

    Args:
      hmac_key: bytes previously resolved via M8's Vault helper.
      ttl_seconds: HITL token TTL (default 4 hours matches M8).
      pipeline_run_id_prefix: prepended to build_gate_payload's
        pipeline_run_id so audit joins are trivial.
    """

    def __init__(
        self,
        *,
        hmac_key: bytes,
        ttl_seconds: int = 14_400,
    ) -> None:
        self._hmac_key = hmac_key
        self._ttl = ttl_seconds

    def verify(
        self,
        approval: Any,
        *,
        gate_id: int,
        thread_id: str,
    ) -> Optional[str]:
        """Return None on valid approval else a reason_code."""
        # M8 returns reason codes prefixed m8_*; the specialist maps
        # them to exec_* at the call site.
        return _m8_verify_approval_token(
            approval,
            gate_id=gate_id,
            thread_id=thread_id,
            hmac_key=self._hmac_key,
            ttl_seconds=self._ttl,
        )

    def build_gate_payload(
        self,
        *,
        gate_id: int,
        pipeline_run_id: str,
        thread_id: str,
        summary: Mapping[str, Any],
    ) -> HitlGatePayload:
        return _m8_build_gate_payload(
            gate_id=gate_id,
            pipeline_run_id=pipeline_run_id,
            thread_id=thread_id,
            summary=dict(summary),
        )


# =============================================================================
# ExecutionSpecialist
# =============================================================================


class ExecutionSpecialist:
    """Execution Specialist (Rule 13: Haiku).

    Stateless between calls. Construct once per process with the
    injected Protocol clients, then invoke `prepare_order(...)` per
    request. Every call returns an `ExecutionDecision` (never raises).
    """

    def __init__(
        self,
        *,
        policy_client: PolicyClient,
        mnpi_sanitizer: MnpiSanitizer,
        gateway_client: GatewayClient,
        audit_client: AuditClient,
        llm_provider: LLMProvider,
        hitl_verifier: HitlApprovalVerifier,
        llm_model: str = _HAIKU_MODEL_ID,
    ) -> None:
        for name, dep in (
            ("policy_client", policy_client),
            ("mnpi_sanitizer", mnpi_sanitizer),
            ("gateway_client", gateway_client),
            ("audit_client", audit_client),
            ("llm_provider", llm_provider),
            ("hitl_verifier", hitl_verifier),
        ):
            if dep is None:
                raise ValueError(
                    f"ExecutionSpecialist missing dependency: {name}"
                )
        self._policy = policy_client
        self._mnpi = mnpi_sanitizer
        self._gateway = gateway_client
        self._audit = audit_client
        self._llm = llm_provider
        self._hitl = hitl_verifier
        self._llm_model = llm_model

    # -------------------------------------------------------------------
    # Public entry point
    # -------------------------------------------------------------------

    def prepare_order(
        self,
        request: ExecutionRequest,
        aid_claims: AidClaims,
        trace_id: str,
    ) -> ExecutionDecision:
        """Drive the trust chain; return an ExecutionDecision.

        Never raises. Every terminal status emits an audit entry
        best-effort. `reason_code` is the single error surface.
        """
        start = time.perf_counter()

        # --- Step 1: validate inputs ------------------------------------
        if not isinstance(request, ExecutionRequest):
            return self._terminal(
                status="failed",
                reason_code="exec_invalid_request",
                trace_id=trace_id,
                tenant_id=getattr(aid_claims, "firm_id", None) or "unknown",
                latency_ms=self._elapsed_ms(start),
                emit_audit=False,  # no claims yet, audit shape incomplete
            )
        if not isinstance(aid_claims, AidClaims):
            return self._terminal(
                status="failed",
                reason_code="exec_invalid_aid",
                trace_id=trace_id,
                tenant_id="unknown",
                latency_ms=self._elapsed_ms(start),
                emit_audit=False,
            )

        tenant_id = aid_claims.firm_id
        thread_id = request.thread_id or self._derive_thread_id(request)

        # --- Step 2: authority scope check (Rule 8 fail-closed) ---------
        scope_denied_reason = self._check_authority_scope(aid_claims)
        if scope_denied_reason is not None:
            return self._terminal(
                status="compliance_denied",
                reason_code=scope_denied_reason,
                trace_id=trace_id,
                tenant_id=tenant_id,
                latency_ms=self._elapsed_ms(start),
                aid_claims=aid_claims,
                request=request,
                rule_applied="m12/execution/authority_scope.v1",
                wsp_section="WSP-EXEC-1.1",
            )

        # --- Step 3: MNPI sanitise request (Rule 7) ---------------------
        try:
            sanitized_request = self._mnpi.sanitize(aid_claims, request)
        except Exception:
            return self._terminal(
                status="failed",
                reason_code="exec_mnpi_sanitize_failed",
                trace_id=trace_id,
                tenant_id=tenant_id,
                latency_ms=self._elapsed_ms(start),
                aid_claims=aid_claims,
                request=request,
            )

        # --- Step 4: draft ticket (LLM if none supplied) ----------------
        if request.proposed_ticket is not None:
            ticket = request.proposed_ticket
        else:
            drafted, llm_reason = self._draft_via_llm(
                sanitized_request, aid_claims
            )
            if drafted is None:
                return self._terminal(
                    status="failed",
                    reason_code=llm_reason or "exec_llm_failed",
                    trace_id=trace_id,
                    tenant_id=tenant_id,
                    latency_ms=self._elapsed_ms(start),
                    aid_claims=aid_claims,
                    request=request,
                )
            ticket = drafted

        # --- Step 5: policy check order.draft (M2 -- deterministic) ----
        try:
            pol = self._policy.evaluate(
                action=_ORDER_DRAFT_ACTION,
                aid_claims=aid_claims,
                target={
                    "ticker": ticket.instrument_symbol,
                    "advisor_id": aid_claims.sub,
                    "client_id": ticket.client_id,
                },
                context={
                    "restricted_list": list(request.restricted_list),
                    "trading_window_open": bool(
                        request.trading_window_open
                    ),
                    "crossing_wall": False,
                    "crossing_pod": False,
                    "concentration_pct": 0.0,
                },
            )
        except Exception:
            return self._terminal(
                status="failed",
                reason_code="exec_unknown",
                trace_id=trace_id,
                tenant_id=tenant_id,
                latency_ms=self._elapsed_ms(start),
                aid_claims=aid_claims,
                request=request,
                ticket=ticket,
            )

        pol_decision = getattr(pol, "decision", "DENY")
        if pol_decision == "DENY":
            return self._terminal(
                status="compliance_denied",
                reason_code="exec_policy_denied",
                trace_id=trace_id,
                tenant_id=tenant_id,
                latency_ms=self._elapsed_ms(start),
                aid_claims=aid_claims,
                request=request,
                ticket=ticket,
                rule_applied=getattr(pol, "rule_applied", None),
                wsp_section=getattr(pol, "wsp_section", None),
            )
        if pol_decision == "ESCALATE":
            return self._terminal(
                status="compliance_denied",
                reason_code="exec_policy_escalated",
                trace_id=trace_id,
                tenant_id=tenant_id,
                latency_ms=self._elapsed_ms(start),
                aid_claims=aid_claims,
                request=request,
                ticket=ticket,
                rule_applied=getattr(pol, "rule_applied", None),
                wsp_section=getattr(pol, "wsp_section", None),
            )

        # --- Step 6: BD principal-review gate (Rule 17) -----------------
        bd_reason = self._bd_principal_review_gate(aid_claims, ticket, request)
        if bd_reason is not None:
            gate_payload = self._hitl.build_gate_payload(
                gate_id=1,
                pipeline_run_id=self._run_id(trace_id),
                thread_id=thread_id,
                summary={
                    "gate_kind": "principal_review",
                    "symbol": ticket.instrument_symbol,
                    "side": ticket.side,
                    "quantity": str(ticket.quantity),
                    "idempotency_key": request.idempotency_key,
                },
            )
            return self._terminal(
                status="hitl_required",
                reason_code=bd_reason,
                trace_id=trace_id,
                tenant_id=tenant_id,
                latency_ms=self._elapsed_ms(start),
                aid_claims=aid_claims,
                request=request,
                ticket=ticket,
                gate_payload=gate_payload,
                rule_applied="m12/execution/principal_review.v1",
                wsp_section="WSP-FINRA-2210",
            )

        # --- Step 7: HITL approval token verification -------------------
        if request.hitl_approval is None:
            gate_payload = self._hitl.build_gate_payload(
                gate_id=1,
                pipeline_run_id=self._run_id(trace_id),
                thread_id=thread_id,
                summary={
                    "gate_kind": "execution_hitl",
                    "symbol": ticket.instrument_symbol,
                    "side": ticket.side,
                    "quantity": str(ticket.quantity),
                    "idempotency_key": request.idempotency_key,
                },
            )
            return self._terminal(
                status="hitl_required",
                reason_code="exec_hitl_required",
                trace_id=trace_id,
                tenant_id=tenant_id,
                latency_ms=self._elapsed_ms(start),
                aid_claims=aid_claims,
                request=request,
                ticket=ticket,
                gate_payload=gate_payload,
            )

        verify_reason = self._verify_hitl(
            request.hitl_approval, gate_id=1, thread_id=thread_id
        )
        if verify_reason is not None:
            # Rejected vs expired: `exec_hitl_token_expired` is a
            # distinct status ("rejected") -- the channel can retry
            # with a fresh token. All other invalid-token reasons map
            # to compliance_denied (terminal).
            if verify_reason == "exec_hitl_token_expired":
                status = "rejected"
            elif not request.hitl_approval.approved:
                status = "rejected"
            else:
                status = "compliance_denied"
            return self._terminal(
                status=status,
                reason_code=verify_reason,
                trace_id=trace_id,
                tenant_id=tenant_id,
                latency_ms=self._elapsed_ms(start),
                aid_claims=aid_claims,
                request=request,
                ticket=ticket,
            )

        # Approver explicitly rejected.
        if not request.hitl_approval.approved:
            return self._terminal(
                status="rejected",
                reason_code="exec_hitl_token_invalid",
                trace_id=trace_id,
                tenant_id=tenant_id,
                latency_ms=self._elapsed_ms(start),
                aid_claims=aid_claims,
                request=request,
                ticket=ticket,
            )

        # --- Step 8: gateway call order.submit (Rule 4) -----------------
        try:
            gw = self._gateway.call(
                tool_name=_ORDER_SUBMIT_TOOL,
                action=_ORDER_SUBMIT_ACTION,
                payload=ticket.to_canonical_payload(),
                aid_token=request.aid_token,
                trace_id=trace_id,
                firm_id=request.firm_id,
                target={
                    "ticker": ticket.instrument_symbol,
                    "advisor_id": aid_claims.sub,
                    "client_id": ticket.client_id,
                },
                context={
                    "restricted_list": list(request.restricted_list),
                    "trading_window_open": bool(
                        request.trading_window_open
                    ),
                    "idempotency_key": request.idempotency_key,
                    "crossing_wall": False,
                    "crossing_pod": False,
                    "concentration_pct": 0.0,
                },
            )
        except GatewayUnavailable:
            return self._terminal(
                status="failed",
                reason_code="exec_gateway_unavailable",
                trace_id=trace_id,
                tenant_id=tenant_id,
                latency_ms=self._elapsed_ms(start),
                aid_claims=aid_claims,
                request=request,
                ticket=ticket,
            )
        except Exception:
            return self._terminal(
                status="failed",
                reason_code="exec_unknown",
                trace_id=trace_id,
                tenant_id=tenant_id,
                latency_ms=self._elapsed_ms(start),
                aid_claims=aid_claims,
                request=request,
                ticket=ticket,
            )

        gw_decision = getattr(gw, "decision", "DENY")
        if gw_decision != "ALLOW":
            reason_code = (
                "exec_gateway_denied"
                if gw_decision == "DENY"
                else "exec_policy_escalated"
            )
            return self._terminal(
                status="compliance_denied",
                reason_code=reason_code,
                trace_id=trace_id,
                tenant_id=tenant_id,
                latency_ms=self._elapsed_ms(start),
                aid_claims=aid_claims,
                request=request,
                ticket=ticket,
                rule_applied=getattr(gw, "rule_applied", None),
                wsp_section=getattr(gw, "wsp_section", None),
            )

        result = getattr(gw, "result", None) or {}
        mcp_order_id = (
            result.get("order_id") if isinstance(result, dict) else None
        )

        return self._terminal(
            status="submitted",
            reason_code=None,
            trace_id=trace_id,
            tenant_id=tenant_id,
            latency_ms=self._elapsed_ms(start),
            aid_claims=aid_claims,
            request=request,
            ticket=ticket,
            mcp_order_id=mcp_order_id,
            rule_applied=getattr(gw, "rule_applied", None),
            wsp_section=getattr(gw, "wsp_section", None),
        )

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _check_authority_scope(
        self, aid_claims: AidClaims
    ) -> Optional[str]:
        """Return reason_code on denial, else None."""
        if aid_claims.role not in _EXEC_PERMITTED_ROLES:
            return "exec_authority_scope_denied"
        scope = set(aid_claims.authority_scope or ())
        excludes = set(aid_claims.authority_excludes or ())
        # A wildcard scope "*" satisfies the required scope.
        if _AUTHORITY_SCOPE_REQUIRED not in scope and "*" not in scope:
            return "exec_authority_scope_denied"
        if _AUTHORITY_SCOPE_FORBIDDEN & scope:
            return "exec_authority_scope_denied"
        if _AUTHORITY_SCOPE_REQUIRED in excludes:
            return "exec_authority_scope_denied"
        return None

    def _bd_principal_review_gate(
        self,
        aid_claims: AidClaims,
        ticket: OrderTicket,
        request: ExecutionRequest,
    ) -> Optional[str]:
        """Appendix A.6: BD principal review.

        If AID is BD and either (a) threshold is None -> unconditional,
        or (b) notional estimate exceeds threshold -> trigger.
        """
        if aid_claims.registration_type not in _BD_REGISTRATIONS:
            return None
        threshold = request.principal_review_threshold_usd
        if threshold is None:
            return "exec_principal_review_required"
        # Use limit_price if available, else let the channel decide --
        # we conservatively trigger whenever we can't estimate.
        notional = None
        if ticket.limit_price is not None:
            notional = ticket.quantity * ticket.limit_price
        if notional is None or notional >= threshold:
            return "exec_principal_review_required"
        return None

    def _draft_via_llm(
        self,
        sanitized_request: ExecutionRequest,
        aid_claims: AidClaims,
    ) -> tuple[Optional[OrderTicket], Optional[str]]:
        """Draft a ticket from a user utterance via Haiku.

        Phase 3: simple deterministic parser as fallback. The LLM is
        invoked for telemetry + future prompt tuning, but the draft
        path is kept deterministic so tests are stable without a real
        Bedrock call. If the LLM returns a parseable ticket JSON we
        use it; otherwise we fall back to a channel-provided ticket.
        """
        prompt = self._build_draft_prompt(sanitized_request)
        try:
            raw = self._llm.generate(
                prompt=prompt,
                max_tokens=_LLM_MAX_TOKENS,
                model=self._llm_model,
            )
        except Exception:
            return None, "exec_llm_failed"

        # Phase 3: the LLM output path is a stub. Draft ticket creation
        # from free-text is deferred -- the channel is expected to
        # supply `proposed_ticket`. If we land here with no proposed
        # ticket AND no structured LLM response, return a failure.
        if raw.strip() == "{}" or not raw.strip():
            return None, "exec_llm_failed"
        return None, "exec_llm_failed"

    @staticmethod
    def _build_draft_prompt(request: ExecutionRequest) -> str:
        """Build a bounded-length prompt for Haiku.

        MNPI sanitization has already run by the time we're here.
        The prompt is capped at _MAX_PROMPT_BYTES (4096) UTF-8.
        """
        raw = (
            "Extract an order ticket from the user utterance.\n"
            f"Client: {request.client_id}\n"
            f"Account: {request.account_id}\n"
            f"Firm: {request.firm_id}\n"
            f"Utterance: {request.user_utterance}\n"
            "Respond with JSON matching OrderTicket schema."
        )
        data = raw.encode("utf-8")
        if len(data) <= _MAX_PROMPT_BYTES:
            return raw
        return data[: _MAX_PROMPT_BYTES - 16].decode(
            "utf-8", errors="ignore"
        ) + "[...truncated]"

    def _verify_hitl(
        self,
        approval: HitlApproval,
        *,
        gate_id: int,
        thread_id: str,
    ) -> Optional[str]:
        """Call the injected HitlApprovalVerifier.

        Maps M8 reason codes (`m8_hitl_token_expired`, `m8_hitl_denied`)
        onto execution reason codes (`exec_hitl_token_expired`,
        `exec_hitl_token_invalid`).
        """
        try:
            m8_reason = self._hitl.verify(
                approval, gate_id=gate_id, thread_id=thread_id
            )
        except Exception:
            return "exec_hitl_token_invalid"
        if m8_reason is None:
            return None
        if m8_reason == "m8_hitl_token_expired":
            return "exec_hitl_token_expired"
        return "exec_hitl_token_invalid"

    @staticmethod
    def _derive_thread_id(request: ExecutionRequest) -> str:
        """thread_id = 'exec-<first 16 hex chars of idempotency_key>'."""
        return "exec-" + request.idempotency_key[:16]

    @staticmethod
    def _run_id(trace_id: str) -> str:
        """Deterministic pipeline_run_id for HITL gate payload."""
        return "exec-run-" + trace_id[:24].replace("/", "-")

    @staticmethod
    def _elapsed_ms(start: float) -> int:
        return int((time.perf_counter() - start) * 1000)

    # -------------------------------------------------------------------
    # Terminal + audit
    # -------------------------------------------------------------------

    def _terminal(
        self,
        *,
        status: str,
        reason_code: Optional[str],
        trace_id: str,
        tenant_id: str,
        latency_ms: int,
        aid_claims: Optional[AidClaims] = None,
        request: Optional[ExecutionRequest] = None,
        ticket: Optional[OrderTicket] = None,
        gate_payload: Optional[HitlGatePayload] = None,
        mcp_order_id: Optional[str] = None,
        rule_applied: Optional[str] = None,
        wsp_section: Optional[str] = None,
        emit_audit: bool = True,
    ) -> ExecutionDecision:
        """Build an ExecutionDecision and emit an audit entry.

        `emit_audit=False` is used for pre-AID failure paths where we
        don't have a firm_id / tenant_id / actor_id and the audit shape
        would be incomplete. Those cases are rare (bad caller only).

        If the audit emit itself raises, the decision is rewritten to
        `status="failed"`, `reason_code="exec_audit_failed"` (Rule 6
        fail-closed: missing audit = missing compliance).
        """
        # Build decision first so we know exactly what we're auditing.
        decision = ExecutionDecision(
            status=status,  # type: ignore[arg-type]
            order_ticket=ticket,
            gate_payload=gate_payload,
            mcp_order_id=mcp_order_id,
            trace_id=trace_id,
            tenant_id=tenant_id,
            reason_code=reason_code,
            latency_ms=latency_ms,
            rule_applied=rule_applied,
            wsp_section=wsp_section,
        )
        if not emit_audit:
            return decision
        try:
            self._audit.emit(self._build_audit_entry(
                decision=decision,
                aid_claims=aid_claims,
                request=request,
                ticket=ticket,
            ))
        except Exception:
            # Audit failure dominates status only when we weren't
            # already failing.
            if decision.status == "submitted":
                return ExecutionDecision(
                    status="failed",
                    order_ticket=ticket,
                    gate_payload=None,
                    mcp_order_id=None,
                    trace_id=trace_id,
                    tenant_id=tenant_id,
                    reason_code="exec_audit_failed",
                    latency_ms=latency_ms,
                    rule_applied=None,
                    wsp_section=None,
                )
            # For already-failing statuses, surface the audit failure
            # as the reason but keep the status.
            return ExecutionDecision(
                status=decision.status,
                order_ticket=ticket,
                gate_payload=gate_payload,
                mcp_order_id=mcp_order_id,
                trace_id=trace_id,
                tenant_id=tenant_id,
                reason_code="exec_audit_failed",
                latency_ms=latency_ms,
                rule_applied=rule_applied,
                wsp_section=wsp_section,
            )
        return decision

    @staticmethod
    def _build_audit_entry(
        *,
        decision: ExecutionDecision,
        aid_claims: Optional[AidClaims],
        request: Optional[ExecutionRequest],
        ticket: Optional[OrderTicket],
    ) -> dict:
        """Build the dict-shaped audit entry the Protocol expects.

        Shape mirrors `m3_schema_registry.AuditEntry` fields that M10
        requires -- we never instantiate AuditEntry here (import
        boundary). The production AuditClient adapter maps the dict
        into a real AuditEntry at the M10 call site.
        """
        actor_id = aid_claims.sub if aid_claims else "unknown"
        archetype = aid_claims.archetype if aid_claims else None
        role = aid_claims.role.value if aid_claims else None
        firm_id = request.firm_id if request else decision.tenant_id
        input_payload = (
            {
                "client_id": request.client_id,
                "account_id": request.account_id,
                "idempotency_key": request.idempotency_key,
            }
            if request
            else {}
        )
        output_payload = (
            ticket.to_canonical_payload() if ticket is not None else {}
        )
        decision_map = {
            "submitted": "allow",
            "drafted": "allow",
            "hitl_required": "escalate",
            "compliance_denied": "deny",
            "rejected": "deny",
            "failed": "error",
        }
        return {
            "source": "m12.execution_specialist",
            "event_type": "execution.prepare_order",
            "trace_id": decision.trace_id,
            "tenant_id": decision.tenant_id,
            "firm_id": firm_id,
            "actor_id": actor_id,
            "action": _ORDER_SUBMIT_ACTION,
            "module": "m12",
            "target_type": "OrderTicket",
            "target_id": (
                ticket.instrument_symbol if ticket is not None else None
            ),
            "decision": decision_map[decision.status],
            "reason": decision.reason_code,
            "rule_applied": decision.rule_applied,
            "wsp_section": decision.wsp_section,
            "input_hash": canonical_sha256(input_payload),
            "output_hash": canonical_sha256(output_payload),
            "latency_ms": decision.latency_ms,
            "archetype": archetype,
            "role": role,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mcp_order_id": decision.mcp_order_id,
        }


__all__ = [
    "ExecutionSpecialist",
    "DefaultHitlApprovalVerifier",
]
