"""
M9 Intent Router v2 — Strands SDK supervisor flavor (ARCH-10 Decision 1).

v1 (router.py): regex + LLM-fallback, <1ms fast-path, keyword-first
v2 (this file): a Strands Agent whose tools are the 5 specialist categories.
                The LLM reasons about which specialist to dispatch. No hand-
                coded routing. Slower (~500ms) but handles ambiguous inputs.

Both versions coexist. The M9 app exposes:
  POST /intent/classify        -> v1 by default
  POST /intent/classify/v2     -> v2 Strands agent
Or, set `M9_ROUTER_VERSION=v2` to swap the default at the /classify endpoint.

Rule 5: no LLM for compliance decisions. Only for classification.
Rule 13: uses Bedrock Haiku via Strands BedrockModel.
Rule 20: no credentials in code; AWS credential chain.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

from models import (
    ClassificationResult,
    ConfidenceTier,
    FSIIntent,
    IntentCategory,
)

logger = logging.getLogger("m9.router_v2")

# Lazy Strands import so the module can be imported even if strands not
# installed (the /classify endpoint falls back to v1 in that case).
_agent_singleton: Any = None


def _build_agent() -> Any:
    """Build a Strands Agent with 5 specialist-dispatch tools."""
    from strands import Agent, tool
    from strands.models.bedrock import BedrockModel

    model_id = os.environ.get(
        "M9_BEDROCK_MODEL_ID",
        "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    )
    region = os.environ.get("AWS_REGION", "us-east-1")
    model = BedrockModel(model_id=model_id, region_name=region)

    # Each tool below is the LLM's "choose this specialist" lever.
    # The function body returns structured routing info that our calling
    # code inspects to synthesize a ClassificationResult.
    _last_dispatch: dict[str, Any] = {}

    @tool
    def route_to_research(action: str, parameters: dict | None = None) -> str:
        """Route to the Research Specialist (deep financial analysis).
        Use for: SEC filings, earnings analysis, sector research, company
        deep-dives, competitive landscape, macroeconomic analysis.
        action: sub-action like 'security_analysis', 'sector_analysis'
        parameters: extracted entities (ticker, company_name, date_range, etc)"""
        _last_dispatch["category"] = "research"
        _last_dispatch["action"] = action
        _last_dispatch["parameters"] = parameters or {}
        return f"Dispatched to Research Specialist: {action}"

    @tool
    def route_to_client_service(action: str, parameters: dict | None = None) -> str:
        """Route to the Client Service Specialist (client-facing data).
        Use for: meeting prep, portfolio reviews, client summaries, account
        inquiries, interaction history, preference lookup.
        action: sub-action like 'meeting_prep', 'portfolio_review'
        parameters: extracted entities (client_id, client_name, etc)"""
        _last_dispatch["category"] = "client"
        _last_dispatch["action"] = action
        _last_dispatch["parameters"] = parameters or {}
        return f"Dispatched to Client Service: {action}"

    @tool
    def route_to_compliance(action: str, parameters: dict | None = None) -> str:
        """Route to Compliance (deterministic OPA checks, not LLM).
        Use for: restricted list, concentration limits, suitability,
        regulatory hold checks, MNPI access requests.
        action: sub-action like 'check_restricted_list', 'check_concentration'
        parameters: extracted entities (ticker, client_id, quantity)"""
        _last_dispatch["category"] = "compliance"
        _last_dispatch["action"] = action
        _last_dispatch["parameters"] = parameters or {}
        return f"Dispatched to Compliance: {action}"

    @tool
    def route_to_execution(action: str, parameters: dict | None = None) -> str:
        """Route to Execution Specialist (trade orders, HITL required).
        Use for: buy, sell, rebalance, order draft, order submit, order
        cancel. Orders always require human approval.
        action: sub-action like 'order_draft', 'order_submit'
        parameters: extracted entities (ticker, quantity, side, account_id)"""
        _last_dispatch["category"] = "execution"
        _last_dispatch["action"] = action
        _last_dispatch["parameters"] = parameters or {}
        return f"Dispatched to Execution: {action}"

    @tool
    def route_to_onboarding(action: str, parameters: dict | None = None) -> str:
        """Route to Onboarding Specialist (new client setup).
        Use for: KYC, sanctions screening, risk profiling, account opening,
        DocuSign flows, beneficiary setup.
        action: sub-action like 'start_kyc', 'complete_account_opening'
        parameters: extracted entities (client_name, account_type)"""
        _last_dispatch["category"] = "onboarding"
        _last_dispatch["action"] = action
        _last_dispatch["parameters"] = parameters or {}
        return f"Dispatched to Onboarding: {action}"

    system_prompt = (
        "You are the 007 Intent Router v2. Your ONLY job is to analyze the "
        "user request and dispatch it to exactly ONE of the 5 specialists by "
        "calling the matching route_to_* tool. Do not answer the request "
        "yourself. Do not explain. After calling the tool, your final "
        "response should be a single short confirmation sentence.\n\n"
        "Routing rules (memorize):\n"
        "- Data about a specific client / portfolio / account -> client_service\n"
        "- Research on a public company / market / sector -> research\n"
        "- Trading / buying / selling / rebalancing -> execution\n"
        "- 'Is X allowed?' / regulatory / restricted list -> compliance\n"
        "- New client setup / KYC / account opening -> onboarding\n"
    )

    agent = Agent(
        model=model,
        tools=[
            route_to_research,
            route_to_client_service,
            route_to_compliance,
            route_to_execution,
            route_to_onboarding,
        ],
        system_prompt=system_prompt,
    )

    # Stash the dispatch dict on the agent so the outer function can read it.
    setattr(agent, "_last_dispatch", _last_dispatch)
    return agent


def _get_agent() -> Any:
    global _agent_singleton
    if _agent_singleton is None:
        _agent_singleton = _build_agent()
    return _agent_singleton


def classify_intent_v2(
    user_input: str, aid_claims: Optional[dict[str, Any]] = None
) -> ClassificationResult:
    """v2 classification via Strands + Bedrock Haiku.

    The LLM selects one route_to_* tool. We inspect the dispatched category
    and action to build a ClassificationResult that is wire-compatible with
    v1 so M12 doesn't need to care which version is running.
    """
    t0 = time.perf_counter()
    agent = _get_agent()
    dispatch: dict[str, Any] = getattr(agent, "_last_dispatch")
    dispatch.clear()

    try:
        _ = agent(user_input)
    except Exception as exc:
        logger.error("v2 agent failed: %s", exc)
        # Fall back to a conservative clarify-tier intent — M12 can ask again.
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return ClassificationResult(
            intent=FSIIntent(
                category=IntentCategory.client,
                action="unknown",
                confidence=0.0,
                parameters={},
            ),
            confidence_tier=ConfidenceTier.clarify,
            raw_input=user_input,
            processing_time_ms=elapsed_ms,
        )

    elapsed_ms = (time.perf_counter() - t0) * 1000

    if not dispatch:
        # LLM did not call any route_to_* tool — low-confidence clarify.
        return ClassificationResult(
            intent=FSIIntent(
                category=IntentCategory.client,
                action="unknown",
                confidence=0.0,
                parameters={},
            ),
            confidence_tier=ConfidenceTier.clarify,
            raw_input=user_input,
            processing_time_ms=elapsed_ms,
        )

    category_str = dispatch.get("category", "client")
    action = dispatch.get("action", "unknown")
    params = dispatch.get("parameters", {}) or {}

    try:
        category = IntentCategory(category_str)
    except ValueError:
        category = IntentCategory.client

    # v2 confidence: LLM function-calling typically high-confidence when
    # it picked a tool deliberately. We use a fixed 0.88 so tier resolves
    # to 'plan' — downstream can A/B against v1's higher-confidence direct.
    confidence = float(os.environ.get("M9_V2_CONFIDENCE", "0.88"))
    tier = (
        ConfidenceTier.direct if confidence > 0.95
        else ConfidenceTier.plan if confidence >= 0.80
        else ConfidenceTier.clarify
    )

    return ClassificationResult(
        intent=FSIIntent(
            category=category,
            action=action,
            confidence=confidence,
            parameters=params,
        ),
        confidence_tier=tier,
        raw_input=user_input,
        processing_time_ms=elapsed_ms,
    )
