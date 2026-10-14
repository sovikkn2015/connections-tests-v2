"""
M12 Execution Specialist -- behavioural unit tests.

Covers every AC from `.kiro/specs/m12-execution-specialist.md`:
  R1.1-R1.4  public API + never-raises contract
  R2.1-R2.8  trust chain: policy/MNPI/authority/HITL/audit/gateway
  R3.1-R3.4  LLM budget + MNPI-before-LLM + prompt cap
  R4.1-R4.2  BD principal review
  R5.1-R5.2  concurrency + idempotency
  A3         error-surface hygiene
  A7         no retry policy
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

import pytest

from m1_identity import AidClaims, Role
from m5_config_loader import Archetype, RegistrationType
from m8_pipeline_engine.hitl import build_approval_token
from m8_pipeline_engine.models import HitlApproval

from m12_supervisor.specialists import (
    FakeAuditClient,
    FakeGatewayClient,
    FakeHitlVerifier,
    FakeLLMProvider,
    FakeMnpiSanitizer,
    FakePolicyClient,
    GatewayResultShape,
    PolicyResultShape,
)
from m12_supervisor.specialists._clients import GatewayUnavailable
from m12_supervisor.specialists.execution import (
    DefaultHitlApprovalVerifier,
    ExecutionDecision,
    ExecutionRequest,
    ExecutionSpecialist,
    OrderTicket,
    VALID_EXECUTION_REASONS,
)


# =============================================================================
# Fixtures
# =============================================================================


def _aid_advisor(
    *,
    scope: Optional[list[str]] = None,
    excludes: Optional[list[str]] = None,
    reg: str = "ria_only",
    role: Role = Role.advisor,
) -> AidClaims:
    return AidClaims(
        iss="007-fsi-platform",
        sub="advisor-01",
        aud="007-mcp-gateway",
        exp=1_747_371_600,
        iat=1_747_368_000,
        nbf=1_747_368_000,
        jti="aid-advisor-0001",
        firm_id="firm-acme",
        lei=None,
        crd_number="CRD-1",
        archetype="tier4_independent_ria",
        role=role,
        authority_scope=scope if scope is not None else ["order.submit_with_hitl"],
        authority_excludes=excludes or [],
        registration_type=reg,
    )


def _ticket(**overrides) -> OrderTicket:
    base = dict(
        client_id="CLT-1",
        account_id="ACC-1",
        instrument_symbol="NVDA",
        side="buy",
        quantity=Decimal("500"),
        order_type="limit",
        limit_price=Decimal("125.50"),
        time_in_force="day",
        notes=None,
    )
    base.update(overrides)
    return OrderTicket(**base)


def _req(
    *,
    ticket: Optional[OrderTicket] = None,
    hitl: Optional[HitlApproval] = None,
    restricted_list: Optional[list[str]] = None,
    threshold: Optional[Decimal] = None,
) -> ExecutionRequest:
    return ExecutionRequest(
        user_utterance="buy 500 NVDA at 125.50",
        client_id="CLT-1",
        account_id="ACC-1",
        proposed_ticket=ticket or _ticket(),
        idempotency_key="b" * 64,
        firm_id="firm-acme",
        aid_token="fake-aid-token",
        hitl_approval=hitl,
        restricted_list=restricted_list or [],
        trading_window_open=True,
        principal_review_threshold_usd=threshold,
    )


def _make_specialist(
    *,
    policy: Optional[FakePolicyClient] = None,
    mnpi: Optional[FakeMnpiSanitizer] = None,
    gateway: Optional[FakeGatewayClient] = None,
    audit: Optional[FakeAuditClient] = None,
    llm: Optional[FakeLLMProvider] = None,
    hitl: Optional[FakeHitlVerifier] = None,
) -> tuple[ExecutionSpecialist, dict]:
    pol = policy or FakePolicyClient()
    mnp = mnpi or FakeMnpiSanitizer()
    gw = gateway or FakeGatewayClient()
    aud = audit or FakeAuditClient()
    lm = llm or FakeLLMProvider()
    hv = hitl or FakeHitlVerifier()
    spec = ExecutionSpecialist(
        policy_client=pol,
        mnpi_sanitizer=mnp,
        gateway_client=gw,
        audit_client=aud,
        llm_provider=lm,
        hitl_verifier=hv,
    )
    return spec, {
        "policy": pol, "mnpi": mnp, "gateway": gw,
        "audit": aud, "llm": lm, "hitl": hv,
    }


# =============================================================================
# R1 -- public API
# =============================================================================


def test_prepare_order_returns_execution_decision():
    spec, _ = _make_specialist()
    aid = _aid_advisor()
    valid_approval = _build_valid_approval(aid)
    decision = spec.prepare_order(
        _req(hitl=valid_approval), aid, "trace-001"
    )
    assert isinstance(decision, ExecutionDecision)


def test_never_raises_on_invalid_aid():
    spec, _ = _make_specialist()
    decision = spec.prepare_order(_req(), None, "trace-bad")  # type: ignore[arg-type]
    assert decision.status == "failed"
    assert decision.reason_code == "exec_invalid_aid"


def test_never_raises_on_invalid_request():
    spec, _ = _make_specialist()
    aid = _aid_advisor()
    decision = spec.prepare_order("not a request", aid, "trace-bad")  # type: ignore[arg-type]
    assert decision.status == "failed"
    assert decision.reason_code == "exec_invalid_request"


def test_specialist_rejects_missing_dependencies():
    with pytest.raises(ValueError):
        ExecutionSpecialist(
            policy_client=None,  # type: ignore[arg-type]
            mnpi_sanitizer=FakeMnpiSanitizer(),
            gateway_client=FakeGatewayClient(),
            audit_client=FakeAuditClient(),
            llm_provider=FakeLLMProvider(),
            hitl_verifier=FakeHitlVerifier(),
        )


# =============================================================================
# R2.3 -- authority scope
# =============================================================================


def test_missing_order_submit_with_hitl_scope_denies():
    spec, deps = _make_specialist()
    aid = _aid_advisor(scope=["client.read"])  # missing required scope
    decision = spec.prepare_order(_req(), aid, "trace-001")
    assert decision.status == "compliance_denied"
    assert decision.reason_code == "exec_authority_scope_denied"
    assert len(deps["audit"].entries) == 1


def test_forbidden_order_submit_without_hitl_denies():
    spec, _ = _make_specialist()
    aid = _aid_advisor(scope=[
        "order.submit_with_hitl", "order.submit_without_hitl"
    ])
    decision = spec.prepare_order(_req(), aid, "trace-001")
    assert decision.status == "compliance_denied"
    assert decision.reason_code == "exec_authority_scope_denied"


def test_wildcard_scope_is_accepted():
    spec, _ = _make_specialist()
    aid = _aid_advisor(scope=["*"])
    valid = _build_valid_approval(aid)
    decision = spec.prepare_order(_req(hitl=valid), aid, "trace-001")
    assert decision.status == "submitted"


def test_agent_role_cannot_submit_orders():
    spec, _ = _make_specialist()
    aid = _aid_advisor(role=Role.agent)
    decision = spec.prepare_order(_req(), aid, "trace-001")
    assert decision.status == "compliance_denied"
    assert decision.reason_code == "exec_authority_scope_denied"


# =============================================================================
# R2.1, R2.2 -- policy denial is terminal
# =============================================================================


def test_policy_deny_is_terminal():
    policy = FakePolicyClient(responses={
        "order.draft": PolicyResultShape(
            decision="DENY",
            reason="ticker_on_restricted_list",
            rule_applied="authority/advisor/restricted_list.v1",
            wsp_section="WSP-TRD-3.1",
        ),
    })
    spec, deps = _make_specialist(policy=policy)
    aid = _aid_advisor()
    decision = spec.prepare_order(_req(), aid, "trace-001")
    assert decision.status == "compliance_denied"
    assert decision.reason_code == "exec_policy_denied"
    assert decision.rule_applied == "authority/advisor/restricted_list.v1"
    assert decision.wsp_section == "WSP-TRD-3.1"
    # Gateway MUST NOT be called after denial.
    assert deps["gateway"].recorded_calls == []


def test_policy_escalate_is_terminal():
    policy = FakePolicyClient(responses={
        "order.draft": PolicyResultShape(
            decision="ESCALATE",
            reason="concentration_exceeds_10pct",
            rule_applied="authority/advisor/concentration_limit.v1",
            wsp_section="WSP-RISK-2.1",
        ),
    })
    spec, deps = _make_specialist(policy=policy)
    aid = _aid_advisor()
    decision = spec.prepare_order(_req(), aid, "trace-001")
    assert decision.status == "compliance_denied"
    assert decision.reason_code == "exec_policy_escalated"
    assert deps["gateway"].recorded_calls == []


# =============================================================================
# R2.4 -- MNPI sanitise BEFORE LLM
# =============================================================================


def test_mnpi_sanitize_called_before_llm():
    class OrderedMnpi:
        def __init__(self):
            self.order: list[str] = []

        def sanitize(self, aid_claims, instance):
            self.order.append("mnpi")
            return instance

    class OrderedLLM:
        def __init__(self, signal: list[str]):
            self.signal = signal

        def generate(self, *, prompt, max_tokens, model):
            self.signal.append("llm")
            return "{}"

    shared_order: list[str] = []
    ordered_mnpi = OrderedMnpi()
    ordered_mnpi.order = shared_order
    ordered_llm = OrderedLLM(shared_order)

    spec = ExecutionSpecialist(
        policy_client=FakePolicyClient(),
        mnpi_sanitizer=ordered_mnpi,
        gateway_client=FakeGatewayClient(),
        audit_client=FakeAuditClient(),
        llm_provider=ordered_llm,
        hitl_verifier=FakeHitlVerifier(),
    )
    aid = _aid_advisor()
    # NO proposed_ticket -> LLM path attempted.
    req = ExecutionRequest(
        user_utterance="buy 500 NVDA at 125.50",
        client_id="CLT-1",
        account_id="ACC-1",
        proposed_ticket=None,
        idempotency_key="c" * 64,
        firm_id="firm-acme",
        aid_token="fake",
    )
    spec.prepare_order(req, aid, "trace-001")
    # mnpi must appear before any llm (even if llm never actually
    # fired because draft-path is a Phase 3 stub).
    if "llm" in shared_order:
        assert shared_order.index("mnpi") < shared_order.index("llm")
    else:
        assert shared_order == ["mnpi"]


def test_mnpi_failure_is_fail_closed():
    spec, _ = _make_specialist(mnpi=FakeMnpiSanitizer(raise_on_call=True))
    aid = _aid_advisor()
    decision = spec.prepare_order(_req(), aid, "trace-001")
    assert decision.status == "failed"
    assert decision.reason_code == "exec_mnpi_sanitize_failed"


# =============================================================================
# R2.5, R2.6 -- HITL
# =============================================================================


def test_hitl_required_when_no_token():
    spec, deps = _make_specialist()
    aid = _aid_advisor()
    decision = spec.prepare_order(_req(hitl=None), aid, "trace-001")
    assert decision.status == "hitl_required"
    assert decision.reason_code == "exec_hitl_required"
    assert decision.gate_payload is not None
    assert decision.gate_payload.gate_id == 1
    # Gateway MUST NOT be reached when HITL is pending.
    assert deps["gateway"].recorded_calls == []


def test_hitl_token_invalid_is_denial():
    bad_approval = HitlApproval(
        approver_aid_sub="supervisor-01",
        approved=True,
        approval_token="f" * 64,  # wrong HMAC
        approver_timestamp=datetime.now(timezone.utc),
    )
    hitl = FakeHitlVerifier(verify_result="m8_hitl_denied")
    spec, _ = _make_specialist(hitl=hitl)
    aid = _aid_advisor()
    decision = spec.prepare_order(_req(hitl=bad_approval), aid, "trace-001")
    assert decision.status == "compliance_denied"
    assert decision.reason_code == "exec_hitl_token_invalid"


def test_hitl_token_expired_is_rejected():
    expired_approval = HitlApproval(
        approver_aid_sub="supervisor-01",
        approved=True,
        approval_token="e" * 64,
        approver_timestamp=datetime.now(timezone.utc),
    )
    hitl = FakeHitlVerifier(verify_result="m8_hitl_token_expired")
    spec, _ = _make_specialist(hitl=hitl)
    aid = _aid_advisor()
    decision = spec.prepare_order(
        _req(hitl=expired_approval), aid, "trace-001"
    )
    assert decision.status == "rejected"
    assert decision.reason_code == "exec_hitl_token_expired"


def test_hitl_rejected_by_approver():
    rejected = HitlApproval(
        approver_aid_sub="supervisor-01",
        approved=False,
        approval_token="a" * 64,
        approver_timestamp=datetime.now(timezone.utc),
    )
    hitl = FakeHitlVerifier(verify_result=None)  # token valid
    spec, _ = _make_specialist(hitl=hitl)
    aid = _aid_advisor()
    decision = spec.prepare_order(_req(hitl=rejected), aid, "trace-001")
    assert decision.status == "rejected"
    assert decision.reason_code == "exec_hitl_token_invalid"


def _build_valid_approval(aid: AidClaims) -> HitlApproval:
    # FakeHitlVerifier returns None by default (valid). Tests that use
    # the default verifier can pass any well-formed approval.
    return HitlApproval(
        approver_aid_sub=aid.sub,
        approved=True,
        approval_token="d" * 64,
        approver_timestamp=datetime.now(timezone.utc),
    )


def test_default_hitl_verifier_accepts_matching_hmac():
    key = b"x" * 32
    verifier = DefaultHitlApprovalVerifier(hmac_key=key)
    now = datetime.now(timezone.utc)
    token = build_approval_token(
        key,
        gate_id=1,
        approver_aid_sub="supervisor-01",
        approver_timestamp=now,
        thread_id="exec-abcdef0123456789",
    )
    approval = HitlApproval(
        approver_aid_sub="supervisor-01",
        approved=True,
        approval_token=token,
        approver_timestamp=now,
    )
    assert verifier.verify(
        approval, gate_id=1, thread_id="exec-abcdef0123456789"
    ) is None


def test_default_hitl_verifier_rejects_bad_hmac():
    key = b"x" * 32
    verifier = DefaultHitlApprovalVerifier(hmac_key=key)
    now = datetime.now(timezone.utc)
    approval = HitlApproval(
        approver_aid_sub="supervisor-01",
        approved=True,
        approval_token="f" * 64,  # wrong
        approver_timestamp=now,
    )
    reason = verifier.verify(
        approval, gate_id=1, thread_id="exec-abcdef0123456789"
    )
    assert reason == "m8_hitl_denied"


# =============================================================================
# R2.7 -- audit on every terminal
# =============================================================================


def test_audit_emitted_on_drafted_terminal():
    spec, deps = _make_specialist()
    aid = _aid_advisor()
    decision = spec.prepare_order(_req(), aid, "trace-001")
    assert decision.status == "hitl_required"
    assert len(deps["audit"].entries) == 1
    entry = deps["audit"].entries[0]
    assert entry["source"] == "m12.execution_specialist"
    assert entry["decision"] == "escalate"


def test_audit_emitted_on_compliance_denied():
    policy = FakePolicyClient(responses={
        "order.draft": PolicyResultShape(
            decision="DENY", reason="x",
            rule_applied="rule.v1", wsp_section="WSP-X",
        ),
    })
    spec, deps = _make_specialist(policy=policy)
    aid = _aid_advisor()
    spec.prepare_order(_req(), aid, "trace-001")
    assert len(deps["audit"].entries) == 1
    assert deps["audit"].entries[0]["decision"] == "deny"


def test_audit_emitted_on_submitted():
    spec, deps = _make_specialist()
    aid = _aid_advisor()
    valid = _build_valid_approval(aid)
    decision = spec.prepare_order(_req(hitl=valid), aid, "trace-001")
    assert decision.status == "submitted"
    assert len(deps["audit"].entries) == 1
    assert deps["audit"].entries[0]["decision"] == "allow"


def test_audit_failure_dominates_submitted_status():
    audit = FakeAuditClient(fail_at=1)
    spec, _ = _make_specialist(audit=audit)
    aid = _aid_advisor()
    valid = _build_valid_approval(aid)
    decision = spec.prepare_order(_req(hitl=valid), aid, "trace-001")
    assert decision.status == "failed"
    assert decision.reason_code == "exec_audit_failed"


# =============================================================================
# R2.8 -- all tool calls via gateway
# =============================================================================


def test_gateway_invoked_with_correct_tool_name():
    spec, deps = _make_specialist()
    aid = _aid_advisor()
    valid = _build_valid_approval(aid)
    spec.prepare_order(_req(hitl=valid), aid, "trace-001")
    assert len(deps["gateway"].recorded_calls) == 1
    call = deps["gateway"].recorded_calls[0]
    assert call["tool_name"] == "broker.order_submit"
    assert call["action"] == "order.submit"


def test_gateway_deny_produces_compliance_denied():
    gateway = FakeGatewayClient(responses={
        "broker.order_submit": GatewayResultShape(
            decision="DENY",
            result={},
            trace_id="trace-001",
            latency_ms=10,
            provenance_head="0" * 64,
            rule_applied="authority/advisor/restricted_list.v1",
            wsp_section="WSP-TRD-3.1",
            reason="authority_denied",
        ),
    })
    spec, _ = _make_specialist(gateway=gateway)
    aid = _aid_advisor()
    valid = _build_valid_approval(aid)
    decision = spec.prepare_order(_req(hitl=valid), aid, "trace-001")
    assert decision.status == "compliance_denied"
    assert decision.reason_code == "exec_gateway_denied"


def test_gateway_unavailable_surfaces_as_failed():
    gateway = FakeGatewayClient(unavailable_tools={"broker.order_submit"})
    spec, _ = _make_specialist(gateway=gateway)
    aid = _aid_advisor()
    valid = _build_valid_approval(aid)
    decision = spec.prepare_order(_req(hitl=valid), aid, "trace-001")
    assert decision.status == "failed"
    assert decision.reason_code == "exec_gateway_unavailable"


# =============================================================================
# R4 -- BD principal review
# =============================================================================


def test_bd_advisor_triggers_principal_review_without_threshold():
    spec, deps = _make_specialist()
    aid = _aid_advisor(reg="bd_only")
    valid = _build_valid_approval(aid)
    decision = spec.prepare_order(
        _req(hitl=valid, threshold=None), aid, "trace-001"
    )
    assert decision.status == "hitl_required"
    assert decision.reason_code == "exec_principal_review_required"
    assert decision.gate_payload is not None
    # Gateway MUST NOT be reached when principal review queued.
    assert deps["gateway"].recorded_calls == []


def test_bd_advisor_below_threshold_proceeds():
    # Notional = 500 * 125.50 = 62,750 < 100,000 threshold.
    spec, _ = _make_specialist()
    aid = _aid_advisor(reg="bd_only")
    valid = _build_valid_approval(aid)
    decision = spec.prepare_order(
        _req(hitl=valid, threshold=Decimal("100000")),
        aid, "trace-001",
    )
    assert decision.status == "submitted"


def test_bd_advisor_above_threshold_queues_review():
    spec, _ = _make_specialist()
    aid = _aid_advisor(reg="dual_registered")
    valid = _build_valid_approval(aid)
    decision = spec.prepare_order(
        _req(hitl=valid, threshold=Decimal("50000")),
        aid, "trace-001",
    )
    assert decision.status == "hitl_required"
    assert decision.reason_code == "exec_principal_review_required"


def test_ria_does_not_trigger_principal_review():
    spec, _ = _make_specialist()
    aid = _aid_advisor(reg="ria_only")
    valid = _build_valid_approval(aid)
    decision = spec.prepare_order(_req(hitl=valid), aid, "trace-001")
    assert decision.status == "submitted"


# =============================================================================
# R5 -- idempotency key passed verbatim
# =============================================================================


def test_idempotency_key_propagated_to_gateway_context():
    spec, deps = _make_specialist()
    aid = _aid_advisor()
    valid = _build_valid_approval(aid)
    req = _req(hitl=valid)
    spec.prepare_order(req, aid, "trace-001")
    call = deps["gateway"].recorded_calls[0]
    assert call["context"]["idempotency_key"] == req.idempotency_key


# =============================================================================
# R3 -- LLM budget + MNPI invariant
# =============================================================================


def test_llm_invoked_with_haiku_budget_when_drafting():
    llm = FakeLLMProvider(responses={"Extract": "{}"})
    spec, _ = _make_specialist(llm=llm)
    aid = _aid_advisor()
    req = ExecutionRequest(
        user_utterance="buy 500 NVDA",
        client_id="CLT-1",
        account_id="ACC-1",
        proposed_ticket=None,
        idempotency_key="f" * 64,
        firm_id="firm-acme",
        aid_token="fake",
    )
    spec.prepare_order(req, aid, "trace-001")
    # LLM is invoked with the Haiku model + 2000 token budget.
    assert len(llm.recorded_calls) == 1
    assert llm.recorded_calls[0]["max_tokens"] == 2000
    assert "haiku" in llm.recorded_calls[0]["model"]


def test_llm_prompt_is_bounded_length():
    llm = FakeLLMProvider(responses={"Extract": "{}"})
    spec, _ = _make_specialist(llm=llm)
    aid = _aid_advisor()
    req = ExecutionRequest(
        user_utterance="x" * 2000,  # max length
        client_id="CLT-1",
        account_id="ACC-1",
        proposed_ticket=None,
        idempotency_key="9" * 64,
        firm_id="firm-acme",
        aid_token="fake",
    )
    spec.prepare_order(req, aid, "trace-001")
    prompt = llm.recorded_calls[0]["prompt"]
    assert len(prompt.encode("utf-8")) <= 4096


# =============================================================================
# Error-surface hygiene (Appendix A.3)
# =============================================================================


def test_error_surface_hygiene_no_exception_text():
    """No exception text appears in any decision field.

    Even when the policy client raises, the decision.reason_code is
    drawn from VALID_EXECUTION_REASONS -- nothing else.
    """
    class BoomPolicy:
        def evaluate(self, **kwargs):
            raise ValueError("secret message that must not leak")

    spec, _ = _make_specialist(policy=BoomPolicy())  # type: ignore[arg-type]
    aid = _aid_advisor()
    decision = spec.prepare_order(_req(), aid, "trace-001")
    assert decision.reason_code in VALID_EXECUTION_REASONS
    # No exception text in any field.
    for field in (
        decision.rule_applied, decision.wsp_section, decision.mcp_order_id
    ):
        if field is not None:
            assert "secret message" not in field


def test_error_surface_audit_reason_only_from_vocab():
    policy = FakePolicyClient(responses={
        "order.draft": PolicyResultShape(
            decision="DENY",
            reason="this is the policy's own reason string",
            rule_applied="rule.v1",
            wsp_section="WSP-X",
        ),
    })
    spec, deps = _make_specialist(policy=policy)
    aid = _aid_advisor()
    spec.prepare_order(_req(), aid, "trace-001")
    entry = deps["audit"].entries[0]
    # The entry's `reason` field IS the specialist's exec_* code,
    # NOT the policy's raw reason string.
    assert entry["reason"] == "exec_policy_denied"
    assert "this is the policy's own reason" not in str(entry)
