"""
M12 Onboarding Specialist — Strands Agent for new client onboarding.

Handles: KYC collection, sanctions screening, risk profiling, account opening.
Model: Haiku (conversational, step-by-step guidance).
Tools: client profile, compliance (KYC/AML) — all via M6.

No direct vendor calls (Rule 4). No cross-module imports (Rule 9).
MNPI filtered by M4 before LLM sees data (Rule 7).
"""

from __future__ import annotations

import logging

from strands import Agent

from ..config import get_haiku_model
from ..tools.m6_tools import get_client_profile
from ..tools.compliance_tools import check_compliance

logger = logging.getLogger("m12.agents.onboarding")

ONBOARDING_SYSTEM_PROMPT = """\
You are a client onboarding specialist for a wealth management firm.

YOUR CAPABILITIES:
- Guide new clients through KYC (Know Your Customer) process
- Initiate sanctions screening via compliance tools
- Collect risk profiling information step by step
- Coordinate account opening workflow

RULES YOU MUST FOLLOW:
1. Collect information step by step — don't overwhelm the client
2. Run compliance check (KYC/AML) at each verification stage
3. If compliance returns DENY, flag immediately and escalate
4. Never skip sanctions screening — it is mandatory
5. Document all collected information clearly
6. Flag any compliance concerns immediately to the advisor
7. Never fabricate client information or screening results
8. All screening results come from compliance tools, not your judgment
"""


def create_onboarding_agent() -> Agent:
    """Create an onboarding specialist Strands Agent."""
    model = get_haiku_model()
    if model is None:
        logger.warning("Bedrock unavailable — onboarding agent "
                       "will have no LLM reasoning")

    return Agent(
        model=model,
        system_prompt=ONBOARDING_SYSTEM_PROMPT,
        tools=[
            get_client_profile,
            check_compliance,
        ],
    )
