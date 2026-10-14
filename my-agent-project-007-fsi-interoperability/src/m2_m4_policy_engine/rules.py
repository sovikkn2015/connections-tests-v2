"""
M2/M4 Policy Engine — rules.py

PolicyRule protocol, regex constants for rule_applied and wsp_section
validation, and the shared `_require` helper used by rules to fail
closed on missing target/context keys.

Source: spec sections 1-2 (R1.5, R2.1, R2.4, R10, R12).
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from m2_m4_policy_engine.decisions import Decision, PolicyDecision, PolicyInput

# =============================================================================
# Regex constants (AC-R2-3, AC-R2-4, AC-R10-3, AC-R12-1)
# =============================================================================

#: Matches Phase-1 rule IDs. Future Rego package path: the part before
#: ``.v<N>`` becomes the OPA package; the ``vN`` suffix becomes the
#: rule version. Example: ``authority/advisor/restricted_list.v1`` ->
#: ``authority.advisor.restricted_list`` rule ``v1``.
RULE_APPLIED_RE: re.Pattern[str] = re.compile(
    r"^(authority|mnpi)/[a-z_]+/[a-z_]+\.v\d+$"
)

#: Matches WSP section identifiers per steering rule 19.
#: Examples: ``WSP-ADV-1.1``, ``WSP-FINRA-2210``, ``WSP-META-0.0``.
WSP_SECTION_RE: re.Pattern[str] = re.compile(
    r"^WSP-[A-Z]+-\d+(\.\d+)?$"
)

#: Allowed rule_kind values (entries in rule_table()).
VALID_RULE_KINDS: frozenset[str] = frozenset(
    {"authority_gate", "authority_meta", "mnpi_filter", "mnpi_access"}
)


# =============================================================================
# PolicyRule Protocol (structural typing)
# =============================================================================

@runtime_checkable
class PolicyRule(Protocol):
    """Structural contract every M2/M4 rule implements.

    An implementation returns:
      * None  — rule abstains / does not apply.
      * PolicyDecision(decision=ALLOW|DENY|ESCALATE, ...) — vote.

    The engine enforces deny-overrides semantics (spec R2.2).
    """

    name: str
    rule_applied: str
    wsp_section: str
    archetypes: frozenset  # frozenset[Archetype] — empty means all
    actions: frozenset     # frozenset[str] — empty means all
    rule_kind: str         # one of VALID_RULE_KINDS
    decision_kinds: frozenset  # subset of {"ALLOW","DENY","ESCALATE"}

    def evaluate(
        self, inp: PolicyInput
    ) -> Optional[PolicyDecision]: ...


# =============================================================================
# Shared helper: _require
# =============================================================================

def _require(
    mapping: Mapping[str, Any],
    key: str,
    mapping_name: str,
    rule_applied: str,
    wsp_section: str,
) -> tuple[Any, Optional[PolicyDecision]]:
    """Fetch ``key`` from ``mapping`` with fail-closed semantics.

    Returns ``(value, None)`` on success or ``(None, DENY-decision)``
    when the key is missing or the value is None.

    ``mapping_name`` is the dict name used in the DENY reason —
    either ``"target"`` or ``"context"`` (R1.5).
    """
    if key not in mapping or mapping[key] is None:
        return None, PolicyDecision(
            decision=Decision.DENY,
            reason=f"missing_{mapping_name}:{key}",
            rule_applied=rule_applied,
            wsp_section=wsp_section,
            details={},
        )
    return mapping[key], None
