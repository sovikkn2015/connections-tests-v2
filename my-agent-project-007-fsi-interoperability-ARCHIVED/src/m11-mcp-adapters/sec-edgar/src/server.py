"""
SEC EDGAR MCP Adapter — M11-REST (Phase 1).
Returns raw vendor data. M6 gateway calls M7 translator to convert to canonical types.

Free public API. 10 req/s rate limit. User-Agent required by SEC.
Tools: search_filings, get_filing, get_company_facts.

Run: uvicorn src.server:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import httpx

# Add parent dir so _shared is importable (works both locally and in Docker)
_here = Path(__file__).resolve().parent
for _ancestor in [_here.parent, _here.parent.parent, *_here.parents]:
    if (_ancestor / "_shared").is_dir():
        sys.path.insert(0, str(_ancestor))
        break

from _shared.mcp_server import MCPAdapterServer, ToolDefinition
from _shared.rate_limiter import TokenBucket
from _shared.errors import canonical_error, tool_result

# ---------------------------------------------------------------------------
# Rate limiter (Rule 4)
# ---------------------------------------------------------------------------
_rpm = int(os.environ.get("SEC_EDGAR_RATE_LIMIT_RPM", "600"))
_burst = int(os.environ.get("SEC_EDGAR_RATE_LIMIT_BURST", "10"))
rate_limiter = TokenBucket(rate_per_second=_rpm / 60.0, burst=_burst)

# ---------------------------------------------------------------------------
# SEC EDGAR HTTP client
# ---------------------------------------------------------------------------
_DEFAULT_UA = "007-FSI-Platform admin@example.com"
SEC_EDGAR_UA = os.environ.get("SEC_EDGAR_USER_AGENT", _DEFAULT_UA)
EFTS_BASE = "https://efts.sec.gov/LATEST"
DATA_BASE = "https://data.sec.gov"

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            headers={"User-Agent": SEC_EDGAR_UA, "Accept": "application/json"},
            timeout=30.0,
        )
    return _http_client


async def _sec_get(url: str, params: dict[str, Any] | None = None) -> Any:
    acquired = await rate_limiter.acquire()
    if not acquired:
        return canonical_error(
            "SEC EDGAR rate limit exceeded.",
            error_code="RATE_LIMIT_EXCEEDED",
            vendor_status_code=429,
            retryable=True,
        )
    client = _get_http_client()
    resp = await client.get(url, params=params)
    if resp.status_code != 200:
        return canonical_error(
            f"SEC EDGAR returned HTTP {resp.status_code}",
            error_code="VENDOR_HTTP_ERROR",
            vendor_status_code=resp.status_code,
            retryable=resp.status_code >= 500,
        )
    return resp.json()


# ---------------------------------------------------------------------------
# Tool handlers (vendor-specific logic only)
# ---------------------------------------------------------------------------
async def _handle_search_filings(args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("query")
    if not query:
        return canonical_error("'query' is required.", error_code="INVALID_PARAMS")
    params: dict[str, Any] = {"q": query, "from": 0, "size": args.get("limit", 10)}
    if args.get("date_range"):
        params["dateRange"] = args["date_range"]
    if args.get("filing_type"):
        params["forms"] = args["filing_type"]
    result = await _sec_get(f"{EFTS_BASE}/search-index", params=params)
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_filing(args: dict[str, Any]) -> dict[str, Any]:
    accession = args.get("accession_number")
    if not accession:
        return canonical_error("'accession_number' is required.", error_code="INVALID_PARAMS")
    clean = accession.replace("-", "")
    result = await _sec_get(f"{DATA_BASE}/submissions/{clean}.json")
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_company_facts(args: dict[str, Any]) -> dict[str, Any]:
    cik = args.get("cik")
    if not cik:
        return canonical_error("'cik' is required.", error_code="INVALID_PARAMS")
    padded = cik.zfill(10)
    result = await _sec_get(f"{DATA_BASE}/api/xbrl/companyfacts/CIK{padded}.json")
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


# ---------------------------------------------------------------------------
# MCP server assembly via _shared factory
# ---------------------------------------------------------------------------
_server = MCPAdapterServer(
    name="sec-edgar-adapter",
    version="1.0.0",
    vendor="sec_edgar",
    description="SEC EDGAR public filings search and retrieval. Free API, 10 req/s.",
)

_server.register_tool(
    ToolDefinition(
        name="search_filings",
        description="Search SEC EDGAR filings by company ticker/name, filing type, and date range.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Company ticker symbol or name (e.g. 'AAPL' or 'Apple Inc')",
                },
                "filing_type": {
                    "type": "string",
                    "description": "SEC filing type filter",
                    "enum": ["10-K", "10-Q", "8-K", "13F", "S-1", "DEF 14A", "4", "SC 13D"],
                },
                "date_range": {
                    "type": "string",
                    "description": "Date range in format 'YYYY-MM-DD:YYYY-MM-DD'",
                    "pattern": "^\\d{4}-\\d{2}-\\d{2}:\\d{4}-\\d{2}-\\d{2}$",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (1-40)",
                    "minimum": 1,
                    "maximum": 40,
                    "default": 10,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    ),
    _handle_search_filings,
)

_server.register_tool(
    ToolDefinition(
        name="get_filing",
        description="Retrieve SEC filing metadata by accession number.",
        inputSchema={
            "type": "object",
            "properties": {
                "accession_number": {
                    "type": "string",
                    "description": "SEC accession number (e.g. '0000320193-23-000106')",
                },
            },
            "required": ["accession_number"],
            "additionalProperties": False,
        },
    ),
    _handle_get_filing,
)

_server.register_tool(
    ToolDefinition(
        name="get_company_facts",
        description="Get XBRL company facts (financial data) for a company by CIK number.",
        inputSchema={
            "type": "object",
            "properties": {
                "cik": {
                    "type": "string",
                    "description": "SEC Central Index Key (CIK) number (e.g. '320193' for Apple)",
                },
            },
            "required": ["cik"],
            "additionalProperties": False,
        },
    ),
    _handle_get_company_facts,
)

app = _server.build_app()


@app.on_event("shutdown")
async def shutdown() -> None:
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
