"""
Gap 7: Cross-Border Regulatory — USEngine (US SEC/FINRA-specific).

Comprehensive US regulatory support: Reg BI applicability, FINRA 2210
communication review, SEC 17a-4 retention, examination packages,
restricted list checks, concentration limits, trading windows,
and FINRA incident management.

All decisions are deterministic — no LLM used.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

try:
    from .models import (
        CommunicationType,
        ComplianceDecision,
        ConcentrationResult,
        FINRA2210Review,
        FINRAIncident,
        IncidentSeverity,
        RecordCategory,
        RetentionRequirement,
        ReviewType,
        SECExaminationPackage,
        SuitabilityStandard,
    )
except ImportError:
    from models import (
        CommunicationType,
        ComplianceDecision,
        ConcentrationResult,
        FINRA2210Review,
        FINRAIncident,
        IncidentSeverity,
        RecordCategory,
        RetentionRequirement,
        ReviewType,
        SECExaminationPackage,
        SuitabilityStandard,
    )


# ── SAR filing deadline (calendar days) ──────────────────────────

_SAR_FILING_DAYS = 30

# ── Customer complaint acknowledgment (business days ≈ calendar) ─

_COMPLAINT_ACK_BUSINESS_DAYS = 10
# Approximate business days as calendar days (10 biz ≈ 14 calendar)
_COMPLAINT_ACK_CALENDAR_DAYS = 14

# ── Concentration limits ─────────────────────────────────────────

_DEFAULT_CONCENTRATION_LIMIT_PCT = 15.0
_ERISA_CONCENTRATION_LIMIT_PCT = 10.0

# ── SEC 17a-4 retention schedule ─────────────────────────────────

_RETENTION_SCHEDULE: dict[str, dict] = {
    "trade_blotter": {
        "retention_years": 6,
        "worm_required": True,
        "record_category": RecordCategory.TRADE_BLOTTER,
        "legal_basis": "SEC Rule 17a-4(a)",
    },
    "order_ticket": {
        "retention_years": 6,
        "worm_required": True,
        "record_category": RecordCategory.ORDER_TICKET,
        "legal_basis": "SEC Rule 17a-4(a)",
    },
    "account_statement": {
        "retention_years": 6,
        "worm_required": True,
        "record_category": RecordCategory.ACCOUNT_STATEMENT,
        "legal_basis": "SEC Rule 17a-4(a)",
    },
    "correspondence": {
        "retention_years": 3,
        "worm_required": False,
        "record_category": RecordCategory.CORRESPONDENCE,
        "legal_basis": "SEC Rule 17a-4(b)(4)",
    },
    "customer_complaint": {
        "retention_years": 4,
        "worm_required": True,
        "record_category": RecordCategory.CUSTOMER_COMPLAINT,
        "legal_basis": "FINRA Rule 4513(a)",
    },
    "advertising": {
        "retention_years": 3,
        "worm_required": False,
        "record_category": RecordCategory.ADVERTISING,
        "legal_basis": "FINRA Rule 2210(b)(1)",
    },
}


class USEngine:
    """
    US SEC/FINRA-specific compliance engine.

    Covers Reg BI applicability, FINRA 2210 communication review,
    SEC 17a-4 retention, examination packages, restricted list,
    concentration limits, trading windows, and FINRA incidents.

    All decisions are deterministic — no LLM used.
    """

    # ── Suitability standard ─────────────────────────────────────

    def resolve_suitability_standard(
        self,
        registration_type: str = "bd_only",
    ) -> SuitabilityStandard:
        """Resolve US suitability standard by registration type.

        BD / dual-registered → Reg BI.
        RIA → Fiduciary duty.
        """
        if registration_type in ("ria_only", "ria"):
            return SuitabilityStandard.FIDUCIARY
        return SuitabilityStandard.REG_BI

    # ── Reg BI applicability ─────────────────────────────────────

    def check_reg_bi_applicability(
        self,
        registration_type: str,
        archetype: str = "retail",
    ) -> bool:
        """Check if Reg BI applies.

        Reg BI applies to BD and dual-registered firms serving retail
        customers only. Pure RIAs have fiduciary duty (not Reg BI).
        Institutional clients are excluded.
        """
        if archetype != "retail":
            return False
        if registration_type in ("ria_only", "ria"):
            return False
        return True

    # ── FINRA 2210 communication review ──────────────────────────

    def check_finra_2210_review_required(
        self,
        communication_type: str,
        audience: str = "retail",
    ) -> FINRA2210Review:
        """Determine FINRA 2210 review requirements.

        Retail communications: principal pre-use approval required.
        Institutional communications: post-use review sufficient.
        Correspondence: spot-check basis, no pre-approval needed.
        """
        ct = CommunicationType(communication_type)

        if ct == CommunicationType.RETAIL:
            return FINRA2210Review(
                communication_type=ct,
                audience=audience,
                review_type=ReviewType.PRE_USE,
                principal_required=True,
                filing_required=True,
            )

        if ct == CommunicationType.INSTITUTIONAL:
            return FINRA2210Review(
                communication_type=ct,
                audience=audience,
                review_type=ReviewType.POST_USE,
                principal_required=False,
                filing_required=False,
            )

        return FINRA2210Review(
            communication_type=ct,
            audience=audience,
            review_type=ReviewType.SPOT_CHECK,
            principal_required=False,
            filing_required=False,
        )

    # ── SEC 17a-4 retention ──────────────────────────────────────

    def check_sec_17a4_retention(
        self,
        record_type: str,
    ) -> RetentionRequirement:
        """Get SEC 17a-4 / FINRA 4511 retention requirement for a record type."""
        schedule = _RETENTION_SCHEDULE.get(record_type)
        if schedule is None:
            return RetentionRequirement(
                record_type=record_type,
                retention_years=6,
                worm_required=True,
                record_category=RecordCategory.TRADE_BLOTTER,
                legal_basis="SEC Rule 17a-4(a) — default (fail-closed)",
            )
        return RetentionRequirement(
            record_type=record_type,
            retention_years=schedule["retention_years"],
            worm_required=schedule["worm_required"],
            record_category=schedule["record_category"],
            legal_basis=schedule["legal_basis"],
        )

    # ── SEC examination package ──────────────────────────────────

    def create_sec_examination_package(
        self,
        firm_id: str,
    ) -> SECExaminationPackage:
        """Generate a pre-assembled SEC/FINRA examination support package."""
        return SECExaminationPackage(
            firm_id=firm_id,
            books_and_records=[
                "trade_blotter",
                "order_tickets",
                "account_statements",
                "customer_confirmations",
                "margin_records",
                "securities_record",
            ],
            compliance_policies=[
                "written_supervisory_procedures",
                "code_of_ethics",
                "insider_trading_policy",
                "business_continuity_plan",
                "anti_money_laundering_program",
                "customer_complaint_procedures",
            ],
            trade_blotter_summary="Trade blotter records available for examination period",
            customer_complaints_summary="Customer complaint log with resolution status",
            advertising_review_log="Principal-reviewed communications per FINRA 2210",
            supervisory_procedures_summary="WSP mapping to OPA/Rego rules per Gap 3",
        )

    # ── FINRA restricted list ────────────────────────────────────

    def check_finra_restricted_list(
        self,
        security_id: str,
        restricted_list: list[str],
    ) -> bool:
        """Check if a security is on the firm restricted list.

        Returns True if restricted (BLOCKED).
        """
        return security_id in restricted_list

    # ── Concentration limits ─────────────────────────────────────

    def check_concentration_limit(
        self,
        position_pct: float,
        account_type: str = "individual_taxable",
        security_id: str = "",
    ) -> ConcentrationResult:
        """Check position concentration against limits.

        Default: 15% of account value.
        ERISA accounts: 10% per DOL guidelines.
        """
        is_erisa = account_type.lower().startswith("erisa") or account_type in (
            "401k", "403b", "457b", "erisa_pension",
        )
        limit = _ERISA_CONCENTRATION_LIMIT_PCT if is_erisa else _DEFAULT_CONCENTRATION_LIMIT_PCT

        if position_pct > limit:
            decision = ComplianceDecision.DENY
            reason = (
                f"Position {position_pct:.1f}% exceeds "
                f"{limit:.0f}% concentration limit for {account_type}"
            )
        elif position_pct > limit * 0.8:
            decision = ComplianceDecision.WARN
            reason = (
                f"Position {position_pct:.1f}% approaching "
                f"{limit:.0f}% concentration limit for {account_type}"
            )
        else:
            decision = ComplianceDecision.ALLOW
            reason = f"Position {position_pct:.1f}% within {limit:.0f}% limit"

        return ConcentrationResult(
            security_id=security_id,
            position_pct=position_pct,
            limit_pct=limit,
            account_type=account_type,
            decision=decision,
            reason=reason,
        )

    # ── Trading window ───────────────────────────────────────────

    def check_trading_window(
        self,
        security_id: str,
        is_restricted_period: bool,
    ) -> bool:
        """Check if trading is allowed. Returns False during restricted periods."""
        return not is_restricted_period

    # ── FINRA incident management ────────────────────────────────

    def create_finra_incident(
        self,
        severity: str,
        description: str,
        detected_at: Optional[datetime] = None,
    ) -> FINRAIncident:
        """Create a FINRA incident with filing deadlines.

        SAR filing: 30 calendar days from detection.
        Customer complaint acknowledgment: 10 business days (~14 calendar).
        """
        sev = IncidentSeverity(severity)
        now = detected_at or datetime.now(timezone.utc)

        return FINRAIncident(
            incident_id=f"FINRA-{uuid.uuid4().hex[:8].upper()}",
            severity=sev,
            description=description,
            detected_at=now,
            sar_filing_deadline=now + timedelta(days=_SAR_FILING_DAYS),
            customer_complaint_ack_deadline=now + timedelta(days=_COMPLAINT_ACK_CALENDAR_DAYS),
            finra_notified=False,
        )
