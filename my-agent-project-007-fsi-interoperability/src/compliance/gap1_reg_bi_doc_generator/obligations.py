"""
Gap 1 — Four-obligation populators + OPA-style required-sections matrix.

See .kiro/specs/gap1-reg-bi-doc-generator.md R3, R3a, R3b.

Contents
--------

1. Min/max bullet floors + deterministic populators for the four
   Reg BI obligations (preserved from v2).
2. ``RequiredSectionsPredicate`` / ``RequiredSectionsRule`` — the OPA
   rule-shaped schema for the required-sections matrix (R3).
3. ``REQUIRED_SECTIONS_MATRIX`` — base + archetype + account-type +
   product-type overlays. Every row has a ``wsp_section`` annotation.
4. ``OpaRequirementsResolver`` — deterministic evaluator producing
   ``ResolvedRequirements``.

Rules enforced here:
    - Min-bullet floor: ``InsufficientBulletsError`` if violated.
    - Max-bullet cap: silently trim (newest dropped).
    - No ``client.display_name`` in bullets (R3a.5).
    - No LLM (R3a.6).
    - Every bullet post-scrubbed via ``_scrub_pii``.
    - Every matrix rule has ``wsp_section`` filled — build-time assert.
"""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from m3_schema_registry import AccountType
from m5_config_loader import Archetype, RegistrationType

from compliance.gap1_reg_bi_doc_generator._types import (
    InsufficientBulletsError,
    ObligationCode,
    TriggerEventType,
)
from compliance.gap1_reg_bi_doc_generator.disclosures import (
    CANONICAL_DISCLOSURE_NAMES,
)
from compliance.gap1_reg_bi_doc_generator.document import (
    GenerationInput,
    ProductType,
    RegBiSection,
    _scrub_pii,
)

# =============================================================================
# Min / max bullet floors (R3a)
# =============================================================================

_MIN_BULLETS: dict[ObligationCode, int] = {
    ObligationCode.DISCLOSURE: 3,
    ObligationCode.CARE: 4,
    ObligationCode.COI: 1,
    ObligationCode.COMPLIANCE: 2,
}

_MAX_BULLETS: dict[ObligationCode, int] = {
    ObligationCode.DISCLOSURE: 8,
    ObligationCode.CARE: 12,
    ObligationCode.COI: 20,
    ObligationCode.COMPLIANCE: 6,
}


def _finalize(
    *,
    obligation: ObligationCode,
    bullets: Iterable[str],
    populated_by: str,
    force_review: bool,
) -> RegBiSection:
    """Scrub, cap, floor-check, return ``RegBiSection``."""
    scrubbed: list[str] = []
    for b in bullets:
        if not b:
            continue
        cleaned = _scrub_pii(b)
        if len(cleaned) > 500:
            cleaned = cleaned[:500]
        scrubbed.append(cleaned)

    max_b = _MAX_BULLETS[obligation]
    if len(scrubbed) > max_b:
        scrubbed = scrubbed[:max_b]

    min_b = _MIN_BULLETS[obligation]
    if len(scrubbed) < min_b:
        raise InsufficientBulletsError(
            obligation=obligation,
            have=len(scrubbed),
            need=min_b,
        )

    return RegBiSection(
        obligation_code=obligation,
        bullets=tuple(scrubbed),
        narrative="",
        populated_by=populated_by,
        force_review=force_review,
    )


# =============================================================================
# DISCLOSURE populator (R3a.1)
# =============================================================================


def _trigger_scope_phrase(trigger: TriggerEventType) -> str:
    mapping = {
        TriggerEventType.recommendation_draft: (
            "Scope: personalized recommendation draft for the client."
        ),
        TriggerEventType.research_rating_issued: (
            "Scope: research rating issued for the security under review."
        ),
        TriggerEventType.order_drafted_retail: (
            "Scope: retail trade order drafted and pending advisor approval."
        ),
    }
    return mapping[trigger]


def populate_disclosure(inp: GenerationInput) -> RegBiSection:
    """Populate the Disclosure obligation section (§15l-1(a)(2)(i))."""
    bullets: list[str] = []

    reg_type = inp.advisor.registration_type
    firm_kind = (
        "dual-registered broker-dealer / investment adviser"
        if reg_type == RegistrationType.dual_registered.value
        else "broker-dealer"
    )
    bullets.append(
        f"Firm operates as a {firm_kind}; "
        f"material relationship disclosed to the client."
    )
    bullets.append(
        f"Acting role: advisor role '{inp.advisor.role.value}' "
        f"is recording the recommendation."
    )
    if (
        inp.order is not None
        and inp.order.commission is not None
        and inp.order.commission > 0
    ):
        bullets.append(
            f"Commission: ${inp.order.commission:.2f} per order."
        )
    else:
        bullets.append(
            "See firm fee schedule for applicable costs."
        )
    bullets.append(_trigger_scope_phrase(inp.trigger))

    return _finalize(
        obligation=ObligationCode.DISCLOSURE,
        bullets=bullets,
        populated_by="reg_bi/disclosure/populate.v1",
        force_review=False,
    )


# =============================================================================
# CARE populator (R3a.2)
# =============================================================================


def _extract_alternatives(
    reason_trace: tuple[str, ...], cap: int = 3
) -> list[str]:
    """Pull up to ``cap`` entries starting with 'alt:' (case-insensitive)."""
    result: list[str] = []
    for entry in reason_trace:
        if entry.lower().startswith("alt:"):
            result.append(
                f"Alternative considered: {entry[4:].strip()}"
            )
            if len(result) >= cap:
                break
    return result


def populate_care(inp: GenerationInput) -> RegBiSection:
    """Populate the Care obligation section (§15l-1(a)(2)(ii))."""
    bullets: list[str] = []
    force_review = False

    if (
        inp.research_brief is not None
        and inp.research_brief.rating is not None
    ):
        bullets.append(
            f"Security rating: {inp.research_brief.rating}."
        )

    rt = inp.client.risk_tolerance
    if rt is None or rt == "":
        bullets.append(
            "Risk tolerance not on file; suitability assessment "
            "required before finalization."
        )
        force_review = True
    else:
        bullets.append(f"Client risk tolerance on file: {rt}.")

    objs = inp.client.investment_objectives or []
    seen: set[str] = set()
    deduped = [o for o in objs if not (o in seen or seen.add(o))]
    if deduped:
        bullets.append(
            "Client investment objectives: " + ", ".join(deduped) + "."
        )
    else:
        bullets.append(
            "Investment objectives not specified on file; "
            "suitability review required."
        )
        force_review = True

    if inp.client.time_horizon:
        bullets.append(
            f"Client time horizon: {inp.client.time_horizon}."
        )
    else:
        bullets.append("Time horizon not specified on file.")

    if inp.order is not None:
        bullets.append(
            f"Order: {inp.order.side} "
            f"{inp.order.quantity:g} units; "
            f"status={inp.order.status.value}."
        )

    bullets.extend(_extract_alternatives(inp.reason_trace, cap=3))

    return _finalize(
        obligation=ObligationCode.CARE,
        bullets=bullets,
        populated_by="reg_bi/care/populate.v1",
        force_review=force_review,
    )


# =============================================================================
# COI populator (R3a.3)
# =============================================================================


def populate_coi(inp: GenerationInput) -> RegBiSection:
    """Populate the Conflict of Interest section (§15l-1(a)(2)(iii))."""
    bullets: list[str] = []

    for ce in inp.config.conflict_inventory:
        bullets.append(
            f"{ce.type}: {ce.description} Mitigation: {ce.mitigation}"
        )

    if (
        inp.order is not None
        and inp.order.commission is not None
        and inp.order.commission > 0
    ):
        bullets.append(
            f"Commission-based compensation: "
            f"${inp.order.commission:.2f} per order."
        )

    if inp.advisor.registration_type == RegistrationType.dual_registered.value:
        bullets.append(
            "Dual-registered firm: fiduciary duty applies under advisory "
            "relationship; best-interest applies under BD relationship."
        )

    if not bullets:
        bullets.append(
            "No conflicts identified from firm conflict inventory."
        )

    return _finalize(
        obligation=ObligationCode.COI,
        bullets=bullets,
        populated_by="reg_bi/coi/populate.v1",
        force_review=False,
    )


# =============================================================================
# COMPLIANCE populator (R3a.4)
# =============================================================================


def populate_compliance(inp: GenerationInput) -> RegBiSection:
    """Populate the Compliance obligation section (§15l-1(a)(2)(iv))."""
    bullets: list[str] = []

    bullets.append("Policies and procedures: WSP-REGBI-1.x.")
    bullets.append(
        "Record-keeping: retained under 17 CFR §240.17a-4(e)(5) "
        "— 6-year WORM."
    )

    if inp.research_brief is not None:
        score = inp.research_brief.anti_fabrication_score
        # Half-up rounding (T1.13 acceptance criterion: 0.8765 -> 0.877).
        # Python's default .3f uses banker's rounding; force half-up.
        rounded = Decimal(str(score)).quantize(
            Decimal("0.001"), rounding=ROUND_HALF_UP
        )
        bullets.append(f"Anti-fabrication score: {rounded}.")

    if inp.config.require_advisor_review:
        bullets.append("Advisor review required before finalization.")

    return _finalize(
        obligation=ObligationCode.COMPLIANCE,
        bullets=bullets,
        populated_by="reg_bi/compliance/populate.v1",
        force_review=False,
    )


# =============================================================================
# Populator registry
# =============================================================================

POPULATORS = (
    (ObligationCode.DISCLOSURE, populate_disclosure),
    (ObligationCode.CARE, populate_care),
    (ObligationCode.COI, populate_coi),
    (ObligationCode.COMPLIANCE, populate_compliance),
)


# =============================================================================
# OPA-style required-sections matrix (R3)
# =============================================================================

#: ``rule_applied`` path regex. Slashes only; lowercase + digits +
#: underscore in segments. ``replace("/", ".")`` yields the future
#: Rego dotted path.
RULE_APPLIED_RE: re.Pattern[str] = re.compile(
    r"^reg_bi/matrix/[a-z0-9_]+\.v[1-9]\d*$"
)

#: ``wsp_section`` annotation regex. WSP-REGBI-X.Y shape.
WSP_SECTION_RE: re.Pattern[str] = re.compile(
    r"^WSP-REGBI-[0-9]+\.[0-9]+$"
)


class RequiredSectionsPredicate(BaseModel):
    """Frozen predicate — all-None matches wildcard."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    archetype: Optional[Archetype] = None
    account_type: Optional[AccountType] = None
    product_type: Optional[ProductType] = None

    def matches(
        self,
        *,
        archetype: Optional[Archetype],
        account_type: Optional[AccountType],
        product_type: Optional[ProductType],
    ) -> bool:
        """True iff each non-None field equals the corresponding input."""
        if self.archetype is not None and self.archetype != archetype:
            return False
        if self.account_type is not None and self.account_type != account_type:
            return False
        if self.product_type is not None and self.product_type != product_type:
            return False
        return True


class RequiredSectionsRule(BaseModel):
    """Frozen matrix row — one OPA-style rule."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_applied: str = Field(min_length=1, max_length=200)
    wsp_section: str = Field(min_length=1, max_length=80)
    applies_when: RequiredSectionsPredicate
    adds_disclosures: frozenset[str] = Field(default_factory=frozenset)
    severity: Literal["ADD", "BLOCK"] = "ADD"

    @field_validator("rule_applied")
    @classmethod
    def _validate_rule_applied(cls, v: str) -> str:
        if not RULE_APPLIED_RE.match(v):
            raise ValueError(
                f"rule_applied '{v}' does not match "
                f"reg_bi/matrix/{{slug}}.v{{N}} shape"
            )
        return v

    @field_validator("wsp_section")
    @classmethod
    def _validate_wsp_section(cls, v: str) -> str:
        if not WSP_SECTION_RE.match(v):
            raise ValueError(
                f"wsp_section '{v}' does not match WSP-REGBI-X.Y shape"
            )
        return v

    @field_validator("adds_disclosures")
    @classmethod
    def _validate_adds_subset(cls, v: frozenset[str]) -> frozenset[str]:
        unknown = v - set(CANONICAL_DISCLOSURE_NAMES)
        if unknown:
            raise ValueError(
                f"adds_disclosures contains unknown names: "
                f"{sorted(unknown)}"
            )
        return v


# ---------- Base matrix ----------

_BASE_RULE = RequiredSectionsRule(
    rule_applied="reg_bi/matrix/base.v1",
    wsp_section="WSP-REGBI-1.1",
    applies_when=RequiredSectionsPredicate(),
    adds_disclosures=frozenset(
        {
            "conflict_inventory",
            "best_interest_rationale",
            "fees_and_compensation",
            "product_scope",
            "discipline_history_link",
            "limitations",
        }
    ),
)

# ---------- Archetype overlays ----------

_ARCHETYPE_TIER3 = RequiredSectionsRule(
    rule_applied="reg_bi/matrix/tier3_broker_dealer.v1",
    wsp_section="WSP-REGBI-3.1",
    applies_when=RequiredSectionsPredicate(
        archetype=Archetype.tier3_broker_dealer
    ),
    adds_disclosures=frozenset({"monitoring_frequency"}),
)

_ARCHETYPE_TIER4 = RequiredSectionsRule(
    rule_applied="reg_bi/matrix/tier4_independent_ria.v1",
    wsp_section="WSP-REGBI-4.1",
    applies_when=RequiredSectionsPredicate(
        archetype=Archetype.tier4_independent_ria
    ),
    adds_disclosures=frozenset(),  # tier4 ria_only never reaches matrix
)

# ---------- Account-type overlays (pre-Gap-5 contract) ----------

_IRA_ACCOUNT_TYPES: frozenset[AccountType] = frozenset(
    {
        AccountType.TRADITIONAL_IRA,
        AccountType.ROTH_IRA,
        AccountType.SEP_IRA,
        AccountType.SIMPLE_IRA,
    }
)

_EMPLOYER_PLAN_TYPES: frozenset[AccountType] = frozenset(
    {AccountType.K401, AccountType.B403}
)


# We model IRA + 401k/403b as a SET of per-account rows so that each
# matrix row predicates on exactly one account_type (keeps OPA-lift
# shape clean). Iterating set(...) is non-deterministic → list.
_IRA_RULES = tuple(
    RequiredSectionsRule(
        rule_applied="reg_bi/matrix/account_ira.v1",
        wsp_section="WSP-REGBI-5.1",
        applies_when=RequiredSectionsPredicate(account_type=at),
        adds_disclosures=frozenset({"monitoring_frequency"}),
    )
    for at in sorted(_IRA_ACCOUNT_TYPES, key=lambda a: a.value)
)

_PLAN_RULES = tuple(
    RequiredSectionsRule(
        rule_applied="reg_bi/matrix/account_401k.v1",
        wsp_section="WSP-REGBI-5.2",
        applies_when=RequiredSectionsPredicate(account_type=at),
        adds_disclosures=frozenset({"monitoring_frequency"}),
    )
    for at in sorted(_EMPLOYER_PLAN_TYPES, key=lambda a: a.value)
)

# ---------- Product-type overlays ----------

_PRODUCT_MF = RequiredSectionsRule(
    rule_applied="reg_bi/matrix/product_mf.v1",
    wsp_section="WSP-REGBI-6.1",
    applies_when=RequiredSectionsPredicate(product_type=ProductType.mutual_fund),
    adds_disclosures=frozenset(),
)

_PRODUCT_ANNUITY = RequiredSectionsRule(
    rule_applied="reg_bi/matrix/product_annuity.v1",
    wsp_section="WSP-REGBI-6.2",
    applies_when=RequiredSectionsPredicate(product_type=ProductType.annuity),
    adds_disclosures=frozenset({"monitoring_frequency", "limitations"}),
)

_PRODUCT_PRIVATE = RequiredSectionsRule(
    rule_applied="reg_bi/matrix/product_private.v1",
    wsp_section="WSP-REGBI-6.3",
    applies_when=RequiredSectionsPredicate(product_type=ProductType.private),
    adds_disclosures=frozenset({"limitations"}),
)


#: Full matrix — stable declaration order.
REQUIRED_SECTIONS_MATRIX: tuple[RequiredSectionsRule, ...] = (
    _BASE_RULE,
    _ARCHETYPE_TIER3,
    _ARCHETYPE_TIER4,
    *_IRA_RULES,
    *_PLAN_RULES,
    _PRODUCT_MF,
    _PRODUCT_ANNUITY,
    _PRODUCT_PRIVATE,
)


# =============================================================================
# Build-time assertion: every rule has a wsp_section (R3.8)
# =============================================================================

def _assert_matrix_annotations() -> None:
    for rule in REQUIRED_SECTIONS_MATRIX:
        if not rule.wsp_section:
            raise AssertionError(
                f"matrix rule {rule.rule_applied} is missing "
                f"wsp_section annotation"
            )
        if not WSP_SECTION_RE.match(rule.wsp_section):
            raise AssertionError(
                f"matrix rule {rule.rule_applied} has malformed "
                f"wsp_section '{rule.wsp_section}'"
            )
        if not RULE_APPLIED_RE.match(rule.rule_applied):
            raise AssertionError(
                f"matrix rule {rule.rule_applied} has malformed "
                f"rule_applied path"
            )


_assert_matrix_annotations()


# =============================================================================
# ResolvedRequirements + OpaRequirementsResolver (R3.7)
# =============================================================================


class ResolvedRequirements(BaseModel):
    """Deterministic union of matched rules."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    matched_rules: tuple[str, ...]
    matched_wsp_sections: tuple[str, ...]
    required_disclosures: frozenset[str]
    required_obligations: frozenset[ObligationCode]
    is_retail: bool
    severity: Literal["ADD", "BLOCK"] = "ADD"


def _archetype_from_claims(raw: str) -> Optional[Archetype]:
    """Coerce ``AidClaims.archetype`` string to ``Archetype`` enum."""
    try:
        return Archetype(raw)
    except ValueError:
        return None


def _account_type_from_order(inp: GenerationInput) -> Optional[AccountType]:
    """Pull account_type from Order if present."""
    if inp.order is not None and inp.order.account_type is not None:
        return inp.order.account_type
    return None


class OpaRequirementsResolver:
    """Deterministic evaluator for the required-sections matrix.

    Intended to be lifted to Rego in Phase 4 — the matrix row shape is
    1:1 with a Rego rule. Every rule has a ``wsp_section`` annotation
    so Gap 3 can emit WSP→Rego / Rego→WSP mappings.
    """

    def __init__(
        self,
        *,
        matrix: tuple[RequiredSectionsRule, ...] = REQUIRED_SECTIONS_MATRIX,
    ) -> None:
        self._matrix = matrix

    def resolve(self, inp: GenerationInput) -> ResolvedRequirements:
        archetype = _archetype_from_claims(inp.advisor.archetype)
        account_type = _account_type_from_order(inp)
        product_type = inp.product_type

        matched_rules: list[str] = []
        matched_wsp: list[str] = []
        required: set[str] = set()

        for rule in self._matrix:
            if rule.applies_when.matches(
                archetype=archetype,
                account_type=account_type,
                product_type=product_type,
            ):
                matched_rules.append(rule.rule_applied)
                matched_wsp.append(rule.wsp_section)
                required.update(rule.adds_disclosures)

        # Sorted + deduped (R3.7 / T1.38).
        matched_rules_sorted = tuple(sorted(set(matched_rules)))
        matched_wsp_sorted = tuple(sorted(set(matched_wsp)))

        is_retail = inp.client.client_type == "individual"

        return ResolvedRequirements(
            matched_rules=matched_rules_sorted,
            matched_wsp_sections=matched_wsp_sorted,
            required_disclosures=frozenset(required),
            required_obligations=frozenset(ObligationCode),
            is_retail=is_retail,
            severity="ADD",
        )
