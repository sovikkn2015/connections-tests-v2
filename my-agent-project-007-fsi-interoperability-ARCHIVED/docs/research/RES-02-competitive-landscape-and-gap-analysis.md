# Project 007: Competitive Landscape & Gap Analysis

> Date: April 12, 2026
> Question: Is there any system in the world like this?
> Answer: No. Pieces exist. The full thing does not.

---

## The Short Answer

No system in the world does what 007 proposes — an agentic AI platform with a compliance proxy layer that works across all 5 FSI enterprise archetypes. But pieces of it exist. Here is what is out there and what each one is missing.

---

## What Exists Today

### BlackRock Aladdin — The Closest Analog

Aladdin is the closest thing to a "platform that connects everything" in FSI. It manages $21.6 trillion across 200+ institutions with ~4,000 engineers maintaining ~100 front-end applications. It covers portfolio management, risk analytics, trading, compliance, and operations in one system.

What Aladdin has:
- Research + portfolio + risk + compliance + execution in one platform
- Pre-trade compliance engine
- Real-time risk analytics
- Multi-asset trading (equities, fixed income, derivatives)
- 35 years of development

What Aladdin is missing:
- Only works within the Aladdin ecosystem (walled garden)
- Does not connect to Orion, Wealthbox, eMoney, or Tier 3/4 systems
- Does not have an AI agent that talks to you on WhatsApp or Slack
- Does not work for Tier 3/4 wealth management at all
- Not agentic — it is a platform humans operate, not an agent that reasons and acts
- Costs millions per year, only serves institutional clients
- Proprietary, not open-source or MCP-based

### Envestnet — The Wealth Management Operating System

Envestnet serves $6.5 trillion in assets across 110,000+ advisors. They announced a $1 billion R&D investment over 5 years and are building a conversational AI interface with persona-aware navigation and built-in compliance features.

What Envestnet has:
- Portfolio management + rebalancing + reporting + billing in one platform
- Tamarac CRM integration
- Model marketplace (third-party model portfolios)
- Data aggregation (Yodlee)
- New conversational AI interface (2026)

What Envestnet is missing:
- Only covers Tier 3/4 (wealth management + RIA)
- Does not touch Tier 1 banks, Tier 2 asset managers, or Tier 5 hedge funds
- Does not have a compliance proxy that adapts per archetype
- Proprietary platform, not an open MCP-based ecosystem
- No FIX protocol, no Bloomberg integration, no hedge fund support
- Conversational AI is platform-specific, not cross-system

### Salesforce Agentforce — The CRM-Native Agent

Agentforce is Salesforce's agentic AI platform with Einstein Trust Layer providing compliance guardrails, Atlas Reasoning Engine for orchestration, and native CRM data access.

What Agentforce has:
- Deep CRM integration (native SOQL, Data Cloud, Platform Events)
- Einstein Trust Layer (PII masking, toxicity, audit trail)
- Permission model (sharing rules, FLS, permission sets)
- Apex-enforced compliance

What Agentforce is missing:
- Only ~5 channels (Web Chat, Slack, Messaging, Voice, API)
- Cannot speak FIX protocol
- Does not integrate with Orion, Envestnet, Aladdin, Bloomberg natively
- Locked to the Salesforce ecosystem (vendor lock-in)
- No structured research pipeline (23-stage)
- No financial modeling (DCF, Monte Carlo)
- No cross-archetype compliance profiles

### AlphaSense / Brightwave / Hebbia — Research Intelligence

AlphaSense ($4B+ valuation), Hebbia ($700M), Brightwave ($21M raised) are production-grade AI research platforms used by institutional investors today.

What they have:
- SEC filing analysis, earnings transcript NLP
- AI-powered search across 500M+ premium documents (AlphaSense)
- Knowledge graphs with source tracing (Brightwave)
- Deep research across offline data (Hebbia)

What they are missing:
- No CRM connection (do not know your clients)
- No compliance awareness (do not check restricted lists)
- No execution capability (cannot submit trades)
- No multi-channel access (no WhatsApp, no Slack agent)
- Standalone tools, not integrated agent platforms

### MuleSoft / Kafka / ESBs — Data Plumbing

MuleSoft (Salesforce-owned), Apache Kafka, and traditional ESBs connect enterprise systems and move data between them.

What they have:
- API-led connectivity across hundreds of systems
- Event streaming (Kafka) for real-time data flow
- Pre-built connectors for many FSI systems
- Enterprise-grade reliability and scale

What they are missing:
- Move data but cannot reason about it
- No MNPI awareness or compliance enforcement
- Not agentic — no LLM, no reasoning, no decision-making
- No user-facing channels (no chat, no WhatsApp)
- Plumbing, not intelligence

### FDC3 / OpenFin — Desktop Interoperability

FDC3 (Financial Desktop Connectivity and Collaboration Consortium) is a FINOS open standard for desktop app interoperability. OpenFin is the leading implementation.

What they have:
- Standardized intents for financial desktop apps
- Context sharing between apps on a trader's screen
- Cross-application workflows
- Adopted by Bloomberg, Refinitiv, Fidessa, and others

What they are missing:
- Desktop-only (no mobile, no messaging channels)
- No agent orchestration or LLM reasoning
- No compliance engine
- No execution capability beyond desktop context sharing
- Solves screen-level interop, not system-level interop

### NICE Actimize / Behavox — Compliance Surveillance

NICE Actimize SURVEIL-X is the market leader in trade and communications surveillance. Behavox uses AI/NLP to detect misconduct patterns across voice, email, and chat.

What they have:
- Trade surveillance (insider trading, market manipulation detection)
- Communications monitoring (email, chat, voice)
- Behavioral analytics (Behavox NLP)
- Regulatory reporting

What they are missing:
- Monitoring tools, not agent infrastructure
- Cannot orchestrate research, CRM access, or execution
- No user-facing agent interface
- Reactive (detect after the fact), not proactive (prevent before action)
- Single-purpose compliance, not multi-system integration

---

## The Gap Map

```
                    Research  CRM    Compliance  Execution  Multi-    Agentic  Cross-
                    Intel     Data   Aware       Connected  Channel   AI       Archetype
                    -------   ----   ----------  ---------  -------   ------   ---------
Aladdin              **       ***    ***         ***        -         -        T2/T5 only
Envestnet            **       ***    **          ***        *         * (new)  T3/T4 only
Agentforce           *        ***    ***         -          *         **       SF only
AlphaSense           ***      -      -           -          -         *        -
MuleSoft             -        **     -           ***        -         -        **
FDC3/OpenFin         -        -      -           -          -         -        T1 desktop
NICE Actimize        -        -      ***         -          -         -        T1/T3
007 (proposed)       ***      ***    ***         ***        ***       ***      ALL 5
```

*** = strong   ** = partial   * = basic   - = absent

---

## What 007 Proposes That Nobody Has

### 1. The Compliance Proxy Layer (Layer 3)

A middleware that sits between an AI agent and enterprise systems, enforcing per-archetype MNPI rules, data isolation, and audit requirements — configurable via YAML, not hardcoded.

The same tool call — get_client_holdings() — returns different data depending on the archetype:
- Tier 1 bank: Ticker list only (no quantities, no values) — Chinese wall enforced
- Tier 2 asset manager: Holdings with quantities (no cost basis) — restricted list checked
- Tier 3 wealth management: Full holdings (retail, not MNPI-sensitive) — Reg BI documented
- Tier 4 RIA: Full holdings (fiduciary context) — advisor-level isolation
- Tier 5 hedge fund: Sector exposure percentages only (no positions) — pod isolation

All from the SAME agent code. The compliance proxy handles the difference.

Nobody has built this.

### 2. An FSI-Specific MCP Adapter Ecosystem

Individual MCP servers exist (2,300+ in public directories as of April 2026). But nobody has built an FSI-specific ecosystem where each adapter is compliance-aware and the agent can swap Bloomberg for Alpha Vantage, Aladdin for Orion, or FIX for custodian REST APIs — all via config change, zero code change.

### 3. Cross-Archetype Agent Platform

Aladdin works for Tier 2/5. Envestnet works for Tier 3/4. Agentforce works for Salesforce shops. Nobody works across all 5 archetypes with the same orchestration core but different compliance profiles.

---

## The Key Insight: 007 Does Not Compete — It Connects

007 does not compete with Aladdin, Envestnet, or Salesforce. It connects them.

```
  TODAY: Each platform is an island

  [Aladdin]     [Envestnet]     [Salesforce]     [Bloomberg]
      |              |               |                |
      |              |               |                |
  (T2/T5 only)  (T3/T4 only)   (CRM only)      (data only)

  No bridge between them. No agent that spans all of them.
  No compliance layer that adapts to the archetype.


  007: The connecting layer

  [Aladdin]     [Envestnet]     [Salesforce]     [Bloomberg]
      |              |               |                |
      +--------------+---------------+----------------+
                     |
              MCP Adapter Layer
                     |
              Compliance Proxy (archetype-aware)
                     |
              Agent Orchestration (OpenClaw)
                     |
              Channel Gateway
                     |
      +--------------+---------------+----------------+
      |              |               |                |
  [Slack]      [WhatsApp]      [Teams]          [Web Chat]
```

An enterprise that uses Aladdin + Salesforce + Bloomberg gets an agent that connects all three, with compliance rules appropriate for their archetype. An enterprise that uses Orion + Wealthbox + eMoney gets the same agent with different adapters and different compliance rules.

Same platform. Different connectors. Different compliance. One agent.

---

## The Honest Comparison to Aladdin

Aladdin is the closest analog — it is a platform that connects research, portfolio, risk, compliance, and execution. But Aladdin took 35 years and 4,000 engineers to build. It is proprietary, costs millions per year, and only serves institutional asset managers and hedge funds.

007 proposes to do something similar but with a fundamentally different architecture:
- Open-source agent runtime (OpenClaw) instead of proprietary platform
- Open protocol adapters (MCP) instead of walled garden integrations
- Configurable compliance (YAML) instead of hardcoded rules
- Coverage across all 5 tiers instead of just institutional
- Agentic AI (reasons and acts) instead of platform humans operate

Can a small team build something that competes with what BlackRock built with 4,000 engineers? Not at Aladdin's depth. But at a useful depth for the specific problem of "research connected to client data connected to compliance connected to execution" — yes. Because 007 is not trying to replace Aladdin. It is trying to be the agent layer that sits on top of whatever systems the enterprise already has — including Aladdin.

Aladdin is the operating system. 007 is the AI assistant that works across operating systems.

---

## Summary

| Question | Answer |
|----------|--------|
| Does a full cross-archetype agentic FSI platform exist? | No |
| Does a compliance proxy for agentic AI exist? | No |
| Does an FSI-specific MCP adapter ecosystem exist? | No |
| Do individual pieces exist? | Yes — Aladdin (T2/5), Envestnet (T3/4), Agentforce (CRM), AlphaSense (research), MuleSoft (plumbing) |
| What is the novel contribution of 007? | Layer 3 — the compliance proxy that makes the same agent work across all 5 archetypes |
| Is it buildable? | Yes, starting with Tier 3/4 (4 months), full platform in ~11 months |
| What is the biggest risk? | Not code — vendor API access, compliance depth, regulatory acceptance |
| What is the relationship to existing platforms? | 007 connects them, does not compete with them |
