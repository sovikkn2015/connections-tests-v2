"""
Adversarial Tests — Client Scope Enforcement (5 tests).

Advisor tries to access clients not in their client_scope.
Uses the local policy evaluator from policy_client.py directly.

Client scope is enforced by both M2 (authority) and M4 (MNPI filter).
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


# ── Helper: RIA advisor with limited client scope ────────────────


def _advisor_identity(
    client_scope: list[str] | None = None,
) -> IdentityContext:
    return IdentityContext(
        actor_type="human",
        archetype=Archetype.tier4_independent_ria,
        role=Role.advisor,
        firm_id="ria-firm-001",
        jurisdiction="US",
        authority_scope=["client.read", "portfolio.read", "client.update"],
        authority_excludes=[],
        client_scope=client_scope or ["C-100", "C-200", "C-300"],
    )


# ═══════════════════════════════════════════════════════════════════
# CLIENT SCOPE TESTS
# ═══════════════════════════════════════════════════════════════════


class TestClientScope:
    """5 tests: advisor cannot access clients outside their scope."""

    # ── Test 1: Access own client — ALLOWED ──────────────────────

    def test_own_client_allowed(self):
        """Advisor can access a client in their client_scope."""
        identity = _advisor_identity(client_scope=["C-100", "C-200"])
        policy_input = PolicyInput(
            identity=identity,
            action="client.read",
            target_id="C-100",
            context={"client_id": "C-100"},
        )
        result = evaluate_authority_local(policy_input)
        assert result.decision == AuthorityDecision.ALLOW

    # ── Test 2: Access other advisor's client — DENIED ────────────

    def test_other_advisors_client_denied(self):
        """Advisor cannot access a client NOT in their client_scope."""
        identity = _advisor_identity(client_scope=["C-100", "C-200"])
        policy_input = PolicyInput(
            identity=identity,
            action="client.read",
            target_id="C-999",
            context={"client_id": "C-999"},
        )
        result = evaluate_authority_local(policy_input)
        assert result.decision == AuthorityDecision.DENY
        assert "client_scope" in result.reason.lower() or "client" in result.reason.lower()

    # ── Test 3: MNPI filter strips all fields for out-of-scope ────

    def test_mnpi_filter_strips_all_for_out_of_scope_client(self):
        """M4 filter strips ALL fields when client is out of scope."""
        filter_input = MnpiFilterInput(
            data_payload={
                "name": "Secret Client",
                "portfolio": "aggressive",
                "balance": 1000000,
            },
            archetype=Archetype.tier4_independent_ria,
            role=Role.advisor,
            jurisdiction="US",
            client_scope=["C-100", "C-200"],
            target_client_id="C-999",  # Not in scope
        )
        result = evaluate_mnpi_filter_local(filter_input)
        # ALL fields must be stripped — access denied
        assert result.filtered_payload == {}
        assert len(result.fields_removed) == 3

    # ── Test 4: Empty client_scope means no restriction ───────────

    def test_empty_client_scope_allows_all(self):
        """
        When client_scope is empty, no client restriction applies.
        (Admin or system-level actors may have empty scope.)
        """
        identity = _advisor_identity(client_scope=[])
        policy_input = PolicyInput(
            identity=identity,
            action="client.read",
            context={},
        )
        result = evaluate_authority_local(policy_input)
        # Empty scope = no restriction on client access
        assert result.decision == AuthorityDecision.ALLOW

    # ── Test 5: Client scope checked via target_id fallback ───────

    def test_client_scope_via_target_id(self):
        """
        When context has no client_id, target_id is used as fallback.
        Out-of-scope target_id must be DENIED.
        """
        identity = _advisor_identity(client_scope=["C-100"])
        policy_input = PolicyInput(
            identity=identity,
            action="client.read",
            target_id="C-FORBIDDEN",
            context={},  # No client_id in context
        )
        result = evaluate_authority_local(policy_input)
        assert result.decision == AuthorityDecision.DENY
