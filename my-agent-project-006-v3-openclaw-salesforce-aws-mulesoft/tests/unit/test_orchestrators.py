"""Concrete orchestrator behavior — research, advisor, liaison."""

from __future__ import annotations

from typing import List

import pytest

from openclaw.orchestration.messages import (
    AgentError,
    AgentErrorType,
    OrchestratorDispatch,
    SessionContext,
    WorkerResponse,
)
from openclaw.orchestration.topology import orchestrator_for_persona
from openclaw.orchestration._stubs import StubBedrockClient
from openclaw.orchestration.research_orchestrator import (
    RESEARCH_SPECIALISTS,
    ResearchOrchestratorImpl,
    enforce_citations,
)
from openclaw.orchestration.advisor_orchestrator import (
    AdvisorIntent,
    AdvisorOrchestratorImpl,
    classify_intent,
)
from openclaw.orchestration.liaison_orchestrator import (
    LiaisonDecision,
    LiaisonOrchestratorImpl,
    classify_inquiry,
)


pytestmark = pytest.mark.asyncio


def make_ctx(persona: str) -> SessionContext:
    return SessionContext(
        session_id="s1",
        principal_id="u1",
        persona=persona,
        correlation_id="c1",
    )


# ------------------------------ research ----------------------------------


async def test_research_plans_all_five_specialists() -> None:
    orch = ResearchOrchestratorImpl(
        orchestrator_for_persona("fsi_research"),
        StubBedrockClient(),
    )
    # Query must contain a statement-analysis trigger word to get all 5
    dispatches = await orch.plan(
        "Research NVDA ahead of earnings — focus on margin trends and ROE", make_ctx("fsi_research")
    )
    ids = [d.target_agent_id for d in dispatches]
    for specialist in RESEARCH_SPECIALISTS:
        assert specialist in ids


async def test_research_narrows_on_sentiment_only_query() -> None:
    orch = ResearchOrchestratorImpl(
        orchestrator_for_persona("fsi_research"),
        StubBedrockClient(),
    )
    dispatches = await orch.plan("score AAPL sentiment", make_ctx("fsi_research"))
    ids = [d.target_agent_id for d in dispatches]
    # Sentiment-only path narrows to 3 specialists.
    assert "filings_specialist" not in ids
    assert "statement_specialist" not in ids
    assert "sentiment_specialist" in ids


async def test_research_synthesis_surfaces_compliance_deny() -> None:
    orch = ResearchOrchestratorImpl(
        orchestrator_for_persona("fsi_research"),
        StubBedrockClient(),
    )
    responses: List[WorkerResponse] = [
        WorkerResponse(
            agent_id="market_specialist",
            result={"text": "Stable quote [src:mkt_1]."},
            citations=["mkt_1"],
            cost_tokens=100,
        ),
        WorkerResponse(
            agent_id="compliance_specialist",
            result={"text": '{"status": "DENY", "reasons": ["restricted list hit"]}'},
            citations=["comp_1"],
            cost_tokens=50,
        ),
    ]
    out = await orch.synthesize("Research NVDA", make_ctx("fsi_research"), responses)
    assert "compliance_status: DENY" in out
    assert "rm_consumable: false" in out


async def test_enforce_citations_strips_unsourced_sentences() -> None:
    body = (
        "## section\n"
        "NVDA is up today. This sentence has no citation. "
        "NVDA trades higher [src:mkt_1]. "
        "Another claim with no cite."
    )
    cleaned = enforce_citations(body)
    assert "no citation" not in cleaned
    assert "NVDA trades higher [src:mkt_1]" in cleaned
    # Heading preserved.
    assert "## section" in cleaned


async def test_enforce_citations_preserves_json_lines() -> None:
    body = '{"sentiment_score": 0.15}\nPlain sentence without cite.'
    cleaned = enforce_citations(body)
    assert '{"sentiment_score": 0.15}' in cleaned
    assert "Plain sentence" not in cleaned


# ------------------------------ advisor ----------------------------------


def test_classify_intent_action_write() -> None:
    assert classify_intent("Sell 100 NVDA") is AdvisorIntent.ACTION_WRITE
    assert classify_intent("Wire $24K to HSBC") is AdvisorIntent.ACTION_WRITE
    assert classify_intent("Rebalance Patel") is AdvisorIntent.ACTION_WRITE


def test_classify_intent_suitability() -> None:
    assert classify_intent("Is this suitable for Patel?") is AdvisorIntent.SUITABILITY


def test_classify_intent_portfolio() -> None:
    assert (
        classify_intent("What's the portfolio concentration in tech?")
        is AdvisorIntent.PORTFOLIO
    )


def test_classify_intent_research_aware_default() -> None:
    assert (
        classify_intent("Which clients care about NVDA earnings?")
        is AdvisorIntent.RESEARCH_AWARE
    )


async def test_advisor_action_write_dispatches_only_action_specialist() -> None:
    orch = AdvisorOrchestratorImpl(
        orchestrator_for_persona("fsi_advisor"),
        StubBedrockClient(),
    )
    dispatches = await orch.plan("Sell 100 NVDA from Patel", make_ctx("fsi_advisor"))
    assert len(dispatches) == 1
    assert dispatches[0].target_agent_id == "action_specialist"
    assert dispatches[0].timeout_s >= 20  # Draft-only mode fits in 29s gateway


async def test_advisor_research_aware_dispatches_two_specialists() -> None:
    orch = AdvisorOrchestratorImpl(
        orchestrator_for_persona("fsi_advisor"),
        StubBedrockClient(),
    )
    # A query without PORTFOLIO or ACTION keywords triggers the default
    # RESEARCH_AWARE path with parallel client_context + portfolio fanout.
    dispatches = await orch.plan(
        "Tell me about NVDA for client meetings", make_ctx("fsi_advisor")
    )
    ids = [d.target_agent_id for d in dispatches]
    assert "client_context_specialist" in ids
    assert "portfolio_specialist" in ids
    assert "action_specialist" not in ids


# ------------------------------ liaison ----------------------------------


def test_classify_faq_known_phrases() -> None:
    assert classify_inquiry("what are market hours?") is LiaisonDecision.FAQ
    assert classify_inquiry("schedule a call with my RM") is LiaisonDecision.FAQ


def test_classify_escalation_ticker_mentions() -> None:
    assert (
        classify_inquiry("Should I sell my NVDA?") is LiaisonDecision.ESCALATE
    )
    assert (
        classify_inquiry("AMD is crashing, what should I do?")
        is LiaisonDecision.ESCALATE
    )


def test_classify_escalates_by_default_on_ambiguity() -> None:
    assert classify_inquiry("random weird question") is LiaisonDecision.ESCALATE


async def test_liaison_faq_plan_dispatches_faq_specialist() -> None:
    orch = LiaisonOrchestratorImpl(
        orchestrator_for_persona("fsi_client_liaison"),
        StubBedrockClient(),
    )
    dispatches = await orch.plan(
        "what are market hours?", make_ctx("fsi_client_liaison")
    )
    assert len(dispatches) == 1
    assert dispatches[0].target_agent_id == "faq_specialist"


async def test_liaison_escalation_plan_skips_specialist() -> None:
    """Escalation path returns empty dispatches — rm_handoff runs in synthesize()."""
    orch = LiaisonOrchestratorImpl(
        orchestrator_for_persona("fsi_client_liaison"),
        StubBedrockClient(),
    )
    dispatches = await orch.plan(
        "should I sell my NVDA?", make_ctx("fsi_client_liaison")
    )
    # Escalation no longer dispatches context_specialist (it was timing out
    # at ~21s). The rm_handoff in synthesize() handles the handoff directly.
    assert len(dispatches) == 0


async def test_liaison_response_always_includes_disclaimer() -> None:
    orch = LiaisonOrchestratorImpl(
        orchestrator_for_persona("fsi_client_liaison"),
        StubBedrockClient(),
    )
    responses = [
        WorkerResponse(
            agent_id="faq_specialist",
            result={"text": "Markets open 9:30-4:00 ET weekdays."},
        )
    ]
    out = await orch.synthesize(
        "what are market hours?", make_ctx("fsi_client_liaison"), responses
    )
    assert "RM makes recommendations" in out


async def test_liaison_mnpi_tripwire_redacts_leaked_dollars() -> None:
    orch = LiaisonOrchestratorImpl(
        orchestrator_for_persona("fsi_client_liaison"),
        StubBedrockClient(),
    )
    # Simulate a FAQ specialist that leaked a dollar amount
    responses = [
        WorkerResponse(
            agent_id="faq_specialist",
            result={"text": "You have $250,000 in NVDA. Market hours are 9:30-4."},
        )
    ]
    out = await orch.synthesize(
        "what are market hours?", make_ctx("fsi_client_liaison"), responses
    )
    assert "$250,000" not in out
    assert "[$REDACTED]" in out
