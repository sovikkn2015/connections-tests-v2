"""XBRL parser.

Pulls structured financial facts out of an inline-XBRL 10-K / 10-Q. The goal
is NOT a full XBRL implementation - we want the five fact families the
financial-statement-analysis skill actually consumes:

    - revenue_by_period
    - net_income_by_period
    - total_assets / total_liabilities / stockholders_equity
    - operating_cash_flow
    - long_term_debt / short_term_debt

Everything else is ignored. This keeps the blast radius of XBRL schema
drift small.

This module does NOT call Bedrock or S3; it is pure in-memory parsing over
bytes passed in. Unit-testable without any AWS permissions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lxml import etree  # type: ignore[import-untyped]

# Canonical concept -> list of US-GAAP taxonomy tags that can carry the value.
CONCEPT_MAP: dict[str, list[str]] = {
    "revenue": [
        "us-gaap:Revenues",
        "us-gaap:SalesRevenueNet",
        "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
    ],
    "net_income": [
        "us-gaap:NetIncomeLoss",
        "us-gaap:ProfitLoss",
    ],
    "total_assets": ["us-gaap:Assets"],
    "total_liabilities": ["us-gaap:Liabilities"],
    "stockholders_equity": [
        "us-gaap:StockholdersEquity",
        "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "operating_cash_flow": [
        "us-gaap:NetCashProvidedByUsedInOperatingActivities",
    ],
    "long_term_debt": [
        "us-gaap:LongTermDebt",
        "us-gaap:LongTermDebtNoncurrent",
    ],
    "short_term_debt": [
        "us-gaap:ShortTermBorrowings",
        "us-gaap:LongTermDebtCurrent",
    ],
}


@dataclass(frozen=True)
class XbrlFact:
    concept: str
    value: float
    unit: str
    period_start: str | None
    period_end: str | None
    context_ref: str


def parse_xbrl(doc_bytes: bytes) -> dict[str, list[XbrlFact]]:
    """Parse inline-XBRL HTML or raw XBRL XML; return facts grouped by canonical concept.

    Accepts both:
      * inline-XBRL (xhtml with ix:nonFraction tags)
      * classic XBRL instance documents (us-gaap:* tags directly)

    Unknown tags are dropped silently; malformed numeric values are dropped
    with a best-effort skip so one bad filing does not poison the run.
    """
    try:
        root = etree.fromstring(doc_bytes, parser=etree.XMLParser(recover=True, huge_tree=True))
    except etree.XMLSyntaxError:
        return {}
    if root is None:
        return {}

    # Build context lookup: contextRef -> (period_start, period_end).
    contexts: dict[str, tuple[str | None, str | None]] = {}
    for ctx in root.iter():
        if etree.QName(ctx).localname != "context":
            continue
        cid = ctx.get("id") or ""
        start = _findtext(ctx, "startDate") or _findtext(ctx, "instant")
        end = _findtext(ctx, "endDate") or start
        contexts[cid] = (start, end)

    # Reverse the concept map for fast lookup.
    tag_to_concept: dict[str, str] = {}
    for canon, tags in CONCEPT_MAP.items():
        for t in tags:
            tag_to_concept[t] = canon

    facts: dict[str, list[XbrlFact]] = {k: [] for k in CONCEPT_MAP}
    for el in root.iter():
        tag = _normalize_tag(el)
        canon = tag_to_concept.get(tag)
        if not canon:
            # Inline XBRL wraps values in <ix:nonFraction name="us-gaap:..." />
            if etree.QName(el).localname == "nonFraction":
                name = el.get("name") or ""
                canon = tag_to_concept.get(name)
                if not canon:
                    continue
                tag = name
            else:
                continue
        try:
            raw = (el.text or "").strip().replace(",", "")
            if not raw:
                continue
            scale = int(el.get("scale") or "0")
            value = float(raw) * (10**scale)
        except (ValueError, TypeError):
            continue
        ctx_ref = el.get("contextRef") or ""
        start, end = contexts.get(ctx_ref, (None, None))
        unit = el.get("unitRef") or "USD"
        facts[canon].append(
            XbrlFact(
                concept=tag,
                value=value,
                unit=unit,
                period_start=start,
                period_end=end,
                context_ref=ctx_ref,
            )
        )
    return facts


def facts_summary(facts: dict[str, list[XbrlFact]]) -> dict[str, Any]:
    """Return a compact, chunker-friendly summary of parsed facts."""
    out: dict[str, Any] = {}
    for concept, fact_list in facts.items():
        if not fact_list:
            out[concept] = None
            continue
        # Most recent (by period_end) wins.
        latest = sorted(fact_list, key=lambda f: f.period_end or "")[-1]
        out[concept] = {
            "value": latest.value,
            "unit": latest.unit,
            "period_end": latest.period_end,
            "period_start": latest.period_start,
        }
    return out


def _normalize_tag(el) -> str:
    qn = etree.QName(el)
    # Rebuild tag as "prefix:localname" when ns looks like the US-GAAP ns.
    ns = qn.namespace or ""
    if "us-gaap" in ns.lower():
        return f"us-gaap:{qn.localname}"
    return qn.localname


def _findtext(el, localname: str) -> str | None:
    for child in el.iter():
        if etree.QName(child).localname == localname:
            return (child.text or "").strip() or None
    return None
