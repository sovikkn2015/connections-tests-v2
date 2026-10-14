"""
A2A manifest handler for the Financial Analysis agent.

Serves ``GET /.well-known/agent.json`` per Google A2A spec v0.1.0.

The manifest is built dynamically so the ``url`` field reflects the
deployment's API Gateway stage/region rather than being hard-coded.
Resolution order for the agent URL:

    1. ``A2A_AGENT_URL``   — explicit override (preferred in prod)
    2. ``API_GATEWAY_URL`` + ``/financial-analysis/agent``
    3. API Gateway request context (host + stage) + ``/financial-analysis/agent``
    4. A placeholder ``https://CONFIGURE_AFTER_DEPLOY/financial-analysis/agent``
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, Optional

# Make the shared/ directory importable from within the Lambda bundle
_HERE = os.path.dirname(os.path.abspath(__file__))
_SHARED = os.path.abspath(os.path.join(_HERE, "..", "..", "shared"))
if _SHARED not in sys.path:
    sys.path.insert(0, _SHARED)

try:
    from a2a_types import (
        AgentCard,
        AgentProvider,
        AgentCapabilities,
        AgentAuthentication,
        AgentSkill,
    )
except ImportError:  # pragma: no cover — fallback when shared/ not packaged
    AgentCard = AgentProvider = AgentCapabilities = None  # type: ignore[assignment]
    AgentAuthentication = AgentSkill = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

AGENT_NAME = "Financial Analysis Agent"
AGENT_VERSION = "1.0.0"
AGENT_DESCRIPTION = (
    "DCF, comps, Monte Carlo, and fair-value calculations for equity "
    "research. Autonomous Strands-SDK agent on AWS Lambda with Bedrock "
    "Claude Sonnet reasoning and Langfuse-traced skill invocations."
)

SKILLS = [
    {
        "id": "run_dcf",
        "name": "Run DCF Valuation",
        "description": (
            "Project 5-year free cash flows and a Gordon-Growth terminal "
            "value to estimate intrinsic fair value per share."
        ),
        "tags": ["valuation", "dcf", "fundamental-analysis"],
        "examples": [
            "Run a DCF on NVDA with a 12% growth rate and 10% WACC.",
            "What is AAPL's intrinsic value using a 3% terminal growth?",
        ],
    },
    {
        "id": "run_comps",
        "name": "Run Comparable Company Analysis",
        "description": (
            "Compare target P/E, EV/EBITDA, and P/S multiples against "
            "sector peers to determine relative premium or discount."
        ),
        "tags": ["valuation", "comps", "peer-analysis"],
        "examples": [
            "How does MSFT trade vs its tech peers on EV/EBITDA?",
            "Run comps on JPM against other large-cap financials.",
        ],
    },
    {
        "id": "monte_carlo",
        "name": "Monte Carlo Price Simulation",
        "description": (
            "Simulate 1-year forward price distribution via geometric "
            "Brownian motion. Returns p5/p25/p50/p75/p95 price targets."
        ),
        "tags": ["risk", "simulation", "stochastic"],
        "examples": [
            "Run a 5000-path Monte Carlo on TSLA for a 1-year horizon.",
            "What is the 95th percentile price for NVDA one year out?",
        ],
    },
    {
        "id": "fair_value",
        "name": "Comprehensive Fair Value Report",
        "description": (
            "Orchestrate DCF, comps, and Monte Carlo, enrich with "
            "Salesforce CRM context, and synthesize bull/base/bear "
            "narrative via Bedrock Claude Sonnet."
        ),
        "tags": ["valuation", "synthesis", "llm"],
        "examples": [
            "Give me a fair value report on NVDA with bull/base/bear cases.",
            "What is the bear case for AAPL over the next year?",
        ],
    },
]


def _resolve_agent_url(event: Optional[Dict[str, Any]] = None) -> str:
    """Resolve the absolute URL to POST A2A tasks to."""
    override = os.environ.get("A2A_AGENT_URL")
    if override:
        return override

    api_base = os.environ.get("API_GATEWAY_URL", "").rstrip("/")
    if api_base and api_base.upper() != "CONFIGURE_AFTER_DEPLOY":
        return f"{api_base}/financial-analysis/agent"

    # Try to derive from the invoking request
    if event:
        headers = event.get("headers") or {}
        host = headers.get("Host") or headers.get("host")
        rc = event.get("requestContext") or {}
        stage = rc.get("stage", "")
        proto = headers.get("X-Forwarded-Proto") or headers.get("x-forwarded-proto") or "https"
        if host:
            base = f"{proto}://{host}"
            if stage:
                base = f"{base}/{stage}"
            return f"{base}/financial-analysis/agent"

    return "https://CONFIGURE_AFTER_DEPLOY/financial-analysis/agent"


def build_manifest(event: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return the Agent Card dict served at ``/.well-known/agent.json``."""
    agent_url = _resolve_agent_url(event)

    if AgentCard is not None:
        card = AgentCard(
            name=AGENT_NAME,
            description=AGENT_DESCRIPTION,
            url=agent_url,
            provider=AgentProvider(organization="ir-research-v3"),
            version=AGENT_VERSION,
            capabilities=AgentCapabilities(
                streaming=True,
                pushNotifications=False,
                stateTransitionHistory=False,
            ),
            authentication=AgentAuthentication(schemes=["apiKey"]),
            defaultInputModes=["application/json"],
            defaultOutputModes=["application/json"],
            skills=[AgentSkill(**s) for s in SKILLS],
        )
        return card.model_dump(exclude_none=True)

    # Fallback: plain dict
    return {
        "name": AGENT_NAME,
        "description": AGENT_DESCRIPTION,
        "url": agent_url,
        "provider": {"organization": "ir-research-v3"},
        "version": AGENT_VERSION,
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": False,
        },
        "authentication": {"schemes": ["apiKey"]},
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": [
            {
                "id": s["id"],
                "name": s["name"],
                "description": s["description"],
                "tags": s.get("tags", []),
                "examples": s.get("examples", []),
                "inputModes": ["application/json"],
                "outputModes": ["application/json"],
            }
            for s in SKILLS
        ],
    }


def handler(event, context=None):
    """Lambda-proxy handler for ``GET /.well-known/agent.json``."""
    manifest = build_manifest(event)
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization,x-api-key",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
            "Cache-Control": "public, max-age=60",
        },
        "body": json.dumps(manifest, default=str),
    }


lambda_handler = handler
