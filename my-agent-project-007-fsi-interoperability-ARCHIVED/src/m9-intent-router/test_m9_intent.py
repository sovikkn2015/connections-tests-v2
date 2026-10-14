"""
M9 Intent Router — Integration Tests.

Tests cover:
  - Deterministic routing for all 5 categories
  - Parameter extraction (ticker, quantity, side, client_name)
  - Confidence tier assignment (direct/plan/clarify)
  - Ambiguous input returns clarify tier
  - LLM fallback with mock provider
  - Taxonomy endpoint returns all 5 categories
  - Health check returns ok
  - FastAPI endpoint integration tests
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Ensure the m9-intent-router directory is on sys.path for imports
_M9_DIR = Path(__file__).resolve().parent
if str(_M9_DIR) not in sys.path:
    sys.path.insert(0, str(_M9_DIR))

from models import (
    ClassificationResult,
    CompletionResponse,
    ConfidenceTier,
    FSIIntent,
    IntentCategory,
    LLMProvider,
    Message,
    ToolDefinition,
)
from router import IntentRouter
from taxonomy import build_taxonomy


# ── Mock LLM Provider ───────────────────────────────────────────


class MockLLMProvider:
    """Mock LLM provider that returns a canned tool_use response."""

    def __init__(self, tool_name: str, args: dict[str, Any]) -> None:
        self._tool_name = tool_name
        self._args = args

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str = "default",
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> CompletionResponse:
        return CompletionResponse(
            content="",
            tool_calls=[{"name": self._tool_name, "input": self._args}],
            model="mock-haiku",
            usage={"input_tokens": 100, "output_tokens": 50},
        )


class FailingLLMProvider:
    """Mock LLM provider that raises an exception."""

    async def complete(self, **kwargs: Any) -> CompletionResponse:
        raise ConnectionError("LLM unavailable")


# ── Deterministic routing tests ──────────────────────────────────


@pytest.mark.asyncio
async def test_execution_buy_order():
    """'Buy 500 shares AAPL' → execution.order_draft with params."""
    router = IntentRouter()
    result = await router.classify_intent("Buy 500 shares AAPL")
    assert result.intent.category == IntentCategory.execution
    assert result.intent.action == "order_draft"
    assert result.intent.confidence > 0.95
    assert result.confidence_tier == ConfidenceTier.direct
    assert result.intent.parameters.get("ticker") == "AAPL"
    assert result.intent.parameters.get("quantity") == 500
    assert result.intent.parameters.get("side") == "buy"
    await router.close()


@pytest.mark.asyncio
async def test_execution_sell_order():
    """'Sell 200 shares MSFT' → execution.order_draft (sell)."""
    router = IntentRouter()
    result = await router.classify_intent("Sell 200 shares MSFT")
    assert result.intent.category == IntentCategory.execution
    assert result.intent.action == "order_draft"
    assert result.intent.parameters.get("side") == "sell"
    assert result.intent.parameters.get("ticker") == "MSFT"
    assert result.intent.parameters.get("quantity") == 200
    assert result.confidence_tier == ConfidenceTier.direct
    await router.close()


@pytest.mark.asyncio
async def test_client_prep_meeting():
    """'Prep me for Henderson meeting' → client.prep_meeting."""
    router = IntentRouter()
    result = await router.classify_intent("Prep me for Henderson meeting")
    assert result.intent.category == IntentCategory.client
    assert result.intent.action == "prep_meeting"
    assert result.intent.confidence > 0.95
    assert result.confidence_tier == ConfidenceTier.direct
    assert result.intent.parameters.get("client_name") == "Henderson"
    await router.close()


@pytest.mark.asyncio
async def test_research_security_analysis():
    """'Research NVDA earnings impact' → research.security_analysis."""
    router = IntentRouter()
    result = await router.classify_intent("Research NVDA earnings impact")
    assert result.intent.category == IntentCategory.research
    assert result.intent.action == "security_analysis"
    assert result.intent.confidence > 0.95
    assert result.confidence_tier == ConfidenceTier.direct
    assert result.intent.parameters.get("ticker") == "NVDA"
    await router.close()


@pytest.mark.asyncio
async def test_research_general():
    """'Analyze the market outlook' → research.*."""
    router = IntentRouter()
    result = await router.classify_intent("Analyze the market outlook")
    assert result.intent.category == IntentCategory.research
    assert result.intent.confidence > 0.95
    assert result.confidence_tier == ConfidenceTier.direct
    await router.close()


@pytest.mark.asyncio
async def test_compliance_restricted_list():
    """'Check restricted list for NVDA' → compliance.restricted_list_check."""
    router = IntentRouter()
    result = await router.classify_intent("Check restricted list for NVDA")
    assert result.intent.category == IntentCategory.compliance
    assert result.intent.action == "restricted_list_check"
    assert result.intent.confidence > 0.95
    assert result.confidence_tier == ConfidenceTier.direct
    await router.close()


@pytest.mark.asyncio
async def test_onboarding_kyc():
    """'Start KYC for new client' → onboarding.kyc_initiation."""
    router = IntentRouter()
    result = await router.classify_intent("Start KYC for new client")
    assert result.intent.category == IntentCategory.onboarding
    assert result.intent.action == "kyc_initiation"
    assert result.intent.confidence > 0.95
    assert result.confidence_tier == ConfidenceTier.direct
    await router.close()


@pytest.mark.asyncio
async def test_onboarding_new_account():
    """'Open new account for Smith' → onboarding.account_opening."""
    router = IntentRouter()
    result = await router.classify_intent("Open new account for Smith")
    assert result.intent.category == IntentCategory.onboarding
    assert result.intent.action == "account_opening"
    assert result.intent.confidence > 0.95
    assert result.intent.parameters.get("client_name") == "Smith"
    await router.close()


# ── Confidence tier tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_ambiguous_input_returns_clarify():
    """Ambiguous input with no LLM → clarify tier."""
    router = IntentRouter()
    result = await router.classify_intent("What should I do about the thing?")
    assert result.confidence_tier == ConfidenceTier.clarify
    assert result.intent.confidence < 0.80
    await router.close()


@pytest.mark.asyncio
async def test_empty_input_returns_clarify():
    """Empty input → clarify tier."""
    router = IntentRouter()
    result = await router.classify_intent("   ")
    assert result.confidence_tier == ConfidenceTier.clarify
    assert result.intent.confidence == 0.0
    await router.close()


@pytest.mark.asyncio
async def test_direct_tier_threshold():
    """Deterministic match always produces direct tier (>0.95)."""
    router = IntentRouter()
    result = await router.classify_intent("Buy 100 shares TSLA")
    assert result.confidence_tier == ConfidenceTier.direct
    assert result.intent.confidence > 0.95
    await router.close()


# ── LLM fallback tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_llm_fallback_plan_tier():
    """LLM returns 0.85 confidence → plan tier."""
    mock = MockLLMProvider(
        "classify_research_intent",
        {"action": "general_research", "confidence": 0.85, "topic": "macro trends"},
    )
    router = IntentRouter(llm_provider=mock)
    result = await router.classify_intent("Tell me about macro trends")
    assert result.intent.category == IntentCategory.research
    assert result.intent.action == "general_research"
    assert result.confidence_tier == ConfidenceTier.plan
    assert result.intent.parameters.get("topic") == "macro trends"
    await router.close()


@pytest.mark.asyncio
async def test_llm_fallback_clarify_tier():
    """LLM returns 0.50 confidence → clarify tier with candidates."""
    mock = MockLLMProvider(
        "classify_client_intent",
        {"action": "general_client_service", "confidence": 0.50},
    )
    router = IntentRouter(llm_provider=mock)
    result = await router.classify_intent("Something about a client maybe")
    assert result.confidence_tier == ConfidenceTier.clarify
    assert len(result.candidates) > 0
    await router.close()


@pytest.mark.asyncio
async def test_llm_failure_graceful_fallback():
    """LLM failure → clarify tier (graceful degradation)."""
    router = IntentRouter(llm_provider=FailingLLMProvider())
    result = await router.classify_intent("Something unclear")
    assert result.confidence_tier == ConfidenceTier.clarify
    await router.close()


# ── Routing target resolution ────────────────────────────────────


@pytest.mark.asyncio
async def test_routing_target_resolved():
    """Routing target auto-resolved from category."""
    router = IntentRouter()
    result = await router.classify_intent("Research AAPL")
    assert "Research Specialist" in result.intent.routing_target
    await router.close()


@pytest.mark.asyncio
async def test_compliance_routing_target():
    """Compliance routes to OPA specialist (no LLM)."""
    router = IntentRouter()
    result = await router.classify_intent("Check restricted list for TSLA")
    assert "Compliance Specialist" in result.intent.routing_target
    assert "no LLM" in result.intent.routing_target
    await router.close()


# ── Taxonomy tests ───────────────────────────────────────────────


def test_taxonomy_has_all_categories():
    """Taxonomy returns all 5 FSI categories."""
    taxonomy = build_taxonomy()
    categories = {c["category"] for c in taxonomy.categories}
    assert categories == {"research", "client", "compliance", "execution", "onboarding"}


def test_taxonomy_has_tool_definitions():
    """Each category has a tool definition."""
    taxonomy = build_taxonomy()
    for cat in taxonomy.categories:
        assert cat["tool_definition"] is not None
        assert "input_schema" in cat["tool_definition"]


def test_taxonomy_has_keyword_patterns():
    """Each category has keyword patterns."""
    taxonomy = build_taxonomy()
    for cat in taxonomy.categories:
        assert len(cat["keyword_patterns"]) > 0


# ── Model validation tests ───────────────────────────────────────


def test_fsi_intent_validation():
    """FSIIntent validates confidence range."""
    intent = FSIIntent(
        category=IntentCategory.research,
        action="security_analysis",
        confidence=0.97,
    )
    assert intent.routing_target == "Research Specialist (LangGraph/Sonnet)"


def test_fsi_intent_confidence_bounds():
    """Confidence must be 0-1."""
    with pytest.raises(Exception):
        FSIIntent(
            category=IntentCategory.research,
            action="test",
            confidence=1.5,
        )


def test_classification_result_model():
    """ClassificationResult serializes correctly."""
    result = ClassificationResult(
        intent=FSIIntent(
            category=IntentCategory.execution,
            action="order_draft",
            confidence=0.98,
            parameters={"ticker": "AAPL", "quantity": 100},
        ),
        confidence_tier=ConfidenceTier.direct,
        raw_input="Buy 100 shares AAPL",
        processing_time_ms=1.5,
    )
    data = result.model_dump()
    assert data["intent"]["category"] == "execution"
    assert data["confidence_tier"] == "direct"


# ── FastAPI endpoint tests ───────────────────────────────────────


@pytest_asyncio.fixture
async def client():
    """Create async test client for FastAPI app."""
    from app import app, lifespan

    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    """GET /health returns ok."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["module"] == "m9-intent-router"


@pytest.mark.asyncio
async def test_taxonomy_endpoint(client: AsyncClient):
    """GET /intent/taxonomy returns all 5 categories."""
    resp = await client.get("/intent/taxonomy")
    assert resp.status_code == 200
    data = resp.json()
    categories = {c["category"] for c in data["categories"]}
    assert categories == {"research", "client", "compliance", "execution", "onboarding"}


@pytest.mark.asyncio
async def test_classify_endpoint(client: AsyncClient):
    """POST /intent/classify classifies correctly."""
    resp = await client.post(
        "/intent/classify",
        json={"user_input": "Buy 500 shares AAPL"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"]["category"] == "execution"
    assert data["intent"]["action"] == "order_draft"
    assert data["confidence_tier"] == "direct"


@pytest.mark.asyncio
async def test_classify_endpoint_empty_input(client: AsyncClient):
    """POST /intent/classify rejects empty input."""
    resp = await client.post(
        "/intent/classify",
        json={"user_input": ""},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_classify_endpoint_research(client: AsyncClient):
    """POST /intent/classify routes research correctly."""
    resp = await client.post(
        "/intent/classify",
        json={"user_input": "Research NVDA earnings impact"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"]["category"] == "research"
    assert data["intent"]["parameters"].get("ticker") == "NVDA"


@pytest.mark.asyncio
async def test_classify_endpoint_compliance(client: AsyncClient):
    """POST /intent/classify routes compliance correctly."""
    resp = await client.post(
        "/intent/classify",
        json={"user_input": "Check restricted list for TSLA"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"]["category"] == "compliance"
    assert data["intent"]["action"] == "restricted_list_check"
