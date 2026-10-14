"""
M9 Task 7 -- BedrockHaikuClient.

AC3.1-3.8: happy path, 5xx retries, 4xx no retry, malformed output,
canary-utterance-not-in-stdout.

Uses botocore.Stubber to avoid live Bedrock. boto3 allowed here and in
hmac_util only (AC13.3).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from botocore.stub import Stubber

from m9_intent_router.errors import (
    LlmMalformedOutputError,
    LlmProviderError,
)
from m9_intent_router.llm_client import BedrockHaikuClient


def _valid_response():
    return {
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "toolUseId": "tooluse_abc",
                            "name": "routing_decision",
                            "input": {
                                "intent": "research.meeting_prep",
                                "confidence": 0.97,
                                "entities": {"ticker": "NVDA"},
                            },
                        }
                    }
                ],
            }
        },
        "stopReason": "tool_use",
        "usage": {"inputTokens": 100, "outputTokens": 50, "totalTokens": 150},
        "metrics": {"latencyMs": 200},
    }


def _make_client():
    return BedrockHaikuClient(
        model_id="anthropic.claude-3-5-haiku-20241022-v1:0",
        region="us-east-1",
        timeout_ms=1500,
        max_retries=2,
    )


def _tc():
    from m9_intent_router.taxonomy import build_tool_schema

    return build_tool_schema()


def test_happy_path_parses_tool_use():
    client = _make_client()
    with Stubber(client._client) as stub:
        stub.add_response("converse", _valid_response())
        result = client.classify("prep me", _tc())
    assert result.intent.value == "research.meeting_prep"
    assert result.confidence == 0.97
    assert result.entities == {"ticker": "NVDA"}
    assert result.provider == "bedrock"


def test_malformed_stop_reason_raises():
    client = _make_client()
    bad = _valid_response()
    bad["stopReason"] = "end_turn"
    with Stubber(client._client) as stub:
        stub.add_response("converse", bad)
        with pytest.raises(LlmMalformedOutputError):
            client.classify("x", _tc())


def test_malformed_tool_name_raises():
    client = _make_client()
    bad = _valid_response()
    bad["output"]["message"]["content"][0]["toolUse"]["name"] = "wrong_tool"
    with Stubber(client._client) as stub:
        stub.add_response("converse", bad)
        with pytest.raises(LlmMalformedOutputError):
            client.classify("x", _tc())


def test_malformed_multiple_tool_uses_raises():
    client = _make_client()
    bad = _valid_response()
    bad["output"]["message"]["content"].append(
        bad["output"]["message"]["content"][0]
    )
    with Stubber(client._client) as stub:
        stub.add_response("converse", bad)
        with pytest.raises(LlmMalformedOutputError):
            client.classify("x", _tc())


def test_invalid_enum_raises_malformed():
    client = _make_client()
    bad = _valid_response()
    bad["output"]["message"]["content"][0]["toolUse"]["input"][
        "intent"
    ] = "not_a_real_intent"
    with Stubber(client._client) as stub:
        stub.add_response("converse", bad)
        with pytest.raises(LlmMalformedOutputError):
            client.classify("x", _tc())


def test_4xx_no_retry_raises_provider_error():
    client = _make_client()
    with Stubber(client._client) as stub:
        stub.add_client_error(
            "converse",
            service_error_code="ValidationException",
            service_message="bad schema",
            http_status_code=400,
        )
        with pytest.raises(LlmProviderError) as exc_info:
            client.classify("x", _tc())
    assert exc_info.value.status_code == 400


def test_5xx_retries_then_raises():
    client = BedrockHaikuClient(
        model_id="m",
        region="us-east-1",
        timeout_ms=500,
        max_retries=1,
    )
    with patch("m9_intent_router.llm_client.time.sleep"):
        with Stubber(client._client) as stub:
            stub.add_client_error(
                "converse",
                service_error_code="InternalServerError",
                http_status_code=503,
            )
            stub.add_client_error(
                "converse",
                service_error_code="InternalServerError",
                http_status_code=503,
            )
            with pytest.raises(LlmProviderError) as exc_info:
                client.classify("x", _tc())
    assert exc_info.value.status_code == 503


def test_canary_utterance_not_in_captured_stdout(capsys):
    """AC3.6 -- classify NEVER logs the raw utterance."""
    client = _make_client()
    canary = "CANARY-PROMPT-NVDA-12345"
    with Stubber(client._client) as stub:
        stub.add_response("converse", _valid_response())
        client.classify(canary, _tc())
    out = capsys.readouterr().out
    assert canary not in out
