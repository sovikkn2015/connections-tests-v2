"""
M12 Onboarding Specialist -- integration tests.

Covers the full trust chain end-to-end with Protocol adapters living
in this test file (Rule 34: integration tests may import real modules
at the boundary; adapters bridge shapes).

Scope:
  - M1 AidClaims real construction.
  - M4 MNPI sanitizer wired; raw MNPI never leaves the specialist.
  - KYC adapter (StubKycAdapter + custom adapters) called with the
    vendor-required hashed tax_id.
  - M10 audit (FakeAuditClient) verified on every terminal AND for
    BSA §326 alerts on CIP failure.
  - Principal review branching by archetype (bd_only /
    dual_registered) when kind = "bd_advisor" (Rule 17).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest

from m1_identity import AidClaims, Role

from m12_supervisor.specialists import (
    FakeAuditClient,
    FakeHitlVerifier,
    FakeLLMProvider,
    FakeMnpiSanitizer,
    FakePolicyClient,
)
from m12_supervisor.specialists.onboarding import (
    KycAdapterProtocol,
    KycVendorResult,
    OnboardingRequest,
    OnboardingSpecialist,
    StubKycAdapter,
)


# =============================================================================
# Helpers
# =============================================================================


def _aid(
    *,
    reg: str = "ria_only",
    scope: list[str] | None = None,
    role: Role = Role.advisor,
) -> AidClaims:
    archetype_map = {
        "ria_only": "tier4_independent_ria",
        "bd_only": "tier3_broker_dealer",
        "dual_registered": "tier3_broker_dealer",
    }
    return AidClaims(
        iss="007-fsi-platform",
        sub="advisor-onb-e2e",
        aud="007-mcp-gateway",
        exp=1_999_999_999,
        iat=1_747_368_000,
        nbf=1_747_368_000,
        jti="aid-onb-e2e-0001",
        firm_id="firm-acme",
        lei=None,
        crd_number="CRD-1",
        archetype=archetype_map.get(reg, "tier4_independent_ria"),
        role=role,
        authority_scope=scope or ["onboarding.start"],
        authority_excludes=[],
        registration_type=reg,
    )


def _request(
    *,
    kind: str = "retail_client",
    legal_name: str = "Jane Doe",
    tax_id: str = "123-45-6789",
    address: str = "123 Main Street, Apt 4, Seattle, WA 98101",
    country: str = "US",
    client_ref: str = "CLT-E2E-0001",
    dob: date | None = None,
) -> OnboardingRequest:
    return OnboardingRequest(
        kind=kind,  # type: ignore[arg-type]
        client_reference=client_ref,
        legal_name=legal_name,
        date_of_birth=dob or date(1985, 6, 15),
        residential_address=address,
        tax_id=tax_id,
        country_code=country,
        firm_id="firm-acme",
        aid_token="eyJ-fake-onb",
    )


def _build_spec(
    *,
    audit: FakeAuditClient | None = None,
    mnpi: FakeMnpiSanitizer | None = None,
    kyc: KycAdapterProtocol | None = None,
    hitl: FakeHitlVerifier | None = None,
) -> tuple[OnboardingSpecialist, dict]:
    aud = audit or FakeAuditClient()
    mnp = mnpi or FakeMnpiSanitizer()
    ky = kyc or StubKycAdapter()
    hv = hitl or FakeHitlVerifier()
    spec = OnboardingSpecialist(
        policy_client=FakePolicyClient(),
        mnpi_sanitizer=mnp,
        audit_client=aud,
        llm_provider=FakeLLMProvider(),
        kyc_adapter=ky,
        hitl_verifier=hv,
    )
    return spec, {"audit": aud, "mnpi": mnp, "kyc": ky, "hitl": hv}


# =============================================================================
# Full trust chain happy path: retail RIA
# =============================================================================


def test_full_trust_chain_happy_path_retail_ria():
    spec, deps = _build_spec()
    aid = _aid(reg="ria_only")
    decision = spec.start_onboarding(
        _request(kind="retail_client"), aid, "trace-onb-001"
    )
    assert decision.status == "cip_passed"
    assert decision.kyc_result is not None
    assert decision.kyc_result.cip.passed is True
    assert decision.kyc_result.vendor is not None
    assert decision.kyc_result.vendor.vendor_status == "approved"
    # Exactly one M10 terminal audit row.
    audit_entries = deps["audit"].entries
    assert len(audit_entries) == 1
    assert audit_entries[0]["event_type"] == "onboarding.start"
    assert audit_entries[0]["decision"] == "allow"


# =============================================================================
# Full trust chain: BD advisor principal review branching (Rule 17)
# =============================================================================


def test_full_trust_chain_bd_advisor_principal_review():
    spec, deps = _build_spec()
    aid = _aid(reg="bd_only")
    decision = spec.start_onboarding(
        _request(kind="bd_advisor", client_ref="BD-E2E-001"),
        aid, "trace-onb-002",
    )
    assert decision.status == "principal_review_queued"
    assert decision.reason_code == "onb_bd_principal_review"
    assert decision.gate_payload is not None
    assert decision.gate_payload.summary["gate_kind"] == (
        "onboarding_principal_review"
    )
    # Audit decision is "escalate".
    audit_entries = [
        e for e in deps["audit"].entries
        if e.get("event_type") == "onboarding.start"
    ]
    assert len(audit_entries) == 1
    assert audit_entries[0]["decision"] == "escalate"


def test_full_trust_chain_dual_registered_triggers_principal_review():
    spec, deps = _build_spec()
    aid = _aid(reg="dual_registered")
    decision = spec.start_onboarding(
        _request(kind="bd_advisor"),
        aid, "trace-onb-002b",
    )
    assert decision.status == "principal_review_queued"


# =============================================================================
# Full trust chain: CIP failure path emits BSA 326 alert
# =============================================================================


def test_full_trust_chain_cip_failure_emits_bsa_326_alert_and_terminal():
    spec, deps = _build_spec()
    aid = _aid()
    decision = spec.start_onboarding(
        _request(legal_name="A"),  # name too short -> CIP fail
        aid, "trace-onb-003",
    )
    assert decision.status == "cip_failed"
    assert decision.bsa_326_alert_emitted is True
    # Two audit entries: one BSA alert + one terminal row.
    entries = deps["audit"].entries
    events = [e.get("event_type") for e in entries]
    assert "bsa_326_cip_failure" in events
    assert "onboarding.start" in events
    # BSA alert must NOT contain MNPI values.
    bsa_alert = next(
        e for e in entries if e["event_type"] == "bsa_326_cip_failure"
    )
    blob = str(bsa_alert)
    assert "123-45-6789" not in blob
    assert "1985-06-15" not in blob


# =============================================================================
# Full trust chain: KYC vendor denial
# =============================================================================


def test_full_trust_chain_kyc_vendor_denial():
    """Denial from the vendor -> cip_failed + BSA alert."""

    class AlwaysDenyVendor(StubKycAdapter):
        def verify_identity(self, *, name, dob, address, tax_id_hash):
            return KycVendorResult(
                vendor_name="fraud-net",
                vendor_status="denied",
                vendor_reference_id="DENY-01",
            )

        def screen_sanctions(self, **kwargs):
            return False

    spec, deps = _build_spec(kyc=AlwaysDenyVendor())
    decision = spec.start_onboarding(
        _request(), _aid(), "trace-onb-004"
    )
    assert decision.status == "cip_failed"
    assert decision.reason_code == "onb_kyc_vendor_denied"
    # BSA alert AND terminal audit both present.
    events = [
        e.get("event_type") for e in deps["audit"].entries
    ]
    assert "bsa_326_cip_failure" in events
    assert "onboarding.start" in events


# =============================================================================
# Full trust chain: sanctions hit takes precedence
# =============================================================================


def test_full_trust_chain_sanctions_hit_path():
    spec, deps = _build_spec()
    aid = _aid()
    # StubKycAdapter flags "KP" as sanctioned.
    decision = spec.start_onboarding(
        _request(country="KP"), aid, "trace-onb-005"
    )
    assert decision.status == "cip_failed"
    assert decision.kyc_result.sanctions_hit is True
    # BSA alert written.
    events = [e.get("event_type") for e in deps["audit"].entries]
    assert "bsa_326_cip_failure" in events


# =============================================================================
# Full trust chain: MNPI sanitizer invoked before any side-effect
# =============================================================================


def test_full_trust_chain_mnpi_invoked_before_kyc_vendor():
    """M4 MNPI sanitizer runs BEFORE the KYC adapter is called.

    This enforces Rule 7 for the onboarding path: vendor calls
    receive sanitized-or-hashed inputs only.
    """
    order: list[str] = []

    class TracingMnpi:
        def sanitize(self, aid_claims, instance):
            order.append("mnpi")
            return instance

    class TracingKyc(StubKycAdapter):
        def verify_identity(self, **kwargs):
            order.append("kyc_verify")
            return super().verify_identity(**kwargs)

        def screen_sanctions(self, **kwargs):
            order.append("kyc_sanctions")
            return super().screen_sanctions(**kwargs)

    spec, _ = _build_spec(mnpi=TracingMnpi(), kyc=TracingKyc())
    decision = spec.start_onboarding(
        _request(), _aid(), "trace-onb-006"
    )
    assert decision.status == "cip_passed"
    assert order[0] == "mnpi"
    # Sanctions must run before vendor verify (Appendix A.4).
    assert order.index("kyc_sanctions") < order.index("kyc_verify")


# =============================================================================
# Full trust chain: audit failure fail-closed on success path
# =============================================================================


def test_full_trust_chain_audit_failure_downgrades_to_failed():
    """If M10 is unavailable on a would-be success, the decision is
    flipped to failed / onb_audit_failed (fail-closed).
    """
    audit = FakeAuditClient(fail_at=1)
    spec, _ = _build_spec(audit=audit)
    decision = spec.start_onboarding(
        _request(), _aid(), "trace-onb-007"
    )
    assert decision.status == "failed"
    assert decision.reason_code == "onb_audit_failed"
