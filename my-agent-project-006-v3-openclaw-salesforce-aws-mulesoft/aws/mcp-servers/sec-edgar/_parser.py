"""Structural parser for SEC EDGAR filings.

Extracts Item 1A (Risk Factors), Item 7 (MD&A), and financial statement
tables as structured Pydantic models. Works on 10-K / 10-Q HTML from
www.sec.gov/Archives/edgar/data/.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field


class FilingSection(BaseModel):
    item: str = Field(..., description="e.g. '1A' or '7'")
    title: str
    text: str


class StatementRow(BaseModel):
    label: str
    value: float | None = None
    unit: str = "USD"


class IncomeStatement(BaseModel):
    period: str = ""
    revenue: StatementRow | None = None
    cost_of_revenue: StatementRow | None = None
    gross_profit: StatementRow | None = None
    operating_income: StatementRow | None = None
    net_income: StatementRow | None = None
    eps_basic: StatementRow | None = None
    eps_diluted: StatementRow | None = None


class BalanceSheet(BaseModel):
    period: str = ""
    total_assets: StatementRow | None = None
    total_liabilities: StatementRow | None = None
    total_equity: StatementRow | None = None
    cash_and_equivalents: StatementRow | None = None
    long_term_debt: StatementRow | None = None


class CashFlow(BaseModel):
    period: str = ""
    operating_cash_flow: StatementRow | None = None
    investing_cash_flow: StatementRow | None = None
    financing_cash_flow: StatementRow | None = None
    free_cash_flow: StatementRow | None = None


class FinancialStatements(BaseModel):
    symbol: str
    period: str
    filing_type: str
    income_statement: IncomeStatement | None = None
    balance_sheet: BalanceSheet | None = None
    cash_flow: CashFlow | None = None


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_AMP_MAP = {
    "&nbsp;": " ", "&amp;": "&", "&quot;": '"', "&#39;": "'",
    "&lt;": "<", "&gt;": ">", "&mdash;": "—", "&ndash;": "–",
    "&rsquo;": "'", "&lsquo;": "'",
}


def strip_html(html: str) -> str:
    text = _TAG_RE.sub(" ", html)
    for k, v in _AMP_MAP.items():
        text = text.replace(k, v)
    return _WS_RE.sub(" ", text).strip()


def _item_start_regex(item_id: str) -> re.Pattern:
    pattern = rf"item[\s\u00A0\.]*{re.escape(item_id)}\b"
    return re.compile(pattern, re.IGNORECASE)


_NEXT_ITEMS = {
    "1A": ["1B", "2", "3"],
    "7": ["7A", "8"],
}


def extract_item(html_or_text: str, item_id: str, max_chars: int = 40_000) -> FilingSection | None:
    text = strip_html(html_or_text)

    start_re = _item_start_regex(item_id)
    m = start_re.search(text)
    if not m:
        return None

    start = m.start()
    end = len(text)
    for nxt in _NEXT_ITEMS.get(item_id, []):
        nm = _item_start_regex(nxt).search(text, pos=m.end())
        if nm and nm.start() < end:
            end = nm.start()

    chunk = text[start:end].strip()
    title_line = chunk[:120].split(".")[0].strip()

    if len(chunk) > max_chars:
        chunk = chunk[:max_chars] + "…[truncated]"

    return FilingSection(item=item_id, title=title_line or f"Item {item_id}", text=chunk)


_NUMERIC_RE = re.compile(r"\$?\s*([\(\-]?[\d,]+(?:\.\d+)?)[\)]?")


def _to_float(s: str | None) -> float | None:
    if not s:
        return None
    clean = s.replace(",", "").replace("$", "").strip()
    neg = False
    if clean.startswith("(") and clean.endswith(")"):
        neg = True
        clean = clean[1:-1]
    try:
        v = float(clean)
        return -v if neg else v
    except ValueError:
        return None


def _find_row(text: str, labels: list[str]) -> float | None:
    lc = text.lower()
    for label in labels:
        idx = lc.find(label.lower())
        if idx < 0:
            continue
        window = text[idx : idx + 200]
        m = _NUMERIC_RE.search(window[len(label):])
        if m:
            val = _to_float(m.group(1))
            if val is not None:
                return val
    return None


def _row(label: str, value: float | None, unit: str = "USD") -> StatementRow | None:
    if value is None:
        return None
    return StatementRow(label=label, value=value, unit=unit)


def extract_financials(
    html_or_text: str, symbol: str, filing_type: str, period: str
) -> FinancialStatements:
    text = strip_html(html_or_text)

    income = IncomeStatement(
        period=period,
        revenue=_row("Revenue", _find_row(text, ["Total revenues", "Total revenue", "Net revenues", "Revenue"])),
        cost_of_revenue=_row("Cost of revenue", _find_row(text, ["Cost of revenue", "Cost of sales"])),
        gross_profit=_row("Gross profit", _find_row(text, ["Gross profit", "Gross margin"])),
        operating_income=_row("Operating income", _find_row(text, ["Operating income", "Income from operations"])),
        net_income=_row("Net income", _find_row(text, ["Net income", "Net earnings"])),
        eps_basic=_row("EPS basic", _find_row(text, ["Earnings per share - basic", "Basic earnings per share"]), unit="USD/share"),
        eps_diluted=_row("EPS diluted", _find_row(text, ["Earnings per share - diluted", "Diluted earnings per share"]), unit="USD/share"),
    )
    bal = BalanceSheet(
        period=period,
        total_assets=_row("Total assets", _find_row(text, ["Total assets"])),
        total_liabilities=_row("Total liabilities", _find_row(text, ["Total liabilities"])),
        total_equity=_row("Total equity", _find_row(text, ["Total stockholders' equity", "Total equity"])),
        cash_and_equivalents=_row("Cash", _find_row(text, ["Cash and cash equivalents", "Cash and equivalents"])),
        long_term_debt=_row("Long-term debt", _find_row(text, ["Long-term debt"])),
    )
    cf = CashFlow(
        period=period,
        operating_cash_flow=_row("Operating cash flow", _find_row(text, ["Net cash provided by operating activities"])),
        investing_cash_flow=_row("Investing cash flow", _find_row(text, ["Net cash used in investing activities", "Net cash provided by investing activities"])),
        financing_cash_flow=_row("Financing cash flow", _find_row(text, ["Net cash used in financing activities", "Net cash provided by financing activities"])),
        free_cash_flow=None,
    )

    return FinancialStatements(
        symbol=symbol,
        period=period,
        filing_type=filing_type,
        income_statement=income,
        balance_sheet=bal,
        cash_flow=cf,
    )


def parse_latest_filing_meta(json_payload: dict[str, Any], filing_type: str) -> dict | None:
    """Given the EDGAR submissions JSON, return the newest filing of the given type."""
    recent = json_payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", []) or []
    dates = recent.get("filingDate", []) or []
    accession = recent.get("accessionNumber", []) or []
    primary_docs = recent.get("primaryDocument", []) or []

    for i, form in enumerate(forms):
        if form.upper() == filing_type.upper():
            return {
                "form": form,
                "filingDate": dates[i] if i < len(dates) else None,
                "accessionNumber": accession[i] if i < len(accession) else None,
                "primaryDocument": primary_docs[i] if i < len(primary_docs) else None,
            }
    return None
