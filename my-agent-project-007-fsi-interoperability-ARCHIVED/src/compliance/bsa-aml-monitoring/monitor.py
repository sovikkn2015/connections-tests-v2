"""
Gap 4: BSA/AML Monitoring — BSAAMLMonitor service.

Deterministic detection of CTR thresholds, SAR patterns, sanctions hits,
and CDD refresh scheduling. Integrates with M2 (Authority Policy).

CRITICAL: All SAR alerts route to compliance_officer ONLY.
Anti-tipping-off: advisor and client NEVER notified (31 USC §5318(g)(2)).
All compliance records written to WORM storage (S3 Object Lock, 6-year retention).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

try:
    from .models import (
        CDD_REFRESH_MONTHS,
        DEFAULT_HIGH_RISK_COUNTRIES,
        AlertSeverity,
        AlertType,
        CDDRecord,
        CTRRecord,
        FilingStatus,
        SARAlert,
        SanctionsHit,
        SanctionsListSource,
        Transaction,
        TransactionType,
    )
except ImportError:
    from models import (
        CDD_REFRESH_MONTHS,
        DEFAULT_HIGH_RISK_COUNTRIES,
        AlertSeverity,
        AlertType,
        CDDRecord,
        CTRRecord,
        FilingStatus,
        SARAlert,
        SanctionsHit,
        SanctionsListSource,
        Transaction,
        TransactionType,
    )


# ── Thresholds (deterministic, per 31 CFR §1010.311) ────────────

CTR_THRESHOLD = 10_000.0
STRUCTURING_LOW = 8_000.0
STRUCTURING_HIGH = 10_000.0
STRUCTURING_MIN_COUNT = 3
STRUCTURING_WINDOW_DAYS = 5
STRUCTURING_TOTAL_MIN = 25_000.0
RAPID_MOVEMENT_MIN_IN = 50_000.0
RAPID_MOVEMENT_OUT_RATIO = 0.80
RAPID_MOVEMENT_WINDOW_DAYS = 3
GEOGRAPHIC_RISK_MIN = 5_000.0
UNUSUAL_VOLUME_MULTIPLIER = 3.0


def _filter_window(
    transactions: list[Transaction],
    reference: datetime,
    window_days: int,
) -> list[Transaction]:
    """Filter transactions within a rolling window ending at reference."""
    cutoff = reference - timedelta(days=window_days)
    return [t for t in transactions if t.timestamp >= cutoff]


class BSAAMLMonitor:
    """
    BSA/AML monitoring service — deterministic rule evaluation.

    All detection patterns are deterministic thresholds.
    No LLM is used for compliance decisions.
    SAR alerts always route to compliance_officer only.
    """

    # ── CTR checks ───────────────────────────────────────────────

    def check_ctr_threshold(self, transaction: Transaction) -> Optional[CTRRecord]:
        """
        Check single cash transaction against $10,000 CTR threshold.

        Per 31 CFR §1010.311: CTR required for cash transactions >$10,000.
        """
        if transaction.type != TransactionType.CASH:
            return None
        if transaction.amount <= CTR_THRESHOLD:
            return None
        return CTRRecord(
            client_id=transaction.client_id,
            amount=transaction.amount,
            aggregate_amount=transaction.amount,
            transaction_count=1,
            filing_status=FilingStatus.PENDING,
        )

    def check_aggregate_ctr(
        self,
        client_id: str,
        transactions: list[Transaction],
    ) -> Optional[CTRRecord]:
        """
        Check same-day aggregate cash transactions against $10,000 threshold.

        Multiple cash transactions by the same client on the same business
        day that aggregate >$10,000 require a CTR filing.
        """
        if not transactions:
            return None

        cash_txns = [
            t for t in transactions
            if t.type == TransactionType.CASH and t.client_id == client_id
        ]
        if not cash_txns:
            return None

        # Group by date
        by_date: dict[date, list[Transaction]] = {}
        for t in cash_txns:
            d = t.timestamp.date() if isinstance(t.timestamp, datetime) else t.timestamp
            by_date.setdefault(d, []).append(t)

        for day_date, day_txns in by_date.items():
            total = sum(t.amount for t in day_txns)
            if total > CTR_THRESHOLD:
                return CTRRecord(
                    client_id=client_id,
                    amount=max(t.amount for t in day_txns),
                    aggregate_amount=total,
                    transaction_count=len(day_txns),
                    filing_status=FilingStatus.PENDING,
                )
        return None

    # ── SAR pattern detection ────────────────────────────────────

    def detect_structuring(
        self,
        client_id: str,
        transactions: list[Transaction],
    ) -> Optional[SARAlert]:
        """
        Detect structuring: 3+ cash txns $8K-$10K in 5 days totaling >$25K.

        Structuring is deliberately breaking transactions into smaller
        amounts to evade CTR reporting requirements.
        """
        if not transactions:
            return None

        now = max(t.timestamp for t in transactions)
        window = _filter_window(transactions, now, STRUCTURING_WINDOW_DAYS)

        suspect = [
            t for t in window
            if t.client_id == client_id
            and t.type == TransactionType.CASH
            and STRUCTURING_LOW <= t.amount < STRUCTURING_HIGH
        ]

        if len(suspect) < STRUCTURING_MIN_COUNT:
            return None

        total = sum(t.amount for t in suspect)
        if total < STRUCTURING_TOTAL_MIN:
            return None

        return SARAlert(
            alert_type=AlertType.STRUCTURING,
            severity=AlertSeverity.HIGH,
            client_id=client_id,
            description=(
                f"Potential structuring: {len(suspect)} cash transactions "
                f"totaling ${total:,.0f} in {STRUCTURING_WINDOW_DAYS}-day window"
            ),
            route_to="compliance_officer",
            do_not_notify=["advisor", "client"],
        )

    def detect_rapid_movement(
        self,
        client_id: str,
        transactions: list[Transaction],
    ) -> Optional[SARAlert]:
        """
        Detect rapid fund movement: wire_in >$50K and wire_out >80% within 3 days.

        Funds flowing in and quickly out may indicate layering or
        pass-through money laundering.
        """
        if not transactions:
            return None

        now = max(t.timestamp for t in transactions)
        window = _filter_window(transactions, now, RAPID_MOVEMENT_WINDOW_DAYS)
        client_txns = [t for t in window if t.client_id == client_id]

        wire_in = sum(
            t.amount for t in client_txns if t.type == TransactionType.WIRE_IN
        )
        wire_out = sum(
            t.amount for t in client_txns if t.type == TransactionType.WIRE_OUT
        )

        if wire_in <= RAPID_MOVEMENT_MIN_IN:
            return None
        if wire_out <= wire_in * RAPID_MOVEMENT_OUT_RATIO:
            return None

        return SARAlert(
            alert_type=AlertType.RAPID_MOVEMENT,
            severity=AlertSeverity.HIGH,
            client_id=client_id,
            description=(
                f"Rapid fund movement: ${wire_in:,.0f} in, "
                f"${wire_out:,.0f} out within {RAPID_MOVEMENT_WINDOW_DAYS} days"
            ),
            route_to="compliance_officer",
            do_not_notify=["advisor", "client"],
        )

    def detect_geographic_risk(
        self,
        transaction: Transaction,
        high_risk_countries: Optional[frozenset[str]] = None,
    ) -> Optional[SARAlert]:
        """
        Detect geographic risk: wire to high-risk country >$5K.
        """
        countries = high_risk_countries or DEFAULT_HIGH_RISK_COUNTRIES

        if transaction.destination_country is None:
            return None
        if transaction.destination_country not in countries:
            return None
        if transaction.amount <= GEOGRAPHIC_RISK_MIN:
            return None

        return SARAlert(
            alert_type=AlertType.GEOGRAPHIC_RISK,
            severity=AlertSeverity.MEDIUM,
            client_id=transaction.client_id,
            description=(
                f"Wire of ${transaction.amount:,.0f} to high-risk "
                f"jurisdiction: {transaction.destination_country}"
            ),
            route_to="compliance_officer",
            do_not_notify=["advisor", "client"],
        )

    def detect_unusual_volume(
        self,
        client_id: str,
        transactions: list[Transaction],
        avg_monthly: float,
    ) -> Optional[SARAlert]:
        """
        Detect unusual volume: current month >3x average monthly volume.
        """
        if not transactions or avg_monthly <= 0:
            return None

        client_txns = [t for t in transactions if t.client_id == client_id]
        current_total = sum(t.amount for t in client_txns)

        if current_total <= avg_monthly * UNUSUAL_VOLUME_MULTIPLIER:
            return None

        return SARAlert(
            alert_type=AlertType.UNUSUAL_PATTERN,
            severity=AlertSeverity.MEDIUM,
            client_id=client_id,
            description=(
                f"Wire volume ${current_total:,.0f} exceeds "
                f"{UNUSUAL_VOLUME_MULTIPLIER:.0f}x monthly avg of ${avg_monthly:,.0f}"
            ),
            route_to="compliance_officer",
            do_not_notify=["advisor", "client"],
        )

    # ── Sanctions screening ──────────────────────────────────────

    def screen_sanctions(
        self,
        name: str,
        sanctions_list: dict[str, SanctionsListSource],
    ) -> Optional[SanctionsHit]:
        """
        Screen a name against sanctions lists (OFAC/EU/UN).

        Deterministic exact-match screening. Fuzzy matching would be
        a future enhancement with a dedicated screening vendor.
        """
        name_upper = name.strip().upper()
        for entity, source in sanctions_list.items():
            if entity.strip().upper() == name_upper:
                return SanctionsHit(
                    client_id=name,
                    matched_entity=entity,
                    list_source=source,
                    match_confidence=1.0,
                )
        return None

    # ── CDD refresh ──────────────────────────────────────────────

    def get_cdd_refresh_date(
        self,
        risk_rating: str,
        last_review: date,
    ) -> date:
        """
        Calculate next CDD review date based on risk tier.

        High risk: 12 months, Medium: 24 months, Low: 36 months.
        """
        months = CDD_REFRESH_MONTHS.get(risk_rating, 36)
        # Approximate months as 30 days each
        return last_review + timedelta(days=months * 30)
