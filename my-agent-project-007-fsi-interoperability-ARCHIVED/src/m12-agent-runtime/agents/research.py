"""
M12 Research Specialist — Strands Agent for deep financial research.

Handles: SEC filings, market analysis, earnings, sector analysis.
Model: Sonnet (deep reasoning for research synthesis).
Tools: SEC EDGAR, market data, news, client profile, compliance — via M6.

This is the v2 research agent. v1 is M8 LangGraph pipeline.
Both coexist per ARCH-10 Decision 2.

No direct vendor calls (Rule 4). No cross-module imports (Rule 9).
MNPI filtered by M4 before LLM sees data (Rule 7).
"""

from __future__ import annotations

import logging

from strands import Agent

from ..config import get_sonnet_model
from ..tools.m6_tools import (
    get_client_profile,
    get_market_data,
    get_news,
    search_sec_filings,
)
from ..tools.compliance_tools import check_compliance

logger = logging.getLogger("m12.agents.research")

RESEARCH_SYSTEM_PROMPT = """\
You are a financial research specialist for a wealth management firm.

YOUR CAPABILITIES:
- Search and analyze SEC filings (10-K, 10-Q, 8-K, proxy statements)
- Retrieve and interpret market data (price, volume, fundamentals)
- Search financial news for sentiment and event analysis
- Synthesize multiple sources into balanced research briefs
"""

RESEARCH_SYSTEM_PROMPT += """\

RULES YOU MUST FOLLOW:
1. Always use tools to get real data — NEVER fabricate filings or quotes
2. Always cite sources: filing type, date, and data system
3. Provide balanced analysis: include BOTH risks and opportunities
4. Never make investment recommendations without compliance check first
5. If compliance check returns DENY, inform the user and stop
6. Cross-reference multiple sources when possible
7. Clearly distinguish between facts (from filings) and analysis
8. Note any data limitations or gaps in your research
"""


def create_research_agent() -> Agent:
    """Create a research specialist Strands Agent with Sonnet model."""
    model = get_sonnet_model()
    if model is None:
        logger.warning("Bedrock unavailable — research agent "
                       "will have no LLM reasoning")

    return Agent(
        model=model,
        system_prompt=RESEARCH_SYSTEM_PROMPT,
        tools=[
            search_sec_filings,
            get_market_data,
            get_news,
            get_client_profile,
            check_compliance,
        ],
    )
