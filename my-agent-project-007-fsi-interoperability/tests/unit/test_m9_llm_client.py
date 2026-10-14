"""
M9 Task 1 -- LLM provider abstraction.

AC4.1-4.9: LLMProvider Protocol satisfaction, FakeLlmClient exception
injection (Fix 9), SlowFakeLlmClient timeout (Fix 13), reserved stubs,
select_provider dispatch.
"""

from __future__ import annotations

import time

import pytest

from m9_intent_router import IntentCategory
from m9_intent_router.errors import (
    LlmMalformedOutputError,
    LlmProviderError,
    LlmTimeoutError,
)
from m9_intent_router.llm_client import (
    AzureOpenAIClient,
    BedrockHaikuClient,
    FakeLlmClient,
    LLMProvider,
    SlowFakeLlmClient,
    VertexClient,
    VllmClient,
    select_provider,
)
from m9_intent_router.models import LlmClassification


# -----------------------------------------------------------------------------
# AC4.1 / AC4.2 -- Protocol satisfaction.
# -----------------------------------------------------------------------------


def test_fake_satisfies_protocol():
    assert isinstance(FakeLlmClient(), LLMProvider)


def test_slow_fake_satisfies_protocol():
    assert isinstance(SlowFakeLlmClient(block_ms=10, timeout_ms=20), LLMProvider)


def test_bedrock_has_classify_method():
    """Can't instantiate without AWS creds path, but class has classify."""
    assert hasattr(BedrockHaikuClient, "classify")
    assert callable(BedrockHaikuClient.classify)


# -----------------------------------------------------------------------------
# AC4.3 / Fix 9 -- FakeLlmClient exception injection.
# -----------------------------------------------------------------------------


def test_fake_returns_classification_verbatim():
    c = LlmClassification(
        intent=IntentCategory.RESEARCH_MEETING_PREP,
        confidence=0.9,
        entities={},
        latency_ms=10,
        model="m",
        provider="fake",
    )
    fake = FakeLlmClient(responses={"hi": c})
    assert fake.classify("hi", {}) == c


def test_fake_raises_timeout_error():
    fake = FakeLlmClient(responses={"hi": LlmTimeoutError("slow")})
    with pytest.raises(LlmTimeoutError):
        fake.classify("hi", {})


def test_fake_raises_provider_error():
    fake = FakeLlmClient(responses={"hi": LlmProviderError(500, "server down")})
    with pytest.raises(LlmProviderError):
        fake.classify("hi", {})


def test_fake_raises_malformed_error():
    fake = FakeLlmClient(responses={"hi": LlmMalformedOutputError("bad")})
    with pytest.raises(LlmMalformedOutputError):
        fake.classify("hi", {})


def test_fake_raises_arbitrary_exception():
    """AC4.3 -- any Exception value is raised verbatim."""
    fake = FakeLlmClient(responses={"hi": RuntimeError("unexpected")})
    with pytest.raises(RuntimeError):
        fake.classify("hi", {})


def test_fake_unmapped_returns_unsupported():
    fake = FakeLlmClient()
    result = fake.classify("unseeded utterance", {})
    assert result.intent == IntentCategory.UNSUPPORTED
    assert result.confidence == 0.0


# -----------------------------------------------------------------------------
# AC4.9 / Fix 13 -- SlowFakeLlmClient timeout determinism.
# -----------------------------------------------------------------------------


def test_slow_fake_raises_timeout_when_block_exceeds_timeout():
    slow = SlowFakeLlmClient(block_ms=200, timeout_ms=100)
    t0 = time.perf_counter()
    with pytest.raises(LlmTimeoutError):
        slow.classify("x", {})
    elapsed_ms = (time.perf_counter() - t0) * 1000
    # Should have slept for min(block_ms, timeout_ms)=100ms, then raised.
    assert 90 <= elapsed_ms < 500


def test_slow_fake_no_timeout_when_block_le_timeout():
    slow = SlowFakeLlmClient(block_ms=50, timeout_ms=200)
    result = slow.classify("x", {})
    assert result.intent == IntentCategory.UNSUPPORTED
    assert result.model == "slow_fake"


# -----------------------------------------------------------------------------
# AC4.4 -- Reserved Phase 3 stubs raise NotImplementedError.
# -----------------------------------------------------------------------------


def test_azure_openai_stub():
    with pytest.raises(NotImplementedError):
        AzureOpenAIClient()


def test_vertex_stub():
    with pytest.raises(NotImplementedError):
        VertexClient()


def test_vllm_stub():
    with pytest.raises(NotImplementedError):
        VllmClient()


# -----------------------------------------------------------------------------
# AC4.5 -- select_provider dispatch.
# -----------------------------------------------------------------------------


class _Cfg:
    def __init__(
        self, provider, model_id="m", region="us-east-1", timeout_ms=1500
    ):
        self.provider = provider
        self.model_id = model_id
        self.region = region
        self.timeout_ms = timeout_ms


def test_select_provider_unknown_raises():
    with pytest.raises(ValueError, match="provider_unconfigured"):
        select_provider(_Cfg(provider="mystery"))


def test_select_provider_azure_returns_stub_error():
    with pytest.raises(NotImplementedError):
        select_provider(_Cfg(provider="azure_openai"))


def test_select_provider_vertex_returns_stub_error():
    with pytest.raises(NotImplementedError):
        select_provider(_Cfg(provider="vertex"))


def test_select_provider_vllm_returns_stub_error():
    with pytest.raises(NotImplementedError):
        select_provider(_Cfg(provider="vllm"))
