"""
M9 FSI Intent Taxonomy — keyword patterns + LLM tool definitions.

Defines all 5 specialist categories with sub-actions, JSON Schema for
each intent's parameters, and keyword patterns for deterministic routing.

The taxonomy is provider-agnostic: expressed as JSON Schema tool definitions
that map to Anthropic tool_use or OpenAI function_calling.
"""

from __future__ import annotations

import re
from typing import Any

from models import IntentCategory, IntentTaxonomy, ToolDefinition


# ── Keyword patterns for deterministic fast-path ─────────────────
# Each entry: (compiled regex, category, action, confidence, param extractor name)

_TICKER_RE = r"[A-Z]{1,5}"

KEYWORD_PATTERNS: list[tuple[re.Pattern[str], IntentCategory, str, float, str | None]] = [
    # ── research.* ───────────────────────────────────────────
    (
        re.compile(
            rf"(?i)\b(?:research|analyze|analysis|deep[\s-]?dive)\b.*\b({_TICKER_RE})\b"
        ),
        IntentCategory.research, "security_analysis", 0.97, "ticker",
    ),
    (
        re.compile(r"(?i)\b(?:research|analyze|analysis|deep[\s-]?dive)\b"),
        IntentCategory.research, "general_research", 0.96, None,
    ),
    (
        re.compile(rf"(?i)\bearnings?\b.*\b({_TICKER_RE})\b"),
        IntentCategory.research, "earnings_analysis", 0.96, "ticker",
    ),
    (
        re.compile(rf"(?i)\b(?:sec|10-?[kq]|filing|edgar)\b.*\b({_TICKER_RE})\b"),
        IntentCategory.research, "sec_filing_analysis", 0.97, "ticker",
    ),
    (
        re.compile(r"(?i)\bmarket\s+(?:outlook|summary|overview|report)\b"),
        IntentCategory.research, "market_overview", 0.96, None,
    ),

    # ── client.* ─────────────────────────────────────────────
    (
        re.compile(r"(?i)\b(?:prep|prepare)\b.*\b(?:meeting|call|review)\b"),
        IntentCategory.client, "prep_meeting", 0.97, "client_name",
    ),
    (
        re.compile(r"(?i)\bmeeting\s+prep\b"),
        IntentCategory.client, "prep_meeting", 0.97, "client_name",
    ),
    (
        re.compile(r"(?i)\bclient\s+(?:summary|profile|overview)\b"),
        IntentCategory.client, "client_summary", 0.96, "client_name",
    ),
    (
        re.compile(r"(?i)\bportfolio\s+(?:review|summary|performance)\b"),
        IntentCategory.client, "portfolio_review", 0.96, "client_name",
    ),

    # ── compliance.* ─────────────────────────────────────────
    (
        re.compile(r"(?i)\brestricted\s+list\b"),
        IntentCategory.compliance, "restricted_list_check", 0.98, "ticker",
    ),
    (
        re.compile(r"(?i)\bcompliance\s+check\b"),
        IntentCategory.compliance, "general_check", 0.96, None,
    ),
    (
        re.compile(r"(?i)\bsuitability\b.*\b(?:check|review|assess)\b"),
        IntentCategory.compliance, "suitability_check", 0.96, "client_name",
    ),
    (
        re.compile(r"(?i)\bconcentration\s+(?:check|limit|review)\b"),
        IntentCategory.compliance, "concentration_check", 0.96, "ticker",
    ),
    (
        re.compile(r"(?i)\btrading\s+window\b"),
        IntentCategory.compliance, "trading_window_check", 0.96, None,
    ),

    # ── execution.* ──────────────────────────────────────────
    (
        re.compile(
            rf"(?i)\b(?:buy|purchase|acquire)\b\s+(\d+)\s+shares?\s+(?:of\s+)?({_TICKER_RE})\b"
        ),
        IntentCategory.execution, "order_draft", 0.98, "buy_order",
    ),
    (
        re.compile(
            rf"(?i)\b(?:sell|liquidate|dispose)\b\s+(\d+)\s+shares?\s+(?:of\s+)?({_TICKER_RE})\b"
        ),
        IntentCategory.execution, "order_draft", 0.98, "sell_order",
    ),
    (
        re.compile(rf"(?i)\b(?:buy|purchase)\b.*\b({_TICKER_RE})\b"),
        IntentCategory.execution, "order_draft", 0.96, "ticker",
    ),
    (
        re.compile(rf"(?i)\b(?:sell|liquidate)\b.*\b({_TICKER_RE})\b"),
        IntentCategory.execution, "order_draft", 0.96, "ticker",
    ),
    (
        re.compile(r"(?i)\brebalance\b"),
        IntentCategory.execution, "rebalance", 0.96, "client_name",
    ),

    # ── onboarding.* ─────────────────────────────────────────
    (
        re.compile(r"(?i)\b(?:start|begin|initiate)\b.*\bkyc\b"),
        IntentCategory.onboarding, "kyc_initiation", 0.97, "client_name",
    ),
    (
        re.compile(r"(?i)\b(?:new|open)\b.*\b(?:client|account)\b"),
        IntentCategory.onboarding, "account_opening", 0.96, "client_name",
    ),
    (
        re.compile(r"(?i)\bonboard(?:ing)?\b"),
        IntentCategory.onboarding, "general_onboarding", 0.96, "client_name",
    ),
]


# ── Parameter extractors ─────────────────────────────────────────

_CLIENT_NAME_RE = re.compile(
    r"(?i)(?:for|with|about|client)\s+([A-Z][a-z]+)"
)


def extract_params(
    text: str, match: re.Match[str], extractor: str | None,
) -> dict[str, Any]:
    """Extract structured parameters from regex match + input text."""
    params: dict[str, Any] = {}

    if extractor == "ticker":
        groups = match.groups()
        if groups:
            params["ticker"] = groups[0].upper()

    elif extractor == "buy_order":
        groups = match.groups()
        if len(groups) >= 2:
            params["quantity"] = int(groups[0])
            params["ticker"] = groups[1].upper()
            params["side"] = "buy"

    elif extractor == "sell_order":
        groups = match.groups()
        if len(groups) >= 2:
            params["quantity"] = int(groups[0])
            params["ticker"] = groups[1].upper()
            params["side"] = "sell"

    elif extractor == "client_name":
        cn = _CLIENT_NAME_RE.search(text)
        if cn:
            params["client_name"] = cn.group(1).strip()

    return params


# ── LLM tool definitions (JSON Schema for function calling) ──────

INTENT_TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="classify_research_intent",
        description=(
            "Classify user input as a research intent: security analysis, "
            "earnings analysis, SEC filing analysis, or market overview."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "security_analysis", "earnings_analysis",
                        "sec_filing_analysis", "market_overview",
                        "general_research",
                    ],
                    "description": "Specific research sub-action",
                },
                "confidence": {
                    "type": "number", "minimum": 0, "maximum": 1,
                    "description": "Classification confidence 0-1",
                },
                "ticker": {"type": "string", "description": "Security ticker if mentioned"},
                "topic": {"type": "string", "description": "Research topic"},
            },
            "required": ["action", "confidence"],
        },
    ),
    ToolDefinition(
        name="classify_client_intent",
        description=(
            "Classify user input as a client service intent: meeting prep, "
            "client summary, portfolio review."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "prep_meeting", "client_summary",
                        "portfolio_review", "general_client_service",
                    ],
                },
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "client_name": {"type": "string", "description": "Client name if mentioned"},
            },
            "required": ["action", "confidence"],
        },
    ),
    ToolDefinition(
        name="classify_compliance_intent",
        description=(
            "Classify user input as a compliance intent: restricted list check, "
            "suitability check, concentration check, trading window check."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "restricted_list_check", "suitability_check",
                        "concentration_check", "trading_window_check",
                        "general_check",
                    ],
                },
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "ticker": {"type": "string"},
                "client_name": {"type": "string"},
            },
            "required": ["action", "confidence"],
        },
    ),
    ToolDefinition(
        name="classify_execution_intent",
        description=(
            "Classify user input as an execution intent: order draft, "
            "rebalance, trade modification."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["order_draft", "rebalance", "trade_modification"],
                },
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "ticker": {"type": "string"},
                "quantity": {"type": "integer"},
                "side": {"type": "string", "enum": ["buy", "sell"]},
                "client_name": {"type": "string"},
            },
            "required": ["action", "confidence"],
        },
    ),
    ToolDefinition(
        name="classify_onboarding_intent",
        description=(
            "Classify user input as an onboarding intent: KYC initiation, "
            "account opening, general onboarding."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "kyc_initiation", "account_opening",
                        "general_onboarding",
                    ],
                },
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "client_name": {"type": "string"},
            },
            "required": ["action", "confidence"],
        },
    ),
]

# Map tool name → IntentCategory
TOOL_TO_CATEGORY: dict[str, IntentCategory] = {
    "classify_research_intent": IntentCategory.research,
    "classify_client_intent": IntentCategory.client,
    "classify_compliance_intent": IntentCategory.compliance,
    "classify_execution_intent": IntentCategory.execution,
    "classify_onboarding_intent": IntentCategory.onboarding,
}


def build_taxonomy() -> IntentTaxonomy:
    """Build the full FSI intent taxonomy for debugging/docs."""
    return IntentTaxonomy(
        categories=[
            {
                "category": cat.value,
                "routing_target": {
                    IntentCategory.research: "Research Specialist (LangGraph/Sonnet)",
                    IntentCategory.client: "Client Service Specialist (Strands/Haiku)",
                    IntentCategory.compliance: "Compliance Specialist (OPA, no LLM)",
                    IntentCategory.execution: "Execution Specialist (Strands+StateMachine/Haiku)",
                    IntentCategory.onboarding: "Onboarding Specialist (Workflow/Haiku)",
                }[cat],
                "tool_definition": next(
                    (t.model_dump() for t in INTENT_TOOL_DEFINITIONS
                     if TOOL_TO_CATEGORY.get(t.name) == cat),
                    None,
                ),
                "keyword_patterns": [
                    p[0].pattern for p in KEYWORD_PATTERNS if p[1] == cat
                ],
            }
            for cat in IntentCategory
        ],
        version="1.0.0",
    )
