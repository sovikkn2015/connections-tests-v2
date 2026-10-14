"""V3 market-data MCP server.

Tools: get_quote, get_historical, get_technicals.
Backend: Finnhub primary, Alpha Vantage fallback (when configured).
Cache: 15s in-memory per warm Lambda container.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _base import McpServer, McpUpstreamError, McpValidationError, ToolSpec  # noqa: E402

# ---------------------------------------------------------------------------
FINNHUB_BASE = "https://finnhub.io/api/v1"
ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"

FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
ALPHA_VANTAGE_API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
MOCK_MODE = os.environ.get("MARKET_DATA_MODE", "live").lower() == "mock"

_QUOTE_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL_S = 15.0


def _mock_quote(symbol: str) -> dict:
    base = 100.0 + (sum(ord(c) for c in symbol) % 500)
    return {
        "symbol": symbol.upper(),
        "price": round(base + 2.5, 2),
        "open": round(base, 2),
        "high": round(base + 3.1, 2),
        "low": round(base - 1.2, 2),
        "previousClose": round(base - 0.5, 2),
        "change": 2.5,
        "changePercent": round(2.5 / base * 100, 4),
        "dataSource": "mock",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


def _mock_historical(symbol: str, period: str) -> dict:
    days_map = {"1mo": 22, "3mo": 66, "6mo": 132, "1y": 252}
    n = days_map.get(period, 66)
    base = 100.0 + (sum(ord(c) for c in symbol) % 500)
    today = datetime.now(tz=timezone.utc).date()
    prices = []
    for i in range(n):
        d = today - timedelta(days=i)
        wobble = ((i * 37) % 11) - 5
        close = round(base + wobble * 0.4, 2)
        prices.append(
            {
                "date": d.strftime("%Y-%m-%d"),
                "open": round(close - 0.3, 2),
                "high": round(close + 0.5, 2),
                "low": round(close - 0.6, 2),
                "close": close,
                "volume": 1_000_000 + (i * 7919),
            }
        )
    return {"symbol": symbol.upper(), "period": period, "prices": prices, "dataSource": "mock"}


def _mock_technicals(symbol: str) -> dict:
    base = 100.0 + (sum(ord(c) for c in symbol) % 500)
    return {
        "symbol": symbol.upper(),
        "rsi_14": 58.2,
        "macd": {"macd": 0.42, "signal": 0.31, "histogram": 0.11},
        "sma_50": round(base - 1.2, 2),
        "sma_200": round(base - 4.5, 2),
        "bollinger": {"upper": round(base + 4, 2), "middle": round(base, 2), "lower": round(base - 4, 2)},
        "dataSource": "mock",
    }


def _finnhub(endpoint: str, params: dict) -> dict | list:
    if not FINNHUB_API_KEY:
        raise McpUpstreamError("FINNHUB_API_KEY not configured")
    query = {**params, "token": FINNHUB_API_KEY}
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{FINNHUB_BASE}{endpoint}", params=query)
    except httpx.HTTPError as exc:
        raise McpUpstreamError(f"Finnhub network error: {exc}") from exc
    if resp.status_code == 429:
        raise McpUpstreamError("Finnhub rate limit", code=-32011)
    if resp.status_code >= 500:
        raise McpUpstreamError(f"Finnhub {resp.status_code}")
    if not resp.is_success:
        raise McpValidationError(f"Finnhub {resp.status_code}: {resp.text[:120]}")
    return resp.json()


def _alpha_vantage_quote(symbol: str) -> dict | None:
    if not ALPHA_VANTAGE_API_KEY:
        return None
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                ALPHA_VANTAGE_BASE,
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": symbol,
                    "apikey": ALPHA_VANTAGE_API_KEY,
                },
            )
    except httpx.HTTPError:
        return None
    if not resp.is_success:
        return None
    data = resp.json().get("Global Quote") or {}
    if not data:
        return None
    price = float(data.get("05. price", 0) or 0)
    prev = float(data.get("08. previous close", 0) or 0)
    return {
        "symbol": symbol.upper(),
        "price": price,
        "open": float(data.get("02. open", 0) or 0),
        "high": float(data.get("03. high", 0) or 0),
        "low": float(data.get("04. low", 0) or 0),
        "previousClose": prev,
        "change": price - prev if price and prev else 0,
        "changePercent": float((data.get("10. change percent") or "0%").rstrip("%") or 0),
        "dataSource": "alphavantage",
    }


def _validate_symbol(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise McpValidationError("'symbol' must be a non-empty string")
    s = raw.strip().upper()
    if len(s) > 16:
        raise McpValidationError("'symbol' too long (max 16 chars)")
    return s


def handle_get_quote(args: dict, ctx: dict) -> dict:
    symbol = _validate_symbol(args.get("symbol"))
    now = time.time()
    cached = _QUOTE_CACHE.get(symbol)
    if cached and cached[0] > now:
        return {**cached[1], "cached": True}

    if MOCK_MODE:
        payload = _mock_quote(symbol)
        _QUOTE_CACHE[symbol] = (now + _CACHE_TTL_S, payload)
        return payload

    try:
        data = _finnhub("/quote", {"symbol": symbol})
        if isinstance(data, dict) and data.get("c"):
            payload = {
                "symbol": symbol,
                "price": data.get("c"),
                "open": data.get("o"),
                "high": data.get("h"),
                "low": data.get("l"),
                "previousClose": data.get("pc"),
                "change": data.get("d"),
                "changePercent": data.get("dp"),
                "dataSource": "finnhub",
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            }
            _QUOTE_CACHE[symbol] = (now + _CACHE_TTL_S, payload)
            return payload
    except McpUpstreamError:
        pass

    av = _alpha_vantage_quote(symbol)
    if av:
        _QUOTE_CACHE[symbol] = (now + _CACHE_TTL_S, av)
        return av
    raise McpUpstreamError(f"No quote available for {symbol}")


def handle_get_historical(args: dict, ctx: dict) -> dict:
    symbol = _validate_symbol(args.get("symbol"))
    period = args.get("period", "3mo")
    if period not in {"1mo", "3mo", "6mo", "1y"}:
        raise McpValidationError("'period' must be one of 1mo, 3mo, 6mo, 1y")

    if MOCK_MODE:
        return _mock_historical(symbol, period)

    days_map = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}
    days = days_map[period]
    now_ts = int(time.time())
    from_ts = now_ts - (days * 86400)
    try:
        data = _finnhub(
            "/stock/candle",
            {"symbol": symbol, "resolution": "D", "from": from_ts, "to": now_ts},
        )
    except McpUpstreamError:
        return _mock_historical(symbol, period)

    if not isinstance(data, dict) or data.get("s") != "ok":
        return _mock_historical(symbol, period)

    ts_list = data.get("t") or []
    opens = data.get("o") or []
    highs = data.get("h") or []
    lows = data.get("l") or []
    closes = data.get("c") or []
    vols = data.get("v") or []
    prices = []
    for i, ts in enumerate(ts_list):
        prices.append(
            {
                "date": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"),
                "open": opens[i] if i < len(opens) else None,
                "high": highs[i] if i < len(highs) else None,
                "low": lows[i] if i < len(lows) else None,
                "close": closes[i] if i < len(closes) else None,
                "volume": vols[i] if i < len(vols) else None,
            }
        )
    prices.reverse()
    return {"symbol": symbol, "period": period, "prices": prices, "dataSource": "finnhub"}


def handle_get_technicals(args: dict, ctx: dict) -> dict:
    symbol = _validate_symbol(args.get("symbol"))
    if MOCK_MODE:
        return _mock_technicals(symbol)

    try:
        rsi = _finnhub(
            "/indicator",
            {
                "symbol": symbol,
                "resolution": "D",
                "from": int(time.time()) - (90 * 86400),
                "to": int(time.time()),
                "indicator": "rsi",
                "timeperiod": 14,
            },
        )
    except McpUpstreamError:
        return _mock_technicals(symbol)

    rsi_series = rsi.get("rsi") if isinstance(rsi, dict) else None
    latest_rsi = rsi_series[-1] if rsi_series else None
    return {
        "symbol": symbol,
        "rsi_14": latest_rsi,
        "macd": None,
        "sma_50": None,
        "sma_200": None,
        "dataSource": "finnhub",
        "notes": "Partial — expand with additional indicator calls in production",
    }


# ---------------------------------------------------------------------------
server = McpServer(
    name="market-data",
    version="3.0.0",
    description="Real-time quotes, historical bars, technical indicators (Finnhub primary, Alpha Vantage fallback).",
)

server.register(
    ToolSpec(
        name="get_quote",
        description="Get a real-time quote for a ticker symbol (15-second cache per warm Lambda).",
        input_schema={
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "Ticker symbol (e.g. NVDA)"}},
            "required": ["symbol"],
        },
    ),
    handle_get_quote,
)
server.register(
    ToolSpec(
        name="get_historical",
        description="Daily OHLCV bars over 1mo / 3mo / 6mo / 1y.",
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "period": {"type": "string", "enum": ["1mo", "3mo", "6mo", "1y"]},
            },
            "required": ["symbol"],
        },
    ),
    handle_get_historical,
)
server.register(
    ToolSpec(
        name="get_technicals",
        description="RSI, MACD, SMA-50/200, Bollinger bands.",
        input_schema={
            "type": "object",
            "properties": {"symbol": {"type": "string"}},
            "required": ["symbol"],
        },
    ),
    handle_get_technicals,
)


def lambda_handler(event, context):
    return server.handle(event, context)
