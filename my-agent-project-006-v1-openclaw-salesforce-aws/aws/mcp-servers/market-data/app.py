"""
Market Data MCP Server — Lambda handler.
Tools: get_quote, get_price_history, get_analyst_consensus,
       get_options_chain, get_earnings_calendar.
Uses Finnhub API (key from FINNHUB_API_KEY env var).
Falls back to yfinance for assets Finnhub free tier doesn't cover
(options chains, Treasury yields, commodities, indices like ^TNX, CL=F, GC=F).
"""

import os
import sys
import time
from datetime import datetime, timedelta, timezone

from mcp_protocol import McpServer

# ---- Hydrate API keys from Secrets Manager BEFORE reading env vars --------
# Keeps Lambda env vars free of plaintext keys. Local dev still works via
# direct env vars (loader never overwrites an already-set env var).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
from secrets_loader import hydrate_env_from_secret  # noqa: E402

hydrate_env_from_secret(
    "VENDOR_SECRET_NAME",
    required_keys=["FINNHUB_API_KEY"],
    default_secret_name="/006/vendors/market-data",
)

import requests

# ---------------------------------------------------------------------------
# Yahoo Finance REST fallback (no yfinance library needed — uses requests only)
# Covers indices (^GSPC, ^VIX), treasuries (^TNX), commodities (CL=F, GC=F)
# ---------------------------------------------------------------------------
YAHOO_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

def _yahoo_quote(symbol: str) -> dict | None:
    """Fetch a quote from Yahoo Finance REST API. Returns None on failure."""
    try:
        url = f"{YAHOO_BASE}/{symbol}"
        resp = requests.get(url, params={"interval": "1d", "range": "1d"},
                          headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if not resp.ok:
            return None
        data = resp.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return None
        meta = result[0].get("meta", {})
        return {
            "symbol": symbol,
            "price": meta.get("regularMarketPrice"),
            "open": meta.get("regularMarketOpen"),
            "high": meta.get("regularMarketDayHigh"),
            "low": meta.get("regularMarketDayLow"),
            "volume": meta.get("regularMarketVolume"),
            "previousClose": meta.get("previousClose"),
            "change": round(meta.get("regularMarketPrice", 0) - meta.get("previousClose", 0), 4) if meta.get("regularMarketPrice") and meta.get("previousClose") else None,
            "changePercent": round((meta.get("regularMarketPrice", 0) / meta.get("previousClose", 1) - 1) * 100, 4) if meta.get("previousClose") else None,
            "latestTradingDay": None,
            "dataSource": "Yahoo Finance",
        }
    except Exception:
        return None


def _yahoo_history(symbol: str, period: str, days: int) -> dict:
    """Fetch daily price history from Yahoo Finance chart API.

    Returns {symbol, period, prices: [...], dataSource}. Empty prices on failure.
    """
    range_map = {30: "1mo", 90: "3mo", 180: "6mo", 365: "1y"}
    yf_range = range_map.get(days, "3mo")
    try:
        url = f"{YAHOO_BASE}/{symbol}"
        resp = requests.get(
            url,
            params={"interval": "1d", "range": yf_range},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if not resp.ok:
            return {"symbol": symbol, "period": period, "prices": [],
                    "dataSource": "Yahoo Finance", "error": f"HTTP {resp.status_code}"}
        data = resp.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return {"symbol": symbol, "period": period, "prices": [], "dataSource": "Yahoo Finance"}
        r0 = result[0]
        timestamps = r0.get("timestamp", []) or []
        q = r0.get("indicators", {}).get("quote", [{}])[0]
        opens = q.get("open") or []
        highs = q.get("high") or []
        lows = q.get("low") or []
        closes = q.get("close") or []
        vols = q.get("volume") or []
        entries = []
        for i, ts in enumerate(timestamps):
            entries.append({
                "date": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"),
                "open": str(opens[i]) if i < len(opens) and opens[i] is not None else None,
                "high": str(highs[i]) if i < len(highs) and highs[i] is not None else None,
                "low": str(lows[i]) if i < len(lows) and lows[i] is not None else None,
                "close": str(closes[i]) if i < len(closes) and closes[i] is not None else None,
                "volume": str(vols[i]) if i < len(vols) and vols[i] is not None else None,
            })
        entries.reverse()
        return {"symbol": symbol, "period": period, "prices": entries, "dataSource": "Yahoo Finance"}
    except Exception as exc:
        return {"symbol": symbol, "period": period, "prices": [],
                "dataSource": "Yahoo Finance", "error": str(exc)[:100]}


def _yahoo_52week(symbol: str) -> dict | None:
    """Fetch 52-week high/low from Yahoo Finance. Returns None on failure.

    Yahoo quote meta endpoint exposes fiftyTwoWeekHigh/fiftyTwoWeekLow directly,
    which is more reliable than computing from history.
    """
    try:
        url = f"{YAHOO_BASE}/{symbol}"
        resp = requests.get(
            url,
            params={"interval": "1d", "range": "1y"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if not resp.ok:
            return None
        data = resp.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return None
        meta = result[0].get("meta", {})
        hi = meta.get("fiftyTwoWeekHigh")
        lo = meta.get("fiftyTwoWeekLow")
        if hi is None or lo is None:
            # Compute from 1y closes as backup
            q = result[0].get("indicators", {}).get("quote", [{}])[0]
            closes = [c for c in (q.get("close") or []) if c is not None]
            if not closes:
                return None
            hi = max(closes)
            lo = min(closes)
        return {
            "symbol": symbol,
            "fiftyTwoWeekHigh": hi,
            "fiftyTwoWeekLow": lo,
            "currentPrice": meta.get("regularMarketPrice"),
            "pctOff52WkHigh": round((meta.get("regularMarketPrice", 0) / hi - 1) * 100, 2) if hi else None,
            "pctAbove52WkLow": round((meta.get("regularMarketPrice", 0) / lo - 1) * 100, 2) if lo else None,
            "dataSource": "Yahoo Finance",
        }
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Constants — fail fast if API key is missing
# ---------------------------------------------------------------------------
FINNHUB_BASE = "https://finnhub.io/api/v1"
API_KEY = os.environ.get("FINNHUB_API_KEY")
if not API_KEY:
    raise RuntimeError("FINNHUB_API_KEY environment variable is required")


# ---------------------------------------------------------------------------
# Symbol alias map — last line of defense against the agent using a wrong
# ticker. Free-text aliases (lowercased) -> canonical Yahoo Finance symbol.
# Resolved BEFORE upstream provider calls, so "S&P 500" or "crude" still
# returns the right instrument.
# ---------------------------------------------------------------------------
SYMBOL_ALIASES = {
    # Indices
    "sp500": "^GSPC", "s&p500": "^GSPC", "s&p 500": "^GSPC", "spx": "^GSPC",
    "^spx": "^GSPC", "sandp500": "^GSPC", "sp 500": "^GSPC",
    "nasdaq": "^IXIC", "nasdaq composite": "^IXIC", "comp": "^IXIC",
    "nasdaq 100": "^NDX", "ndx": "^NDX", "^ndx": "^NDX",
    "dow": "^DJI", "dow jones": "^DJI", "djia": "^DJI",
    "russell 2000": "^RUT", "russell2000": "^RUT", "rut": "^RUT",
    "vix": "^VIX", "volatility index": "^VIX",
    "ftse": "^FTSE", "ftse 100": "^FTSE",
    "nikkei": "^N225", "nikkei 225": "^N225",
    # Treasuries (Yahoo ^TNX = 10Y yield * 10)
    "10y": "^TNX", "10yr": "^TNX", "10-year": "^TNX", "10-year treasury": "^TNX",
    "10 year treasury": "^TNX", "10y treasury": "^TNX", "ust10y": "^TNX",
    "30y": "^TYX", "30-year": "^TYX", "30-year treasury": "^TYX", "30 year treasury": "^TYX",
    "2y": "^IRX", "2-year": "^IRX", "2y treasury": "^IRX",
    "5y": "^FVX", "5-year": "^FVX",
    # Commodities (Yahoo continuous futures)
    "crude": "CL=F", "wti": "CL=F", "crude oil": "CL=F", "oil": "CL=F", "wti crude": "CL=F",
    "brent": "BZ=F", "brent crude": "BZ=F",
    "gold": "GC=F", "silver": "SI=F", "copper": "HG=F",
    "natgas": "NG=F", "natural gas": "NG=F",
    "gasoline": "RB=F", "heating oil": "HO=F",
    # Crypto
    "btc": "BTC-USD", "bitcoin": "BTC-USD",
    "eth": "ETH-USD", "ethereum": "ETH-USD",
    # FX
    "eurusd": "EURUSD=X", "eur/usd": "EURUSD=X",
    "usdjpy": "JPY=X", "usd/jpy": "JPY=X",
    "gbpusd": "GBPUSD=X", "gbp/usd": "GBPUSD=X",
    "dxy": "DX-Y.NYB", "dollar index": "DX-Y.NYB",
}

YAHOO_ONLY_PREFIXES = ("^",)
YAHOO_ONLY_SUFFIXES = ("=F", "-USD", "=X")


def resolve_symbol(raw: str) -> str:
    """Normalize user-provided ticker to a canonical symbol."""
    if not raw:
        return raw
    key = raw.strip().lower()
    if key in SYMBOL_ALIASES:
        return SYMBOL_ALIASES[key]
    if raw.startswith("^") or "=" in raw or "-USD" in raw.upper():
        return raw.upper()
    return raw.upper()


def _is_yahoo_only(symbol: str) -> bool:
    """True if the symbol must be fetched from Yahoo (not Finnhub)."""
    return symbol.startswith(YAHOO_ONLY_PREFIXES) or symbol.endswith(YAHOO_ONLY_SUFFIXES)


def _finnhub_request(endpoint: str, params: dict | None = None) -> dict | list:
    """Make a request to Finnhub and return parsed JSON.

    Handles rate-limit (429) and invalid-symbol responses gracefully.
    """
    params = params or {}
    params["token"] = API_KEY
    url = f"{FINNHUB_BASE}{endpoint}"
    resp = requests.get(url, params=params, timeout=15)

    # Rate limit — 60 calls/min on free tier
    if resp.status_code == 429:
        return {
            "error": True,
            "message": "Finnhub rate limit exceeded (60 calls/min). Please wait and retry.",
            "rate_limited": True,
        }

    resp.raise_for_status()
    data = resp.json()

    # Finnhub returns empty dict / {"s":"no_data"} for invalid symbols
    if isinstance(data, dict) and data.get("s") == "no_data":
        return {
            "error": True,
            "message": "No data returned — check that the symbol is valid.",
        }

    return data


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def handle_get_quote(params: dict) -> dict:
    """Get real-time quote for a stock symbol.

    Primary: Finnhub (faster, real-time for US equities).
    Fallback: Yahoo Finance (covers indices, treasuries, commodities, FX, crypto).
    Aliases: 'S&P 500' -> ^GSPC, '10y' -> ^TNX, 'crude' -> CL=F, etc.
    """
    symbol = resolve_symbol(params["symbol"])

    # Yahoo-only symbols skip Finnhub entirely
    if _is_yahoo_only(symbol):
        yahoo_result = _yahoo_quote(symbol)
        if yahoo_result:
            return yahoo_result
        return {
            "error": True,
            "message": f"No quote data for symbol '{symbol}' via Yahoo Finance.",
        }

    data = _finnhub_request("/quote", {"symbol": symbol})

    # If Finnhub returned valid data, use it
    finnhub_failed = (
        (isinstance(data, dict) and data.get("error"))
        or (isinstance(data, dict) and data.get("c", 0) == 0 and data.get("h", 0) == 0)
    )

    if not finnhub_failed:
        return {
            "symbol": symbol,
            "price": data.get("c"),
            "open": data.get("o"),
            "high": data.get("h"),
            "low": data.get("l"),
            "volume": None,  # Finnhub /quote does not return volume
            "previousClose": data.get("pc"),
            "change": data.get("d"),
            "changePercent": data.get("dp"),
            "latestTradingDay": None,  # Not provided by Finnhub /quote
            "dataSource": "Finnhub",
        }

    # Fallback to Yahoo Finance REST API for symbols Finnhub doesn't cover
    yahoo_result = _yahoo_quote(symbol)
    if yahoo_result:
        return yahoo_result

    return {
        "error": True,
        "message": f"No quote data for symbol '{symbol}' — verify it is a valid ticker.",
    }


def handle_get_price_history(params: dict) -> dict:
    """Get daily price history for a symbol.

    Finnhub for equities, Yahoo for indices/futures/FX/crypto.
    Falls back to Yahoo on any Finnhub failure.
    """
    symbol = resolve_symbol(params["symbol"])
    period = params.get("period", "3mo")
    period_days = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}
    days = period_days.get(period, 90)

    if _is_yahoo_only(symbol):
        return _yahoo_history(symbol, period, days)

    now = int(time.time())
    from_ts = now - (days * 86400)

    try:
        data = _finnhub_request("/stock/candle", {
            "symbol": symbol, "resolution": "D", "from": from_ts, "to": now,
        })
    except requests.RequestException as exc:
        fallback = _yahoo_history(symbol, period, days)
        if fallback.get("prices"):
            fallback["fallback_reason"] = f"Finnhub error: {str(exc)[:80]}"
            return fallback
        return {"error": True, "message": f"Price history unavailable for '{symbol}'"}

    if isinstance(data, dict) and (data.get("error") or data.get("s") != "ok"):
        fallback = _yahoo_history(symbol, period, days)
        if fallback.get("prices"):
            fallback["fallback_reason"] = "Finnhub returned no_data or error"
            return fallback
        return data if isinstance(data, dict) and data.get("error") else {
            "error": True, "message": f"No price history for '{symbol}'",
        }

    timestamps = data.get("t", [])
    closes = data.get("c", [])
    opens = data.get("o", [])
    highs = data.get("h", [])
    lows = data.get("l", [])
    volumes = data.get("v", [])

    entries = []
    for i in range(len(timestamps)):
        entries.append({
            "date": datetime.fromtimestamp(timestamps[i], tz=timezone.utc).strftime("%Y-%m-%d"),
            "open": str(opens[i]) if i < len(opens) else None,
            "high": str(highs[i]) if i < len(highs) else None,
            "low": str(lows[i]) if i < len(lows) else None,
            "close": str(closes[i]) if i < len(closes) else None,
            "volume": str(volumes[i]) if i < len(volumes) else None,
        })
    entries.reverse()
    return {"symbol": symbol, "period": period, "prices": entries, "dataSource": "Finnhub"}


def handle_get_52_week_range(params: dict) -> dict:
    """Get 52-week high/low directly via Yahoo Finance meta (most reliable)."""
    symbol = resolve_symbol(params["symbol"])
    result = _yahoo_52week(symbol)
    if result:
        return result
    return {"error": True, "message": f"52-week range unavailable for '{symbol}'"}


def handle_get_analyst_consensus(params: dict) -> dict:
    """Get analyst ratings and price target consensus via Finnhub."""
    symbol = resolve_symbol(params["symbol"])

    # Fetch recommendation trends
    recs = _finnhub_request("/stock/recommendation", {"symbol": symbol})
    if isinstance(recs, dict) and recs.get("error"):
        return recs

    # Fetch price target consensus
    targets = _finnhub_request("/stock/price-target", {"symbol": symbol})
    if isinstance(targets, dict) and targets.get("error"):
        return targets

    # Use the most recent recommendation period
    latest_rec = recs[0] if isinstance(recs, list) and recs else {}

    return {
        "symbol": symbol,
        "analystTargetPrice": targets.get("targetMean") if isinstance(targets, dict) else None,
        "targetHigh": targets.get("targetHigh") if isinstance(targets, dict) else None,
        "targetLow": targets.get("targetLow") if isinstance(targets, dict) else None,
        "targetMedian": targets.get("targetMedian") if isinstance(targets, dict) else None,
        "lastUpdated": targets.get("lastUpdated") if isinstance(targets, dict) else None,
        "analystRatingStrongBuy": latest_rec.get("strongBuy"),
        "analystRatingBuy": latest_rec.get("buy"),
        "analystRatingHold": latest_rec.get("hold"),
        "analystRatingSell": latest_rec.get("sell"),
        "analystRatingStrongSell": latest_rec.get("strongSell"),
        "recommendationPeriod": latest_rec.get("period"),
    }


def handle_get_options_chain(params: dict) -> dict:
    """Options chain — not available on Finnhub free tier. Yahoo Finance REST doesn't expose options easily."""
    symbol = resolve_symbol(params["symbol"])
    return {
        "symbol": symbol,
        "optionsCount": 0,
        "options": [],
        "message": (
            "Options chain data is not available through the current data providers. "
            "Use get_quote for current price and get_analyst_consensus for price targets."
        ),
    }


def handle_get_earnings_calendar(params: dict) -> dict:
    """Get upcoming earnings dates and estimates via Finnhub."""
    symbol = params.get("symbol", "")
    horizon = params.get("horizon", "3month")

    # Map horizon to date range
    horizon_days = {"3month": 90, "6month": 180, "12month": 365}
    days = horizon_days.get(horizon, 90)

    today = datetime.now(tz=timezone.utc).date()
    from_date = today.strftime("%Y-%m-%d")
    to_date = (today + timedelta(days=days)).strftime("%Y-%m-%d")

    data = _finnhub_request("/calendar/earnings", {
        "from": from_date,
        "to": to_date,
    })
    if isinstance(data, dict) and data.get("error"):
        return data

    earnings_list = []
    if isinstance(data, dict):
        earnings_list = data.get("earningsCalendar", [])

    # Filter by symbol if provided
    if symbol:
        symbol_upper = symbol.upper()
        earnings_list = [e for e in earnings_list if e.get("symbol", "").upper() == symbol_upper]

    # Limit to 50 results
    earnings_list = earnings_list[:50]

    earnings = []
    for e in earnings_list:
        earnings.append({
            "symbol": e.get("symbol", ""),
            "date": e.get("date", ""),
            "epsEstimate": e.get("epsEstimate"),
            "epsActual": e.get("epsActual"),
            "revenueEstimate": e.get("revenueEstimate"),
            "revenueActual": e.get("revenueActual"),
            "hour": e.get("hour", ""),
            "quarter": e.get("quarter"),
            "year": e.get("year"),
        })

    return {"symbol": symbol or "all", "horizon": horizon, "earnings": earnings}


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------
TOOLS = {
    "get_quote": {
        "description": (
            "Get real-time stock quote including price, volume, and change. "
            "Supports equities (AAPL), indices (^GSPC, ^VIX), treasuries (^TNX), "
            "and commodities (CL=F, GC=F) via Yahoo Finance fallback."
        ),
        "properties": {
            "symbol": {"type": "string", "description": "Ticker symbol (e.g. AAPL, ^TNX, CL=F, GC=F, ^GSPC, ^VIX)"},
        },
        "required": ["symbol"],
    },
    "get_price_history": {
        "description": "Get daily historical price data for a symbol. Returns up to 1 year. Falls back to Yahoo Finance if Finnhub fails.",
        "properties": {
            "symbol": {"type": "string", "description": "Stock ticker symbol"},
            "period": {"type": "string", "description": "Time period: 1mo, 3mo, 6mo, 1y (default 3mo)"},
        },
        "required": ["symbol"],
    },
    "get_52_week_range": {
        "description": "Get 52-week high, low, and current price for any symbol (equities, indices, futures). Prefer this over get_price_history when the user asks for 52-week range — it's more reliable and skips Finnhub.",
        "properties": {
            "symbol": {"type": "string", "description": "Ticker symbol (e.g. TSLA, ^GSPC, CL=F)"},
        },
        "required": ["symbol"],
    },
    "get_analyst_consensus": {
        "description": "Get analyst ratings, price targets, and valuation metrics.",
        "properties": {
            "symbol": {"type": "string", "description": "Stock ticker symbol"},
        },
        "required": ["symbol"],
    },
    "get_options_chain": {
        "description": (
            "Get options chain data (calls and puts) for a stock symbol. "
            "Powered by Yahoo Finance. Returns up to 25 calls and 25 puts."
        ),
        "properties": {
            "symbol": {"type": "string", "description": "Stock ticker symbol"},
            "date": {"type": "string", "description": "Expiration date (YYYY-MM-DD). Omit for nearest expiration."},
        },
        "required": ["symbol"],
    },
    "get_earnings_calendar": {
        "description": "Get upcoming earnings dates and EPS estimates.",
        "properties": {
            "symbol": {"type": "string", "description": "Stock ticker symbol (omit for all)"},
            "horizon": {"type": "string", "description": "Horizon: 3month, 6month, 12month (default 3month)"},
        },
        "required": [],
    },
}

HANDLERS = {
    "get_quote": handle_get_quote,
    "get_price_history": handle_get_price_history,
    "get_52_week_range": handle_get_52_week_range,
    "get_analyst_consensus": handle_get_analyst_consensus,
    "get_options_chain": handle_get_options_chain,
    "get_earnings_calendar": handle_get_earnings_calendar,
}

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------
server = McpServer(
    name="market-data",
    version="2.1.0",
    description=(
        "Market data — quotes, price history, analyst consensus, options, earnings. "
        "Powered by Finnhub (primary) with Yahoo Finance fallback for options, "
        "treasuries, commodities, and indices."
    ),
)

for tool_name, schema in TOOLS.items():
    server.register_tool(tool_name, schema, HANDLERS[tool_name])


def lambda_handler(event, context):
    """AWS Lambda entry point."""
    return server.handle(event)
