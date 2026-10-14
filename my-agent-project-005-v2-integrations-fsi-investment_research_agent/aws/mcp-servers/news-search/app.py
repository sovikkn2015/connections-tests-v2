"""
News Search MCP Server — Lambda Handler (V2: MCP Protocol)

V2 MCP Protocol Endpoints:
    GET  /news-search/              — Server info and capabilities
    POST /news-search/tools/list    — Tool catalog with JSON Schema
    POST /news-search/tools/call    — Invoke a tool by name with arguments

Legacy REST Endpoints (backward compatible):
    POST /news-search/search_financial_news, get_headlines, get_news_sentiment
"""

import json
import os
import logging
import sys

import requests

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
    from mcp_protocol import McpServer
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TAVILY_BASE = "https://api.tavily.com"
API_KEY = os.environ.get("TAVILY_API_KEY", "")


def _build_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps(body),
    }

def _parse_body(event):
    try:
        return json.loads(event.get("body", "{}")), None
    except (json.JSONDecodeError, AttributeError):
        return None, _build_response(400, {"error": "Invalid JSON body"})

def _tavily_search(query, search_depth="basic", max_results=5):
    try:
        resp = requests.post(
            f"{TAVILY_BASE}/search",
            json={
                "api_key": API_KEY, "query": query,
                "search_depth": search_depth, "max_results": max_results,
                "include_domains": [
                    "reuters.com", "bloomberg.com", "cnbc.com", "wsj.com",
                    "ft.com", "marketwatch.com", "seekingalpha.com", "finance.yahoo.com",
                ],
            },
            timeout=15,
        )
        resp.raise_for_status()
        return [
            {"title": i.get("title", ""), "url": i.get("url", ""), "content": i.get("content", "")[:500],
             "score": i.get("score", 0), "published_date": i.get("published_date", "")}
            for i in resp.json().get("results", [])
        ]
    except requests.RequestException as e:
        logger.error("Tavily search failed: %s", str(e))
        return []


# ---------------------------------------------------------------------------
# Core data functions
# ---------------------------------------------------------------------------
def _search_financial_news_data(ticker):
    results = _tavily_search(f"{ticker} stock financial news latest", max_results=8)
    if not results:
        return {"tool": "search_financial_news", "ticker": ticker, "message": f"No recent news for {ticker}.", "articles": []}
    return {"tool": "search_financial_news", "ticker": ticker, "articles": results}

def _get_headlines_data(ticker):
    results = _tavily_search(f"{ticker} stock headlines today", max_results=10)
    if not results:
        return {"tool": "get_headlines", "ticker": ticker, "message": f"No headlines for {ticker}.", "headlines": []}
    return {"tool": "get_headlines", "ticker": ticker, "headlines": [{"title": r["title"], "url": r["url"], "published_date": r.get("published_date", "")} for r in results]}

def _get_news_sentiment_data(ticker):
    positive_results = _tavily_search(f"{ticker} stock positive outlook bullish", max_results=5)
    negative_results = _tavily_search(f"{ticker} stock negative risk bearish", max_results=5)
    positive_score = sum(r.get("score", 0) for r in positive_results)
    negative_score = sum(r.get("score", 0) for r in negative_results)
    total = positive_score + negative_score
    if total > 0:
        ratio = positive_score / total
        sentiment = "Bullish" if ratio > 0.6 else ("Bearish" if ratio < 0.4 else "Neutral")
    else:
        sentiment = "Insufficient Data"
    return {
        "tool": "get_news_sentiment", "ticker": ticker, "sentiment": sentiment,
        "positive_signals": len(positive_results), "negative_signals": len(negative_results),
        "positive_articles": [{"title": r["title"], "url": r["url"]} for r in positive_results[:3]],
        "negative_articles": [{"title": r["title"], "url": r["url"]} for r in negative_results[:3]],
    }


# Legacy REST handlers
def search_financial_news(event):
    body, err = _parse_body(event)
    if err: return err
    ticker = body.get("ticker", "").strip().upper()
    if not ticker: return _build_response(400, {"error": "Missing required field: ticker"})
    return _build_response(200, _search_financial_news_data(ticker))

def get_headlines(event):
    body, err = _parse_body(event)
    if err: return err
    ticker = body.get("ticker", "").strip().upper()
    if not ticker: return _build_response(400, {"error": "Missing required field: ticker"})
    return _build_response(200, _get_headlines_data(ticker))

def get_news_sentiment(event):
    body, err = _parse_body(event)
    if err: return err
    ticker = body.get("ticker", "").strip().upper()
    if not ticker: return _build_response(400, {"error": "Missing required field: ticker"})
    return _build_response(200, _get_news_sentiment_data(ticker))


# MCP Protocol tool handlers
def _mcp_search_news(args):
    t = args.get("ticker", "").strip().upper()
    return {"error": "Missing ticker"} if not t else _search_financial_news_data(t)

def _mcp_get_headlines(args):
    t = args.get("ticker", "").strip().upper()
    return {"error": "Missing ticker"} if not t else _get_headlines_data(t)

def _mcp_get_news_sentiment(args):
    t = args.get("ticker", "").strip().upper()
    return {"error": "Missing ticker"} if not t else _get_news_sentiment_data(t)


# MCP Server instance
TICKER_SCHEMA = {"type": "object", "properties": {"ticker": {"type": "string", "description": "Stock ticker symbol"}}, "required": ["ticker"]}
_mcp_server = None

def _get_mcp_server():
    global _mcp_server
    if _mcp_server is not None: return _mcp_server
    if not MCP_AVAILABLE: return None
    _mcp_server = McpServer(name="news-search", version="2.0.0", description="Financial news search MCP server")
    _mcp_server.register_tool("search_financial_news", "Search recent financial news articles", TICKER_SCHEMA, _mcp_search_news)
    _mcp_server.register_tool("get_headlines", "Fetch top headlines for a ticker", TICKER_SCHEMA, _mcp_get_headlines)
    _mcp_server.register_tool("get_news_sentiment", "Analyze news sentiment for a ticker", TICKER_SCHEMA, _mcp_get_news_sentiment)
    return _mcp_server


TOOLS = {"search_financial_news": search_financial_news, "get_headlines": get_headlines, "get_news_sentiment": get_news_sentiment}

def lambda_handler(event, context):
    logger.info("News Search MCP request: %s", json.dumps({"path": event.get("path"), "httpMethod": event.get("httpMethod")}))
    mcp = _get_mcp_server()
    if mcp:
        mcp_response = mcp.handle_mcp_request(event)
        if mcp_response is not None:
            return mcp_response
    path = event.get("pathParameters", {}).get("proxy", "")
    tool_name = path.strip("/").split("/")[-1] if path else ""
    if tool_name not in TOOLS:
        return _build_response(404, {"error": f"Unknown tool: {tool_name}", "available_tools": list(TOOLS.keys()), "mcp_endpoints": ["GET /", "POST /tools/list", "POST /tools/call"]})
    try:
        return TOOLS[tool_name](event)
    except Exception as e:
        logger.exception("Tool %s failed", tool_name)
        return _build_response(500, {"error": f"Internal error in {tool_name}", "message": str(e)})
