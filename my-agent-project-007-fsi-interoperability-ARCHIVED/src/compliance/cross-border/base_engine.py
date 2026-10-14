"""
Gap 7: Cross-Border Regulatory — BaseEngine (shared cross-jurisdiction logic).

Extracted from the monolithic CrossBorderEngine. Contains jurisdiction config,
data residency, consent management, erasure vs retention conflict resolution,
DORA incident management, and cross-jurisdiction conflict resolution.

All decisions are deterministic — no LLM used.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

try:
    from .models import (
        ConflictPriority,
        ConflictResolution,
        ConsentRecord,
        ConsentType,
        DORAIncident,
        DataCategory,
        DEFAULT_JURISDICTION_CONFIGS,
        ErasureDecision,
        ErasureRequest,
        IncidentSeverity,
        Jurisdiction,
        JURISDICTION_REGIONS,
        JurisdictionConfig,
        SuitabilityStandard,
    )
except ImportError:
    from models import (
        ConflictPriority,
        ConflictResolution,
        ConsentRecord,
        ConsentType,
        DORAIncident,
        DataCategory,
        DEFAULT_JURISDICTION_CONFIGS,
        ErasureDecision,
        ErasureRequest,
        IncidentSeverity,
        Jurisdiction,
        JURISDICTION_REGIONS,
        JurisdictionConfig,
        SuitabilityStandard,
    )


# ── Jurisdictions requiring consent for LLM processing ──────────

_LLM_CONSENT_REQUIRED: frozenset[str] = frozenset({"EU", "UK"})

# ── DORA deadline offsets ────────────────────────────────────────

_DORA_INITIAL_HOURS = 4
_DORA_INTERMEDIATE_HOURS = 72
_DORA_FINAL_DAYS = 30

# ── GDPR erasure deadline days ───────────────────────────────────

_ERASURE_DEADLINE_DAYS = 30


class BaseEngine:
    """
    Shared cross-jurisdiction compliance engine.

    Provides jurisdiction configuration, data residency routing,
    consent management, GDPR erasure vs retention conflict resolution,
    DORA incident management, and cross-jurisdiction conflict resolution.

    All decisions are deterministic — no LLM used.
    """

    def __init__(self) -> None:
        self._consents: dict[str, ConsentRecord] = {}

    # ── Jurisdiction config ──────────────────────────────────────

    def get_jurisdiction_config(self, jurisdiction: str) -> JurisdictionConfig:
        """Get regulatory configuration for a jurisdiction."""
        j = jurisdiction.upper()
        defaults = DEFAULT_JURISDICTION_CONFIGS.get(j)
        if defaults is None:
            raise ValueError(f"Unsupported jurisdiction: {jurisdiction}")
        return JurisdictionConfig(jurisdiction=Jurisdiction(j), **defaults)

    # ── Data residency ───────────────────────────────────────────

    def get_data_residency_region(self, jurisdiction: str) -> str:
        """Get the AWS region for data residency enforcement."""
        j = jurisdiction.upper()
        region = JURISDICTION_REGIONS.get(j)
        if region is None:
            raise ValueError(f"No data residency region for jurisdiction: {jurisdiction}")
        return region

    # ── Suitability standard ─────────────────────────────────────

    def resolve_suitability_standard(
        self,
        jurisdiction: str,
        registration_type: str = "bd_only",
    ) -> SuitabilityStandard:
        """Resolve the applicable suitability standard per jurisdiction."""
        j = jurisdiction.upper()
        if j == "US":
            if registration_type in ("ria_only", "ria"):
                return SuitabilityStandard.FIDUCIARY
            return SuitabilityStandard.REG_BI
        if j == "EU":
            return SuitabilityStandard.MIFID2
        if j == "UK":
            return SuitabilityStandard.CONSUMER_DUTY
        if j in ("SG", "HK"):
            return SuitabilityStandard.FIDUCIARY
        raise ValueError(f"Unsupported jurisdiction: {jurisdiction}")

    # ── Erasure vs retention ─────────────────────────────────────

    def resolve_erasure_vs_retention(
        self,
        data_category: str,
        jurisdiction: str,
    ) -> ErasureRequest:
        """Resolve GDPR erasure vs regulatory retention conflict."""
        cat = DataCategory(data_category)
        now = datetime.now(timezone.utc)

        if cat == DataCategory.REGULATED_RECORD:
            return ErasureRequest(
                client_id="",
                data_category=cat,
                decision=ErasureDecision.DENY_ERASURE,
                reason=(
                    "Record subject to regulatory retention "
                    "(17a-4/MiFID II). GDPR Article 17(3)(b) — legal obligation. "
                    "Marked for erasure after retention period expires."
                ),
            )
        deadline = now + timedelta(days=_ERASURE_DEADLINE_DAYS)
        return ErasureRequest(
            client_id="",
            data_category=cat,
            decision=ErasureDecision.ALLOW_ERASURE,
            reason=f"Erase from all systems within {_ERASURE_DEADLINE_DAYS} days",
            erasure_deadline=deadline,
        )

    # ── Consent management ───────────────────────────────────────

    def check_consent_required(
        self,
        jurisdiction: str,
        processing_type: str,
    ) -> bool:
        """Check if consent is required for a processing type in a jurisdiction."""
        j = jurisdiction.upper()
        if processing_type == ConsentType.LLM_PROCESSING or processing_type == "llm_processing":
            return j in _LLM_CONSENT_REQUIRED
        if processing_type == ConsentType.CROSS_BORDER_TRANSFER or processing_type == "cross_border_transfer":
            return j in _LLM_CONSENT_REQUIRED
        if processing_type == ConsentType.MARKETING or processing_type == "marketing":
            return True
        return False

    def record_consent(
        self,
        client_id: str,
        jurisdiction: str,
        consent_type: str,
        granted: bool,
    ) -> ConsentRecord:
        """Record a consent decision for a client."""
        j = Jurisdiction(jurisdiction.upper())
        ct = ConsentType(consent_type)
        now = datetime.now(timezone.utc)
        record = ConsentRecord(
            client_id=client_id,
            jurisdiction=j,
            consent_type=ct,
            granted=granted,
            granted_at=now if granted else None,
            legal_basis="consent" if granted else "withdrawn",
        )
        key = f"{client_id}:{j.value}:{ct.value}"
        self._consents[key] = record
        return record

    def check_consent(
        self,
        client_id: str,
        jurisdiction: str,
        consent_type: str,
    ) -> bool:
        """Check if a client has granted consent for a processing type."""
        j = jurisdiction.upper()
        key = f"{client_id}:{j}:{consent_type}"
        record = self._consents.get(key)
        if record is None:
            return False
        return record.granted and record.withdrawn_at is None

    def withdraw_consent(
        self,
        client_id: str,
        jurisdiction: str,
        consent_type: str,
    ) -> ConsentRecord:
        """Withdraw a previously granted consent."""
        j = Jurisdiction(jurisdiction.upper())
        ct = ConsentType(consent_type)
        key = f"{client_id}:{j.value}:{ct.value}"
        record = self._consents.get(key)
        now = datetime.now(timezone.utc)
        if record is None:
            record = ConsentRecord(
                client_id=client_id,
                jurisdiction=j,
                consent_type=ct,
                granted=False,
                withdrawn_at=now,
                legal_basis="withdrawn",
            )
        else:
            record.granted = False
            record.withdrawn_at = now
            record.legal_basis = "withdrawn"
        self._consents[key] = record
        return record

    # ── DORA incident management ─────────────────────────────────

    def create_dora_incident(
        self,
        severity: str,
        description: str,
        detected_at: Optional[datetime] = None,
    ) -> DORAIncident:
        """Create a DORA ICT incident with correct notification deadlines."""
        sev = IncidentSeverity(severity)
        now = detected_at or datetime.now(timezone.utc)
        return DORAIncident(
            incident_id=f"DORA-{uuid.uuid4().hex[:8].upper()}",
            severity=sev,
            description=description,
            detected_at=now,
            initial_notification_deadline=now + timedelta(hours=_DORA_INITIAL_HOURS),
            intermediate_deadline=now + timedelta(hours=_DORA_INTERMEDIATE_HOURS),
            final_deadline=now + timedelta(days=_DORA_FINAL_DAYS),
            nca_notified=False,
        )

    # ── Conflict resolution ──────────────────────────────────────

    def resolve_conflict(
        self,
        request_type: str,
        jurisdictions: list[str],
    ) -> ConflictResolution:
        """Resolve cross-jurisdiction regulatory conflicts.

        Hierarchy: SAFETY > RETENTION > PRIVACY > OPERATIONAL.
        """
        j_enums = [Jurisdiction(j.upper()) for j in jurisdictions]

        if request_type in ("gdpr_erasure", "erasure"):
            return ConflictResolution(
                request_type=request_type,
                jurisdictions=j_enums,
                resolution=(
                    "Regulated records retained per 17a-4/MiFID II. "
                    "Non-regulated PII erased within 30 days."
                ),
                legal_basis="GDPR Article 17(3)(b) — legal obligation",
                priority_applied=ConflictPriority.RETENTION,
            )

        if request_type in ("safety_block", "restricted_security", "sanctions"):
            return ConflictResolution(
                request_type=request_type,
                jurisdictions=j_enums,
                resolution="Blocked. Any jurisdiction block takes precedence.",
                legal_basis="Safety priority — most restrictive rule applies",
                priority_applied=ConflictPriority.SAFETY,
            )

        if request_type in ("data_collection", "data_minimization"):
            return ConflictResolution(
                request_type=request_type,
                jurisdictions=j_enums,
                resolution=(
                    "Collect minimum data required for compliance. "
                    "GDPR data minimization applies."
                ),
                legal_basis="GDPR Article 5(1)(c) — data minimization",
                priority_applied=ConflictPriority.PRIVACY,
            )

        if request_type in ("reporting", "best_execution", "transaction_reporting"):
            return ConflictResolution(
                request_type=request_type,
                jurisdictions=j_enums,
                resolution=(
                    "Generate ALL required reports for all applicable jurisdictions. "
                    "More reporting is preferred over less."
                ),
                legal_basis="Operational priority — comply with all jurisdictions",
                priority_applied=ConflictPriority.OPERATIONAL,
            )

        return ConflictResolution(
            request_type=request_type,
            jurisdictions=j_enums,
            resolution="Apply most restrictive rule across jurisdictions.",
            legal_basis="Default — most restrictive applies",
            priority_applied=ConflictPriority.OPERATIONAL,
        )
