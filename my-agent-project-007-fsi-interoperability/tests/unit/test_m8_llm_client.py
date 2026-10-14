"""Task 1 -- LLMClient Protocol satisfaction + dispatch tests."""

import pytest

from m8_pipeline_engine.errors import (
    LlmMalformedOutputError,
    LlmProviderError,
    LlmTimeoutError,
)
from m8_pipeline_engine.llm_client import (
    AzureOpenAIClient,
    FakeSonnetClient,
    LLMClient,
    SonnetClient,
    VertexClient,
    VllmClient,
    select_llm_client,
)
from m8_pipeline_engine.models import LlmGeneration


class _Cfg:
    def __init__(self, provider):
        self.model_provider = provider
        self.model_id = "fake-model"
        self.region = "us-east-1"


def test_sonnet_client_satisfies_protocol():
    client = SonnetClient(model_id="fake-model", region="us-east-1")
    assert isinstance(client, LLMClient)


def test_fake_sonnet_client_default_response():
    fake = FakeSonnetClient()
    gen = fake.generate(
        stage_name="stage_1_intake",
        prompt="hello",
        max_tokens=100,
        temperature=0.1,
        response_format="text",
    )
    assert isinstance(gen, LlmGeneration)
    assert gen.provider == "fake"


def test_fake_sonnet_raises_injected_exception():
    fake = FakeSonnetClient(
        responses={"stage_1_intake": LlmTimeoutError("injected")}
    )
    with pytest.raises(LlmTimeoutError):
        fake.generate(
            stage_name="stage_1_intake",
            prompt="x",
            max_tokens=10,
            temperature=0.1,
            response_format="text",
        )


def test_fake_sonnet_returns_injected_generation():
    g = LlmGeneration(
        text="custom",
        input_tokens=5,
        output_tokens=3,
        latency_ms=7,
        model="m",
        provider="fake",
        stop_reason="end_turn",
    )
    fake = FakeSonnetClient(responses={"stage_1_intake": g})
    out = fake.generate(
        stage_name="stage_1_intake",
        prompt="x",
        max_tokens=10,
        temperature=0.1,
        response_format="text",
    )
    assert out.text == "custom"


def test_reserved_stubs_raise_not_implemented():
    for cls in (AzureOpenAIClient, VertexClient, VllmClient):
        with pytest.raises(NotImplementedError):
            cls()


def test_select_llm_client_dispatch_bedrock():
    client = select_llm_client(_Cfg("bedrock"))
    assert isinstance(client, SonnetClient)


def test_select_llm_client_unknown_raises():
    with pytest.raises(ValueError, match="provider_unconfigured"):
        select_llm_client(_Cfg("other"))
