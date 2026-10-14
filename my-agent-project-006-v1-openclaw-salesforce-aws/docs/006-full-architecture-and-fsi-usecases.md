# Project 006: The Full Story

## OpenClaw + Salesforce + AWS + AutoResearchClaw — Architecture & FSI Use Cases

> Research date: April 6, 2026
> Sources: [OpenClaw GitHub](https://github.com/openclaw/openclaw), [AutoResearchClaw](https://github.com/aiming-lab/AutoResearchClaw), [AWS Lightsail OpenClaw](https://aws.amazon.com/blogs/aws/introducing-openclaw-on-amazon-lightsail-to-run-your-autonomous-private-ai-agents/), [FINRA 2026 Oversight Report](https://www.jdsupra.com/legalnews/finra-s-2026-oversight-report-signals-a-4923301/), [Agentforce for FSI](https://vantagepoint.io/blog/sf/agentforce-for-financial-services-2026-guide), [FinRobot](https://arxiv.org/html/2411.08804v1), [CFA Agentic AI](https://rpc.cfainstitute.org/research/the-automation-ahead-content-series/agentic-ai-for-finance)
> Content was rephrased for compliance with licensing restrictions.

---

## The Story

Financial services firms are spending over $35 billion on AI in 2026. FINRA's 2026 Oversight Report now dedicates an entire section to agentic AI, demanding the same compliance rigor as any supervised technology. The industry needs agents that can reason, act, and be audited — across CRM, market data, regulatory filings, and client communications.

Three platforms have converged to make this possible:

- **Salesforce** owns the client relationship — CRM data, compliance records, advisor workflows, Data Cloud for unified profiles, and Agentforce for CRM-native agents with Einstein Trust Layer.
- **AWS** owns the compute and data infrastructure — Bedrock for LLMs, Lambda for serverless tools, Redshift for historical data, Transcribe/Textract/Comprehend for multimodal AI, and AgentCore for agent deployment.
- **OpenClaw** owns the user interface and orchestration — 12+ messaging channels, persistent memory, MCP-native tool integration, a skill marketplace with thousands of pre-built capabilities, and the ability to run complex multi-stage pipelines like AutoResearchClaw.

No single platform does everything. Together, they cover the full stack.

And then there's **AutoResearchClaw** — a 23-stage autonomous research pipeline built on OpenClaw that turns a topic into a verified, structured research output. Originally designed for academic papers, its architecture (staged pipeline, gate stages, HITL co-pilot, self-healing, multi-agent debate, citation verification, cross-run learning) is exactly what FSI needs for rigorous, auditable, analyst-grade research automation.

---

## The Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                                                                                  │
│  FSI USERS                                                                       │
│                                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │ Equity   │ │ Wealth   │ │ Compli-  │ │ Risk     │ │ Client   │              │
│  │ Research │ │ Advisor  │ │ ance     │ │ Manager  │ │ Service  │              │
│  │ Analyst  │ │          │ │ Officer  │ │          │ │ Rep      │              │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘              │
│       └─────────────┴────────────┴─────────────┴────────────┘                    │
│                                   │                                              │
│                                   ▼                                              │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │  CHANNEL LAYER (OpenClaw Gateway)                                          │  │
│  │                                                                            │  │
│  │  ┌──────┐┌──────┐┌────────┐┌────────┐┌───────┐┌──────┐┌───────────────┐  │  │
│  │  │Slack ││ Web  ││WhatsApp││Telegram││Discord││Mobile││ Agent API     │  │  │
│  │  │      ││ Chat ││        ││        ││       ││      ││ (REST)        │  │  │
│  │  └──┬───┘└──┬───┘└───┬────┘└───┬────┘└──┬────┘└──┬───┘└──────┬───────┘  │  │
│  │     └───────┴────────┴─────────┴────────┴────────┴───────────┘           │  │
│  │                              │                                            │  │
│  │                     OpenClaw Multi-Channel Router                          │  │
│  └──────────────────────────────┬─────────────────────────────────────────────┘  │
│                                 │                                                │
└─────────────────────────────────┼────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                     │
│  AWS — OPENCLAW ON BEDROCK AGENTCORE                                                │
│                                                                                     │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │  OPENCLAW AGENT (Orchestrator)                                                │  │
│  │  LLM: Claude Sonnet 4 (Bedrock)  │  Memory: persistent per-user              │  │
│  │                                                                               │  │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │  INTENT ROUTER                                                          │  │  │
│  │  │  Classifies request → routes to skill / pipeline / backend              │  │  │
│  │  └───┬────────┬────────┬────────┬────────┬────────┬────────┬───────────┘  │  │
│  │      │        │        │        │        │        │        │               │  │
│  │      ▼        ▼        ▼        ▼        ▼        ▼        ▼               │  │
│  │  ┌────────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────────────────┐  │  │
│  │  │SF CRM  ││Fin.  ││Market││Compli││Doc   ││News  ││AutoResearchClaw  │  │  │
│  │  │Skill   ││Analy-││Data  ││ance  ││Proc. ││Search││Pipeline          │  │  │
│  │  │        ││sis   ││(MCP) ││Check ││(AWS  ││(MCP) ││                  │  │  │
│  │  │SOQL    ││      ││      ││      ││AI)   ││      ││23-stage research │  │  │
│  │  │CRUD    ││DCF   ││Quote ││MNPI  ││      ││      ││with HITL co-pilot│  │  │
│  │  │Apex    ││Comps ││Hist. ││Restr.││Transc││Headln││self-healing      │  │  │
│  │  │Events  ││Monte ││Cons. ││Trade ││Textr.││Sentmt││citation verify   │  │  │
│  │  │        ││Carlo ││Opts. ││Wndws ││Compr.││      ││cross-run learn   │  │  │
│  │  └───┬────┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└────────┬─────────┘  │  │
│  │      │        │       │       │       │       │             │              │  │
│  └──────┼────────┼───────┼───────┼───────┼───────┼─────────────┼──────────────┘  │
│         │        │       │       │       │       │             │                  │
│  ┌──────┼────────┼───────┼───────┼───────┼───────┼─────────────┼──────────────┐  │
│  │      ▼        ▼       ▼       ▼       ▼       ▼             ▼              │  │
│  │  AWS SERVICES                                                              │  │
│  │                                                                            │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌─────────────┐  │  │
│  │  │Bedrock │ │Lambda  │ │Redshift│ │S3      │ │Kinesis │ │EventBridge  │  │  │
│  │  │(LLM)   │ │(MCP    │ │(10yr   │ │(filings│ │(real-  │ │(scheduled   │  │  │
│  │  │        │ │servers)│ │hist.)  │ │reports)│ │time)   │ │triggers)    │  │  │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └─────────────┘  │  │
│  │                                                                            │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐ ┌────────────────────┐  │  │
│  │  │Transcr.│ │Textract│ │Compreh.│ │Secrets Mgr │ │CloudWatch / Logs   │  │  │
│  │  │(audio) │ │(PDF)   │ │(NLP)   │ │(creds)     │ │(monitoring)        │  │  │
│  │  └────────┘ └────────┘ └────────┘ └────────────┘ └────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│         │  Salesforce REST API (OAuth 2.0)                                       │
│         ▼                                                                        │
│  ┌───────────────────────────────────────────────────────────────────────────┐   │
│  │  SALESFORCE ORG                                                           │   │
│  │                                                                           │   │
│  │  ┌─────────────────────────────────────────────────────────────────────┐  │   │
│  │  │  CRM DATA                                                           │  │   │
│  │  │  Accounts │ Contacts │ Opportunities │ Financial Accounts           │  │   │
│  │  │  Holdings │ Goals │ Meetings │ Transactions │ Compliance Records    │  │   │
│  │  │  Research Notes │ Coverage │ Watchlists │ Audit Logs                │  │   │
│  │  └─────────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                           │   │
│  │  ┌─────────────────────────────────────────────────────────────────────┐  │   │
│  │  │  DATA CLOUD                                                         │  │   │
│  │  │  Unified Client Profiles │ Zero-Copy Redshift │ Vector Search/RAG   │  │   │
│  │  │  Identity Resolution │ Calculated Insights │ Segments               │  │   │
│  │  └─────────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                           │   │
│  │  ┌─────────────────────────┐  ┌────────────────────────────────────────┐  │   │
│  │  │  AGENTFORCE (optional)  │  │  PLATFORM SERVICES                     │  │   │
│  │  │  Coexists with OpenClaw │  │  Platform Events │ Flows │ Apex        │  │   │
│  │  │  for SF-native use cases│  │  Permission Sets │ Sharing Rules       │  │   │
│  │  │                         │  │  Einstein Trust Layer │ Shield          │  │   │
│  │  └─────────────────────────┘  └────────────────────────────────────────┘  │   │
│  └───────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```


---

## AutoResearchClaw Pipeline — Adapted for FSI

The 23-stage pipeline, re-mapped from academic research to financial services:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│  AutoResearchClaw Pipeline — FSI Adaptation                                     │
│                                                                                 │
│  TRIGGER: Analyst says "Research NVIDIA ahead of earnings" (any channel)        │
│                                                                                 │
│  ┌─── Phase A: Research Scoping ──────────────────────────────────────────────┐ │
│  │  1. TOPIC_INIT         → Parse ticker, timeframe, context from CRM        │ │
│  │  2. PROBLEM_DECOMPOSE  → Break into: fundamentals, sentiment, technicals, │ │
│  │                          catalysts, risks, compliance check               │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                        │                                        │
│                                        ▼                                        │
│  ┌─── Phase B: Data Collection ───────────────────────────────────────────────┐ │
│  │  3. SEARCH_STRATEGY    → Query plan: SEC EDGAR + market data + news +     │ │
│  │                          CRM coverage + Redshift historical               │ │
│  │  4. DATA_COLLECT       → MCP servers: 10-K/10-Q, price history,           │ │
│  │                          consensus, news, earnings transcripts            │ │
│  │                          SF skill: coverage, holdings, meetings            │ │
│  │  5. DATA_SCREEN [GATE] → Relevance scoring, dedup, completeness check    │ │
│  │                          ★ Analyst can review/approve data set            │ │
│  │  6. KNOWLEDGE_EXTRACT  → Structured extraction: key metrics, guidance,    │ │
│  │                          risk factors, competitive position               │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                        │                                        │
│                                        ▼                                        │
│  ┌─── Phase C: Synthesis ─────────────────────────────────────────────────────┐ │
│  │  7. SYNTHESIS          → Cross-source: financials + sentiment + macro +   │ │
│  │                          competitive landscape                            │ │
│  │  8. THESIS_GEN         → Multi-agent debate: bull case, bear case, base   │ │
│  │     (multi-agent)        case with catalysts                              │ │
│  │                          ★ Co-Pilot: Idea Workshop — analyst refines      │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                        │                                        │
│                                        ▼                                        │
│  ┌─── Phase D: Analysis Design ───────────────────────────────────────────────┐ │
│  │  9. ANALYSIS_DESIGN [GATE] → DCF params, comp set, Monte Carlo ranges    │ │
│  │                          ★ Analyst reviews model assumptions              │ │
│  │ 10. CODE_GENERATION    → Python: DCF, comps, Monte Carlo, backtesting    │ │
│  │ 11. RESOURCE_PLANNING  → Compute estimate for model execution             │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                        │                                        │
│                                        ▼                                        │
│  ┌─── Phase E: Execution ─────────────────────────────────────────────────────┐ │
│  │ 12. MODEL_RUN          → Execute: DCF → fair value, comps → relative      │ │
│  │                          value, Monte Carlo → probability distribution    │ │
│  │ 13. ITERATIVE_REFINE   → Self-healing: diagnose failures, adjust params   │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                        │                                        │
│                                        ▼                                        │
│  ┌─── Phase F: Analysis & Decision ───────────────────────────────────────────┐ │
│  │ 14. RESULT_ANALYSIS    → Multi-agent: valuation range, upside/downside    │ │
│  │ 15. RESEARCH_DECISION  → PROCEED / REFINE / PIVOT                         │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                        │                                        │
│                                        ▼                                        │
│  ┌─── Phase G: Brief Writing ─────────────────────────────────────────────────┐ │
│  │ 16. BRIEF_OUTLINE      → Rating, Target Price, Thesis, Catalysts, Risks   │ │
│  │ 17. BRIEF_DRAFT        → Section-by-section, anti-fabrication guard       │ │
│  │                          ★ Co-Pilot: analyst edits key sections            │ │
│  │ 18. PEER_REVIEW        → Methodology-evidence consistency check           │ │
│  │ 19. BRIEF_REVISION     → Incorporate feedback                             │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                        │                                        │
│                                        ▼                                        │
│  ┌─── Phase H: Finalization ──────────────────────────────────────────────────┐ │
│  │ 20. QUALITY_GATE [GATE]→ All claims verified, compliance passed           │ │
│  │                          ★ Analyst final approval                         │ │
│  │ 21. KNOWLEDGE_ARCHIVE  → MetaClaw cross-run learning                      │ │
│  │ 22. PUBLISH            → Write IR_Research_Note__c to Salesforce CRM      │ │
│  │ 23. AUDIT_VERIFY       → Log everything to IR_Audit_Log__c (FINRA)        │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  CROSS-CUTTING:                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────────┐ │
│  │ HITL     │ │ Anti-    │ │ MetaClaw │ │ Cost     │ │ Compliance           │ │
│  │ Co-Pilot │ │ Fabrica- │ │ Learning │ │ Guard-   │ │ Screening            │ │
│  │ (6 modes)│ │ tion     │ │ (cross-  │ │ rails    │ │ (MNPI, restricted    │ │
│  │          │ │ Sentinel │ │  run)    │ │ (budget) │ │  list, trade windows)│ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## FSI Use Cases — Practical Applications

### Use Case 1: Autonomous Equity Research Brief Generation

**Who:** Equity research analysts (sell-side or buy-side)
**Trigger:** "Deep dive on NVIDIA ahead of earnings next week"

```
Analyst (Slack) → OpenClaw → AutoResearchClaw pipeline:
  → SEC EDGAR MCP: latest 10-Q, 8-K, insider transactions
  → Market Data MCP: price, 52-week range, analyst consensus
  → News MCP: headlines, sentiment scoring
  → Salesforce skill: coverage history, client holdings exposure
  → Financial Analysis skill: DCF, comps, Monte Carlo
  → Sentiment skill: earnings transcript NLP, management tone
  → Compliance skill: restricted list, MNPI screening
  → Assembles structured research brief
  → Writes IR_Research_Note__c to Salesforce
  → Notifies analyst in Slack with summary
```

**Value:** Analysts spend 70% of time on data gathering and formatting. This reclaims that time for judgment and client interaction. Anti-fabrication ensures all numbers come from real models. HITL co-pilot lets the analyst steer thesis direction.

---

### Use Case 2: Proactive Earnings Season Monitoring

**Who:** Portfolio managers, research analysts
**Trigger:** EventBridge scheduled rule — 5 days before each earnings date

```
EventBridge (AWS) → Platform Event (SF) → OpenClaw:
  → For each stock on IR_Watchlist__c approaching earnings:
    → Abbreviated pipeline (Phases A-C only)
    → Pull latest data, synthesize key themes
    → Write pre-earnings alert to Salesforce
    → Push to analyst via Slack/WhatsApp/Telegram
    → Include: consensus, key metrics to watch,
      historical reaction, client exposure
```

**Value:** No analyst manually tracks 40+ earnings dates. MetaClaw learning means the system gets better at predicting which metrics matter for each stock over time.

---

### Use Case 3: Client Meeting Preparation

**Who:** Wealth advisors, relationship managers
**Trigger:** "Prep me for my meeting with [client] tomorrow"

```
Advisor (WhatsApp) → OpenClaw:
  → SF skill: client profile, holdings, goals, transactions, meetings, cases
  → Market Data MCP: performance of client's top holdings since last meeting
  → News MCP: relevant news for client's sector exposure
  → Financial Analysis skill: portfolio drift, rebalancing needs
  → Generate meeting prep brief:
    - Client summary (AUM, risk profile, goals)
    - Portfolio performance since last meeting
    - Holdings requiring discussion
    - Recommended talking points
    - Compliance notes (suitability, KYC refresh?)
  → Write to Salesforce, send to advisor via WhatsApp
```

**Value:** 45-minute prep → zero. The brief is waiting when the advisor wakes up. WhatsApp means advisors in the field don't need Salesforce open.

---

### Use Case 4: Regulatory Compliance Monitoring

**Who:** Compliance officers, risk managers
**Trigger:** Continuous + scheduled

```
OpenClaw (EventBridge cron):
  → SF skill: pull agent actions from IR_Audit_Log__c
  → Analyze: unauthorized access, MNPI violations, restricted list breaches
  → SEC EDGAR MCP: new regulatory filings affecting covered companies
  → News MCP: regulatory actions, enforcement notices
  → Generate compliance report:
    - Agent activity summary
    - Flagged items for human review
    - Regulatory filing changes
    - FINRA 2026 compliance checklist status
  → Write to Salesforce, notify compliance officer
  → Critical violation → immediate escalation via all channels
```

**Value:** FINRA 2026 demands AI agents be supervised like human employees. This makes the agent self-auditing. Audit trail in Salesforce provides books-and-records preservation.

---

### Use Case 5: KYC/AML Onboarding Automation

**Who:** Operations, compliance, client service
**Trigger:** New client account created in Salesforce

```
Platform Event (new Account) → OpenClaw:
  → SF skill: pull application data
  → Textract: extract from uploaded ID, proof of address
  → Compliance skill: sanctions lists, PEP databases, adverse media
  → News MCP: adverse media search
  → Risk scoring: jurisdiction, source of wealth, PEP status
  → Generate KYC report:
    - Identity verification status
    - Sanctions/PEP screening results
    - Adverse media findings
    - Risk tier recommendation
  → Write to SF compliance objects
  → Low risk → auto-approve (with audit trail)
  → Medium/high risk → route to compliance officer
```

**Value:** KYC drops from days to minutes for low-risk clients. Multi-source screening is more thorough than manual. Every decision logged for audit.

---

### Use Case 6: Real-Time Portfolio Risk Alerting

**Who:** Risk managers, portfolio managers
**Trigger:** Kinesis real-time market data stream

```
Kinesis → OpenClaw:
  → Monitor positions against thresholds:
    - Concentration > 10%, sector > 25%, drawdown breach, VaR breach
  → When triggered:
    → SF skill: pull affected client portfolios
    → Financial Analysis: calculate impact, suggest rebalancing
    → Generate risk alert with affected clients and recommended actions
    → Push to risk manager via Telegram/Slack (immediate)
    → Write to Salesforce risk objects
    → Critical → escalate to CIO
```

**Value:** Real-time risk monitoring connecting market data (AWS) to client portfolios (Salesforce) through an agent that reasons about implications — not just threshold alerts.

---

### Use Case 7: Regulatory Filing Deep Dive (10-K/10-Q Analysis)

**Who:** Research analysts, compliance
**Trigger:** "Analyze NVIDIA's latest 10-K — focus on risk factors and revenue recognition"

```
Analyst (Slack) → OpenClaw → AutoResearchClaw (adapted):
  → SEC EDGAR MCP: download full 10-K PDF
  → Textract: extract tables, financials, risk factors
  → Comprehend: entity extraction, key phrases
  → Pipeline stages:
    → KNOWLEDGE_EXTRACT: risk factors, revenue policies, segments, guidance
    → SYNTHESIS: compare against prior year 10-K — what changed?
    → THESIS_GEN: material changes and implications
    → BRIEF_DRAFT + PEER_REVIEW + AUDIT_VERIFY
  → Write analysis to Salesforce, notify analyst
```

**Value:** 200-page 10-K analyzed in minutes. Year-over-year diff catches changes humans miss. Anti-fabrication traces every claim to filing text.

---

### Use Case 8: Multi-Asset Class Macro Research

**Who:** Multi-strategy fund analysts
**Trigger:** "What's the macro setup for Q3? Cover equities, fixed income, commodities, FX"

```
Analyst (Discord) → OpenClaw → AutoResearchClaw with branch exploration:
  → Fork into 4 parallel branches:
    Branch 1: Equities (S&P 500, sector rotation, earnings)
    Branch 2: Fixed Income (yield curve, credit spreads, Fed)
    Branch 3: Commodities (oil, gold, copper supply/demand)
    Branch 4: FX (DXY, EUR/USD, EM currencies)
  → Each branch runs Phases A-F independently
  → Phase G: Merge into unified macro outlook
  → Cross-asset correlation analysis
  → Generate comprehensive macro brief
```

**Value:** AutoResearchClaw's branch exploration (designed for parallel hypothesis testing) maps perfectly to multi-asset research. Four streams run simultaneously, merge into a coherent cross-asset view.

---

## What Each Layer Contributes

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│  OpenClaw          → User interface (12+ channels)               │
│                    → Orchestration & intent routing               │
│                    → Persistent memory per user                  │
│                    → Skill marketplace (rapid capability add)    │
│                                                                  │
│  AutoResearchClaw  → Structured multi-stage pipeline             │
│                    → HITL co-pilot (6 intervention modes)        │
│                    → Anti-fabrication & claim verification        │
│                    → Self-healing & cross-run learning            │
│                    → Multi-agent debate for thesis generation     │
│                    → Branch exploration for parallel research     │
│                                                                  │
│  Salesforce        → Client relationship data (CRM)              │
│                    → Compliance records & audit trail             │
│                    → Data Cloud (unified profiles, RAG)           │
│                    → Platform Events (triggers)                  │
│                    → Agentforce (optional, SF-native flows)      │
│                    → Einstein Trust Layer (CRM interactions)     │
│                                                                  │
│  AWS               → LLM compute (Bedrock / Claude)              │
│                    → Serverless tools (Lambda MCP servers)        │
│                    → Data (Redshift, S3, Kinesis)                │
│                    → AI services (Transcribe, Textract, Compreh.)│
│                    → Agent hosting (AgentCore, zero idle cost)   │
│                    → Event orchestration (EventBridge)            │
│                                                                  │
│  TOGETHER          → Analyst says "Research NVIDIA" in Slack     │
│                    → Gets a verified, auditable, compliance-     │
│                      screened research brief written to CRM      │
│                    → Every step logged for FINRA                 │
│                    → System learns and improves over time         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
