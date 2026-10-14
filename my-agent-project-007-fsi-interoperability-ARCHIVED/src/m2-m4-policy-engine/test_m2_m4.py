"""
Integration tests for M2/M4 Unified Authority + MNPI Policy Engine.

Tests cover:
  - Authority ALLOW for valid scope
  - Authority DENY for excluded action
  - Authority DENY for out-of-scope action
  - Client scope enforcement (advisor can't access other advisor's clients)
  - Pod isolation (HF PM can't see other pod's positions)
  - MNPI filter strips SSN/DOB for tier3 advisor
  - MNPI filter strips PII for tier4 advisor
  - Fail-closed when OPA unreachable
  - Every policy output includes wsp_section
  - FastAPI endpoint integration

Uses in-memory local evaluator (no OPA server required for tests).
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Set local evaluator BEFORE importing app
os.environ["USE_LOCAL_EVALUATOR"] = "true"

# Handle hyphenated directory name for imports
import importlib
import sys
from pathlib import Path

_module_dir = Path(__file__).parent
if str(_module_dir.parent) not in sys.path:
    sys.path.insert(0, str(_module_dir.parent))

_pkg = "m2_m4_policy_engine"
if _pkg not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _pkg, _module_dir / "__init__.py",
        submodule_search_locations=[str(_module_dir)],
    )
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_pkg] = _mod
    _spec.loader.exec_module(_mod)

# Register submodules
for _sub in ("models", "policy_client", "app"):
    _sub_full = f"{_pkg}.{_sub}"
    if _sub_full not in sys.modules:
        _sub_spec = importlib.util.spec_from_file_location(
            _sub_full, _module_dir / f"{_sub}.py",
        )
        _sub_mod = importlib.util.module_from_spec(_sub_spec)
        _sub_mod.__package__ = _pkg
        sys.modules[_sub_full] = _sub_mod
        _sub_spec.loader.exec_module(_sub_mod)

from m2_m4_policy_engine.app import app  # noqa: E402
from m2_m4_policy_engine.models import (  # noqa: E402
    Archetype,
    AuthorityDecision,
    IdentityContext,
    MnpiFilterInput,
    PolicyInput,
    Role,
)
from m2_m4_policy_engine.policy_client import (  # noqa: E402
    evaluate_authority_local,
    evaluate_mnpi_filter_local,
)

client = TestClient(app)



# ── Test fixtures ────────────────────────────────────────────────


def _make_identity(**overrides) -> IdentityContext:
    """Create a test identity with sensible defaults."""
    defaults = dict(
        actor_type="human",
        archetype=Archetype.tier3_broker_dealer,
        role=Role.advisor,
        firm_id="firm-001",
        jurisdiction="US",
        authority_scope=["client.*", "portfolio.*"],
        authority_excludes=[],
        client_scope=["C-100", "C-101", "C-102"],
        pod_id=None,
    )
    defaults.update(overrides)
    return IdentityContext(**defaults)


def _make_policy_input(identity: IdentityContext, action: str, **ctx) -> PolicyInput:
    return PolicyInput(identity=identity, action=action, context=ctx)


# ═══════════════════════════════════════════════════════════════════
# M2 AUTHORITY TESTS
# ═══════════════════════════════════════════════════════════════════


class TestAuthorityAllow:
    """Authority ALLOW for valid scope."""

    def test_allow_action_in_scope(self):
        identity = _make_identity()
        pi = _make_policy_input(identity, "client.read")
        result = evaluate_authority_local(pi)
        assert result.decision == AuthorityDecision.ALLOW
        assert result.wsp_section  # wsp_section must be present

    def test_allow_wildcard_scope(self):
        identity = _make_identity(authority_scope=["*"])
        pi = _make_policy_input(identity, "anything.goes")
        result = evaluate_authority_local(pi)
        assert result.decision == AuthorityDecision.ALLOW

    def test_allow_with_matching_client_scope(self):
        identity = _make_identity(client_scope=["C-100", "C-101"])
        pi = _make_policy_input(identity, "client.read", client_id="C-100")
        result = evaluate_authority_local(pi)
        assert result.decision == AuthorityDecision.ALLOW


class TestAuthorityDenyExcluded:
    """Authority DENY for excluded action."""

    def test_deny_excluded_action(self):
        identity = _make_identity(authority_excludes=["order.submit"])
        pi = _make_policy_input(identity, "order.submit")
        result = evaluate_authority_local(pi)
        assert result.decision == AuthorityDecision.DENY
        assert "excluded" in result.reason.lower()
        assert result.wsp_section

    def test_deny_excluded_wildcard(self):
        identity = _make_identity(authority_excludes=["order.*"])
        pi = _make_policy_input(identity, "order.submit")
        result = evaluate_authority_local(pi)
        assert result.decision == AuthorityDecision.DENY


class TestAuthorityDenyOutOfScope:
    """Authority DENY for out-of-scope action."""

    def test_deny_action_not_in_scope(self):
        identity = _make_identity(authority_scope=["client.read"])
        pi = _make_policy_input(identity, "order.submit")
        result = evaluate_authority_local(pi)
        assert result.decision == AuthorityDecision.DENY
        assert "not in authority_scope" in result.reason
        assert result.wsp_section


class TestClientScopeEnforcement:
    """Client scope enforcement — advisor can't access other advisor's clients."""

    def test_deny_access_to_other_advisors_client(self):
        identity = _make_identity(client_scope=["C-100", "C-101"])
        pi = _make_policy_input(identity, "client.read", client_id="C-999")
        result = evaluate_authority_local(pi)
        assert result.decision == AuthorityDecision.DENY
        assert "client_scope" in result.reason.lower() or "C-999" in result.reason
        assert result.wsp_section

    def test_allow_access_to_own_client(self):
        identity = _make_identity(client_scope=["C-100", "C-101"])
        pi = _make_policy_input(identity, "client.read", client_id="C-100")
        result = evaluate_authority_local(pi)
        assert result.decision == AuthorityDecision.ALLOW

    def test_empty_client_scope_allows_all(self):
        """Admin/system with empty client_scope can access any client."""
        identity = _make_identity(client_scope=[], role=Role.admin)
        pi = _make_policy_input(identity, "client.read", client_id="C-999")
        result = evaluate_authority_local(pi)
        assert result.decision == AuthorityDecision.ALLOW


class TestPodIsolation:
    """Pod isolation — HF PM can't see other pod's positions."""

    def test_deny_cross_pod_access(self):
        identity = _make_identity(
            archetype=Archetype.tier5_hedge_fund,
            role=Role.portfolio_manager,
            pod_id="pod-alpha",
            authority_scope=["portfolio.*"],
        )
        pi = _make_policy_input(
            identity, "portfolio.read", target_pod_id="pod-beta"
        )
        result = evaluate_authority_local(pi)
        assert result.decision == AuthorityDecision.DENY
        assert "pod" in result.reason.lower()
        assert result.wsp_section

    def test_allow_same_pod_access(self):
        identity = _make_identity(
            archetype=Archetype.tier5_hedge_fund,
            role=Role.portfolio_manager,
            pod_id="pod-alpha",
            authority_scope=["portfolio.*"],
        )
        pi = _make_policy_input(
            identity, "portfolio.read", target_pod_id="pod-alpha"
        )
        result = evaluate_authority_local(pi)
        assert result.decision == AuthorityDecision.ALLOW


class TestEscalation:
    """Sensitive actions by agent actors require escalation."""

    def test_escalate_agent_order_submit(self):
        identity = _make_identity(
            actor_type="agent",
            role=Role.agent_execution,
            authority_scope=["order.*"],
        )
        pi = _make_policy_input(identity, "order.submit")
        result = evaluate_authority_local(pi)
        assert result.decision == AuthorityDecision.ESCALATE
        assert "human approval" in result.reason.lower()
        assert result.wsp_section == "5.1"

    def test_no_escalation_for_human(self):
        identity = _make_identity(authority_scope=["order.*"])
        pi = _make_policy_input(identity, "order.submit")
        result = evaluate_authority_local(pi)
        assert result.decision == AuthorityDecision.ALLOW



# ═══════════════════════════════════════════════════════════════════
# M4 MNPI FILTER TESTS
# ═══════════════════════════════════════════════════════════════════


class TestMnpiTier3Advisor:
    """MNPI filter strips SSN/DOB for tier3 advisor."""

    def test_strips_pii_fields(self):
        fi = MnpiFilterInput(
            data_payload={
                "name": "Henderson",
                "ssn": "123-45-6789",
                "dob": "1970-01-01",
                "holdings": [{"ticker": "AAPL", "shares": 100}],
                "email": "henderson@example.com",
            },
            archetype=Archetype.tier3_broker_dealer,
            role=Role.advisor,
            client_scope=["C-100"],
            target_client_id="C-100",
        )
        result = evaluate_mnpi_filter_local(fi)
        assert "ssn" not in result.filtered_payload
        assert "dob" not in result.filtered_payload
        assert "email" not in result.filtered_payload
        assert "name" in result.filtered_payload
        assert "holdings" in result.filtered_payload  # Tier 3 keeps holdings
        assert "ssn" in result.fields_removed
        assert "dob" in result.fields_removed
        assert result.wsp_section
        assert len(result.filter_log) > 0  # Filter log MUST be produced

    def test_keeps_non_pii_fields(self):
        fi = MnpiFilterInput(
            data_payload={"name": "Henderson", "risk_tolerance": "moderate"},
            archetype=Archetype.tier3_broker_dealer,
            role=Role.advisor,
        )
        result = evaluate_mnpi_filter_local(fi)
        assert result.filtered_payload == {"name": "Henderson", "risk_tolerance": "moderate"}
        assert result.fields_removed == []


class TestMnpiTier4Advisor:
    """MNPI filter strips PII for tier4 advisor, own clients only."""

    def test_strips_pii(self):
        fi = MnpiFilterInput(
            data_payload={
                "name": "Client A",
                "ssn": "999-88-7777",
                "dob": "1985-06-15",
                "phone": "555-0100",
                "portfolio_value": 500000,
            },
            archetype=Archetype.tier4_independent_ria,
            role=Role.advisor,
            client_scope=["C-200"],
            target_client_id="C-200",
        )
        result = evaluate_mnpi_filter_local(fi)
        assert "ssn" not in result.filtered_payload
        assert "dob" not in result.filtered_payload
        assert "phone" not in result.filtered_payload
        assert "portfolio_value" in result.filtered_payload
        assert result.wsp_section

    def test_denies_access_to_other_clients_data(self):
        fi = MnpiFilterInput(
            data_payload={"name": "Other Client", "ssn": "111-22-3333"},
            archetype=Archetype.tier4_independent_ria,
            role=Role.advisor,
            client_scope=["C-200"],
            target_client_id="C-999",  # Not in scope
        )
        result = evaluate_mnpi_filter_local(fi)
        assert result.filtered_payload == {}  # ALL fields stripped
        assert len(result.fields_removed) == 2


class TestMnpiPodIsolation:
    """Tier 5 HF pod isolation — strip cross-pod position data."""

    def test_strips_cross_pod_positions(self):
        fi = MnpiFilterInput(
            data_payload={
                "fund_name": "Alpha Fund",
                "positions": [{"ticker": "TSLA", "shares": 50000}],
                "pnl": 1200000,
                "nav": 50000000,
                "ssn": "000-00-0000",
            },
            archetype=Archetype.tier5_hedge_fund,
            role=Role.portfolio_manager,
            pod_id="pod-alpha",
            target_pod_id="pod-beta",  # Different pod
        )
        result = evaluate_mnpi_filter_local(fi)
        assert "positions" not in result.filtered_payload
        assert "pnl" not in result.filtered_payload
        assert "nav" not in result.filtered_payload
        assert "ssn" not in result.filtered_payload  # PII also stripped
        assert "fund_name" in result.filtered_payload
        # Verify filter log categories
        categories = {e.mnpi_category for e in result.filter_log}
        assert "cross_pod" in categories
        assert "pii" in categories
        assert result.wsp_section

    def test_allows_same_pod_positions(self):
        fi = MnpiFilterInput(
            data_payload={
                "positions": [{"ticker": "TSLA", "shares": 50000}],
                "pnl": 1200000,
            },
            archetype=Archetype.tier5_hedge_fund,
            role=Role.portfolio_manager,
            pod_id="pod-alpha",
            target_pod_id="pod-alpha",  # Same pod
        )
        result = evaluate_mnpi_filter_local(fi)
        assert "positions" in result.filtered_payload
        assert "pnl" in result.filtered_payload


class TestMnpiChineseWall:
    """Tier 1 IB Chinese wall enforcement."""

    def test_strips_deal_pipeline_for_analyst(self):
        fi = MnpiFilterInput(
            data_payload={
                "deal_pipeline": [{"target": "ACME", "stage": "due_diligence"}],
                "ma_targets": ["XYZ Corp"],
                "public_filings": ["10-K"],
            },
            archetype=Archetype.tier1_investment_bank,
            role=Role.analyst,
        )
        result = evaluate_mnpi_filter_local(fi)
        assert "deal_pipeline" not in result.filtered_payload
        assert "ma_targets" not in result.filtered_payload
        assert "public_filings" in result.filtered_payload

    def test_compliance_officer_sees_all(self):
        fi = MnpiFilterInput(
            data_payload={
                "deal_pipeline": [{"target": "ACME"}],
                "ssn": "123-45-6789",
            },
            archetype=Archetype.tier1_investment_bank,
            role=Role.compliance_officer,
        )
        result = evaluate_mnpi_filter_local(fi)
        assert "deal_pipeline" in result.filtered_payload
        assert "ssn" in result.filtered_payload  # CO sees all
        assert result.fields_removed == []


class TestMnpiWspSection:
    """Every MNPI filter output includes wsp_section."""

    def test_wsp_section_always_present(self):
        for archetype in Archetype:
            fi = MnpiFilterInput(
                data_payload={"name": "Test", "ssn": "000-00-0000"},
                archetype=archetype,
                role=Role.advisor,
            )
            result = evaluate_mnpi_filter_local(fi)
            assert result.wsp_section, f"Missing wsp_section for {archetype}"


class TestFailClosed:
    """Fail-closed when OPA unreachable — tested via local deny helpers."""

    def test_authority_deny_helper(self):
        from m2_m4_policy_engine.policy_client import _deny_authority
        result = _deny_authority("OPA unreachable")
        assert result.decision == AuthorityDecision.DENY
        assert result.wsp_section

    def test_mnpi_deny_helper(self):
        from m2_m4_policy_engine.policy_client import _deny_mnpi
        payload = {"name": "Test", "ssn": "000", "holdings": []}
        result = _deny_mnpi(payload)
        assert result.filtered_payload == {}
        assert len(result.fields_removed) == 3
        assert result.wsp_section


# ═══════════════════════════════════════════════════════════════════
# FASTAPI ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════════


class TestAuthorityEndpoint:
    """POST /policy/authority endpoint integration."""

    def test_authority_allow(self):
        resp = client.post("/policy/authority", json={
            "identity": {
                "actor_type": "human",
                "archetype": "tier3_broker_dealer",
                "role": "advisor",
                "firm_id": "firm-001",
                "authority_scope": ["client.*"],
                "authority_excludes": [],
                "client_scope": [],
            },
            "action": "client.read",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["decision"] == "ALLOW"
        assert body["wsp_section"]

    def test_authority_deny(self):
        resp = client.post("/policy/authority", json={
            "identity": {
                "actor_type": "human",
                "archetype": "tier3_broker_dealer",
                "role": "advisor",
                "firm_id": "firm-001",
                "authority_scope": ["client.read"],
                "authority_excludes": [],
                "client_scope": [],
            },
            "action": "order.submit",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["decision"] == "DENY"


class TestMnpiEndpoint:
    """POST /policy/mnpi/filter endpoint integration."""

    def test_mnpi_filter_strips_pii(self):
        resp = client.post("/policy/mnpi/filter", json={
            "data_payload": {
                "name": "Henderson",
                "ssn": "123-45-6789",
                "dob": "1970-01-01",
            },
            "archetype": "tier3_broker_dealer",
            "role": "advisor",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "ssn" not in body["filtered_payload"]
        assert "dob" not in body["filtered_payload"]
        assert "name" in body["filtered_payload"]
        assert body["wsp_section"]
        assert len(body["filter_log"]) > 0


class TestBundlesEndpoint:
    """GET /policy/bundles endpoint."""

    def test_list_bundles(self):
        resp = client.get("/policy/bundles")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["bundles"]) == 2
        names = {b["name"] for b in body["bundles"]}
        assert "authority" in names
        assert "mnpi" in names


class TestHealthEndpoint:
    """GET /health endpoint."""

    def test_health_check(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["module"] == "m2-m4-policy-engine"
