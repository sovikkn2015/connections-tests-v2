"""
M9 Intent Router — Public API.

Phase 2: LLM function-calling classifier consumed directly by the M12
Supervisor Model. Pure in-process library. No FastAPI, no HTTP listener,
no direct M6 MCP calls, no M8 pipeline dispatch.

Usage:
    from m9_intent_router import route, RouterContext
    decision = route(utterance, ctx, _provider=prov, _config=cfg)

See `.kiro/specs/m9-intent-router.md` v0.2.0 for the full contract.
"""

from __future__ import annotations

from m9_intent_router.errors import VALID_REASON_CODES
from m9_intent_router.llm_client import (
    BedrockHaikuClient,
    FakeLlmClient,
    LLMProvider,
    SlowFakeLlmClient,
)
from m9_intent_router.models import (
    LlmClassification,
    RouterContext,
    RoutingDecision,
)
from m9_intent_router.route import route
from m9_intent_router.taxonomy import IntentCategory, SelectedTarget

#: SemVer of the M9 public contract. Bumped to 1.1.0 for Fix 11 rename
#: (CLIENT_HOUSEHOLD_SUMMARY -> RESEARCH_HOUSEHOLD_SUMMARY) per AC15.3.
SCHEMA_VERSION: str = "1.1.0"

# Exactly 11 public names per AC15.1 (v0.2.0 -- added SlowFakeLlmClient, Fix 13).
__all__ = [
    "route",
    "RoutingDecision",
    "RouterContext",
    "IntentCategory",
    "SelectedTarget",
    "VALID_REASON_CODES",
    "LLMProvider",
    "BedrockHaikuClient",
    "FakeLlmClient",
    "SlowFakeLlmClient",
    "SCHEMA_VERSION",
]
# LlmClassification is importable via the submodule but not in __all__.
