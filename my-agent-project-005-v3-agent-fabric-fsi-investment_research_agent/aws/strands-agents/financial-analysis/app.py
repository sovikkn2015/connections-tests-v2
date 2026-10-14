"""
Financial Analysis Agent — Lambda Handler (V3: A2A-compliant)

Provides financial analysis tools for investment research:
    GET  /financial-analysis/.well-known/agent.json  — A2A AgentCard manifest
    POST /financial-analysis/agent                    — A2A JSON-RPC task endpoint
    POST /financial-analysis/run_dcf                  — direct tool (V2 compat)
    POST /financial-analysis/run_comps                — direct tool (V2 compat)
    POST /financial-analysis/monte_carlo              — direct tool (V2 compat)
    POST /financial-analysis/fair_value               — direct tool (V2 compat)

V3 changes:
    - Routes ``.well-known/agent.json`` to a2a_manifest.handler
    - Routes ``POST /agent`` to a2a_handler.handler (JSON-RPC 2.0, tasks/send)
    - Keeps the V2 autonomous-agent natural-language fallback available
      via the legacy ``GET /agent`` flow when the body is empty.
    - Backward-compatible: all V2 direct tool endpoints still work.
"""

import json
import os
import logging
import random
import math
import time

import boto3

# --- Strands SDK import with graceful fallback ---
try:
    from strands import Agent, tool
    from strands.models import BedrockModel
    STRANDS_AVAILABLE = True
except ImportError:
    STRANDS_AVAILABLE = False
    # Fallback: define a no-op @tool decorator
    def tool(fn):
        """No-op decorator when strands-agents is not installed."""
        fn._is_tool = True
        return fn

# --- Langfuse wrapper ---
try:
    from langfuse_wrapper import (
        create_trace, add_span, add_generation, end_trace, get_prompt, is_configured,
    )
except ImportError:
    def create_trace(*a, **kw): return "no-trace"
    def add_span(*a, **kw): pass
    def add_generation(*a, **kw): pass
    def end_trace(*a, **kw): pass
    def get_prompt(name, fallback): return fallback
    def is_configured(): return False

# --- Salesforce client (bidirectional) ---
try:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
    from salesforce_client import SalesforceClient
    _sf_client = SalesforceClient()
except ImportError:
    _sf_client = None

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"
)


# ---------------------------------------------------------------------------
# Cached financial data for the 10 seed tickers (FALLBACK ONLY)
# Used when live market-data MCP is unavailable. Each entry includes a
# snapshot date so consumers know the data is stale.
# ---------------------------------------------------------------------------
_CACHED_DATA_DATE = "2026-04-08"

FINANCIAL_DATA = {
    "AAPL": {
        "name": "Apple Inc.", "sector": "Technology",
        "revenue_ttm": 383_285_000_000, "fcf_margin": 0.26,
        "pe_ratio": 33.5, "ev_ebitda": 26.1, "ps_ratio": 8.8,
        "volatility": 0.24, "current_price": 198.11,
    },
    "MSFT": {
        "name": "Microsoft Corp.", "sector": "Technology",
        "revenue_ttm": 227_583_000_000, "fcf_margin": 0.33,
        "pe_ratio": 37.2, "ev_ebitda": 27.8, "ps_ratio": 13.5,
        "volatility": 0.22, "current_price": 425.52,
    },
    "NVDA": {
        "name": "NVIDIA Corp.", "sector": "Technology",
        "revenue_ttm": 79_774_000_000, "fcf_margin": 0.51,
        "pe_ratio": 65.4, "ev_ebitda": 55.2, "ps_ratio": 37.1,
        "volatility": 0.48, "current_price": 135.40,
    },
    "AMZN": {
        "name": "Amazon.com Inc.", "sector": "Consumer Discretionary",
        "revenue_ttm": 604_334_000_000, "fcf_margin": 0.14,
        "pe_ratio": 60.8, "ev_ebitda": 22.3, "ps_ratio": 3.4,
        "volatility": 0.30, "current_price": 197.12,
    },
    "GOOGL": {
        "name": "Alphabet Inc.", "sector": "Technology",
        "revenue_ttm": 339_859_000_000, "fcf_margin": 0.24,
        "pe_ratio": 25.1, "ev_ebitda": 18.7, "ps_ratio": 6.5,
        "volatility": 0.27, "current_price": 176.49,
    },
    "JPM": {
        "name": "JPMorgan Chase & Co.", "sector": "Financials",
        "revenue_ttm": 162_367_000_000, "fcf_margin": 0.18,
        "pe_ratio": 12.4, "ev_ebitda": 9.8, "ps_ratio": 3.9,
        "volatility": 0.22, "current_price": 243.28,
    },
    "V": {
        "name": "Visa Inc.", "sector": "Financials",
        "revenue_ttm": 35_926_000_000, "fcf_margin": 0.52,
        "pe_ratio": 31.2, "ev_ebitda": 24.5, "ps_ratio": 16.8,
        "volatility": 0.20, "current_price": 317.45,
    },
    "JNJ": {
        "name": "Johnson & Johnson", "sector": "Healthcare",
        "revenue_ttm": 85_159_000_000, "fcf_margin": 0.22,
        "pe_ratio": 15.8, "ev_ebitda": 13.2, "ps_ratio": 4.5,
        "volatility": 0.16, "current_price": 155.72,
    },
    "XOM": {
        "name": "Exxon Mobil Corp.", "sector": "Energy",
        "revenue_ttm": 344_582_000_000, "fcf_margin": 0.10,
        "pe_ratio": 14.2, "ev_ebitda": 6.8, "ps_ratio": 1.5,
        "volatility": 0.25, "current_price": 113.98,
    },
    "TSLA": {
        "name": "Tesla Inc.", "sector": "Consumer Discretionary",
        "revenue_ttm": 96_773_000_000, "fcf_margin": 0.06,
        "pe_ratio": 72.3, "ev_ebitda": 48.9, "ps_ratio": 8.2,
        "volatility": 0.55, "current_price": 248.42,
    },
    "CRM": {
        "name": "Salesforce Inc.", "sector": "Technology",
        "revenue_ttm": 35_000_000_000, "fcf_margin": 0.33,
        "pe_ratio": 45.0, "ev_ebitda": 30.2, "ps_ratio": 7.5,
        "volatility": 0.32, "current_price": 272.00,
    },
}

SECTOR_PEERS = {
    "Technology": ["AAPL", "MSFT", "NVDA", "GOOGL", "CRM"],
    "Consumer Discretionary": ["AMZN", "TSLA"],
    "Financials": ["JPM", "V"],
    "Healthcare": ["JNJ"],
    "Energy": ["XOM"],
}


# ---------------------------------------------------------------------------
# Live data fetcher — calls market-data MCP, falls back to cached data
# ---------------------------------------------------------------------------
import requests as _requests

MCP_MARKET_DATA_URL = os.environ.get("MCP_MARKET_DATA_URL", "")
MCP_API_KEY = os.environ.get("MCP_API_KEY", "")


def _fetch_live_data(ticker: str) -> tuple:
    """Fetch financial data for a ticker, trying live MCP first, then cache.

    Returns:
        (data_dict, source_label) where source_label is "live" or "cached (YYYY-MM-DD)"
    """
    ticker = ticker.upper()

    # Try live market-data MCP if configured
    if MCP_MARKET_DATA_URL and MCP_API_KEY:
        try:
            quote_resp = _requests.post(
                f"{MCP_MARKET_DATA_URL}/tools/call",
                json={"name": "get_quote", "arguments": {"ticker": ticker}},
                headers={"x-api-key": MCP_API_KEY, "Content-Type": "application/json"},
                timeout=10,
            )
            overview_resp = _requests.post(
                f"{MCP_MARKET_DATA_URL}/tools/call",
                json={"name": "get_analyst_consensus", "arguments": {"ticker": ticker}},
                headers={"x-api-key": MCP_API_KEY, "Content-Type": "application/json"},
                timeout=10,
            )

            if quote_resp.ok and overview_resp.ok:
                quote_data = _parse_mcp_response(quote_resp.json())
                overview_data = _parse_mcp_response(overview_resp.json())

                quote = quote_data.get("quote", {})
                consensus = overview_data.get("consensus", {})

                price_str = quote.get("price", "")
                if price_str and price_str != "N/A":
                    live_price = float(price_str)
                    cached = FINANCIAL_DATA.get(ticker, {})

                    pe_str = consensus.get("pe_ratio", "")
                    pe = float(pe_str) if pe_str and pe_str != "N/A" else cached.get("pe_ratio", 20.0)
                    pm_str = consensus.get("profit_margin", "")
                    fcf_margin = float(pm_str) if pm_str and pm_str != "N/A" else cached.get("fcf_margin", 0.15)

                    live_data = {
                        "name": cached.get("name", ticker),
                        "sector": cached.get("sector", "Unknown"),
                        "revenue_ttm": cached.get("revenue_ttm", 100_000_000_000),
                        "fcf_margin": fcf_margin,
                        "pe_ratio": pe,
                        "ev_ebitda": cached.get("ev_ebitda", 15.0),
                        "ps_ratio": cached.get("ps_ratio", 5.0),
                        "volatility": cached.get("volatility", 0.30),
                        "current_price": live_price,
                    }
                    logger.info("Live data for %s: price=%.2f, P/E=%.1f", ticker, live_price, pe)
                    return live_data, "live"

        except Exception as exc:
            logger.warning("Live data fetch failed for %s: %s — using cache", ticker, exc)

    # Fallback to cached data
    if ticker in FINANCIAL_DATA:
        return FINANCIAL_DATA[ticker], f"cached ({_CACHED_DATA_DATE})"

    return {}, "not_found"


def _parse_mcp_response(body):
    """Parse an MCP response that may be wrapped in content[].text."""
    if "content" in body:
        for item in body.get("content", []):
            if item.get("type") == "text":
                text = item["text"]
                text = text.replace("[TOOL_OUTPUT_START]", "").replace("[TOOL_OUTPUT_END]", "")
                lines = text.strip().split("\n")
                json_lines = [l for l in lines if not l.startswith("[Source:") and not l.startswith("IMPORTANT:")]
                try:
                    return json.loads("\n".join(json_lines))
                except json.JSONDecodeError:
                    pass
    return body


# ---------------------------------------------------------------------------
# Tool 1: Discounted Cash Flow Model
# ---------------------------------------------------------------------------
@tool
def run_dcf(ticker: str, growth_rate: float = 0.12, discount_rate: float = 0.10,
            terminal_growth: float = 0.03) -> dict:
    """Run a simplified Discounted Cash Flow (DCF) valuation model for a stock ticker.

    Projects 5-year free cash flows from revenue and FCF margin data,
    discounts them at the WACC, and adds a Gordon-Growth terminal value
    to estimate intrinsic fair value per share.

    Args:
        ticker: Stock ticker symbol (e.g. 'NVDA', 'AAPL', 'MSFT').
        growth_rate: Assumed annual revenue growth rate (default 12%).
        discount_rate: Weighted average cost of capital / WACC (default 10%).
        terminal_growth: Perpetual growth rate for terminal value (default 3%).

    Returns:
        dict with fair value estimate, assumptions, and year-by-year projections.
    """
    ticker = ticker.upper()
    data, data_source = _fetch_live_data(ticker)
    if not data:
        return {"error": f"Ticker {ticker} not found. Supported: {list(FINANCIAL_DATA.keys())}"}

    revenue = data["revenue_ttm"]
    fcf_margin = data["fcf_margin"]
    current_price = data["current_price"]
    shares_outstanding = 1_000_000_000  # simplified assumption

    projections = []
    total_pv = 0.0
    for year in range(1, 6):
        proj_rev = revenue * ((1 + growth_rate) ** year)
        proj_fcf = proj_rev * fcf_margin
        pv_fcf = proj_fcf / ((1 + discount_rate) ** year)
        total_pv += pv_fcf
        projections.append({
            "year": year,
            "revenue_bn": round(proj_rev / 1e9, 2),
            "fcf_bn": round(proj_fcf / 1e9, 2),
            "pv_fcf_bn": round(pv_fcf / 1e9, 2),
        })

    year5_fcf = revenue * ((1 + growth_rate) ** 5) * fcf_margin
    terminal_value = year5_fcf * (1 + terminal_growth) / (discount_rate - terminal_growth)
    pv_terminal = terminal_value / ((1 + discount_rate) ** 5)
    total_pv += pv_terminal
    fair_value_ps = total_pv / shares_outstanding

    return {
        "ticker": ticker, "company": data["name"],
        "data_source": data_source,
        "fair_value_per_share": round(fair_value_ps, 2),
        "current_price": current_price,
        "upside_pct": round(((fair_value_ps / current_price) - 1) * 100, 1),
        "assumptions": {
            "growth_rate": growth_rate, "discount_rate": discount_rate,
            "terminal_growth": terminal_growth, "fcf_margin": fcf_margin,
            "revenue_ttm_bn": round(revenue / 1e9, 2),
        },
        "projections": projections,
        "terminal_value_bn": round(pv_terminal / 1e9, 2),
        "enterprise_value_bn": round(total_pv / 1e9, 2),
    }


# ---------------------------------------------------------------------------
# Tool 2: Comparable Company Analysis
# ---------------------------------------------------------------------------
@tool
def run_comps(ticker: str) -> dict:
    """Run comparable company analysis against sector peers for a stock ticker.

    Compares P/E, EV/EBITDA, and P/S valuation ratios of the target ticker
    against its sector peers to determine relative valuation (premium or discount).

    Args:
        ticker: Stock ticker symbol (e.g. 'NVDA', 'AAPL', 'MSFT').

    Returns:
        dict with peer comparison table and relative valuation assessment.
    """
    ticker = ticker.upper()
    data, data_source = _fetch_live_data(ticker)
    if not data:
        return {"error": f"Ticker {ticker} not found. Supported: {list(FINANCIAL_DATA.keys())}"}

    sector = data["sector"]
    peers = [t for t in SECTOR_PEERS.get(sector, []) if t != ticker]

    peer_data = []
    pe_vals = [data["pe_ratio"]]
    ev_vals = [data["ev_ebitda"]]
    ps_vals = [data["ps_ratio"]]

    for p in peers:
        pd_item, _ = _fetch_live_data(p)
        if not pd_item:
            continue
        peer_data.append({
            "ticker": p, "name": pd_item["name"],
            "pe_ratio": pd_item["pe_ratio"], "ev_ebitda": pd_item["ev_ebitda"],
            "ps_ratio": pd_item["ps_ratio"], "current_price": pd_item["current_price"],
        })
        pe_vals.append(pd_item["pe_ratio"])
        ev_vals.append(pd_item["ev_ebitda"])
        ps_vals.append(pd_item["ps_ratio"])

    avg_pe = sum(pe_vals) / len(pe_vals)
    avg_ev = sum(ev_vals) / len(ev_vals)
    avg_ps = sum(ps_vals) / len(ps_vals)

    def premium_label(val, avg):
        pct = ((val / avg) - 1) * 100 if avg else 0
        return f"{round(pct, 1)}% {'premium' if pct > 0 else 'discount'}"

    return {
        "ticker": ticker, "company": data["name"], "sector": sector,
        "data_source": data_source,
        "target_multiples": {
            "pe_ratio": data["pe_ratio"], "ev_ebitda": data["ev_ebitda"],
            "ps_ratio": data["ps_ratio"],
        },
        "peer_average": {
            "pe_ratio": round(avg_pe, 1), "ev_ebitda": round(avg_ev, 1),
            "ps_ratio": round(avg_ps, 1),
        },
        "relative_valuation": {
            "pe_vs_peers": premium_label(data["pe_ratio"], avg_pe),
            "ev_ebitda_vs_peers": premium_label(data["ev_ebitda"], avg_ev),
            "ps_vs_peers": premium_label(data["ps_ratio"], avg_ps),
        },
        "peers": peer_data,
        "current_price": data["current_price"],
    }


# ---------------------------------------------------------------------------
# Tool 3: Monte Carlo Simulation
# ---------------------------------------------------------------------------
@tool
def monte_carlo(ticker: str, simulations: int = 1000) -> dict:
    """Run Monte Carlo simulation for future stock price distribution over 1 year.

    Uses geometric Brownian motion with historical volatility to simulate
    252 trading days of price paths. Returns percentile price targets
    (5th, 25th, 50th, 75th, 95th) for risk assessment.

    Args:
        ticker: Stock ticker symbol (e.g. 'NVDA', 'AAPL', 'TSLA').
        simulations: Number of simulation paths to run (default 1000).

    Returns:
        dict with percentile prices, mean price, and simulation assumptions.
    """
    ticker = ticker.upper()
    data, data_source = _fetch_live_data(ticker)
    if not data:
        return {"error": f"Ticker {ticker} not found. Supported: {list(FINANCIAL_DATA.keys())}"}

    price = data["current_price"]
    vol = data["volatility"]
    drift = 0.08  # assumed annual drift (risk-free + equity premium)
    days = 252
    dt = 1.0 / days

    final_prices = []
    for _ in range(simulations):
        current = price
        for _ in range(days):
            u1 = random.random()
            u2 = random.random()
            z = math.sqrt(-2.0 * math.log(max(u1, 1e-10))) * math.cos(2.0 * math.pi * u2)
            daily_return = (drift - 0.5 * vol ** 2) * dt + vol * math.sqrt(dt) * z
            current *= math.exp(daily_return)
        final_prices.append(current)

    final_prices.sort()

    def percentile(pct):
        idx = min(int(len(final_prices) * pct / 100), len(final_prices) - 1)
        return round(final_prices[idx], 2)

    mean_price = sum(final_prices) / len(final_prices)

    return {
        "ticker": ticker, "company": data["name"],
        "data_source": data_source,
        "current_price": price, "simulations": simulations,
        "horizon": "1 year (252 trading days)",
        "percentiles": {
            "p5": percentile(5), "p25": percentile(25),
            "p50": percentile(50), "p75": percentile(75),
            "p95": percentile(95),
        },
        "mean_price": round(mean_price, 2),
        "assumptions": {
            "annual_volatility": vol, "annual_drift": drift,
            "model": "Geometric Brownian Motion",
        },
    }


# ---------------------------------------------------------------------------
# Tool 4: Fair Value (orchestrates all three + Bedrock LLM narrative)
# ---------------------------------------------------------------------------
@tool
def fair_value(ticker: str) -> dict:
    """Generate a comprehensive fair value report by orchestrating DCF, comps, and Monte Carlo analyses.

    Runs all three financial analysis tools, optionally enriches with
    Salesforce CRM company data, then calls Bedrock Claude to synthesize
    a narrative with bull/base/bear price targets.

    Args:
        ticker: Stock ticker symbol (e.g. 'NVDA', 'AAPL', 'MSFT').

    Returns:
        dict with combined analysis, LLM narrative, and bull/base/bear cases.
    """
    ticker = ticker.upper()
    data, data_source = _fetch_live_data(ticker)
    if not data:
        return {"error": f"Ticker {ticker} not found. Supported: {list(FINANCIAL_DATA.keys())}"}

    dcf_result = run_dcf(ticker=ticker)
    comps_result = run_comps(ticker=ticker)
    mc_result = monte_carlo(ticker=ticker, simulations=500)

    # Enrich with Salesforce CRM data if available (Gap 18)
    crm_context = {}
    if _sf_client and _sf_client.is_configured():
        try:
            crm_context = _sf_client.get_company_info(ticker)
        except Exception as exc:
            logger.warning("SF company info fetch failed for %s: %s", ticker, exc)

    analysis_context = json.dumps({
        "dcf": dcf_result,
        "comps": comps_result,
        "monte_carlo": mc_result,
        "crm_context": crm_context if crm_context else "No CRM data available",
    }, indent=2)

    default_prompt = (
        f"You are a senior equity research analyst. Based on the following "
        f"financial analysis data for {ticker}, write a concise fair value "
        f"summary with:\n"
        f"1. A one-paragraph executive summary\n"
        f"2. Bull case (optimistic scenario with price target)\n"
        f"3. Base case (most likely scenario with price target)\n"
        f"4. Bear case (pessimistic scenario with price target)\n"
        f"5. Key risks\n\n"
        f"Analysis data:\n{analysis_context}"
    )
    prompt_template = get_prompt("financial-analysis-fair-value", default_prompt)
    try:
        prompt = prompt_template.format(ticker=ticker, analysis_context=analysis_context)
    except (KeyError, IndexError):
        prompt = prompt_template

    try:
        client = boto3.client("bedrock-runtime")
        response = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )
        resp_body = json.loads(response["body"].read())
        narrative = resp_body["content"][0]["text"]
    except Exception as exc:
        logger.error("Bedrock call failed: %s", exc)
        narrative = (
            f"LLM narrative unavailable. Raw analysis: "
            f"DCF fair value ${dcf_result.get('fair_value_per_share', 'N/A')}, "
            f"Monte Carlo median ${mc_result.get('percentiles', {}).get('p50', 'N/A')}."
        )

    return {
        "ticker": ticker,
        "company": data["name"],
        "current_price": data["current_price"],
        "data_source": data_source,
        "dcf_fair_value": dcf_result.get("fair_value_per_share"),
        "monte_carlo_median": mc_result.get("percentiles", {}).get("p50"),
        "monte_carlo_range": {
            "low_5pct": mc_result.get("percentiles", {}).get("p5"),
            "high_95pct": mc_result.get("percentiles", {}).get("p95"),
        },
        "comps_summary": comps_result.get("relative_valuation"),
        "crm_context": crm_context if crm_context else None,
        "narrative": narrative,
        "raw": {"dcf": dcf_result, "comps": comps_result, "monte_carlo": mc_result},
    }


# ---------------------------------------------------------------------------
# Strands Agent Instance (V2)
# ---------------------------------------------------------------------------
AGENT_SYSTEM_PROMPT = (
    "You are a senior financial analysis agent specializing in equity research. "
    "You have access to four tools: run_dcf (DCF valuation), run_comps "
    "(comparable company analysis), monte_carlo (price simulation), and "
    "fair_value (comprehensive report combining all three). "
    "When given a query about a stock, reason about which tools to use and "
    "synthesize the results into a clear, actionable investment analysis. "
    "Supported tickers: AAPL, MSFT, NVDA, AMZN, GOOGL, JPM, V, JNJ, XOM, TSLA, CRM."
)

_agent_instance = None


def _get_agent():
    """Lazily initialize the Strands Agent with BedrockModel.

    Returns:
        Agent instance, or None if Strands SDK is not available.
    """
    global _agent_instance
    if _agent_instance is not None:
        return _agent_instance

    if not STRANDS_AVAILABLE:
        logger.warning("Strands SDK not available — agent endpoint disabled")
        return None

    try:
        model = BedrockModel(
            model_id=BEDROCK_MODEL_ID,
            max_tokens=2048,
        )
        _agent_instance = Agent(
            model=model,
            tools=[run_dcf, run_comps, monte_carlo, fair_value],
            system_prompt=get_prompt("financial-analysis-agent-system", AGENT_SYSTEM_PROMPT),
        )
        logger.info("Financial Analysis Strands Agent initialized")
        return _agent_instance
    except Exception as exc:
        logger.error("Failed to initialize Strands Agent: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------
TOOL_MAP = {
    "run_dcf": run_dcf,
    "run_comps": run_comps,
    "monte_carlo": monte_carlo,
    "fair_value": fair_value,
}


def lambda_handler(event, context):
    """AWS Lambda entry point for the Financial Analysis Agent.

    Routes requests based on the path parameter:
    - /financial-analysis/.well-known/agent.json — A2A AgentCard manifest
    - /financial-analysis/agent                   — A2A JSON-RPC endpoint (POST)
                                                    or V2 natural-language (legacy)
    - /financial-analysis/<tool>                  — direct tool invocation (V2)

    Every invocation creates a Langfuse trace.

    Args:
        event: API Gateway proxy event.
        context: Lambda context object.

    Returns:
        API Gateway proxy response with JSON body.
    """
    logger.info("Event: %s", json.dumps(event))

    try:
        path = event.get("pathParameters", {}).get("proxy", "") or ""
        segments = [s for s in path.strip("/").split("/") if s]
        tool_name = segments[0] if segments else ""
        http_method = (
            event.get("httpMethod")
            or event.get("requestContext", {}).get("http", {}).get("method")
            or ""
        ).upper()

        # --- V3: A2A AgentCard discovery endpoint ---
        if ".well-known" in segments:
            from a2a_manifest import handler as manifest_handler  # lazy import
            return manifest_handler(event, context)

        body_raw = event.get("body") or ""
        body = {}
        body_parse_error = False
        if body_raw:
            try:
                body = json.loads(body_raw) if isinstance(body_raw, str) else dict(body_raw)
            except (json.JSONDecodeError, TypeError):
                body = {}
                body_parse_error = True

        # --- V3: A2A task endpoint ---
        if tool_name == "agent":
            # JSON-RPC 2.0 request OR unparsable body (let A2A emit -32600)
            if http_method == "POST" and (body_parse_error or (isinstance(body, dict) and body.get("jsonrpc") == "2.0")):
                from a2a_handler import handler as a2a_task_handler
                return a2a_task_handler(event, context)
            # Legacy V2 natural-language query (back-compat)
            if http_method == "POST":
                return _handle_agent_request(body)
            # GET /agent => return the manifest for convenience
            if http_method == "GET":
                from a2a_manifest import handler as manifest_handler
                return manifest_handler(event, context)
            return _response(405, {"error": f"Method {http_method} not allowed on /agent"})

        # --- V2: Direct tool endpoints (backward compatible) ---
        ticker = (body.get("ticker") or "").upper() if isinstance(body, dict) else ""

        if not tool_name or tool_name not in TOOL_MAP:
            return _response(400, {
                "error": f"Unknown tool: '{tool_name}'",
                "available_tools": list(TOOL_MAP.keys()) + ["agent", ".well-known/agent.json"],
            })

        if not ticker:
            return _response(400, {"error": "Missing 'ticker' in request body."})

        # --- Langfuse trace ---
        trace_id = create_trace(
            f"financial-analysis-{tool_name}",
            input_data={"ticker": ticker, "tool": tool_name},
            metadata={"platform": "aws", "agent": "financial-analysis"},
        )

        kwargs = {"ticker": ticker}
        if tool_name == "run_dcf":
            for key in ("growth_rate", "discount_rate", "terminal_growth"):
                if key in body:
                    kwargs[key] = float(body[key])
        elif tool_name == "monte_carlo":
            if "simulations" in body:
                kwargs["simulations"] = int(body["simulations"])

        start_time = time.time()
        result = TOOL_MAP[tool_name](**kwargs)
        duration_ms = int((time.time() - start_time) * 1000)

        add_span(
            trace_id, tool_name,
            input_data={"ticker": ticker},
            output_data=result,
            duration_ms=duration_ms,
            metadata={"tool": tool_name},
        )
        end_trace(trace_id, output=result, metadata={"duration_ms": duration_ms})

        return _response(200, result)

    except Exception as exc:
        logger.exception("Unhandled error")
        return _response(500, {"error": str(exc)})


def _handle_agent_request(body):
    """Handle the autonomous agent endpoint (V2).

    Receives a natural language query, passes it to the Strands Agent,
    which reasons about which tools to call and returns a synthesized result.

    Args:
        body: Parsed JSON request body with 'query' field.

    Returns:
        API Gateway proxy response with agent result.
    """
    query = body.get("query", "").strip()
    if not query:
        return _response(400, {
            "error": "Missing 'query' in request body.",
            "example": {"query": "What is the fair value of NVDA? Run a DCF and comps analysis."},
        })

    trace_id = create_trace(
        "financial-analysis-agent",
        input_data={"query": query},
        metadata={"platform": "aws", "agent": "financial-analysis", "mode": "autonomous"},
    )

    agent = _get_agent()
    if agent is None:
        # Fallback: if Strands not available, try to extract ticker and run fair_value
        logger.warning("Agent unavailable — falling back to direct fair_value call")
        ticker = _extract_ticker_from_query(query)
        if ticker:
            result = fair_value(ticker=ticker)
            end_trace(trace_id, output=result, metadata={"fallback": True})
            return _response(200, {
                "mode": "fallback",
                "message": "Strands SDK not available. Ran fair_value directly.",
                "result": result,
            })
        return _response(503, {
            "error": "Agent not available and could not extract ticker from query.",
        })

    start_time = time.time()
    try:
        response = agent(query)
        duration_ms = int((time.time() - start_time) * 1000)

        result_text = str(response)

        add_span(
            trace_id, "agent_reasoning",
            input_data={"query": query},
            output_data=result_text,
            duration_ms=duration_ms,
            metadata={"mode": "autonomous"},
        )
        end_trace(trace_id, output=result_text, metadata={"duration_ms": duration_ms})

        return _response(200, {
            "mode": "agent",
            "query": query,
            "response": result_text,
        })

    except Exception as exc:
        logger.exception("Agent execution failed")
        end_trace(trace_id, output={"error": str(exc)})
        return _response(500, {"error": f"Agent execution failed: {exc}"})


def _extract_ticker_from_query(query):
    """Best-effort extraction of a ticker symbol from a natural language query.

    Args:
        query: Natural language query string.

    Returns:
        str: Extracted ticker or empty string.
    """
    query_upper = query.upper()
    for ticker in FINANCIAL_DATA:
        if ticker in query_upper:
            return ticker
    return ""


def _response(status_code, body):
    """Build an API Gateway proxy response.

    Args:
        status_code: HTTP status code.
        body: Response body (will be JSON-serialized).

    Returns:
        dict formatted as API Gateway proxy response.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }
