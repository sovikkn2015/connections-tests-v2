"""
Gap 1 — Enums + errors.

See .kiro/specs/gap1-reg-bi-doc-generator.md §2.2.
"""

from __future__ import annotations

from enum import Enum


class TriggerEventType(str, Enum):
    """Valid trigger events for Reg BI doc generation (R1.1)."""

    recommendation_draft = "recommendation.draft"
    research_rating_issued = "research.rating_issued"
    order_drafted_retail = "order.drafted_retail"


class ObligationCode(str, Enum):
    """Reg BI four-obligation codes (R3.0)."""

    DISCLOSURE = "disclosure"
    CARE = "care"
    COI = "coi"
    COMPLIANCE = "compliance"


class ApplicabilityResult(str, Enum):
    """Applicability gate outcome (R2.1)."""

    APPLICABLE = "applicable"
    SKIP_RIA = "skip_ria"
    SKIP_INSTITUTIONAL = "skip_institutional"
    SKIP_AUTO_DISABLED = "skip_auto_disabled"


class UnsupportedTriggerError(ValueError):
    """Raised if a trigger-like string cannot be mapped to TriggerEventType."""


class InsufficientBulletsError(ValueError):
    """Raised by obligation populators when the min-bullet floor is violated.

    Generator propagates (does NOT catch) per R3.7 / spec F1.
    """

    def __init__(
        self,
        *,
        obligation: ObligationCode,
        have: int,
        need: int,
    ) -> None:
        self.obligation = obligation
        self.have = have
        self.need = need
        super().__init__(f"{obligation.value}:{have}<{need}")
