"""
News Search MCP Server — Lambda handler.
Tools: search_financial_news, get_headlines, get_news_coverage.
Uses Tavily API (key from TAVILY_API_KEY env var).
"""

import json
import os
import sys
from urllib.parse import urlparse

from mcp_protocol import McpServer

import requests

# ---- Hydrate API keys from Secrets Manager BEFORE reading env vars --------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
from secrets_loader import hydrate_env_from_secret  # noqa: E402

hydrate_env_from_secret(
    "VENDOR_SECRET_NAME",
    required_keys=["TAVILY_API_KEY"],
    default_secret_name="/006-v2/vendors/news-search",
)

# ---------------------------------------------------------------------------
# Constants — fail fast if API key is missing (Fix #11)
# ---------------------------------------------------------------------------
TAVILY_BASE = os.environ.get("TAVILY_BASE_URL", "https://api.tavily.com")
API_KEY = os.environ.get("TAVILY_API_KEY")
if not API_KEY:
    raise RuntimeError("TAVILY_API_KEY environment variable is required")


class TavilyApiError(Exception):
    """Raised when Tavily API returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Tavily {status_code}: {detail}")


def _tavily_search(query: str, **kwargs) -> dict:
    """Execute a Tavily search request with retry on transient errors."""
    payload = {
        "api_key": API_KEY,
        "query": query,
        "search_depth": kwargs.get("search_depth", "advanced"),
        "include_answer": kwargs.get("include_answer", True),
        "max_results": kwargs.get("max_results", 10),
    }
    if kwargs.get("topic"):
        payload["topic"] = kwargs["topic"]
    if kwargs.get("days"):
        payload["days"] = kwargs["days"]
    if kwargs.get("include_domains"):
        payload["include_domains"] = kwargs["include_domains"]

    last_err = None
    for attempt in range(3):
        try:
            resp = requests.post(
                f"{TAVILY_BASE}/search",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=20,
            )
            if resp.ok:
                return resp.json()

            # Parse error detail from Tavily response
            try:
                err_body = resp.json()
                detail = err_body.get("detail", {})
                if isinstance(detail, dict):
                    err_msg = detail.get("error", resp.text[:200])
                else:
                    err_msg = str(detail)[:200]
            except Exception:
                err_msg = resp.text[:200]

            # Don't retry on quota/auth errors — they won't resolve
            if resp.status_code in (401, 403, 429):
                raise TavilyApiError(resp.status_code, err_msg)

            # Retry on 5xx server errors
            if resp.status_code >= 500 and attempt < 2:
                import time
                time.sleep(1 * (attempt + 1))
                last_err = TavilyApiError(resp.status_code, err_msg)
                continue

            raise TavilyApiError(resp.status_code, err_msg)

        except requests.exceptions.Timeout:
            if attempt < 2:
                import time
                time.sleep(1)
                last_err = TavilyApiError(408, "Request timed out")
                continue
            raise TavilyApiError(408, "Request timed out after 3 attempts")
        except TavilyApiError:
            raise
        except requests.exceptions.RequestException as e:
            raise TavilyApiError(0, f"Connection error: {str(e)[:150]}")

    raise last_err or TavilyApiError(500, "All retry attempts failed")


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------
FINANCIAL_DOMAINS = [
    "reuters.com", "bloomberg.com", "cnbc.com", "wsj.com",
    "ft.com", "marketwatch.com", "seekingalpha.com", "finance.yahoo.com",
]


def _safe_source(url: str) -> str:
    """Extract domain from URL safely (Fix #20)."""
    return urlparse(url).netloc or "unknown"


def handle_search_financial_news(params: dict) -> dict:
    """Search for financial news articles on a topic or company."""
    query = params["query"]
    max_results = params.get("max_results", 10)
    days = params.get("days", 7)

    try:
        data = _tavily_search(
            query,
            topic="news",
            max_results=max_results,
            days=days,
            include_domains=FINANCIAL_DOMAINS,
        )
    except TavilyApiError as e:
        return {
            "query": query,
            "error": f"News search failed: {e.detail}",
            "errorCode": e.status_code,
            "resultCount": 0,
            "results": [],
        }

    results = []
    for r in data.get("results", []):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", "")[:500],
            "publishedDate": r.get("published_date", ""),
            "source": _safe_source(r.get("url", "")),
            "score": r.get("score", 0),
        })

    return {
        "query": query,
        "answer": data.get("answer", ""),
        "resultCount": len(results),
        "results": results,
    }


def handle_get_headlines(params: dict) -> dict:
    """Get latest financial headlines, optionally filtered by sector."""
    sector = params.get("sector", "markets")
    max_results = params.get("max_results", 10)

    query = f"latest {sector} financial news headlines today"
    try:
        data = _tavily_search(
            query,
            topic="news",
            max_results=max_results,
            days=1,
            include_domains=FINANCIAL_DOMAINS,
        )
    except TavilyApiError as e:
        return {
            "sector": sector,
            "error": f"Headlines fetch failed: {e.detail}",
            "errorCode": e.status_code,
            "headlineCount": 0,
            "headlines": [],
        }

    headlines = []
    for r in data.get("results", []):
        headlines.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "source": _safe_source(r.get("url", "")),
            "publishedDate": r.get("published_date", ""),
        })

    return {"sector": sector, "headlineCount": len(headlines), "headlines": headlines}


def handle_get_news_coverage(params: dict) -> dict:
    """
    Get recent news coverage for a company or topic.
    Returns articles for LLM-based sentiment analysis — does NOT return
    pre-computed sentiment scores. The calling agent/LLM should interpret
    the articles to derive sentiment. (Fix #10: renamed from get_news_sentiment)
    """
    query = params["query"]
    days = params.get("days", 7)

    try:
        data = _tavily_search(
            f"{query} stock market news coverage",
            topic="news",
            max_results=15,
            days=days,
            include_answer=True,
        )
    except TavilyApiError as e:
        return {
            "query": query,
            "error": f"News coverage fetch failed: {e.detail}",
            "errorCode": e.status_code,
            "articleCount": 0,
            "articles": [],
            "coverageSummary": "",
        }

    articles = []
    for r in data.get("results", []):
        articles.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", "")[:300],
            "source": _safe_source(r.get("url", "")),
        })

    return {
        "query": query,
        "coverageSummary": data.get("answer", ""),
        "articleCount": len(articles),
        "articles": articles,
    }


# ---------------------------------------------------------------------------
# Tool schemas (Fix #10: renamed get_news_sentiment → get_news_coverage)
# ---------------------------------------------------------------------------
TOOLS = {
    "search_financial_news": {
        "description": "Search for financial news articles about a company, sector, or topic.",
        "properties": {
            "query": {"type": "string", "description": "Search query (e.g. 'Apple earnings Q4')"},
            "max_results": {"type": "integer", "description": "Max articles to return (default 10)"},
            "days": {"type": "integer", "description": "Look back N days (default 7)"},
        },
        "required": ["query"],
    },
    "get_headlines": {
        "description": "Get the latest financial news headlines, optionally filtered by sector.",
        "properties": {
            "sector": {"type": "string", "description": "Sector filter: markets, tech, energy, healthcare, crypto (default markets)"},
            "max_results": {"type": "integer", "description": "Max headlines to return (default 10)"},
        },
        "required": [],
    },
    "get_news_coverage": {
        "description": "Get recent news articles covering a company or market topic. Returns raw articles for the LLM agent to perform sentiment analysis — no pre-computed sentiment scores.",
        "properties": {
            "query": {"type": "string", "description": "Company or topic to get news coverage for"},
            "days": {"type": "integer", "description": "Look back N days (default 7)"},
        },
        "required": ["query"],
    },
}

HANDLERS = {
    "search_financial_news": handle_search_financial_news,
    "get_headlines": handle_get_headlines,
    "get_news_coverage": handle_get_news_coverage,
}

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------
server = McpServer(
    name="news-search",
    version="1.0.0",
    description="Financial news — search articles, headlines, and news coverage for LLM analysis.",
)

for tool_name, schema in TOOLS.items():
    server.register_tool(tool_name, schema, HANDLERS[tool_name])


def lambda_handler(event, context):
    """AWS Lambda entry point."""
    return server.handle(event)
# Force redeploy
