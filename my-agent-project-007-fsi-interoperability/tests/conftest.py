"""
Test conftest for Project 007.

Hosts M9 shared fixtures (F1-F5 per spec Fixtures Catalog). Other modules
bring their own fixtures in-file; we extend here without overwriting.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict, Field

from m1_identity import AidClaims, Role
from m5_config_loader import Archetype, Runtime

# -----------------------------------------------------------------------------
# F1: fixture_tenant_hmac_key
# -----------------------------------------------------------------------------

_FIXTURE_TENANT_HMAC_KEY = b"m9-test-fixture-not-a-real-key!!"  # 32 bytes


@pytest.fixture(scope="session")
def fixture_tenant_hmac_key() -> bytes:
    return _FIXTURE_TENANT_HMAC_KEY


# -----------------------------------------------------------------------------
# F2: AidClaims fixtures (advisor / agent / compliance_officer).
# -----------------------------------------------------------------------------

# Common AID fields. registration_type must be a valid M5 enum value
# (Phase 2 RIA lighthouse -> "ria_only").
_COMMON_AID = dict(
    iss="007-fsi-platform",
    aud="007-mcp-gateway",
    firm_id="firm-hyp-fixture",
    lei=None,
    crd_number="CRD-1",
    archetype="tier4_independent_ria",  # firm-level (Fix 4)
    registration_type="ria_only",
    iat=1747368000,
    nbf=1747368000,
    exp=1747371600,
)


@pytest.fixture
def fixture_aid_advisor() -> AidClaims:
    return AidClaims(
        sub="advisor-01",
        role=Role.advisor,
        authority_scope=[
            "research.read",
            "research.execute",
            "client.read",
            "goal.read",
            "plan.read",
            "trade.read",
        ],
        authority_excludes=[],
        jti="aid-advisor-0001",
        **_COMMON_AID,
    )


@pytest.fixture
def fixture_aid_agent() -> AidClaims:
    """Agent role -- narrower authority (Fix 8 downgrades TRADE_INQUIRY)."""
    return AidClaims(
        sub="agent-01",
        role=Role.agent,
        authority_scope=["research.read", "client.read", "trade.read"],
        authority_excludes=["trade.execute", "plan.write"],
        jti="aid-agent-0001",
        **_COMMON_AID,
    )


@pytest.fixture
def fixture_aid_compliance_officer() -> AidClaims:
    return AidClaims(
        sub="compliance-01",
        role=Role.compliance_officer,
        authority_scope=["*"],
        authority_excludes=["trade.execute"],
        jti="aid-compliance-0001",
        **_COMMON_AID,
    )


# -----------------------------------------------------------------------------
# F3: fixture_router_context_factory
# -----------------------------------------------------------------------------


@pytest.fixture
def fixture_router_context_factory():
    from m9_intent_router import RouterContext

    def _make(aid: AidClaims, *, trace_id: str = "test-trace-0001"):
        return RouterContext(
            trace_id=trace_id,
            runtime=Runtime.managed_agents,
            archetype=Archetype.tier4_independent_ria,
            tenant_id=aid.firm_id,
            identity=aid,
            prior_turns_summary=None,
        )

    return _make


# -----------------------------------------------------------------------------
# F4: fixture_fake_llm_factory -- keyed by raw utterance for simplicity.
# -----------------------------------------------------------------------------


@pytest.fixture
def fixture_fake_llm_factory():
    from m9_intent_router.llm_client import FakeLlmClient

    def _make(utterance_to_response: dict) -> FakeLlmClient:
        return FakeLlmClient(responses=dict(utterance_to_response))

    return _make


# -----------------------------------------------------------------------------
# F5: FakeIntentRouterConfig (TODO M5 v0.3.0 -- use real IntentRouterConfig).
# -----------------------------------------------------------------------------


class FakeIntentRouterConfig(BaseModel):
    """Duck-typed stand-in for M5's forthcoming IntentRouterConfig sub-model.

    TODO(M5 v0.3.0): switch to m5_config_loader.IntentRouterConfig per AC12.4.
    """

    model_config = ConfigDict(extra="forbid")
    model_id: str = "anthropic.claude-3-5-haiku-20241022-v1:0"
    provider: str = "bedrock"
    region: str = "us-east-1"
    confidence_high: float = Field(default=0.95, ge=0.0, le=1.0)
    confidence_med: float = Field(default=0.80, ge=0.0, le=1.0)
    timeout_ms: int = Field(default=1500, ge=1)
    fallback_enabled: bool = True
    tenant_hmac_key_vault_path: str = (
        "secret/data/m9/tenants/<tenant_id>/hmac_key"
    )


@pytest.fixture
def fixture_intent_router_config() -> FakeIntentRouterConfig:
    return FakeIntentRouterConfig()


# -----------------------------------------------------------------------------
# Tenant HMAC resolver bypass for tests -- monkeypatches the Vault adapter.
# -----------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _bypass_vault_in_m9(monkeypatch):
    """Patch m9_intent_router.hmac_util._resolve_tenant_hmac_key to return the
    fixture key directly, bypassing AWS Secrets Manager.

    Autouse so every test exercising route() gets a consistent key.
    Clears the LRU cache before patching so callers see the fake.
    """
    from m9_intent_router import hmac_util

    def _fake(tenant_id: str, vault_path: str) -> bytes:  # noqa: ARG001
        return _FIXTURE_TENANT_HMAC_KEY

    hmac_util._resolve_tenant_hmac_key.cache_clear()
    monkeypatch.setattr(hmac_util, "_resolve_tenant_hmac_key", _fake)
    # route.py holds its own reference imported at module load. Import the
    # submodule explicitly to avoid name collision with the route() function.
    import importlib

    route_mod = importlib.import_module("m9_intent_router.route")
    monkeypatch.setattr(route_mod, "_resolve_tenant_hmac_key", _fake)
    yield


# -----------------------------------------------------------------------------
# M8 shared fixtures re-exported from tests/fixtures/m8_fixtures.py
# -----------------------------------------------------------------------------

from tests.fixtures.m8_fixtures import (  # noqa: E402,F401
    FakePipelineConfig,
    fake_pipeline_config,
    fixture_initial_state,
    fixture_routing_decision_pipeline,
    make_initial_state,
    make_pipeline_routing_decision,
)
