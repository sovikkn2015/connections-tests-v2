"""
Gap 1 — Seven canonical disclosure types.

See .kiro/specs/gap1-reg-bi-doc-generator.md §0.4 + R3b.

Each of the seven types is a frozen Pydantic v2 model
(``frozen=True, extra="forbid"``). ``CanonicalDisclosures`` is the
single nested container surfaced on ``RegBiDocument``.

These are DETERMINISTIC typed records — no LLM, no narrative. The
prose ``summary`` field on ``BestInterestRationale`` is reserved as a
narrative slot; populators leave it empty in Phase 3 and the hosting
narrative layer may fill it post-stitch. Gap 1's deterministic
populator in ``populate_disclosures`` always emits ``summary=""``.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from m5_config_loader import ConflictEntry

from compliance.gap1_reg_bi_doc_generator.document import (
    GenerationInput,
    _scrub_pii,
)

# =============================================================================
# Disclosure name vocabulary — the 7 canonical names used across R3
# =============================================================================

#: The seven canonical disclosure-type names. Order is contractually
#: stable so the OPA resolver and the renderer can iterate
#: deterministically.
CANONICAL_DISCLOSURE_NAMES: tuple[str, ...] = (
    "conflict_inventory",
    "best_interest_rationale",
    "fees_and_compensation",
    "product_scope",
    "monitoring_frequency",
    "discipline_history_link",
    "limitations",
)


# =============================================================================
# 1 — ConflictInventoryDisclosure
# =============================================================================


class ConflictInventoryDisclosure(BaseModel):
    """Typed list of firm conflict inventory entries (§15l-1(a)(2)(iii))."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: tuple[ConflictEntry, ...] = Field(default_factory=tuple)


# =============================================================================
# 2 — BestInterestRationale
# =============================================================================


class BestInterestRationale(BaseModel):
    """Typed best-interest rationale record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    objectives_alignment: str = Field(max_length=500)
    risk_alignment: str = Field(max_length=500)
    time_horizon_alignment: str = Field(max_length=500)
    #: Prose slot reserved for post-stitch LLM narrative; deterministic
    #: populator leaves empty.
    summary: str = Field(default="", max_length=2000)


# =============================================================================
# 3 — FeesAndCompensation
# =============================================================================


class FeeItem(BaseModel):
    """One line item in the fees/compensation disclosure."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str = Field(min_length=1, max_length=120)
    fee_type: str = Field(min_length=1, max_length=80)
    amount: Optional[float] = None
    basis: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=500)


class FeesAndCompensation(BaseModel):
    """Typed list of fee / compensation line items."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: tuple[FeeItem, ...] = Field(default_factory=tuple)


# =============================================================================
# 4 — ProductScope
# =============================================================================


class ProductScope(BaseModel):
    """Firm product-universe scope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scope: Literal[
        "proprietary", "affiliated", "third_party", "captive", "mixed"
    ]


# =============================================================================
# 5 — MonitoringFrequency
# =============================================================================


class MonitoringFrequency(BaseModel):
    """Scheduled review cadence for the recommendation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cadence: Literal[
        "none", "quarterly", "semi_annual", "annual", "event_driven"
    ]


# =============================================================================
# 6 — DisciplineHistoryLink
# =============================================================================

_URL_RE = re.compile(r"^https://[A-Za-z0-9._/\-]+$")


class DisciplineHistoryLink(BaseModel):
    """Stable URL to the firm's Form CRS / IAPD / BrokerCheck page."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str = Field(default="", max_length=500)

    @field_validator("url")
    @classmethod
    def _validate_url_shape(cls, v: str) -> str:
        if v == "":
            return v
        if not _URL_RE.match(v):
            raise ValueError(
                "discipline_history_link.url must be empty or match "
                "https://{host}{path} with a conservative char set"
            )
        return v


# =============================================================================
# 7 — Limitations
# =============================================================================


class Limitations(BaseModel):
    """Free-list of declared recommendation limitations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: tuple[str, ...] = Field(default_factory=tuple, max_length=20)

    @field_validator("entries")
    @classmethod
    def _cap_entry_length(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        for entry in v:
            if not isinstance(entry, str):
                raise ValueError("limitations entries must be strings")
            if len(entry) > 200:
                raise ValueError(
                    "limitations entry exceeds 200-char cap"
                )
        return v


# =============================================================================
# Container
# =============================================================================


class CanonicalDisclosures(BaseModel):
    """The 7-type canonical disclosure record surfaced on RegBiDocument."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    conflict_inventory: ConflictInventoryDisclosure
    best_interest_rationale: BestInterestRationale
    fees_and_compensation: FeesAndCompensation
    product_scope: ProductScope
    monitoring_frequency: MonitoringFrequency
    discipline_history_link: DisciplineHistoryLink
    limitations: Limitations


# =============================================================================
# Deterministic populator
# =============================================================================


def _discipline_history_url(firm_id: str) -> str:
    """Build a deterministic URL from AidClaims.firm_id.

    Defensive: if firm_id contains unusual characters, fall back to
    empty. The URL validator would reject malformed inputs.
    """
    # Conservative allowed-character scrub — keep alnum / dash / underscore.
    safe = re.sub(r"[^A-Za-z0-9_\-]", "", firm_id or "")
    if not safe:
        return ""
    return f"https://adviserinfo.sec.gov/firm/summary/{safe}"


def _base_limitations() -> list[str]:
    return [
        "Recommendation scope limited to in-scope products and "
        "firm-licensed jurisdictions.",
    ]


def _product_limitations_overlay(product_type: Optional[str]) -> list[str]:
    """Deterministic product-type limitation overlays."""
    if product_type is None:
        return []
    if product_type == "annuity":
        return [
            "Surrender charges may apply; see contract for schedule.",
        ]
    if product_type == "private":
        return [
            "Private placement — limited liquidity; accredited investor "
            "status required.",
        ]
    return []


def _default_monitoring_cadence(product_type: Optional[str]) -> str:
    """Annuity / private default to event_driven; others annual."""
    if product_type in ("annuity", "private"):
        return "event_driven"
    return "annual"


def _best_interest_rationale(inp: GenerationInput) -> BestInterestRationale:
    """Deterministic rationale derived from Client profile only.

    No client.display_name / email / DOB / SSN / tax_id read (R5.3).
    """
    rt = inp.client.risk_tolerance or "unspecified"
    objs = inp.client.investment_objectives or []
    obj_text = ", ".join(objs) if objs else "unspecified"
    th = inp.client.time_horizon or "unspecified"

    return BestInterestRationale(
        objectives_alignment=_scrub_pii(
            f"Client stated objectives: {obj_text}."
        )[:500],
        risk_alignment=_scrub_pii(
            f"Client risk tolerance on file: {rt}."
        )[:500],
        time_horizon_alignment=_scrub_pii(
            f"Client time horizon on file: {th}."
        )[:500],
        summary="",
    )


def _fee_items_from_order(inp: GenerationInput) -> tuple[FeeItem, ...]:
    """Deterministic fee items — commission-based, derived from Order."""
    items: list[FeeItem] = []
    order = inp.order
    if (
        order is not None
        and order.commission is not None
        and order.commission > 0
    ):
        items.append(
            FeeItem(
                source="order",
                fee_type="commission",
                amount=float(order.commission),
                basis="per_order",
                description=_scrub_pii(
                    f"Commission of ${order.commission:.2f} applied to "
                    f"this order."
                )[:500],
            )
        )
    return tuple(items)


def populate_disclosures(
    inp: GenerationInput,
    resolved,  # type: ignore[valid-type]  # forward-avoid import cycle
) -> CanonicalDisclosures:
    """Populate the 7 canonical disclosures deterministically (R3b.1).

    ``resolved`` is a ``ResolvedRequirements`` from
    ``obligations.OpaRequirementsResolver``. We accept it duck-typed
    to avoid an import cycle (``obligations.py`` imports this module).
    """
    conflict_inventory = ConflictInventoryDisclosure(
        entries=tuple(inp.config.conflict_inventory)
    )

    best_interest = _best_interest_rationale(inp)

    fees = FeesAndCompensation(items=_fee_items_from_order(inp))

    # ProductScope default = "mixed" in Phase 3 (hook for enterprise
    # config in Phase 4).
    product_scope = ProductScope(scope="mixed")

    product_type_val: Optional[str] = None
    if inp.product_type is not None:
        product_type_val = inp.product_type.value

    monitoring = MonitoringFrequency(
        cadence=_default_monitoring_cadence(product_type_val)  # type: ignore[arg-type]
    )

    discipline = DisciplineHistoryLink(
        url=_discipline_history_url(inp.advisor.firm_id)
    )

    limitations_list = _base_limitations() + _product_limitations_overlay(
        product_type_val
    )
    limitations = Limitations(entries=tuple(limitations_list))

    return CanonicalDisclosures(
        conflict_inventory=conflict_inventory,
        best_interest_rationale=best_interest,
        fees_and_compensation=fees,
        product_scope=product_scope,
        monitoring_frequency=monitoring,
        discipline_history_link=discipline,
        limitations=limitations,
    )
