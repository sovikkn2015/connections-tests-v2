"""
Gap 7 — 5×5 Jurisdiction Matrix.

Every (primary, data_residency) pair must be explicitly populated.
The lookup helper raises UndefinedJurisdictionPair on anything else;
the egress gate catches that and emits DENY. Fail-closed per
steering rule 8.

See .kiro/specs/gap7-cross-border.md R1, §2.1.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from m5_config_loader import Jurisdiction

from compliance.gap7_cross_border._types import (
    GDPRLawfulBasis,
    UndefinedJurisdictionPair,
)

MatrixBaseline = Literal["ALLOW", "REQUIRE_SCC", "DENY"]


class MatrixCell(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    baseline: MatrixBaseline
    required_lawful_bases: tuple[GDPRLawfulBasis, ...]
    wsp_section: str


_JX = Jurisdiction
_LB = GDPRLawfulBasis

# Short-hands to keep the table readable.
_ALLOW_US = MatrixCell(
    baseline="ALLOW",
    required_lawful_bases=(),
    wsp_section="Reg BI §15l-1",
)
_ALLOW_EU = MatrixCell(
    baseline="ALLOW",
    required_lawful_bases=(
        _LB.consent,
        _LB.contract,
        _LB.legal_obligation,
        _LB.legitimate_interests,
    ),
    wsp_section="GDPR Art. 6(1)(a)",
)
_ALLOW_UK = MatrixCell(
    baseline="ALLOW",
    required_lawful_bases=(
        _LB.consent,
        _LB.contract,
        _LB.legitimate_interests,
    ),
    wsp_section="FCA Consumer Duty PRIN 2A",
)
_ALLOW_SG = MatrixCell(
    baseline="ALLOW",
    required_lawful_bases=(_LB.consent, _LB.contract),
    wsp_section="MAS Notice 626 §9",
)
_ALLOW_HK = MatrixCell(
    baseline="ALLOW",
    required_lawful_bases=(_LB.consent, _LB.contract),
    wsp_section="SFC Code of Conduct §5.1A",
)

_SCC_EU = MatrixCell(
    baseline="REQUIRE_SCC",
    required_lawful_bases=(_LB.contract, _LB.legitimate_interests),
    wsp_section="GDPR Art. 46",
)
_SCC_US = MatrixCell(
    baseline="REQUIRE_SCC",
    required_lawful_bases=(_LB.contract,),
    wsp_section="17 CFR §240.17a-4(e)(5)",
)
_SCC_UK = MatrixCell(
    baseline="REQUIRE_SCC",
    required_lawful_bases=(_LB.contract, _LB.legitimate_interests),
    wsp_section="FCA Consumer Duty PRIN 2A",
)
_SCC_SG = MatrixCell(
    baseline="REQUIRE_SCC",
    required_lawful_bases=(_LB.contract,),
    wsp_section="MAS Notice 626 §9",
)
_SCC_HK = MatrixCell(
    baseline="REQUIRE_SCC",
    required_lawful_bases=(_LB.contract,),
    wsp_section="SFC Code of Conduct §5.1A",
)

_DENY_EU_OUT = MatrixCell(
    baseline="DENY",
    required_lawful_bases=(),
    wsp_section="GDPR Art. 46",
)
_DENY_HK_EU = MatrixCell(
    baseline="DENY",
    required_lawful_bases=(),
    wsp_section="SFC Part XIVA",
)


JURISDICTION_MATRIX: dict[tuple[Jurisdiction, Jurisdiction], MatrixCell] = {
    # US primary
    (_JX.us, _JX.us): _ALLOW_US,
    (_JX.us, _JX.eu): _SCC_EU,
    (_JX.us, _JX.uk): _SCC_UK,
    (_JX.us, _JX.sg): _SCC_SG,
    (_JX.us, _JX.hk): _SCC_HK,
    # EU primary
    (_JX.eu, _JX.us): _SCC_US,
    (_JX.eu, _JX.eu): _ALLOW_EU,
    (_JX.eu, _JX.uk): _SCC_UK,
    (_JX.eu, _JX.sg): _DENY_EU_OUT,  # no EU adequacy for SG
    (_JX.eu, _JX.hk): _DENY_EU_OUT,  # no EU adequacy for HK
    # UK primary
    (_JX.uk, _JX.us): _SCC_US,
    (_JX.uk, _JX.eu): _SCC_EU,
    (_JX.uk, _JX.uk): _ALLOW_UK,
    (_JX.uk, _JX.sg): _SCC_SG,
    (_JX.uk, _JX.hk): _SCC_HK,
    # SG primary
    (_JX.sg, _JX.us): _SCC_US,
    (_JX.sg, _JX.eu): _SCC_EU,
    (_JX.sg, _JX.uk): _SCC_UK,
    (_JX.sg, _JX.sg): _ALLOW_SG,
    (_JX.sg, _JX.hk): _SCC_HK,
    # HK primary
    (_JX.hk, _JX.us): _SCC_US,
    (_JX.hk, _JX.eu): _DENY_HK_EU,  # no SFC-recognized EU adequacy
    (_JX.hk, _JX.uk): _SCC_UK,
    (_JX.hk, _JX.sg): _SCC_SG,
    (_JX.hk, _JX.hk): _ALLOW_HK,
}


# Import-time completeness check — 5×5 = 25 cells, no exceptions.
assert len(JURISDICTION_MATRIX) == 25, (
    f"JURISDICTION_MATRIX must have 25 cells, got {len(JURISDICTION_MATRIX)}"
)
# And every Jurisdiction enum value must appear as both axis.
_ALL_JX = set(Jurisdiction)
_PRIMARIES = {k[0] for k in JURISDICTION_MATRIX}
_RESIDENCIES = {k[1] for k in JURISDICTION_MATRIX}
assert _PRIMARIES == _ALL_JX, "primary axis missing a Jurisdiction value"
assert _RESIDENCIES == _ALL_JX, "residency axis missing a Jurisdiction value"


def matrix_lookup(
    primary: Jurisdiction, residency: Jurisdiction
) -> MatrixCell:
    """Return the MatrixCell for the pair, raising fail-closed on misses.

    `UndefinedJurisdictionPair` is a defensive raise — if every
    Jurisdiction enum value appears in the matrix (asserted above),
    this path is only reachable under enum drift.
    """
    try:
        return JURISDICTION_MATRIX[(primary, residency)]
    except KeyError:
        raise UndefinedJurisdictionPair(
            f"no matrix cell for primary={primary.value}, "
            f"residency={residency.value}"
        ) from None
