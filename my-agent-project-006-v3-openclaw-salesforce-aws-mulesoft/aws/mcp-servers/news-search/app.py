"""V3 news-search MCP server.

Tools:
- search_news(query, days_back) — Tavily-powered news search
- score_sentiment(text) — Bedrock Claude Sonnet sentiment scoring

Backend:
- Tavily (TAVILY_API_KEY env) for search
- Bedrock Claude Sonnet for sentiment (NOT Amazon Comprehend — steering)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _base import McpServer, McpUpstreamError, McpValidationError, ToolSpec  # noqa: E402

TAVILY_URL = "https://api.tavily.com/search"
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/company-news"
FINNHUB_GENERAL_NEWS_URL = "https://finnhub.io/api/v1/news"
MOCK_MODE = os.environ.get("NEWS_SEARCH_MODE", "live").lower() == "mock"
BEDROCK_REGION = os.environ.get("AWS_REGION_BEDROCK", "us-east-1")
SONNET_MODEL_ID = os.environ.get("BEDROCK_SONNET_MODEL_ID", "anthropic.claude-sonnet-4-5-20250929-v1:0")

# Quick-and-correct ticker extraction for the common case in this MCP's
# input. Keys pulled from the big-cap universe the demo covers; a full
# ticker resolver lives in market-data. Zero false positives here.
_KNOWN_TICKERS = {
    "NVDA", "MSFT", "AAPL", "TSLA", "META", "GOOGL", "GOOG", "AMZN",
    "AMD", "JPM", "GS", "BAC", "C", "WFC", "V", "MA", "PYPL", "COIN",
    "NFLX", "DIS", "INTC", "ORCL", "CRM", "IBM", "UBER", "LYFT",
}


def _validate_query(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise McpValidationError("'query' must be a non-empty string")
    if len(raw) > 500:
        raise McpValidationError("'query' too long (max 500 chars)")
    return raw.strip()


def _mock_search(query: str, days_back: int) -> dict:
    now = datetime.now(tz=timezone.utc)
    base = query.split()[0].upper() if query.split() else "MARKET"
    return {
        "query": query,
        "days_back": days_back,
        "results": [
            {
                "title": f"{base} beats Q1 revenue estimates on data-center strength",
                "url": "https://example-news.com/article-1",
                "published": (now - timedelta(days=1)).isoformat(),
                "snippet": f"{base} reported quarterly revenue above analyst consensus driven by AI infrastructure demand.",
                "source": "MockWire",
            },
            {
                "title": f"Analysts raise {base} price targets ahead of earnings",
                "url": "https://example-news.com/article-2",
                "published": (now - timedelta(days=3)).isoformat(),
                "snippet": f"Three major banks lifted {base} targets citing tighter supply and steady demand.",
                "source": "MockStreet",
            },
            {
                "title": f"Supply chain concerns weigh on {base} sentiment",
                "url": "https://example-news.com/article-3",
                "published": (now - timedelta(days=7)).isoformat(),
                "snippet": f"Geopolitical tensions and export controls add uncertainty to {base}'s outlook.",
                "source": "MockJournal",
            },
        ],
        "dataSource": "mock",
    }


def _mock_sentiment(text: str) -> dict:
    pos = {"beat", "raise", "strong", "growth", "positive", "upgrade", "record", "bullish"}
    neg = {"miss", "concern", "weak", "decline", "negative", "downgrade", "risk", "bearish"}
    tokens = text.lower().split()
    p = sum(1 for t in tokens if t in pos)
    n = sum(1 for t in tokens if t in neg)
    score = (p - n) / max(1, p + n)
    label = "positive" if score > 0.15 else "negative" if score < -0.15 else "neutral"
    return {
        "score": round(score, 4),
        "label": label,
        "confidence": round(min(1.0, (p + n) / 8), 2),
        "reasoning": f"Heuristic: {p} positive and {n} negative tokens",
        "dataSource": "mock",
    }


def _tavily_search(query: str, days_back: int) -> dict:
    if not TAVILY_API_KEY:
        raise McpUpstreamError("TAVILY_API_KEY not configured")
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                TAVILY_URL,
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "topic": "news",
                    "days": max(1, min(30, days_back)),
                    "max_results": 10,
                    "include_answer": False,
                },
            )
    except httpx.HTTPError as exc:
        raise McpUpstreamError(f"Tavily network error: {exc}") from exc
    if resp.status_code == 429:
        raise McpUpstreamError("Tavily rate limit", code=-32011)
    if not resp.is_success:
        raise McpUpstreamError(f"Tavily {resp.status_code}: {resp.text[:120]}")
    data = resp.json()
    results = []
    for r in data.get("results", []):
        results.append(
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "published": r.get("published_date", ""),
                "snippet": (r.get("content") or "")[:600],
                "source": r.get("source", ""),
            }
        )
    return {
        "query": query,
        "days_back": days_back,
        "results": results,
        "dataSource": "tavily",
    }


def _bedrock_sentiment(text: str) -> dict:
    try:
        import boto3
    except ImportError as exc:
        raise McpUpstreamError(f"boto3 not available: {exc}")

    client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)

    system = (
        "You are a financial news sentiment classifier. "
        "Return STRICT JSON only: {\"score\": float in [-1, 1], \"label\": \"positive|neutral|negative\", "
        "\"confidence\": float in [0, 1], \"reasoning\": string under 120 chars}. "
        "Positive = bullish for the equity. Negative = bearish."
    )

    try:
        resp = client.converse(
            modelId=SONNET_MODEL_ID,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": text[:6000]}]}],
            inferenceConfig={"maxTokens": 256, "temperature": 0.0},
        )
    except Exception as exc:
        raise McpUpstreamError(f"Bedrock sentiment call failed: {exc}") from exc

    content = resp.get("output", {}).get("message", {}).get("content", [])
    body = ""
    for part in content:
        if isinstance(part, dict) and part.get("text"):
            body = part["text"]
            break
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return {**_mock_sentiment(text), "dataSource": "bedrock-fallback-heuristic", "raw": body[:200]}

    score = max(-1.0, min(1.0, float(parsed.get("score", 0))))
    label = parsed.get("label", "neutral")
    if label not in {"positive", "neutral", "negative"}:
        label = "neutral"
    return {
        "score": round(score, 4),
        "label": label,
        "confidence": round(float(parsed.get("confidence", 0.5)), 2),
        "reasoning": str(parsed.get("reasoning", ""))[:200],
        "dataSource": "bedrock-sonnet",
    }


def _extract_ticker(query: str) -> str | None:
    """Find a known ticker symbol in the query. Case-insensitive match on
    whole-word tokens. Returns the first match or None."""
    import re

    for tok in re.findall(r"\b[A-Za-z]{2,5}\b", query):
        up = tok.upper()
        if up in _KNOWN_TICKERS:
            return up
    return None


def _finnhub_search(query: str, days_back: int) -> dict:
    """Fall back to Finnhub company-news when Tavily is rate-limited/over-quota.

    Tries two endpoints: company-news (needs a symbol) then general market news.
    Returns the same shape Tavily does so the downstream sentiment path is
    untouched.
    """
    if not FINNHUB_API_KEY:
        raise McpUpstreamError("FINNHUB_API_KEY not configured; Tavily was the primary and it failed")

    now = datetime.now(tz=timezone.utc)
    frm = (now - timedelta(days=max(1, min(30, days_back)))).strftime("%Y-%m-%d")
    to = now.strftime("%Y-%m-%d")

    symbol = _extract_ticker(query)
    try:
        with httpx.Client(timeout=15.0) as client:
            if symbol:
                resp = client.get(
                    FINNHUB_NEWS_URL,
                    params={"symbol": symbol, "from": frm, "to": to, "token": FINNHUB_API_KEY},
                )
            else:
                resp = client.get(
                    FINNHUB_GENERAL_NEWS_URL,
                    params={"category": "general", "token": FINNHUB_API_KEY},
                )
    except httpx.HTTPError as exc:
        raise McpUpstreamError(f"Finnhub network error: {exc}") from exc

    if not resp.is_success:
        raise McpUpstreamError(f"Finnhub {resp.status_code}: {resp.text[:120]}")

    data = resp.json() or []
    out = []
    q_lower = query.lower()
    for r in data:
        # When we have no symbol, filter the general-news feed by query keywords
        headline = (r.get("headline") or "").strip()
        summary = (r.get("summary") or "").strip()
        if not symbol and q_lower and q_lower not in (headline + " " + summary).lower():
            continue
        ts = r.get("datetime")
        published = (
            datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if isinstance(ts, (int, float)) else ""
        )
        out.append(
            {
                "title": headline,
                "url": r.get("url") or "",
                "published": published,
                "snippet": summary[:600],
                "source": r.get("source") or "finnhub",
            }
        )
        if len(out) >= 10:
            break

    return {
        "query": query,
        "days_back": days_back,
        "results": out,
        "dataSource": "finnhub",
        "fallback_reason": "tavily_unavailable",
    }


def handle_search_news(args: dict, ctx: dict) -> dict:
    query = _validate_query(args.get("query"))
    days_back = args.get("days_back", 7)
    if not isinstance(days_back, int) or days_back < 1 or days_back > 30:
        raise McpValidationError("'days_back' must be an integer in [1, 30]")

    if MOCK_MODE:
        return _mock_search(query, days_back)
    try:
        return _tavily_search(query, days_back)
    except McpUpstreamError as exc:
        # Tavily rate limit, quota, or transient — fall through to Finnhub.
        # Re-raise if Finnhub also isn't configured or fails: never silently
        # swap to mock data in live mode.
        return _finnhub_search(query, days_back)


def handle_score_sentiment(args: dict, ctx: dict) -> dict:
    text = args.get("text")
    if not isinstance(text, str) or not text.strip():
        raise McpValidationError("'text' must be a non-empty string")

    if MOCK_MODE:
        return _mock_sentiment(text)
    return _bedrock_sentiment(text)


server = McpServer(
    name="news-search",
    version="3.0.0",
    description="News search (Tavily) + LLM-based sentiment scoring (Bedrock Claude Sonnet).",
)

server.register(
    ToolSpec(
        name="search_news",
        description="Find recent news articles for a query. Returns up to 10 results.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "days_back": {"type": "integer", "minimum": 1, "maximum": 30, "default": 7},
            },
            "required": ["query"],
        },
    ),
    handle_search_news,
)
server.register(
    ToolSpec(
        name="score_sentiment",
        description=(
            "Score sentiment for a block of financial text. "
            "Backed by Bedrock Claude Sonnet — never Amazon Comprehend (per steering)."
        ),
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    ),
    handle_score_sentiment,
)


def lambda_handler(event, context):
    return server.handle(event, context)
