"""
Tests for Gap 5: ERISA Account-Type Compliance.

Covers: per-account-type rules, prohibited transaction detection,
concentration checks, tax calculator, wash sale detection.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from datetime import date, timedelta

_HERE = Path(__file__).resolve().parent


def _load_local(name: str):
    """Load a module from this directory by file path (avoids sys.path collisions)."""
    spec = importlib.util.spec_from_file_location(
        f"erisa_{name}", _HERE / f"{name}.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_models = _load_local("models")
# Register as bare 'models' so tax_calculator.py's fallback import finds the right one
sys.modules["models"] = _models
_tax = _load_local("tax_calculator")

ACCOUNT_TAX_STATUS = _models.ACCOUNT_TAX_STATUS
CONCENTRATION_LIMITS = _models.CONCENTRATION_LIMITS
DEFAULT_CONCENTRATION_LIMIT = _models.DEFAULT_CONCENTRATION_LIMIT
ERISA_GOVERNED_TYPES = _models.ERISA_GOVERNED_TYPES
AccountType = _models.AccountType
CapitalGainsType = _models.CapitalGainsType
CostBasisMethod = _models.CostBasisMethod
TaxLot = _models.TaxLot
TaxStatus = _models.TaxStatus
TaxCalculator = _tax.TaxCalculator


# ── Fixtures ─────────────────────────────────────────────────────


def _make_lot(
    security_id: str = "AAPL",
    quantity: float = 100,
    cost_basis_per_share: float = 150.0,
    days_ago: int = 400,
    method: CostBasisMethod = CostBasisMethod.fifo,
) -> TaxLot:
    return TaxLot(
        lot_id=f"lot-{security_id}-{days_ago}",
        security_id=security_id,
        quantity=quantity,
        cost_basis_per_share=cost_basis_per_share,
        cost_basis_method=method,
        acquisition_date=date.today() - timedelta(days=days_ago),
        source_custodian="schwab",
    )


# ── Account Type Metadata ────────────────────────────────────────


class TestAccountTypeMetadata:
    def test_all_16_account_types_have_tax_status(self):
        """All 16 account types must have a tax status mapping."""
        expected_types = {
            "individual_taxable", "joint_wros", "joint_tic",
            "joint_community_property", "traditional_ira", "roth_ira",
            "sep_ira", "simple_ira", "401k", "403b", "457b",
            "erisa_pension", "ugma", "utma", "trust_revocable",
            "trust_irrevocable", "estate",
        }
        for acct_type in expected_types:
            assert acct_type in ACCOUNT_TAX_STATUS, f"Missing tax status for {acct_type}"

    def test_erisa_governed_types(self):
        assert "401k" in ERISA_GOVERNED_TYPES
        assert "403b" in ERISA_GOVERNED_TYPES
        assert "erisa_pension" in ERISA_GOVERNED_TYPES
        assert "individual_taxable" not in ERISA_GOVERNED_TYPES

    def test_erisa_concentration_limit_is_10(self):
        for acct_type in ERISA_GOVERNED_TYPES:
            assert CONCENTRATION_LIMITS.get(acct_type, DEFAULT_CONCENTRATION_LIMIT) == 10.0

    def test_default_concentration_limit_is_15(self):
        assert DEFAULT_CONCENTRATION_LIMIT == 15.0

    def test_taxable_accounts(self):
        taxable = ["individual_taxable", "joint_wros", "ugma", "estate"]
        for acct in taxable:
            assert ACCOUNT_TAX_STATUS[acct] == TaxStatus.taxable

    def test_tax_deferred_accounts(self):
        deferred = ["traditional_ira", "401k", "403b", "erisa_pension"]
        for acct in deferred:
            assert ACCOUNT_TAX_STATUS[acct] == TaxStatus.tax_deferred

    def test_roth_is_tax_exempt(self):
        assert ACCOUNT_TAX_STATUS["roth_ira"] == TaxStatus.tax_exempt


# ── Tax Lot Model ────────────────────────────────────────────────


class TestTaxLot:
    def test_cost_basis_method_required(self):
        """cost_basis_method is NEVER null — steering rule 16."""
        lot = _make_lot()
        assert lot.cost_basis_method is not None
        assert lot.cost_basis_method == CostBasisMethod.fifo

    def test_total_cost_basis(self):
        lot = _make_lot(quantity=100, cost_basis_per_share=150.0)
        assert lot.total_cost_basis == 15000.0

    def test_holding_period(self):
        lot = _make_lot(days_ago=400)
        assert lot.holding_period_days >= 399
        assert lot.is_long_term is True

    def test_short_term_holding(self):
        lot = _make_lot(days_ago=100)
        assert lot.is_long_term is False

    def test_cost_basis_method_enum_values(self):
        for method in CostBasisMethod:
            lot = _make_lot(method=method)
            assert lot.cost_basis_method == method


# ── Tax Calculator ───────────────────────────────────────────────


class TestTaxCalculator:
    def setup_method(self):
        self.calc = TaxCalculator()

    def test_ira_no_immediate_tax(self):
        lots = [_make_lot()]
        impact = self.calc.calculate_sell_impact("traditional_ira", lots, 200.0, 50)
        assert impact.tax_deferred is True
        assert impact.realized_gain_loss == 0.0
        assert "tax-deferred" in impact.summary

    def test_401k_no_immediate_tax(self):
        lots = [_make_lot()]
        impact = self.calc.calculate_sell_impact("401k", lots, 200.0, 50)
        assert impact.tax_deferred is True

    def test_roth_no_tax(self):
        lots = [_make_lot()]
        impact = self.calc.calculate_sell_impact("roth_ira", lots, 200.0, 50)
        assert impact.tax_exempt is True
        assert "tax-exempt" in impact.summary

    def test_taxable_long_term_gain(self):
        lots = [_make_lot(days_ago=400, cost_basis_per_share=150.0)]
        impact = self.calc.calculate_sell_impact(
            "individual_taxable", lots, 200.0, 50,
        )
        assert impact.capital_gains_type == CapitalGainsType.long_term
        assert impact.realized_gain_loss == 2500.0
        assert "Long-term" in impact.summary

    def test_taxable_short_term_gain(self):
        lots = [_make_lot(days_ago=100, cost_basis_per_share=150.0)]
        impact = self.calc.calculate_sell_impact(
            "individual_taxable", lots, 200.0, 50,
        )
        assert impact.capital_gains_type == CapitalGainsType.short_term
        assert impact.realized_gain_loss == 2500.0

    def test_taxable_loss(self):
        lots = [_make_lot(days_ago=400, cost_basis_per_share=200.0)]
        impact = self.calc.calculate_sell_impact(
            "individual_taxable", lots, 150.0, 50,
        )
        assert impact.realized_gain_loss == -2500.0
        assert "loss" in impact.summary

    def test_multiple_lots_fifo(self):
        lots = [
            _make_lot(days_ago=400, cost_basis_per_share=100.0, quantity=30),
            _make_lot(days_ago=200, cost_basis_per_share=150.0, quantity=70),
        ]
        impact = self.calc.calculate_sell_impact(
            "individual_taxable", lots, 200.0, 50,
        )
        expected_cost = 30 * 100 + 20 * 150
        expected_proceeds = 50 * 200
        assert impact.realized_gain_loss == expected_proceeds - expected_cost

    def test_wash_sale_detected(self):
        recent = [_make_lot(days_ago=15, security_id="AAPL")]
        is_wash, reason = self.calc.detect_wash_sale(
            "AAPL", date.today(), recent,
        )
        assert is_wash is True
        assert "Wash sale risk" in reason

    def test_no_wash_sale_outside_window(self):
        recent = [_make_lot(days_ago=60, security_id="AAPL")]
        is_wash, reason = self.calc.detect_wash_sale(
            "AAPL", date.today(), recent,
        )
        assert is_wash is False

    def test_no_wash_sale_different_security(self):
        recent = [_make_lot(days_ago=15, security_id="MSFT")]
        is_wash, reason = self.calc.detect_wash_sale(
            "AAPL", date.today(), recent,
        )
        assert is_wash is False

    def test_erisa_concentration_limit(self):
        assert self.calc.get_concentration_limit("401k") == 10.0
        assert self.calc.get_concentration_limit("erisa_pension") == 10.0

    def test_default_concentration_limit(self):
        assert self.calc.get_concentration_limit("individual_taxable") == 15.0
        assert self.calc.get_concentration_limit("roth_ira") == 15.0

    def test_estate_concentration_limit(self):
        assert self.calc.get_concentration_limit("estate") == 10.0

    def test_erisa_governed(self):
        assert self.calc.is_erisa_governed("401k") is True
        assert self.calc.is_erisa_governed("erisa_pension") is True

    def test_not_erisa_governed(self):
        assert self.calc.is_erisa_governed("individual_taxable") is False
        assert self.calc.is_erisa_governed("roth_ira") is False
