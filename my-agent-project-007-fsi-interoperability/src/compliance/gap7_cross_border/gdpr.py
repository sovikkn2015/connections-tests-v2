"""
Gap 7 — GDPR lawful-basis evaluator.

Implements the 11-row truth table from .kiro/specs/gap7-cross-border.md
§R2.2. Pure, deterministic, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from compliance.gap7_cross_border._types import GDPRLawfulBasis

GdprOutcome = Literal["ALLOW", "REQUIRE_CONSENT", "REQUIRE_SCC"]


@dataclass(frozen=True)
class GdprEvaluation:
    outcome: GdprOutcome
    basis: GDPRLawfulBasis
    wsp_section: str
    rule_id: str


# Mapping basis → wsp_section (Art. 6(1)(a)..(f)).
_BASIS_WSP: dict[GDPRLawfulBasis, str] = {
    GDPRLawfulBasis.consent: "GDPR Art. 6(1)(a)",
    GDPRLawfulBasis.contract: "GDPR Art. 6(1)(b)",
    GDPRLawfulBasis.legal_obligation: "GDPR Art. 6(1)(c)",
    GDPRLawfulBasis.vital_interests: "GDPR Art. 6(1)(d)",
    GDPRLawfulBasis.public_task: "GDPR Art. 6(1)(e)",
    GDPRLawfulBasis.legitimate_interests: "GDPR Art. 6(1)(f)",
}


def evaluate(
    *,
    basis: GDPRLawfulBasis,
    involves_eu_data_subject: bool,
    consent_on_file: bool,
    scc_on_file: bool,
) -> GdprEvaluation:
    """R2.2 — 11-row truth table.

    Returns the strongest constraint (ALLOW | REQUIRE_CONSENT |
    REQUIRE_SCC). Never returns DENY directly — DENY is a
    jurisdiction-matrix concern, not a lawful-basis concern.
    """
    wsp = _BASIS_WSP[basis]

    # Rows 1-2: consent basis
    if basis == GDPRLawfulBasis.consent:
        if consent_on_file:
            return GdprEvaluation("ALLOW", basis, wsp, "gap7.gdpr.consent_ok")
        return GdprEvaluation(
            "REQUIRE_CONSENT", basis, wsp, "gap7.gdpr.consent_missing"
        )

    # Rows 3-5: contract basis
    if basis == GDPRLawfulBasis.contract:
        if involves_eu_data_subject and not scc_on_file:
            return GdprEvaluation(
                "REQUIRE_SCC", basis, wsp, "gap7.gdpr.contract_requires_scc"
            )
        return GdprEvaluation("ALLOW", basis, wsp, "gap7.gdpr.contract_ok")

    # Rows 6, 7, 8: legal_obligation / vital_interests / public_task
    if basis in (
        GDPRLawfulBasis.legal_obligation,
        GDPRLawfulBasis.vital_interests,
        GDPRLawfulBasis.public_task,
    ):
        return GdprEvaluation(
            "ALLOW", basis, wsp, f"gap7.gdpr.{basis.value}_ok"
        )

    # Rows 9-11: legitimate_interests
    if basis == GDPRLawfulBasis.legitimate_interests:
        if involves_eu_data_subject and not scc_on_file:
            return GdprEvaluation(
                "REQUIRE_SCC",
                basis,
                wsp,
                "gap7.gdpr.legitimate_interests_requires_scc",
            )
        return GdprEvaluation(
            "ALLOW", basis, wsp, "gap7.gdpr.legitimate_interests_ok"
        )

    # Unreachable under Enum typing, but fail-closed for safety.
    raise ValueError(f"unhandled GDPR basis: {basis!r}")  # pragma: no cover
