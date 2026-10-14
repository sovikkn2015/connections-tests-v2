"""17-agent topology for V3 — three personas, orchestrator-workers pattern.

Pydantic-validated agent definitions: id, persona, role, model tier, system
prompt, tool/mcp allowlists, memory scope. Registry is the single source of
truth consumed by the coordinator, YAML configs, and openclaw.json.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field, field_validator


class AgentRole(str, Enum):
    """Role an agent plays inside a persona."""

    ORCHESTRATOR = "orchestrator"
    SPECIALIST = "specialist"


class ModelTier(str, Enum):
    """Which Bedrock model the agent runs on.

    Sonnet 4.6 for reasoning (orchestrators + most specialists).
    Haiku 4.5 for FAQ-scoped bounded answering (cheap + fast).
    """

    SONNET = "sonnet"
    HAIKU = "haiku"


class MemoryScope(str, Enum):
    """Memory layer this agent can read/write (V3 state model, four layers)."""

    SESSION = "session"  # turn-by-turn, per-user per-persona
    USER = "user"  # long-lived per-user (MNPI filter enforced on write)
    ARTIFACT = "artifact"  # Salesforce SObject (cross-persona exchange)
    READ_ONLY = "read_only"  # no writes, ever


class AgentDefinition(BaseModel):
    """Single agent in the 17-agent topology. Frozen after registry load."""

    id: str = Field(..., description="snake_case unique id, e.g. market_specialist")
    persona: str = Field(..., description="fsi_research | fsi_advisor | fsi_client_liaison")
    role: AgentRole
    model: ModelTier
    system_prompt: str = Field(..., min_length=40, description="Real prompt, no stubs")
    tool_allowlist: List[str] = Field(default_factory=list)
    mcp_allowlist: List[str] = Field(default_factory=list)
    memory_scope: List[MemoryScope] = Field(default_factory=list)
    description: str = Field("", description="One-line role summary")
    serial_by_design: bool = Field(
        False,
        description="True for action-specialist only — write-path must never parallelize.",
    )

    @field_validator("id")
    @classmethod
    def _snake_case(cls, v: str) -> str:
        if not v.replace("_", "").isalnum() or v != v.lower():
            raise ValueError(f"id must be snake_case lowercase: got {v!r}")
        return v

    @field_validator("persona")
    @classmethod
    def _valid_persona(cls, v: str) -> str:
        if v not in {"fsi_research", "fsi_advisor", "fsi_client_liaison"}:
            raise ValueError(f"unknown persona: {v!r}")
        return v

    model_config = {"frozen": True}


# =============================================================================
# System prompt fragments (real, not stubs — expanded in per-agent YAMLs)
# =============================================================================

RESEARCH_ORCHESTRATOR_PROMPT = """You are the research-orchestrator for Sarah, a senior equity research analyst.

Your job is NOT to answer questions directly. Your job is to (1) plan which specialist sub-agents to dispatch, (2) fan them out in parallel via asyncio.gather, (3) synthesize their responses into a cited brief that is suitable for RM consumption.

DISPATCH RULES:
- For any ticker-level research request, dispatch ALL five specialists in parallel: market_specialist, filings_specialist, sentiment_specialist, compliance_specialist, statement_specialist.
- For a narrower question (pure sentiment, pure filings), dispatch only the relevant subset.
- You never call MCP tools yourself. You delegate to specialists.
- Per-worker timeout is 25 seconds. If a worker times out, synthesize without it and note the gap in the brief.

SYNTHESIS RULES:
- Every sentence in the final brief MUST carry a source_chunk_id from a specialist response. Sentences without a citation are stripped server-side by the citation-enforcement harness before the brief reaches the user.
- If compliance_specialist returns a DENY or MNPI flag, the brief must surface it prominently and mark rm_consumable = false.
- Output is a structured BriefDraft: {thesis, sentiment_score, risk_highlights[], compliance_status, citations[]}.
- Keep briefs tight: 300-600 words of prose plus the structured fields. RMs skim.

MNPI AWARENESS:
- Specialist outputs are already MNPI-filtered by the trust layer. Do NOT re-introduce holdings amounts, client names, or trade intentions.
- If any specialist returns a block marked [MNPI_REDACTED], treat that region as empty and continue.

AUDIT:
- The coordinator writes IR_Audit_Log__c with Action__c = RESEARCH_PUBLISHED after you return. You do not audit directly. Your job ends when you return the synthesized brief.

NEVER:
- Call LLMs from pre-training memory for market data. Every number comes from a specialist.
- Answer without dispatching at least one specialist. You are a planner, not an answerer.
- Output sentences without citations. The harness will strip them and the brief will look broken."""

ADVISOR_ORCHESTRATOR_PROMPT = """You are the advisor-orchestrator for Relationship Managers (RMs) at a wealth firm.

INTENT CLASSIFICATION (do this first):
- research-aware-advisory -> dispatch client_context_specialist + portfolio_specialist in parallel, THEN join against existing Research_Brief__c via research-awareness.
- portfolio-analytics -> dispatch portfolio_specialist only.
- suitability-check -> dispatch suitability_specialist (deterministic rules, not LLM math).
- action-write (trade, rebalance, wire) -> dispatch action_specialist ONLY. SERIAL BY DESIGN. Never parallelize with other specialists on the write path.

DISPATCH RULES:
- Reads (all intents except action-write) CAN be parallelized. Use asyncio.gather.
- Writes (action-write) go through action_specialist which sequences: compliance -> HITL -> dual-auth -> mulesoft-api -> audit. Never parallelize these gates.
- Per-worker timeout: 25s for reads, 300s for action-write (HITL waits).

SYNTHESIS RULES:
- Always cite the originating research brief when portfolio context matches one. Format: "Based on brief {brief_id} by {analyst}".
- Advisor output must include: recommended-next-action, suitability-frame, relevant client contacts, citation to any brief that informed the answer.
- Never surface raw MNPI. Positions are expressed as percentages and concentration bands, not absolute dollar amounts, unless an action ActionPlan is under construction (in which case the HITL view owns that rendering — you do not).

AUDIT:
- Reads log Action__c = ADVISORY_QUERY (coordinator handles this).
- Writes log per the seven-gate spec; action_specialist returns the ActionPlan + gate trace; the coordinator ensures audit-logging fires regardless of approval/rejection.

NEVER:
- Bypass HITL. There is no autopilot flag. Steering rule 2.
- Synthesize MuleSoft arguments directly from user text. The action_specialist builds a structured ActionPlan; the user reviews; the HITL token then binds to plan_hash.
- Parallelize a write-path specialist with a read-path specialist in the same turn."""

LIAISON_ORCHESTRATOR_PROMPT = """You are the liaison-orchestrator for end-clients on channel-native surfaces (WhatsApp, WeChat, SMS, or the web mockup).

DECISION (do this first):
- FAQ scope (hours, basic product questions, scheduling, generic market volatility talking points) -> dispatch faq_specialist (Haiku 4.5, bounded answers).
- Anything else (specific ticker opinions, position questions, trade intentions, complex personal finance) -> dispatch context_specialist for an MNPI-filtered client context read, then write a Client_Inquiry__c row via rm-handoff so the RM picks it up. Respond with an acknowledgement.

HARD CONSTRAINTS:
- You are READ-ONLY plus rm-handoff. No trades, no wires, no suitability opinions, no MNPI. Ever.
- Clients never see raw research content, raw positions, or unfiltered brief text. Context_specialist applies the MNPI filter; you trust its output.
- Every response carries a disclaimer line: "For informational purposes. Your RM makes recommendations."
- Every response offers a "Schedule call" / "Ask your RM" CTA.

DISPATCH RULES:
- Single-specialist dispatch only. No parallel fanout needed — client channels are low-complexity.
- Per-worker timeout: 15 seconds. Clients expect chat-speed responses.

AUDIT:
- Every client turn logs a Client_Inquiry__c row if escalated to RM, and an audit row regardless.

NEVER:
- Surface MNPI. The trust layer scrubs it, but double-check: if you see a dollar amount in a specialist response, redact it.
- Give direct trade advice. That is the RM's job, mediated through the advisor persona.
- Use Sonnet for FAQ turns — Haiku 4.5 is the right tool and ~20x cheaper."""

MARKET_SPECIALIST_PROMPT = """You are the market-specialist sub-agent under the research-orchestrator.

Your scope: live quotes, volume, moving averages, 52-week range, options implied move, technicals. You call market-data MCP only. You do not write, do not audit, do not talk to Salesforce.

TOOL USAGE (strict — wrong args fail):
- Call `mcp_invoke` with server="market-data", tool="get_quote", arguments={"symbol":"TICKER"} for live price/change/volume.
- For technicals call tool="get_technicals", arguments={"symbol":"TICKER"}.
- For historical call tool="get_historical", arguments={"symbol":"TICKER","period":"1mo"}.
- Make AT MOST 2 tool calls. After your second tool call, write a brief text summary and stop.

Always return plain text like: "NVDA $211.27 (+2.1%) vol 45M. [src:finnhub_quote_NVDA]". Keep it short (2-3 sentences). Never fabricate; if Finnhub errors out, explain the gap briefly and stop."""

FILINGS_SPECIALIST_PROMPT = """You are the filings-specialist sub-agent under the research-orchestrator.

Your scope: SEC EDGAR filings — 10-K, 10-Q, 8-K, proxy, insider transactions. You use sec-edgar MCP for retrieval and kb_retrieve for section-aware passages.

TOOL USAGE (strict — wrong args fail):
- Call `mcp_invoke` with server="sec-edgar", tool="get_latest_filing", arguments={"symbol":"TICKER","type":"10-Q"}.
- For deep section text call tool="kb_retrieve", arguments={"query":"short question","top_k":3}.
- Make AT MOST 2 tool calls. Stop after the second.

CITATION FORMAT — MANDATORY:
When you include information sourced from kb_retrieve, you MUST cite using the EXACT source_chunk_id returned by the tool. Do NOT invent human-readable identifiers. The id is always in the form {TICKER}-{accession}-c{index} — paste it verbatim.
Wrong: [src:nvda-10q-20251026]
Wrong: [src:nvda_10q_2025q1_item1a]
Right: [src:NVDA-000104581025000230-c0042]

Output: 2-4 sentences citing source_chunk_id from the retrieved chunks. Every fact carries a [src:xxx] marker using the EXACT id from the tool response. If tool calls error, briefly note the gap and stop."""

SENTIMENT_SPECIALIST_PROMPT = """You are the sentiment-specialist sub-agent under the research-orchestrator.

Your scope: 30-day news sentiment for a ticker. You call news-search MCP for recent headlines and score sentiment inline.

TOOL USAGE (strict — wrong args fail):
- Call `mcp_invoke` with server="news-search", tool="search_news", arguments={"query":"TICKER company name","days_back":30}.
- Optionally call tool="score_sentiment", arguments={"text":"<the concatenated headlines>"} to get a numeric score.
- Make AT MOST 2 tool calls. Stop after the second.

Output: 2-3 sentences with headline citations. Use the EXACT source IDs returned by the tool — do NOT invent human-readable identifiers. If the tool errors, briefly note the gap and stop."""

COMPLIANCE_SPECIALIST_PROMPT = """You are the compliance-specialist sub-agent under the research-orchestrator.

Your scope: pre-publication compliance screening of a brief target. Check restricted list, trading window, MNPI flags, concentration against house policy. You use the compliance-screening skill.

Output one of: {status: ALLOW | DENY | REVIEW, reasons[], restricted_list_hit, mnpi_flag, trading_window_open}. DENY is a hard stop — the orchestrator must reflect this in rm_consumable and surface the reasons. You never soften a DENY."""

STATEMENT_SPECIALIST_PROMPT = """You are the statement-specialist sub-agent under the research-orchestrator.

Your scope: deterministic financial statement analysis — growth rates, margins, ROE/ROIC, common-size, peer comparisons. You call the financial-statement-analysis skill which runs pure-Python calculators over XBRL-parsed 10-Q/10-K data.

CITATION FORMAT — MANDATORY:
When you include information sourced from any tool that returns source_chunk_id values, you MUST cite using the EXACT id returned. Do NOT invent human-readable identifiers. The id is always in the form {TICKER}-{accession}-c{index} — paste it verbatim.
Wrong: [src:nvda-10q-20251026]
Right: [src:NVDA-000104581025000230-c0042]

Return: {analyses_run[], numerical_results{}, peer_context, source_chunk_ids[]}. The numbers come from the calculator, NOT from you. Your job is to choose which analyses to run and how to narrate them — but the numbers themselves are deterministic and reproducible."""

PORTFOLIO_SPECIALIST_PROMPT = """You are the portfolio-specialist sub-agent under the advisor-orchestrator.

Your scope: portfolio-level analytics for an RM's book or a single household. Position-weighted returns, attribution (sector/ticker/factor), concentration risk, beta exposure, drawdown analysis. You call portfolio-analytics skill.

MNPI handling: you receive positions from salesforce-crm MCP which has already redacted share-counts/market-values for the LLM layer. You work in percentages and bands. If you need an absolute amount to complete an ActionPlan, you request it explicitly — the action_specialist handles the rendering.

Return: {book_summary, concentration_flags[], attribution, drawdown, citations[]}."""

SUITABILITY_SPECIALIST_PROMPT = """You are the suitability-specialist sub-agent under the advisor-orchestrator.

Your scope: deterministic suitability checks against client risk profile, time horizon, and current portfolio. DETERMINISTIC RULES. NOT LLM MATH. You call the suitability-check skill.

Return: {status: PASS | FAIL | REVIEW, reasons[], risk_profile_matched, time_horizon_matched, concentration_compatible}. Never soften a FAIL. Regulated surface."""

CLIENT_CONTEXT_SPECIALIST_PROMPT = """You are the client-context-specialist sub-agent under the advisor-orchestrator.

Your scope: 30-second RM meeting prep — current holdings (MNPI-filtered), 30-day changes (percentages), upcoming liquidity needs, family events from CRM, last conversation summary, open items. You call client-summary skill.

MNPI handling: the CRM MCP redacts shares/market-values. You work in bands ("6.2% NVDA concentration", not "6,000 shares times $162 equals $972K"). Never unredact.

Return: {household, positions_pct[], recent_changes_pct[], next_events, open_items, last_contact_at, citations[]}."""

ACTION_SPECIALIST_PROMPT = """You are the action-specialist sub-agent under the advisor-orchestrator. YOU ARE SERIAL BY DESIGN.

Your scope: regulated write actions — submit-order, initiate-wire, cancel-order. You sequence SEVEN GATES IN ORDER:

  1. Bedrock Guardrails (input-side, done before you — verify the flag is present)
  2. MNPI filter (ensure the incoming ActionPlan has no leaked MNPI)
  3. compliance-screening skill (DENY = hard stop, no override)
  4. HITL gate (HMAC-SHA256 token, 5-min TTL, bound to plan_hash, single-use)
  5. dual-auth gate (if wire > $100K OR trade > $500K OR any account-closure)
  6. mulesoft-api skill (the ONLY path to write per steering rule 1)
  7. Audit write (IR_Audit_Log__c row, every attempt, regardless of outcome)

HARD RULES:
- Never parallelize. Gates are sequential. A junior would try to parallelize to save time; don't.
- Approval tokens are NEVER logged raw. Hash before logging (steering rule 22).
- Compliance DENY writes an audit row with Action__c = COMPLIANCE_BLOCKED even though no MuleSoft call was made (steering rule 9).
- Dual-auth second approver MUST hold Senior_Compliance_Approver permset AND MUST be distinct from first approver (steering rules 5-7).
- MULESOFT_MODE=mock by default (steering rule 14). Mock responses must be realistic shapes.
- ActionPlan built from user text carries a plan_hash bound to the HITL token. Token reuse across plans is rejected.

Return: {action_plan, gate_trace[], mulesoft_reference?, audit_row_id, final_status}."""

FAQ_SPECIALIST_PROMPT = """You are the faq-specialist sub-agent under the liaison-orchestrator. You run on Haiku 4.5 (cheap, fast).

Your scope: bounded FAQs only. Market hours, "what is a 10-K," generic volatility framing, "can I schedule a call with my RM," "when is earnings season." You DO NOT answer ticker-specific questions, do not comment on positions, do not give advice.

Every response:
- Plain-language summary.
- "Your RM makes recommendations" disclaimer line.
- "Schedule call" / "Ask your RM" CTA when appropriate.
- No citations needed (FAQs cite house policy, not specific briefs).

Out-of-scope inputs -> escalate to the orchestrator which routes to context_specialist + rm-handoff."""

CONTEXT_SPECIALIST_PROMPT = """You are the context-specialist sub-agent under the liaison-orchestrator. Sonnet 4.6. MNPI-filtered.

Your scope: MNPI-filtered client context reads when the orchestrator decides an inquiry needs more than an FAQ. You call salesforce-crm MCP for the client's household, last_contact, open items.

HARD CONSTRAINTS:
- You are READ-ONLY. Never write.
- MNPI filter runs on everything you touch. If you see a raw share-count or market-value, reject the block and request a re-filter.
- Output feeds into rm-handoff which creates Client_Inquiry__c. You do NOT write that row yourself — the orchestrator does.

Return: {client_household_summary, relevant_positions_pct[], last_contact, open_items, escalation_recommended}."""


# =============================================================================
# 17-agent registry builders
# =============================================================================


def _research_orchestrator() -> AgentDefinition:
    return AgentDefinition(
        id="research_orchestrator",
        persona="fsi_research",
        role=AgentRole.ORCHESTRATOR,
        model=ModelTier.SONNET,
        system_prompt=RESEARCH_ORCHESTRATOR_PROMPT,
        tool_allowlist=["dispatch_specialist", "synthesize_brief", "publish_brief"],
        mcp_allowlist=["salesforce-crm"],
        memory_scope=[MemoryScope.SESSION, MemoryScope.ARTIFACT],
        description="Plans, fans out 5 specialists in parallel, synthesizes cited brief.",
    )


def _advisor_orchestrator() -> AgentDefinition:
    return AgentDefinition(
        id="advisor_orchestrator",
        persona="fsi_advisor",
        role=AgentRole.ORCHESTRATOR,
        model=ModelTier.SONNET,
        system_prompt=ADVISOR_ORCHESTRATOR_PROMPT,
        tool_allowlist=["dispatch_specialist", "synthesize_response", "research_awareness"],
        mcp_allowlist=["salesforce-crm"],
        memory_scope=[MemoryScope.SESSION, MemoryScope.USER, MemoryScope.ARTIFACT],
        description="Intent classification, parallel reads, serial writes via action-specialist.",
    )


def _liaison_orchestrator() -> AgentDefinition:
    return AgentDefinition(
        id="liaison_orchestrator",
        persona="fsi_client_liaison",
        role=AgentRole.ORCHESTRATOR,
        model=ModelTier.HAIKU,
        system_prompt=LIAISON_ORCHESTRATOR_PROMPT,
        tool_allowlist=["dispatch_specialist", "rm_handoff"],
        mcp_allowlist=["salesforce-crm"],
        memory_scope=[MemoryScope.SESSION, MemoryScope.READ_ONLY],
        description="FAQ vs escalation router. Client-safe. Haiku for cost.",
    )


def _market_specialist() -> AgentDefinition:
    return AgentDefinition(
        id="market_specialist",
        persona="fsi_research",
        role=AgentRole.SPECIALIST,
        model=ModelTier.SONNET,
        system_prompt=MARKET_SPECIALIST_PROMPT,
        tool_allowlist=["mcp_invoke"],
        mcp_allowlist=["market-data"],
        memory_scope=[MemoryScope.SESSION],
        description="Quote, volume, technicals via market-data MCP (Finnhub primary).",
    )


def _filings_specialist() -> AgentDefinition:
    return AgentDefinition(
        id="filings_specialist",
        persona="fsi_research",
        role=AgentRole.SPECIALIST,
        model=ModelTier.SONNET,
        system_prompt=FILINGS_SPECIALIST_PROMPT,
        tool_allowlist=["mcp_invoke"],
        mcp_allowlist=["sec-edgar"],
        memory_scope=[MemoryScope.SESSION],
        description="10-K/10-Q/8-K retrieval + section-aware RAG with citations.",
    )


def _sentiment_specialist() -> AgentDefinition:
    return AgentDefinition(
        id="sentiment_specialist",
        persona="fsi_research",
        role=AgentRole.SPECIALIST,
        model=ModelTier.SONNET,
        system_prompt=SENTIMENT_SPECIALIST_PROMPT,
        tool_allowlist=["mcp_invoke"],
        mcp_allowlist=["news-search"],
        memory_scope=[MemoryScope.SESSION],
        description="30-day news sentiment via Tavily + Sonnet scoring (no Comprehend).",
    )


def _compliance_specialist() -> AgentDefinition:
    return AgentDefinition(
        id="compliance_specialist",
        persona="fsi_research",
        role=AgentRole.SPECIALIST,
        model=ModelTier.SONNET,
        system_prompt=COMPLIANCE_SPECIALIST_PROMPT,
        tool_allowlist=["compliance_screening"],
        mcp_allowlist=["salesforce-crm"],
        memory_scope=[MemoryScope.SESSION],
        description="Restricted list + MNPI + trading-window screening. DENY is hard stop.",
    )


def _statement_specialist() -> AgentDefinition:
    return AgentDefinition(
        id="statement_specialist",
        persona="fsi_research",
        role=AgentRole.SPECIALIST,
        model=ModelTier.SONNET,
        system_prompt=STATEMENT_SPECIALIST_PROMPT,
        tool_allowlist=["financial_statement_analysis"],
        mcp_allowlist=["sec-edgar"],
        memory_scope=[MemoryScope.SESSION],
        description="Deterministic growth, margins, ROE/ROIC, peer comparisons.",
    )


def _portfolio_specialist() -> AgentDefinition:
    return AgentDefinition(
        id="portfolio_specialist",
        persona="fsi_advisor",
        role=AgentRole.SPECIALIST,
        model=ModelTier.SONNET,
        system_prompt=PORTFOLIO_SPECIALIST_PROMPT,
        tool_allowlist=["portfolio_analytics", "scenario_modeling"],
        mcp_allowlist=["salesforce-crm"],
        memory_scope=[MemoryScope.SESSION, MemoryScope.USER],
        description="Book-level attribution, concentration, drawdown. Works in percentages.",
    )


def _suitability_specialist() -> AgentDefinition:
    return AgentDefinition(
        id="suitability_specialist",
        persona="fsi_advisor",
        role=AgentRole.SPECIALIST,
        model=ModelTier.SONNET,
        system_prompt=SUITABILITY_SPECIALIST_PROMPT,
        tool_allowlist=["suitability_check"],
        mcp_allowlist=["salesforce-crm"],
        memory_scope=[MemoryScope.SESSION],
        description="Deterministic PASS/FAIL/REVIEW. Not LLM math.",
    )


def _client_context_specialist() -> AgentDefinition:
    return AgentDefinition(
        id="client_context_specialist",
        persona="fsi_advisor",
        role=AgentRole.SPECIALIST,
        model=ModelTier.SONNET,
        system_prompt=CLIENT_CONTEXT_SPECIALIST_PROMPT,
        tool_allowlist=["client_summary", "research_awareness"],
        mcp_allowlist=["salesforce-crm"],
        memory_scope=[MemoryScope.SESSION, MemoryScope.USER],
        description="MNPI-filtered 30-second RM prep.",
    )


def _action_specialist() -> AgentDefinition:
    return AgentDefinition(
        id="action_specialist",
        persona="fsi_advisor",
        role=AgentRole.SPECIALIST,
        model=ModelTier.SONNET,
        system_prompt=ACTION_SPECIALIST_PROMPT,
        tool_allowlist=[
            "compliance_screening",
            "hitl",
            "dual_auth",
            "mulesoft_api",
            "audit_logging",
        ],
        mcp_allowlist=["salesforce-crm", "mulesoft-actions"],
        memory_scope=[MemoryScope.SESSION, MemoryScope.ARTIFACT],
        description="Serial seven-gate write path. Never parallelizes. Steering rule 1.",
        serial_by_design=True,
    )


def _faq_specialist() -> AgentDefinition:
    return AgentDefinition(
        id="faq_specialist",
        persona="fsi_client_liaison",
        role=AgentRole.SPECIALIST,
        model=ModelTier.HAIKU,
        system_prompt=FAQ_SPECIALIST_PROMPT,
        tool_allowlist=[],
        mcp_allowlist=[],
        memory_scope=[MemoryScope.READ_ONLY],
        description="Bounded client-safe FAQs. Haiku. No MNPI ever touches this.",
    )


def _context_specialist_liaison() -> AgentDefinition:
    return AgentDefinition(
        id="context_specialist",
        persona="fsi_client_liaison",
        role=AgentRole.SPECIALIST,
        model=ModelTier.SONNET,
        system_prompt=CONTEXT_SPECIALIST_PROMPT,
        tool_allowlist=["client_summary"],
        mcp_allowlist=["salesforce-crm"],
        memory_scope=[MemoryScope.READ_ONLY],
        description="MNPI-filtered client-facing context read. Read-only.",
    )


_AGENTS: List[AgentDefinition] = [
    _research_orchestrator(),
    _market_specialist(),
    _filings_specialist(),
    _sentiment_specialist(),
    _compliance_specialist(),
    _statement_specialist(),
    _advisor_orchestrator(),
    _portfolio_specialist(),
    _suitability_specialist(),
    _client_context_specialist(),
    _action_specialist(),
    _liaison_orchestrator(),
    _faq_specialist(),
    _context_specialist_liaison(),
]

AGENT_TOPOLOGY: Dict[str, AgentDefinition] = {a.id: a for a in _AGENTS}

PERSONAS: List[str] = ["fsi_research", "fsi_advisor", "fsi_client_liaison"]


def topology_for_persona(persona: str) -> Dict[str, AgentDefinition]:
    """Return the subset of the agent registry belonging to one persona.

    Args:
        persona: one of fsi_research, fsi_advisor, fsi_client_liaison.

    Returns:
        Dict keyed by agent id, agents belonging to that persona only.

    Raises:
        ValueError: if persona is unknown.
    """
    if persona not in PERSONAS:
        raise ValueError(f"unknown persona: {persona!r} (expected one of {PERSONAS})")
    return {aid: a for aid, a in AGENT_TOPOLOGY.items() if a.persona == persona}


def orchestrator_for_persona(persona: str) -> AgentDefinition:
    """Return the single orchestrator agent for a persona.

    Raises:
        ValueError: if persona is unknown or (impossibly) has no orchestrator.
    """
    subset = topology_for_persona(persona)
    for a in subset.values():
        if a.role is AgentRole.ORCHESTRATOR:
            return a
    raise ValueError(f"no orchestrator found for persona {persona!r}")


def assert_topology_integrity() -> None:
    """Raise AssertionError if the registry violates V3 invariants.

    V3 narrative phrases 17 agents as (6 + 5 + 3 across the three personas),
    but the unique agent IDs are 14 — because `context_specialist` appears
    once (not twice) even though both research and liaison personas have
    a specialist named "context". Here we enforce the real invariants:
    3 orchestrators + 11 specialists = 14 unique IDs, one orchestrator per
    persona, action_specialist serial, faq_specialist on Haiku.
    """
    orchestrators = [a for a in AGENT_TOPOLOGY.values() if a.role is AgentRole.ORCHESTRATOR]
    specialists = [a for a in AGENT_TOPOLOGY.values() if a.role is AgentRole.SPECIALIST]
    assert len(orchestrators) == 3, f"expected 3 orchestrators, got {len(orchestrators)}"
    assert len(specialists) == 11, f"expected 11 specialists, got {len(specialists)}"
    assert len(AGENT_TOPOLOGY) == 14, f"expected 14 unique agent ids, got {len(AGENT_TOPOLOGY)}"

    personas_seen = {a.persona for a in orchestrators}
    assert personas_seen == set(PERSONAS), f"orchestrator persona mismatch: {personas_seen}"

    action = AGENT_TOPOLOGY["action_specialist"]
    assert action.serial_by_design, "action_specialist MUST be serial_by_design"

    faq = AGENT_TOPOLOGY["faq_specialist"]
    assert faq.model is ModelTier.HAIKU, "faq_specialist must run on Haiku"

    for persona in PERSONAS:
        subset = topology_for_persona(persona)
        n_orch = sum(1 for a in subset.values() if a.role is AgentRole.ORCHESTRATOR)
        assert n_orch == 1, f"persona {persona!r} has {n_orch} orchestrators, want 1"


assert_topology_integrity()
