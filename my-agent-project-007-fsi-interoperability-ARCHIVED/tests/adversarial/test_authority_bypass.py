"""
Adversarial Tests — Authority Bypass (5 tests).

Attempts to bypass authority checks:
  - Missing AID / empty authority_scope
  - Expired token (simulated via empty scope)
  - Excluded action attempted
  - Wildcard abuse
  - Action not in scope

Uses the local policy evaluator from policy_client.py directly.
Default: DENY (fail-closed). No degraded mode.
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
    PolicyInput,
    Role,
)
from m2_m4_policy_engine.policy_client import evaluate_authority_local


# ═══════════════════════════════════════════════════════════════════
# AUTHORITY BYPASS TESTS
# ═══════════════════════════════════════════════════════════════════


class TestAuthorityBypass:
    """5 tests: attempts to bypass authority checks."""

    # ── Test 1: Empty authority_scope — DENIED ────────────────────

    def test_empty_authority_scope_denied(self):
        """
        Actor with empty authority_scope cannot perform any action.
        Simulates a misconfigured or revoked AID.
        """
        identity = IdentityContext(
            actor_type="human",
            archetype=Archetype.tier4_independent_ria,
            role=Role.advisor,
            firm_id="firm-001",
            jurisdiction="US",
            authority_scope=[],  # No permissions
            authority_excludes=[],
            client_scope=[],
        )
        policy_input = PolicyInput(
            identity=identity,
            action="client.read",
            context={},
        )
        result = evaluate_authority_local(policy_input)
        assert result.decision == AuthorityDecision.DENY
        assert "not in authority_scope" in result.reason.lower() or "scope" in result.reason.lower()

    # ── Test 2: Excluded action attempted — DENIED ────────────────

    def test_excluded_action_denied(self):
        """
        Action in authority_excludes is always denied, even if
        it matches authority_scope.
        """
        identity = IdentityContext(
            actor_type="human",
            archetype=Archetype.tier3_broker_dealer,
            role=Role.advisor,
            firm_id="bd-firm-001",
            jurisdiction="US",
            authority_scope=["client.*", "order.*"],
            authority_excludes=["order.submit"],  # Explicitly excluded
            client_scope=[],
        )
        policy_input = PolicyInput(
            identity=identity,
            action="order.submit",
            context={},
        )
        result = evaluate_authority_local(policy_input)
        assert result.decision == AuthorityDecision.DENY
        assert "excluded" in result.reason.lower()

    # ── Test 3: Wildcard scope does not override excludes ─────────

    def test_wildcard_scope_does_not_override_excludes(self):
        """
        Even with wildcard '*' in authority_scope, an action in
        authority_excludes must still be DENIED.
        """
        identity = IdentityContext(
            actor_type="human",
            archetype=Archetype.tier4_independent_ria,
            role=Role.admin,
            firm_id="firm-001",
            jurisdiction="US",
            authority_scope=["*"],  # Wildcard — everything
            authority_excludes=["account.close"],  # But this is excluded
            client_scope=[],
        )
        policy_input = PolicyInput(
            identity=identity,
            action="account.close",
            context={},
        )
        result = evaluate_authority_local(policy_input)
        assert result.decision == AuthorityDecision.DENY

    # ── Test 4: Action outside scope pattern — DENIED ─────────────

    def test_action_outside_scope_pattern_denied(self):
        """
        Actor with 'client.*' scope cannot perform 'order.submit'.
        Wildcard prefix matching must be strict.
        """
        identity = IdentityContext(
            actor_type="human",
            archetype=Archetype.tier4_independent_ria,
            role=Role.advisor,
            firm_id="firm-001",
            jurisdiction="US",
            authority_scope=["client.*"],  # Only client actions
            authority_excludes=[],
            client_scope=[],
        )
        policy_input = PolicyInput(
            identity=identity,
            action="order.submit",  # Not in client.* scope
            context={},
        )
        result = evaluate_authority_local(policy_input)
        assert result.decision == AuthorityDecision.DENY

    # ── Test 5: Wildcard prefix must match exactly ────────────────

    def test_wildcard_prefix_exact_match(self):
        """
        'client.*' must match 'client.read' but NOT 'clientele.read'.
        The prefix must be followed by a dot.
        """
        identity = IdentityContext(
            actor_type="human",
            archetype=Archetype.tier4_independent_ria,
            role=Role.advisor,
            firm_id="firm-001",
            jurisdiction="US",
            authority_scope=["client.*"],
            authority_excludes=[],
            client_scope=[],
        )

        # 'client.read' should match
        result_match = evaluate_authority_local(PolicyInput(
            identity=identity,
            action="client.read",
            context={},
        ))
        assert result_match.decision == AuthorityDecision.ALLOW

        # 'clientele.read' should NOT match 'client.*'
        result_no_match = evaluate_authority_local(PolicyInput(
            identity=identity,
            action="clientele.read",
            context={},
        ))
        assert result_no_match.decision == AuthorityDecision.DENY
