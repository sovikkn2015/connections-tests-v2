# Project 007 — Input/Output Diagram (ASCII)

```
╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║                                    INPUTS (LEFT)                                             ║
╚══════════════════════════════════════════════════════════════════════════════════════════════╝

  ┌─────────────────────┐
  │   HUMAN USERS        │
  │                      │
  │  Advisor on Slack    │──┐
  │  Advisor on Teams    │──┤
  │  Advisor on WhatsApp │──┤
  │  Advisor on Web UI   │──┤
  │  Principal (reviewer)│──┤
  │  Compliance Officer  │──┘
  └─────────────────────┘   │
                            │  Natural language queries
                            │  "Prep me for Henderson meeting"
                            │  "Show Henderson's portfolio"
                            │  "Submit buy order for AAPL"
                            │  Approval/rejection decisions
                            ▼
╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║                              M12 OpenClaw (Channel Gateway)                                  ║
║                     12+ channels → unified message format                                    ║
╚═══════════════════════════════════════════╤══════════════════════════════════════════════════╝
                                            │
                    ┌───────────────────────┐│┌───────────────────────┐
                    │ IN:                   │││ OUT:                  │
                    │  - raw user message   │││  - formatted response │
                    │  - channel metadata   │││  - rich cards/links   │
                    │  - session context    │││  - file attachments   │
                    └───────────────────────┘│└───────────────────────┘
                                            ▼
╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║                              M9 Intent Router (Haiku, <500ms)                                ║
╚═══════════════════════════════════════════╤══════════════════════════════════════════════════╝
                    ┌───────────────────────┐│┌───────────────────────┐
                    │ IN:                   │││ OUT:                  │
                    │  - user message       │││  - structured intent  │
                    │  - AID token          │││    (domain.action)    │
                    │  - conversation hist  │││  - confidence score   │
                    │                       │││  - extracted params   │
                    │                       │││  - specialist routing │
                    └───────────────────────┘│└───────────────────────┘
                                            │
                    ┌───────────────────────┐│
                    │ Confidence thresholds: ││
                    │  >95%  → direct route ││
                    │  80-95 → LLM plan     ││
                    │  <80%  → clarify user ││
                    └───────────────────────┘│
                                            ▼
╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║                         SUPERVISOR (Managed Agents / Strands)                                ║
║                              Routes to 5 specialists                                         ║
╚═══════════════════════════════════════════╤══════════════════════════════════════════════════╝
            ┌───────────┬───────────┬───────┴───────┬───────────┐
            ▼           ▼           ▼               ▼           ▼
  ┌─────────────┐┌────────────┐┌──────────┐┌────────────┐┌───────────┐
  │  RESEARCH   ││  CLIENT    ││COMPLIANCE││ EXECUTION  ││ONBOARDING │
  │  Specialist ││  SERVICE   ││Specialist││ Specialist ││Specialist │
  │  (Sonnet)   ││  (Haiku)   ││(OPA/Rego)││ (Haiku)    ││(Haiku)    │
  │  LangGraph  ││  Strands   ││ NO LLM   ││ StateMach  ││ Workflow  │
  └──────┬──────┘└─────┬──────┘└────┬─────┘└─────┬──────┘└─────┬─────┘
         │             │            │             │             │
         │ IN:         │ IN:        │ IN:         │ IN:         │ IN:
         │  query      │  client_id │  identity   │  order spec │  client info
         │  sources    │  intent    │  action     │  approval   │  KYC docs
         │  budget     │  memory    │  target     │  token      │  risk profile
         │             │  context   │  context    │             │
         │ OUT:        │ OUT:       │ OUT:        │ OUT:        │ OUT:
         │  Research   │  meeting   │  ALLOW/     │  order      │  account
         │  Brief      │  prep      │  DENY/      │  status     │  opened
         │  (sourced)  │  portfolio │  ESCALATE   │  confirm    │  DocuSign
         │  23 stages  │  summary   │  (determ.)  │  T+1 track  │  CDD record
         └──────┬──────┘─────┬──────┘─────┬───────┘──────┬──────┘──────┬──────
                │            │            │              │             │
                └────────────┴────────────┴──────┬───────┴─────────────┘
                                                 │
                              ALL specialist calls go through:
                                                 ▼
╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║                        M6 MCP Gateway (Trust-Aware — THE CORE)                               ║
╠══════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                              ║
║   ┌──────────────────────────── PRE-CALL PIPELINE ──────────────────────────────┐            ║
║   │                                                                              │            ║
║   │  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐  │            ║
║   │  │ M1 Identity  │───>│ M2 Authority │───>│ M4 MNPI      │───>│ M5 Config  │  │            ║
║   │  │              │    │              │    │ (pre-filter)  │    │ (archetype)│  │            ║
║   │  │ IN:          │    │ IN:          │    │ IN:           │    │ IN:        │  │            ║
║   │  │  AID token   │    │  identity    │    │  request      │    │  firm_id   │  │            ║
║   │  │              │    │  action      │    │  archetype    │    │            │  │            ║
║   │  │ OUT:         │    │  target      │    │  role         │    │ OUT:       │  │            ║
║   │  │  identity    │    │  context     │    │              │    │  vendor    │  │            ║
║   │  │  claims      │    │              │    │ OUT:          │    │  config    │  │            ║
║   │  │  (LEI, CRD,  │    │ OUT:         │    │  filtered    │    │  MNPI      │  │            ║
║   │  │   archetype,  │    │  ALLOW/      │    │  request     │    │  rules     │  │            ║
║   │  │   role)       │    │  DENY/       │    │  (MNPI       │    │            │  │            ║
║   │  │              │    │  ESCALATE    │    │   stripped)   │    │            │  │            ║
║   │  └─────────────┘    └──────────────┘    └──────────────┘    └────────────┘  │            ║
║   └──────────────────────────────────────────────────────────────────────────────┘            ║
║                                          │                                                    ║
║                                          ▼                                                    ║
║                              ┌──────────────────────┐                                        ║
║                              │  ROUTE TO VENDOR      │                                        ║
║                              │  (circuit breaker,    │                                        ║
║                              │   rate limit, retry)  │                                        ║
║                              └──────────┬───────────┘                                        ║
║                                          │                                                    ║
║   ┌──────────────────────────── POST-CALL PIPELINE ─────────────────────────────┐            ║
║   │                                                                              │            ║
║   │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐  │            ║
║   │  │ M7 Translate  │───>│ M4 MNPI      │───>│ Gap 6 Leak   │───>│ M10 Audit  │  │            ║
║   │  │              │    │ (post-filter) │    │ Scan (3-lyr) │    │ Logger     │  │            ║
║   │  │ IN:          │    │ IN:           │    │ IN:           │    │ IN:        │  │            ║
║   │  │  vendor raw   │    │  canonical   │    │  response    │    │  full      │  │            ║
║   │  │  response     │    │  response    │    │  text        │    │  journey   │  │            ║
║   │  │              │    │  archetype    │    │              │    │            │  │            ║
║   │  │ OUT:         │    │              │    │ OUT:          │    │ OUT:       │  │            ║
║   │  │  canonical    │    │ OUT:         │    │  PASS/BLOCK  │    │  3-tier:   │  │            ║
║   │  │  type         │    │  stripped    │    │  (regex+NER  │    │  Langfuse  │  │            ║
║   │  │  (Pydantic)   │    │  response    │    │   +Haiku)    │    │  S3 WORM   │  │            ║
║   │  │              │    │  (no SSN,    │    │              │    │  CRM       │  │            ║
║   │  │              │    │   no DOB,    │    │              │    │  SHA-256   │  │            ║
║   │  │              │    │   no MNPI)   │    │              │    │  6-year    │  │            ║
║   │  └──────────────┘    └──────────────┘    └──────────────┘    └────────────┘  │            ║
║   └──────────────────────────────────────────────────────────────────────────────┘            ║
║                                                                                              ║
╚═══════════════════════════════════════════╤══════════════════════════════════════════════════╝
                                            │
                                            ▼
╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║                     M11 MCP Adapters (17+ systems, 5 protocols)                              ║
╠══════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                              ║
║  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐            ║
║  │ M11-REST (TS/Py)│ │ M11-BLPAPI (Py) │ │ M11-gRPC (Py)  │ │ M11-SFTP (Py)  │            ║
║  │                 │ │                 │ │                 │ │                 │            ║
║  │ IN:  MCP call   │ │ IN:  MCP call   │ │ IN:  MCP call   │ │ IN:  MCP call   │            ║
║  │ OUT: vendor JSON│ │ OUT: market data│ │ OUT: OMS data   │ │ OUT: daily file │            ║
║  │                 │ │                 │ │                 │ │      parsed     │            ║
║  │ Salesforce FSC  │ │ Bloomberg B-PIPE│ │ SS&C Eze (xAPI) │ │ Schwab daily    │            ║
║  │ Orion           │ │ ($24K+/yr)      │ │ (hedge fund OMS)│ │ Fidelity daily  │            ║
║  │ eMoney          │ │                 │ │                 │ │                 │            ║
║  │ Schwab REST     │ └─────────────────┘ └─────────────────┘ └─────────────────┘            ║
║  │ Fidelity        │                                                                        ║
║  │ Pershing        │ ┌─────────────────┐ ┌─────────────────────────────────────┐            ║
║  │ SEC EDGAR       │ │ M11-MCP-NATIVE  │ │ M13 FIX Bridge (Separate Module)   │            ║
║  │ Alpha Vantage   │ │                 │ │                                     │            ║
║  │ News API        │ │ IN:  MCP call   │ │ IN:  MCP call (from M6)            │            ║
║  │ Wealthbox       │ │ OUT: passthru   │ │ OUT: ExecutionReport, OrderAck     │            ║
║  │ Redtail         │ │                 │ │                                     │            ║
║  │ Envestnet       │ │ FactSet (own    │ │ FIX 4.2 TCP, stateful sessions     │            ║
║  │ ComplySci       │ │  MCP server)    │ │ QuickFIX, StatefulSet, seq nums    │            ║
║  └─────────────────┘ └─────────────────┘ └─────────────────────────────────────┘            ║
║                                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════════════════════╝
                                            │
                                            ▼
╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║                                   EXTERNAL SYSTEMS                                           ║
╠══════════════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                              ║
║  CRM/Client        Portfolio/Custody     Planning          Market Data       Compliance       ║
║  ┌──────────┐      ┌──────────┐         ┌──────────┐      ┌──────────┐     ┌──────────┐     ║
║  │Salesforce│      │ Orion    │         │ eMoney   │      │Bloomberg │     │ Smarsh   │     ║
║  │ FSC      │      │ Schwab   │         │MoneyGuide│      │ FactSet  │     │ComplySci │     ║
║  │Wealthbox │      │ Fidelity │         │RightCap  │      │Alpha Vnt │     │          │     ║
║  │ Redtail  │      │ Pershing │         │          │      │ News API │     │          │     ║
║  └──────────┘      │ Eze OMS  │         └──────────┘      └──────────┘     └──────────┘     ║
║                    └──────────┘                                                              ║
║                                                                                              ║
║  Regulatory        Execution                                                                 ║
║  ┌──────────┐      ┌──────────┐                                                             ║
║  │SEC EDGAR │      │ Brokers  │                                                             ║
║  │          │      │ (FIX 4.2)│                                                             ║
║  └──────────┘      └──────────┘                                                             ║
║                                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════════════════════╝


╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║                                    OUTPUTS (RIGHT)                                           ║
╚══════════════════════════════════════════════════════════════════════════════════════════════╝

  BACK TO USER (via M12 OpenClaw):
  ┌─────────────────────────────────────────────────────────────────┐
  │  - Meeting prep brief (Client + Holdings + Plan, MNPI-filtered) │
  │  - Portfolio review (holdings, performance, tax lots)           │
  │  - Research brief (23-stage, sourced, map-reduce synthesis)     │
  │  - Order confirmation (after HITL approval)                     │
  │  - Onboarding status (KYC, account opening progress)           │
  │  - Compliance alerts (restricted list, concentration, AML)      │
  │  - Clarification questions (when intent confidence <80%)        │
  └─────────────────────────────────────────────────────────────────┘

  AUDIT TRAIL (via M10, every request):
  ┌─────────────────────────────────────────────────────────────────┐
  │  Tier 1: Langfuse        → LLM observability (90-day)          │
  │  Tier 2: S3 Object Lock  → WORM regulatory record (6-year)     │
  │  Tier 3: CRM (Salesforce) → Business-accessible audit trail     │
  │  + SHA-256 integrity hash per stage                             │
  │  + Provenance chain: M1→M9→M2→M6→M11→M7→M4→LLM→M10           │
  └─────────────────────────────────────────────────────────────────┘

  COMPLIANCE OUTPUTS (via M2/M4 OPA, deterministic):
  ┌─────────────────────────────────────────────────────────────────┐
  │  - ALLOW / DENY / ESCALATE decisions (every request)            │
  │  - MNPI-filtered responses (SSN, DOB, account nums stripped)    │
  │  - Principal review queue items (BD comms, FINRA 2210)          │
  │  - Reg BI documentation (auto-generated per recommendation)     │
  │  - CTR reports ($10K+ transactions)                             │
  │  - SAR triggers (suspicious activity patterns)                  │
  │  - Sanctions screening results                                  │
  │  - ERISA account-type enforcement                               │
  │  - Cross-border jurisdiction checks (US/EU/UK/SG/HK)           │
  │  - WSP-to-YAML mapping reports (human policy <-> OPA rules)     │
  └─────────────────────────────────────────────────────────────────┘

  MEMORY WRITES (6 layers, MNPI-filtered on retrieval):
  ┌─────────────────────────────────────────────────────────────────┐
  │  L1: Working Memory    → Redis          (8hr TTL, conversation) │
  │  L2: Short-term Memory → DynamoDB       (7-day, summarized)     │
  │  L3: Episodic Memory   → DynamoDB+vec   (2-year, interactions)  │
  │  L4: Semantic Memory   → pgvector       (permanent, facts)      │
  │  L5: Procedural Memory → S3 JSON        (permanent, prefs)      │
  │  L6: Compliance Memory → S3 WORM        (6+ years, immutable)   │
  └─────────────────────────────────────────────────────────────────┘
```
