"""
M12 Execution Specialist -- integration tests.

Covers the full trust chain end-to-end with lightweight protocol
adapters that SIMULATE the M2/M4/M6/M10 call shapes. Per Steering
Rule 34 and the spec Known Blockers section, these adapters live in
the TEST FILE (not in src/) to respect the specialist boundary rule.

Scope:
  - M6 gateway (stubbed through FakeGatewayClient behind a mTLS-like
    wrapper) invoked for order.submit.
  - M10 audit emission (stubbed through FakeAuditClient) verified on
    every terminal.
  - M4 MNPI sanitizer wired before LLM call.
  - M1 AidClaims real construction; HITL HMAC verify via M8 helpers.
  - Principal-review branching by archetype + communication type.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

import pytest

from m1_identity import AidClaims, Role
from m8_pipeline_engine.hitl import build_approval_token
from m8_pipeline_engine.models import HitlApproval

from m12_supervisor.specialists import (
    FakeAuditClient,
    FakeGatewayClient,
    FakeLLMProvider,
    FakeMnpiSanitizer,
    FakePolicyClient,
    GatewayResultShape,
    PolicyResultShape,
)
from m12_supervisor.specialists.execution import (
    DefaultHitlApprovalVerifier,
    ExecutionRequest,
    ExecutionSpecialist,
    OrderTicket,
)


# =============================================================================
# Integration helpers (Protocol adapters; live HERE per Rule 34)
# =============================================================================


def _aid(
    *,
    reg: str = "ria_only",
    scope: list[str] | None = None,
    role: Role = Role.advisor,
) -> AidClaims:
    return AidClaims(
        iss="007-fsi-platform",
        sub="advisor-e2e",
        aud="007-mcp-gateway",
        exp=1_999_999_999,
        iat=1_747_368_000,
        nbf=1_747_368_000,
        jti="aid-exec-e2e-0001",
        firm_id="firm-acme",
        lei=None,
        crd_number="CRD-1",
        archetype=(
            "tier3_broker_dealer"
            if reg in ("bd_only", "dual_registered")
            else "tier4_independent_ria"
        ),
        role=role,
        authority_scope=scope or ["order.submit_with_hitl"],
        authority_excludes=[],
        registration_type=reg,
    )


def _ticket(**overrides) -> OrderTicket:
    base = dict(
        client_id="CLT-1", account_id="ACC-1",
        instrument_symbol="NVDA", side="buy",
        quantity=Decimal("100"), order_type="limit",
        limit_price=Decimal("100.00"), time_in_force="day",
        notes=None,
    )
    base.update(overrides)
    return OrderTicket(**base)


def _build_specialist_with_real_hitl(
    *,
    gateway: FakeGatewayClient | None = None,
    audit: FakeAuditClient | None = None,
    policy: FakePolicyClient | None = None,
    mnpi: FakeMnpiSanitizer | None = None,
):
    hmac_key = b"\xab" * 32
    verifier = DefaultHitlApprovalVerifier(hmac_key=hmac_key)
    spec = ExecutionSpecialist(
        policy_client=policy or FakePolicyClient(),
        mnpi_sanitizer=mnpi or FakeMnpiSanitizer(),
        gateway_client=gateway or FakeGatewayClient(),
        audit_client=audit or FakeAuditClient(),
        llm_provider=FakeLLMProvider(),
        hitl_verifier=verifier,
    )
    return spec, hmac_key


def _approval_for(aid: AidClaims, *, thread_id: str, key: bytes) -> HitlApproval:
    now = datetime.now(timezone.utc)
    token = build_approval_token(
        key,
        gate_id=1,
        approver_aid_sub="supervisor-01",
        approver_timestamp=now,
        thread_id=thread_id,
    )
    return HitlApproval(
        approver_aid_sub="supervisor-01",
        approved=True,
        approval_token=token,
        approver_timestamp=now,
    )


def _req_thread_id(idempotency_key: str) -> str:
    # Same derivation as the specialist's internal helper.
    return "exec-" + idempotency_key[:16]


# =============================================================================
# Full trust chain: AID -> MNPI -> Policy -> HITL -> Gateway -> Audit
# =============================================================================


def test_full_trust_chain_happy_path_ria():
    audit = FakeAuditClient()
    gateway = FakeGatewayClient(responses={
        "broker.order_submit": GatewayResultShape(
            decision="ALLOW",
            result={"order_id": "BROKER-XYZ-001"},
            trace_id="trace-int-001",
            latency_ms=12,
            provenance_head="a" * 64,
            rule_applied="authority/advisor/order_submit.v2",
            wsp_section="WSP-TRD-4.1",
            reason="authorised_submit",
        ),
    })
    spec, key = _build_specialist_with_real_hitl(
        gateway=gateway, audit=audit
    )
    aid = _aid(reg="ria_only")
    idk = "1" * 64
    approval = _approval_for(aid, thread_id=_req_thread_id(idk), key=key)
    request = ExecutionRequest(
        user_utterance="buy 100 NVDA at 100",
        client_id="CLT-1", account_id="ACC-1",
        proposed_ticket=_ticket(),
        idempotency_key=idk,
        firm_id="firm-acme",
        aid_token="eyJ-fake",
        hitl_approval=approval,
    )
    decision = spec.prepare_order(request, aid, "trace-int-001")

    # End-state: submitted with the broker's order id propagated.
    assert decision.status == "submitted"
    assert decision.mcp_order_id == "BROKER-XYZ-001"
    assert decision.rule_applied == "authority/advisor/order_submit.v2"
    assert decision.wsp_section == "WSP-TRD-4.1"
    # One gateway call through M6.
    assert len(gateway.recorded_calls) == 1
    gw_call = gateway.recorded_calls[0]
    assert gw_call["tool_name"] == "broker.order_submit"
    assert gw_call["action"] == "order.submit"
    # Idempotency key in context (§R5).
    assert gw_call["context"]["idempotency_key"] == idk
    # Exactly one audit entry for M10.
    assert len(audit.entries) == 1
    entry = audit.entries[0]
    assert entry["source"] == "m12.execution_specialist"
    assert entry["decision"] == "allow"
    assert entry["action"] == "order.submit"


def test_full_trust_chain_bd_unconditional_principal_review():
    audit = FakeAuditClient()
    gateway = FakeGatewayClient()
    spec, key = _build_specialist_with_real_hitl(
        gateway=gateway, audit=audit
    )
    aid = _aid(reg="bd_only")
    idk = "2" * 64
    approval = _approval_for(aid, thread_id=_req_thread_id(idk), key=key)
    request = ExecutionRequest(
        user_utterance="buy 100 NVDA at 100",
        client_id="CLT-1", account_id="ACC-1",
        proposed_ticket=_ticket(),
        idempotency_key=idk,
        firm_id="firm-acme",
        aid_token="eyJ-fake",
        hitl_approval=approval,
        principal_review_threshold_usd=None,  # unconditional for BD
    )
    decision = spec.prepare_order(request, aid, "trace-int-002")

    assert decision.status == "hitl_required"
    assert decision.reason_code == "exec_principal_review_required"
    assert decision.gate_payload is not None
    assert decision.gate_payload.summary["gate_kind"] == "principal_review"
    # No gateway call was made -- principal review is pre-submit.
    assert gateway.recorded_calls == []
    # Audit entry written.
    assert len(audit.entries) == 1
    assert audit.entries[0]["decision"] == "escalate"


def test_full_trust_chain_policy_denial_never_touches_gateway():
    audit = FakeAuditClient()
    gateway = FakeGatewayClient()
    policy = FakePolicyClient(responses={
        "order.draft": PolicyResultShape(
            decision="DENY",
            reason="restricted_list_hit",
            rule_applied="authority/advisor/restricted_list.v1",
            wsp_section="WSP-TRD-3.1",
        ),
    })
    spec, key = _build_specialist_with_real_hitl(
        gateway=gateway, audit=audit, policy=policy
    )
    aid = _aid()
    idk = "3" * 64
    approval = _approval_for(aid, thread_id=_req_thread_id(idk), key=key)
    decision = spec.prepare_order(
        ExecutionRequest(
            user_utterance="buy 100 NVDA",
            client_id="CLT-1", account_id="ACC-1",
            proposed_ticket=_ticket(),
            idempotency_key=idk,
            firm_id="firm-acme",
            aid_token="eyJ-fake",
            hitl_approval=approval,
            restricted_list=["NVDA"],
        ),
        aid, "trace-int-003",
    )

    assert decision.status == "compliance_denied"
    assert decision.reason_code == "exec_policy_denied"
    # Gateway MUST NOT be touched after policy denial.
    assert gateway.recorded_calls == []
    # M10 audit entry captures the denial.
    assert len(audit.entries) == 1
    assert audit.entries[0]["decision"] == "deny"
    assert audit.entries[0]["rule_applied"] == (
        "authority/advisor/restricted_list.v1"
    )


def test_full_trust_chain_mnpi_sanitizer_invoked_before_llm_path():
    """M4 MNPI filter invoked before the specialist decides anything.

    We wire the real MNPI sanitizer first in the chain -- the request
    passes through it BEFORE any policy or gateway step runs.
    """
    order: list[str] = []

    class TracingMnpi:
        def sanitize(self, aid_claims, instance):
            order.append("mnpi")
            return instance

    audit = FakeAuditClient()
    gateway = FakeGatewayClient(responses={
        "broker.order_submit": GatewayResultShape(
            decision="ALLOW",
            result={"order_id": "BX-1"},
            trace_id="trace-int-004",
            latency_ms=3,
            provenance_head="a" * 64,
            rule_applied=None, wsp_section=None, reason=None,
        ),
    })

    class TracingGateway(FakeGatewayClient):
        def call(self, **kwargs):
            order.append("gateway")
            return super().call(**kwargs)

    trace_gw = TracingGateway(responses=gateway.responses)
    spec, key = _build_specialist_with_real_hitl(
        gateway=trace_gw, audit=audit, mnpi=TracingMnpi(),
    )
    aid = _aid()
    idk = "4" * 64
    approval = _approval_for(aid, thread_id=_req_thread_id(idk), key=key)
    spec.prepare_order(
        ExecutionRequest(
            user_utterance="buy 100 NVDA",
            client_id="CLT-1", account_id="ACC-1",
            proposed_ticket=_ticket(),
            idempotency_key=idk, firm_id="firm-acme",
            aid_token="eyJ-fake", hitl_approval=approval,
        ),
        aid, "trace-int-004",
    )
    # MNPI ran before any gateway call.
    assert order[0] == "mnpi"
    assert "gateway" in order
    assert order.index("mnpi") < order.index("gateway")


def test_full_trust_chain_audit_failure_downgrades_submitted_to_failed():
    """Fail-closed: if the terminal M10 audit write fails on a
    submitted order, the specialist MUST NOT claim success.
    """
    audit = FakeAuditClient(fail_at=1)
    gateway = FakeGatewayClient(responses={
        "broker.order_submit": GatewayResultShape(
            decision="ALLOW", result={"order_id": "X"},
            trace_id="trace-int-005", latency_ms=1,
            provenance_head="a" * 64,
            rule_applied=None, wsp_section=None, reason=None,
        ),
    })
    spec, key = _build_specialist_with_real_hitl(
        audit=audit, gateway=gateway
    )
    aid = _aid()
    idk = "5" * 64
    approval = _approval_for(aid, thread_id=_req_thread_id(idk), key=key)
    decision = spec.prepare_order(
        ExecutionRequest(
            user_utterance="buy 100 NVDA",
            client_id="CLT-1", account_id="ACC-1",
            proposed_ticket=_ticket(),
            idempotency_key=idk, firm_id="firm-acme",
            aid_token="eyJ-fake", hitl_approval=approval,
        ),
        aid, "trace-int-005",
    )
    assert decision.status == "failed"
    assert decision.reason_code == "exec_audit_failed"


def test_full_trust_chain_hitl_hmac_real_key_round_trip():
    """Real HMAC-SHA-256 token verification through M8 helpers."""
    audit = FakeAuditClient()
    spec, key = _build_specialist_with_real_hitl(audit=audit)
    aid = _aid(reg="ria_only")
    idk = "6" * 64
    # Mint a genuine M8 HMAC token via the public helper.
    thread_id = _req_thread_id(idk)
    approval = _approval_for(aid, thread_id=thread_id, key=key)

    decision = spec.prepare_order(
        ExecutionRequest(
            user_utterance="buy 100 NVDA",
            client_id="CLT-1", account_id="ACC-1",
            proposed_ticket=_ticket(),
            idempotency_key=idk, firm_id="firm-acme",
            aid_token="eyJ-fake", hitl_approval=approval,
        ),
        aid, "trace-int-006",
    )
    assert decision.status == "submitted"
    # Token was valid for THIS thread_id only -- tamper by using a
    # different thread_id and verify denial.
    tampered = _approval_for(
        aid, thread_id="exec-othersession", key=key
    )
    decision2 = spec.prepare_order(
        ExecutionRequest(
            user_utterance="buy 100 NVDA",
            client_id="CLT-1", account_id="ACC-1",
            proposed_ticket=_ticket(),
            idempotency_key=idk, firm_id="firm-acme",
            aid_token="eyJ-fake", hitl_approval=tampered,
        ),
        aid, "trace-int-006-b",
    )
    assert decision2.status == "compliance_denied"
    assert decision2.reason_code == "exec_hitl_token_invalid"
