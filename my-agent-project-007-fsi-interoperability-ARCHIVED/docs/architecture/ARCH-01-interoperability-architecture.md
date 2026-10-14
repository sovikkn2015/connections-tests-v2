# Project 007: FSI Intersystem Interoperability — A Modular Agent Architecture

> Date: April 12, 2026
> Status: Deep research + architecture design (pre-implementation)
> Problem: "We need research connected to client data connected to compliance connected to execution, accessible from wherever our people work" — across 5 radically different FSI enterprise archetypes
> Sources: 853-line enterprise archetype analysis (007-fsi-enterprise-archetypes-technology-analysis.md), OpenClaw/MyClaw ecosystem, FDC3/FINOS standards, MCP protocol, A2A protocol, FINRA 2026 Oversight Report, vendor documentation
> Predecessor: Project 006 (OpenClaw + Salesforce + AWS — single-archetype prototype)

---

## Why This Is Hard — And Why No One Has Solved It

Nobody has solved FSI intersystem interoperability for agentic AI because the problem has 5 dimensions that conflict with each other:

1. **Protocol diversity.** Tier 1 banks speak FIX + SWIFT + Kafka + proprietary binary. Tier 4 RIAs speak REST + SFTP + CSV. An agent platform must speak all of them — or abstract them away.

2. **Compliance regime diversity.** A Tier 1 bank has Chinese walls, MAR surveillance, CCAR stress testing, and 17a-4 WORM archiving. A Tier 4 RIA has fiduciary duty, Form ADV, and a compliance calendar. Same word ("compliance"), completely different systems, rules, and enforcement mechanisms.

3. **Data sensitivity asymmetry.** At a hedge fund, current holdings are the most sensitive data in the firm — leaking them enables front-running. At an RIA, holdings are routine portfolio data. The same data type has radically different sensitivity levels depending on the archetype.

4. **System landscape fragmentation.** The average wealth management firm juggles 20-35 separate technology platforms. A Tier 1 bank has hundreds of internal systems. There is no "standard FSI tech stack" — every firm is a unique snowflake of vendor choices, legacy systems, and proprietary builds.

5. **The "last mile" problem.** Even if you solve research, client data, and compliance — execution is different everywhere. A Tier 1 bank routes orders via FIX to their proprietary algo engine. A Tier 4 RIA clicks "rebalance" in Orion through the Schwab API. A hedge fund uses DMA through their prime broker. Same intent ("execute this trade"), completely different plumbing.

The reason previous attempts failed is that they tried to build a universal middleware layer (MuleSoft, Kafka, ESBs) that connects everything. That works for data plumbing but fails for agentic AI because an agent needs to understand context, enforce compliance rules, and make decisions — not just move data between systems.

---

## The 5 FSI Enterprise Archetypes

Full analysis in 007-fsi-enterprise-archetypes-technology-analysis.md. Summary:

| Archetype | Examples | CRM | Portfolio/OMS | Execution | Compliance | Primary Protocol |
|-----------|----------|-----|---------------|-----------|------------|-----------------|
| Tier 1: Investment Bank | Goldman, MS, JPM | SF FSC / Proprietary | Proprietary OMS/EMS | FIX + Algo engines | NICE Actimize, Behavox | FIX, SWIFT, Kafka |
| Tier 2: Asset Manager | Fidelity, T. Rowe, Wellington | SF FSC / Proprietary | Aladdin, Charles River | FIX to brokers | CRD compliance | FIX, REST, SFTP |
| Tier 3: Wealth Mgmt / BD | Merrill, UBS WM, Raymond James | SF FSC, Dynamics | Envestnet, Black Diamond | Custodian platforms | Smarsh, Global Relay | REST, SFTP |
| Tier 4: Independent RIA | Carson, Creative Planning | Wealthbox, Redtail, SF | Orion, Addepar | iRebal, tRx, custodian | RIA in a Box, SmartRIA | REST, OAuth, SFTP |
| Tier 5: Hedge Fund | Citadel, Two Sigma, Point72 | Backstop, SF | SS&C Eze, Enfusion | FIX + DMA via PB | ComplySci, ACA Group | FIX, Kafka, proprietary |

---

## The Insight: MCP as the Universal Adapter Layer

The Model Context Protocol (MCP) changes the equation. Instead of building point-to-point integrations between the agent and every FSI system, you build MCP servers that wrap each system. The agent speaks MCP. The MCP servers speak whatever protocol the underlying system requires.

This is the same pattern that made USB-C work for hardware. You don't redesign every device — you build an adapter.

```
BEFORE (point-to-point — N x M integrations):

  Agent ---- Bloomberg API
  Agent ---- Salesforce REST
  Agent ---- Aladdin SDK
  Agent ---- FIX Engine
  Agent ---- Schwab API
  Agent ---- NICE Actimize API
  ... (20-35 integrations per firm)

AFTER (MCP adapter layer — N+M integrations):

  Agent ---- MCP Protocol ---- MCP Server: Bloomberg
                           ---- MCP Server: Salesforce
                           ---- MCP Server: Aladdin
                           ---- MCP Server: FIX Bridge
                           ---- MCP Server: Schwab
                           ---- MCP Server: NICE Actimize
```

Each MCP server is a standalone, deployable unit that:
- Exposes tools via POST /tools/list (what can I do?)
- Accepts tool calls via POST /tools/call (do this thing)
- Handles authentication, rate limiting, and error handling for its specific system
- Can be developed, tested, and deployed independently

The agent does not know or care whether it is talking to Bloomberg or Alpha Vantage. It calls get_quote(symbol="NVDA") and the MCP server handles the rest.

### Why MCP and not A2A?

A2A (Agent-to-Agent protocol) is for agents talking to agents — discovery, capability negotiation, task delegation between autonomous systems. That is not what we need here. We need an agent talking to tools (systems that do one thing when asked). MCP is the right abstraction. A2A becomes relevant later if multiple enterprise agents need to collaborate across firm boundaries.

### Why not FDC3?

FDC3 (Financial Desktop Connectivity and Collaboration Consortium) solves desktop app interoperability — apps sharing context on a trader's screen. It is complementary, not competing. An MCP server could expose FDC3 intents as tools, bridging the desktop interop world with the agentic AI world. But FDC3 alone does not solve the agent orchestration problem.


---

## The Architecture: 5 Layers

```
+------------------------------------------------------------------------------+
|                                                                              |
|  LAYER 1: CHANNEL GATEWAY                                                    |
|  Where users interact. OpenClaw Gateway handles 12+ channels.                |
|  Enterprise adds their own: Bloomberg IB chat, Symphony, Teams.              |
|                                                                              |
|  [Slack] [Teams] [WhatsApp] [Telegram] [Discord] [Web] [Custom Portal]      |
|                              |                                               |
|                     OpenClaw Multi-Channel Router                             |
|                              |                                               |
+------------------------------+-----------------------------------------------+
|                              |                                               |
|  LAYER 2: AGENT ORCHESTRATION CORE                                           |
|  The brain. OpenClaw on Bedrock AgentCore.                                   |
|  This layer is ARCHETYPE-AGNOSTIC.                                           |
|                                                                              |
|  [Intent Router] [Pipeline Engine] [Memory] [LLM Router] [Observability]    |
|                              |                                               |
|                    MCP Protocol (tools/list + tools/call)                     |
|                              |                                               |
+------------------------------+-----------------------------------------------+
|                              |                                               |
|  LAYER 3: COMPLIANCE & DATA SENSITIVITY ENGINE                               |
|  Sits BETWEEN the agent and the MCP servers.                                 |
|  Every tool call passes through here. Archetype-aware.                       |
|                                                                              |
|  [Archetype Profile] [MNPI Filter] [Compliance Rules] [Data Isolation]      |
|  [Audit Logger] -- all loaded from enterprise-config.yaml                    |
|                              |                                               |
|                    MCP Protocol (filtered, audited)                           |
|                              |                                               |
+------------------------------+-----------------------------------------------+
|                                                                              |
|  LAYER 4: MCP SERVER ECOSYSTEM (the adapter layer)                           |
|  Each MCP server wraps one external system.                                  |
|  Enterprise picks which servers to deploy.                                   |
|                                                                              |
|  RESEARCH:    [Bloomberg] [FactSet] [SEC EDGAR] [Morningstar] [Refinitiv]   |
|  CLIENT DATA: [SF FSC] [Wealthbox] [Redtail] [Backstop] [Aladdin] [Orion]  |
|  COMPLIANCE:  [NICE Actimize] [Smarsh] [RIA in a Box] [ComplySci]           |
|  EXECUTION:   [FIX Bridge] [Custodian APIs] [MuleSoft] [Rebalancing]        |
|  AGGREGATION: [Plaid] [MX] [Yodlee] [Custodian SFTP]                        |
|                                                                              |
+------------------------------------------------------------------------------+
|                                                                              |
|  LAYER 5: ENTERPRISE CONFIGURATION                                           |
|  One YAML file per enterprise. Declares everything.                          |
|                                                                              |
+------------------------------------------------------------------------------+
```

---

## Layer 3 Deep Dive: The Compliance & Data Sensitivity Engine

This is the layer that makes the architecture enterprise-grade. Without it, you have a chatbot that can call APIs. With it, you have a system a compliance officer would sign off on.

### Archetype-Specific MNPI Policies

The same tool call behaves differently depending on the archetype:

```
get_client_holdings(client_id="C-12345")

TIER 1 (Investment Bank):
  - CHECK: Same side of Chinese wall?
  - FILTER: Strip ALL position sizes, dollar amounts, cost basis
  - RETURN: Ticker list only
  - LOG: To NICE Actimize surveillance

TIER 2 (Asset Manager):
  - CHECK: Authorized for this portfolio/mandate?
  - FILTER: Strip cost basis, keep quantities
  - RETURN: Holdings with quantities, no cost basis
  - LOG: To compliance system + Langfuse

TIER 3 (Wealth Management / BD):
  - CHECK: Client's assigned advisor?
  - FILTER: Strip SSN, account numbers
  - RETURN: Full holdings (retail, not MNPI-sensitive)
  - LOG: To Smarsh + Salesforce audit

TIER 4 (Independent RIA):
  - CHECK: Client's advisor? (advisor-level isolation)
  - FILTER: Strip PII (SSN, DOB)
  - RETURN: Full holdings (retail, fiduciary context)
  - LOG: To CRM audit trail

TIER 5 (Hedge Fund):
  - CHECK: Authorized for this fund/pod?
  - FILTER: Strip ALL -- aggregate exposure only
  - RETURN: Sector exposure percentages only
  - LOG: To ComplySci + internal compliance
```

### Runtime Flow

Every MCP tool call passes through the compliance engine:

1. DATA ISOLATION CHECK -- Is this user authorized for this data?
2. MNPI FILTER (pre-call) -- Which fields need stripping?
3. COMPLIANCE RULES CHECK -- Any blocking rules triggered?
4. TOOL CALL EXECUTION -- Forward filtered call to MCP server
5. MNPI FILTER (post-call) -- Strip sensitive fields from response
6. AUDIT LOG -- Log everything immutably
7. RETURN filtered, audited data to agent

---

## The Universal Pipeline: Research -> Client -> Compliance -> Execution

Across all 5 archetypes, the agent follows a 4-stage pipeline. The specific systems change, but the pattern is universal:

STAGE 1: RESEARCH (Read-Only)
- Agent ingests and synthesizes from research sources
- T1: Bloomberg, Refinitiv. T2: FactSet, MSCI. T3/T4: Morningstar, planning tools. T5: Alt data, proprietary
- Action: SUMMARIZE, ANALYZE -- never RECOMMEND yet

STAGE 2: CLIENT CONTEXT (Read-Only, Access-Controlled)
- Agent retrieves client/portfolio context to personalize
- T1: Institutional mandates. T2: Portfolio holdings. T3/T4: Household, goals, risk profile. T5: Fund holdings, LP data
- Action: RETRIEVE, CONTEXTUALIZE -- enforce data isolation

STAGE 3: COMPLIANCE GATE (Mandatory, Blocking)
- Agent validates against compliance rules before any suggestion
- T1: Chinese walls, restricted list. T2: Pre-trade compliance. T3: Reg BI. T4: Fiduciary. T5: Position limits, leverage
- Action: VALIDATE, DOCUMENT, BLOCK if non-compliant

STAGE 4: EXECUTION (Write, Human-Approved)
- Agent facilitates execution -- NEVER autonomous for trades
- T1: FIX order for approval. T2: OMS submission. T3: Custodian platform. T4: Rebalancing queue. T5: OMS via FIX/DMA
- Action: PREPARE, PRESENT, WAIT FOR HUMAN APPROVAL

---

## OpenClaw / MyClaw Integration

The architecture leverages OpenClaw's native skill system. Each MCP server category maps to an OpenClaw skill. Skills read from enterprise-config.yaml to determine which MCP servers to call. The skill is the same across all archetypes -- the config determines the behavior.

MyClaw (managed hosting) could offer these as a pre-configured "FSI Agent Pack." ClawHub (skill marketplace) could host individual MCP server adapters as community skills.

---

## What Makes This Different

| Previous Approach | Why It Failed | 007 Approach |
|-------------------|---------------|--------------|
| MuleSoft / ESB | Moves data, cannot reason about it | Compliance engine reasons about data per-archetype |
| Bloomberg Terminal | Walled garden, no CRM/compliance integration | MCP wraps Bloomberg as one source among many |
| Salesforce Agentforce | 5 channels, no FIX, no portfolio mgmt, vendor lock-in | OpenClaw 12+ channels, MCP universal integration |
| Custom point-to-point | Not reusable, expensive per firm | MCP servers reusable, configure per enterprise |
| FDC3 / OpenFin | Desktop interop only, no agent orchestration | Complementary -- MCP can expose FDC3 intents |
| Plaid / MX | Read-only aggregation | One MCP server in the ecosystem, not the whole solution |

---

## Implementation Roadmap

| Phase | Focus | Timeline | What Gets Built |
|-------|-------|----------|-----------------|
| 1 | Generalize 006 | 4-6 weeks | Config engine, compliance engine, adapter pattern, enterprise YAML |
| 2 | Tier 3/4 connectors | 6-8 weeks | Orion, Schwab, Fidelity, Wealthbox, eMoney, Smarsh, Plaid |
| 3 | Tier 2 connectors | 6-8 weeks | Bloomberg, FactSet, FIX Bridge, Charles River |
| 4 | Tier 5 connectors | 4-6 weeks | SS&C Eze, Backstop, ComplySci, Prime Broker APIs |
| 5 | Tier 1 connectors | 8-12 weeks | NICE Actimize, SWIFT/ISO 20022, Chinese wall enforcement |

Start with Tier 3/4 (largest market, clearest use cases, simplest integration). Prove it works. Expand.

---

## Relationship to Project 006

006 is the proof-of-concept. 007 is the platform.

006 validated: OpenClaw as runtime, MCP as adapter pattern, pipeline orchestration, Salesforce as CRM, Bedrock as LLM, compliance screening, audit logging.

007 adds: archetype awareness (5 tiers), system agnosticism (MCP adapters), compliance configurability (YAML rules engine), enterprise deployability (config file), extensibility (new MCP server = new system, zero agent changes).

---

## The Honest Assessment

The MCP adapter pattern is proven. The compliance engine is the novel contribution -- nobody has built a per-archetype, per-field, per-role data sensitivity engine for agentic AI in FSI.

Hard parts remaining:
1. Vendor API access (Bloomberg, Aladdin, custodians require partnerships/licenses)
2. Compliance engine depth (real CCO acceptance)
3. Testing across 5 archetypes with real data
4. FIX protocol bridge (complex, stateful, latency-sensitive)
5. Regulatory acceptance (FINRA has not blessed any specific agentic AI architecture)

Realistic timeline: Tier 3/4 production-ready in 6-9 months. All 5 tiers in 18-24 months. Tier 1 alone could take 12 months.

The architecture is the right foundation. The question is execution.
