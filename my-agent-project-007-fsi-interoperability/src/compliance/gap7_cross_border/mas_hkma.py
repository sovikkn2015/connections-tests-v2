"""
Gap 7 — MAS Notice 626 (Singapore) + HKMA / SFC (Hong Kong) marketing rules.

See .kiro/specs/gap7-cross-border.md §R4.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from compliance.gap7_cross_border._types import MiFIDClientClassification

MarketingOutcome = Literal["ALLOW", "DENY"]

# Product types MAS Notice 626 §9 explicitly restricts in retail marketing.
MAS_RESTRICTED_RETAIL_PRODUCTS: frozenset[str] = frozenset(
    {
        "crypto",
        "leveraged_fx",
    }
)


@dataclass(frozen=True)
class MarketingEvaluation:
    outcome: MarketingOutcome
    rule_id: str
    wsp_section: str
    rationale: str


def evaluate_mas_notice_626(
    *,
    classification: MiFIDClientClassification,
    marketing_channel: str,
    product_type: str,
) -> MarketingEvaluation:
    """R4.1 — MAS Notice 626 §9.

    Outbound marketing to a retail investor of restricted products
    (crypto, leveraged FX) → DENY.
    """
    if marketing_channel == "none":
        return MarketingEvaluation(
            outcome="ALLOW",
            rule_id="gap7.mas.no_marketing_channel",
            wsp_section="MAS Notice 626 §9",
            rationale="no marketing channel",
        )
    if (
        classification == MiFIDClientClassification.retail
        and product_type in MAS_RESTRICTED_RETAIL_PRODUCTS
    ):
        return MarketingEvaluation(
            outcome="DENY",
            rule_id="gap7.mas.retail_restricted_product",
            wsp_section="MAS Notice 626 §9",
            rationale=(
                f"MAS 626 retail marketing of restricted product "
                f"{product_type}"
            ),
        )
    return MarketingEvaluation(
        outcome="ALLOW",
        rule_id="gap7.mas.ok",
        wsp_section="MAS Notice 626 §9",
        rationale="marketing permitted",
    )


def evaluate_hkma_sfc(
    *,
    classification: MiFIDClientClassification,
    product_type: str,
    kyc_on_file: bool,
) -> MarketingEvaluation:
    """R4.2 — HKMA / SFC Code of Conduct §5.1A.

    Marketing of a complex product to a non-professional without
    KYC-on-file → DENY.
    """
    from compliance.gap7_cross_border.mifid2 import COMPLEX_PRODUCTS

    if (
        classification != MiFIDClientClassification.professional
        and product_type in COMPLEX_PRODUCTS
        and not kyc_on_file
    ):
        return MarketingEvaluation(
            outcome="DENY",
            rule_id="gap7.hkma.complex_no_kyc",
            wsp_section="SFC Code of Conduct §5.1A",
            rationale=(
                f"SFC §5.1A complex product {product_type} to "
                f"non-professional without KYC"
            ),
        )
    return MarketingEvaluation(
        outcome="ALLOW",
        rule_id="gap7.hkma.ok",
        wsp_section="SFC Code of Conduct §5.1A",
        rationale="SFC marketing permitted",
    )
