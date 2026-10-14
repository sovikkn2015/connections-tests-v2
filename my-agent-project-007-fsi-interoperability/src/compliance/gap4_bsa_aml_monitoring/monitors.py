"""
Gap 4 — Deterministic CTR + SAR monitors.

CtrMonitor: 31 CFR §1010.311 — flag cash >= $10,000 single txn AND
            24h aggregate > $10,000.
SarStructuringMonitor: 31 CFR §1023.320 — flag 3+ cash deposits in
            $7,000-$9,999.99 range in 7-day rolling window.

All comparisons use Decimal to avoid float drift at the $10K boundary.
Fail-closed: caller misconfiguration -> empty tuple + no side effect.

See .kiro/specs/gap4-bsa-aml-monitoring.md R3.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Callable, Optional
from uuid import UUID, uuid4

from m5_config_loader import BsaAmlConfig

from compliance.gap4_bsa_aml_monitoring.models import (
    AlertSeverity,
    AlertType,
    BsaAmlAlert,
    CashTransaction,
    CashTransactionCategory,
    SAR_STRUCTURING_LOWER_USD_DEFAULT,
)
from compliance.gap4_bsa_aml_monitoring.window_store import WindowStore


# =============================================================================
# Helpers
# =============================================================================


_CASH_IN_OUT: frozenset[CashTransactionCategory] = frozenset(
    {
        CashTransactionCategory.cash_deposit,
        CashTransactionCategory.cash_withdrawal,
    }
)


def _decimal(value: float | int | Decimal) -> Decimal:
    """Normalize config thresholds (which may arrive as float) to Decimal."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _sum_amount(txns: tuple[CashTransaction, ...]) -> Decimal:
    total = Decimal("0")
    for t in txns:
        total += t.amount_usd
    return total


def _store_key(txn: CashTransaction) -> tuple[str, UUID]:
    return (txn.firm_id, txn.client_id)


# =============================================================================
# CTR Monitor (spec R3.1)
# =============================================================================


class CtrMonitor:
    """Currency Transaction Report threshold monitor.

    Single-transaction: cash deposit or withdrawal with
    amount_usd >= CTR threshold (default $10,000). The single
    comparison is >= (per 31 CFR §1010.311: the rule triggers AT the
    threshold).

    24h aggregate: sum of cash deposits/withdrawals for
    (firm_id, client_id) over (now - 24h, now] STRICTLY GREATER than
    the CTR threshold. The aggregate comparison is > (strict), so a
    single-txn $10,000 deposit emits the single-txn alert only, not
    an aggregate alert too (the aggregate equals the single-txn
    amount, which does not exceed the threshold).
    """

    RULE_ID: str = "authority/bsa_aml/ctr.v1"
    WSP_SECTION: str = "WSP-BSA-8.2"

    def __init__(
        self,
        *,
        store: WindowStore,
        config: Optional[BsaAmlConfig],
        clock: Callable[[], datetime],
    ) -> None:
        self._store = store
        self._config = config
        self._clock = clock

    def evaluate(
        self,
        txn: CashTransaction,
    ) -> tuple[BsaAmlAlert, ...]:
        """Evaluate `txn` against CTR threshold rules.

        Returns empty tuple if config is None or disabled (R6.1). Does
        NOT record the transaction — the orchestrator owns recording.
        """
        if self._config is None or not self._config.enabled:
            return ()
        if txn.category not in _CASH_IN_OUT:
            return ()

        threshold = _decimal(self._config.ctr_threshold)
        alerts: list[BsaAmlAlert] = []

        # R3.1 step 3: single-transaction check (>= threshold).
        if txn.amount_usd >= threshold:
            alerts.append(
                _build_alert(
                    txn=txn,
                    alert_type=AlertType.ctr_threshold,
                    severity=AlertSeverity.high,
                    threshold_type="ctr_single",
                    threshold_value=threshold,
                    matched_transactions=(txn.txn_id,),
                    matched_amount=txn.amount_usd,
                    rule_applied=self.RULE_ID,
                    wsp_section=self.WSP_SECTION,
                    reason_code="ctr_threshold_exceeded",
                    reason_detail="single cash transaction at or above CTR threshold",
                    detected_at=self._clock(),
                )
            )

        # R3.1 step 4: 24h rolling aggregate (> threshold, strict).
        window_start = txn.occurred_at - timedelta(hours=24)
        window_end = txn.occurred_at
        recent = self._store.within(
            _store_key(txn),
            start=window_start,
            end=window_end,
            categories=_CASH_IN_OUT,
        )
        # The store may or may not yet have `txn` (caller records
        # before OR after evaluate; we add the current txn explicitly
        # to make ordering independent).
        seen_ids = {t.txn_id for t in recent}
        all_txns = list(recent)
        if txn.txn_id not in seen_ids:
            all_txns.append(txn)
        total = _sum_amount(tuple(all_txns))

        if total > threshold:
            # Skip aggregate alert if the only txn is the current one
            # and it already triggered the single-txn alert. Otherwise
            # the signals are redundant.
            if not (len(all_txns) == 1 and alerts):
                matched_ids = tuple(t.txn_id for t in all_txns)
                alerts.append(
                    _build_alert(
                        txn=txn,
                        alert_type=AlertType.ctr_aggregate,
                        severity=AlertSeverity.high,
                        threshold_type="ctr_aggregate_24h",
                        threshold_value=threshold,
                        matched_transactions=matched_ids,
                        matched_amount=total,
                        rule_applied=self.RULE_ID,
                        wsp_section=self.WSP_SECTION,
                        reason_code="ctr_aggregate_exceeded",
                        reason_detail=(
                            "24h aggregate cash transactions exceed CTR threshold"
                        ),
                        detected_at=self._clock(),
                    )
                )

        return tuple(alerts)


# =============================================================================
# SAR Structuring Monitor (spec R3.2)
# =============================================================================


class SarStructuringMonitor:
    """SAR structuring detector.

    Pattern: 3 or more cash deposits/withdrawals in a 7-day rolling
    window where each amount is >= SAR lower bound AND < CTR
    threshold (exclusive on upper). Severity is critical — structuring
    is a felony under 31 U.S.C. §5324.

    The window is strictly 7 days prior (end-inclusive) using the
    WindowStore's half-open semantics: (now - 7d, now].
    """

    RULE_ID: str = "authority/bsa_aml/sar_structuring.v1"
    WSP_SECTION: str = "WSP-BSA-8.1"
    WINDOW_DAYS: int = 7
    MIN_OCCURRENCES: int = 3

    def __init__(
        self,
        *,
        store: WindowStore,
        config: Optional[BsaAmlConfig],
        clock: Callable[[], datetime],
    ) -> None:
        self._store = store
        self._config = config
        self._clock = clock

    def evaluate(
        self,
        txn: CashTransaction,
    ) -> tuple[BsaAmlAlert, ...]:
        if self._config is None or not self._config.enabled:
            return ()
        if txn.category not in _CASH_IN_OUT:
            return ()

        lower = _decimal(self._config.sar_structuring_threshold)
        upper = _decimal(self._config.ctr_threshold)
        # Sanity: if lower >= upper, the mid-band is empty → no alerts.
        if lower >= upper:
            return ()
        # The current txn must itself be in the mid-band — otherwise
        # it's either a CTR trigger (>= upper) or below the lower bound.
        if not (lower <= txn.amount_usd < upper):
            return ()

        window_start = txn.occurred_at - timedelta(days=self.WINDOW_DAYS)
        window_end = txn.occurred_at
        recent = self._store.within(
            _store_key(txn),
            start=window_start,
            end=window_end,
            categories=_CASH_IN_OUT,
        )
        # Include current txn if not already in store.
        seen_ids = {t.txn_id for t in recent}
        candidates: list[CashTransaction] = [
            t for t in recent if lower <= t.amount_usd < upper
        ]
        if txn.txn_id not in seen_ids:
            candidates.append(txn)

        if len(candidates) < self.MIN_OCCURRENCES:
            return ()

        total = _sum_amount(tuple(candidates))
        matched_ids = tuple(
            sorted({t.txn_id for t in candidates}, key=lambda u: str(u))
        )
        return (
            _build_alert(
                txn=txn,
                alert_type=AlertType.sar_structuring,
                severity=AlertSeverity.critical,
                threshold_type="sar_structuring_7d",
                threshold_value=lower,
                matched_transactions=matched_ids,
                matched_amount=total,
                rule_applied=self.RULE_ID,
                wsp_section=self.WSP_SECTION,
                reason_code="structuring_pattern_detected",
                reason_detail=(
                    "3+ mid-band cash transactions within 7 days "
                    "(structuring pattern — 31 USC 5324)"
                ),
                detected_at=self._clock(),
            ),
        )


# =============================================================================
# Alert builder (shared)
# =============================================================================


def _build_alert(
    *,
    txn: CashTransaction,
    alert_type: AlertType,
    severity: AlertSeverity,
    threshold_type: str,
    threshold_value: Decimal,
    matched_transactions: tuple[UUID, ...],
    matched_amount: Decimal,
    rule_applied: str,
    wsp_section: str,
    reason_code: str,
    reason_detail: str,
    detected_at: datetime,
) -> BsaAmlAlert:
    return BsaAmlAlert(
        alert_id=uuid4(),
        rule_id=rule_applied,
        alert_type=alert_type,
        severity=severity,
        client_id=txn.client_id,
        firm_id=txn.firm_id,
        threshold_type=threshold_type,
        threshold_value_usd=threshold_value,
        matched_transactions=matched_transactions,
        matched_amount_usd=matched_amount,
        wsp_section=wsp_section,
        rule_applied=rule_applied,
        route_to="compliance_officer",
        do_not_notify=("advisor", "client"),
        detected_at=detected_at,
        reason_code=reason_code,
        reason_detail=reason_detail,
    )


__all__ = [
    "CtrMonitor",
    "SarStructuringMonitor",
    "SAR_STRUCTURING_LOWER_USD_DEFAULT",
]
