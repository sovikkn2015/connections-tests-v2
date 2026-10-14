"""Shared M8 test fixtures.

Builds RoutingDecision + FakePipelineConfig stand-ins for M8 tests.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, Field


class FakePipelineConfig(BaseModel):
    """Duck-typed stand-in for M5 v0.4.0's forthcoming PipelineConfig."""

    model_config = ConfigDict(extra="forbid")
    model_id: str = "anthropic.claude-sonnet-4-5-20250929-v1:0"
    model_provider: str = "bedrock"
    region: str = "us-east-1"
    checkpointer_backend: str = "memory"
    checkpointer_dsn_vault_path: str = "secret/data/m8/checkpointer_dsn"
    hitl_hmac_key_vault_path: str = "secret/data/m8/hitl_hmac_key"
    hitl_timeout_seconds: int = Field(default=14400, ge=1)
    max_concurrent_instruments: int = Field(default=10, ge=1)
    max_pipeline_wall_clock_seconds: int = Field(default=1200, ge=1)
    alert_pipeline_wall_clock_seconds: int = Field(default=900, ge=1)
    gateway_base_url: str = "https://m6-gateway.internal:8443"
    gateway_mtls_client_cert_path: str = "/etc/m8/mtls/client.pem"
    audit_base_url: str = "https://m10-audit.internal:8443"
    audit_mtls_client_cert_path: str = "/etc/m8/mtls/audit-client.pem"
    token_budgets: dict[str, int] = Field(default_factory=dict)


@pytest.fixture
def fake_pipeline_config() -> FakePipelineConfig:
    return FakePipelineConfig()


def make_pipeline_routing_decision(
    *, name: str = "m8.research_pipeline_1", tenant_id: str = "tenant-1"
) -> Any:
    """Build a minimal RoutingDecision with kind=pipeline."""
    from m9_intent_router.models import RoutingDecision
    from m9_intent_router.taxonomy import IntentCategory, SelectedTarget

    return RoutingDecision(
        trace_id="trace-test-" + uuid.uuid4().hex[:8],
        utterance_sha256="a" * 64,
        intent=IntentCategory.RESEARCH_MEETING_PREP,
        confidence=0.99,
        entities={"ticker": "NVDA"},
        selected_target=SelectedTarget(kind="pipeline", name=name),
        fallback_used=False,
        llm_latency_ms=10,
        llm_model="fake",
        llm_provider="fake",
        reason_code=None,
        tenant_id=tenant_id,
    )


@pytest.fixture
def fixture_routing_decision_pipeline():
    return make_pipeline_routing_decision()


def make_initial_state(
    *,
    routing_decision: Any = None,
    tenant_id: str = "tenant-1",
    firm_id: str = "firm-abc",
    thread_id: str | None = None,
) -> dict:
    if routing_decision is None:
        routing_decision = make_pipeline_routing_decision(tenant_id=tenant_id)
    return {
        "trace_id": "trace-" + uuid.uuid4().hex[:12],
        "thread_id": thread_id or ("thread-" + uuid.uuid4().hex[:16]),
        "pipeline_run_id": "run-" + uuid.uuid4().hex[:12],
        "tenant_id": tenant_id,
        "firm_id": firm_id,
        "routing_decision": routing_decision,
        "user_utterance": "Research NVDA earnings",
        "runtime": "managed_agents",
        "archetype": "tier4_independent_ria",
        "supervisor_aid_token": "fake-aid-token",
    }


@pytest.fixture
def fixture_initial_state():
    return make_initial_state()


__all__ = [
    "FakePipelineConfig",
    "fake_pipeline_config",
    "make_pipeline_routing_decision",
    "fixture_routing_decision_pipeline",
    "make_initial_state",
    "fixture_initial_state",
]
