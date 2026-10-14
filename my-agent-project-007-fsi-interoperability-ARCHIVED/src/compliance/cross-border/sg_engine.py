"""
Gap 7: Cross-Border Regulatory — SGEngine (Singapore MAS-specific).

Extracted from the monolithic CrossBorderEngine. Contains MAS TRM incident
management, FEAT assessment, AIRG materiality/inventory, MAS vendor risk,
and SG consent requirements.

All decisions are deterministic — no LLM used.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

try:
    from .models import (
        AIRGInventoryEntry,
        AIRGMaterialityAssessment,
        FEATAssessment,
        FEATStatus,
        IncidentSeverity,
        MASIncident,
        MASVendorRisk,
        MaterialityLevel,
        SuitabilityStandard,
        VendorRiskRating,
    )
except ImportError:
    from models import (
        AIRGInventoryEntry,
        AIRGMaterialityAssessment,
        FEATAssessment,
        FEATStatus,
        IncidentSeverity,
        MASIncident,
        MASVendorRisk,
        MaterialityLevel,
        SuitabilityStandard,
        VendorRiskRating,
    )


# ── MAS TRM deadline offsets ─────────────────────────────────────

_MAS_INITIAL_HOURS = 1
_MAS_INTERMEDIATE_DAYS = 14
_MAS_FINAL_DAYS = 30

# ── FEAT fairness threshold ──────────────────────────────────────

_FEAT_FAIRNESS_THRESHOLD = 0.7

# ── SG consent-required processing types ─────────────────────────

_SG_CONSENT_PROCESSING: frozenset[str] = frozenset({
    "ai_credit_decision",
    "ai_insurance_decision",
})

# ── AIRG controls by materiality ─────────────────────────────────

_AIRG_CONTROLS_HIGH: list[str] = [
    "pre_deployment_testing",
    "ongoing_monitoring",
    "human_oversight",
    "explainability",
    "bias_testing",
    "change_management",
    "third_party_risk_management",
]

_AIRG_CONTROLS_MEDIUM: list[str] = [
    "pre_deployment_testing",
    "ongoing_monitoring",
    "explainability",
    "change_management",
]

_AIRG_CONTROLS_LOW: list[str] = [
    "change_management",
    "basic_documentation",
]


class SGEngine:
    """
    Singapore MAS-specific compliance engine.

    Covers MAS TRM incident management, FEAT assessment,
    AIRG materiality/inventory, vendor risk, and SG consent.

    All decisions are deterministic — no LLM used.
    """

    def __init__(self) -> None:
        self._ai_inventory: dict[str, AIRGInventoryEntry] = {}

    # ── Suitability standard ─────────────────────────────────────

    def resolve_suitability_standard(self) -> SuitabilityStandard:
        """SG always applies fiduciary standard."""
        return SuitabilityStandard.FIDUCIARY

    # ── MAS TRM incident management ─────────────────────────────

    def create_mas_incident(
        self,
        severity: str,
        description: str,
        detected_at: Optional[datetime] = None,
    ) -> MASIncident:
        """Create a MAS TRM incident with 1-hour initial notification deadline."""
        sev = IncidentSeverity(severity)
        now = detected_at or datetime.now(timezone.utc)
        return MASIncident(
            incident_id=f"MAS-{uuid.uuid4().hex[:8].upper()}",
            severity=sev,
            description=description,
            detected_at=now,
            initial_notification_deadline=now + timedelta(hours=_MAS_INITIAL_HOURS),
            intermediate_deadline=now + timedelta(days=_MAS_INTERMEDIATE_DAYS),
            final_deadline=now + timedelta(days=_MAS_FINAL_DAYS),
            mas_notified=False,
        )

    # ── FEAT assessment ──────────────────────────────────────────

    def assess_feat_compliance(
        self,
        system_name: str,
        fairness_score: float,
        ethics_reviewed: bool,
        accountability_owner: str,
        transparency_disclosed: bool,
    ) -> FEATAssessment:
        """Assess FEAT compliance. All four pillars must pass for overall PASS."""
        now = datetime.now(timezone.utc)

        fairness_ok = fairness_score >= _FEAT_FAIRNESS_THRESHOLD
        ethics_ok = ethics_reviewed
        accountability_ok = bool(accountability_owner and accountability_owner.strip())
        transparency_ok = transparency_disclosed

        f_status = FEATStatus.PASS if fairness_ok else FEATStatus.FAIL
        e_status = FEATStatus.PASS if ethics_ok else FEATStatus.FAIL
        a_status = FEATStatus.PASS if accountability_ok else FEATStatus.FAIL
        t_status = FEATStatus.PASS if transparency_ok else FEATStatus.FAIL

        all_pass = fairness_ok and ethics_ok and accountability_ok and transparency_ok
        overall = FEATStatus.PASS if all_pass else FEATStatus.FAIL

        return FEATAssessment(
            system_name=system_name,
            fairness_score=fairness_score,
            fairness_status=f_status,
            ethics_review_status=e_status,
            accountability_owner=accountability_owner,
            accountability_status=a_status,
            transparency_disclosed=transparency_disclosed,
            transparency_status=t_status,
            overall_status=overall,
            bias_test_date=now if fairness_ok else None,
            bias_test_result="pass" if fairness_ok else "below_threshold",
            assessed_at=now,
        )

    # ── AIRG materiality assessment ──────────────────────────────

    def assess_airg_materiality(
        self,
        use_case_name: str,
        impact: str,
        complexity: str,
        reliance: str,
    ) -> AIRGMaterialityAssessment:
        """Assess AIRG risk materiality. Overall = highest dimension."""
        impact_lvl = MaterialityLevel(impact)
        complexity_lvl = MaterialityLevel(complexity)
        reliance_lvl = MaterialityLevel(reliance)

        _rank = {MaterialityLevel.HIGH: 3, MaterialityLevel.MEDIUM: 2, MaterialityLevel.LOW: 1}
        max_rank = max(_rank[impact_lvl], _rank[complexity_lvl], _rank[reliance_lvl])
        _reverse = {3: MaterialityLevel.HIGH, 2: MaterialityLevel.MEDIUM, 1: MaterialityLevel.LOW}
        overall = _reverse[max_rank]

        if overall == MaterialityLevel.HIGH:
            controls = list(_AIRG_CONTROLS_HIGH)
        elif overall == MaterialityLevel.MEDIUM:
            controls = list(_AIRG_CONTROLS_MEDIUM)
        else:
            controls = list(_AIRG_CONTROLS_LOW)

        return AIRGMaterialityAssessment(
            use_case_name=use_case_name,
            impact_level=impact_lvl,
            complexity_level=complexity_lvl,
            reliance_level=reliance_lvl,
            overall_materiality=overall,
            controls_required=controls,
        )

    # ── AIRG AI inventory ────────────────────────────────────────

    def register_ai_system(
        self,
        system_name: str,
        use_case: str,
        materiality: str,
        owner: str,
    ) -> AIRGInventoryEntry:
        """Register an AI system in the AIRG inventory."""
        mat = MaterialityLevel(materiality)
        entry = AIRGInventoryEntry(
            system_name=system_name,
            use_case_category=use_case,
            materiality=mat,
            owner=owner,
            deployment_status="registered",
            pre_deployment_tested=False,
            monitoring_enabled=False,
        )
        self._ai_inventory[system_name] = entry
        return entry

    def get_ai_inventory(self) -> list[AIRGInventoryEntry]:
        """Return all registered AI systems."""
        return list(self._ai_inventory.values())

    # ── MAS vendor risk ──────────────────────────────────────────

    def check_mas_vendor_risk(
        self,
        vendor_name: str,
        ai_services: list[str],
        last_pen_test_date: Optional[datetime] = None,
        access_controls_verified: bool = False,
    ) -> MASVendorRisk:
        """Assess third-party AI vendor risk per MAS TRM Guidelines."""
        now = datetime.now(timezone.utc)

        if last_pen_test_date is None:
            rating = VendorRiskRating.HIGH
        elif (now - last_pen_test_date).days > 365:
            rating = VendorRiskRating.HIGH
        elif not access_controls_verified:
            rating = VendorRiskRating.MEDIUM
        else:
            rating = VendorRiskRating.LOW

        return MASVendorRisk(
            vendor_name=vendor_name,
            ai_services=ai_services,
            risk_rating=rating,
            last_assessment_date=now,
            penetration_test_date=last_pen_test_date,
            access_controls_verified=access_controls_verified,
        )

    # ── SG consent for AI decisions ──────────────────────────────

    def check_sg_consent_required(self, processing_type: str) -> bool:
        """Check if SG requires consent for a specific AI processing type."""
        return processing_type in _SG_CONSENT_PROCESSING
