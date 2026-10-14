"""
Financial Analysis Agent — Lambda Handler

Provides financial analysis tools for investment research:
    POST /financial-analysis/run_dcf         — Discounted Cash Flow model
    POST /financial-analysis/run_comps       — Comparable company analysis
    POST /financial-analysis/monte_carlo     — Monte Carlo price simulation
    POST /financial-analysis/fair_value      — Orchestrated fair value (uses Bedrock LLM)

Tools run as pure Python functions except fair_value, which calls
Bedrock Claude Sonnet 4 to synthesize a narrative from all three analyses.
No external dependencies beyond boto3 (included in Lambda runtime).
"""

import json
import os
import logging
import random
import math
import time
import boto3
from langfuse_wrapper import (
    create_trace, add_span, add_generation, end_trace, get_prompt, is_configured,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"
)

# ---------------------------------------------------------------------------
# Hardcoded financial data for the 10 seed tickers
# Each entry: revenue (TTM), FCF margin, P/E, EV/EBITDA, P/S,
#             historical volatility (annualized), current price
# ---------------------------------------------------------------------------
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
}

SECTOR_PEERS = {
    "Technology": ["AAPL", "MSFT", "NVDA", "GOOGL"],
    "Consumer Discretionary": ["AMZN", "TSLA"],
    "Financials": ["JPM", "V"],
    "Healthcare": ["JNJ"],
    "Energy": ["XOM"],
}


# ---------------------------------------------------------------------------
# Tool 1: Discounted Cash Flow Model
# ---------------------------------------------------------------------------
def run_dcf(ticker, growth_rate=0.12, discount_rate=0.10, terminal_growth=0.03):
    """Run a simplified DCF model for the given ticker.

    Projects 5-year free cash flows from hardcoded revenue/FCF-margin data,
    discounts them at the WACC, and adds a Gordon-Growth terminal value.

    Args:
        ticker: Stock ticker symbol (e.g. 'NVDA').
        growth_rate: Assumed annual revenue growth rate (default 12%).
        discount_rate: Weighted average cost of capital (default 10%).
        terminal_growth: Perpetual growth rate for terminal value (default 3%).

    Returns:
        dict with fair value estimate, assumptions, and year-by-year projections.
    """
    ticker = ticker.upper()
    if ticker not in FINANCIAL_DATA:
        return {"error": f"Ticker {ticker} not found. Supported: {list(FINANCIAL_DATA.keys())}"}

    data = FINANCIAL_DATA[ticker]
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
def run_comps(ticker):
    """Run comparable company analysis against sector peers.

    Compares P/E, EV/EBITDA, and P/S ratios of the target ticker against
    its sector peers from hardcoded data.

    Args:
        ticker: Stock ticker symbol (e.g. 'NVDA').

    Returns:
        dict with peer comparison table and relative valuation assessment.
    """
    ticker = ticker.upper()
    if ticker not in FINANCIAL_DATA:
        return {"error": f"Ticker {ticker} not found. Supported: {list(FINANCIAL_DATA.keys())}"}

    data = FINANCIAL_DATA[ticker]
    sector = data["sector"]
    peers = [t for t in SECTOR_PEERS.get(sector, []) if t != ticker]

    peer_data = []
    pe_vals = [data["pe_ratio"]]
    ev_vals = [data["ev_ebitda"]]
    ps_vals = [data["ps_ratio"]]

    for p in peers:
        pd = FINANCIAL_DATA[p]
        peer_data.append({
            "ticker": p, "name": pd["name"],
            "pe_ratio": pd["pe_ratio"], "ev_ebitda": pd["ev_ebitda"],
            "ps_ratio": pd["ps_ratio"], "current_price": pd["current_price"],
        })
        pe_vals.append(pd["pe_ratio"])
        ev_vals.append(pd["ev_ebitda"])
        ps_vals.append(pd["ps_ratio"])

    avg_pe = sum(pe_vals) / len(pe_vals)
    avg_ev = sum(ev_vals) / len(ev_vals)
    avg_ps = sum(ps_vals) / len(ps_vals)

    def premium_label(val, avg):
        """Return a human-readable premium/discount label."""
        pct = ((val / avg) - 1) * 100 if avg else 0
        return f"{round(pct, 1)}% {'premium' if pct > 0 else 'discount'}"

    return {
        "ticker": ticker, "company": data["name"], "sector": sector,
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
def monte_carlo(ticker, simulations=1000):
    """Run Monte Carlo simulation for future price distribution.

    Uses geometric Brownian motion with hardcoded historical volatility
    to simulate 252 trading days (1 year) of price paths.  Uses Python's
    built-in random module (no numpy dependency).

    Args:
        ticker: Stock ticker symbol (e.g. 'NVDA').
        simulations: Number of simulation paths (default 1000).

    Returns:
        dict with percentile prices (5th/25th/50th/75th/95th) and statistics.
    """
    ticker = ticker.upper()
    if ticker not in FINANCIAL_DATA:
        return {"error": f"Ticker {ticker} not found. Supported: {list(FINANCIAL_DATA.keys())}"}

    data = FINANCIAL_DATA[ticker]
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
        """Calculate the value at a given percentile."""
        idx = min(int(len(final_prices) * pct / 100), len(final_prices) - 1)
        return round(final_prices[idx], 2)

    mean_price = sum(final_prices) / len(final_prices)

    return {
        "ticker": ticker, "company": data["name"],
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
def fair_value(ticker, _trace_id=None):
    """Orchestrate DCF, comps, and Monte Carlo into a combined fair value report.

    Runs all three analysis tools, then calls Bedrock Claude Sonnet 4 to
    synthesize a narrative with bull/base/bear cases.

    Args:
        ticker: Stock ticker symbol (e.g. 'NVDA').
        _trace_id: Internal trace ID for Langfuse (set by lambda_handler).

    Returns:
        dict with combined analysis and LLM-generated narrative summary.
    """
    ticker = ticker.upper()
    if ticker not in FINANCIAL_DATA:
        return {"error": f"Ticker {ticker} not found. Supported: {list(FINANCIAL_DATA.keys())}"}

    dcf_result = run_dcf(ticker)
    comps_result = run_comps(ticker)
    mc_result = monte_carlo(ticker, simulations=500)

    analysis_context = json.dumps(
        {"dcf": dcf_result, "comps": comps_result, "monte_carlo": mc_result},
        indent=2,
    )

    # Fetch prompt from Langfuse registry (falls back to hardcoded default)
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
    # If the fetched prompt contains {ticker} or {analysis_context}, format it
    try:
        prompt = prompt_template.format(ticker=ticker, analysis_context=analysis_context)
    except (KeyError, IndexError):
        prompt = prompt_template

    try:
        client = boto3.client("bedrock-runtime")
        gen_start = time.time()
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
        gen_duration_ms = int((time.time() - gen_start) * 1000)
        resp_body = json.loads(response["body"].read())
        narrative = resp_body["content"][0]["text"]
        usage = resp_body.get("usage", {})

        # Log the Bedrock generation to Langfuse
        if _trace_id:
            add_generation(
                _trace_id, "fair_value_narrative",
                model=BEDROCK_MODEL_ID,
                input_data=prompt,
                output_data=narrative,
                usage={
                    "promptTokens": usage.get("input_tokens", 0),
                    "completionTokens": usage.get("output_tokens", 0),
                },
            )
    except Exception as exc:
        logger.error("Bedrock call failed: %s", exc)
        narrative = (
            f"LLM narrative unavailable. Raw analysis: "
            f"DCF fair value ${dcf_result.get('fair_value_per_share', 'N/A')}, "
            f"Monte Carlo median ${mc_result.get('percentiles', {}).get('p50', 'N/A')}."
        )

    return {
        "ticker": ticker,
        "company": FINANCIAL_DATA[ticker]["name"],
        "current_price": FINANCIAL_DATA[ticker]["current_price"],
        "dcf_fair_value": dcf_result.get("fair_value_per_share"),
        "monte_carlo_median": mc_result.get("percentiles", {}).get("p50"),
        "monte_carlo_range": {
            "low_5pct": mc_result.get("percentiles", {}).get("p5"),
            "high_95pct": mc_result.get("percentiles", {}).get("p95"),
        },
        "comps_summary": comps_result.get("relative_valuation"),
        "narrative": narrative,
        "raw": {"dcf": dcf_result, "comps": comps_result, "monte_carlo": mc_result},
    }


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

    Routes requests based on the path parameter to the appropriate tool.
    Every invocation creates a Langfuse trace. Bedrock LLM calls (fair_value)
    also produce generation events.

    Args:
        event: API Gateway proxy event.
        context: Lambda context object.

    Returns:
        API Gateway proxy response with JSON body.
    """
    logger.info("Event: %s", json.dumps(event))

    try:
        path = event.get("pathParameters", {}).get("proxy", "")
        tool_name = path.strip("/").split("/")[0] if path else ""

        body = json.loads(event.get("body", "{}") or "{}")
        ticker = body.get("ticker", "").upper()

        if not tool_name or tool_name not in TOOL_MAP:
            return _response(400, {
                "error": f"Unknown tool: '{tool_name}'",
                "available_tools": list(TOOL_MAP.keys()),
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
        elif tool_name == "fair_value":
            kwargs["_trace_id"] = trace_id

        start_time = time.time()
        result = TOOL_MAP[tool_name](**kwargs)
        duration_ms = int((time.time() - start_time) * 1000)

        # Log tool execution span
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
