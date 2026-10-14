"""
SEC EDGAR MCP Server — Lambda handler.
Tools: get_10k, get_10q, get_8k, get_insider_transactions, search_filings.
Uses the free data.sec.gov REST API (no key required, User-Agent header required).
"""

import json
import time

from mcp_protocol import McpServer

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SEC_BASE = "https://www.sec.gov"
SEC_DATA_BASE = "https://data.sec.gov"
EFTS_BASE = "https://efts.sec.gov/LATEST"
SEC_HEADERS = {
    "User-Agent": "OpenClaw-MCP/1.0 (support@openclaw.dev)",
    "Accept": "application/json",
}

# ---------------------------------------------------------------------------
# Rate limiter — SEC EDGAR allows max 10 requests/sec
# ---------------------------------------------------------------------------
_LAST_SEC_CALL = 0.0


def _rate_limited_get(url, **kwargs):
    """GET with rate limiting for SEC EDGAR (max 10 req/sec)."""
    global _LAST_SEC_CALL
    elapsed = time.time() - _LAST_SEC_CALL
    if elapsed < 0.1:
        time.sleep(0.1 - elapsed)
    _LAST_SEC_CALL = time.time()
    kwargs.setdefault("headers", SEC_HEADERS)
    kwargs.setdefault("timeout", 15)
    return requests.get(url, **kwargs)


# ---------------------------------------------------------------------------
# CIK cache — loaded once per Lambda warm instance (Fix #6)
# ---------------------------------------------------------------------------
_CIK_CACHE: dict | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _cik_padded(cik: str) -> str:
    """Pad CIK to 10 digits as required by SEC EDGAR."""
    return cik.strip().zfill(10)


def _get_company_cik(ticker: str) -> str | None:
    """Resolve a ticker symbol to a CIK number (cached)."""
    global _CIK_CACHE
    if _CIK_CACHE is None:
        url = f"{SEC_BASE}/files/company_tickers.json"
        resp = _rate_limited_get(url)
        resp.raise_for_status()
        _CIK_CACHE = resp.json()
    ticker_upper = ticker.upper()
    for entry in _CIK_CACHE.values():
        if entry.get("ticker", "").upper() == ticker_upper:
            return str(entry["cik_str"])
    return None


def _get_filings(cik: str, form_type: str, count: int = 5) -> list[dict]:
    """Fetch recent filings of a given form type for a CIK."""
    padded = _cik_padded(cik)
    url = f"{SEC_DATA_BASE}/submissions/CIK{padded}.json"
    resp = _rate_limited_get(url)
    resp.raise_for_status()
    data = resp.json()

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    results = []
    for i, form in enumerate(forms):
        if form == form_type and len(results) < count:
            acc_no = accessions[i].replace("-", "")
            results.append({
                "form": form,
                "filingDate": dates[i],
                "accessionNumber": accessions[i],
                "documentUrl": f"{SEC_DATA_BASE}/Archives/edgar/data/{padded}/{acc_no}/{primary_docs[i]}",
            })
    return results


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------
def handle_get_10k(params: dict) -> dict:
    """Retrieve recent 10-K annual reports."""
    ticker = params["ticker"]
    count = params.get("count", 3)
    cik = _get_company_cik(ticker)
    if not cik:
        return {"error": f"Could not resolve ticker: {ticker}"}
    filings = _get_filings(cik, "10-K", count)
    return {"ticker": ticker, "cik": cik, "form": "10-K", "filings": filings}


def handle_get_10q(params: dict) -> dict:
    """Retrieve recent 10-Q quarterly reports."""
    ticker = params["ticker"]
    count = params.get("count", 3)
    cik = _get_company_cik(ticker)
    if not cik:
        return {"error": f"Could not resolve ticker: {ticker}"}
    filings = _get_filings(cik, "10-Q", count)
    return {"ticker": ticker, "cik": cik, "form": "10-Q", "filings": filings}


def handle_get_8k(params: dict) -> dict:
    """Retrieve recent 8-K current reports."""
    ticker = params["ticker"]
    count = params.get("count", 5)
    cik = _get_company_cik(ticker)
    if not cik:
        return {"error": f"Could not resolve ticker: {ticker}"}
    filings = _get_filings(cik, "8-K", count)
    return {"ticker": ticker, "cik": cik, "form": "8-K", "filings": filings}


def handle_get_insider_transactions(params: dict) -> dict:
    """Retrieve recent insider transaction filings (Form 4)."""
    ticker = params["ticker"]
    count = params.get("count", 10)
    cik = _get_company_cik(ticker)
    if not cik:
        return {"error": f"Could not resolve ticker: {ticker}"}
    filings = _get_filings(cik, "4", count)
    return {"ticker": ticker, "cik": cik, "form": "4", "filings": filings}


def handle_search_filings(params: dict) -> dict:
    """Full-text search across SEC EDGAR filings."""
    query = params["query"]
    form_type = params.get("form_type", "")
    date_from = params.get("date_from", "")
    date_to = params.get("date_to", "")
    count = params.get("count", 10)

    search_params = {"q": query, "dateRange": "custom", "startdt": date_from, "enddt": date_to}
    if form_type:
        search_params["forms"] = form_type
    if not date_from:
        search_params.pop("startdt", None)
        search_params.pop("dateRange", None)
    if not date_to:
        search_params.pop("enddt", None)

    # Fix #19: correct EFTS endpoint is /search, not /search-index
    url = f"{EFTS_BASE}/search"
    resp = _rate_limited_get(url, params=search_params)
    resp.raise_for_status()
    data = resp.json()

    hits = data.get("hits", {}).get("hits", [])[:count]
    results = []
    for hit in hits:
        src = hit.get("_source", {})
        results.append({
            "entityName": src.get("entity_name", ""),
            "form": src.get("form_type", ""),
            "filingDate": src.get("file_date", ""),
            "description": src.get("display_names", [""])[0] if src.get("display_names") else "",
            "url": f"https://www.sec.gov/Archives/edgar/data/{src.get('file_num', '')}" if src.get("file_num") else "",
        })
    return {"query": query, "resultCount": len(results), "results": results}


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------
TICKER_COUNT_SCHEMA = {
    "description": "",
    "properties": {
        "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL, MSFT)"},
        "count": {"type": "integer", "description": "Number of filings to return (default 3)"},
    },
    "required": ["ticker"],
}

TOOLS = {
    "get_10k": {
        **TICKER_COUNT_SCHEMA,
        "description": "Get recent 10-K annual report filings for a company from SEC EDGAR.",
    },
    "get_10q": {
        **TICKER_COUNT_SCHEMA,
        "description": "Get recent 10-Q quarterly report filings for a company from SEC EDGAR.",
    },
    "get_8k": {
        **TICKER_COUNT_SCHEMA,
        "description": "Get recent 8-K current report filings for a company from SEC EDGAR.",
    },
    "get_insider_transactions": {
        **TICKER_COUNT_SCHEMA,
        "description": "Get recent insider transaction filings (Form 4) for a company from SEC EDGAR.",
    },
    "search_filings": {
        "description": "Full-text search across all SEC EDGAR filings.",
        "properties": {
            "query": {"type": "string", "description": "Search query text"},
            "form_type": {"type": "string", "description": "Filter by form type (e.g. 10-K, 8-K)"},
            "date_from": {"type": "string", "description": "Start date filter (YYYY-MM-DD)"},
            "date_to": {"type": "string", "description": "End date filter (YYYY-MM-DD)"},
            "count": {"type": "integer", "description": "Max results to return (default 10)"},
        },
        "required": ["query"],
    },
}

HANDLERS = {
    "get_10k": handle_get_10k,
    "get_10q": handle_get_10q,
    "get_8k": handle_get_8k,
    "get_insider_transactions": handle_get_insider_transactions,
    "search_filings": handle_search_filings,
}

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------
server = McpServer(
    name="sec-edgar",
    version="1.0.0",
    description="SEC EDGAR filings — 10-K, 10-Q, 8-K, insider transactions, full-text search.",
)

for tool_name, schema in TOOLS.items():
    server.register_tool(tool_name, schema, HANDLERS[tool_name])


def lambda_handler(event, context):
    """AWS Lambda entry point."""
    return server.handle(event)
# Force redeploy
