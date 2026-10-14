"""
Gap 7 — Egress Gate.

The public composer. Every outbound M6 vendor call passes through
`EgressGate.evaluate(req)`. All decisions are audited to M10 via the
injected AuditClient Protocol.

Fail-closed on:
  - undefined matrix pair (UndefinedJurisdictionPair caught → DENY);
  - missing lawful_basis when EU subject present;
  - audit sink raise (AuditWriteFailed).

See .kiro/specs/gap7-cross-border.md R6, R7.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from m5_config_loader import Jurisdiction

from compliance.gap7_cross_border import gdpr, mifid2, mas_hkma
from compliance.gap7_cross_border._types import (
    EGRESS_DECISION_SCHEMA_VERSION,
    AuditWriteFailed,
    GDPRLawfulBasis,
    MiFIDClientClassification,
    UndefinedJurisdictionPair,
)
from compliance.gap7_cross_border.audit_client import AuditClient
from compliance.gap7_cross_border.matrix import matrix_lookup
from compliance.gap7_cross_border.mnpi_cross_border import (
    scan_cross_border_mnpi,
)

# Same safe charset as Gap 5 (R6.4) + comma/colon/equals for field-name
# lists and key=value rationale fragments.
_RATIONALE_RE: re.Pattern[str] = re.compile(
    r"^[A-Za-z0-9 _\-\.\(\)/§,:=]+$"
)

OutcomeLiteral = Literal["ALLOW", "DENY"]
LayeredOutcomeLiteral = Literal[
    "ALLOW", "REQUIRE_CONSENT", "REQUIRE_SCC", "DENY"
]


# =============================================================================
# Request
# =============================================================================


class EgressRequest(BaseModel):
    """R6.1 — the request the egress gate evaluates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trace_id: str = Field(
        min_length=8, max_length=64, pattern=r"^[A-Za-z0-9\-]+$"
    )
    primary_jurisdiction: Jurisdiction
    data_residency: Jurisdiction
    target_vendor_jurisdiction: Jurisdiction
    lawful_basis: GDPRLawfulBasis | None = None
    involves_eu_data_subject: bool = False
    consent_on_file: bool = False
    scc_on_file: bool = False
    payload_fields: tuple[str, ...] = ()
    client_classification: MiFIDClientClassification | None = None
    marketing_channel: Literal[
        "none", "retail_mass", "direct_solicitation"
    ] = "none"
    product_type: str = Field(
        default="generic",
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_\-]+$",
    )
    knowledge_experience_assessed: bool = True
    kyc_on_file: bool = True
    requested_by: str = Field(
        min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$"
    )


# =============================================================================
# Decision
# =============================================================================


class EgressDecision(BaseModel):
    """R6.1 — the record emitted to M10."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: OutcomeLiteral
    layered_outcome: LayeredOutcomeLiteral
    rule_ids: tuple[str, ...]
    wsp_sections: tuple[str, ...]
    rationale: str = Field(max_length=240)
    trace_id: str

    @field_validator("rationale")
    @classmethod
    def _rationale_charset(cls, v: str) -> str:
        if not _RATIONALE_RE.match(v):
            raise ValueError(
                "rationale must match the safe charset "
                "[A-Za-z0-9 _\\-\\.\\(\\)/§,:=]"
            )
        return v


# =============================================================================
# Gate
# =============================================================================


class EgressGate:
    def __init__(self, audit_client: AuditClient) -> None:
        self._audit = audit_client

    def evaluate(self, req: EgressRequest) -> EgressDecision:
        rule_ids: list[str] = []
        wsp_sections: list[str] = []

        # 1. Matrix lookup. Undefined pair → fail-closed DENY.
        try:
            cell = matrix_lookup(req.primary_jurisdiction, req.data_residency)
        except UndefinedJurisdictionPair:
            decision = EgressDecision(
                outcome="DENY",
                layered_outcome="DENY",
                rule_ids=("gap7.matrix.undefined_pair",),
                wsp_sections=("GDPR Art. 46",),
                rationale="undefined jurisdiction pair fail-closed",
                trace_id=req.trace_id,
            )
            self._emit_audit(decision, req)
            return decision

        # 2. Baseline. If matrix itself denies → DENY.
        if cell.baseline == "DENY":
            decision = EgressDecision(
                outcome="DENY",
                layered_outcome="DENY",
                rule_ids=("gap7.matrix.baseline_deny",),
                wsp_sections=(cell.wsp_section,),
                rationale=(
                    f"matrix DENY for "
                    f"{req.primary_jurisdiction.value}/"
                    f"{req.data_residency.value}"
                ),
                trace_id=req.trace_id,
            )
            self._emit_audit(decision, req)
            return decision

        layered: LayeredOutcomeLiteral
        if cell.baseline == "REQUIRE_SCC":
            layered = "REQUIRE_SCC"
        else:  # ALLOW
            layered = "ALLOW"
        rule_ids.append("gap7.matrix.baseline_ok")
        wsp_sections.append(cell.wsp_section)

        # 3. GDPR lawful-basis gate.
        if req.involves_eu_data_subject and req.lawful_basis is None:
            decision = EgressDecision(
                outcome="DENY",
                layered_outcome="DENY",
                rule_ids=tuple(rule_ids + ["gap7.gdpr.basis_missing"]),
                wsp_sections=tuple(wsp_sections + ["GDPR Art. 6(1)(a)"]),
                rationale="EU subject present with no lawful_basis",
                trace_id=req.trace_id,
            )
            self._emit_audit(decision, req)
            return decision

        if req.lawful_basis is not None:
            g = gdpr.evaluate(
                basis=req.lawful_basis,
                involves_eu_data_subject=req.involves_eu_data_subject,
                consent_on_file=req.consent_on_file,
                scc_on_file=req.scc_on_file,
            )
            rule_ids.append(g.rule_id)
            wsp_sections.append(g.wsp_section)
            # Promote to strongest constraint.
            if g.outcome == "REQUIRE_CONSENT":
                layered = "REQUIRE_CONSENT"
            elif g.outcome == "REQUIRE_SCC" and layered != "REQUIRE_CONSENT":
                layered = "REQUIRE_SCC"

        # 4. MiFID II (only when classification provided).
        if req.client_classification is not None:
            m = mifid2.evaluate(
                classification=req.client_classification,
                product_type=req.product_type,
                knowledge_experience_assessed=(
                    req.knowledge_experience_assessed
                ),
            )
            rule_ids.append(m.rule_id)
            wsp_sections.append(m.wsp_section)
            if m.outcome == "DENY":
                decision = EgressDecision(
                    outcome="DENY",
                    layered_outcome="DENY",
                    rule_ids=tuple(rule_ids),
                    wsp_sections=tuple(wsp_sections),
                    rationale=f"MiFID II DENY: {m.rationale}",
                    trace_id=req.trace_id,
                )
                self._emit_audit(decision, req)
                return decision

        # 5. MAS Notice 626 (SG) + HKMA (HK) marketing gates.
        if req.target_vendor_jurisdiction == Jurisdiction.sg:
            mas = mas_hkma.evaluate_mas_notice_626(
                classification=(
                    req.client_classification
                    or MiFIDClientClassification.retail
                ),
                marketing_channel=req.marketing_channel,
                product_type=req.product_type,
            )
            rule_ids.append(mas.rule_id)
            wsp_sections.append(mas.wsp_section)
            if mas.outcome == "DENY":
                decision = EgressDecision(
                    outcome="DENY",
                    layered_outcome="DENY",
                    rule_ids=tuple(rule_ids),
                    wsp_sections=tuple(wsp_sections),
                    rationale=f"MAS 626 DENY: {mas.rationale}",
                    trace_id=req.trace_id,
                )
                self._emit_audit(decision, req)
                return decision

        if req.target_vendor_jurisdiction == Jurisdiction.hk:
            hk = mas_hkma.evaluate_hkma_sfc(
                classification=(
                    req.client_classification
                    or MiFIDClientClassification.retail
                ),
                product_type=req.product_type,
                kyc_on_file=req.kyc_on_file,
            )
            rule_ids.append(hk.rule_id)
            wsp_sections.append(hk.wsp_section)
            if hk.outcome == "DENY":
                decision = EgressDecision(
                    outcome="DENY",
                    layered_outcome="DENY",
                    rule_ids=tuple(rule_ids),
                    wsp_sections=tuple(wsp_sections),
                    rationale=f"HKMA SFC DENY: {hk.rationale}",
                    trace_id=req.trace_id,
                )
                self._emit_audit(decision, req)
                return decision

        # 6. Cross-border MNPI scan — runs last, before allow.
        mnpi = scan_cross_border_mnpi(
            payload_fields=req.payload_fields,
            src_jx=req.primary_jurisdiction,
            dst_jx=req.target_vendor_jurisdiction,
        )
        rule_ids.append(mnpi.rule_id)
        wsp_sections.append(mnpi.wsp_section)
        if mnpi.outcome == "DENY":
            decision = EgressDecision(
                outcome="DENY",
                layered_outcome="DENY",
                rule_ids=tuple(rule_ids),
                wsp_sections=tuple(wsp_sections),
                rationale=f"cross-border MNPI: {mnpi.rationale}",
                trace_id=req.trace_id,
            )
            self._emit_audit(decision, req)
            return decision

        # 7. Compose final ALLOW.
        # outcome == ALLOW means the request may proceed; layered may
        # still carry REQUIRE_CONSENT / REQUIRE_SCC so the caller
        # knows to attach consent/SCC artifacts.
        rationale = f"ALLOW layered={layered}"
        decision = EgressDecision(
            outcome="ALLOW",
            layered_outcome=layered,
            rule_ids=tuple(rule_ids),
            wsp_sections=tuple(wsp_sections),
            rationale=rationale,
            trace_id=req.trace_id,
        )
        self._emit_audit(decision, req)
        return decision

    # ------------------------------------------------------------------
    # Audit emission — fail-closed (R6.3)
    # ------------------------------------------------------------------

    def _emit_audit(
        self, decision: EgressDecision, request: EgressRequest
    ) -> None:
        payload: dict = {
            "gap": "gap7",
            "schema_version": EGRESS_DECISION_SCHEMA_VERSION,
            "requested_by": request.requested_by,
            "primary_jurisdiction": request.primary_jurisdiction.value,
            "data_residency": request.data_residency.value,
            "target_vendor_jurisdiction": (
                request.target_vendor_jurisdiction.value
            ),
            "decision": decision.model_dump(mode="json"),
        }
        try:
            self._audit.write(payload)
        except Exception as exc:  # noqa: BLE001 — translate any failure
            raise AuditWriteFailed("audit_write_failed") from exc
