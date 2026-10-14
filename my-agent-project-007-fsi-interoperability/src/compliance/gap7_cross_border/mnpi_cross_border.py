"""
Gap 7 — Cross-border MNPI filter.

Runs BEFORE any vendor call crosses a jurisdiction boundary. This is
distinct from M4 (which strips MNPI before LLM); Gap 7 strips MNPI
before cross-border egress.

See .kiro/specs/gap7-cross-border.md §R5 and steering rule 7.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from m5_config_loader import Jurisdiction

CrossBorderOutcome = Literal["ALLOW", "DENY"]

# R5.1 — PII fields that MUST NOT leave the EU without SCC / adequacy.
EU_PII_FIELDS: frozenset[str] = frozenset(
    {
        "national_id",
        "tax_id_eu",
        "client_eu_address",
    }
)

# R5.1 — HK SFC MNPI fields that MUST NOT leave Hong Kong.
HK_SFC_MNPI_FIELDS: frozenset[str] = frozenset(
    {
        "sfc_order_id",
        "hk_block_trade_size",
    }
)


@dataclass(frozen=True)
class CrossBorderScanResult:
    outcome: CrossBorderOutcome
    rule_id: str
    wsp_section: str
    matched_fields: tuple[str, ...]
    rationale: str


def scan_cross_border_mnpi(
    *,
    payload_fields: tuple[str, ...],
    src_jx: Jurisdiction,
    dst_jx: Jurisdiction,
) -> CrossBorderScanResult:
    """Return DENY if any restricted field would leave its jurisdiction.

    Only `payload_fields` (the *names* of fields present in the
    outbound payload) are inspected. The values never enter this
    function — Gap 7 is a metadata-level gate.
    """
    # Same-jurisdiction is always safe at this layer.
    if src_jx == dst_jx:
        return CrossBorderScanResult(
            outcome="ALLOW",
            rule_id="gap7.mnpi.same_jurisdiction",
            wsp_section="GDPR Art. 46",
            matched_fields=(),
            rationale="intra-jurisdiction egress",
        )

    if src_jx == Jurisdiction.eu and dst_jx != Jurisdiction.eu:
        matches = tuple(
            f for f in payload_fields if f in EU_PII_FIELDS
        )
        if matches:
            return CrossBorderScanResult(
                outcome="DENY",
                rule_id="gap7.mnpi.eu_pii_egress",
                wsp_section="GDPR Art. 46",
                matched_fields=matches,
                rationale=(
                    f"EU PII fields in cross-border egress: "
                    f"{','.join(matches)}"
                ),
            )

    if src_jx == Jurisdiction.hk and dst_jx != Jurisdiction.hk:
        matches = tuple(
            f for f in payload_fields if f in HK_SFC_MNPI_FIELDS
        )
        if matches:
            return CrossBorderScanResult(
                outcome="DENY",
                rule_id="gap7.mnpi.hk_sfc_egress",
                wsp_section="SFC Part XIVA",
                matched_fields=matches,
                rationale=(
                    f"HK SFC MNPI fields in cross-border egress: "
                    f"{','.join(matches)}"
                ),
            )

    return CrossBorderScanResult(
        outcome="ALLOW",
        rule_id="gap7.mnpi.ok",
        wsp_section="GDPR Art. 46",
        matched_fields=(),
        rationale="no restricted fields present",
    )
