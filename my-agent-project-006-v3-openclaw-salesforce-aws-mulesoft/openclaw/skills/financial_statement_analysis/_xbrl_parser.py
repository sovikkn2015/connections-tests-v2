"""XBRL -> canonical Pydantic statements.

Real XBRL is verbose and uses US-GAAP concept URIs. This parser accepts a
simplified facts dict (either from pre-parsed EDGAR facts or from the
sec-edgar MCP handler) and returns normalized Income/Balance/CashFlow models.

The sec-edgar MCP is the one place that parses raw XBRL; this module handles
the already-extracted facts dict so business logic doesn't re-implement XBRL.
"""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, Field


class IncomeStatement(BaseModel):
    """Canonical GAAP line items for revenue -> net income."""

    fiscal_period: str = Field(..., min_length=1, description="e.g. 2024-Q4, 2024-FY")
    revenue: float = Field(..., description="Top-line revenue, USD")
    cost_of_revenue: float = 0.0
    gross_profit: float = 0.0
    operating_expenses: float = 0.0
    operating_income: float = 0.0
    interest_expense: float = 0.0
    income_tax_expense: float = 0.0
    net_income: float = 0.0

    @property
    def gross_profit_computed(self) -> float:
        """Derived gross profit (revenue - COGS) if not explicitly reported."""
        return self.gross_profit or (self.revenue - self.cost_of_revenue)

    model_config = {"frozen": True}


class BalanceSheet(BaseModel):
    fiscal_period: str = Field(..., min_length=1)
    cash_and_equivalents: float = 0.0
    current_assets: float = 0.0
    total_assets: float = 0.0
    current_liabilities: float = 0.0
    long_term_debt: float = 0.0
    total_liabilities: float = 0.0
    total_equity: float = 0.0
    shares_outstanding: float = 0.0
    retained_earnings: float = 0.0

    model_config = {"frozen": True}


class CashFlow(BaseModel):
    fiscal_period: str = Field(..., min_length=1)
    operating_cash_flow: float = 0.0
    investing_cash_flow: float = 0.0
    financing_cash_flow: float = 0.0
    capex: float = 0.0
    free_cash_flow: float = 0.0
    model_config = {"frozen": True}


# GAAP concept -> canonical field mapping. Minimal but complete enough for V3.
_INCOME_MAP = {
    "us-gaap:Revenues": "revenue",
    "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
    "us-gaap:CostOfRevenue": "cost_of_revenue",
    "us-gaap:CostOfGoodsSold": "cost_of_revenue",
    "us-gaap:GrossProfit": "gross_profit",
    "us-gaap:OperatingExpenses": "operating_expenses",
    "us-gaap:OperatingIncomeLoss": "operating_income",
    "us-gaap:InterestExpense": "interest_expense",
    "us-gaap:IncomeTaxExpenseBenefit": "income_tax_expense",
    "us-gaap:NetIncomeLoss": "net_income",
}

_BALANCE_MAP = {
    "us-gaap:CashAndCashEquivalentsAtCarryingValue": "cash_and_equivalents",
    "us-gaap:AssetsCurrent": "current_assets",
    "us-gaap:Assets": "total_assets",
    "us-gaap:LiabilitiesCurrent": "current_liabilities",
    "us-gaap:LongTermDebt": "long_term_debt",
    "us-gaap:Liabilities": "total_liabilities",
    "us-gaap:StockholdersEquity": "total_equity",
    "us-gaap:CommonStockSharesOutstanding": "shares_outstanding",
    "us-gaap:RetainedEarningsAccumulatedDeficit": "retained_earnings",
}

_CASH_MAP = {
    "us-gaap:NetCashProvidedByUsedInOperatingActivities": "operating_cash_flow",
    "us-gaap:NetCashProvidedByUsedInInvestingActivities": "investing_cash_flow",
    "us-gaap:NetCashProvidedByUsedInFinancingActivities": "financing_cash_flow",
    "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment": "capex",
}


def _map_facts(
    facts: Dict[str, Any], mapping: Dict[str, str], period: str
) -> Dict[str, Any]:
    """Extract canonical values from a facts dict for one fiscal period."""
    out: Dict[str, Any] = {"fiscal_period": period}
    for concept, field in mapping.items():
        value = facts.get(concept)
        if isinstance(value, dict):
            value = value.get(period)
        if value is not None:
            out[field] = float(value)
    return out


def parse_income_statement(facts: Dict[str, Any], period: str) -> IncomeStatement:
    """Parse a pre-extracted facts dict into an IncomeStatement."""
    return IncomeStatement(**_map_facts(facts, _INCOME_MAP, period))


def parse_balance_sheet(facts: Dict[str, Any], period: str) -> BalanceSheet:
    return BalanceSheet(**_map_facts(facts, _BALANCE_MAP, period))


def parse_cash_flow(facts: Dict[str, Any], period: str) -> CashFlow:
    mapped = _map_facts(facts, _CASH_MAP, period)
    ocf = mapped.get("operating_cash_flow", 0.0)
    capex = mapped.get("capex", 0.0)
    mapped["free_cash_flow"] = ocf - capex
    return CashFlow(**mapped)
