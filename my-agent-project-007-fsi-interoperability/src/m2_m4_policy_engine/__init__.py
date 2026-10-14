"""
M2/M4 Policy Engine — Public API.

M2 Authority Policy + M4 MNPI Policy. Deterministic, no LLM,
fail-closed. Phase 1: Python rules with Rego-style metadata
(rule_applied, wsp_section, archetype, action). Phase 2: port to
OPA/Rego bundles; Python engine becomes the test oracle.

Usage:
    from m2_m4_policy_engine import (
        AuthorityPolicy, MnpiPolicy,
        PolicyDecision, PolicyInput, Decision,
    )
    authority = AuthorityPolicy()
    mnpi = MnpiPolicy()
    decision = authority.evaluate(PolicyInput(
        identity=aid_claims,
        action="client.read",
        target={"client_id": "CLT-1", "advisor_id": aid_claims.sub},
    ))
    filtered = mnpi.filter(aid_claims, client_instance, strict=True)

See `.kiro/specs/m2-m4-policy-engine.md` for the full contract.
"""

from __future__ import annotations

from m2_m4_policy_engine.decisions import (
    DECISION_TO_COMPLIANCE_DECISION,
    MAX_REASON_LEN,
    Decision,
    PolicyDecision,
    PolicyInput,
)
from m2_m4_policy_engine.rules import (
    RULE_APPLIED_RE,
    WSP_SECTION_RE,
    PolicyRule,
)
from m2_m4_policy_engine.authority import AuthorityPolicy
from m2_m4_policy_engine.mnpi import MnpiPolicy, UnsupportedTypeForFilterError

__all__ = [
    # Decisions + inputs
    "Decision",
    "PolicyDecision",
    "PolicyInput",
    "MAX_REASON_LEN",
    "DECISION_TO_COMPLIANCE_DECISION",
    # Rule protocol + regexes
    "PolicyRule",
    "RULE_APPLIED_RE",
    "WSP_SECTION_RE",
    # Policies
    "AuthorityPolicy",
    "MnpiPolicy",
    "UnsupportedTypeForFilterError",
]
