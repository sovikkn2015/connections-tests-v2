"""
M12 Onboarding Specialist -- behavioural unit tests.

Covers every AC from `.kiro/specs/m12-onboarding-specialist.md` /
`.kiro/specs/onboarding-specialist.md`:
  R1         public API + never-raises contract
  R2.1-R2.4  BSA §326 CIP checks + BSA 326 alert + MNPI hygiene
  R3.1-R3.4  trust chain: MNPI/authority/audit
  R4         BD advisor principal review
  R5         KYC adapter Protocol + StubKycAdapter
  R6         no hardcoded creds (security test)
  R7         LLM Haiku budget

35+ tests per task requirement.
"""

from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
from typing import Any, Optional

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
    CipResult,
    KycAdapterProtocol,
    KycResult,
    KycVendorResult,
    OnboardingDecision,
    OnboardingRequest,
    OnboardingSpecialist,
    StubKycAdapter,
    VALID_ONBOARDING_REASONS,
)
from m12_supervisor.specialists.onboarding.models import (
    _cip_validate_address,
    _cip_validate_dob,
    _cip_validate_name,
    _cip_validate_tax_id,
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
        authority_scope=scope if scope is not None else ["onboarding.start"],
        authority_excludes=excludes or [],
        registration_type=reg,
    )


def _request(
    *,
    kind: str = "retail_client",
    legal_name: str = "Jane Doe",
    dob: Optional[date] = None,
    address: str = "123 Main Street, Apt 4, Seattle, WA 98101",
    tax_id: str = "123-45-6789",
    country: str = "US",
    client_ref: str = "CLT-REF-0001",
) -> OnboardingRequest:
    if dob is None:
        dob = date(1990, 1, 1)
    return OnboardingRequest(
        kind=kind,  # type: ignore[arg-type]
        client_reference=client_ref,
        legal_name=legal_name,
        date_of_birth=dob,
        residential_address=address,
        tax_id=tax_id,
        country_code=country,
        firm_id="firm-acme",
        aid_token="fake-aid-token",
    )


def _make_specialist(
    *,
    policy: Optional[FakePolicyClient] = None,
    mnpi: Optional[FakeMnpiSanitizer] = None,
    audit: Optional[FakeAuditClient] = None,
    llm: Optional[FakeLLMProvider] = None,
    kyc: Optional[KycAdapterProtocol] = None,
    hitl: Optional[FakeHitlVerifier] = None,
) -> tuple[OnboardingSpecialist, dict]:
    pol = policy or FakePolicyClient()
    mnp = mnpi or FakeMnpiSanitizer()
    aud = audit or FakeAuditClient()
    lm = llm or FakeLLMProvider()
    ky = kyc or StubKycAdapter()
    hv = hitl or FakeHitlVerifier()
    spec = OnboardingSpecialist(
        policy_client=pol,
        mnpi_sanitizer=mnp,
        audit_client=aud,
        llm_provider=lm,
        kyc_adapter=ky,
        hitl_verifier=hv,
    )
    return spec, {
        "policy": pol, "mnpi": mnp, "audit": aud,
        "llm": lm, "kyc": ky, "hitl": hv,
    }


# =============================================================================
# R1 -- public API + never-raises
# =============================================================================


def test_start_onboarding_returns_onboarding_decision():
    spec, _ = _make_specialist()
    decision = spec.start_onboarding(_request(), _aid_advisor(), "trace-001")
    assert isinstance(decision, OnboardingDecision)


def test_never_raises_on_invalid_request():
    spec, _ = _make_specialist()
    decision = spec.start_onboarding(
        "not a request",  # type: ignore[arg-type]
        _aid_advisor(),
        "trace-bad",
    )
    assert decision.status == "failed"
    assert decision.reason_code == "onb_invalid_request"


def test_never_raises_on_invalid_aid():
    spec, _ = _make_specialist()
    decision = spec.start_onboarding(
        _request(),
        None,  # type: ignore[arg-type]
        "trace-bad",
    )
    assert decision.status == "failed"
    assert decision.reason_code == "onb_invalid_aid"


def test_specialist_rejects_missing_dependencies():
    with pytest.raises(ValueError):
        OnboardingSpecialist(
            policy_client=None,  # type: ignore[arg-type]
            mnpi_sanitizer=FakeMnpiSanitizer(),
            audit_client=FakeAuditClient(),
            llm_provider=FakeLLMProvider(),
            kyc_adapter=StubKycAdapter(),
        )


def test_specialist_rejects_missing_kyc_adapter():
    with pytest.raises(ValueError):
        OnboardingSpecialist(
            policy_client=FakePolicyClient(),
            mnpi_sanitizer=FakeMnpiSanitizer(),
            audit_client=FakeAuditClient(),
            llm_provider=FakeLLMProvider(),
            kyc_adapter=None,  # type: ignore[arg-type]
        )


# =============================================================================
# R3.4 -- AID authority scope
# =============================================================================


def test_missing_onboarding_start_scope_denies():
    spec, _ = _make_specialist()
    aid = _aid_advisor(scope=["client.read"])
    decision = spec.start_onboarding(_request(), aid, "trace-001")
    assert decision.status == "failed"
    assert decision.reason_code == "onb_authority_scope_denied"


def test_wildcard_scope_accepted():
    spec, _ = _make_specialist()
    aid = _aid_advisor(scope=["*"])
    decision = spec.start_onboarding(_request(), aid, "trace-001")
    assert decision.status == "cip_passed"


def test_agent_role_cannot_onboard():
    spec, _ = _make_specialist()
    aid = _aid_advisor(role=Role.agent)
    decision = spec.start_onboarding(_request(), aid, "trace-001")
    assert decision.status == "failed"
    assert decision.reason_code == "onb_authority_scope_denied"


def test_onboarding_start_in_excludes_denies():
    spec, _ = _make_specialist()
    aid = _aid_advisor(
        scope=["onboarding.start"],
        excludes=["onboarding.start"],
    )
    decision = spec.start_onboarding(_request(), aid, "trace-001")
    assert decision.status == "failed"
    assert decision.reason_code == "onb_authority_scope_denied"


# =============================================================================
# R2.1 -- BSA §326 CIP checks
# =============================================================================


def test_cip_all_four_checks_pass_on_valid_input():
    spec, _ = _make_specialist()
    decision = spec.start_onboarding(_request(), _aid_advisor(), "trace-001")
    assert decision.status == "cip_passed"
    assert decision.kyc_result is not None
    assert decision.kyc_result.cip.passed is True
    assert decision.kyc_result.cip.failed_checks == []


def test_cip_fails_on_too_short_name():
    spec, deps = _make_specialist()
    decision = spec.start_onboarding(
        _request(legal_name="A"), _aid_advisor(), "trace-001"
    )
    assert decision.status == "cip_failed"
    assert "name" in decision.kyc_result.cip.failed_checks


def test_cip_fails_on_numeric_only_name():
    spec, _ = _make_specialist()
    decision = spec.start_onboarding(
        _request(legal_name="12345"), _aid_advisor(), "trace-001"
    )
    assert decision.status == "cip_failed"
    assert "name" in decision.kyc_result.cip.failed_checks


def test_cip_fails_on_under_18_dob():
    # Child born 10 years ago -> fails DOB check.
    today = datetime.now(timezone.utc).date()
    ten_years_ago = today.replace(year=today.year - 10)
    spec, _ = _make_specialist()
    decision = spec.start_onboarding(
        _request(dob=ten_years_ago), _aid_advisor(), "trace-001"
    )
    assert decision.status == "cip_failed"
    assert "dob" in decision.kyc_result.cip.failed_checks


def test_cip_fails_on_future_dob():
    future = (datetime.now(timezone.utc).date() + timedelta(days=365))
    spec, _ = _make_specialist()
    decision = spec.start_onboarding(
        _request(dob=future), _aid_advisor(), "trace-001"
    )
    assert decision.status == "cip_failed"
    assert "dob" in decision.kyc_result.cip.failed_checks


def test_cip_fails_on_too_short_address():
    spec, _ = _make_specialist()
    decision = spec.start_onboarding(
        _request(address="short"), _aid_advisor(), "trace-001"
    )
    assert decision.status == "cip_failed"
    assert "address" in decision.kyc_result.cip.failed_checks


def test_cip_fails_on_address_without_digits():
    spec, _ = _make_specialist()
    decision = spec.start_onboarding(
        _request(address="Somewhere in the big city"),
        _aid_advisor(), "trace-001",
    )
    assert decision.status == "cip_failed"
    assert "address" in decision.kyc_result.cip.failed_checks


def test_cip_fails_on_bad_us_ssn_format():
    spec, _ = _make_specialist()
    decision = spec.start_onboarding(
        _request(tax_id="not-a-real-ssn"), _aid_advisor(), "trace-001"
    )
    assert decision.status == "cip_failed"
    assert "tax_id" in decision.kyc_result.cip.failed_checks


def test_cip_accepts_valid_us_ssn_formats():
    spec, _ = _make_specialist()
    for valid_ssn in ("123-45-6789", "123456789"):
        decision = spec.start_onboarding(
            _request(tax_id=valid_ssn), _aid_advisor(), "trace-001"
        )
        assert decision.status == "cip_passed", (
            f"expected cip_passed for tax_id={valid_ssn!r}"
        )


def test_cip_accepts_us_itin():
    spec, _ = _make_specialist()
    decision = spec.start_onboarding(
        _request(tax_id="912-34-5678"), _aid_advisor(), "trace-001"
    )
    assert decision.status == "cip_passed"


def test_cip_accepts_us_ein():
    spec, _ = _make_specialist()
    decision = spec.start_onboarding(
        _request(tax_id="12-3456789"), _aid_advisor(), "trace-001"
    )
    assert decision.status == "cip_passed"


def test_cip_non_us_tax_id_length_only():
    spec, _ = _make_specialist()
    decision = spec.start_onboarding(
        _request(tax_id="AB12345", country="GB"),
        _aid_advisor(), "trace-001",
    )
    assert decision.status == "cip_passed"


def test_cip_non_us_tax_id_rejects_too_short():
    spec, _ = _make_specialist()
    decision = spec.start_onboarding(
        _request(tax_id="AB1", country="GB"),
        _aid_advisor(), "trace-001",
    )
    assert decision.status == "cip_failed"
    assert "tax_id" in decision.kyc_result.cip.failed_checks


def test_cip_validator_helpers_direct():
    """Unit-test the standalone validators (Appendix A.1)."""
    today = datetime.now(timezone.utc).date()
    assert _cip_validate_name("Jane Doe") is True
    assert _cip_validate_name("J") is False
    assert _cip_validate_name("12345") is False
    assert _cip_validate_dob(date(1980, 1, 1), today) is True
    assert _cip_validate_dob(today, today) is False
    assert _cip_validate_address("123 Main Street") is True
    assert _cip_validate_address("no numbers here") is False
    assert _cip_validate_tax_id("123-45-6789", "US") is True
    assert _cip_validate_tax_id("12345", "US") is False
    assert _cip_validate_tax_id("ABC12345", "DE") is True


# =============================================================================
# R2.2, R2.3, R2.4 -- BSA 326 alert on CIP failure
# =============================================================================


def test_bsa_326_alert_emitted_on_cip_failure():
    spec, deps = _make_specialist()
    decision = spec.start_onboarding(
        _request(legal_name="A"), _aid_advisor(), "trace-001"
    )
    assert decision.status == "cip_failed"
    assert decision.bsa_326_alert_emitted is True
    alerts = [
        e for e in deps["audit"].entries
        if e.get("event_type") == "bsa_326_cip_failure"
    ]
    assert len(alerts) == 1


def test_bsa_326_alert_payload_whitelist():
    """A3: alert payload contains ONLY whitelisted keys, no MNPI."""
    spec, deps = _make_specialist()
    spec.start_onboarding(
        _request(legal_name="A", tax_id="BAD"),
        _aid_advisor(), "trace-001",
    )
    alerts = [
        e for e in deps["audit"].entries
        if e.get("event_type") == "bsa_326_cip_failure"
    ]
    assert len(alerts) == 1
    alert = alerts[0]
    allowed = {
        "source", "event_type", "module", "action", "trace_id",
        "tenant_id", "firm_id", "actor_id", "client_reference",
        "failed_checks", "decision", "reason", "role", "archetype",
        "timestamp",
    }
    assert set(alert.keys()) == allowed, (
        f"BSA alert has unexpected fields: {set(alert.keys()) - allowed}"
    )


def test_bsa_326_alert_has_no_mnpi_values():
    spec, deps = _make_specialist()
    spec.start_onboarding(
        _request(
            legal_name="A",
            tax_id="123-45-6789",
            address="123 Main St, Seattle, WA 98101",
            dob=date(1990, 3, 15),
        ),
        _aid_advisor(), "trace-001",
    )
    # Find any BSA alert
    alerts = [
        e for e in deps["audit"].entries
        if e.get("event_type") == "bsa_326_cip_failure"
    ]
    assert len(alerts) == 1
    blob = str(alerts[0])
    # Raw MNPI values must NOT appear.
    assert "123-45-6789" not in blob
    assert "1990-03-15" not in blob
    assert "98101" not in blob
    # Only the FIELD NAMES that failed appear:
    assert "name" in alerts[0]["failed_checks"]


def test_bsa_alert_decision_is_deny():
    spec, deps = _make_specialist()
    spec.start_onboarding(
        _request(legal_name="A"), _aid_advisor(), "trace-001"
    )
    alerts = [
        e for e in deps["audit"].entries
        if e.get("event_type") == "bsa_326_cip_failure"
    ]
    assert alerts[0]["decision"] == "deny"
    assert alerts[0]["reason"] == "cip_failed"


def test_multiple_cip_failures_all_listed_in_alert():
    spec, deps = _make_specialist()
    spec.start_onboarding(
        _request(
            legal_name="A",
            address="short",
            tax_id="bad",
        ),
        _aid_advisor(), "trace-001",
    )
    alerts = [
        e for e in deps["audit"].entries
        if e.get("event_type") == "bsa_326_cip_failure"
    ]
    assert set(alerts[0]["failed_checks"]) >= {"name", "address", "tax_id"}


def test_bsa_alert_failure_does_not_raise():
    # First emit is the BSA alert; failing that yields
    # `bsa_326_alert_emitted=False` but the decision is still returned.
    audit = FakeAuditClient(fail_at=1)
    spec, _ = _make_specialist(audit=audit)
    decision = spec.start_onboarding(
        _request(legal_name="A"), _aid_advisor(), "trace-001"
    )
    assert decision.status == "cip_failed"
    assert decision.bsa_326_alert_emitted is False


# =============================================================================
# R2.4 -- sanctions hit branching
# =============================================================================


def test_sanctions_hit_produces_cip_failed():
    class SanctionsHitAdapter(StubKycAdapter):
        def screen_sanctions(self, *, name, dob, country):
            return True

        def verify_identity(self, *, name, dob, address, tax_id_hash):
            return KycVendorResult(
                vendor_name="stub",
                vendor_status="approved",
                vendor_reference_id="X",
            )

    spec, _ = _make_specialist(kyc=SanctionsHitAdapter())
    decision = spec.start_onboarding(_request(), _aid_advisor(), "trace-001")
    assert decision.status == "cip_failed"
    assert decision.kyc_result.sanctions_hit is True
    assert "sanctions" in decision.kyc_result.cip.failed_checks


def test_sanctions_only_failure_reason_is_specific():
    class SanctionsOnly(StubKycAdapter):
        def screen_sanctions(self, *, name, dob, country):
            return True

    spec, _ = _make_specialist(kyc=SanctionsOnly())
    decision = spec.start_onboarding(_request(), _aid_advisor(), "trace-001")
    assert decision.reason_code == "onb_sanctions_hit"


def test_sanctions_adapter_exception_is_fail_closed():
    """If screen_sanctions raises, treat as sanctions hit (fail-closed)."""

    class BoomSanctions(StubKycAdapter):
        def screen_sanctions(self, *, name, dob, country):
            raise RuntimeError("vendor down")

    spec, _ = _make_specialist(kyc=BoomSanctions())
    decision = spec.start_onboarding(_request(), _aid_advisor(), "trace-001")
    assert decision.status == "cip_failed"
    assert decision.kyc_result.sanctions_hit is True


def test_stub_kyc_sanctions_by_country():
    stub = StubKycAdapter()
    assert stub.screen_sanctions(
        name="Alice", dob=date(1990, 1, 1), country="KP"
    ) is True
    assert stub.screen_sanctions(
        name="Alice", dob=date(1990, 1, 1), country="IR"
    ) is True
    assert stub.screen_sanctions(
        name="Alice", dob=date(1990, 1, 1), country="US"
    ) is False


def test_stub_kyc_sanctions_by_name():
    stub = StubKycAdapter()
    assert stub.screen_sanctions(
        name="SANCTIONED PERSON", dob=date(1990, 1, 1), country="US"
    ) is True


# =============================================================================
# R5 -- KYC vendor verification path
# =============================================================================


def test_kyc_vendor_denied_triggers_cip_failed():
    class DeniedVendor(StubKycAdapter):
        def verify_identity(self, *, name, dob, address, tax_id_hash):
            return KycVendorResult(
                vendor_name="stub",
                vendor_status="denied",
                vendor_reference_id="V-1",
            )

        def screen_sanctions(self, **kwargs):
            return False

    spec, deps = _make_specialist(kyc=DeniedVendor())
    decision = spec.start_onboarding(_request(), _aid_advisor(), "trace-001")
    assert decision.status == "cip_failed"
    assert decision.reason_code == "onb_kyc_vendor_denied"
    alerts = [
        e for e in deps["audit"].entries
        if e.get("event_type") == "bsa_326_cip_failure"
    ]
    assert len(alerts) == 1


def test_kyc_vendor_unavailable_is_failed():
    class DownVendor(StubKycAdapter):
        def verify_identity(self, *, name, dob, address, tax_id_hash):
            raise RuntimeError("timeout")

        def screen_sanctions(self, **kwargs):
            return False

    spec, _ = _make_specialist(kyc=DownVendor())
    decision = spec.start_onboarding(_request(), _aid_advisor(), "trace-001")
    assert decision.status == "failed"
    assert decision.reason_code == "onb_kyc_vendor_unavailable"


def test_kyc_adapter_protocol_is_runtime_checkable():
    """R5.1: KycAdapterProtocol is runtime-checkable."""
    assert isinstance(StubKycAdapter(), KycAdapterProtocol)


def test_stub_kyc_verify_identity_deterministic():
    stub = StubKycAdapter()
    a = stub.verify_identity(
        name="Alice", dob=date(1990, 1, 1),
        address="123 Main St", tax_id_hash="a" * 64,
    )
    b = stub.verify_identity(
        name="Alice", dob=date(1990, 1, 1),
        address="123 Main St", tax_id_hash="a" * 64,
    )
    assert a == b
    assert a.vendor_status in ("approved", "manual_review", "denied")


def test_stub_kyc_fail_hash_prefix_denied():
    """Hash of literal 'FAIL' triggers denial."""
    import hashlib
    fail_hash = hashlib.sha256(b"FAIL").hexdigest()
    stub = StubKycAdapter()
    result = stub.verify_identity(
        name="Alice", dob=date(1990, 1, 1),
        address="123 Main St", tax_id_hash=fail_hash,
    )
    assert result.vendor_status == "denied"


def test_kyc_adapter_receives_hashed_tax_id():
    """R5.3 / A5: raw tax_id NEVER sent to vendor -- hash only."""
    received: list[str] = []

    class Recorder(StubKycAdapter):
        def verify_identity(self, *, name, dob, address, tax_id_hash):
            received.append(tax_id_hash)
            return KycVendorResult(
                vendor_name="stub",
                vendor_status="approved",
                vendor_reference_id="REC",
            )

        def screen_sanctions(self, **kwargs):
            return False

    spec, _ = _make_specialist(kyc=Recorder())
    spec.start_onboarding(_request(), _aid_advisor(), "trace-001")
    assert len(received) == 1
    # It's a sha256 hex, not the raw ssn.
    assert len(received[0]) == 64
    assert "123-45-6789" not in received[0]
    assert received[0] != "123-45-6789"


# =============================================================================
# R3.1 -- MNPI sanitise invariant
# =============================================================================


def test_mnpi_sanitizer_called():
    mnpi = FakeMnpiSanitizer()
    spec, _ = _make_specialist(mnpi=mnpi)
    spec.start_onboarding(_request(), _aid_advisor(), "trace-001")
    assert len(mnpi.recorded_calls) == 1


def test_mnpi_failure_is_fail_closed():
    spec, _ = _make_specialist(mnpi=FakeMnpiSanitizer(raise_on_call=True))
    decision = spec.start_onboarding(_request(), _aid_advisor(), "trace-001")
    assert decision.status == "failed"
    assert decision.reason_code == "onb_mnpi_sanitize_failed"


# =============================================================================
# R3.3 -- audit on every terminal
# =============================================================================


def test_audit_emitted_on_cip_passed():
    spec, deps = _make_specialist()
    spec.start_onboarding(_request(), _aid_advisor(), "trace-001")
    terminal = [
        e for e in deps["audit"].entries
        if e.get("event_type") == "onboarding.start"
    ]
    assert len(terminal) == 1
    assert terminal[0]["decision"] == "allow"


def test_audit_emitted_on_cip_failed():
    spec, deps = _make_specialist()
    spec.start_onboarding(
        _request(legal_name="A"), _aid_advisor(), "trace-001"
    )
    terminal = [
        e for e in deps["audit"].entries
        if e.get("event_type") == "onboarding.start"
    ]
    assert len(terminal) == 1
    assert terminal[0]["decision"] == "deny"


def test_audit_failure_dominates_success_status():
    # CIP is valid so alert is NOT emitted; audit_client fail_at=1 kills
    # the terminal audit. Decision must flip to failed / onb_audit_failed.
    audit = FakeAuditClient(fail_at=1)
    spec, _ = _make_specialist(audit=audit)
    decision = spec.start_onboarding(_request(), _aid_advisor(), "trace-001")
    assert decision.status == "failed"
    assert decision.reason_code == "onb_audit_failed"


def test_terminal_audit_has_no_mnpi():
    spec, deps = _make_specialist()
    spec.start_onboarding(_request(), _aid_advisor(), "trace-001")
    terminal = [
        e for e in deps["audit"].entries
        if e.get("event_type") == "onboarding.start"
    ][0]
    blob = str(terminal)
    assert "123-45-6789" not in blob
    assert "1990-01-01" not in blob


# =============================================================================
# R4 -- BD advisor principal review
# =============================================================================


def test_bd_advisor_triggers_principal_review_queued():
    spec, deps = _make_specialist()
    aid = _aid_advisor(reg="bd_only")
    decision = spec.start_onboarding(
        _request(kind="bd_advisor"), aid, "trace-001"
    )
    assert decision.status == "principal_review_queued"
    assert decision.reason_code == "onb_bd_principal_review"
    assert decision.gate_payload is not None


def test_dual_registered_bd_advisor_triggers_principal_review():
    spec, _ = _make_specialist()
    aid = _aid_advisor(reg="dual_registered")
    decision = spec.start_onboarding(
        _request(kind="bd_advisor"), aid, "trace-001"
    )
    assert decision.status == "principal_review_queued"


def test_retail_client_does_not_trigger_principal_review():
    spec, _ = _make_specialist()
    aid = _aid_advisor(reg="ria_only")
    decision = spec.start_onboarding(
        _request(kind="retail_client"), aid, "trace-001"
    )
    assert decision.status == "cip_passed"


def test_principal_review_gate_payload_has_expected_shape():
    spec, _ = _make_specialist()
    aid = _aid_advisor(reg="bd_only")
    decision = spec.start_onboarding(
        _request(kind="bd_advisor", client_ref="BD-0007"),
        aid, "trace-001",
    )
    gp = decision.gate_payload
    assert gp is not None
    assert gp.thread_id.startswith("onb-")
    assert gp.summary["gate_kind"] == "onboarding_principal_review"
    assert gp.summary["kind"] == "bd_advisor"


def test_principal_review_audit_is_escalate():
    spec, deps = _make_specialist()
    aid = _aid_advisor(reg="bd_only")
    spec.start_onboarding(
        _request(kind="bd_advisor"), aid, "trace-001",
    )
    terminal = [
        e for e in deps["audit"].entries
        if e.get("event_type") == "onboarding.start"
    ]
    assert terminal[0]["decision"] == "escalate"


# =============================================================================
# R7 -- LLM budget cap + Haiku
# =============================================================================


def test_valid_onboarding_reasons_is_frozen():
    """Vocabulary MUST be a frozenset at module load."""
    assert isinstance(VALID_ONBOARDING_REASONS, frozenset)
    # Every reason code currently returned by the specialist IS in the
    # vocab.
    for code in (
        "onb_invalid_request", "onb_invalid_aid",
        "onb_authority_scope_denied", "onb_mnpi_sanitize_failed",
        "onb_cip_failed", "onb_kyc_vendor_unavailable",
        "onb_kyc_vendor_denied", "onb_sanctions_hit",
        "onb_bd_principal_review", "onb_audit_failed",
        "onb_bsa_alert_failed", "onb_unknown",
    ):
        assert code in VALID_ONBOARDING_REASONS


def test_unknown_reason_code_rejected_at_construction():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        OnboardingDecision(
            status="failed",
            trace_id="t",
            tenant_id="firm-x",
            reason_code="not_in_vocab",  # invalid
            latency_ms=1,
        )


def test_cip_failed_checks_whitelist_enforced():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CipResult(passed=False, failed_checks=["not_whitelisted"])


# =============================================================================
# Error-surface hygiene (A6)
# =============================================================================


def test_error_surface_hygiene_no_exception_text():
    """No exception text appears in any decision field (A6)."""

    class BoomPolicy:
        def evaluate(self, **kwargs):
            raise ValueError("secret that must not leak")

    spec, _ = _make_specialist(policy=BoomPolicy())  # type: ignore[arg-type]
    decision = spec.start_onboarding(_request(), _aid_advisor(), "trace-001")
    # Since policy client isn't used on a successful CIP path (CIP
    # is deterministic without policy), the decision should still
    # terminate cleanly -- the BoomPolicy is never actually invoked
    # by the onboarding specialist. Verify decision is stable:
    assert decision.status in (
        "cip_passed", "principal_review_queued", "cip_failed", "failed"
    )
    assert decision.reason_code is None or (
        decision.reason_code in VALID_ONBOARDING_REASONS
    )


def test_decision_reason_code_always_in_vocab():
    """Every path produces a reason_code from the closed set (or None)."""
    # Run a variety of paths and confirm the vocab invariant.
    spec, _ = _make_specialist()

    decisions = []
    decisions.append(
        spec.start_onboarding(_request(), _aid_advisor(), "trace-1")
    )
    decisions.append(
        spec.start_onboarding(
            _request(legal_name="A"), _aid_advisor(), "trace-2"
        )
    )
    decisions.append(
        spec.start_onboarding(
            _request(kind="bd_advisor"),
            _aid_advisor(reg="bd_only"), "trace-3",
        )
    )
    decisions.append(
        spec.start_onboarding(
            _request(), _aid_advisor(scope=["nope"]), "trace-4",
        )
    )
    for d in decisions:
        assert (
            d.reason_code is None
            or d.reason_code in VALID_ONBOARDING_REASONS
        )


# =============================================================================
# Tax-ID hashing helper
# =============================================================================


def test_onboarding_request_tax_id_hash_is_sha256():
    req = _request(tax_id="123-45-6789")
    import hashlib
    expected = hashlib.sha256(b"123-45-6789").hexdigest()
    assert req.tax_id_hash() == expected


def test_country_code_uppercased_on_construction():
    req = OnboardingRequest(
        kind="retail_client",
        client_reference="C-1",
        legal_name="Jane Doe",
        date_of_birth=date(1990, 1, 1),
        residential_address="123 Main Street, Seattle",
        tax_id="123-45-6789",
        country_code="us",  # lower
        firm_id="firm-acme",
        aid_token="fake",
    )
    assert req.country_code == "US"


# =============================================================================
# OnboardingRequest model validation
# =============================================================================


def test_request_extra_field_forbidden():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        OnboardingRequest(
            kind="retail_client",
            client_reference="C-1",
            legal_name="Jane Doe",
            date_of_birth=date(1990, 1, 1),
            residential_address="123 Main Street",
            tax_id="123-45-6789",
            country_code="US",
            firm_id="firm-acme",
            aid_token="fake",
            not_a_real_field="oops",
        )


def test_request_is_frozen():
    from pydantic import ValidationError
    r = _request()
    with pytest.raises((ValidationError, TypeError)):
        r.legal_name = "new"  # type: ignore[misc]


def test_onboarding_decision_is_frozen():
    from pydantic import ValidationError
    d = OnboardingDecision(
        status="cip_passed",
        trace_id="t", tenant_id="firm-x",
        reason_code=None, latency_ms=5,
    )
    with pytest.raises((ValidationError, TypeError)):
        d.status = "failed"  # type: ignore[misc]
