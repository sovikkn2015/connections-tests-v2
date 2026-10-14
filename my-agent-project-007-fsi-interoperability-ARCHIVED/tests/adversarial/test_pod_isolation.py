"""
Adversarial Tests — Pod Isolation (5 tests).

Tier 5 hedge fund actor tries to access another pod's data.
Uses the local policy evaluator from policy_client.py directly.

Pod isolation is enforced by both M2 (authority) and M4 (MNPI filter).
These tests verify that cross-pod access is DENIED at both layers.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# ── Package registration for m2-m4-policy-engine ─────────────────

_m2m4_dir = Path(__file__).resolve().parents[2] / "src" / "m2-m4-policy-engine"
_m2m4_pkg = "m2_m4_policy_engine"
if _m2m4_pkg not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _m2m4_pkg,
        _m2m4_dir / "__init__.py",
        submodule_search_locations=[str(_m2m4_dir)],
    )
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_m2m4_pkg] = _mod
    _spec.loader.exec_module(_mod)

for _submod in ("models", "policy_client"):
    _full = f"{_m2m4_pkg}.{_submod}"
    if _full not in sys.modules:
        _sub_spec = importlib.util.spec_from_file_location(
            _full,
            _m2m4_dir / f"{_submod}.py",
            submodule_search_locations=[str(_m2m4_dir)],
        )
        _sub_mod = importlib.util.module_from_spec(_sub_spec)
        sys.modules[_full] = _sub_mod
        _sub_spec.loader.exec_module(_sub_mod)

from m2_m4_policy_engine.models import (
    Archetype,
    AuthorityDecision,
    IdentityContext,
    MnpiFilterInput,
    PolicyInput,
    Role,
)
from m2_m4_policy_engine.policy_client import (
    evaluate_authority_local,
    evaluate_mnpi_filter_local,
)


# ── Helper: Tier 5 HF identity ──────────────────────────────────


def _hf_identity(pod_id: str = "pod-alpha") -> IdentityContext:
    return IdentityContext(
        actor_type="human",
        archetype=Archetype.tier5_hedge_fund,
        role=Role.portfolio_manager,
        firm_id="hf-firm-001",
        jurisdiction="US",
        authority_scope=["portfolio.read", "positions.read", "client.read"],
        authority_excludes=[],
        client_scope=[],
        pod_id=pod_id,
    )


# ═══════════════════════════════════════════════════════════════════
# POD ISOLATION TESTS
# ═══════════════════════════════════════════════════════════════════


class TestPodIsolation:
    """5 tests: Tier 5 hedge fund pod boundary enforcement."""

    # ── Test 1: Cross-pod authority DENIED ────────────────────────

    def test_cross_pod_authority_denied(self):
        """Actor in pod-alpha cannot access pod-beta via M2 authority."""
        identity = _hf_identity(pod_id="pod-alpha")
        policy_input = PolicyInput(
            identity=identity,
            action="portfolio.read",
            context={"target_pod_id": "pod-beta"},
        )
        result = evaluate_authority_local(policy_input)
        assert result.decision == AuthorityDecision.DENY
        assert "pod" in result.reason.lower()

    # ── Test 2: Same-pod authority ALLOWED ────────────────────────

    def test_same_pod_authority_allowed(self):
        """Actor in pod-alpha CAN access pod-alpha data."""
        identity = _hf_identity(pod_id="pod-alpha")
        policy_input = PolicyInput(
            identity=identity,
            action="portfolio.read",
            context={"target_pod_id": "pod-alpha"},
        )
        result = evaluate_authority_local(policy_input)
        assert result.decision == AuthorityDecision.ALLOW

    # ── Test 3: Cross-pod MNPI filter strips position data ────────

    def test_cross_pod_mnpi_strips_positions(self):
        """M4 filter strips position fields for cross-pod access."""
        filter_input = MnpiFilterInput(
            data_payload={
                "name": "Fund Alpha",
                "positions": [{"ticker": "AAPL", "qty": 10000}],
                "holdings": {"total": 5000000},
                "pnl": 250000,
                "nav": 10000000,
                "exposure": 0.85,
            },
            archetype=Archetype.tier5_hedge_fund,
            role=Role.portfolio_manager,
            jurisdiction="US",
            pod_id="pod-alpha",
            target_pod_id="pod-beta",
        )
        result = evaluate_mnpi_filter_local(filter_input)
        # All position fields must be stripped
        assert "positions" not in result.filtered_payload
        assert "holdings" not in result.filtered_payload
        assert "pnl" not in result.filtered_payload
        assert "nav" not in result.filtered_payload
        assert "exposure" not in result.filtered_payload
        # Non-position fields should remain
        assert "name" in result.filtered_payload

    # ── Test 4: Cross-pod with different pod IDs ──────────────────

    def test_cross_pod_different_ids_denied(self):
        """Any two different pod IDs must trigger isolation."""
        identity = _hf_identity(pod_id="pod-quant-1")
        policy_input = PolicyInput(
            identity=identity,
            action="positions.read",
            context={"target_pod_id": "pod-macro-2"},
        )
        result = evaluate_authority_local(policy_input)
        assert result.decision == AuthorityDecision.DENY

    # ── Test 5: Null target pod allows access ─────────────────────

    def test_null_target_pod_allows_access(self):
        """
        When target_pod_id is not specified (None), pod isolation
        does not apply — the request is evaluated normally.
        """
        identity = _hf_identity(pod_id="pod-alpha")
        policy_input = PolicyInput(
            identity=identity,
            action="portfolio.read",
            context={},  # No target_pod_id
        )
        result = evaluate_authority_local(policy_input)
        assert result.decision == AuthorityDecision.ALLOW
