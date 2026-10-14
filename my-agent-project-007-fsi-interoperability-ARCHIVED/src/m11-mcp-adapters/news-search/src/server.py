"""
News API MCP Adapter — M11-REST (Phase 2).
Returns raw vendor data. M6 gateway calls M7 translator to convert to canonical types.

API key auth via NEWS_API_KEY env var.
Used by Research Specialist pipeline for news scan stage.
Tools: search_news, get_headlines.

Run: uvicorn src.server:app --host 0.0.0.0 --port 8002
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
_rpm = int(os.environ.get("NEWS_API_RATE_LIMIT_RPM", "100"))
_burst = int(os.environ.get("NEWS_API_RATE_LIMIT_BURST", "10"))
rate_limiter = TokenBucket(rate_per_second=_rpm / 60.0, burst=_burst)

# ---------------------------------------------------------------------------
# News API HTTP client (Rule 3 — API key from env)
# ---------------------------------------------------------------------------
NEWS_API_BASE = "https://newsapi.org/v2"
_http_client: httpx.AsyncClient | None = None


def _get_api_key() -> str:
    key = os.environ.get("NEWS_API_KEY", "")
    if not key:
        raise ValueError("NEWS_API_KEY environment variable is required.")
    return key


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


async def _news_get(endpoint: str, params: dict[str, Any]) -> Any:
    """Rate-limited GET to News API."""
    acquired = await rate_limiter.acquire()
    if not acquired:
        return canonical_error("News API rate limit exceeded.",
                               error_code="RATE_LIMIT_EXCEEDED",
                               vendor_status_code=429, retryable=True)
    try:
        api_key = _get_api_key()
    except ValueError as e:
        return canonical_error(str(e), error_code="AUTH_MISSING", retryable=False)

    params["apiKey"] = api_key
    client = _get_http_client()
    resp = await client.get(f"{NEWS_API_BASE}/{endpoint}", params=params)
    if resp.status_code == 401:
        return canonical_error("Invalid News API key.", error_code="AUTH_INVALID",
                               vendor_status_code=401, retryable=False)
    if resp.status_code == 429:
        return canonical_error("News API rate limit exceeded.",
                               error_code="RATE_LIMIT_EXCEEDED",
                               vendor_status_code=429, retryable=True)
    if resp.status_code != 200:
        return canonical_error(f"News API returned HTTP {resp.status_code}",
                               error_code="VENDOR_HTTP_ERROR",
                               vendor_status_code=resp.status_code,
                               retryable=resp.status_code >= 500)
    data = resp.json()
    if data.get("status") == "error":
        return canonical_error(data.get("message", "Unknown News API error"),
                               error_code="VENDOR_API_ERROR",
                               vendor_status_code=200, retryable=False)
    return data


# ---------------------------------------------------------------------------
# Tool handlers (vendor-specific logic only)
# ---------------------------------------------------------------------------
async def _handle_search_news(args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("query")
    if not query:
        return canonical_error("'query' is required.", error_code="INVALID_PARAMS")
    params: dict[str, Any] = {
        "q": query,
        "sortBy": args.get("sort_by", "relevancy"),
        "pageSize": args.get("page_size", 20),
    }
    if args.get("from_date"):
        params["from"] = args["from_date"]
    if args.get("to_date"):
        params["to"] = args["to_date"]
    result = await _news_get("everything", params)
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_headlines(args: dict[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {
        "category": args.get("category", "business"),
        "country": args.get("country", "us"),
        "pageSize": args.get("page_size", 20),
    }
    result = await _news_get("top-headlines", params)
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


# ---------------------------------------------------------------------------
# MCP server assembly via _shared factory
# ---------------------------------------------------------------------------
_server = MCPAdapterServer(
    name="news-search-adapter",
    version="1.0.0",
    vendor="news_api",
    description="News API: article search and top headlines for Research Specialist pipeline.",
)

_server.register_tool(
    ToolDefinition(
        name="search_news",
        description="Search news articles by keyword query with date range and sort options. Used by Research Specialist for news scan.",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g. 'Apple earnings' or 'AAPL SEC filing')",
                },
                "from_date": {
                    "type": "string",
                    "description": "Start date ISO 8601 (e.g. '2026-01-01')",
                    "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                },
                "to_date": {
                    "type": "string",
                    "description": "End date ISO 8601 (e.g. '2026-01-31')",
                    "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                },
                "sort_by": {
                    "type": "string",
                    "description": "Sort order",
                    "enum": ["relevancy", "popularity", "publishedAt"],
                    "default": "relevancy",
                },
                "page_size": {
                    "type": "integer",
                    "description": "Results per page (1-100)",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    ),
    _handle_search_news,
)

_server.register_tool(
    ToolDefinition(
        name="get_headlines",
        description="Get top headlines by category and/or country.",
        inputSchema={
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "News category",
                    "enum": ["business", "technology", "science", "health", "general"],
                    "default": "business",
                },
                "country": {
                    "type": "string",
                    "description": "Two-letter ISO 3166-1 country code",
                    "pattern": "^[a-z]{2}$",
                    "default": "us",
                },
                "page_size": {
                    "type": "integer",
                    "description": "Number of results (1-100)",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    ),
    _handle_get_headlines,
)

app = _server.build_app()


@app.on_event("shutdown")
async def shutdown() -> None:
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
