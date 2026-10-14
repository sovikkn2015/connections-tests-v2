"""
Tests for Gap 7: Cross-Border Regulatory.

Covers: jurisdiction configs, suitability standards, GDPR erasure vs retention,
consent management, DORA incidents, data residency, conflict resolution.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent


def _load_local(name: str):
    """Load a module from this directory by file path (avoids sys.path collisions)."""
    spec = importlib.util.spec_from_file_location(
        f"crossborder_{name}", _HERE / f"{name}.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_models = _load_local("models")
sys.modules["models"] = _models
_jurisdiction = _load_local("jurisdiction")

CrossBorderEngine = _jurisdiction.CrossBorderEngine
Jurisdiction = _models.Jurisdiction
SuitabilityStandard = _models.SuitabilityStandard
ErasureDecision = _models.ErasureDecision
DataCategory = _models.DataCategory
ConflictPriority = _models.ConflictPriority
IncidentSeverity = _models.IncidentSeverity
ConsentType = _models.ConsentType
FEATStatus = _models.FEATStatus
MaterialityLevel = _models.MaterialityLevel
VendorRiskRating = _models.VendorRiskRating


# ── Jurisdiction config defaults ─────────────────────────────────


class TestJurisdictionConfig:
    def test_us_config(self):
        eng = CrossBorderEngine()
        cfg = eng.get_jurisdiction_config("US")
        assert cfg.jurisdiction == Jurisdiction.US
        assert cfg.regulator == "FINRA/SEC"
        assert cfg.suitability_standard == SuitabilityStandard.REG_BI
        assert cfg.retention_years == 6
        assert cfg.worm_required is True
        assert cfg.gdpr_enabled is False
        assert cfg.dora_enabled is False

    def test_eu_config(self):
        eng = CrossBorderEngine()
        cfg = eng.get_jurisdiction_config("EU")
        assert cfg.jurisdiction == Jurisdiction.EU
        assert cfg.regulator == "ESMA/NCA"
        assert cfg.suitability_standard == SuitabilityStandard.MIFID2
        assert cfg.retention_years == 5
        assert cfg.gdpr_enabled is True
        assert cfg.dora_enabled is True
        assert cfg.ai_act_enabled is True

    def test_uk_config(self):
        eng = CrossBorderEngine()
        cfg = eng.get_jurisdiction_config("UK")
        assert cfg.jurisdiction == Jurisdiction.UK
        assert cfg.regulator == "FCA"
        assert cfg.suitability_standard == SuitabilityStandard.CONSUMER_DUTY
        assert cfg.gdpr_enabled is True
        assert cfg.dora_enabled is False

    def test_sg_config(self):
        eng = CrossBorderEngine()
        cfg = eng.get_jurisdiction_config("SG")
        assert cfg.jurisdiction == Jurisdiction.SG
        assert cfg.regulator == "MAS"
        assert cfg.suitability_standard == SuitabilityStandard.FIDUCIARY

    def test_hk_config(self):
        eng = CrossBorderEngine()
        cfg = eng.get_jurisdiction_config("HK")
        assert cfg.jurisdiction == Jurisdiction.HK
        assert cfg.regulator == "SFC"
        assert cfg.retention_years == 7

    def test_unsupported_jurisdiction_raises(self):
        eng = CrossBorderEngine()
        with pytest.raises(ValueError, match="Unsupported"):
            eng.get_jurisdiction_config("XX")


# ── Suitability standard resolution ─────────────────────────────


class TestSuitabilityStandard:
    def test_us_bd_reg_bi(self):
        eng = CrossBorderEngine()
        result = eng.resolve_suitability_standard("US", "bd_only")
        assert result == SuitabilityStandard.REG_BI

    def test_us_ria_fiduciary(self):
        eng = CrossBorderEngine()
        result = eng.resolve_suitability_standard("US", "ria_only")
        assert result == SuitabilityStandard.FIDUCIARY

    def test_us_ria_short_form(self):
        eng = CrossBorderEngine()
        result = eng.resolve_suitability_standard("US", "ria")
        assert result == SuitabilityStandard.FIDUCIARY

    def test_eu_mifid2(self):
        eng = CrossBorderEngine()
        result = eng.resolve_suitability_standard("EU")
        assert result == SuitabilityStandard.MIFID2

    def test_uk_consumer_duty(self):
        eng = CrossBorderEngine()
        result = eng.resolve_suitability_standard("UK")
        assert result == SuitabilityStandard.CONSUMER_DUTY

    def test_sg_fiduciary(self):
        eng = CrossBorderEngine()
        result = eng.resolve_suitability_standard("SG")
        assert result == SuitabilityStandard.FIDUCIARY

    def test_hk_fiduciary(self):
        eng = CrossBorderEngine()
        result = eng.resolve_suitability_standard("HK")
        assert result == SuitabilityStandard.FIDUCIARY


# ── GDPR erasure vs retention ────────────────────────────────────


class TestErasureVsRetention:
    def test_regulated_record_denied(self):
        eng = CrossBorderEngine()
        result = eng.resolve_erasure_vs_retention("regulated_record", "EU")
        assert result.decision == ErasureDecision.DENY_ERASURE
        assert "17a-4" in result.reason or "retention" in result.reason.lower()

    def test_non_regulated_pii_allowed(self):
        eng = CrossBorderEngine()
        result = eng.resolve_erasure_vs_retention("non_regulated_pii", "EU")
        assert result.decision == ErasureDecision.ALLOW_ERASURE
        assert result.erasure_deadline is not None

    def test_memory_allowed(self):
        eng = CrossBorderEngine()
        result = eng.resolve_erasure_vs_retention("memory", "EU")
        assert result.decision == ErasureDecision.ALLOW_ERASURE


# ── Consent management ───────────────────────────────────────────


class TestConsentManagement:
    def test_record_consent_granted(self):
        eng = CrossBorderEngine()
        record = eng.record_consent("C-200", "EU", "llm_processing", True)
        assert record.client_id == "C-200"
        assert record.jurisdiction == Jurisdiction.EU
        assert record.consent_type == ConsentType.LLM_PROCESSING
        assert record.granted is True
        assert record.granted_at is not None

    def test_check_consent_granted(self):
        eng = CrossBorderEngine()
        eng.record_consent("C-200", "EU", "llm_processing", True)
        assert eng.check_consent("C-200", "EU", "llm_processing") is True

    def test_check_consent_not_granted(self):
        eng = CrossBorderEngine()
        assert eng.check_consent("C-200", "EU", "llm_processing") is False

    def test_withdraw_consent(self):
        eng = CrossBorderEngine()
        eng.record_consent("C-200", "EU", "llm_processing", True)
        record = eng.withdraw_consent("C-200", "EU", "llm_processing")
        assert record.granted is False
        assert record.withdrawn_at is not None
        assert eng.check_consent("C-200", "EU", "llm_processing") is False

    def test_withdraw_consent_never_granted(self):
        eng = CrossBorderEngine()
        record = eng.withdraw_consent("C-300", "UK", "llm_processing")
        assert record.granted is False
        assert record.withdrawn_at is not None


# ── Consent required by jurisdiction ─────────────────────────────


class TestConsentRequired:
    def test_eu_requires_llm_consent(self):
        eng = CrossBorderEngine()
        assert eng.check_consent_required("EU", "llm_processing") is True

    def test_uk_requires_llm_consent(self):
        eng = CrossBorderEngine()
        assert eng.check_consent_required("UK", "llm_processing") is True

    def test_us_no_llm_consent(self):
        eng = CrossBorderEngine()
        assert eng.check_consent_required("US", "llm_processing") is False

    def test_sg_no_llm_consent(self):
        eng = CrossBorderEngine()
        assert eng.check_consent_required("SG", "llm_processing") is False

    def test_marketing_consent_required_everywhere(self):
        eng = CrossBorderEngine()
        assert eng.check_consent_required("US", "marketing") is True
        assert eng.check_consent_required("EU", "marketing") is True
        assert eng.check_consent_required("SG", "marketing") is True


# ── DORA incident deadlines ──────────────────────────────────────


class TestDORAIncident:
    def test_major_incident_deadlines(self):
        eng = CrossBorderEngine()
        detected = datetime(2026, 7, 15, 10, 0, 0, tzinfo=timezone.utc)
        incident = eng.create_dora_incident("major", "Data breach", detected_at=detected)

        assert incident.severity == IncidentSeverity.MAJOR
        assert incident.detected_at == detected
        assert incident.initial_notification_deadline == detected + timedelta(hours=4)
        assert incident.intermediate_deadline == detected + timedelta(hours=72)
        assert incident.final_deadline == detected + timedelta(days=30)
        assert incident.nca_notified is False

    def test_significant_incident(self):
        eng = CrossBorderEngine()
        incident = eng.create_dora_incident("significant", "Extended outage")
        assert incident.severity == IncidentSeverity.SIGNIFICANT
        assert incident.incident_id.startswith("DORA-")

    def test_minor_incident(self):
        eng = CrossBorderEngine()
        incident = eng.create_dora_incident("minor", "Brief service degradation")
        assert incident.severity == IncidentSeverity.MINOR


# ── Data residency routing ───────────────────────────────────────


class TestDataResidency:
    def test_us_region(self):
        eng = CrossBorderEngine()
        assert eng.get_data_residency_region("US") == "us-east-1"

    def test_eu_region(self):
        eng = CrossBorderEngine()
        assert eng.get_data_residency_region("EU") == "eu-central-1"

    def test_uk_region(self):
        eng = CrossBorderEngine()
        assert eng.get_data_residency_region("UK") == "eu-west-2"

    def test_sg_region(self):
        eng = CrossBorderEngine()
        assert eng.get_data_residency_region("SG") == "ap-southeast-1"

    def test_hk_region(self):
        eng = CrossBorderEngine()
        assert eng.get_data_residency_region("HK") == "ap-east-1"

    def test_unsupported_region_raises(self):
        eng = CrossBorderEngine()
        with pytest.raises(ValueError):
            eng.get_data_residency_region("XX")


# ── Conflict resolution hierarchy ────────────────────────────────


class TestConflictResolution:
    def test_erasure_retention_conflict(self):
        eng = CrossBorderEngine()
        result = eng.resolve_conflict("gdpr_erasure", ["US", "EU"])
        assert result.priority_applied == ConflictPriority.RETENTION
        assert "retained" in result.resolution.lower() or "retention" in result.resolution.lower()

    def test_safety_block_conflict(self):
        eng = CrossBorderEngine()
        result = eng.resolve_conflict("safety_block", ["US", "EU"])
        assert result.priority_applied == ConflictPriority.SAFETY
        assert "blocked" in result.resolution.lower()

    def test_sanctions_safety_priority(self):
        eng = CrossBorderEngine()
        result = eng.resolve_conflict("sanctions", ["US", "EU", "UK"])
        assert result.priority_applied == ConflictPriority.SAFETY

    def test_data_minimization_privacy(self):
        eng = CrossBorderEngine()
        result = eng.resolve_conflict("data_collection", ["US", "EU"])
        assert result.priority_applied == ConflictPriority.PRIVACY

    def test_reporting_operational(self):
        eng = CrossBorderEngine()
        result = eng.resolve_conflict("reporting", ["US", "EU", "UK"])
        assert result.priority_applied == ConflictPriority.OPERATIONAL
        assert len(result.jurisdictions) == 3

    def test_best_execution_operational(self):
        eng = CrossBorderEngine()
        result = eng.resolve_conflict("best_execution", ["EU"])
        assert result.priority_applied == ConflictPriority.OPERATIONAL

    def test_unknown_type_defaults_operational(self):
        eng = CrossBorderEngine()
        result = eng.resolve_conflict("unknown_type", ["US"])
        assert result.priority_applied == ConflictPriority.OPERATIONAL


# ── Multi-jurisdiction firm ──────────────────────────────────────


class TestMultiJurisdiction:
    def test_dual_jurisdiction_configs(self):
        eng = CrossBorderEngine()
        us_cfg = eng.get_jurisdiction_config("US")
        eu_cfg = eng.get_jurisdiction_config("EU")
        assert us_cfg.gdpr_enabled is False
        assert eu_cfg.gdpr_enabled is True
        assert us_cfg.retention_years == 6
        assert eu_cfg.retention_years == 5

    def test_consent_per_jurisdiction(self):
        eng = CrossBorderEngine()
        eng.record_consent("C-400", "EU", "llm_processing", True)
        eng.record_consent("C-400", "UK", "llm_processing", False)
        assert eng.check_consent("C-400", "EU", "llm_processing") is True
        assert eng.check_consent("C-400", "UK", "llm_processing") is False

    def test_different_suitability_per_jurisdiction(self):
        eng = CrossBorderEngine()
        us_std = eng.resolve_suitability_standard("US", "bd_only")
        eu_std = eng.resolve_suitability_standard("EU")
        uk_std = eng.resolve_suitability_standard("UK")
        assert us_std != eu_std
        assert eu_std != uk_std


# ── DPA record tracking ─────────────────────────────────────────


class TestDPARecord:
    def test_dpa_model_creation(self):
        DPARecord = _models.DPARecord
        VendorCriticality = _models.VendorCriticality
        dpa = DPARecord(
            vendor_name="AWS Bedrock",
            service_type="LLM Provider",
            dpa_signed=True,
            scc_required=True,
            sub_processors=["Anthropic"],
            criticality=VendorCriticality.CRITICAL,
        )
        assert dpa.vendor_name == "AWS Bedrock"
        assert dpa.dpa_signed is True
        assert dpa.scc_required is True
        assert dpa.criticality == VendorCriticality.CRITICAL
        assert "Anthropic" in dpa.sub_processors

    def test_dpa_defaults(self):
        DPARecord = _models.DPARecord
        VendorCriticality = _models.VendorCriticality
        dpa = DPARecord(vendor_name="Test Vendor", service_type="Analytics")
        assert dpa.dpa_signed is False
        assert dpa.scc_required is False
        assert dpa.sub_processors == []
        assert dpa.criticality == VendorCriticality.STANDARD


# ── MAS TRM incident deadlines ───────────────────────────────────


class TestMASIncident:
    def test_mas_incident_1hr_deadline(self):
        """MAS TRM requires 1-hour initial notification — NOT 4 hours like DORA."""
        eng = CrossBorderEngine()
        detected = datetime(2026, 7, 15, 10, 0, 0, tzinfo=timezone.utc)
        incident = eng.create_mas_incident("major", "Data breach", detected_at=detected)

        assert incident.severity == IncidentSeverity.MAJOR
        assert incident.detected_at == detected
        assert incident.initial_notification_deadline == detected + timedelta(hours=1)
        assert incident.intermediate_deadline == detected + timedelta(days=14)
        assert incident.final_deadline == detected + timedelta(days=30)
        assert incident.mas_notified is False
        assert incident.incident_id.startswith("MAS-")

    def test_mas_vs_dora_different_deadlines(self):
        """MAS initial = 1hr, DORA initial = 4hr — verify they differ."""
        eng = CrossBorderEngine()
        detected = datetime(2026, 7, 15, 10, 0, 0, tzinfo=timezone.utc)
        mas = eng.create_mas_incident("major", "Breach", detected_at=detected)
        dora = eng.create_dora_incident("major", "Breach", detected_at=detected)

        assert mas.initial_notification_deadline == detected + timedelta(hours=1)
        assert dora.initial_notification_deadline == detected + timedelta(hours=4)
        assert mas.initial_notification_deadline < dora.initial_notification_deadline

    def test_mas_significant_incident(self):
        eng = CrossBorderEngine()
        incident = eng.create_mas_incident("significant", "Extended outage")
        assert incident.severity == IncidentSeverity.SIGNIFICANT
        assert incident.incident_id.startswith("MAS-")

    def test_mas_minor_incident(self):
        eng = CrossBorderEngine()
        incident = eng.create_mas_incident("minor", "Brief degradation")
        assert incident.severity == IncidentSeverity.MINOR


# ── FEAT assessment ──────────────────────────────────────────────


class TestFEATAssessment:
    def test_all_pillars_pass(self):
        eng = CrossBorderEngine()
        result = eng.assess_feat_compliance(
            system_name="WealthAdvisor AI",
            fairness_score=0.85,
            ethics_reviewed=True,
            accountability_owner="Jane Smith",
            transparency_disclosed=True,
        )
        assert result.overall_status == FEATStatus.PASS
        assert result.fairness_status == FEATStatus.PASS
        assert result.ethics_review_status == FEATStatus.PASS
        assert result.accountability_status == FEATStatus.PASS
        assert result.transparency_status == FEATStatus.PASS

    def test_fairness_below_threshold_fails(self):
        eng = CrossBorderEngine()
        result = eng.assess_feat_compliance(
            system_name="CreditScorer",
            fairness_score=0.5,
            ethics_reviewed=True,
            accountability_owner="Jane Smith",
            transparency_disclosed=True,
        )
        assert result.overall_status == FEATStatus.FAIL
        assert result.fairness_status == FEATStatus.FAIL
        assert result.bias_test_result == "below_threshold"

    def test_fairness_at_threshold_passes(self):
        eng = CrossBorderEngine()
        result = eng.assess_feat_compliance(
            system_name="RiskModel",
            fairness_score=0.7,
            ethics_reviewed=True,
            accountability_owner="Jane Smith",
            transparency_disclosed=True,
        )
        assert result.fairness_status == FEATStatus.PASS
        assert result.overall_status == FEATStatus.PASS

    def test_ethics_not_reviewed_fails(self):
        eng = CrossBorderEngine()
        result = eng.assess_feat_compliance(
            system_name="ChatBot",
            fairness_score=0.9,
            ethics_reviewed=False,
            accountability_owner="Jane Smith",
            transparency_disclosed=True,
        )
        assert result.overall_status == FEATStatus.FAIL
        assert result.ethics_review_status == FEATStatus.FAIL

    def test_missing_accountability_owner_fails(self):
        eng = CrossBorderEngine()
        result = eng.assess_feat_compliance(
            system_name="Recommender",
            fairness_score=0.9,
            ethics_reviewed=True,
            accountability_owner="",
            transparency_disclosed=True,
        )
        assert result.overall_status == FEATStatus.FAIL
        assert result.accountability_status == FEATStatus.FAIL

    def test_transparency_not_disclosed_fails(self):
        eng = CrossBorderEngine()
        result = eng.assess_feat_compliance(
            system_name="PortfolioOptimizer",
            fairness_score=0.9,
            ethics_reviewed=True,
            accountability_owner="Jane Smith",
            transparency_disclosed=False,
        )
        assert result.overall_status == FEATStatus.FAIL
        assert result.transparency_status == FEATStatus.FAIL


# ── AIRG materiality assessment ──────────────────────────────────


class TestAIRGMateriality:
    def test_all_high_yields_high(self):
        eng = CrossBorderEngine()
        result = eng.assess_airg_materiality("TradeBot", "high", "high", "high")
        assert result.overall_materiality == MaterialityLevel.HIGH

    def test_all_low_yields_low(self):
        eng = CrossBorderEngine()
        result = eng.assess_airg_materiality("SimpleCalc", "low", "low", "low")
        assert result.overall_materiality == MaterialityLevel.LOW

    def test_mixed_levels_takes_highest(self):
        eng = CrossBorderEngine()
        result = eng.assess_airg_materiality("MixedBot", "low", "medium", "low")
        assert result.overall_materiality == MaterialityLevel.MEDIUM

    def test_one_high_dimension_yields_high(self):
        eng = CrossBorderEngine()
        result = eng.assess_airg_materiality("CriticalBot", "high", "low", "low")
        assert result.overall_materiality == MaterialityLevel.HIGH

    def test_high_requires_all_controls(self):
        eng = CrossBorderEngine()
        result = eng.assess_airg_materiality("HighRisk", "high", "high", "high")
        assert "pre_deployment_testing" in result.controls_required
        assert "ongoing_monitoring" in result.controls_required
        assert "human_oversight" in result.controls_required
        assert "explainability" in result.controls_required
        assert "bias_testing" in result.controls_required
        assert len(result.controls_required) == 7

    def test_low_requires_basic_controls_only(self):
        eng = CrossBorderEngine()
        result = eng.assess_airg_materiality("LowRisk", "low", "low", "low")
        assert "change_management" in result.controls_required
        assert "basic_documentation" in result.controls_required
        assert "human_oversight" not in result.controls_required
        assert len(result.controls_required) == 2


# ── AIRG AI inventory ────────────────────────────────────────────


class TestAIRGInventory:
    def test_register_and_retrieve(self):
        eng = CrossBorderEngine()
        entry = eng.register_ai_system("WealthBot", "advisory", "high", "Alice")
        assert entry.system_name == "WealthBot"
        assert entry.use_case_category == "advisory"
        assert entry.materiality == MaterialityLevel.HIGH
        assert entry.owner == "Alice"
        assert entry.deployment_status == "registered"

    def test_get_inventory_list(self):
        eng = CrossBorderEngine()
        eng.register_ai_system("Bot1", "advisory", "high", "Alice")
        eng.register_ai_system("Bot2", "analytics", "low", "Bob")
        inventory = eng.get_ai_inventory()
        assert len(inventory) == 2
        names = {e.system_name for e in inventory}
        assert names == {"Bot1", "Bot2"}

    def test_pre_deployment_tested_default_false(self):
        eng = CrossBorderEngine()
        entry = eng.register_ai_system("NewBot", "trading", "high", "Carol")
        assert entry.pre_deployment_tested is False
        assert entry.monitoring_enabled is False


# ── MAS vendor risk ──────────────────────────────────────────────


class TestMASVendorRisk:
    def test_missing_pen_test_high_risk(self):
        eng = CrossBorderEngine()
        result = eng.check_mas_vendor_risk("VendorX", ["llm_api"])
        assert result.risk_rating == VendorRiskRating.HIGH

    def test_old_pen_test_high_risk(self):
        eng = CrossBorderEngine()
        old_date = datetime.now(timezone.utc) - timedelta(days=400)
        result = eng.check_mas_vendor_risk("VendorY", ["llm_api"], last_pen_test_date=old_date)
        assert result.risk_rating == VendorRiskRating.HIGH

    def test_recent_pen_test_no_access_controls_medium(self):
        eng = CrossBorderEngine()
        recent = datetime.now(timezone.utc) - timedelta(days=30)
        result = eng.check_mas_vendor_risk(
            "VendorZ", ["llm_api", "embedding"],
            last_pen_test_date=recent, access_controls_verified=False,
        )
        assert result.risk_rating == VendorRiskRating.MEDIUM

    def test_recent_pen_test_with_access_controls_low(self):
        eng = CrossBorderEngine()
        recent = datetime.now(timezone.utc) - timedelta(days=30)
        result = eng.check_mas_vendor_risk(
            "VendorA", ["llm_api"],
            last_pen_test_date=recent, access_controls_verified=True,
        )
        assert result.risk_rating == VendorRiskRating.LOW


# ── SG consent for AI decisions ──────────────────────────────────


class TestSGConsent:
    def test_ai_credit_decision_requires_consent(self):
        eng = CrossBorderEngine()
        assert eng.check_sg_consent_required("ai_credit_decision") is True

    def test_ai_insurance_decision_requires_consent(self):
        eng = CrossBorderEngine()
        assert eng.check_sg_consent_required("ai_insurance_decision") is True

    def test_general_analytics_no_consent(self):
        eng = CrossBorderEngine()
        assert eng.check_sg_consent_required("general_analytics") is False

    def test_reporting_no_consent(self):
        eng = CrossBorderEngine()
        assert eng.check_sg_consent_required("reporting") is False


# ── SG jurisdiction config — MAS flags ───────────────────────────


class TestSGJurisdictionMASFlags:
    def test_sg_has_trm_feat_airg_enabled(self):
        eng = CrossBorderEngine()
        cfg = eng.get_jurisdiction_config("SG")
        assert cfg.trm_enabled is True
        assert cfg.feat_enabled is True
        assert cfg.airg_enabled is True

    def test_us_has_trm_feat_airg_disabled(self):
        eng = CrossBorderEngine()
        cfg = eng.get_jurisdiction_config("US")
        assert cfg.trm_enabled is False
        assert cfg.feat_enabled is False
        assert cfg.airg_enabled is False

    def test_eu_has_trm_feat_airg_disabled(self):
        eng = CrossBorderEngine()
        cfg = eng.get_jurisdiction_config("EU")
        assert cfg.trm_enabled is False
        assert cfg.feat_enabled is False
        assert cfg.airg_enabled is False


# ══════════════════════════════════════════════════════════════════
# US SEC/FINRA Tests (~25 new tests)
# ══════════════════════════════════════════════════════════════════

# Load new US models
ComplianceDecision = _models.ComplianceDecision
RecordCategory = _models.RecordCategory
CommunicationType = _models.CommunicationType
ReviewType = _models.ReviewType


# ── Reg BI applicability ─────────────────────────────────────────


class TestRegBIApplicability:
    def test_bd_retail_applies(self):
        eng = CrossBorderEngine()
        assert eng.check_reg_bi_applicability("bd_only", "retail") is True

    def test_dual_registered_retail_applies(self):
        eng = CrossBorderEngine()
        assert eng.check_reg_bi_applicability("dual_registered", "retail") is True

    def test_ria_does_not_apply(self):
        eng = CrossBorderEngine()
        assert eng.check_reg_bi_applicability("ria_only", "retail") is False

    def test_institutional_does_not_apply(self):
        eng = CrossBorderEngine()
        assert eng.check_reg_bi_applicability("bd_only", "institutional") is False


# ── FINRA 2210 communication review ──────────────────────────────


class TestFINRA2210Review:
    def test_retail_pre_use_review(self):
        eng = CrossBorderEngine()
        result = eng.check_finra_2210_review_required("retail")
        assert result.review_type == ReviewType.PRE_USE
        assert result.principal_required is True
        assert result.filing_required is True

    def test_institutional_post_use_review(self):
        eng = CrossBorderEngine()
        result = eng.check_finra_2210_review_required("institutional")
        assert result.review_type == ReviewType.POST_USE
        assert result.principal_required is False

    def test_correspondence_spot_check(self):
        eng = CrossBorderEngine()
        result = eng.check_finra_2210_review_required("correspondence")
        assert result.review_type == ReviewType.SPOT_CHECK
        assert result.principal_required is False
        assert result.filing_required is False


# ── SEC 17a-4 retention ──────────────────────────────────────────


class TestSEC17a4Retention:
    def test_trade_blotter_6yr_worm(self):
        eng = CrossBorderEngine()
        result = eng.check_sec_17a4_retention("trade_blotter")
        assert result.retention_years == 6
        assert result.worm_required is True
        assert result.record_category == RecordCategory.TRADE_BLOTTER

    def test_correspondence_3yr(self):
        eng = CrossBorderEngine()
        result = eng.check_sec_17a4_retention("correspondence")
        assert result.retention_years == 3
        assert result.worm_required is False
        assert result.record_category == RecordCategory.CORRESPONDENCE

    def test_customer_complaint_4yr_worm(self):
        eng = CrossBorderEngine()
        result = eng.check_sec_17a4_retention("customer_complaint")
        assert result.retention_years == 4
        assert result.worm_required is True
        assert result.record_category == RecordCategory.CUSTOMER_COMPLAINT

    def test_unknown_record_type_fail_closed(self):
        """Unknown record types default to 6yr WORM (fail-closed)."""
        eng = CrossBorderEngine()
        result = eng.check_sec_17a4_retention("unknown_type")
        assert result.retention_years == 6
        assert result.worm_required is True


# ── SEC examination package ──────────────────────────────────────


class TestSECExaminationPackage:
    def test_package_generation(self):
        eng = CrossBorderEngine()
        pkg = eng.create_sec_examination_package("FIRM-001")
        assert pkg.firm_id == "FIRM-001"
        assert len(pkg.books_and_records) >= 5
        assert len(pkg.compliance_policies) >= 5
        assert "trade_blotter" in pkg.books_and_records
        assert "written_supervisory_procedures" in pkg.compliance_policies
        assert pkg.generated_at is not None


# ── FINRA restricted list ────────────────────────────────────────


class TestFINRARestrictedList:
    def test_restricted_security_blocked(self):
        eng = CrossBorderEngine()
        assert eng.check_finra_restricted_list("AAPL", ["AAPL", "MSFT"]) is True

    def test_unrestricted_security_allowed(self):
        eng = CrossBorderEngine()
        assert eng.check_finra_restricted_list("GOOG", ["AAPL", "MSFT"]) is False


# ── Concentration limits ─────────────────────────────────────────


class TestConcentrationLimits:
    def test_default_15pct_below_limit_allow(self):
        eng = CrossBorderEngine()
        result = eng.check_concentration_limit(10.0, "individual_taxable")
        assert result.decision == ComplianceDecision.ALLOW
        assert result.limit_pct == 15.0

    def test_default_15pct_above_limit_deny(self):
        eng = CrossBorderEngine()
        result = eng.check_concentration_limit(20.0, "individual_taxable")
        assert result.decision == ComplianceDecision.DENY

    def test_erisa_10pct_above_limit_deny(self):
        eng = CrossBorderEngine()
        result = eng.check_concentration_limit(12.0, "erisa_pension")
        assert result.decision == ComplianceDecision.DENY
        assert result.limit_pct == 10.0

    def test_erisa_401k_10pct_limit(self):
        eng = CrossBorderEngine()
        result = eng.check_concentration_limit(8.0, "401k")
        assert result.decision == ComplianceDecision.ALLOW
        assert result.limit_pct == 10.0


# ── Trading window ───────────────────────────────────────────────


class TestTradingWindow:
    def test_restricted_period_denied(self):
        eng = CrossBorderEngine()
        assert eng.check_trading_window("AAPL", True) is False

    def test_open_period_allowed(self):
        eng = CrossBorderEngine()
        assert eng.check_trading_window("AAPL", False) is True


# ── FINRA incident ───────────────────────────────────────────────


class TestFINRAIncident:
    def test_sar_30_day_deadline(self):
        eng = CrossBorderEngine()
        detected = datetime(2026, 7, 15, 10, 0, 0, tzinfo=timezone.utc)
        incident = eng.create_finra_incident("major", "Suspicious activity", detected_at=detected)
        assert incident.sar_filing_deadline == detected + timedelta(days=30)
        assert incident.incident_id.startswith("FINRA-")
        assert incident.finra_notified is False

    def test_complaint_ack_deadline(self):
        eng = CrossBorderEngine()
        detected = datetime(2026, 7, 15, 10, 0, 0, tzinfo=timezone.utc)
        incident = eng.create_finra_incident("significant", "Customer complaint", detected_at=detected)
        # 10 business days ≈ 14 calendar days
        assert incident.customer_complaint_ack_deadline == detected + timedelta(days=14)


# ── US suitability standard ──────────────────────────────────────


class TestUSSuitabilityStandard:
    def test_bd_reg_bi(self):
        eng = CrossBorderEngine()
        # Via base engine (jurisdiction-aware)
        result = eng.resolve_suitability_standard("US", "bd_only")
        assert result == SuitabilityStandard.REG_BI

    def test_ria_fiduciary(self):
        eng = CrossBorderEngine()
        result = eng.resolve_suitability_standard("US", "ria_only")
        assert result == SuitabilityStandard.FIDUCIARY

    def test_dual_registered_reg_bi(self):
        eng = CrossBorderEngine()
        result = eng.resolve_suitability_standard("US", "dual_registered")
        assert result == SuitabilityStandard.REG_BI


# ── US/SG engine independence ────────────────────────────────────


class TestEngineIndependence:
    def test_us_engine_does_not_affect_sg(self):
        """US engine operations must not contaminate SG engine state."""
        eng = CrossBorderEngine()
        # Register AI system via SG engine
        eng.register_ai_system("TestBot", "advisory", "high", "Alice")
        # US operations should not affect SG inventory
        pkg = eng.create_sec_examination_package("FIRM-001")
        assert pkg.firm_id == "FIRM-001"
        inventory = eng.get_ai_inventory()
        assert len(inventory) == 1
        assert inventory[0].system_name == "TestBot"

    def test_sg_engine_does_not_affect_us(self):
        """SG engine operations must not contaminate US engine results."""
        eng = CrossBorderEngine()
        # SG operation
        eng.create_mas_incident("major", "SG incident")
        # US operation should work independently
        result = eng.check_reg_bi_applicability("bd_only", "retail")
        assert result is True
