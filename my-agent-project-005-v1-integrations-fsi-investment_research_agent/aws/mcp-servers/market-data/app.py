"""
Market Data MCP Server — Lambda Handler

Provides tools for fetching real-time stock quotes, price history,
analyst consensus estimates, and options chain data via Alpha Vantage API.

Routes:
    POST /market-data/get_quote            — Current stock quote
    POST /market-data/get_price_history    — Historical prices
    POST /market-data/get_analyst_consensus — Analyst consensus estimates
    POST /market-data/get_options_chain    — Options data summary
"""

import json
import os
import logging

import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"
API_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "")


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


def _alpha_vantage_request(function, params=None):
    """
    Make a request to the Alpha Vantage API.

    Args:
        function: Alpha Vantage API function name.
        params: Additional query parameters.

    Returns:
        Parsed JSON response dict, or empty dict on failure.
    """
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
            return {"rate_limited": True, "message": "API rate limit reached. Please try again shortly."}
        return data
    except requests.RequestException as e:
        logger.error("Alpha Vantage request failed: %s", str(e))
        return {}


def get_quote(event):
    """
    Fetch the current stock quote for a ticker.

    Args:
        event: API Gateway proxy event with ticker in body.

    Returns:
        API Gateway proxy response with quote data.
    """
    body, err = _parse_body(event)
    if err:
        return err
    ticker = body.get("ticker", "").strip().upper()
    if not ticker:
        return _build_response(400, {"error": "Missing required field: ticker"})

    data = _alpha_vantage_request("GLOBAL_QUOTE", {"symbol": ticker})
    quote = data.get("Global Quote", {})

    if not quote:
        return _build_response(200, {
            "tool": "get_quote",
            "ticker": ticker,
            "message": f"No quote data available for {ticker}.",
            "quote": {},
        })

    return _build_response(200, {
        "tool": "get_quote",
        "ticker": ticker,
        "quote": {
            "price": quote.get("05. price", "N/A"),
            "change": quote.get("09. change", "N/A"),
            "change_percent": quote.get("10. change percent", "N/A"),
            "volume": quote.get("06. volume", "N/A"),
            "high": quote.get("03. high", "N/A"),
            "low": quote.get("04. low", "N/A"),
            "open": quote.get("02. open", "N/A"),
            "previous_close": quote.get("08. previous close", "N/A"),
            "latest_trading_day": quote.get("07. latest trading day", "N/A"),
        },
    })


def get_price_history(event):
    """
    Fetch historical price data for a ticker.

    Args:
        event: API Gateway proxy event with ticker and optional period in body.
            period defaults to 30 (days).

    Returns:
        API Gateway proxy response with price history.
    """
    body, err = _parse_body(event)
    if err:
        return err
    ticker = body.get("ticker", "").strip().upper()
    if not ticker:
        return _build_response(400, {"error": "Missing required field: ticker"})

    period = int(body.get("period", 30))
    data = _alpha_vantage_request("TIME_SERIES_DAILY", {
        "symbol": ticker,
        "outputsize": "compact",
    })

    time_series = data.get("Time Series (Daily)", {})
    if not time_series:
        return _build_response(200, {
            "tool": "get_price_history",
            "ticker": ticker,
            "message": f"No price history available for {ticker}.",
            "prices": [],
        })

    sorted_dates = sorted(time_series.keys(), reverse=True)[:period]
    prices = []
    for date in sorted_dates:
        day = time_series[date]
        prices.append({
            "date": date,
            "open": day.get("1. open"),
            "high": day.get("2. high"),
            "low": day.get("3. low"),
            "close": day.get("4. close"),
            "volume": day.get("5. volume"),
        })

    return _build_response(200, {
        "tool": "get_price_history",
        "ticker": ticker,
        "period_days": period,
        "prices": prices,
    })


def get_analyst_consensus(event):
    """
    Fetch analyst consensus estimates for a ticker using Alpha Vantage overview.

    Args:
        event: API Gateway proxy event with ticker in body.

    Returns:
        API Gateway proxy response with analyst consensus data.
    """
    body, err = _parse_body(event)
    if err:
        return err
    ticker = body.get("ticker", "").strip().upper()
    if not ticker:
        return _build_response(400, {"error": "Missing required field: ticker"})

    data = _alpha_vantage_request("OVERVIEW", {"symbol": ticker})
    if not data or data.get("rate_limited"):
        return _build_response(200, {
            "tool": "get_analyst_consensus",
            "ticker": ticker,
            "message": data.get("message", f"No analyst data available for {ticker}."),
            "consensus": {},
        })

    return _build_response(200, {
        "tool": "get_analyst_consensus",
        "ticker": ticker,
        "consensus": {
            "analyst_target_price": data.get("AnalystTargetPrice", "N/A"),
            "pe_ratio": data.get("PERatio", "N/A"),
            "forward_pe": data.get("ForwardPE", "N/A"),
            "eps": data.get("EPS", "N/A"),
            "revenue_per_share": data.get("RevenuePerShareTTM", "N/A"),
            "profit_margin": data.get("ProfitMargin", "N/A"),
            "beta": data.get("Beta", "N/A"),
            "52_week_high": data.get("52WeekHigh", "N/A"),
            "52_week_low": data.get("52WeekLow", "N/A"),
            "dividend_yield": data.get("DividendYield", "N/A"),
        },
    })


def get_options_chain(event):
    """
    Fetch options chain summary for a ticker.

    Note: Alpha Vantage free tier has limited options data. Returns
    available overview metrics related to options/volatility.

    Args:
        event: API Gateway proxy event with ticker in body.

    Returns:
        API Gateway proxy response with options-related data.
    """
    body, err = _parse_body(event)
    if err:
        return err
    ticker = body.get("ticker", "").strip().upper()
    if not ticker:
        return _build_response(400, {"error": "Missing required field: ticker"})

    data = _alpha_vantage_request("OVERVIEW", {"symbol": ticker})
    if not data or data.get("rate_limited"):
        return _build_response(200, {
            "tool": "get_options_chain",
            "ticker": ticker,
            "message": data.get("message", f"No options data available for {ticker}."),
            "options_summary": {},
        })

    return _build_response(200, {
        "tool": "get_options_chain",
        "ticker": ticker,
        "options_summary": {
            "beta": data.get("Beta", "N/A"),
            "52_week_high": data.get("52WeekHigh", "N/A"),
            "52_week_low": data.get("52WeekLow", "N/A"),
            "50_day_moving_avg": data.get("50DayMovingAverage", "N/A"),
            "200_day_moving_avg": data.get("200DayMovingAverage", "N/A"),
            "shares_outstanding": data.get("SharesOutstanding", "N/A"),
            "shares_short": data.get("SharesShort", "N/A"),
            "short_ratio": data.get("ShortRatio", "N/A"),
            "short_percent_outstanding": data.get("ShortPercentOutstanding", "N/A"),
        },
    })


# Tool routing map
TOOLS = {
    "get_quote": get_quote,
    "get_price_history": get_price_history,
    "get_analyst_consensus": get_analyst_consensus,
    "get_options_chain": get_options_chain,
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
    logger.info("Market Data MCP request: %s", json.dumps({
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
