"""
SEC EDGAR MCP Server — Lambda Handler (V2: MCP Protocol)

Provides tools for fetching SEC filings (10-K, 10-Q, 8-K) and insider
transactions from the free SEC EDGAR XBRL/full-text search API.

V2 MCP Protocol Endpoints:
    GET  /sec-edgar/              — Server info and capabilities
    POST /sec-edgar/tools/list    — Tool catalog with JSON Schema
    POST /sec-edgar/tools/call    — Invoke a tool by name with arguments

Legacy REST Endpoints (backward compatible):
    POST /sec-edgar/get_10k       — Latest 10-K filing summary
    POST /sec-edgar/get_10q       — Latest 10-Q filing summary
    POST /sec-edgar/get_8k        — Latest 8-K filing summary
    POST /sec-edgar/get_insider_transactions — Recent insider transactions
"""

import json
import os
import logging
import sys
from datetime import datetime, timedelta

import requests

# --- MCP Protocol support ---
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
    from mcp_protocol import McpServer
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SEC_EDGAR_BASE = "https://efts.sec.gov/LATEST/search-index"
SEC_EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions"
USER_AGENT = os.environ.get("SEC_EDGAR_USER_AGENT", "placeholder@example.com")

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
}


def _build_response(status_code, body):
    """Build a standard API Gateway proxy response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def _parse_ticker(event):
    """Extract ticker from the request body JSON."""
    try:
        body = json.loads(event.get("body", "{}"))
        ticker = body.get("ticker", "").strip().upper()
        if not ticker:
            return None, _build_response(400, {"error": "Missing required field: ticker"})
        return ticker, None
    except (json.JSONDecodeError, AttributeError):
        return None, _build_response(400, {"error": "Invalid JSON body"})


def _search_filings(ticker, form_type, limit=5):
    """Search SEC EDGAR for filings by ticker and form type.

    Args:
        ticker: Stock ticker symbol (e.g. 'AAPL').
        form_type: SEC form type (e.g. '10-K', '10-Q', '8-K').
        limit: Maximum number of results to return.

    Returns:
        List of filing dicts with accession number, date, and description.
    """
    one_year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    try:
        search_url = "https://efts.sec.gov/LATEST/search-index"
        search_params = {
            "q": f'"{ticker}" AND formType:"{form_type}"',
            "dateRange": "custom",
            "startdt": one_year_ago,
        }
        resp = requests.get(search_url, params=search_params, headers=HEADERS, timeout=15)

        if resp.status_code != 200 or not resp.json().get("hits", {}).get("hits"):
            cik = _get_company_cik(ticker)
            if cik:
                sub_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
                resp2 = requests.get(sub_url, headers=HEADERS, timeout=15)
                if resp2.status_code == 200:
                    sub_data = resp2.json()
                    recent = sub_data.get("filings", {}).get("recent", {})
                    forms = recent.get("form", [])
                    dates = recent.get("filingDate", [])
                    accessions = recent.get("accessionNumber", [])
                    descs = recent.get("primaryDocDescription", [])
                    results = []
                    for i in range(len(forms)):
                        if forms[i] == form_type:
                            results.append({
                                "accession_number": accessions[i] if i < len(accessions) else "",
                                "filing_date": dates[i] if i < len(dates) else "",
                                "form_type": forms[i],
                                "company_name": sub_data.get("name", ticker),
                                "description": descs[i] if i < len(descs) else "",
                            })
                            if len(results) >= limit:
                                break
                    return results

        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])
        results = []
        for hit in hits[:limit]:
            source = hit.get("_source", {})
            results.append({
                "accession_number": source.get("file_num", ""),
                "filing_date": source.get("file_date", ""),
                "form_type": source.get("form_type", form_type),
                "company_name": source.get("display_names", [ticker])[0] if source.get("display_names") else ticker,
                "description": source.get("display_description", ""),
            })
        return results
    except requests.RequestException as e:
        logger.error("SEC EDGAR search failed for %s %s: %s", ticker, form_type, str(e))
        return []


def _get_company_cik(ticker):
    """Look up the CIK number for a ticker.

    Args:
        ticker: Stock ticker symbol.

    Returns:
        Zero-padded CIK string or None if not found.
    """
    try:
        resp = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=HEADERS, timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker.upper():
                return str(entry["cik_str"]).zfill(10)
    except requests.RequestException as e:
        logger.error("CIK lookup failed for %s: %s", ticker, str(e))
    return None


# ---------------------------------------------------------------------------
# Legacy REST tool handlers
# ---------------------------------------------------------------------------
def get_10k(event):
    """Fetch the latest 10-K (annual report) filing summary for a ticker."""
    ticker, err = _parse_ticker(event)
    if err:
        return err
    filings = _search_filings(ticker, "10-K", limit=3)
    if not filings:
        return _build_response(200, {
            "tool": "get_10k", "ticker": ticker,
            "message": f"No recent 10-K filings found for {ticker}.", "filings": [],
        })
    return _build_response(200, {"tool": "get_10k", "ticker": ticker, "filings": filings})


def get_10q(event):
    """Fetch the latest 10-Q (quarterly report) filing summary for a ticker."""
    ticker, err = _parse_ticker(event)
    if err:
        return err
    filings = _search_filings(ticker, "10-Q", limit=3)
    if not filings:
        return _build_response(200, {
            "tool": "get_10q", "ticker": ticker,
            "message": f"No recent 10-Q filings found for {ticker}.", "filings": [],
        })
    return _build_response(200, {"tool": "get_10q", "ticker": ticker, "filings": filings})


def get_8k(event):
    """Fetch the latest 8-K (current report) filing summary for a ticker."""
    ticker, err = _parse_ticker(event)
    if err:
        return err
    filings = _search_filings(ticker, "8-K", limit=5)
    if not filings:
        return _build_response(200, {
            "tool": "get_8k", "ticker": ticker,
            "message": f"No recent 8-K filings found for {ticker}.", "filings": [],
        })
    return _build_response(200, {"tool": "get_8k", "ticker": ticker, "filings": filings})


def get_insider_transactions(event):
    """Fetch recent insider transactions for a ticker from SEC EDGAR."""
    ticker, err = _parse_ticker(event)
    if err:
        return err
    filings = _search_filings(ticker, "4", limit=10)
    if not filings:
        filings = _search_filings(ticker, "3", limit=5)
        filings.extend(_search_filings(ticker, "5", limit=5))
    if not filings:
        return _build_response(200, {
            "tool": "get_insider_transactions", "ticker": ticker,
            "message": f"No recent insider transactions found for {ticker}.", "transactions": [],
        })
    return _build_response(200, {
        "tool": "get_insider_transactions", "ticker": ticker, "transactions": filings,
    })


# ---------------------------------------------------------------------------
# MCP Protocol tool handlers (accept arguments dict)
# ---------------------------------------------------------------------------
def _mcp_get_10k(arguments):
    ticker = arguments.get("ticker", "").strip().upper()
    if not ticker:
        return {"error": "Missing required argument: ticker"}
    return {"tool": "get_10k", "ticker": ticker, "filings": _search_filings(ticker, "10-K", limit=3)}


def _mcp_get_10q(arguments):
    ticker = arguments.get("ticker", "").strip().upper()
    if not ticker:
        return {"error": "Missing required argument: ticker"}
    return {"tool": "get_10q", "ticker": ticker, "filings": _search_filings(ticker, "10-Q", limit=3)}


def _mcp_get_8k(arguments):
    ticker = arguments.get("ticker", "").strip().upper()
    if not ticker:
        return {"error": "Missing required argument: ticker"}
    return {"tool": "get_8k", "ticker": ticker, "filings": _search_filings(ticker, "8-K", limit=5)}


def _mcp_get_insider_transactions(arguments):
    ticker = arguments.get("ticker", "").strip().upper()
    if not ticker:
        return {"error": "Missing required argument: ticker"}
    filings = _search_filings(ticker, "4", limit=10)
    if not filings:
        filings = _search_filings(ticker, "3", limit=5)
        filings.extend(_search_filings(ticker, "5", limit=5))
    return {"tool": "get_insider_transactions", "ticker": ticker, "transactions": filings}


# ---------------------------------------------------------------------------
# MCP Server instance
# ---------------------------------------------------------------------------
TICKER_SCHEMA = {
    "type": "object",
    "properties": {
        "ticker": {"type": "string", "description": "Stock ticker symbol (e.g. 'AAPL', 'NVDA')"},
    },
    "required": ["ticker"],
}

_mcp_server = None

def _get_mcp_server():
    global _mcp_server
    if _mcp_server is not None:
        return _mcp_server
    if not MCP_AVAILABLE:
        return None
    _mcp_server = McpServer(
        name="sec-edgar", version="2.0.0",
        description="SEC EDGAR filings MCP server — 10-K, 10-Q, 8-K, insider transactions",
    )
    _mcp_server.register_tool("get_10k", "Fetch latest 10-K annual report filings", TICKER_SCHEMA, _mcp_get_10k)
    _mcp_server.register_tool("get_10q", "Fetch latest 10-Q quarterly report filings", TICKER_SCHEMA, _mcp_get_10q)
    _mcp_server.register_tool("get_8k", "Fetch latest 8-K current report filings", TICKER_SCHEMA, _mcp_get_8k)
    _mcp_server.register_tool("get_insider_transactions", "Fetch recent insider transactions (Form 3/4/5)", TICKER_SCHEMA, _mcp_get_insider_transactions)
    return _mcp_server


# Legacy tool routing map
TOOLS = {
    "get_10k": get_10k,
    "get_10q": get_10q,
    "get_8k": get_8k,
    "get_insider_transactions": get_insider_transactions,
}


def lambda_handler(event, context):
    """Main Lambda entry point. Routes MCP protocol requests first, then legacy REST.

    Args:
        event: API Gateway proxy event.
        context: Lambda context object.

    Returns:
        API Gateway proxy response dict.
    """
    logger.info("SEC EDGAR MCP request: %s", json.dumps({
        "path": event.get("path"), "httpMethod": event.get("httpMethod"),
    }))

    # Try MCP protocol first
    mcp = _get_mcp_server()
    if mcp:
        mcp_response = mcp.handle_mcp_request(event)
        if mcp_response is not None:
            return mcp_response

    # Legacy REST routing
    path = event.get("pathParameters", {}).get("proxy", "")
    tool_name = path.strip("/").split("/")[-1] if path else ""

    if tool_name not in TOOLS:
        return _build_response(404, {
            "error": f"Unknown tool: {tool_name}",
            "available_tools": list(TOOLS.keys()),
            "mcp_endpoints": ["GET /", "POST /tools/list", "POST /tools/call"],
        })

    try:
        return TOOLS[tool_name](event)
    except Exception as e:
        logger.exception("Tool %s failed", tool_name)
        return _build_response(500, {"error": f"Internal error in {tool_name}", "message": str(e)})
