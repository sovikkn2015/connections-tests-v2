"""
MNPI Field Filter — strips Material Non-Public Information fields from SOQL results.

Security Finding #7: MNPI enforcement must be code, not documentation.
Architecture Rule 26: MNPI fields NEVER sent to LLM prompts or stored in OpenClaw memory.

This module provides two functions:
  - filter_mnpi(): removes MNPI fields from raw SOQL record lists
  - summarize_holdings_safe(): creates an LLM-safe holdings summary (no amounts)
"""

from __future__ import annotations

import copy
import logging
from typing import Any

logger = logging.getLogger("mnpi-filter")

# ── Fields that must NEVER reach LLM prompts or OpenClaw memory ─────
MNPI_FIELDS: set[str] = {
    "FinServ__Shares__c",
    "FinServ__MarketValue__c",
    "FinServ__Price__c",
    "Amount",
    "Balance__c",
    "Trade_Amount__c",
    "Wire_Amount__c",
    "Position_Size__c",
}


def filter_mnpi(records: list[dict]) -> list[dict]:
    """
    Strip MNPI fields from SOQL result records.

    Parameters
    ----------
    records : list[dict]
        Raw Salesforce SOQL query result records.

    Returns
    -------
    list[dict]
        Deep-copied records with all MNPI_FIELDS removed.
    """
    if not records:
        return []

    filtered: list[dict] = []
    stripped_count = 0

    for record in records:
        try:
            clean = copy.deepcopy(record)
            for field in MNPI_FIELDS:
                if field in clean:
                    del clean[field]
                    stripped_count += 1
            filtered.append(clean)
        except Exception as exc:
            logger.warning("MNPI filter error on record: %s", exc)
            # Return a safe empty dict rather than leaking MNPI data
            filtered.append({})

    if stripped_count > 0:
        logger.info("MNPI filter: stripped %d field(s) from %d record(s)", stripped_count, len(records))

    return filtered


def summarize_holdings_safe(holdings: list[dict]) -> dict:
    """
    Create an LLM-safe holdings summary: ticker, client_count, is_top_holding.
    No dollar amounts, no share counts, no prices.

    Parameters
    ----------
    holdings : list[dict]
        Raw holdings records (may contain MNPI fields).

    Returns
    -------
    dict
        {
            "tickers": ["NVDA", "AAPL", ...],
            "client_count": 42,
            "top_holdings": ["NVDA", "AAPL"],
            "sector_exposure": {"Technology": 3, "Healthcare": 1},
            "record_count": 10,
        }
    """
    if not holdings:
        return {
            "tickers": [],
            "client_count": 0,
            "top_holdings": [],
            "sector_exposure": {},
            "record_count": 0,
        }

    try:
        tickers: list[str] = []
        accounts: set[str] = set()
        sector_counts: dict[str, int] = {}

        for h in holdings:
            # Extract ticker — try common field names
            ticker = (
                h.get("FinServ__Symbol__c")
                or h.get("Ticker__c")
                or h.get("Symbol__c")
                or h.get("Name", "")
            )
            if ticker and ticker not in tickers:
                tickers.append(ticker)

            # Count unique accounts/clients
            acct = h.get("FinServ__FinancialAccount__c") or h.get("Account__c") or ""
            if acct:
                accounts.add(acct)

            # Sector exposure (count, not value)
            sector = h.get("Sector__c") or h.get("FinServ__Sector__c") or ""
            if sector:
                sector_counts[sector] = sector_counts.get(sector, 0) + 1

        # Top holdings = tickers that appear most frequently (by record count, not value)
        ticker_freq: dict[str, int] = {}
        for h in holdings:
            t = (
                h.get("FinServ__Symbol__c")
                or h.get("Ticker__c")
                or h.get("Symbol__c")
                or h.get("Name", "")
            )
            if t:
                ticker_freq[t] = ticker_freq.get(t, 0) + 1

        sorted_tickers = sorted(ticker_freq.items(), key=lambda x: x[1], reverse=True)
        top_holdings = [t for t, _ in sorted_tickers[:5]]

        return {
            "tickers": tickers,
            "client_count": len(accounts),
            "top_holdings": top_holdings,
            "sector_exposure": sector_counts,
            "record_count": len(holdings),
        }

    except Exception as exc:
        logger.warning("Holdings summarization error: %s", exc)
        return {
            "tickers": [],
            "client_count": 0,
            "top_holdings": [],
            "sector_exposure": {},
            "record_count": 0,
            "error": str(exc),
        }


__all__ = ["MNPI_FIELDS", "filter_mnpi", "summarize_holdings_safe"]
