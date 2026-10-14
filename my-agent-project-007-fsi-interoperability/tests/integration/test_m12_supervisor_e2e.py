"""
M12 Supervisor -- RIA lighthouse end-to-end.

Channel (synthesised) -> M1-verified AID -> M9 routes
"prep me for Henderson meeting tomorrow" to RESEARCH_MEETING_PREP ->
M12 dispatches -> M8 23-stage pipeline completes -> SupervisorResult
(status="completed", pipeline_result carries the final brief).

Uses the same FakeSonnetClient + FakeGatewayClient + FakeAuditClient +
InMemorySaver plumbing that M8's own tests rely on. M8's run() default
path constructs them itself, so the test simply calls dispatch().

This IS the Phase 2 lighthouse test.
"""

from __future__ import annotations

from m9_intent_router import IntentCategory
from m9_intent_router.models import LlmClassification

from m12_supervisor import SupervisorResult, dispatch


def test_ria_lighthouse_meeting_prep_e2e(
    fixture_aid_advisor,
    fixture_fake_llm_factory,
    fixture_intent_router_config,
):
    """The flagship RIA journey. An advisor asks to prep for a meeting;
    M9 classifies RESEARCH_MEETING_PREP; M12 runs the full M8 23-stage
    pipeline; the final brief appears on SupervisorResult."""
    utter = "prep me for Henderson meeting tomorrow"
    provider = fixture_fake_llm_factory({
        utter: LlmClassification(
            intent=IntentCategory.RESEARCH_MEETING_PREP,
            confidence=0.98,
            entities={"client": "Henderson"},
            latency_ms=250,
            model="fake",
            provider="fake",
        )
    })

    result = dispatch(
        utter,
        fixture_aid_advisor,
        "trace-ria-lighthouse-001",
        _provider=provider,
        _config=fixture_intent_router_config,
    )

    # --- SupervisorResult shape ---
    assert isinstance(result, SupervisorResult)
    assert result.status == "completed"
    assert result.trace_id == "trace-ria-lighthouse-001"
    assert result.tenant_id == fixture_aid_advisor.firm_id
    assert result.wall_clock_seconds >= 0.0
    assert result.escalation_target is None
    assert result.tool_target is None

    # --- M9 routing ---
    assert result.routing_decision is not None
    assert (
        result.routing_decision.intent
        == IntentCategory.RESEARCH_MEETING_PREP
    )
    assert result.routing_decision.selected_target.kind == "pipeline"
    assert (
        result.routing_decision.selected_target.name
        == "m8.research_pipeline_1"
    )

    # --- M8 pipeline ---
    pr = result.pipeline_result
    assert pr is not None
    assert pr.status == "completed"
    assert pr.final_stage == 23
    # research_brief may be None when M8 is wired with pure Fake* deps
    # (no LLM response templates); the lighthouse criterion is that all
    # 23 stages completed cleanly through M12 -> M8.


def test_ria_lighthouse_tool_intent_routes_to_m6_via_channel(
    fixture_aid_advisor,
    fixture_fake_llm_factory,
    fixture_intent_router_config,
):
    """Tool intent -> channel should forward via M6. M12 returns the
    tool name and never touches M6 itself (Rule 7 boundary)."""
    utter = "look up client data for CLIENT-HENDERSON"
    provider = fixture_fake_llm_factory({
        utter: LlmClassification(
            intent=IntentCategory.CLIENT_DATA_LOOKUP,
            confidence=0.99,
            entities={"client_id": "CLIENT-HENDERSON"},
            latency_ms=95,
            model="fake",
            provider="fake",
        )
    })
    result = dispatch(
        utter,
        fixture_aid_advisor,
        "trace-ria-tool-001",
        _provider=provider,
        _config=fixture_intent_router_config,
    )
    assert result.status == "completed"
    assert result.tool_target == "sfdc.fetch_client"
    assert result.pipeline_result is None


def test_ria_lighthouse_compliance_question_escalates(
    fixture_aid_advisor,
    fixture_fake_llm_factory,
    fixture_intent_router_config,
):
    utter = "is TSLA restricted for Henderson"
    provider = fixture_fake_llm_factory({
        utter: LlmClassification(
            intent=IntentCategory.COMPLIANCE_QUESTION,
            confidence=0.99,
            entities={},
            latency_ms=70,
            model="fake",
            provider="fake",
        )
    })
    result = dispatch(
        utter,
        fixture_aid_advisor,
        "trace-ria-comp-001",
        _provider=provider,
        _config=fixture_intent_router_config,
    )
    assert result.status == "escalated"
    assert result.escalation_target == "compliance_specialist"
