"""
M9 Task 16 -- Bedrock first-live-call probe.

Gated behind M9_LIVE=1 env var. In CI this is always skipped.

See Known Blockers row 3.
"""

from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(
    not os.environ.get("M9_LIVE"),
    reason="live Bedrock gated behind M9_LIVE=1 env var",
)
def test_bedrock_first_live_call(fixture_intent_router_config):
    from m9_intent_router.llm_client import BedrockHaikuClient
    from m9_intent_router.taxonomy import build_tool_schema

    client = BedrockHaikuClient(
        model_id=fixture_intent_router_config.model_id,
        region=fixture_intent_router_config.region,
        timeout_ms=fixture_intent_router_config.timeout_ms,
    )
    result = client.classify("prep me for meeting tomorrow", build_tool_schema())
    assert result.provider == "bedrock"
    assert 0.0 <= result.confidence <= 1.0
