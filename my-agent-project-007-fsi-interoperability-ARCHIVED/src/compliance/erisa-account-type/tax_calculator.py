"""
Gap 5: Deterministic Tax Impact Calculator.

Calculates capital gains (short/long term), wash sale detection,
and holding period analysis. 100% deterministic — NO LLM.

Sub-module of M2 (Authority Policy). No cross-module imports.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

try:
    from .models import (
        ACCOUNT_TAX_STATUS,
        CONCENTRATION_LIMITS,
        DEFAULT_CONCENTRATION_LIMIT,
        ERISA_GOVERNED_TYPES,
        AccountTypeCheckInput,
        AccountTypeCheckResult,
        CapitalGainsType,
        TaxImpact,
        TaxLot,
        TaxStatus,
    )
except ImportError:
    from models import (
        ACCOUNT_TAX_STATUS,
        CONCENTRATION_LIMITS,
        DEFAULT_CONCENTRATION_LIMIT,
        ERISA_GOVERNED_TYPES,
        AccountTypeCheckInput,
        AccountTypeCheckResult,
        CapitalGainsType,
        TaxImpact,
        TaxLot,
        TaxStatus,
    )

logger = logging.getLogger("compliance.erisa.tax")


class TaxCalculator:
    """
    Deterministic tax impact calculator for account-type-aware
    compliance. All calculations are pure functions — no external
    calls, no LLM, no side effects.
    """

    def calculate_sell_impact(
        self,
        account_type: str,
        tax_lots: list[TaxLot],
        current_price: float,
        sell_quantity: float,
    ) -> TaxImpact:
        """
        Calculate tax impact of selling shares.

        For tax-deferred/exempt accounts: no immediate tax impact.
        For taxable accounts: compute capital gains from tax lots.
        """
        tax_status = ACCOUNT_TAX_STATUS.get(account_type, TaxStatus.taxable)

        if tax_status == TaxStatus.tax_deferred:
            return TaxImpact(
                account_type=account_type,
                tax_status=tax_status,
                security_id=tax_lots[0].security_id if tax_lots else "",
                action="sell",
                quantity=sell_quantity,
                current_price=current_price,
                tax_deferred=True,
                summary=f"No immediate tax impact — {account_type} is tax-deferred",
            )

        if tax_status == TaxStatus.tax_exempt:
            return TaxImpact(
                account_type=account_type,
                tax_status=tax_status,
                security_id=tax_lots[0].security_id if tax_lots else "",
                action="sell",
                quantity=sell_quantity,
                current_price=current_price,
                tax_exempt=True,
                summary=f"No tax impact — {account_type} is tax-exempt",
            )

        # Taxable account — calculate capital gains using FIFO
        remaining = sell_quantity
        total_cost_basis = 0.0
        total_proceeds = 0.0
        earliest_acquisition = date.today()
        latest_acquisition = date.min

        sorted_lots = sorted(tax_lots, key=lambda t: t.acquisition_date)

        for lot in sorted_lots:
            if remaining <= 0:
                break
            shares_from_lot = min(remaining, lot.quantity)
            lot_cost = shares_from_lot * lot.cost_basis_per_share
            lot_proceeds = shares_from_lot * current_price
            total_cost_basis += lot_cost
            total_proceeds += lot_proceeds
            remaining -= shares_from_lot

            if lot.acquisition_date < earliest_acquisition:
                earliest_acquisition = lot.acquisition_date
            if lot.acquisition_date > latest_acquisition:
                latest_acquisition = lot.acquisition_date

        realized = total_proceeds - total_cost_basis
        holding_days = (date.today() - earliest_acquisition).days
        gains_type = (
            CapitalGainsType.long_term
            if holding_days > 365
            else CapitalGainsType.short_term
        )

        gain_label = "gain" if realized >= 0 else "loss"
        summary = (
            f"{'Long' if gains_type == CapitalGainsType.long_term else 'Short'}-term "
            f"capital {gain_label}: ${abs(realized):,.2f} "
            f"(cost basis ${total_cost_basis:,.2f}, proceeds ${total_proceeds:,.2f})"
        )

        return TaxImpact(
            account_type=account_type,
            tax_status=tax_status,
            security_id=tax_lots[0].security_id if tax_lots else "",
            action="sell",
            quantity=sell_quantity,
            current_price=current_price,
            capital_gains_type=gains_type,
            realized_gain_loss=round(realized, 2),
            cost_basis_used=round(total_cost_basis, 2),
            holding_period_days=holding_days,
            summary=summary,
        )

    def detect_wash_sale(
        self,
        security_id: str,
        sell_date: date,
        recent_purchases: list[TaxLot],
    ) -> tuple[bool, str]:
        """
        Detect wash sale risk: purchase of substantially identical
        security within 30 days before or after a sale at a loss.
        """
        window_start = sell_date - timedelta(days=30)
        window_end = sell_date + timedelta(days=30)

        for lot in recent_purchases:
            if lot.security_id == security_id:
                if window_start <= lot.acquisition_date <= window_end:
                    return True, (
                        f"Wash sale risk: {security_id} purchased on "
                        f"{lot.acquisition_date} is within 30-day window of sale"
                    )
        return False, ""

    def get_concentration_limit(self, account_type: str) -> float:
        """Get concentration limit for account type."""
        return CONCENTRATION_LIMITS.get(account_type, DEFAULT_CONCENTRATION_LIMIT)

    def is_erisa_governed(self, account_type: str) -> bool:
        """Check if account type is ERISA-governed."""
        return account_type in ERISA_GOVERNED_TYPES
