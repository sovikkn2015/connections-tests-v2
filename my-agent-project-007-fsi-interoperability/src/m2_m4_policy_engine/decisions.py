"""
M2/M4 Policy Engine — decisions.py

Decision enum, PolicyDecision dataclass, PolicyInput dataclass, and the
DECISION_TO_COMPLIANCE_DECISION mapping consumed by M6 when writing
ComplianceCheck records to M10.

Source: spec section 1 (R1.1, R1.2, R1.3, R1.6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from m1_identity import AidClaims

# =============================================================================
# Constants
# =============================================================================

MAX_REASON_LEN: int = 200


# =============================================================================
# Decision enum (3 values)
# =============================================================================

class Decision(str, Enum):
    """M2/M4 outcome. ALLOW, DENY, or ESCALATE.

    See R1.1. WARN and REQUIRE_APPROVAL from M3 ComplianceDecision are
    NOT in scope for M2/M4 Phase 1.
    """

    ALLOW = "ALLOW"
    DENY = "DENY"
    ESCALATE = "ESCALATE"


# =============================================================================
# Decision -> M3 ComplianceDecision mapping (F11)
# =============================================================================

#: Stable mapping consumed by M6 when writing ComplianceCheck records
#: to M10. M2/M4 returns Decision; M6 translates on audit. M2/M4 does
#: not import m3_schema_registry for compliance decision types to keep
#: the boundary tight; M6 imports both modules and owns the mapping.
DECISION_TO_COMPLIANCE_DECISION: dict[Decision, str] = {
    Decision.ALLOW: "ALLOW",
    Decision.DENY: "DENY",
    Decision.ESCALATE: "REQUIRE_APPROVAL",
}


# =============================================================================
# PolicyDecision dataclass
# =============================================================================

@dataclass(frozen=True)
class PolicyDecision:
    """Immutable outcome of a policy evaluation.

    frozen=True — cannot be mutated after construction.

    reason MUST NOT contain PII/MNPI. rule_applied and wsp_section
    MUST be non-empty (validated at construction). reason is bounded
    at MAX_REASON_LEN characters.
    """

    decision: Decision
    reason: str
    rule_applied: str
    wsp_section: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.decision, Decision):
            raise TypeError("decision must be Decision")
        if not self.reason or len(self.reason) > MAX_REASON_LEN:
            raise ValueError(
                f"reason must be non-empty and <={MAX_REASON_LEN} chars"
            )
        if not self.rule_applied:
            raise ValueError("rule_applied must be non-empty")
        if not self.wsp_section:
            raise ValueError("wsp_section must be non-empty")


# =============================================================================
# PolicyInput dataclass
# =============================================================================

@dataclass(frozen=True)
class PolicyInput:
    """Immutable input to AuthorityPolicy.evaluate.

    identity  — verified AidClaims (M1 validated).
    action    — dotted action name from catalog (spec R1.4).
    target    — WHAT the action operates on.
    context   — environmental data (restricted_list, windows, etc).

    NOTE: identity.archetype is a string (not Archetype enum) — see
    m1_identity.AidClaims for the stored type.
    """

    identity: AidClaims
    action: str
    target: Mapping[str, Any] = field(default_factory=dict)
    context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.identity, AidClaims):
            raise TypeError("identity must be AidClaims")
        if not self.action:
            raise ValueError("action must be non-empty")
