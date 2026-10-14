"""
Gap 4 — Pydantic v2 models.

CashTransaction (normalized input), BsaAmlAlert (output),
TransactionType adapter from M3 Transaction. All frozen, extra='forbid'.
Decimal amounts (no float drift). Anti-tipping-off invariants
enforced at construction.

See .kiro/specs/gap4-bsa-aml-monitoring.md R1-R2.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from m3_schema_registry import Transaction, TransactionType


# =============================================================================
# Thresholds (spec R1.3)
# =============================================================================

CTR_THRESHOLD_USD_DEFAULT: Decimal = Decimal("10000.00")
SAR_STRUCTURING_UPPER_USD_DEFAULT: Decimal = Decimal("10000.00")
SAR_STRUCTURING_LOWER_USD_DEFAULT: Decimal = Decimal("7000.00")


# =============================================================================
# Enums (spec R1.1, R2.1, R2.2)
# =============================================================================


class CashTransactionCategory(str, Enum):
    cash_deposit = "cash_deposit"
    cash_withdrawal = "cash_withdrawal"
    wire_in = "wire_in"
    wire_out = "wire_out"


class AlertSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AlertType(str, Enum):
    ctr_threshold = "ctr_threshold"
    ctr_aggregate = "ctr_aggregate"
    sar_structuring = "sar_structuring"


# =============================================================================
# Regex constants — coupled to M2 for wsp_section and rule_applied.
# =============================================================================

# Same pattern as M2's WSP_SECTION_RE + RULE_APPLIED_RE. Duplicated
# locally to keep the module boundary tight; T4.26/T4.35 assert the
# values match M2's.
_WSP_SECTION_RE: re.Pattern[str] = re.compile(r"^WSP-[A-Z]+-\d+(\.\d+)?$")
_RULE_APPLIED_RE: re.Pattern[str] = re.compile(
    r"^(authority|mnpi)/[a-z_]+/[a-z_]+\.v\d+$"
)
_REASON_CODE_RE: re.Pattern[str] = re.compile(r"^[a-z_]+$")
_THRESHOLD_TYPE_RE: re.Pattern[str] = re.compile(r"^[a-z_0-9]+$")

# =============================================================================
# PII regex set for alert reason_detail (spec R9.1).
# =============================================================================

_PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("account_number", re.compile(r"\b\d{12,}\b")),
    ("email", re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    )),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")),
)


def _reject_pii(value: str, field_name: str) -> str:
    for code, pattern in _PII_PATTERNS:
        if pattern.search(value):
            raise ValueError(
                f"{field_name} contains potential PII pattern: {code}"
            )
    return value


# =============================================================================
# Frozen reason vocabulary (spec R2.4)
# =============================================================================

ALERT_REASONS: frozenset[str] = frozenset(
    {
        "ctr_threshold_exceeded",
        "ctr_aggregate_exceeded",
        "structuring_pattern_detected",
    }
)


# =============================================================================
# Exceptions
# =============================================================================


class NotACashTransactionError(ValueError):
    """Raised by `CashTransaction.from_m3` when the M3 Transaction is
    not a cash-equivalent transaction (e.g., BUY / SELL). Caller
    should skip such transactions — they do not hit Gap 4."""


# =============================================================================
# CashTransaction (spec R1)
# =============================================================================

_M3_TO_CATEGORY: dict[TransactionType, CashTransactionCategory] = {
    TransactionType.WIRE_IN: CashTransactionCategory.wire_in,
    TransactionType.WIRE_OUT: CashTransactionCategory.wire_out,
}


class CashTransaction(BaseModel):
    """Normalized post-trade cash transaction. Frozen. Decimal amount."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    txn_id: UUID
    client_id: UUID
    account_id: UUID
    category: CashTransactionCategory
    amount_usd: Decimal = Field(gt=Decimal("0"), le=Decimal("1000000000000"))
    occurred_at: datetime
    firm_id: str = Field(min_length=1, max_length=100)
    source_txn_ref: str = Field(min_length=1, max_length=200)
    trace_id: str = Field(min_length=1, max_length=200)

    @field_validator("occurred_at")
    @classmethod
    def _require_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        return v.astimezone(timezone.utc)

    # -------------------------------------------------------------------------
    # Adapter from M3 Transaction (spec R1.4)
    # -------------------------------------------------------------------------

    @classmethod
    def from_m3(cls, txn: Transaction) -> "CashTransaction":
        """Convert an M3 Transaction to a CashTransaction.

        Raises:
            NotACashTransactionError: txn is not a cash-equivalent type.
        """
        if not isinstance(txn, Transaction):
            raise TypeError("txn must be m3_schema_registry.Transaction")

        category: CashTransactionCategory
        if txn.transaction_type in _M3_TO_CATEGORY:
            category = _M3_TO_CATEGORY[txn.transaction_type]
        elif (
            txn.transaction_type == TransactionType.CONTRIBUTION
            and (txn.source_transaction_type or "").lower() == "cash_deposit"
        ):
            category = CashTransactionCategory.cash_deposit
        elif (
            txn.transaction_type == TransactionType.DISTRIBUTION
            and (txn.source_transaction_type or "").lower() == "cash_withdrawal"
        ):
            category = CashTransactionCategory.cash_withdrawal
        else:
            raise NotACashTransactionError(
                f"transaction_type {txn.transaction_type.value!r} is not "
                f"a cash-equivalent for BSA/AML monitoring"
            )

        # Convert M3's float amount to Decimal via string to avoid
        # float drift at the $10,000 boundary.
        amount = Decimal(str(abs(txn.amount)))
        occurred_at = (
            txn.created_at
            if isinstance(txn.created_at, datetime)
            else datetime.combine(txn.trade_date, datetime.min.time(), tzinfo=timezone.utc)
        )
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)

        # firm_id + trace_id must be supplied by the caller context in
        # real wiring; in this adapter we fall back to trace_id from the
        # Transaction and require a firm_id caller-side. Since M3 does
        # not carry firm_id directly, we use source_system.
        trace_id = txn.trace_id or "unknown-trace"
        firm_id = txn.source_system  # best-available multi-tenant anchor

        return cls(
            txn_id=txn.transaction_id,
            client_id=txn.client_ref or txn.account_ref,
            account_id=txn.account_ref,
            category=category,
            amount_usd=amount,
            occurred_at=occurred_at,
            firm_id=firm_id,
            source_txn_ref=txn.source_id,
            trace_id=trace_id,
        )


# =============================================================================
# BsaAmlAlert (spec R2)
# =============================================================================


class BsaAmlAlert(BaseModel):
    """Immutable BSA/AML alert. Routes to compliance officer ONLY.

    Anti-tipping-off invariants (31 U.S.C. §5318(g)(2)):
      - route_to is Literal["compliance_officer"] — type-enforced.
      - "advisor" and "client" MUST be in do_not_notify.
      - action string in the downstream AuditEntry is uniform across
        all alert types so log observers cannot infer a SAR is
        imminent.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    alert_id: UUID
    rule_id: str = Field(min_length=1, max_length=120)
    alert_type: AlertType
    severity: AlertSeverity
    client_id: UUID
    firm_id: str = Field(min_length=1, max_length=100)
    threshold_type: str = Field(min_length=1, max_length=80)
    threshold_value_usd: Decimal = Field(ge=Decimal("0"))
    matched_transactions: tuple[UUID, ...] = Field(min_length=1)
    matched_amount_usd: Decimal = Field(gt=Decimal("0"))
    wsp_section: str = Field(min_length=1, max_length=40)
    rule_applied: str = Field(min_length=1, max_length=120)
    route_to: Literal["compliance_officer"]
    do_not_notify: tuple[str, ...] = Field(min_length=2)
    detected_at: datetime
    reason_code: str = Field(min_length=1, max_length=80)
    reason_detail: str = Field(max_length=500)

    @field_validator("rule_id", "rule_applied")
    @classmethod
    def _validate_rule(cls, v: str) -> str:
        if not _RULE_APPLIED_RE.match(v):
            raise ValueError(
                f"rule identifier {v!r} does not match RULE_APPLIED_RE"
            )
        return v

    @field_validator("wsp_section")
    @classmethod
    def _validate_wsp(cls, v: str) -> str:
        if not _WSP_SECTION_RE.match(v):
            raise ValueError(
                f"wsp_section {v!r} does not match WSP_SECTION_RE"
            )
        return v

    @field_validator("threshold_type")
    @classmethod
    def _validate_threshold_type(cls, v: str) -> str:
        if not _THRESHOLD_TYPE_RE.match(v):
            raise ValueError(
                f"threshold_type {v!r} must be lowercase snake_case"
            )
        return v

    @field_validator("reason_code")
    @classmethod
    def _validate_reason_code(cls, v: str) -> str:
        if v not in ALERT_REASONS:
            raise ValueError(
                f"reason_code {v!r} not in ALERT_REASONS vocabulary"
            )
        if not _REASON_CODE_RE.match(v):
            raise ValueError(
                f"reason_code {v!r} must be lowercase snake_case"
            )
        return v

    @field_validator("reason_detail")
    @classmethod
    def _validate_reason_detail(cls, v: str) -> str:
        return _reject_pii(v, "reason_detail")

    @field_validator("detected_at")
    @classmethod
    def _require_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("detected_at must be timezone-aware")
        return v.astimezone(timezone.utc)

    @field_validator("matched_transactions")
    @classmethod
    def _validate_matched_unique(
        cls, v: tuple[UUID, ...]
    ) -> tuple[UUID, ...]:
        if len(v) != len(set(v)):
            raise ValueError("matched_transactions elements must be unique")
        return v

    @model_validator(mode="after")
    def _anti_tipping_off_invariants(self) -> "BsaAmlAlert":
        # route_to is Literal; already type-enforced. Belt-and-braces:
        if self.route_to != "compliance_officer":  # pragma: no cover
            raise ValueError(
                "route_to must be compliance_officer (anti-tipping-off)"
            )
        if "advisor" not in self.do_not_notify:
            raise ValueError(
                "do_not_notify must contain 'advisor' (31 USC 5318(g)(2))"
            )
        if "client" not in self.do_not_notify:
            raise ValueError(
                "do_not_notify must contain 'client' (31 USC 5318(g)(2))"
            )
        return self
