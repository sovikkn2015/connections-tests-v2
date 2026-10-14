"""
Gap 7: Cross-Border Regulatory — Pydantic v2 Models.

Jurisdiction-aware compliance overlays for multi-jurisdictional operations.
5 jurisdictions: US, EU, UK, SG, HK.
Overlay model: base US rules + jurisdiction-specific additions/overrides.

GDPR, MiFID II, DORA, FCA Consumer Duty, MAS, SFC.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Jurisdiction(str, Enum):
    """Supported jurisdictions per ARCH-06 §7."""
    US = "US"
    EU = "EU"
    UK = "UK"
    SG = "SG"
    HK = "HK"


class SuitabilityStandard(str, Enum):
    """Suitability standard per jurisdiction and registration type."""
    REG_BI = "reg_bi"
    FIDUCIARY = "fiduciary"
    MIFID2 = "mifid2"
    CONSUMER_DUTY = "consumer_duty"


class ConsentType(str, Enum):
    """Types of consent tracked for GDPR/UK GDPR."""
    LLM_PROCESSING = "llm_processing"
    CROSS_BORDER_TRANSFER = "cross_border_transfer"
    MARKETING = "marketing"


class DataCategory(str, Enum):
    """Data categories for erasure vs retention conflict resolution."""
    REGULATED_RECORD = "regulated_record"
    NON_REGULATED_PII = "non_regulated_pii"
    MEMORY = "memory"


class ErasureDecision(str, Enum):
    """Decision on GDPR erasure request."""
    DENY_ERASURE = "DENY_ERASURE"
    ALLOW_ERASURE = "ALLOW_ERASURE"


class IncidentSeverity(str, Enum):
    """DORA incident severity levels."""
    MAJOR = "major"
    SIGNIFICANT = "significant"
    MINOR = "minor"


class VendorCriticality(str, Enum):
    """ICT third-party criticality per DORA."""
    CRITICAL = "critical"
    IMPORTANT = "important"
    STANDARD = "standard"


class ConflictPriority(str, Enum):
    """Conflict resolution hierarchy per ARCH-06 §7.4."""
    SAFETY = "SAFETY"
    RETENTION = "RETENTION"
    PRIVACY = "PRIVACY"
    OPERATIONAL = "OPERATIONAL"


# ── Data residency mapping ───────────────────────────────────────

JURISDICTION_REGIONS: dict[str, str] = {
    "US": "us-east-1",
    "EU": "eu-central-1",
    "UK": "eu-west-2",
    "SG": "ap-southeast-1",
    "HK": "ap-east-1",
}


# ── Jurisdiction Config ──────────────────────────────────────────


class MaterialityLevel(str, Enum):
    """AIRG risk materiality levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FEATStatus(str, Enum):
    """FEAT assessment status values."""
    PASS = "pass"
    FAIL = "fail"
    PENDING = "pending"


class VendorRiskRating(str, Enum):
    """MAS TRM vendor risk rating."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class JurisdictionConfig(BaseModel):
    """Per-jurisdiction regulatory configuration."""
    jurisdiction: Jurisdiction
    regulator: str
    suitability_standard: SuitabilityStandard
    retention_years: int = 6
    worm_required: bool = True
    gdpr_enabled: bool = False
    dora_enabled: bool = False
    ai_act_enabled: bool = False
    trm_enabled: bool = False
    feat_enabled: bool = False
    airg_enabled: bool = False
    data_residency: str = "us-east-1"


# ── Default configs per jurisdiction ─────────────────────────────

DEFAULT_JURISDICTION_CONFIGS: dict[str, dict] = {
    "US": {
        "regulator": "FINRA/SEC",
        "suitability_standard": SuitabilityStandard.REG_BI,
        "retention_years": 6,
        "worm_required": True,
        "gdpr_enabled": False,
        "dora_enabled": False,
        "ai_act_enabled": False,
        "data_residency": "us-east-1",
    },
    "EU": {
        "regulator": "ESMA/NCA",
        "suitability_standard": SuitabilityStandard.MIFID2,
        "retention_years": 5,
        "worm_required": True,
        "gdpr_enabled": True,
        "dora_enabled": True,
        "ai_act_enabled": True,
        "data_residency": "eu-central-1",
    },
    "UK": {
        "regulator": "FCA",
        "suitability_standard": SuitabilityStandard.CONSUMER_DUTY,
        "retention_years": 5,
        "worm_required": True,
        "gdpr_enabled": True,
        "dora_enabled": False,
        "ai_act_enabled": False,
        "data_residency": "eu-west-2",
    },
    "SG": {
        "regulator": "MAS",
        "suitability_standard": SuitabilityStandard.FIDUCIARY,
        "retention_years": 5,
        "worm_required": True,
        "gdpr_enabled": False,
        "dora_enabled": False,
        "ai_act_enabled": False,
        "trm_enabled": True,
        "feat_enabled": True,
        "airg_enabled": True,
        "data_residency": "ap-southeast-1",
    },
    "HK": {
        "regulator": "SFC",
        "suitability_standard": SuitabilityStandard.FIDUCIARY,
        "retention_years": 7,
        "worm_required": True,
        "gdpr_enabled": False,
        "dora_enabled": False,
        "ai_act_enabled": False,
        "data_residency": "ap-east-1",
    },
}


# ── Consent Record ───────────────────────────────────────────────


class ConsentRecord(BaseModel):
    """Per-client consent record for GDPR/UK GDPR compliance."""
    client_id: str
    jurisdiction: Jurisdiction
    consent_type: ConsentType
    granted: bool
    granted_at: Optional[datetime] = None
    withdrawn_at: Optional[datetime] = None
    legal_basis: str = ""
    scc_reference: str = ""


# ── Erasure Request ──────────────────────────────────────────────


class ErasureRequest(BaseModel):
    """GDPR right-to-erasure request with retention conflict resolution."""
    client_id: str
    request_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    data_category: DataCategory
    decision: ErasureDecision
    reason: str
    erasure_deadline: Optional[datetime] = None


# ── DORA Incident ────────────────────────────────────────────────


class DORAIncident(BaseModel):
    """DORA ICT incident with regulatory notification deadlines."""
    incident_id: str
    severity: IncidentSeverity
    description: str
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    initial_notification_deadline: datetime  # 4 hours
    intermediate_deadline: datetime  # 72 hours
    final_deadline: datetime  # 30 days
    nca_notified: bool = False


# ── DPA Record ───────────────────────────────────────────────────


class DPARecord(BaseModel):
    """Data Processing Agreement tracking for GDPR Article 28."""
    vendor_name: str
    service_type: str
    dpa_signed: bool = False
    scc_required: bool = False
    sub_processors: list[str] = Field(default_factory=list)
    criticality: VendorCriticality = VendorCriticality.STANDARD


# ── Conflict Resolution ─────────────────────────────────────────


class ConflictResolution(BaseModel):
    """Resolution of cross-jurisdiction regulatory conflicts."""
    request_type: str
    jurisdictions: list[Jurisdiction]
    resolution: str
    legal_basis: str
    priority_applied: ConflictPriority


# ── MAS Incident (TRM) ──────────────────────────────────────────


class MASIncident(BaseModel):
    """MAS TRM ICT incident with 1-hour initial notification deadline.

    Stricter than DORA (4 hours). Per MAS Technology Risk Management
    Guidelines — significant incidents must be reported within 1 hour.
    """
    incident_id: str
    severity: IncidentSeverity
    description: str
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    initial_notification_deadline: datetime   # 1 hour (MAS TRM)
    intermediate_deadline: datetime            # 14 days
    final_deadline: datetime                   # 30 days
    mas_notified: bool = False


# ── FEAT Assessment ──────────────────────────────────────────────


class FEATAssessment(BaseModel):
    """MAS FEAT (Fairness, Ethics, Accountability, Transparency) assessment.

    Per Veritas Consortium principles. All four pillars must pass
    for overall compliance.
    """
    system_name: str
    fairness_score: float = Field(ge=0.0, le=1.0)
    fairness_status: FEATStatus = FEATStatus.PENDING
    ethics_review_status: FEATStatus = FEATStatus.PENDING
    accountability_owner: str = ""
    accountability_status: FEATStatus = FEATStatus.PENDING
    transparency_disclosed: bool = False
    transparency_status: FEATStatus = FEATStatus.PENDING
    overall_status: FEATStatus = FEATStatus.PENDING
    bias_test_date: Optional[datetime] = None
    bias_test_result: str = ""
    assessed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── AIRG Materiality Assessment ──────────────────────────────────


class AIRGMaterialityAssessment(BaseModel):
    """MAS AIRG risk materiality assessment per AI use case.

    Three dimensions: impact, complexity, reliance.
    Overall materiality derived from highest individual dimension.
    Controls required scale with materiality level.
    """
    use_case_name: str
    impact_level: MaterialityLevel
    complexity_level: MaterialityLevel
    reliance_level: MaterialityLevel
    overall_materiality: MaterialityLevel
    controls_required: list[str] = Field(default_factory=list)
    last_assessed: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── AIRG Inventory Entry ─────────────────────────────────────────


class AIRGInventoryEntry(BaseModel):
    """MAS AIRG AI system inventory entry.

    All AI systems must be registered with materiality assessment,
    deployment status, and monitoring configuration.
    """
    system_name: str
    description: str = ""
    use_case_category: str = ""
    materiality: MaterialityLevel = MaterialityLevel.LOW
    deployment_status: str = "registered"
    owner: str = ""
    last_review_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    pre_deployment_tested: bool = False
    monitoring_enabled: bool = False


# ── MAS Vendor Risk ──────────────────────────────────────────────


class MASVendorRisk(BaseModel):
    """MAS TRM third-party AI vendor risk assessment.

    Covers penetration testing, access controls, and overall risk rating.
    Annual pen test required per MAS TRM Guidelines.
    """
    vendor_name: str
    ai_services: list[str] = Field(default_factory=list)
    risk_rating: VendorRiskRating = VendorRiskRating.HIGH
    last_assessment_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    penetration_test_date: Optional[datetime] = None
    access_controls_verified: bool = False


# ══════════════════════════════════════════════════════════════════
# US SEC/FINRA Models
# ══════════════════════════════════════════════════════════════════


class ComplianceDecision(str, Enum):
    """Compliance check decision outcome."""
    ALLOW = "ALLOW"
    WARN = "WARN"
    DENY = "DENY"


class RecordCategory(str, Enum):
    """SEC Rule 17a-4 record categories."""
    TRADE_BLOTTER = "trade_blotter"
    ORDER_TICKET = "order_ticket"
    ACCOUNT_STATEMENT = "account_statement"
    CORRESPONDENCE = "correspondence"
    CUSTOMER_COMPLAINT = "customer_complaint"
    ADVERTISING = "advertising"


class CommunicationType(str, Enum):
    """FINRA Rule 2210 communication types."""
    RETAIL = "retail"
    INSTITUTIONAL = "institutional"
    CORRESPONDENCE = "correspondence"


class ReviewType(str, Enum):
    """FINRA 2210 principal review type."""
    PRE_USE = "pre_use"
    POST_USE = "post_use"
    SPOT_CHECK = "spot_check"
    NOT_REQUIRED = "not_required"


# ── SEC 17a-4 Retention Requirement ──────────────────────────────


class RetentionRequirement(BaseModel):
    """SEC Rule 17a-4 / FINRA Rule 4511 record retention requirement.

    Specifies retention period, WORM requirement, and legal basis
    per record category.
    """
    record_type: str
    retention_years: int
    worm_required: bool
    record_category: RecordCategory
    legal_basis: str


# ── SEC Examination Package ──────────────────────────────────────


class SECExaminationPackage(BaseModel):
    """SEC/FINRA examination support package.

    Pre-assembled documentation package for regulatory examinations.
    Contains books and records, compliance policies, trade blotters,
    customer complaints, advertising review logs, and supervisory
    procedures summary.
    """
    firm_id: str
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    books_and_records: list[str] = Field(default_factory=list)
    compliance_policies: list[str] = Field(default_factory=list)
    trade_blotter_summary: str = ""
    customer_complaints_summary: str = ""
    advertising_review_log: str = ""
    supervisory_procedures_summary: str = ""


# ── FINRA 2210 Review ────────────────────────────────────────────


class FINRA2210Review(BaseModel):
    """FINRA Rule 2210 communication review determination.

    Classifies communication type and determines required review level:
    - Retail: principal pre-use approval required
    - Institutional: post-use review sufficient
    - Correspondence: spot-check basis, no pre-approval
    """
    communication_type: CommunicationType
    audience: str
    review_type: ReviewType
    principal_required: bool
    filing_required: bool


# ── FINRA Incident ───────────────────────────────────────────────


class FINRAIncident(BaseModel):
    """FINRA regulatory incident with filing deadlines.

    SAR filing: 30 calendar days from detection.
    Customer complaint acknowledgment: 10 business days.
    """
    incident_id: str
    severity: IncidentSeverity
    description: str
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    sar_filing_deadline: datetime
    customer_complaint_ack_deadline: datetime
    finra_notified: bool = False


# ── Concentration Result ─────────────────────────────────────────


class ConcentrationResult(BaseModel):
    """Position concentration limit check result.

    Default limit: 15% of account value.
    ERISA accounts: 10% limit per DOL guidelines.
    """
    security_id: str
    position_pct: float
    limit_pct: float
    account_type: str
    decision: ComplianceDecision
    reason: str
