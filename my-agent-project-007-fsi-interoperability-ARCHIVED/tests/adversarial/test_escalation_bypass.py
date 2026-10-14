"""
Adversarial Tests — Escalation Bypass (5 tests).

Agent actor tries to submit orders without HITL (Human-In-The-Loop)
approval. WSP 5.1 requires mandatory human approval for sensitive
actions (order.submit, wire.send, account.close) when actor_type=agent.

Uses the local policy evaluator from policy_client.py directly.
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


# ── Helper: Agent identity ───────────────────────────────────────


def _agent_identity(
    role: Role = Role.agent_execution,
    authority_scope: list[str] | None = None,
) -> IdentityContext:
    return IdentityContext(
        actor_type="agent",
        archetype=Archetype.tier4_independent_ria,
        role=role,
        firm_id="ria-firm-001",
        jurisdiction="US",
        authority_scope=authority_scope or [
            "client.read", "portfolio.read", "order.submit",
            "wire.send", "account.close",
        ],
        authority_excludes=[],
        client_scope=[],
    )


def _human_identity(
    authority_scope: list[str] | None = None,
) -> IdentityContext:
    return IdentityContext(
        actor_type="human",
        archetype=Archetype.tier4_independent_ria,
        role=Role.advisor,
        firm_id="ria-firm-001",
        jurisdiction="US",
        authority_scope=authority_scope or [
            "client.read", "portfolio.read", "order.submit",
            "wire.send", "account.close",
        ],
        authority_excludes=[],
        client_scope=[],
    )


# ═══════════════════════════════════════════════════════════════════
# ESCALATION BYPASS TESTS
# ═══════════════════════════════════════════════════════════════════


class TestEscalationBypass:
    """5 tests: agent actor cannot bypass HITL for sensitive actions."""

    # ── Test 1: Agent order.submit requires ESCALATION ────────────

    def test_agent_order_submit_escalates(self):
        """Agent submitting an order must get ESCALATE, not ALLOW."""
        identity = _agent_identity()
        policy_input = PolicyInput(
            identity=identity,
            action="order.submit",
            context={},
        )
        result = evaluate_authority_local(policy_input)
        assert result.decision == AuthorityDecision.ESCALATE
        assert "human approval" in result.reason.lower() or "escalat" in result.reason.lower()

    # ── Test 2: Agent wire.send requires ESCALATION ───────────────

    def test_agent_wire_send_escalates(self):
        """Agent sending a wire must get ESCALATE."""
        identity = _agent_identity()
        policy_input = PolicyInput(
            identity=identity,
            action="wire.send",
            context={},
        )
        result = evaluate_authority_local(policy_input)
        assert result.decision == AuthorityDecision.ESCALATE

    # ── Test 3: Agent account.close requires ESCALATION ───────────

    def test_agent_account_close_escalates(self):
        """Agent closing an account must get ESCALATE."""
        identity = _agent_identity()
        policy_input = PolicyInput(
            identity=identity,
            action="account.close",
            context={},
        )
        result = evaluate_authority_local(policy_input)
        assert result.decision == AuthorityDecision.ESCALATE

    # ── Test 4: Human can submit orders directly ──────────────────

    def test_human_order_submit_allowed(self):
        """Human advisor can submit orders without escalation."""
        identity = _human_identity()
        policy_input = PolicyInput(
            identity=identity,
            action="order.submit",
            context={},
        )
        result = evaluate_authority_local(policy_input)
        assert result.decision == AuthorityDecision.ALLOW

    # ── Test 5: Agent non-sensitive action is ALLOWED ─────────────

    def test_agent_read_action_allowed(self):
        """Agent performing a read action does not require escalation."""
        identity = _agent_identity()
        policy_input = PolicyInput(
            identity=identity,
            action="client.read",
            context={},
        )
        result = evaluate_authority_local(policy_input)
        assert result.decision == AuthorityDecision.ALLOW
