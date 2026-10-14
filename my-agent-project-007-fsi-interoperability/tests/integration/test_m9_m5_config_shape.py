"""
M9 Task 17 -- M5 IntentRouterConfig shape check.

SHARED-WITH-M5 v0.4.0 ships IntentRouterConfig. xfail lifted per Known
Blockers row 2 (AC12.4).
"""

from __future__ import annotations


def test_m5_exposes_intent_router_config():
    """M5 v0.4.0 exposes IntentRouterConfig under m5_config_loader."""
    from m5_config_loader import IntentRouterConfig  # noqa: F401

    cfg = IntentRouterConfig(
        model_id="anthropic.claude-3-5-haiku-20241022-v1:0",
        provider="bedrock",
        region="us-east-1",
        confidence_high=0.95,
        confidence_med=0.80,
        timeout_ms=1500,
        fallback_enabled=True,
        tenant_hmac_key_vault_path=(
            "secret/data/m9/tenants/<tenant_id>/hmac_key"
        ),
    )
    assert cfg.provider == "bedrock"
    assert cfg.confidence_high > cfg.confidence_med
