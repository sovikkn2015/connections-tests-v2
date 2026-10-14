"""
M2/M4 Policy Engine — Unit Tests.

Covers spec tasks T1..T26 (R1..R12 acceptance criteria).

Run:
    PYTHONPATH=my-agent-project-007-fsi-interoperability/src \\
        python3 -m pytest my-agent-project-007-fsi-interoperability/tests/ -v
"""

from __future__ import annotations

import ast
import dataclasses
import re
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from m1_identity import AidClaims, ISSUER, Role
from m3_schema_registry import (
    AssetClass,
    Beneficiary,
    Client,
    Holding,
    PaymentInstruction,
    PaymentStatus,
    PaymentType,
    SecurityProfile,
)
from m5_config_loader import Archetype, RegistrationType

from m2_m4_policy_engine import (
    DECISION_TO_COMPLIANCE_DECISION,
    RULE_APPLIED_RE,
    WSP_SECTION_RE,
    AuthorityPolicy,
    Decision,
    MAX_REASON_LEN,
    MnpiPolicy,
    PolicyDecision,
    PolicyInput,
    UnsupportedTypeForFilterError,
)


# =============================================================================
# Fixtures — PII test constants (pinned for AC-R8-4 substring audit)
# =============================================================================

_FIXTURE_EMAIL = "test@example.com"
_FIXTURE_SSN = "1234"
_FIXTURE_DOB = date(1980, 1, 1)
_FIXTURE_TAX_ID = "TAX-EIN-1234"


def _make_claims(
    sub: str = "sarah.chen@acmewm.com",
    role: Role = Role.advisor,
    archetype: str = Archetype.tier4_independent_ria.value,
    registration_type: str = RegistrationType.ria_only.value,
    authority_scope: list[str] | None = None,
    authority_excludes: list[str] | None = None,
) -> AidClaims:
    now = 1_713_000_000
    return AidClaims(
        iss=ISSUER,
        sub=sub,
        aud="007-mcp-gateway",
        iat=now,
        nbf=now,
        exp=now + 900,
        jti=str(uuid4()),
        firm_id="CRD-123456",
        lei="549300ACMEWM1234RI99",
        crd_number="CRD-123456",
        archetype=archetype,
        role=role,
        authority_scope=authority_scope or ["portfolio.read"],
        authority_excludes=authority_excludes or [],
        registration_type=registration_type,
    )


def _make_client() -> Client:
    now = datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc)
    return Client(
        canonical_id=uuid4(),
        display_name="Henderson Family",
        client_type="individual",
        first_name="John",
        last_name="Henderson",
        email=_FIXTURE_EMAIL,
        phone="+1-555-0100",
        date_of_birth=_FIXTURE_DOB,
        ssn_last_four=_FIXTURE_SSN,
        tax_id=_FIXTURE_TAX_ID,
        firm_id=uuid4(),
        jurisdiction="US",
        source_system="salesforce_fsc",
        source_id="SF-001",
        created_at=now,
        updated_at=now,
    )


def _make_payment() -> PaymentInstruction:
    now = datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc)
    ben = Beneficiary(
        name="Henderson Family Trust",
        account_number="ACCT-987654321",
        bank_name="Acme Bank",
    )
    return PaymentInstruction(
        instruction_id=uuid4(),
        client_ref=uuid4(),
        account_ref=uuid4(),
        payment_type=PaymentType.WIRE_DOMESTIC,
        amount=50000.00,
        currency="USD",
        beneficiary=ben,
        status=PaymentStatus.DRAFT,
        trace_id="trace-001",
        source_system="manual",
        created_at=now,
        updated_at=now,
    )


def _make_security(mnpi_flag: bool | None = False) -> SecurityProfile:
    now = datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc)
    return SecurityProfile(
        canonical_id=uuid4(),
        ticker="ACME",
        security_name="Acme Corp",
        asset_class=AssetClass.EQUITY,
        currency="USD",
        is_restricted=False,
        mnpi_flag=mnpi_flag,
        last_updated=now,
        source_system="bloomberg",
        source_id="ACME-US",
    )


def _make_holding() -> Holding:
    return Holding(
        canonical_id=uuid4(),
        account_ref=str(uuid4()),
        client_ref=str(uuid4()),
        security_name="Acme Corp",
        security_type="equity",
        quantity=100.0,
        market_value=10000.0,
        as_of_date=date(2026, 4, 14),
        source_system="orion",
        source_id="OR-001",
    )


def _order_submit_input(
    claims: AidClaims,
    ticker: str = "ACME",
    restricted: list[str] | None = None,
    trading_window_open: bool = True,
    concentration_pct: float | None = 0.05,
    crossing_wall: bool = False,
    crossing_pod: bool = False,
) -> PolicyInput:
    return PolicyInput(
        identity=claims,
        action="order.submit",
        target={
            "security_id": "SEC-ACME",
            "ticker": ticker,
            "side": "buy",
            "quantity": 100.0,
            "client_id": "CLT-123",
        },
        context={
            "restricted_list": restricted if restricted is not None else [],
            "trading_window_open": trading_window_open,
            "concentration_pct": concentration_pct,
            "crossing_wall": crossing_wall,
            "crossing_pod": crossing_pod,
        },
    )


# =============================================================================
# T2 — Decisions, PolicyDecision, PolicyInput (AC-R1-*)
# =============================================================================

class TestDecisions:
    def test_decision_has_three_members(self):
        assert len(Decision) == 3
        assert set(Decision) == {
            Decision.ALLOW, Decision.DENY, Decision.ESCALATE,
        }

    def test_policy_decision_is_frozen(self):
        pd = PolicyDecision(
            decision=Decision.ALLOW,
            reason="ok",
            rule_applied="authority/advisor/read_own_clients.v1",
            wsp_section="WSP-ADV-1.1",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            pd.reason = "tampered"  # type: ignore[misc]

    def test_policy_input_is_frozen(self):
        claims = _make_claims()
        inp = PolicyInput(identity=claims, action="client.read")
        with pytest.raises(dataclasses.FrozenInstanceError):
            inp.action = "tampered"  # type: ignore[misc]

    def test_reason_length_limit(self):
        with pytest.raises(ValueError):
            PolicyDecision(
                decision=Decision.DENY,
                reason="x" * (MAX_REASON_LEN + 1),
                rule_applied="authority/meta/default_deny.v1",
                wsp_section="WSP-META-0.1",
            )

    def test_wsp_section_non_empty(self):
        with pytest.raises(ValueError):
            PolicyDecision(
                decision=Decision.DENY,
                reason="x",
                rule_applied="authority/meta/default_deny.v1",
                wsp_section="",
            )

    def test_rule_applied_non_empty(self):
        with pytest.raises(ValueError):
            PolicyDecision(
                decision=Decision.DENY,
                reason="x",
                rule_applied="",
                wsp_section="WSP-META-0.1",
            )

    def test_policy_input_action_non_empty(self):
        with pytest.raises(ValueError):
            PolicyInput(identity=_make_claims(), action="")

    def test_unknown_action_returns_unknown_action_rule(self):
        pol = AuthorityPolicy()
        decision = pol.evaluate(
            PolicyInput(identity=_make_claims(), action="nonexistent.action")
        )
        assert decision.decision == Decision.DENY
        assert decision.rule_applied == "authority/meta/unknown_action.v1"
        assert decision.wsp_section == "WSP-META-0.0"

    def test_missing_restricted_list_returns_deny(self):
        pol = AuthorityPolicy()
        inp = PolicyInput(
            identity=_make_claims(),
            action="order.submit",
            target={"ticker": "ACME"},
            context={
                "trading_window_open": True,
                "concentration_pct": 0.0,
                "crossing_wall": False,
                "crossing_pod": False,
            },
        )
        decision = pol.evaluate(inp)
        assert decision.decision == Decision.DENY
        assert decision.reason == "missing_context:restricted_list"

    def test_missing_advisor_id_returns_deny(self):
        pol = AuthorityPolicy()
        inp = PolicyInput(
            identity=_make_claims(),
            action="client.read",
            target={"client_id": "CLT-123"},  # no advisor_id
            context={},
        )
        decision = pol.evaluate(inp)
        assert decision.decision == Decision.DENY
        assert decision.reason == "missing_target:advisor_id"

    def test_policy_input_rejects_non_aidclaims_identity(self):
        with pytest.raises(TypeError):
            PolicyInput(identity="not-a-claims", action="client.read")  # type: ignore[arg-type]

    def test_decision_to_compliance_decision_mapping(self):
        assert DECISION_TO_COMPLIANCE_DECISION[Decision.ALLOW] == "ALLOW"
        assert DECISION_TO_COMPLIANCE_DECISION[Decision.DENY] == "DENY"
        assert DECISION_TO_COMPLIANCE_DECISION[Decision.ESCALATE] == (
            "REQUIRE_APPROVAL"
        )


# =============================================================================
# T3 — Regex constants (AC-R10-3, AC-R12-1)
# =============================================================================

class TestRegexes:
    def test_rule_applied_matches(self):
        assert RULE_APPLIED_RE.fullmatch("authority/advisor/restricted_list.v1")
        assert RULE_APPLIED_RE.fullmatch("mnpi/security/mnpi_check.v1")

    def test_rule_applied_rejects_bad_inputs(self):
        assert not RULE_APPLIED_RE.fullmatch("authority/advisor/RestrictedList.v1")
        assert not RULE_APPLIED_RE.fullmatch("authority/advisor/restricted_list")
        assert not RULE_APPLIED_RE.fullmatch("other/advisor/x.v1")

    def test_wsp_section_matches(self):
        assert WSP_SECTION_RE.fullmatch("WSP-ADV-1.1")
        assert WSP_SECTION_RE.fullmatch("WSP-FINRA-2210")
        assert WSP_SECTION_RE.fullmatch("WSP-META-0.0")

    def test_wsp_section_rejects_bad_inputs(self):
        assert not WSP_SECTION_RE.fullmatch("WSP-adv-1.1")
        assert not WSP_SECTION_RE.fullmatch("ADV-1.1")


# =============================================================================
# T4 — Meta rules + engine skeleton
# =============================================================================

class TestAuthorityMeta:
    def test_list_rules_has_11_entries(self):
        pol = AuthorityPolicy()
        assert len(pol.list_rules()) == 11

    def test_all_rule_applied_match_regex(self):
        pol = AuthorityPolicy()
        for rule_applied, _ in pol.list_rules():
            assert RULE_APPLIED_RE.fullmatch(rule_applied), (
                f"Bad rule_applied: {rule_applied}"
            )

    def test_all_wsp_sections_match_regex(self):
        pol = AuthorityPolicy()
        for _, wsp in pol.list_rules():
            assert WSP_SECTION_RE.fullmatch(wsp), f"Bad wsp_section: {wsp}"

    def test_all_abstain_falls_to_default_deny(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        decision = pol.evaluate(
            PolicyInput(
                identity=claims, action="security.lookup",
                target={"ticker": "ACME"},
                context={},
            )
        )
        assert decision.decision == Decision.DENY
        assert decision.reason == "no_rule_matched"
        assert decision.rule_applied == "authority/meta/default_deny.v1"
        assert decision.wsp_section == "WSP-META-0.1"

    def test_list_rules_stable_across_instances(self):
        assert AuthorityPolicy().list_rules() == AuthorityPolicy().list_rules()

    def test_excludes_check_denies_excluded_action(self):
        claims = _make_claims(authority_excludes=["order.submit"])
        pol = AuthorityPolicy()
        decision = pol.evaluate(_order_submit_input(claims))
        assert decision.decision == Decision.DENY
        assert decision.rule_applied == "authority/meta/excludes_check.v1"
        assert decision.wsp_section == "WSP-META-0.2"
        assert decision.reason == "excluded_by_aid"

    def test_excludes_check_abstains_for_non_excluded_action(self):
        claims = _make_claims(authority_excludes=["order.submit"])
        pol = AuthorityPolicy()
        decision = pol.evaluate(
            PolicyInput(
                identity=claims,
                action="client.read",
                target={"advisor_id": claims.sub, "client_id": "CLT-1"},
                context={},
            )
        )
        assert decision.rule_applied != "authority/meta/excludes_check.v1"

    def test_empty_excludes_does_not_deny(self):
        claims = _make_claims(authority_excludes=[])
        pol = AuthorityPolicy()
        decision = pol.evaluate(
            PolicyInput(
                identity=claims, action="client.read",
                target={"advisor_id": claims.sub, "client_id": "CLT-1"},
                context={},
            )
        )
        assert decision.rule_applied != "authority/meta/excludes_check.v1"


# =============================================================================
# T5 — read_own / read_other (AC-R4-3-*, AC-R4-4-*)
# =============================================================================

class TestClientReadRules:
    def test_advisor_reads_own_client(self):
        claims = _make_claims(sub="sarah@acme.com", role=Role.advisor)
        pol = AuthorityPolicy()
        decision = pol.evaluate(
            PolicyInput(
                identity=claims, action="client.read",
                target={"advisor_id": "sarah@acme.com", "client_id": "C1"},
                context={},
            )
        )
        assert decision.decision == Decision.ALLOW
        assert decision.rule_applied == "authority/advisor/read_own_clients.v1"
        assert decision.wsp_section == "WSP-ADV-1.1"

    def test_missing_advisor_id(self):
        claims = _make_claims()
        pol = AuthorityPolicy()
        decision = pol.evaluate(
            PolicyInput(
                identity=claims, action="client.read",
                target={"client_id": "C1"},
                context={},
            )
        )
        assert decision.decision == Decision.DENY
        assert decision.reason == "missing_target:advisor_id"

    def test_compliance_officer_reads_any_client(self):
        claims = _make_claims(
            sub="audit@acme.com", role=Role.compliance_officer,
        )
        pol = AuthorityPolicy()
        decision = pol.evaluate(
            PolicyInput(
                identity=claims, action="client.read",
                target={"advisor_id": "tom@acme.com", "client_id": "C2"},
                context={},
            )
        )
        assert decision.decision == Decision.ALLOW
        assert decision.rule_applied == "authority/advisor/read_own_clients.v1"

    def test_sarah_cannot_read_toms_client(self):
        claims = _make_claims(sub="sarah@acme.com", role=Role.advisor)
        pol = AuthorityPolicy()
        decision = pol.evaluate(
            PolicyInput(
                identity=claims, action="client.read",
                target={"advisor_id": "tom@acme.com", "client_id": "C1"},
                context={},
            )
        )
        assert decision.decision == Decision.DENY
        assert decision.rule_applied == (
            "authority/advisor/read_other_advisor_clients.v1"
        )
        assert decision.wsp_section == "WSP-ADV-1.2"

    def test_cross_advisor_client_list_denied(self):
        claims = _make_claims(sub="sarah@acme.com", role=Role.advisor)
        pol = AuthorityPolicy()
        decision = pol.evaluate(
            PolicyInput(
                identity=claims, action="client.list",
                target={"advisor_id": "tom@acme.com"},
                context={},
            )
        )
        assert decision.decision == Decision.DENY
        assert decision.rule_applied == (
            "authority/advisor/read_other_advisor_clients.v1"
        )


# =============================================================================
# T6 — restricted_list (AC-R4-5-*)
# =============================================================================

class TestRestrictedListRule:
    def test_restricted_ticker_denied(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        decision = pol.evaluate(
            _order_submit_input(claims, ticker="ACME", restricted=["ACME"])
        )
        assert decision.decision == Decision.DENY
        assert decision.rule_applied == "authority/advisor/restricted_list.v1"
        assert decision.wsp_section == "WSP-TRD-3.1"

    def test_non_restricted_ticker_abstains(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        decision = pol.evaluate(
            _order_submit_input(claims, ticker="MSFT", restricted=["ACME"])
        )
        # No rule ALLOWs order.submit; falls to default-deny.
        assert decision.decision == Decision.DENY
        assert decision.rule_applied == "authority/meta/default_deny.v1"

    def test_missing_restricted_list(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        inp = PolicyInput(
            identity=claims, action="order.submit",
            target={"ticker": "ACME", "security_id": "SEC-1",
                    "side": "buy", "quantity": 1.0, "client_id": "C1"},
            context={
                "trading_window_open": True,
                "concentration_pct": 0.0,
                "crossing_wall": False,
                "crossing_pod": False,
            },
        )
        decision = pol.evaluate(inp)
        assert decision.decision == Decision.DENY
        assert decision.reason == "missing_context:restricted_list"
        assert decision.rule_applied == "authority/advisor/restricted_list.v1"

    def test_empty_restricted_list_abstains(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        decision = pol.evaluate(
            _order_submit_input(claims, ticker="ACME", restricted=[])
        )
        assert decision.decision == Decision.DENY
        assert decision.rule_applied == "authority/meta/default_deny.v1"


# =============================================================================
# T7 — trading_window (AC-R4-6-*)
# =============================================================================

class TestTradingWindowRule:
    def test_closed_window_denied(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        decision = pol.evaluate(
            _order_submit_input(claims, trading_window_open=False)
        )
        assert decision.decision == Decision.DENY
        assert decision.rule_applied == "authority/advisor/trading_window.v1"
        assert decision.wsp_section == "WSP-TRD-3.2"

    def test_open_window_abstains(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        decision = pol.evaluate(
            _order_submit_input(claims, trading_window_open=True)
        )
        assert decision.rule_applied != "authority/advisor/trading_window.v1"

    def test_missing_trading_window(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        inp = PolicyInput(
            identity=claims, action="order.submit",
            target={"ticker": "MSFT", "security_id": "SEC-1",
                    "side": "buy", "quantity": 1.0, "client_id": "C1"},
            context={
                "restricted_list": [],
                "concentration_pct": 0.0,
                "crossing_wall": False,
                "crossing_pod": False,
            },
        )
        decision = pol.evaluate(inp)
        assert decision.decision == Decision.DENY
        assert decision.reason == "missing_context:trading_window_open"


# =============================================================================
# T8 — concentration_limit (AC-R4-7-*)
# =============================================================================

class TestConcentrationLimitRule:
    def test_escalate_over_threshold(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        decision = pol.evaluate(
            _order_submit_input(claims, concentration_pct=0.12)
        )
        assert decision.decision == Decision.ESCALATE
        assert decision.rule_applied == "authority/advisor/concentration_limit.v1"
        assert decision.wsp_section == "WSP-RISK-2.1"

    def test_under_threshold_abstains(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        decision = pol.evaluate(
            _order_submit_input(claims, concentration_pct=0.05)
        )
        assert decision.rule_applied != "authority/advisor/concentration_limit.v1"

    def test_exact_threshold_abstains(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        decision = pol.evaluate(
            _order_submit_input(claims, concentration_pct=0.10)
        )
        assert decision.rule_applied != "authority/advisor/concentration_limit.v1"

    def test_missing_concentration(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        decision = pol.evaluate(
            _order_submit_input(claims, concentration_pct=None)
        )
        assert decision.decision == Decision.DENY
        assert decision.reason == "missing_context:concentration_pct"

    def test_string_concentration_treated_as_missing(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        inp = PolicyInput(
            identity=claims, action="order.submit",
            target={"ticker": "MSFT", "security_id": "SEC-1",
                    "side": "buy", "quantity": 1.0, "client_id": "C1"},
            context={
                "restricted_list": [],
                "trading_window_open": True,
                "concentration_pct": "12%",
                "crossing_wall": False,
                "crossing_pod": False,
            },
        )
        decision = pol.evaluate(inp)
        assert decision.decision == Decision.DENY
        assert decision.reason == "missing_context:concentration_pct"

    def test_int_concentration_treated_as_missing(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        inp = PolicyInput(
            identity=claims, action="order.submit",
            target={"ticker": "MSFT", "security_id": "SEC-1",
                    "side": "buy", "quantity": 1.0, "client_id": "C1"},
            context={
                "restricted_list": [],
                "trading_window_open": True,
                "concentration_pct": 1,
                "crossing_wall": False,
                "crossing_pod": False,
            },
        )
        decision = pol.evaluate(inp)
        assert decision.decision == Decision.DENY
        assert decision.reason == "missing_context:concentration_pct"

    def test_out_of_range_concentration(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        decision = pol.evaluate(
            _order_submit_input(claims, concentration_pct=1.5)
        )
        assert decision.decision == Decision.DENY
        assert decision.reason == "missing_context:concentration_pct"


# =============================================================================
# T9 — chinese_wall (AC-R4-8-*)
# =============================================================================

class TestChineseWallRule:
    def test_tier1_wall_crossing_denied(self):
        pol = AuthorityPolicy()
        claims = _make_claims(archetype=Archetype.tier1_investment_bank.value)
        decision = pol.evaluate(
            _order_submit_input(claims, crossing_wall=True)
        )
        assert decision.decision == Decision.DENY
        assert decision.rule_applied == "authority/advisor/chinese_wall.v1"

    def test_tier1_no_crossing_abstains(self):
        pol = AuthorityPolicy()
        claims = _make_claims(archetype=Archetype.tier1_investment_bank.value)
        decision = pol.evaluate(
            _order_submit_input(claims, crossing_wall=False)
        )
        assert decision.rule_applied != "authority/advisor/chinese_wall.v1"

    def test_tier4_crossing_wall_skipped(self):
        pol = AuthorityPolicy()
        claims = _make_claims(archetype=Archetype.tier4_independent_ria.value)
        decision = pol.evaluate(
            _order_submit_input(claims, crossing_wall=True)
        )
        assert decision.rule_applied != "authority/advisor/chinese_wall.v1"

    def test_tier1_missing_crossing_wall(self):
        pol = AuthorityPolicy()
        claims = _make_claims(archetype=Archetype.tier1_investment_bank.value)
        inp = PolicyInput(
            identity=claims, action="order.submit",
            target={"ticker": "MSFT", "security_id": "SEC-1",
                    "side": "buy", "quantity": 1.0, "client_id": "C1"},
            context={
                "restricted_list": [],
                "trading_window_open": True,
                "concentration_pct": 0.0,
                "crossing_pod": False,
            },
        )
        decision = pol.evaluate(inp)
        assert decision.decision == Decision.DENY
        assert decision.reason == "missing_context:crossing_wall"


# =============================================================================
# T10 — pod_isolation (AC-R4-9-*)
# =============================================================================

class TestPodIsolationRule:
    def test_tier5_pod_crossing_denied(self):
        pol = AuthorityPolicy()
        claims = _make_claims(archetype=Archetype.tier5_hedge_fund.value)
        decision = pol.evaluate(
            _order_submit_input(claims, crossing_pod=True)
        )
        assert decision.decision == Decision.DENY
        assert decision.rule_applied == "authority/advisor/pod_isolation.v1"

    def test_tier5_no_crossing_abstains(self):
        pol = AuthorityPolicy()
        claims = _make_claims(archetype=Archetype.tier5_hedge_fund.value)
        decision = pol.evaluate(
            _order_submit_input(claims, crossing_pod=False)
        )
        assert decision.rule_applied != "authority/advisor/pod_isolation.v1"

    def test_tier3_crossing_pod_skipped(self):
        pol = AuthorityPolicy()
        claims = _make_claims(archetype=Archetype.tier3_broker_dealer.value)
        decision = pol.evaluate(
            _order_submit_input(claims, crossing_pod=True)
        )
        assert decision.rule_applied != "authority/advisor/pod_isolation.v1"

    def test_tier5_missing_crossing_pod(self):
        pol = AuthorityPolicy()
        claims = _make_claims(archetype=Archetype.tier5_hedge_fund.value)
        inp = PolicyInput(
            identity=claims, action="order.submit",
            target={"ticker": "MSFT", "security_id": "SEC-1",
                    "side": "buy", "quantity": 1.0, "client_id": "C1"},
            context={
                "restricted_list": [],
                "trading_window_open": True,
                "concentration_pct": 0.0,
                "crossing_wall": False,
            },
        )
        decision = pol.evaluate(inp)
        assert decision.decision == Decision.DENY
        assert decision.reason == "missing_context:crossing_pod"


# =============================================================================
# T11 — principal.review_required (AC-R4-10-*)
# =============================================================================

class TestPrincipalReviewRule:
    def test_bd_retail_escalates(self):
        pol = AuthorityPolicy()
        claims = _make_claims(
            registration_type=RegistrationType.bd_only.value,
            archetype=Archetype.tier3_broker_dealer.value,
        )
        decision = pol.evaluate(
            PolicyInput(
                identity=claims, action="comm.send_retail",
                target={"client_id": "C1"},
                context={"recipient_type": "retail"},
            )
        )
        assert decision.decision == Decision.ESCALATE
        assert decision.rule_applied == "authority/principal/review_required.v1"
        assert decision.wsp_section == "WSP-FINRA-2210"

    def test_bd_institutional_abstains(self):
        pol = AuthorityPolicy()
        claims = _make_claims(
            registration_type=RegistrationType.bd_only.value,
            archetype=Archetype.tier3_broker_dealer.value,
        )
        decision = pol.evaluate(
            PolicyInput(
                identity=claims, action="comm.send_retail",
                target={"client_id": "C1"},
                context={"recipient_type": "institutional"},
            )
        )
        assert decision.rule_applied != "authority/principal/review_required.v1"

    def test_ria_retail_rule_skipped(self):
        pol = AuthorityPolicy()
        claims = _make_claims(registration_type=RegistrationType.ria_only.value)
        decision = pol.evaluate(
            PolicyInput(
                identity=claims, action="comm.send_retail",
                target={"client_id": "C1"},
                context={"recipient_type": "retail"},
            )
        )
        assert decision.rule_applied != "authority/principal/review_required.v1"

    def test_dual_registered_retail_escalates(self):
        pol = AuthorityPolicy()
        claims = _make_claims(
            registration_type=RegistrationType.dual_registered.value,
        )
        decision = pol.evaluate(
            PolicyInput(
                identity=claims, action="comm.send_retail",
                target={"client_id": "C1"},
                context={"recipient_type": "retail"},
            )
        )
        assert decision.decision == Decision.ESCALATE

    def test_bd_missing_recipient_type(self):
        pol = AuthorityPolicy()
        claims = _make_claims(registration_type=RegistrationType.bd_only.value)
        decision = pol.evaluate(
            PolicyInput(
                identity=claims, action="comm.send_retail",
                target={"client_id": "C1"},
                context={},
            )
        )
        assert decision.decision == Decision.DENY
        assert decision.reason == "missing_context:recipient_type"


# =============================================================================
# T12 — Engine DENY-OVERRIDES + determinism (AC-R2-8, R3-1..3, R6-1)
# =============================================================================

class TestEngineOrdering:
    def test_restricted_list_deny_wins(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        decision = pol.evaluate(
            _order_submit_input(
                claims, ticker="ACME", restricted=["ACME"],
                concentration_pct=0.12,
            )
        )
        assert decision.decision == Decision.DENY
        assert decision.rule_applied == "authority/advisor/restricted_list.v1"

    def test_allow_plus_escalate_returns_escalate(self):
        """AC-R2-8: ALLOW recorded, later ESCALATE overrides."""

        class _FakeAllowRule:
            name = "authority.advisor.fake_allow"
            rule_applied = "authority/advisor/read_own_clients.v1"
            # Reuse an existing valid rule_applied so regex/golden pass.
            # The golden-vector test builds a stock AuthorityPolicy, so
            # this subclass is not scanned by that test.
            wsp_section = "WSP-ADV-1.1"
            archetypes = frozenset()
            actions = frozenset({"order.submit"})
            rule_kind = "authority_gate"
            decision_kinds = frozenset({"ALLOW"})

            def evaluate(self, inp):
                return PolicyDecision(
                    decision=Decision.ALLOW,
                    reason="test_allow",
                    rule_applied=self.rule_applied,
                    wsp_section=self.wsp_section,
                    details={},
                )

        class _TestPolicy(AuthorityPolicy):
            def _build_rules(self):
                base = list(super()._build_rules())
                # Insert fake ALLOW as FIRST rule so it records an
                # ALLOW before concentration_limit fires ESCALATE.
                return tuple([_FakeAllowRule()] + base)

        pol = _TestPolicy()
        claims = _make_claims()
        decision = pol.evaluate(
            _order_submit_input(claims, concentration_pct=0.15)
        )
        assert decision.decision == Decision.ESCALATE
        assert decision.rule_applied == "authority/advisor/concentration_limit.v1"

    def test_determinism_100_calls(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        inp = PolicyInput(
            identity=claims, action="client.read",
            target={"advisor_id": claims.sub, "client_id": "C1"},
            context={},
        )
        first = pol.evaluate(inp)
        for _ in range(100):
            d = pol.evaluate(inp)
            assert d == first

    def test_evaluate_requires_policy_input(self):
        pol = AuthorityPolicy()
        with pytest.raises(TypeError):
            pol.evaluate({"action": "client.read"})  # type: ignore[arg-type]


# =============================================================================
# T13 — Exception handling (AC-R2-5, AC-R7-*)
# =============================================================================

class _BoomRuleValueError:
    name = "authority.test.boom_value"
    rule_applied = "authority/advisor/restricted_list.v1"
    wsp_section = "WSP-TRD-3.1"
    archetypes = frozenset()
    actions = frozenset({"order.submit"})
    rule_kind = "authority_gate"
    decision_kinds = frozenset({"DENY"})

    def evaluate(self, inp):
        raise ValueError("bad")


class _BoomRuleWithPII:
    name = "authority.test.boom_pii"
    rule_applied = "authority/advisor/restricted_list.v1"
    wsp_section = "WSP-TRD-3.1"
    archetypes = frozenset()
    actions = frozenset({"order.submit"})
    rule_kind = "authority_gate"
    decision_kinds = frozenset({"DENY"})

    def evaluate(self, inp):
        raise RuntimeError("client@example.com")


class _WrongTypeRule:
    name = "authority.test.wrong_type"
    rule_applied = "authority/advisor/restricted_list.v1"
    wsp_section = "WSP-TRD-3.1"
    archetypes = frozenset()
    actions = frozenset({"order.submit"})
    rule_kind = "authority_gate"
    decision_kinds = frozenset({"DENY"})

    def evaluate(self, inp):
        return "ALLOW"  # wrong type


def _policy_with_rule(*extra_rules):
    class _TestPolicy(AuthorityPolicy):
        def _build_rules(self):
            return tuple(extra_rules)

    return _TestPolicy()


class TestExceptionHandling:
    def test_rule_raising_returns_evaluation_error(self):
        pol = _policy_with_rule(_BoomRuleValueError())
        claims = _make_claims()
        decision = pol.evaluate(_order_submit_input(claims, restricted=[]))
        assert decision.decision == Decision.DENY
        assert decision.reason == "evaluation_error"
        assert decision.rule_applied == "authority/advisor/restricted_list.v1"

    def test_reason_is_literal_no_pii_leak(self):
        pol = _policy_with_rule(_BoomRuleWithPII())
        claims = _make_claims()
        decision = pol.evaluate(_order_submit_input(claims, restricted=[]))
        assert decision.reason == "evaluation_error"
        assert "client@example.com" not in decision.reason
        assert "@" not in decision.reason
        for v in decision.details.values():
            assert "client@example.com" not in str(v)
            assert "@" not in str(v)

    def test_engine_never_returns_none(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        decision = pol.evaluate(
            PolicyInput(identity=claims, action="nonexistent.action")
        )
        assert isinstance(decision, PolicyDecision)

    def test_wrong_type_returns_evaluation_error(self):
        pol = _policy_with_rule(_WrongTypeRule())
        claims = _make_claims()
        decision = pol.evaluate(_order_submit_input(claims, restricted=[]))
        assert decision.decision == Decision.DENY
        assert decision.reason == "evaluation_error"


# =============================================================================
# T14 — Role.system / Role.agent (AC-R4-11-*)
# =============================================================================

class TestSystemAgentRoles:
    def test_system_role_denied_on_client_read(self):
        # AC-R4-11-1: Role.system with matching advisor_id still denied
        # because read_own_clients requires role in {advisor,
        # compliance_officer}. read_other_advisor_clients abstains
        # (own client). Falls through to default-deny.
        claims = _make_claims(sub="svc-x", role=Role.system)
        pol = AuthorityPolicy()
        decision = pol.evaluate(
            PolicyInput(
                identity=claims, action="client.read",
                target={"advisor_id": "svc-x", "client_id": "C1"},
                context={},
            )
        )
        assert decision.decision == Decision.DENY
        # System role with matching advisor_id -> default-deny.
        assert decision.rule_applied == "authority/meta/default_deny.v1"

    def test_agent_role_denied_on_client_read(self):
        claims = _make_claims(sub="agent-x", role=Role.agent)
        pol = AuthorityPolicy()
        decision = pol.evaluate(
            PolicyInput(
                identity=claims, action="client.read",
                target={"advisor_id": "someone-else", "client_id": "C1"},
                context={},
            )
        )
        assert decision.decision == Decision.DENY
        assert decision.rule_applied == (
            "authority/advisor/read_other_advisor_clients.v1"
        )

    def test_advisor_role_matching_advisor_id_allowed(self):
        claims = _make_claims(sub="sarah@acme.com", role=Role.advisor)
        pol = AuthorityPolicy()
        decision = pol.evaluate(
            PolicyInput(
                identity=claims, action="client.read",
                target={"advisor_id": "sarah@acme.com", "client_id": "C1"},
                context={},
            )
        )
        assert decision.decision == Decision.ALLOW


# =============================================================================
# T15 — Authority rule_table golden vector (AC-R10-*)
# =============================================================================

_AUTHORITY_RULE_TABLE_EXPECTED = [
    {
        "rule_applied": "authority/meta/excludes_check.v1",
        "wsp_section": "WSP-META-0.2",
        "archetypes": ["ALL"],
        "actions": ["ALL"],
        "rule_kind": "authority_meta",
        "decision_kinds": ["DENY"],
    },
    {
        "rule_applied": "authority/advisor/restricted_list.v1",
        "wsp_section": "WSP-TRD-3.1",
        "archetypes": ["ALL"],
        "actions": ["order.draft", "order.submit"],
        "rule_kind": "authority_gate",
        "decision_kinds": ["DENY"],
    },
    {
        "rule_applied": "authority/advisor/trading_window.v1",
        "wsp_section": "WSP-TRD-3.2",
        "archetypes": ["ALL"],
        "actions": ["order.draft", "order.submit"],
        "rule_kind": "authority_gate",
        "decision_kinds": ["DENY"],
    },
    {
        "rule_applied": "authority/advisor/chinese_wall.v1",
        "wsp_section": "WSP-CWL-4.1",
        "archetypes": ["tier1_investment_bank"],
        "actions": ["ALL"],
        "rule_kind": "authority_gate",
        "decision_kinds": ["DENY"],
    },
    {
        "rule_applied": "authority/advisor/pod_isolation.v1",
        "wsp_section": "WSP-POD-5.1",
        "archetypes": ["tier5_hedge_fund"],
        "actions": ["ALL"],
        "rule_kind": "authority_gate",
        "decision_kinds": ["DENY"],
    },
    {
        "rule_applied": "authority/advisor/read_other_advisor_clients.v1",
        "wsp_section": "WSP-ADV-1.2",
        "archetypes": ["ALL"],
        "actions": ["client.list", "client.read", "portfolio.view"],
        "rule_kind": "authority_gate",
        "decision_kinds": ["DENY"],
    },
    {
        "rule_applied": "authority/advisor/read_own_clients.v1",
        "wsp_section": "WSP-ADV-1.1",
        "archetypes": ["ALL"],
        "actions": ["client.list", "client.read", "portfolio.view"],
        "rule_kind": "authority_gate",
        "decision_kinds": ["ALLOW"],
    },
    {
        "rule_applied": "authority/advisor/concentration_limit.v1",
        "wsp_section": "WSP-RISK-2.1",
        "archetypes": ["ALL"],
        "actions": ["order.draft", "order.submit"],
        "rule_kind": "authority_gate",
        "decision_kinds": ["ESCALATE"],
    },
    {
        "rule_applied": "authority/principal/review_required.v1",
        "wsp_section": "WSP-FINRA-2210",
        "archetypes": ["ALL"],
        "actions": ["comm.send_retail"],
        "rule_kind": "authority_gate",
        "decision_kinds": ["ESCALATE"],
    },
    {
        "rule_applied": "authority/meta/default_deny.v1",
        "wsp_section": "WSP-META-0.1",
        "archetypes": ["ALL"],
        "actions": ["ALL"],
        "rule_kind": "authority_meta",
        "decision_kinds": ["DENY"],
    },
    {
        "rule_applied": "authority/meta/unknown_action.v1",
        "wsp_section": "WSP-META-0.0",
        "archetypes": ["ALL"],
        "actions": ["ALL"],
        "rule_kind": "authority_meta",
        "decision_kinds": ["DENY"],
    },
]


class TestAuthorityRuleTable:
    def test_has_11_entries(self):
        pol = AuthorityPolicy()
        assert len(pol.rule_table()) == 11

    def test_wsp_sections_match(self):
        pol = AuthorityPolicy()
        for entry in pol.rule_table():
            assert WSP_SECTION_RE.fullmatch(entry["wsp_section"])

    def test_decision_kinds_subset(self):
        allowed = {"ALLOW", "DENY", "ESCALATE"}
        pol = AuthorityPolicy()
        for entry in pol.rule_table():
            for kind in entry["decision_kinds"]:
                assert kind in allowed

    def test_golden_vector(self):
        pol = AuthorityPolicy()
        assert pol.rule_table() == _AUTHORITY_RULE_TABLE_EXPECTED


# =============================================================================
# T16..T20 — MnpiPolicy
# =============================================================================

class TestMnpiFilterClient:
    def test_ssn_redacted_for_advisor(self):
        claims = _make_claims(role=Role.advisor)
        pol = MnpiPolicy()
        client = _make_client()
        filtered = pol.filter(claims, client)
        assert filtered.ssn_last_four is None
        assert filtered.email == client.email
        assert filtered.first_name == client.first_name

    def test_ssn_visible_for_compliance(self):
        claims = _make_claims(role=Role.compliance_officer)
        pol = MnpiPolicy()
        client = _make_client()
        filtered = pol.filter(claims, client)
        assert filtered.ssn_last_four == client.ssn_last_four

    def test_dob_redacted_for_advisor(self):
        claims = _make_claims(role=Role.advisor)
        pol = MnpiPolicy()
        filtered = pol.filter(claims, _make_client())
        assert filtered.date_of_birth is None

    def test_dob_visible_for_compliance(self):
        claims = _make_claims(role=Role.compliance_officer)
        pol = MnpiPolicy()
        client = _make_client()
        filtered = pol.filter(claims, client)
        assert filtered.date_of_birth == client.date_of_birth

    def test_tax_id_redacted_for_advisor(self):
        claims = _make_claims(role=Role.advisor)
        pol = MnpiPolicy()
        filtered = pol.filter(claims, _make_client())
        assert filtered.tax_id is None

    def test_tax_id_visible_for_compliance(self):
        claims = _make_claims(role=Role.compliance_officer)
        pol = MnpiPolicy()
        client = _make_client()
        filtered = pol.filter(claims, client)
        assert filtered.tax_id == client.tax_id


class TestMnpiFilterPayment:
    def test_account_redacted_for_advisor(self):
        claims = _make_claims(role=Role.advisor)
        pol = MnpiPolicy()
        payment = _make_payment()
        filtered = pol.filter(claims, payment)
        assert filtered.beneficiary.account_number is None
        assert filtered.beneficiary.name == payment.beneficiary.name
        assert filtered.beneficiary.bank_name == payment.beneficiary.bank_name

    def test_account_visible_for_compliance(self):
        claims = _make_claims(role=Role.compliance_officer)
        pol = MnpiPolicy()
        payment = _make_payment()
        filtered = pol.filter(claims, payment)
        assert filtered.beneficiary.account_number == (
            payment.beneficiary.account_number
        )

    def test_fully_authorized_returns_same_instance(self):
        # When compliance_officer has no redactions, filter is a no-op.
        claims = _make_claims(role=Role.compliance_officer)
        pol = MnpiPolicy()
        payment = _make_payment()
        filtered = pol.filter(claims, payment)
        assert filtered is payment


class TestMnpiNonMutation:
    def test_input_unchanged_after_filter_flat(self):
        claims = _make_claims(role=Role.advisor)
        pol = MnpiPolicy()
        client = _make_client()
        original_ssn = client.ssn_last_four
        original_dob = client.date_of_birth
        original_tax = client.tax_id
        _ = pol.filter(claims, client)
        assert client.ssn_last_four == original_ssn
        assert client.date_of_birth == original_dob
        assert client.tax_id == original_tax

    def test_input_unchanged_after_filter_nested(self):
        claims = _make_claims(role=Role.advisor)
        pol = MnpiPolicy()
        payment = _make_payment()
        original_account = payment.beneficiary.account_number
        _ = pol.filter(claims, payment)
        assert payment.beneficiary.account_number == original_account

    def test_type_stable(self):
        claims = _make_claims(role=Role.advisor)
        pol = MnpiPolicy()
        assert type(pol.filter(claims, _make_client())) is Client
        assert type(pol.filter(claims, _make_payment())) is PaymentInstruction

    def test_unsupported_type_strict_false_passthrough(self):
        claims = _make_claims(role=Role.advisor)
        pol = MnpiPolicy()
        holding = _make_holding()
        result = pol.filter(claims, holding)
        assert result is holding

    def test_unsupported_type_strict_true_raises(self):
        claims = _make_claims(role=Role.advisor)
        pol = MnpiPolicy()
        holding = _make_holding()
        with pytest.raises(UnsupportedTypeForFilterError):
            pol.filter(claims, holding, strict=True)


class TestMnpiCheckAccess:
    def test_compliance_allowed_even_with_mnpi_flag(self):
        claims = _make_claims(role=Role.compliance_officer)
        pol = MnpiPolicy()
        decision = pol.check_mnpi_access(claims, _make_security(mnpi_flag=True))
        assert decision.decision == Decision.ALLOW
        assert decision.rule_applied == "mnpi/security/mnpi_check.v1"
        assert decision.wsp_section == "WSP-MNPI-3.1"

    def test_advisor_denied_with_mnpi_flag(self):
        claims = _make_claims(role=Role.advisor)
        pol = MnpiPolicy()
        decision = pol.check_mnpi_access(claims, _make_security(mnpi_flag=True))
        assert decision.decision == Decision.DENY
        assert decision.reason == "mnpi_flag_set"
        assert decision.rule_applied == "mnpi/security/mnpi_check.v1"
        assert decision.wsp_section == "WSP-MNPI-3.1"

    def test_advisor_allowed_no_mnpi_flag(self):
        claims = _make_claims(role=Role.advisor)
        pol = MnpiPolicy()
        decision = pol.check_mnpi_access(claims, _make_security(mnpi_flag=False))
        assert decision.decision == Decision.ALLOW

    def test_missing_flag_treated_as_present(self):
        claims = _make_claims(role=Role.advisor)
        pol = MnpiPolicy()
        decision = pol.check_mnpi_access(claims, _make_security(mnpi_flag=None))
        assert decision.decision == Decision.DENY
        assert decision.reason == "mnpi_flag_set"


class TestMnpiDriftCheck:
    def test_beneficiary_drift_raises_at_construction(self, monkeypatch):
        """AC-R5-18 / F13 — simulate M3 drift removing account_number."""
        original_fields = Beneficiary.model_fields
        patched = {
            k: v for k, v in original_fields.items() if k != "account_number"
        }
        monkeypatch.setattr(Beneficiary, "model_fields", patched)
        with pytest.raises(AttributeError):
            MnpiPolicy()


# =============================================================================
# T20 — MnpiPolicy rule_table (AC-R10-2, AC-R10-6)
# =============================================================================

class TestMnpiRuleTable:
    def test_list_rules_has_5_entries(self):
        pol = MnpiPolicy()
        assert len(pol.list_rules()) == 5

    def test_rule_table_has_5_entries(self):
        pol = MnpiPolicy()
        assert len(pol.rule_table()) == 5

    def test_rule_kinds_mnpi(self):
        allowed = {"mnpi_filter", "mnpi_access"}
        pol = MnpiPolicy()
        for entry in pol.rule_table():
            assert entry["rule_kind"] in allowed

    def test_all_rule_applied_match(self):
        pol = MnpiPolicy()
        for ra, _ in pol.list_rules():
            assert RULE_APPLIED_RE.fullmatch(ra)

    def test_all_wsp_sections_match(self):
        pol = MnpiPolicy()
        for _, wsp in pol.list_rules():
            assert WSP_SECTION_RE.fullmatch(wsp)


# =============================================================================
# T21 — Determinism + purity AST scans (AC-R6-*)
# =============================================================================

_SRC_DIR = Path(__file__).resolve().parents[2] / "src" / "m2_m4_policy_engine"
_SRC_FILES = {
    "__init__": _SRC_DIR / "__init__.py",
    "decisions": _SRC_DIR / "decisions.py",
    "rules": _SRC_DIR / "rules.py",
    "authority": _SRC_DIR / "authority.py",
    "mnpi": _SRC_DIR / "mnpi.py",
}

_IMPORT_ALLOWLIST: dict[str, set[str]] = {
    "__init__": {"__future__", "m2_m4_policy_engine"},
    "decisions": {
        "__future__", "dataclasses", "enum", "typing", "m1_identity",
    },
    "rules": {
        "__future__", "re", "typing", "m2_m4_policy_engine",
    },
    "authority": {
        "__future__", "dataclasses", "typing",
        "m1_identity", "m5_config_loader", "m2_m4_policy_engine",
    },
    "mnpi": {
        "__future__", "typing", "pydantic",
        "m1_identity", "m3_schema_registry", "m2_m4_policy_engine",
    },
}


def _top_level_module(name: str) -> str:
    return name.split(".")[0]


def _import_module_names(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(_top_level_module(alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.add(_top_level_module(node.module))
    return found


class TestDeterminismPurity:
    def test_100_call_determinism(self):
        pol = AuthorityPolicy()
        claims = _make_claims()
        inp = PolicyInput(
            identity=claims, action="client.read",
            target={"advisor_id": claims.sub, "client_id": "C1"},
            context={},
        )
        expected = pol.evaluate(inp)
        for _ in range(100):
            assert pol.evaluate(inp) == expected

    def test_100_filter_determinism(self):
        pol = MnpiPolicy()
        claims = _make_claims(role=Role.advisor)
        client = _make_client()
        expected_dump = pol.filter(claims, client).model_dump()
        for _ in range(100):
            assert pol.filter(claims, client).model_dump() == expected_dump

    def test_ast_no_forbidden_imports_per_file(self):
        forbidden = {
            "os", "requests", "httpx", "boto3",
            "openai", "anthropic", "langchain", "langfuse",
        }
        for key, path in _SRC_FILES.items():
            tree = ast.parse(path.read_text())
            imports = _import_module_names(tree)
            assert not (imports & forbidden), (
                f"{key}.py imports forbidden modules: {imports & forbidden}"
            )
            allowed = _IMPORT_ALLOWLIST[key]
            disallowed = imports - allowed
            assert not disallowed, (
                f"{key}.py imports not in allow-list: {disallowed}"
            )

    def test_ast_no_other_m_module_imports(self):
        for key, path in _SRC_FILES.items():
            tree = ast.parse(path.read_text())
            imports = _import_module_names(tree)
            m_imports = {i for i in imports if re.match(r"^m\d+_", i)}
            allowed = _IMPORT_ALLOWLIST[key]
            disallowed_m = m_imports - allowed
            assert not disallowed_m, (
                f"{key}.py imports forbidden m*_ modules: {disallowed_m}"
            )

    def test_ast_no_forbidden_calls(self):
        forbidden_calls = {("datetime", "now"), ("time", "time")}
        forbidden_bare = {"print"}
        forbidden_attr = {"random", "logging"}
        for key, path in _SRC_FILES.items():
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name):
                        assert func.id not in forbidden_bare, (
                            f"{key}.py calls forbidden bare: {func.id}"
                        )
                        assert func.id != "open", (
                            f"{key}.py calls open() — forbidden"
                        )
                    if isinstance(func, ast.Attribute) and isinstance(
                        func.value, ast.Name
                    ):
                        assert (
                            (func.value.id, func.attr) not in forbidden_calls
                        ), f"{key}.py calls {func.value.id}.{func.attr}()"
                        assert func.value.id not in forbidden_attr, (
                            f"{key}.py calls {func.value.id}.{func.attr}"
                        )


# =============================================================================
# T22 — Security invariants (AC-R8-*)
# =============================================================================

_TEST_FILE = Path(__file__).resolve()
_ALL_SCAN_FILES: list[Path] = list(_SRC_FILES.values()) + [_TEST_FILE]


class TestSecurity:
    def test_no_secrets_in_sources(self):
        secret_patterns = [
            re.compile(r"AKIA[A-Z0-9]{16}"),
            re.compile(r"sk-[A-Za-z0-9]{20,}"),
            re.compile(r"Bearer\s+[A-Za-z0-9\-_.]+"),
            re.compile(r"password\s*=\s*['\"][^'\"]+['\"]"),
            re.compile(r"api_key\s*=\s*['\"][^'\"]+['\"]"),
            re.compile(r"secret\s*=\s*['\"][^'\"]+['\"]"),
        ]
        for path in _ALL_SCAN_FILES:
            text = path.read_text()
            for pattern in secret_patterns:
                if path == _TEST_FILE:
                    # Test file literally defines these regex patterns;
                    # skip secret scan on it.
                    continue
                match = pattern.search(text)
                assert match is None, (
                    f"{path.name} matches secret pattern "
                    f"{pattern.pattern}: {match.group(0) if match else ''}"
                )

    def test_no_eval_exec_compile_in_sources(self):
        forbidden = {"eval", "exec", "compile", "__import__"}
        for key, path in _SRC_FILES.items():
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and (
                        node.func.id in forbidden
                    ):
                        raise AssertionError(
                            f"{key}.py calls forbidden: {node.func.id}"
                        )

    def test_non_mutation_of_input_client(self):
        claims = _make_claims(role=Role.advisor)
        pol = MnpiPolicy()
        client = _make_client()
        snapshot = client.ssn_last_four
        _ = pol.filter(claims, client)
        assert client.ssn_last_four == snapshot

    def test_no_pii_in_any_engine_reason_or_details(self):
        pol = AuthorityPolicy()
        mnpi_pol = MnpiPolicy()
        claims = _make_claims()

        decisions_under_test: list[PolicyDecision] = []

        # 1) Missing target advisor_id — DENY.
        decisions_under_test.append(
            pol.evaluate(
                PolicyInput(
                    identity=claims, action="client.read",
                    target={"client_id": "C-1"},
                    context={},
                )
            )
        )
        # 2) Unknown action with PII-like payload in target/context.
        #    Engine constructs the decision itself — it shouldn't copy
        #    these payloads into reason/details.
        decisions_under_test.append(
            pol.evaluate(PolicyInput(
                identity=claims, action="nonexistent",
                target={"attacker": _FIXTURE_SSN},
                context={"leak": _FIXTURE_TAX_ID},
            ))
        )
        # 3) MNPI access deny.
        decisions_under_test.append(
            mnpi_pol.check_mnpi_access(claims, _make_security(mnpi_flag=True))
        )

        fixture_substrings = [
            _FIXTURE_EMAIL, _FIXTURE_SSN, _FIXTURE_TAX_ID,
            _FIXTURE_DOB.isoformat(),
        ]
        for d in decisions_under_test:
            for sub in fixture_substrings:
                assert sub not in d.reason, (
                    f"PII leaked into reason: {sub} / {d.reason}"
                )
                for v in d.details.values():
                    assert sub not in str(v), (
                        f"PII leaked into details value: {sub} / {v}"
                    )


# =============================================================================
# T24 — Public API surface (AC-R11-*)
# =============================================================================

class TestPublicAPI:
    def test_public_imports(self):
        from m2_m4_policy_engine import (
            AuthorityPolicy,
            DECISION_TO_COMPLIANCE_DECISION,
            Decision,
            MnpiPolicy,
            PolicyDecision,
            PolicyInput,
            UnsupportedTypeForFilterError,
        )
        assert AuthorityPolicy().list_rules()
        assert MnpiPolicy().list_rules()
        assert Decision.ALLOW.value == "ALLOW"
        assert issubclass(UnsupportedTypeForFilterError, TypeError)
        assert DECISION_TO_COMPLIANCE_DECISION[Decision.ESCALATE] == (
            "REQUIRE_APPROVAL"
        )
        claims = _make_claims()
        inp = PolicyInput(identity=claims, action="client.read")
        assert inp.action == "client.read"
        pd = PolicyDecision(
            decision=Decision.ALLOW,
            reason="ok",
            rule_applied="authority/advisor/read_own_clients.v1",
            wsp_section="WSP-ADV-1.1",
        )
        assert pd.decision == Decision.ALLOW

    def test_all_contains_expected(self):
        import m2_m4_policy_engine as pkg
        expected = {
            "Decision", "PolicyDecision", "PolicyInput", "MAX_REASON_LEN",
            "DECISION_TO_COMPLIANCE_DECISION",
            "PolicyRule", "RULE_APPLIED_RE", "WSP_SECTION_RE",
            "AuthorityPolicy", "MnpiPolicy", "UnsupportedTypeForFilterError",
        }
        assert set(pkg.__all__) == expected


# =============================================================================
# T25 — Integration smoke test (executable contract, F23)
# =============================================================================

class TestIntegrationSmoke:
    def test_advisor_reads_own_client_and_filters_pii(self):
        claims = _make_claims(sub="sarah@acme.com", role=Role.advisor)
        inp = PolicyInput(
            identity=claims, action="client.read",
            target={"advisor_id": "sarah@acme.com", "client_id": "C1"},
            context={},
        )
        auth = AuthorityPolicy()
        decision = auth.evaluate(inp)
        assert decision.decision == Decision.ALLOW
        assert decision.rule_applied == "authority/advisor/read_own_clients.v1"
        assert decision.wsp_section == "WSP-ADV-1.1"

        mnpi_pol = MnpiPolicy()
        client = _make_client()
        filtered = mnpi_pol.filter(claims, client)
        assert filtered.ssn_last_four is None
        assert filtered.date_of_birth is None
        assert filtered.tax_id is None
        assert filtered.email == client.email
        assert filtered.canonical_id == client.canonical_id


# =============================================================================
# T26 — M1/M3/M5 drift tests
# =============================================================================

class TestDrift:
    def test_m1_role_compliance_officer_exists(self):
        assert Role.compliance_officer.value == "compliance_officer"

    def test_m5_archetypes(self):
        assert Archetype.tier1_investment_bank.value == "tier1_investment_bank"
        assert Archetype.tier5_hedge_fund.value == "tier5_hedge_fund"

    def test_m5_registration_types(self):
        assert RegistrationType.bd_only.value == "bd_only"
        assert RegistrationType.dual_registered.value == "dual_registered"

    def test_m3_client_pii_fields(self):
        assert "ssn_last_four" in Client.model_fields
        assert "date_of_birth" in Client.model_fields
        assert "tax_id" in Client.model_fields

    def test_m3_beneficiary_account_number(self):
        assert "account_number" in Beneficiary.model_fields

    def test_m3_payment_beneficiary_field(self):
        assert "beneficiary" in PaymentInstruction.model_fields

    def test_m3_security_mnpi_flag(self):
        assert "mnpi_flag" in SecurityProfile.model_fields

    def test_aidclaims_authority_excludes_is_list(self):
        claims = _make_claims()
        assert isinstance(claims.authority_excludes, list)
