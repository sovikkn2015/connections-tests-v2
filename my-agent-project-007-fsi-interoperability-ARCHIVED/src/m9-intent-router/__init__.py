"""
M9 — FSI Intent Router.

Project 007 FSI Interoperability Platform.

Classifies natural-language user input into structured FSI intents using
LLM function calling (Anthropic tool_use / OpenAI function_calling) with
a deterministic fast-path for unambiguous patterns.

Confidence thresholds (Rule 6):
  >0.95  → direct route to specialist (bypass LLM planning)
  0.80–0.95 → LLM-assisted plan generation
  <0.80  → ask user for clarification

Called by M12 (Agent Runtime). Calls M1 (identity verification), M5 (config).
All tool calls through M6 gateway ONLY (Rule 7).
"""

from models import (
    ClassificationResult,
    ConfidenceTier,
    FSIIntent,
    IntentCategory,
    IntentTaxonomy,
)
from router import IntentRouter

__all__ = [
    "ClassificationResult",
    "ConfidenceTier",
    "FSIIntent",
    "IntentCategory",
    "IntentRouter",
    "IntentTaxonomy",
]
