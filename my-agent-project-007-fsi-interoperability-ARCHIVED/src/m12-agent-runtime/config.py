"""
M12 Agent Runtime — Model and agent configuration.

Reads env vars for Bedrock model config and M6 gateway URL.
Creates BedrockModel instances for Haiku (routing) and Sonnet (research).
Dev mode: logs warning when Bedrock unavailable, doesn't crash.

No credentials in code (Rule 20). Model provider via env vars.
No cross-module imports (Rule 9). M6 URL for REST communication only.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger("m12.config")

# ── Environment variables (no hardcoded creds — Rule 20) ────────

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
BEDROCK_MODEL_HAIKU = os.environ.get(
    "BEDROCK_MODEL_HAIKU", "us.anthropic.claude-3-5-haiku-20241022-v1:0"
)
BEDROCK_MODEL_SONNET = os.environ.get(
    "BEDROCK_MODEL_SONNET", "us.anthropic.claude-sonnet-4-20250514-v1:0"
)
M6_GATEWAY_URL = os.environ.get("M6_GATEWAY_URL", "http://localhost:8000")
AGENT_VERSION = os.environ.get("AGENT_VERSION", "v2")

# ── Lazy model creation (dev-safe) ──────────────────────────────

_haiku_model = None
_sonnet_model = None
_bedrock_available: Optional[bool] = None


def _check_bedrock() -> bool:
    """Check if Bedrock is available. Cached after first call."""
    global _bedrock_available
    if _bedrock_available is not None:
        return _bedrock_available
    try:
        from strands.models import BedrockModel
        # Attempt to create — validates AWS credentials exist
        BedrockModel(
            model_id=BEDROCK_MODEL_HAIKU,
            region_name=AWS_REGION,
        )
        _bedrock_available = True
        logger.info("Bedrock available in region %s", AWS_REGION)
    except Exception as exc:
        _bedrock_available = False
        logger.warning(
            "Bedrock unavailable (%s). Tools still work with M6 gateway. "
            "Set AWS credentials to enable LLM calls.",
            exc,
        )
    return _bedrock_available


def get_haiku_model():
    """
    Get BedrockModel for Haiku (routing/conversation/execution).
    Returns None if Bedrock is unavailable (dev mode).
    """
    global _haiku_model
    if _haiku_model is not None:
        return _haiku_model
    if not _check_bedrock():
        return None
    from strands.models import BedrockModel
    _haiku_model = BedrockModel(
        model_id=BEDROCK_MODEL_HAIKU,
        region_name=AWS_REGION,
    )
    return _haiku_model


def get_sonnet_model():
    """
    Get BedrockModel for Sonnet (research/deep analysis).
    Returns None if Bedrock is unavailable (dev mode).
    """
    global _sonnet_model
    if _sonnet_model is not None:
        return _sonnet_model
    if not _check_bedrock():
        return None
    from strands.models import BedrockModel
    _sonnet_model = BedrockModel(
        model_id=BEDROCK_MODEL_SONNET,
        region_name=AWS_REGION,
    )
    return _sonnet_model
