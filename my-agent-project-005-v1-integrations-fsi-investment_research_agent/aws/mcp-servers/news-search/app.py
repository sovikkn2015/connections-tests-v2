"""
News Search MCP Server — Lambda Handler

Provides tools for searching financial news, fetching headlines, and
analyzing news sentiment via the Tavily API.

Routes:
    POST /news-search/search_financial_news — Search recent financial news
    POST /news-search/get_headlines         — Top headlines for a ticker
    POST /news-search/get_news_sentiment    — News sentiment analysis
"""

import json
import os
import logging

import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TAVILY_BASE = "https://api.tavily.com"
API_KEY = os.environ.get("TAVILY_API_KEY", "")


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


def _parse_body(event):
    """Parse the JSON request body from an API Gateway event."""
    try:
        return json.loads(event.get("body", "{}")), None
    except (json.JSONDecodeError, AttributeError):
        return None, _build_response(400, {"error": "Invalid JSON body"})


def _tavily_search(query, search_depth="basic", max_results=5):
    """
    Execute a search query against the Tavily API.

    Args:
        query: Search query string.
        search_depth: 'basic' or 'advanced' search depth.
        max_results: Maximum number of results to return.

    Returns:
        List of result dicts with title, url, content, and score.
    """
    try:
        resp = requests.post(
            f"{TAVILY_BASE}/search",
            json={
                "api_key": API_KEY,
                "query": query,
                "search_depth": search_depth,
                "max_results": max_results,
                "include_domains": [
                    "reuters.com", "bloomberg.com", "cnbc.com",
                    "wsj.com", "ft.com", "marketwatch.com",
                    "seekingalpha.com", "finance.yahoo.com",
                ],
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", "")[:500],
                "score": item.get("score", 0),
                "published_date": item.get("published_date", ""),
            })
        return results
    except requests.RequestException as e:
        logger.error("Tavily search failed: %s", str(e))
        return []


def search_financial_news(event):
    """
    Search for recent financial news about a ticker or company.

    Args:
        event: API Gateway proxy event with ticker in body.

    Returns:
        API Gateway proxy response with news articles.
    """
    body, err = _parse_body(event)
    if err:
        return err
    ticker = body.get("ticker", "").strip().upper()
    if not ticker:
        return _build_response(400, {"error": "Missing required field: ticker"})

    query = f"{ticker} stock financial news latest"
    results = _tavily_search(query, max_results=8)

    if not results:
        return _build_response(200, {
            "tool": "search_financial_news",
            "ticker": ticker,
            "message": f"No recent financial news found for {ticker}.",
            "articles": [],
        })

    return _build_response(200, {
        "tool": "search_financial_news",
        "ticker": ticker,
        "articles": results,
    })


def get_headlines(event):
    """
    Fetch top headlines for a ticker or company.

    Args:
        event: API Gateway proxy event with ticker in body.

    Returns:
        API Gateway proxy response with headline list.
    """
    body, err = _parse_body(event)
    if err:
        return err
    ticker = body.get("ticker", "").strip().upper()
    if not ticker:
        return _build_response(400, {"error": "Missing required field: ticker"})

    query = f"{ticker} stock headlines today"
    results = _tavily_search(query, max_results=10)

    if not results:
        return _build_response(200, {
            "tool": "get_headlines",
            "ticker": ticker,
            "message": f"No headlines found for {ticker}.",
            "headlines": [],
        })

    headlines = [
        {"title": r["title"], "url": r["url"], "published_date": r.get("published_date", "")}
        for r in results
    ]
    return _build_response(200, {
        "tool": "get_headlines",
        "ticker": ticker,
        "headlines": headlines,
    })


def get_news_sentiment(event):
    """
    Analyze news sentiment for a ticker by searching for recent articles
    and summarizing the overall tone.

    Args:
        event: API Gateway proxy event with ticker in body.

    Returns:
        API Gateway proxy response with sentiment analysis.
    """
    body, err = _parse_body(event)
    if err:
        return err
    ticker = body.get("ticker", "").strip().upper()
    if not ticker:
        return _build_response(400, {"error": "Missing required field: ticker"})

    positive_query = f"{ticker} stock positive outlook bullish"
    negative_query = f"{ticker} stock negative risk bearish"

    positive_results = _tavily_search(positive_query, max_results=5)
    negative_results = _tavily_search(negative_query, max_results=5)

    positive_score = sum(r.get("score", 0) for r in positive_results)
    negative_score = sum(r.get("score", 0) for r in negative_results)
    total = positive_score + negative_score

    if total > 0:
        sentiment_ratio = positive_score / total
        if sentiment_ratio > 0.6:
            sentiment = "Bullish"
        elif sentiment_ratio < 0.4:
            sentiment = "Bearish"
        else:
            sentiment = "Neutral"
    else:
        sentiment = "Insufficient Data"

    return _build_response(200, {
        "tool": "get_news_sentiment",
        "ticker": ticker,
        "sentiment": sentiment,
        "positive_signals": len(positive_results),
        "negative_signals": len(negative_results),
        "positive_articles": [{"title": r["title"], "url": r["url"]} for r in positive_results[:3]],
        "negative_articles": [{"title": r["title"], "url": r["url"]} for r in negative_results[:3]],
    })


# Tool routing map
TOOLS = {
    "search_financial_news": search_financial_news,
    "get_headlines": get_headlines,
    "get_news_sentiment": get_news_sentiment,
}


def lambda_handler(event, context):
    """
    Main Lambda entry point. Routes requests to the appropriate tool
    based on the path parameter from API Gateway proxy integration.

    Args:
        event: API Gateway proxy event.
        context: Lambda context object.

    Returns:
        API Gateway proxy response dict.
    """
    logger.info("News Search MCP request: %s", json.dumps({
        "path": event.get("path"),
        "httpMethod": event.get("httpMethod"),
    }))

    path = event.get("pathParameters", {}).get("proxy", "")
    tool_name = path.strip("/").split("/")[-1] if path else ""

    if tool_name not in TOOLS:
        return _build_response(404, {
            "error": f"Unknown tool: {tool_name}",
            "available_tools": list(TOOLS.keys()),
        })

    try:
        return TOOLS[tool_name](event)
    except Exception as e:
        logger.exception("Tool %s failed", tool_name)
        return _build_response(500, {
            "error": f"Internal error in {tool_name}",
            "message": str(e),
        })
