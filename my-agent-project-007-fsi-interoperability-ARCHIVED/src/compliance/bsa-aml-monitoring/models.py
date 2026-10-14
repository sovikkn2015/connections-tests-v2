"""
Gap 4: BSA/AML Monitoring — Pydantic v2 Models.

Bank Secrecy Act / Anti-Money Laundering ongoing monitoring.
CTR ($10K+), SAR patterns, sanctions screening, anti-tipping-off.

CRITICAL: SAR alerts route to compliance_officer ONLY.
Anti-tipping-off: advisor and client NEVER notified (31 USC §5318(g)(2)).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TransactionType(str, Enum):
    """Transaction types for BSA/AML monitoring."""
    CASH = "cash"
    WIRE_IN = "wire_in"
    WIRE_OUT = "wire_out"
    ACH = "ach"
    CHECK = "check"


class AlertType(str, Enum):
    """SAR alert trigger types per ARCH-06 §4.3."""
    STRUCTURING = "STRUCTURING"
    RAPID_MOVEMENT = "RAPID_MOVEMENT"
    GEOGRAPHIC_RISK = "GEOGRAPHIC_RISK"
    UNUSUAL_PATTERN = "UNUSUAL_PATTERN"


class AlertSeverity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RiskRating(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FilingStatus(str, Enum):
    PENDING = "pending"
    FILED = "filed"
    NOT_REQUIRED = "not_required"


class SanctionsListSource(str, Enum):
    OFAC = "OFAC"
    EU = "EU"
    UN = "UN"


class AlertDecisionType(str, Enum):
    DISMISS = "dismiss"
    INVESTIGATE = "investigate"
    FILE_SAR = "file_sar"


# ── CDD refresh periods (months) ────────────────────────────────

CDD_REFRESH_MONTHS: dict[str, int] = {
    "high": 12,
    "medium": 24,
    "low": 36,
}

# ── High-risk jurisdictions (default list) ───────────────────────

DEFAULT_HIGH_RISK_COUNTRIES: frozenset[str] = frozenset({
    "IR", "KP", "MM", "SY", "YE", "AF", "LY", "SO", "SD", "VE",
})


# ── Transaction ──────────────────────────────────────────────────


class Transaction(BaseModel):
    """Single financial transaction for BSA/AML monitoring."""
    transaction_id: str = ""
    client_id: str
    amount: float
    type: TransactionType
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    destination_country: Optional[str] = None
    counterparty: str = ""


# ── SAR Alert ────────────────────────────────────────────────────


class SARAlert(BaseModel):
    """
    Suspicious Activity Report alert.

    CRITICAL: route_to is ALWAYS 'compliance_officer'.
    do_not_notify ALWAYS includes 'advisor' and 'client'.
    Anti-tipping-off: 31 USC §5318(g)(2) — violation is a felony.
    """
    alert_id: str = ""
    alert_type: AlertType
    severity: AlertSeverity
    client_id: str
    description: str
    route_to: str = Field(default="compliance_officer")
    do_not_notify: list[str] = Field(
        default_factory=lambda: ["advisor", "client"],
    )
    wsp_section: str = "WSP-8.1"
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── CTR Record ───────────────────────────────────────────────────


class CTRRecord(BaseModel):
    """Currency Transaction Report for cash transactions >$10,000."""
    client_id: str
    amount: float = 0.0
    aggregate_amount: float = 0.0
    transaction_count: int = 1
    filing_status: FilingStatus = FilingStatus.PENDING
    wsp_section: str = "WSP-8.2"
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Sanctions Hit ────────────────────────────────────────────────


class SanctionsHit(BaseModel):
    """Match against OFAC/EU/UN sanctions list."""
    client_id: str
    matched_entity: str
    list_source: SanctionsListSource
    match_confidence: float = 1.0
    wsp_section: str = "WSP-8.3"


# ── CDD Record ───────────────────────────────────────────────────


class CDDRecord(BaseModel):
    """Customer Due Diligence record for ongoing monitoring."""
    client_id: str
    risk_rating: RiskRating
    last_review_date: date
    next_review_date: date
    kyc_data_hash: str = ""


# ── Alert Decision ───────────────────────────────────────────────


class AlertDecision(BaseModel):
    """Compliance officer decision on a SAR alert."""
    alert_id: str
    decision: AlertDecisionType
    decided_by: str  # compliance officer ID only
    reason: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
