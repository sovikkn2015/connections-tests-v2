"""
M9 Task 11 -- Determinism + input immutability property tests.

AC1.5-1.7, AC10.1-10.7.
"""

from __future__ import annotations

import copy

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from m9_intent_router import IntentCategory, route
from m9_intent_router.models import LlmClassification


def _seeded_provider(utter: str, intent=IntentCategory.RESEARCH_MEETING_PREP):
    from m9_intent_router.llm_client import FakeLlmClient

    return FakeLlmClient(
        responses={
            utter: LlmClassification(
                intent=intent,
                confidence=0.97,
                entities={},
                latency_ms=50,
                model="fake",
                provider="fake",
            )
        }
    )


@given(
    utterance=st.sampled_from(
        [
            "prep me for the meeting",
            "pull up 003xx0000012ABCAA2",
            "show me household HH-A1B2C3D4E5",
        ]
    )
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_route_determinism(
    utterance,
    fixture_aid_advisor,
    fixture_router_context_factory,
    fixture_intent_router_config,
):
    """Same inputs -> equal RoutingDecision sans llm_latency_ms."""
    ctx = fixture_router_context_factory(fixture_aid_advisor)
    provider = _seeded_provider(utterance)
    d1 = route(
        utterance, ctx, _provider=provider, _config=fixture_intent_router_config
    )
    d2 = route(
        utterance, ctx, _provider=provider, _config=fixture_intent_router_config
    )
    assert d1.model_dump(exclude={"llm_latency_ms"}) == d2.model_dump(
        exclude={"llm_latency_ms"}
    )


@given(
    utterance=st.sampled_from(
        [
            "prep me for the meeting",
            "find the client",
            "pull up 003xx0000012ABCAA2",
        ]
    ),
    prior=st.one_of(st.none(), st.text(max_size=50)),
)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_prior_turns_ignored(
    utterance,
    prior,
    fixture_aid_advisor,
    fixture_intent_router_config,
):
    """AC1.7 -- prior_turns_summary accepted but ignored in Phase 2."""
    from m5_config_loader import Archetype, Runtime
    from m9_intent_router import RouterContext

    ctx_none = RouterContext(
        trace_id="t",
        runtime=Runtime.managed_agents,
        archetype=Archetype.tier4_independent_ria,
        tenant_id=fixture_aid_advisor.firm_id,
        identity=fixture_aid_advisor,
        prior_turns_summary=None,
    )
    ctx_with = RouterContext(
        trace_id="t",
        runtime=Runtime.managed_agents,
        archetype=Archetype.tier4_independent_ria,
        tenant_id=fixture_aid_advisor.firm_id,
        identity=fixture_aid_advisor,
        prior_turns_summary=prior,
    )
    provider = _seeded_provider(utterance)
    d1 = route(
        utterance,
        ctx_none,
        _provider=provider,
        _config=fixture_intent_router_config,
    )
    d2 = route(
        utterance,
        ctx_with,
        _provider=provider,
        _config=fixture_intent_router_config,
    )
    assert d1.intent == d2.intent
    assert d1.reason_code == d2.reason_code


@given(utterance=st.sampled_from(["prep me", "find client", "quote on NVDA"]))
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_input_immutability(
    utterance,
    fixture_aid_advisor,
    fixture_router_context_factory,
    fixture_intent_router_config,
):
    """AC1.6 -- route() does not mutate inputs."""
    ctx = fixture_router_context_factory(fixture_aid_advisor)
    ctx_snapshot = copy.deepcopy(ctx.model_dump())
    utter_snapshot = utterance
    provider = _seeded_provider(utterance)
    route(
        utterance, ctx, _provider=provider, _config=fixture_intent_router_config
    )
    assert ctx.model_dump() == ctx_snapshot
    assert utterance == utter_snapshot
