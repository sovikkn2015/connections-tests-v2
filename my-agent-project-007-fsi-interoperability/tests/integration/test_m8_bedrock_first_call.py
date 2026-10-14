"""Task 18 -- Live Bedrock first-call probe (gated behind M8_LIVE=1).

Skipped unless ``M8_LIVE=1`` is set in env. Not run in CI.
"""

import os

import pytest


@pytest.mark.skipif(
    os.environ.get("M8_LIVE") != "1",
    reason="Live Bedrock call gated behind M8_LIVE=1 env",
)
def test_bedrock_first_call_probe() -> None:
    """First-live-call probe -- records actual Bedrock-advertised model ID
    in DECISION-LOG on mismatch.
    """
    from m8_pipeline_engine.llm_client import SonnetClient

    region = os.environ.get("AWS_REGION", "us-east-1")
    model_id = os.environ.get(
        "M8_MODEL_ID", "anthropic.claude-sonnet-4-5-20250929-v1:0"
    )

    sonnet = SonnetClient(
        model_id=model_id, region=region, timeout_ms=30000, max_retries=0
    )
    gen = sonnet.generate(
        stage_name="live_probe",
        prompt="Return a single JSON object: {\"ok\": true}",
        max_tokens=100,
        temperature=0.0,
        response_format="json",
    )
    assert gen.provider == "bedrock"
    assert gen.model == model_id
