"""
Gap 7: Cross-Border Regulatory — CrossBorderEngine facade.

Thin facade that composes BaseEngine + SGEngine + USEngine.
Preserves the original public API for backward compatibility.

All compliance decisions are deterministic — no LLM used.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

try:
    from .base_engine import BaseEngine
    from .sg_engine import SGEngine
    from .us_engine import USEngine
    from .models import (
        AIRGInventoryEntry,
        AIRGMaterialityAssessment,
        ConcentrationResult,
        ConflictResolution,
        ConsentRecord,
        DORAIncident,
        ErasureRequest,
        FEATAssessment,
        FINRA2210Review,
        FINRAIncident,
        JurisdictionConfig,
        MASIncident,
        MASVendorRisk,
        RetentionRequirement,
        SECExaminationPackage,
        SuitabilityStandard,
    )
except ImportError:
    from base_engine import BaseEngine
    from sg_engine import SGEngine
    from us_engine import USEngine
    from models import (
        AIRGInventoryEntry,
        AIRGMaterialityAssessment,
        ConcentrationResult,
        ConflictResolution,
        ConsentRecord,
        DORAIncident,
        ErasureRequest,
        FEATAssessment,
        FINRA2210Review,
        FINRAIncident,
        JurisdictionConfig,
        MASIncident,
        MASVendorRisk,
        RetentionRequirement,
        SECExaminationPackage,
        SuitabilityStandard,
    )


class CrossBorderEngine:
    """
    Cross-border regulatory compliance engine (facade).

    Composes BaseEngine (shared logic), SGEngine (MAS-specific),
    and USEngine (SEC/FINRA-specific). Delegates all calls to the
    appropriate sub-engine while preserving the original public API.

    All decisions are deterministic — no LLM used.
    """

    def __init__(self) -> None:
        self._base = BaseEngine()
        self._sg = SGEngine()
        self._us = USEngine()

    # ══════════════════════════════════════════════════════════════
    # BaseEngine delegates
    # ══════════════════════════════════════════════════════════════

    def get_jurisdiction_config(self, jurisdiction: str) -> JurisdictionConfig:
        """Get regulatory configuration for a jurisdiction."""
        return self._base.get_jurisdiction_config(jurisdiction)

    def get_data_residency_region(self, jurisdiction: str) -> str:
        """Get the AWS region for data residency enforcement."""
        return self._base.get_data_residency_region(jurisdiction)

    def resolve_suitability_standard(
        self,
        jurisdiction: str,
        registration_type: str = "bd_only",
    ) -> SuitabilityStandard:
        """Resolve the applicable suitability standard per jurisdiction."""
        return self._base.resolve_suitability_standard(jurisdiction, registration_type)

    def resolve_erasure_vs_retention(
        self,
        data_category: str,
        jurisdiction: str,
    ) -> ErasureRequest:
        """Resolve GDPR erasure vs regulatory retention conflict."""
        return self._base.resolve_erasure_vs_retention(data_category, jurisdiction)

    def check_consent_required(
        self,
        jurisdiction: str,
        processing_type: str,
    ) -> bool:
        """Check if consent is required for a processing type."""
        return self._base.check_consent_required(jurisdiction, processing_type)

    def record_consent(
        self,
        client_id: str,
        jurisdiction: str,
        consent_type: str,
        granted: bool,
    ) -> ConsentRecord:
        """Record a consent decision for a client."""
        return self._base.record_consent(client_id, jurisdiction, consent_type, granted)

    def check_consent(
        self,
        client_id: str,
        jurisdiction: str,
        consent_type: str,
    ) -> bool:
        """Check if a client has granted consent."""
        return self._base.check_consent(client_id, jurisdiction, consent_type)

    def withdraw_consent(
        self,
        client_id: str,
        jurisdiction: str,
        consent_type: str,
    ) -> ConsentRecord:
        """Withdraw a previously granted consent."""
        return self._base.withdraw_consent(client_id, jurisdiction, consent_type)

    def create_dora_incident(
        self,
        severity: str,
        description: str,
        detected_at: Optional[datetime] = None,
    ) -> DORAIncident:
        """Create a DORA ICT incident with notification deadlines."""
        return self._base.create_dora_incident(severity, description, detected_at)

    def resolve_conflict(
        self,
        request_type: str,
        jurisdictions: list[str],
    ) -> ConflictResolution:
        """Resolve cross-jurisdiction regulatory conflicts."""
        return self._base.resolve_conflict(request_type, jurisdictions)

    # ══════════════════════════════════════════════════════════════
    # SGEngine delegates
    # ══════════════════════════════════════════════════════════════

    def create_mas_incident(
        self,
        severity: str,
        description: str,
        detected_at: Optional[datetime] = None,
    ) -> MASIncident:
        """Create a MAS TRM incident with 1-hour notification deadline."""
        return self._sg.create_mas_incident(severity, description, detected_at)

    def assess_feat_compliance(
        self,
        system_name: str,
        fairness_score: float,
        ethics_reviewed: bool,
        accountability_owner: str,
        transparency_disclosed: bool,
    ) -> FEATAssessment:
        """Assess FEAT compliance (all four pillars)."""
        return self._sg.assess_feat_compliance(
            system_name, fairness_score, ethics_reviewed,
            accountability_owner, transparency_disclosed,
        )

    def assess_airg_materiality(
        self,
        use_case_name: str,
        impact: str,
        complexity: str,
        reliance: str,
    ) -> AIRGMaterialityAssessment:
        """Assess AIRG risk materiality for an AI use case."""
        return self._sg.assess_airg_materiality(use_case_name, impact, complexity, reliance)

    def register_ai_system(
        self,
        system_name: str,
        use_case: str,
        materiality: str,
        owner: str,
    ) -> AIRGInventoryEntry:
        """Register an AI system in the AIRG inventory."""
        return self._sg.register_ai_system(system_name, use_case, materiality, owner)

    def get_ai_inventory(self) -> list[AIRGInventoryEntry]:
        """Return all registered AI systems."""
        return self._sg.get_ai_inventory()

    def check_mas_vendor_risk(
        self,
        vendor_name: str,
        ai_services: list[str],
        last_pen_test_date: Optional[datetime] = None,
        access_controls_verified: bool = False,
    ) -> MASVendorRisk:
        """Assess third-party AI vendor risk per MAS TRM."""
        return self._sg.check_mas_vendor_risk(
            vendor_name, ai_services, last_pen_test_date, access_controls_verified,
        )

    def check_sg_consent_required(self, processing_type: str) -> bool:
        """Check if SG requires consent for a specific AI processing type."""
        return self._sg.check_sg_consent_required(processing_type)

    # ══════════════════════════════════════════════════════════════
    # USEngine delegates
    # ══════════════════════════════════════════════════════════════

    def check_reg_bi_applicability(
        self,
        registration_type: str,
        archetype: str = "retail",
    ) -> bool:
        """Check if Reg BI applies (BD/dual retail only)."""
        return self._us.check_reg_bi_applicability(registration_type, archetype)

    def check_finra_2210_review_required(
        self,
        communication_type: str,
        audience: str = "retail",
    ) -> FINRA2210Review:
        """Determine FINRA 2210 review requirements."""
        return self._us.check_finra_2210_review_required(communication_type, audience)

    def check_sec_17a4_retention(
        self,
        record_type: str,
    ) -> RetentionRequirement:
        """Get SEC 17a-4 retention requirement for a record type."""
        return self._us.check_sec_17a4_retention(record_type)

    def create_sec_examination_package(
        self,
        firm_id: str,
    ) -> SECExaminationPackage:
        """Generate SEC/FINRA examination support package."""
        return self._us.create_sec_examination_package(firm_id)

    def check_finra_restricted_list(
        self,
        security_id: str,
        restricted_list: list[str],
    ) -> bool:
        """Check if a security is on the firm restricted list."""
        return self._us.check_finra_restricted_list(security_id, restricted_list)

    def check_concentration_limit(
        self,
        position_pct: float,
        account_type: str = "individual_taxable",
        security_id: str = "",
    ) -> ConcentrationResult:
        """Check position concentration against limits."""
        return self._us.check_concentration_limit(position_pct, account_type, security_id)

    def check_trading_window(
        self,
        security_id: str,
        is_restricted_period: bool,
    ) -> bool:
        """Check if trading is allowed (False during restricted periods)."""
        return self._us.check_trading_window(security_id, is_restricted_period)

    def create_finra_incident(
        self,
        severity: str,
        description: str,
        detected_at: Optional[datetime] = None,
    ) -> FINRAIncident:
        """Create a FINRA incident with filing deadlines."""
        return self._us.create_finra_incident(severity, description, detected_at)
