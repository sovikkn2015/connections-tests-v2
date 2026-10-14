"""
M12 Execution Specialist — Strands Agent for trade order lifecycle.

Handles: order preparation, compliance validation, order submission.
Model: Haiku (fast, structured).
Tools: holdings, balances, compliance, concentration, submit — via M6.
HITL mandatory: orders require human approval (enforced by M6).

No direct vendor calls (Rule 4). No cross-module imports (Rule 9).
MNPI filtered by M4 before LLM sees data (Rule 7).
"""

from __future__ import annotations

import logging

from strands import Agent

from ..config import get_haiku_model
from ..tools.m6_tools import (
    get_account_balances,
    get_holdings,
    submit_order,
)
from ..tools.compliance_tools import (
    check_compliance,
    check_concentration,
)

logger = logging.getLogger("m12.agents.execution")

EXECUTION_SYSTEM_PROMPT = """\
You are a trade execution specialist for a wealth management firm.

YOUR CAPABILITIES:
- Prepare trade orders with proper specifications
- Validate orders against compliance rules and concentration limits
- Submit orders for human approval (HITL mandatory)
- Check current holdings and account balances before trading

RULES YOU MUST FOLLOW:
1. ALWAYS run check_compliance before ANY order submission
2. ALWAYS run check_concentration for position sizing
3. If compliance returns DENY, DO NOT submit — inform the user
4. Orders REQUIRE human approval — you prepare, humans approve
5. Never submit an order without compliance clearance
6. Always verify current holdings before proposing trades
7. Include clear rationale for each trade in the order spec
8. Never fabricate prices, quantities, or account data
"""


def create_execution_agent() -> Agent:
    """Create an execution specialist Strands Agent."""
    model = get_haiku_model()
    if model is None:
        logger.warning("Bedrock unavailable — execution agent "
                       "will have no LLM reasoning")

    return Agent(
        model=model,
        system_prompt=EXECUTION_SYSTEM_PROMPT,
        tools=[
            get_holdings,
            get_account_balances,
            check_compliance,
            check_concentration,
            submit_order,
        ],
    )
