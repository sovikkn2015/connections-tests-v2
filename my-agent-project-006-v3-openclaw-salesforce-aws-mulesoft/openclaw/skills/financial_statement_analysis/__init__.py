"""financial_statement_analysis skill — deterministic XBRL math, no LLM."""

from .actions import FSAInput, FSAOutput, AnalysisType, run
from ._xbrl_parser import IncomeStatement, BalanceSheet, CashFlow
from . import _calculators as calc

__all__ = [
    "FSAInput",
    "FSAOutput",
    "AnalysisType",
    "IncomeStatement",
    "BalanceSheet",
    "CashFlow",
    "run",
    "calc",
]
