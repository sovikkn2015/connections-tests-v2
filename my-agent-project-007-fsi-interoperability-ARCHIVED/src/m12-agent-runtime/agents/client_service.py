"""
M12 Client Service Specialist — Strands Agent for client data requests.

Handles: meeting prep, portfolio reviews, client summaries, account inquiries.
Model: Haiku (fast, conversational).
Tools: Salesforce, Orion, eMoney, Schwab, memory, compliance — all via M6.

No direct vendor calls (Rule 4). No cross-module imports (Rule 9).
MNPI filtered by M4 before LLM sees data (Rule 7).
"""

from __future__ import annotations

import logging

from strands import Agent

from ..config import get_haiku_model
from ..tools.m6_tools import (
    get_account_balances,
    get_client_profile,
    get_financial_plan,
    get_holdings,
)
from ..tools.compliance_tools import check_compliance
from ..tools.memory_tools import (
    get_client_preferences,
    get_recent_interactions,
)

logger = logging.getLogger("m12.agents.client_service")

CLIENT_SERVICE_SYSTEM_PROMPT = """\
You are a client service specialist for a wealth management firm.

YOUR CAPABILITIES:
- Prepare meeting briefs with client profile, holdings, and plan data
- Create portfolio review summaries with performance and allocation
- Answer account balance and position inquiries
- Retrieve recent interaction history for context

RULES YOU MUST FOLLOW:
1. Always use tools to get real data — NEVER fabricate or guess
2. Cite which systems the data came from (Salesforce, Orion, eMoney)
3. Run compliance check before accessing sensitive client data
4. If a compliance check returns DENY, inform the user and stop
5. Present data clearly with relevant context
6. Flag any data inconsistencies across systems
7. Never make investment recommendations — that requires compliance
"""


def create_client_service_agent() -> Agent:
    """Create a client service specialist Strands Agent."""
    model = get_haiku_model()
    if model is None:
        logger.warning("Bedrock unavailable — client service agent "
                       "will have no LLM reasoning")

    return Agent(
        model=model,
        system_prompt=CLIENT_SERVICE_SYSTEM_PROMPT,
        tools=[
            get_client_profile,
            get_holdings,
            get_financial_plan,
            get_account_balances,
            get_recent_interactions,
            get_client_preferences,
            check_compliance,
        ],
    )
