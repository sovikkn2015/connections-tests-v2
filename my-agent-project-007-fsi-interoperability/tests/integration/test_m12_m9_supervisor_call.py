"""
M9 Task 18 -- Supervisor (M12) call integration.

AC17.1-17.6: constructs RouterContext with a real AID from m1_identity,
calls route(), asserts round-trip shape per §Integration Point with M12.
Does NOT import M12 (Phase 2 depth-first).
"""

from __future__ import annotations

from m1_identity import IdentityService, Role
from m5_config_loader import Archetype, RegistrationType, Runtime

from m9_intent_router import IntentCategory, RouterContext, route
from m9_intent_router.models import LlmClassification


def test_supervisor_round_trip(
    fixture_intent_router_config,
    fixture_fake_llm_factory,
    monkeypatch,
):
    """AC17.6 -- construct RouterContext from M1 IdentityService-issued AID."""
    monkeypatch.setenv(
        "AID_SIGNING_KEY", "test-key-only-for-unit-tests-do-not-deploy!"
    )
    svc = IdentityService(audience="007-mcp-gateway")
    token = svc.issue(
        sub="advisor-01",
        firm_id="firm-abc",
        crd_number="CRD-1",
        archetype=Archetype.tier4_independent_ria,
        role=Role.advisor,
        registration_type=RegistrationType.ria_only,
        authority_scope=["research.read", "research.execute"],
        authority_excludes=[],
    )
    aid = svc.verify(token)

    ctx = RouterContext(
        trace_id="supv-2026-05-16-abc",
        runtime=Runtime.managed_agents,
        archetype=Archetype.tier4_independent_ria,
        tenant_id=aid.firm_id,
        identity=aid,
        prior_turns_summary=None,
    )

    utter = "prep me for tomorrow's meeting"
    provider = fixture_fake_llm_factory(
        {
            utter: LlmClassification(
                intent=IntentCategory.RESEARCH_MEETING_PREP,
                confidence=0.97,
                entities={},
                latency_ms=300,
                model="fake",
                provider="fake",
            )
        }
    )
    decision = route(
        utter, ctx, _provider=provider, _config=fixture_intent_router_config
    )
    # Round-trip shape.
    payload = decision.audit_payload()
    assert len(payload) == 12
    assert payload["intent"] == "research.meeting_prep"
    assert payload["tenant_id"] == "firm-abc"
    assert payload["trace_id"] == "supv-2026-05-16-abc"
    assert payload["selected_target"]["kind"] == "pipeline"
    assert payload["selected_target"]["name"] == "m8.research_pipeline_1"
