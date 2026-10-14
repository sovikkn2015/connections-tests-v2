"""
Gap 7 — MiFID II classification + product-governance gate.

See .kiro/specs/gap7-cross-border.md §R3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from compliance.gap7_cross_border._types import MiFIDClientClassification

MiFIDOutcome = Literal["ALLOW", "DENY"]

# Products MiFID II classes as "complex" in its primary product-governance
# taxonomy. Gap 7 ships a conservative starter list; expansion is a
# data change, not a logic change.
COMPLEX_PRODUCTS: frozenset[str] = frozenset(
    {
        "derivatives",
        "structured_notes",
        "leveraged_etf",
        "crypto",
        "leveraged_fx",
        "contingent_convertibles",
    }
)


@dataclass(frozen=True)
class MifidEvaluation:
    outcome: MiFIDOutcome
    rule_id: str
    wsp_section: str
    rationale: str


def evaluate(
    *,
    classification: MiFIDClientClassification,
    product_type: str,
    knowledge_experience_assessed: bool,
) -> MifidEvaluation:
    """R3.2 truth table.

    - retail + complex product + suitability not assessed → DENY
    - retail + knowledge_experience_assessed=False → DENY
    - professional / eligible_counterparty → ALLOW
    """
    if classification == MiFIDClientClassification.retail:
        if product_type in COMPLEX_PRODUCTS and not knowledge_experience_assessed:
            return MifidEvaluation(
                outcome="DENY",
                rule_id="gap7.mifid2.retail_complex_no_suitability",
                wsp_section="MiFID II Art. 25(2)",
                rationale=(
                    f"retail investor on complex product {product_type} "
                    f"without suitability assessment"
                ),
            )
        if not knowledge_experience_assessed:
            return MifidEvaluation(
                outcome="DENY",
                rule_id="gap7.mifid2.retail_no_knowledge_assessment",
                wsp_section="MiFID II Art. 25(3)",
                rationale=(
                    "retail investor without knowledge/experience assessment"
                ),
            )
        return MifidEvaluation(
            outcome="ALLOW",
            rule_id="gap7.mifid2.retail_ok",
            wsp_section="MiFID II Art. 25(2)",
            rationale="retail with suitability assessment on file",
        )

    # professional / eligible_counterparty
    return MifidEvaluation(
        outcome="ALLOW",
        rule_id="gap7.mifid2.professional_ok",
        wsp_section="MiFID II Art. 25(2)",
        rationale=f"{classification.value} — suitability waived",
    )
