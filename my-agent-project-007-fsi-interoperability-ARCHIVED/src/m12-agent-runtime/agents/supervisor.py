"""
M12 Supervisor Agent — Routes requests to specialist agents.

The supervisor uses Haiku to decide which specialist to invoke.
Each specialist is wrapped as a @tool so the LLM can call it.
No if/else routing — the model reasons about which specialist fits.

This is v2 (Strands). v1 is M9 regex router. Both coexist per ARCH-10.

No direct vendor calls (Rule 4). No cross-module imports (Rule 9).
Compliance via OPA/M2 (Rule 5). MNPI filtered by M4 (Rule 7).
"""

from __future__ import annotations

import logging

from strands import Agent, tool

from ..config import get_haiku_model
from .client_service import create_client_service_agent
from .research import create_research_agent
from .execution import create_execution_agent
from .onboarding import create_onboarding_agent
from ..tools.compliance_tools import check_compliance

logger = logging.getLogger("m12.agents.supervisor")

SUPERVISOR_SYSTEM_PROMPT = """\
You are a wealth management supervisor agent. Your job is to route
requests to the appropriate specialist and synthesize their responses.
"""

SUPERVISOR_SYSTEM_PROMPT += """\

ROUTING RULES:
- Client data requests (meeting prep, portfolio reviews, client summaries,
  account inquiries) → use client_service_specialist
- Research questions (SEC filings, market analysis, earnings, sector
  analysis, company research) → use research_specialist
- Compliance checks (restricted list, concentration, suitability,
  regulatory) → use compliance_check directly
- Trade orders (buy, sell, rebalance, order preparation) →
  use execution_specialist
- New client onboarding (KYC, sanctions, risk profiling, account
  opening) → use onboarding_specialist

RULES YOU MUST FOLLOW:
1. Always check compliance before financial actions
2. Never fabricate data — always delegate to a specialist with tools
3. If a request spans multiple domains, call multiple specialists
4. Synthesize specialist responses into a coherent answer
5. If unsure which specialist to use, ask the user for clarification
6. Never bypass compliance — if compliance_check returns DENY, stop
"""


def create_supervisor_agent() -> Agent:
    """Create the supervisor agent with specialists as tools."""

    @tool
    def client_service_specialist(request: str) -> str:
        """Handle client-related requests: meeting prep, portfolio
        reviews, client summaries, account inquiries. Use for any
        request about a specific client or their financial data."""
        agent = create_client_service_agent()
        result = agent(request)
        return str(result)

    @tool
    def research_specialist(query: str) -> str:
        """Deep financial research: SEC filings, market analysis,
        earnings, sector analysis. Use for research questions that
        need multiple sources and synthesis."""
        agent = create_research_agent()
        result = agent(query)
        return str(result)

    @tool
    def execution_specialist(request: str) -> str:
        """Trade execution: prepare orders, validate compliance,
        submit for human approval. Use for any buy/sell/rebalance
        request. Orders always require human approval."""
        agent = create_execution_agent()
        result = agent(request)
        return str(result)

    @tool
    def onboarding_specialist(request: str) -> str:
        """New client onboarding: KYC, sanctions screening, risk
        profiling, account opening. Use for new client setup."""
        agent = create_onboarding_agent()
        result = agent(request)
        return str(result)

    model = get_haiku_model()
    if model is None:
        logger.warning("Bedrock unavailable — supervisor agent "
                       "will have no LLM reasoning")

    supervisor = Agent(
        model=model,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        tools=[
            client_service_specialist,
            research_specialist,
            check_compliance,
            execution_specialist,
            onboarding_specialist,
        ],
    )
    return supervisor
