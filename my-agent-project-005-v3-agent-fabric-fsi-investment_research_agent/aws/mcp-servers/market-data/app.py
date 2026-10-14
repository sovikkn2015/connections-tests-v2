"""
Market Data MCP Server — Lambda Handler (V2: MCP Protocol)

V2 MCP Protocol Endpoints:
    GET  /market-data/              — Server info and capabilities
    POST /market-data/tools/list    — Tool catalog with JSON Schema
    POST /market-data/tools/call    — Invoke a tool by name with arguments

Legacy REST Endpoints (backward compatible):
    POST /market-data/get_quote, get_price_history, get_analyst_consensus, get_options_chain
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

ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"
API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "")


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


def _alpha_vantage_request(function, params=None):
    query_params = {"function": function, "apikey": API_KEY}
    if params:
        query_params.update(params)
    try:
        resp = requests.get(ALPHA_VANTAGE_BASE, params=query_params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if "Error Message" in data:
            logger.error("Alpha Vantage error: %s", data["Error Message"])
            return {}
        if "Note" in data:
            logger.warning("Alpha Vantage rate limit: %s", data["Note"])
            return {"rate_limited": True, "message": "API rate limit reached."}
        return data
    except requests.RequestException as e:
        logger.error("Alpha Vantage request failed: %s", str(e))
        return {}


# ---------------------------------------------------------------------------
# Core data functions
# ---------------------------------------------------------------------------
def _get_quote_data(ticker):
    data = _alpha_vantage_request("GLOBAL_QUOTE", {"symbol": ticker})
    quote = data.get("Global Quote", {})
    if not quote:
        return {"tool": "get_quote", "ticker": ticker, "message": f"No quote data for {ticker}.", "quote": {}}
    return {
        "tool": "get_quote", "ticker": ticker,
        "quote": {
            "price": quote.get("05. price", "N/A"), "change": quote.get("09. change", "N/A"),
            "change_percent": quote.get("10. change percent", "N/A"), "volume": quote.get("06. volume", "N/A"),
            "high": quote.get("03. high", "N/A"), "low": quote.get("04. low", "N/A"),
            "open": quote.get("02. open", "N/A"), "previous_close": quote.get("08. previous close", "N/A"),
            "latest_trading_day": quote.get("07. latest trading day", "N/A"),
        },
    }


def _get_price_history_data(ticker, period=30):
    data = _alpha_vantage_request("TIME_SERIES_DAILY", {"symbol": ticker, "outputsize": "compact"})
    time_series = data.get("Time Series (Daily)", {})
    if not time_series:
        return {"tool": "get_price_history", "ticker": ticker, "message": f"No price history for {ticker}.", "prices": []}
    sorted_dates = sorted(time_series.keys(), reverse=True)[:period]
    prices = []
    for date in sorted_dates:
        day = time_series[date]
        prices.append({
            "date": date, "open": day.get("1. open"), "high": day.get("2. high"),
            "low": day.get("3. low"), "close": day.get("4. close"), "volume": day.get("5. volume"),
        })
    return {"tool": "get_price_history", "ticker": ticker, "period_days": period, "prices": prices}


def _get_analyst_consensus_data(ticker):
    data = _alpha_vantage_request("OVERVIEW", {"symbol": ticker})
    if not data or data.get("rate_limited"):
        return {"tool": "get_analyst_consensus", "ticker": ticker, "message": data.get("message", f"No analyst data for {ticker}."), "consensus": {}}
    return {
        "tool": "get_analyst_consensus", "ticker": ticker,
        "consensus": {
            "analyst_target_price": data.get("AnalystTargetPrice", "N/A"),
            "pe_ratio": data.get("PERatio", "N/A"), "forward_pe": data.get("ForwardPE", "N/A"),
            "eps": data.get("EPS", "N/A"), "revenue_per_share": data.get("RevenuePerShareTTM", "N/A"),
            "profit_margin": data.get("ProfitMargin", "N/A"), "beta": data.get("Beta", "N/A"),
            "52_week_high": data.get("52WeekHigh", "N/A"), "52_week_low": data.get("52WeekLow", "N/A"),
            "dividend_yield": data.get("DividendYield", "N/A"),
        },
    }


def _get_options_chain_data(ticker):
    data = _alpha_vantage_request("OVERVIEW", {"symbol": ticker})
    if not data or data.get("rate_limited"):
        return {"tool": "get_options_chain", "ticker": ticker, "message": data.get("message", f"No options data for {ticker}."), "options_summary": {}}
    return {
        "tool": "get_options_chain", "ticker": ticker,
        "options_summary": {
            "beta": data.get("Beta", "N/A"), "52_week_high": data.get("52WeekHigh", "N/A"),
            "52_week_low": data.get("52WeekLow", "N/A"), "50_day_moving_avg": data.get("50DayMovingAverage", "N/A"),
            "200_day_moving_avg": data.get("200DayMovingAverage", "N/A"),
            "shares_outstanding": data.get("SharesOutstanding", "N/A"),
            "shares_short": data.get("SharesShort", "N/A"), "short_ratio": data.get("ShortRatio", "N/A"),
            "short_percent_outstanding": data.get("ShortPercentOutstanding", "N/A"),
        },
    }


# Legacy REST handlers
def get_quote(event):
    body, err = _parse_body(event)
    if err: return err
    ticker = body.get("ticker", "").strip().upper()
    if not ticker: return _build_response(400, {"error": "Missing required field: ticker"})
    return _build_response(200, _get_quote_data(ticker))

def get_price_history(event):
    body, err = _parse_body(event)
    if err: return err
    ticker = body.get("ticker", "").strip().upper()
    if not ticker: return _build_response(400, {"error": "Missing required field: ticker"})
    return _build_response(200, _get_price_history_data(ticker, int(body.get("period", 30))))

def get_analyst_consensus(event):
    body, err = _parse_body(event)
    if err: return err
    ticker = body.get("ticker", "").strip().upper()
    if not ticker: return _build_response(400, {"error": "Missing required field: ticker"})
    return _build_response(200, _get_analyst_consensus_data(ticker))

def get_options_chain(event):
    body, err = _parse_body(event)
    if err: return err
    ticker = body.get("ticker", "").strip().upper()
    if not ticker: return _build_response(400, {"error": "Missing required field: ticker"})
    return _build_response(200, _get_options_chain_data(ticker))


# MCP Protocol tool handlers
def _mcp_get_quote(args):
    t = args.get("ticker", "").strip().upper()
    return {"error": "Missing ticker"} if not t else _get_quote_data(t)

def _mcp_get_price_history(args):
    t = args.get("ticker", "").strip().upper()
    return {"error": "Missing ticker"} if not t else _get_price_history_data(t, int(args.get("period", 30)))

def _mcp_get_analyst_consensus(args):
    t = args.get("ticker", "").strip().upper()
    return {"error": "Missing ticker"} if not t else _get_analyst_consensus_data(t)

def _mcp_get_options_chain(args):
    t = args.get("ticker", "").strip().upper()
    return {"error": "Missing ticker"} if not t else _get_options_chain_data(t)


# MCP Server instance
TICKER_SCHEMA = {"type": "object", "properties": {"ticker": {"type": "string", "description": "Stock ticker symbol"}}, "required": ["ticker"]}
PRICE_HISTORY_SCHEMA = {"type": "object", "properties": {"ticker": {"type": "string", "description": "Stock ticker symbol"}, "period": {"type": "integer", "description": "Days of history (default 30)", "default": 30}}, "required": ["ticker"]}

_mcp_server = None

def _get_mcp_server():
    global _mcp_server
    if _mcp_server is not None: return _mcp_server
    if not MCP_AVAILABLE: return None
    _mcp_server = McpServer(name="market-data", version="2.0.0", description="Market data MCP server — quotes, history, analyst consensus, options")
    _mcp_server.register_tool("get_quote", "Fetch current stock quote", TICKER_SCHEMA, _mcp_get_quote)
    _mcp_server.register_tool("get_price_history", "Fetch historical daily prices", PRICE_HISTORY_SCHEMA, _mcp_get_price_history)
    _mcp_server.register_tool("get_analyst_consensus", "Fetch analyst consensus estimates", TICKER_SCHEMA, _mcp_get_analyst_consensus)
    _mcp_server.register_tool("get_options_chain", "Fetch options chain summary", TICKER_SCHEMA, _mcp_get_options_chain)
    return _mcp_server


TOOLS = {"get_quote": get_quote, "get_price_history": get_price_history, "get_analyst_consensus": get_analyst_consensus, "get_options_chain": get_options_chain}


def lambda_handler(event, context):
    """Main Lambda entry point. MCP protocol first, then legacy REST."""
    logger.info("Market Data MCP request: %s", json.dumps({"path": event.get("path"), "httpMethod": event.get("httpMethod")}))
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
