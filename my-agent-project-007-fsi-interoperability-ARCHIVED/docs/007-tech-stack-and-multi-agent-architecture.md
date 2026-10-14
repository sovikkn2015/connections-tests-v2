# 007 Tech Stack and Multi-Agent Architecture

---

## Tech Stack

```
LAYER              TECHNOLOGY                    PURPOSE
─────────────────────────────────────────────────────────────────────
Languages          Python 3.12+                  11 of 13 modules + compliance
                   TypeScript/Node               M12 Web Console + 1 adapter
                   Rego                          OPA policy rules (all compliance)

Frontend           React 18 + TypeScript         M12 Web Console (51 files)
                   Tailwind CSS 4                Styling + design system
                   Vite                          Build + dev server
                   TanStack Query                Server state (M6 API calls)
                   Zustand                       Client state (sidebar, theme)
                   Recharts                      Charts (allocation, performance)

Backend APIs       FastAPI                       M1, M2/M4, M6, M8, M9, M10
                   Pydantic v2                   Models, validation, config

Compliance         OPA (Open Policy Agent)       Deterministic rule evaluation
                   Rego                          2,100+ rules, 5 jurisdictions
                   (NO LLM for compliance)       Compliance is never probabilistic

AI / Agents        Claude Sonnet (Bedrock)       Research specialist (deep reasoning)
                   Claude Haiku (Bedrock)        Routing, conversation, execution
                   Managed Agents (cloud)        Agent orchestration (Tier 3/4)
                   Strands SDK (hybrid)          Agent orchestration (Tier 1/2/5)
                   LangGraph                     23-stage research pipeline

Protocol           MCP                           Agent-to-tool (all 20 adapters)
                   REST/HTTP                     Module-to-module (mTLS)
                   SSE                           Streaming agent responses to UI
                   FIX 4.2                       Broker order execution (M13)
                   gRPC                          SS&C Eze OMS (M11)
                   BLPAPI                        Bloomberg B-PIPE (M11)
                   SFTP                          Custodian daily files (M11)

Databases          PostgreSQL (RDS)              User store, pipeline state
                   Redis (ElastiCache)           Working memory, rate limits
                   DynamoDB                      Memory L2/L3, checkpoints
                   pgvector / Pinecone           Semantic memory L4
                   S3 Object Lock (WORM)         Regulatory audit (6-year)
                   Langfuse                      LLM observability

Auth               Keycloak                      Identity provider
                   JWT RS256                     Agent Identity Documents
                   PyJWT + cryptography          Token signing/verification

Infrastructure     Kubernetes (EKS)              Container orchestration
                   Docker                        Every module = own container
                   Terraform                     VPC, PrivateLink, subnets
                   Helm                          Umbrella chart, 3 topologies
                   ArgoCD                        GitOps deployment
                   GitHub Actions                11-job CI/CD pipeline
                   cert-manager                  mTLS (24hr rotation)
                   HashiCorp Vault               Secrets management
                   Trivy                         CVE scanning

Monitoring         Prometheus + Grafana           Metrics
                   OpenTelemetry + Jaeger         Distributed tracing
                   Langfuse                       LLM observability
                   Structured JSON logs           CloudWatch / ELK
```

---

## Multi-Agent Architecture

```
                              USER
                               |
              ┌────────────────┴────────────────┐
              |                                  |
         Slack/Teams/                      M12 Web Console
         WhatsApp                          (React + TypeScript)
              |                                  |
              └────────────────┬────────────────┘
                               |
                        M12 OpenClaw
                     (Channel Gateway)
                     12+ channels → unified format
                               |
                               ▼
                    ┌─────────────────────┐
                    │  M9 INTENT ROUTER   │
                    │  Haiku · <500ms     │
                    │                     │
                    │  "Prep me for       │
                    │   Henderson"        │
                    │       ↓             │
                    │  client.prep_meeting│
                    │  confidence: 0.97   │
                    │  route: client_svc  │
                    └─────────┬───────────┘
                              |
                              ▼
         ┌──────────────────────────────────────────┐
         │          SUPERVISOR                       │
         │   Managed Agents (cloud)                  │
         │   Strands SDK (hybrid/on-prem)            │
         │   Haiku · <500ms routing                  │
         │                                           │
         │   Constrained plan-and-execute:           │
         │   Routes to correct specialist            │
         │   based on M9 intent classification       │
         └──┬──────┬──────┬──────┬──────┬───────────┘
            |      |      |      |      |
            ▼      ▼      ▼      ▼      ▼

  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐
  │ RESEARCH ││ CLIENT   ││COMPLIANCE││EXECUTION ││ONBOARDING│
  │          ││ SERVICE  ││          ││          ││          │
  │ Sonnet   ││ Haiku    ││ NO LLM   ││ Haiku    ││ Haiku    │
  │ LangGraph││ Strands  ││ OPA/Rego ││ State    ││ Workflow │
  │          ││          ││ Only     ││ Machine  ││ Engine   │
  │ 23 stages││ <3s resp ││ <10ms    ││ Mandatory││ Multi-   │
  │ 3 HITL   ││ Cross-   ││ 99.9%   ││ HITL     ││ session  │
  │ gates    ││ channel  ││ accurate ││ 24hr     ││ KYC →    │
  │ Map-     ││ memory   ││          ││ timeout  ││ Sanctions│
  │ reduce   ││ L1-L5    ││ Called   ││ Zero     ││ → Risk → │
  │ 20min max││          ││ as TOOL  ││ autonomous│ Account │
  │          ││          ││ by others││ trades   ││ → DocuSign│
  └────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘
       |           |           |           |           |
       └───────────┴───────────┴─────┬─────┴───────────┘
                                     |
                    ALL specialist calls go through:
                                     |
                                     ▼
  ╔══════════════════════════════════════════════════════════════╗
  ║              M6 MCP GATEWAY (THE CORE)                      ║
  ║                                                              ║
  ║  ┌─── PRE-CALL ──────────────────────────────────────────┐  ║
  ║  │                                                        │  ║
  ║  │  M1 Identity ──→ M2 Authority ──→ M4 MNPI ──→ M5 Cfg │  ║
  ║  │  (JWT RS256)     (OPA/Rego)       (field strip)        │  ║
  ║  │  WHO are you?    ARE you allowed? WHAT can you see?    │  ║
  ║  │                                                        │  ║
  ║  └────────────────────────┬───────────────────────────────┘  ║
  ║                           │                                   ║
  ║              Circuit Breaker → Rate Limit → Retry             ║
  ║                           │                                   ║
  ║  ┌─── POST-CALL ─────────┴───────────────────────────────┐  ║
  ║  │                                                        │  ║
  ║  │  M7 Translate ──→ M4 MNPI ──→ Gap6 Scan ──→ M10 Audit│  ║
  ║  │  (vendor→canon)   (strip resp)  (regex+NER)  (3-tier) │  ║
  ║  │                                                        │  ║
  ║  └────────────────────────────────────────────────────────┘  ║
  ║                                                              ║
  ║  + Web API Bridge (13 REST endpoints for M12 UI)             ║
  ║  + SSE streaming with mid-stream leakage scan                ║
  ║                                                              ║
  ╚══════════════════════════════════════════════════════════════╝
                                     |
                                     ▼
  ┌──────────────────────────────────────────────────────────────┐
  │              M11 MCP ADAPTERS (20 adapters)                   │
  │                                                               │
  │  REST (Python)     BLPAPI (Python)   gRPC (Python)           │
  │  ┌────────────┐    ┌────────────┐    ┌────────────┐          │
  │  │Salesforce  │    │Bloomberg   │    │SS&C Eze    │          │
  │  │Orion       │    │B-PIPE      │    │(hedge OMS) │          │
  │  │eMoney      │    │$24K+/yr    │    └────────────┘          │
  │  │Schwab      │    └────────────┘                            │
  │  │Fidelity    │    SFTP (Python)     MCP-Native              │
  │  │Pershing    │    ┌────────────┐    ┌────────────┐          │
  │  │Wealthbox   │    │Schwab daily│    │FactSet     │          │
  │  │Redtail     │    │Fidelity    │    │(own MCP    │          │
  │  │Envestnet   │    │daily files │    │ server)    │          │
  │  │ComplySci   │    └────────────┘    └────────────┘          │
  │  │SEC EDGAR   │                                              │
  │  │Market Data │    M13 FIX BRIDGE (Separate Module)          │
  │  │News Search │    ┌────────────────────────────────┐        │
  │  └────────────┘    │FIX 4.2 TCP · QuickFIX          │        │
  │                    │Stateful sessions · Seq tracking │        │
  │  REST (TypeScript) │StatefulSet · Gap-fill recovery  │        │
  │  ┌────────────┐    └────────────────────────────────┘        │
  │  │SEC EDGAR TS│                                              │
  │  │(reference) │                                              │
  │  └────────────┘                                              │
  └──────────────────────────────────────────────────────────────┘
                                     |
                                     ▼
  ┌──────────────────────────────────────────────────────────────┐
  │                    EXTERNAL SYSTEMS (17+)                     │
  │                                                               │
  │  CRM           Portfolio        Planning      Market Data    │
  │  Salesforce    Orion            eMoney        Bloomberg      │
  │  Wealthbox     Schwab           MoneyGuide    FactSet        │
  │  Redtail       Fidelity                       Alpha Vantage  │
  │                Pershing         Compliance    News API       │
  │                Eze OMS          Smarsh                       │
  │                                 ComplySci     Regulatory     │
  │  Execution                                    SEC EDGAR      │
  │  Brokers (FIX 4.2)                                           │
  └──────────────────────────────────────────────────────────────┘


  ╔══════════════════════════════════════════════════════════════╗
  ║                    6-LAYER MEMORY                            ║
  ║  (MNPI-filtered on retrieval via M4)                        ║
  ║                                                              ║
  ║  L1 Working     Redis          8hr TTL    conversation       ║
  ║  L2 Short-term  DynamoDB       7-day      summarized         ║
  ║  L3 Episodic    DynamoDB+vec   2-year     interactions       ║
  ║  L4 Semantic    pgvector       permanent  client facts       ║
  ║  L5 Procedural  S3 JSON        permanent  advisor prefs      ║
  ║  L6 Compliance  S3 WORM        6+ years   immutable audit    ║
  ╚══════════════════════════════════════════════════════════════╝


  ╔══════════════════════════════════════════════════════════════╗
  ║                    3-TIER AUDIT (M10)                        ║
  ║  (Every action, every request, fail-closed)                  ║
  ║                                                              ║
  ║  Tier 1: Langfuse        → LLM observability (90-day)       ║
  ║  Tier 2: S3 Object Lock  → WORM regulatory (6-year)         ║
  ║  Tier 3: CRM (Salesforce) → Business-accessible             ║
  ║  + SHA-256 integrity hash per entry                          ║
  ║  + Provenance chain: M1→M9→M2→M6→M11→M7→M4→LLM→M10        ║
  ╚══════════════════════════════════════════════════════════════╝
```

---

*Project 007 FSI Interoperability Platform*
