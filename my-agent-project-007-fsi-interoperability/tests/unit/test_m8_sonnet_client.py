"""Task 7 -- SonnetClient via botocore Stubber. No live Bedrock call."""

import pytest

# Skip entire module if boto3 unavailable
boto3 = pytest.importorskip("boto3")
from botocore.stub import Stubber  # type: ignore  # noqa: E402

from m8_pipeline_engine.errors import (
    LlmMalformedOutputError,
    LlmProviderError,
    LlmTimeoutError,
)
from m8_pipeline_engine.llm_client import SonnetClient
from m8_pipeline_engine.models import LlmGeneration


def _build_client_with_stub():
    real = boto3.client("bedrock-runtime", region_name="us-east-1")
    stubber = Stubber(real)
    sonnet = SonnetClient(model_id="fake-model", region="us-east-1", max_retries=0)
    sonnet._client = real  # inject stubbed client
    return sonnet, stubber


def test_sonnet_happy_path():
    sonnet, stubber = _build_client_with_stub()
    stubber.add_response(
        "converse",
        {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "hello"}],
                }
            },
            "usage": {
                "inputTokens": 5,
                "outputTokens": 3,
                "totalTokens": 8,
            },
            "metrics": {"latencyMs": 42},
            "stopReason": "end_turn",
        },
        expected_params={
            "modelId": "fake-model",
            "messages": [{"role": "user", "content": [{"text": "p"}]}],
            "inferenceConfig": {"temperature": 0.1, "maxTokens": 10},
        },
    )
    with stubber:
        gen = sonnet.generate(
            stage_name="stage_1_intake",
            prompt="p",
            max_tokens=10,
            temperature=0.1,
            response_format="text",
        )
    assert isinstance(gen, LlmGeneration)
    assert gen.text == "hello"
    assert gen.input_tokens == 5


def test_sonnet_malformed_json_raises():
    sonnet, stubber = _build_client_with_stub()
    stubber.add_response(
        "converse",
        {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "not json"}],
                }
            },
            "usage": {
                "inputTokens": 1,
                "outputTokens": 1,
                "totalTokens": 2,
            },
            "metrics": {"latencyMs": 7},
            "stopReason": "end_turn",
        },
        expected_params={
            "modelId": "fake-model",
            "messages": [{"role": "user", "content": [{"text": "p"}]}],
            "inferenceConfig": {"temperature": 0.1, "maxTokens": 10},
            "additionalModelRequestFields": {"response_format": {"type": "json_object"}},
        },
    )
    with stubber:
        with pytest.raises(LlmMalformedOutputError):
            sonnet.generate(
                stage_name="stage_1_intake",
                prompt="p",
                max_tokens=10,
                temperature=0.1,
                response_format="json",
            )


def test_sonnet_4xx_does_not_retry():
    # ClientError with HTTPStatusCode=400 should raise LlmProviderError, no retry
    sonnet, stubber = _build_client_with_stub()
    stubber.add_client_error(
        "converse",
        service_error_code="ValidationException",
        http_status_code=400,
    )
    with stubber:
        with pytest.raises(LlmProviderError) as exc:
            sonnet.generate(
                stage_name="stage_x",
                prompt="p",
                max_tokens=10,
                temperature=0.1,
                response_format="text",
            )
        assert 400 <= exc.value.status_code < 500
