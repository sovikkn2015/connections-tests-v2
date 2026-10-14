"""
M9 Pydantic v2 models — FSI Intent Router.

Defines:
  - FSIIntent: structured intent with category, action, confidence, parameters
  - ClassificationResult: full classification output with confidence tier
  - IntentTaxonomy: the complete FSI taxonomy as tool definitions for LLM function calling
  - LLMProvider: protocol interface for swappable LLM backends (Rule 9)
"""

from __future__ import annotations

import enum
from typing import Any, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────


class IntentCategory(str, enum.Enum):
    """Five FSI specialist routing targets (Rule 15)."""
    research = "research"
    client = "client"
    compliance = "compliance"
    execution = "execution"
    onboarding = "onboarding"


class ConfidenceTier(str, enum.Enum):
    """Confidence-based routing tiers (Rule 6)."""
    direct = "direct"      # >0.95 — deterministic route
    plan = "plan"          # 0.80–0.95 — LLM-assisted plan
    clarify = "clarify"    # <0.80 — ask user


ROUTING_TARGETS: dict[IntentCategory, str] = {
    IntentCategory.research: "Research Specialist (LangGraph/Sonnet)",
    IntentCategory.client: "Client Service Specialist (Strands/Haiku)",
    IntentCategory.compliance: "Compliance Specialist (OPA, no LLM)",
    IntentCategory.execution: "Execution Specialist (Strands+StateMachine/Haiku)",
    IntentCategory.onboarding: "Onboarding Specialist (Workflow/Haiku)",
}


# ── Core models ──────────────────────────────────────────────────


class FSIIntent(BaseModel):
    """Structured FSI intent produced by classification."""
    category: IntentCategory
    action: str = Field(
        ..., min_length=1,
        description="Sub-action within category, e.g. 'security_analysis', 'order_draft'",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted entities: ticker, client_name, date, quantity, etc.",
    )
    routing_target: str = Field(
        default="",
        description="Specialist name resolved from category",
    )

    def model_post_init(self, __context: Any) -> None:
        """Resolve routing_target from category if not explicitly set."""
        if not self.routing_target:
            target = ROUTING_TARGETS.get(self.category, "")
            object.__setattr__(self, "routing_target", target)


class ClassificationResult(BaseModel):
    """Full classification output returned to M12."""
    intent: FSIIntent
    confidence_tier: ConfidenceTier
    raw_input: str
    processing_time_ms: float = Field(
        ..., ge=0.0,
        description="Classification latency in milliseconds",
    )
    candidates: list[FSIIntent] = Field(
        default_factory=list,
        description="Alternative intents when confidence < 0.80",
    )


class IntentTaxonomy(BaseModel):
    """Complete FSI intent taxonomy as structured tool definitions."""
    categories: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Tool/function definitions for LLM function calling",
    )
    version: str = "1.0.0"


# ── LLM Provider Protocol (Rule 9 — ARCH-04 Section 4) ──────────


class Message(BaseModel):
    """Chat message for LLM provider."""
    role: str
    content: str


class ToolDefinition(BaseModel):
    """Tool/function definition for LLM function calling."""
    name: str
    description: str
    input_schema: dict[str, Any]


class CompletionResponse(BaseModel):
    """Unified LLM completion response."""
    content: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    model: str = ""
    usage: dict[str, int] = Field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """
    Unified LLM provider interface (ARCH-04 Section 4).

    No module directly imports a provider-specific SDK.
    Provider is swappable via config: Bedrock, Azure OpenAI, GCP Vertex, vLLM.
    """

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str = "default",
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> CompletionResponse: ...
