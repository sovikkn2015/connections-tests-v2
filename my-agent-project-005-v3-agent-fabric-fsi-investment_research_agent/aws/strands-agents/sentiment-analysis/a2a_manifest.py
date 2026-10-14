"""
A2A manifest handler for the Sentiment Analysis agent.

Serves ``GET /.well-known/agent.json`` per Google A2A spec v0.1.0.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, Optional

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
except ImportError:  # pragma: no cover
    AgentCard = AgentProvider = AgentCapabilities = None  # type: ignore[assignment]
    AgentAuthentication = AgentSkill = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

AGENT_NAME = "Sentiment Analysis Agent"
AGENT_VERSION = "1.0.0"
AGENT_DESCRIPTION = (
    "Transcript analysis, news sentiment scoring, management tone-shift "
    "detection, and aggregated sentiment reports. Strands-SDK agent on "
    "AWS Lambda combining Amazon Comprehend NLP with Bedrock Claude Sonnet."
)

SKILLS = [
    {
        "id": "analyze_transcript",
        "name": "Analyze Earnings Call Transcript",
        "description": (
            "Analyze an earnings call transcript for sentiment, key themes, "
            "management tone, and named entities. Uses Comprehend for NLP "
            "and Bedrock Claude for synthesis."
        ),
        "tags": ["nlp", "earnings", "transcript"],
        "examples": [
            "Analyze the latest NVDA earnings call transcript.",
            "What was the management tone on AAPL's Q3 call?",
        ],
    },
    {
        "id": "score_news_sentiment",
        "name": "Score News Sentiment",
        "description": (
            "Aggregate recent financial news for a ticker and produce an "
            "overall sentiment score with Comprehend + Bedrock reasoning."
        ),
        "tags": ["nlp", "news", "sentiment"],
        "examples": [
            "Score news sentiment for TSLA over the last 7 days.",
            "Is recent MSFT news bullish or bearish?",
        ],
    },
    {
        "id": "detect_tone_shifts",
        "name": "Detect Management Tone Shifts",
        "description": (
            "Identify where management changes tone (optimistic <-> cautious) "
            "between or within earnings commentary. Flags red-flag language."
        ),
        "tags": ["nlp", "tone", "risk-signal"],
        "examples": [
            "Did NVDA management shift tone between Q2 and Q3?",
            "Detect tone shifts in this transcript for AAPL.",
        ],
    },
    {
        "id": "aggregate_sentiment",
        "name": "Aggregate Sentiment Report",
        "description": (
            "Orchestrate transcript analysis, news scoring, and tone "
            "detection, enrich with Salesforce analyst context, and "
            "synthesize a combined sentiment report via Bedrock Claude."
        ),
        "tags": ["nlp", "synthesis", "llm"],
        "examples": [
            "Give me a combined sentiment report on NVDA.",
            "Aggregate sentiment for MSFT including news and earnings.",
        ],
    },
]


def _resolve_agent_url(event: Optional[Dict[str, Any]] = None) -> str:
    override = os.environ.get("A2A_AGENT_URL")
    if override:
        return override

    api_base = os.environ.get("API_GATEWAY_URL", "").rstrip("/")
    if api_base and api_base.upper() != "CONFIGURE_AFTER_DEPLOY":
        return f"{api_base}/sentiment-analysis/agent"

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
            return f"{base}/sentiment-analysis/agent"

    return "https://CONFIGURE_AFTER_DEPLOY/sentiment-analysis/agent"


def build_manifest(event: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
