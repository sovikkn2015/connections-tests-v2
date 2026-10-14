"""
Gap 5 — Pure gate evaluators.

No I/O, no clock, no LLM. Two gates:
  1. Fiduciary gate      — R3
  2. DOL PTE 2020-02     — R4

Both are tiny, named, unit-tested independently of composition.

See .kiro/specs/gap5-erisa-account-type.md §R3, §R4.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from m5_config_loader import SuitabilityStandard

from compliance.gap5_erisa_account_type._types import AccountType
from compliance.gap5_erisa_account_type.taxonomy import (
    RETIREMENT_SET,
    is_retirement,
)

# =============================================================================
# Rule IDs (R2.3) — stable, machine-readable, mirror the Rego rule paths
# =============================================================================

RULE_ID_FIDUCIARY_GATE = (
    "authority.account_type.fiduciary_gate.reg_bi_blocked_on_retirement"
)
RULE_ID_PTE_2020_02 = (
    "authority.account_type.pte_2020_02.rollover_requires_enhanced_doc"
)

# Corresponding wsp_sections
WSP_FIDUCIARY_GATE = "ERISA Policy §404(a)(1)(B)"
WSP_PTE_2020_02 = "ERISA Policy §PTE 2020-02(b)"


@dataclass(frozen=True)
class GateFinding:
    """A single gate's output — triggered or not, with attribution."""

    triggered: bool
    rule_id: str
    wsp_section: str
    rationale: str


def fiduciary_gate(
    *,
    account_type: AccountType,
    suitability_standard: SuitabilityStandard,
    proposed_doc_path: Literal["reg_bi", "fiduciary"],
) -> GateFinding:
    """Rule 1 — block Reg BI doc path on fiduciary-standard retirement accts.

    Truth table — R3.2:

      retirement? | suit.standard | doc_path  | triggered?
      ------------|---------------|-----------|------------
      False       | *             | *         | False
      True        | reg_bi        | *         | False
      True        | fiduciary     | reg_bi    | TRUE
      True        | fiduciary     | fiduciary | False
    """
    triggered = (
        is_retirement(account_type)
        and suitability_standard == SuitabilityStandard.fiduciary
        and proposed_doc_path == "reg_bi"
    )
    rationale = (
        f"fiduciary standard requires fiduciary doc for {account_type.value}"
        if triggered
        else "pass"
    )
    return GateFinding(
        triggered=triggered,
        rule_id=RULE_ID_FIDUCIARY_GATE,
        wsp_section=WSP_FIDUCIARY_GATE,
        rationale=rationale,
    )


def pte_2020_02_gate(
    *,
    account_type: AccountType,
    is_rollover: bool,
) -> GateFinding:
    """Rule 2 — rollover into retirement account → enhanced documentation.

    Truth table — R4.2:

      is_rollover | retirement? | triggered?
      ------------|-------------|------------
      False       | *           | False
      True        | False       | False
      True        | True        | TRUE
    """
    triggered = is_rollover and is_retirement(account_type)
    rationale = (
        f"PTE 2020-02 rollover into {account_type.value} requires enhanced doc"
        if triggered
        else "pass"
    )
    return GateFinding(
        triggered=triggered,
        rule_id=RULE_ID_PTE_2020_02,
        wsp_section=WSP_PTE_2020_02,
        rationale=rationale,
    )


# Gate membership assertion — defence in depth for RETIREMENT_SET drift.
assert AccountType.taxable_brokerage not in RETIREMENT_SET, (
    "taxable_brokerage must not be in RETIREMENT_SET"
)
