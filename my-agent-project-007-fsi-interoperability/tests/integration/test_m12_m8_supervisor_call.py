"""Integration: M12 Supervisor -> M8 Pipeline Engine round-trip.

Formerly simulated the M12 role by calling run_with_deps() directly;
now calls `m12_supervisor.dispatch()` which builds PipelineState from
a RoutingDecision and delegates to M8's default run() path.
"""

from __future__ import annotations

from m9_intent_router import IntentCategory
from m9_intent_router.models import LlmClassification

from m12_supervisor import SupervisorResult, dispatch


def test_m12_supervisor_m8_round_trip_returns_pipeline_result(
    fixture_aid_advisor,
    fixture_fake_llm_factory,
    fixture_intent_router_config,
) -> None:
    utter = "Research NVDA earnings impact"
    provider = fixture_fake_llm_factory({
        utter: LlmClassification(
            intent=IntentCategory.RESEARCH_MEETING_PREP,
            confidence=0.99,
            entities={"ticker": "NVDA"},
            latency_ms=200,
            model="fake",
            provider="fake",
        )
    })

    result = dispatch(
        utter,
        fixture_aid_advisor,
        "trace-supv-m8-1",
        _provider=provider,
        _config=fixture_intent_router_config,
    )

    assert isinstance(result, SupervisorResult)
    assert result.pipeline_result is not None
    assert result.pipeline_result.thread_id  # non-empty
    assert result.pipeline_result.pipeline_run_id  # non-empty
    assert result.status in (
        "completed",
        "paused",
        "failed",
        "timed_out",
        "rejected",
    )


def test_m12_supervisor_single_tool_bypass_variant(
    fixture_aid_advisor,
    fixture_fake_llm_factory,
    fixture_intent_router_config,
) -> None:
    """Zero-fan-out pipeline (AC5.8) -- RESEARCH_MARKET_QUERY dispatches
    to the m8.research_single_tool pipeline."""
    utter = "What's the current price of NVDA"
    provider = fixture_fake_llm_factory({
        utter: LlmClassification(
            intent=IntentCategory.RESEARCH_MARKET_QUERY,
            confidence=0.99,
            entities={"ticker": "NVDA"},
            latency_ms=200,
            model="fake",
            provider="fake",
        )
    })

    result = dispatch(
        utter,
        fixture_aid_advisor,
        "trace-supv-m8-single-1",
        _provider=provider,
        _config=fixture_intent_router_config,
    )

    assert isinstance(result, SupervisorResult)
    assert result.pipeline_result is not None
    assert result.routing_decision is not None
    assert (
        result.routing_decision.selected_target.name
        == "m8.research_single_tool"
    )


def test_m12_supervisor_tool_intent_does_not_invoke_m8(
    fixture_aid_advisor,
    fixture_fake_llm_factory,
    fixture_intent_router_config,
) -> None:
    """A tool-kind route must NOT run the M8 pipeline."""
    utter = "look up client Henderson"
    provider = fixture_fake_llm_factory({
        utter: LlmClassification(
            intent=IntentCategory.CLIENT_DATA_LOOKUP,
            confidence=0.99,
            entities={},
            latency_ms=100,
            model="fake",
            provider="fake",
        )
    })

    result = dispatch(
        utter,
        fixture_aid_advisor,
        "trace-supv-tool-1",
        _provider=provider,
        _config=fixture_intent_router_config,
    )

    assert result.status == "completed"
    assert result.tool_target == "sfdc.fetch_client"
    assert result.pipeline_result is None
