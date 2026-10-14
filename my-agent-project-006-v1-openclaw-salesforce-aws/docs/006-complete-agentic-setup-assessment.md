# Project 006: Complete Agentic Setup, Usefulness, Commercial Value, and Readiness Assessment

> Date: April 12, 2026
> Scope: Full analysis of the 006 OpenClaw + Salesforce + AWS agentic system
> Method: Complete codebase read — every config, skill, pipeline stage, MCP server, frontend component, eval framework, and deployment artifact

---

## Table of Contents

1. [The Entire Agentic Setup](#1-the-entire-agentic-setup)
2. [How Useful Is It?](#2-how-useful-is-it)
3. [Why Would an FSI Customer Consider 006?](#3-why-would-an-fsi-customer-consider-006)
4. [How Ready Is 006?](#4-how-ready-is-006)

---

## 1. The Entire Agentic Setup

Project 006 is a multi-platform AI agent system for FSI equity research. An analyst types something like "Deep dive on NVIDIA ahead of earnings" in Slack, and gets back a compliance-screened research brief with a rating, target price, DCF valuation, comps analysis, and Monte Carlo simulation — every step auditable for FINRA.

### High-Level Flow

```
Analyst (Slack / Web / WhatsApp)
  → OpenClaw Gateway (AgentCore, WebSocket)
    → Claude Sonnet 4.6 / Haiku 4.5 (Bedrock)
    → AutoResearchClaw Pipeline (23 stages, 3 HITL gates)
    → MCP Servers (Lambda): SEC EDGAR, Market Data, News
    → Financial Skills: DCF, comps, Monte Carlo, stress test
    → Salesforce CRM: client data, audit trail, research notes
```

### Agent Runtime: OpenClaw on AWS Bedrock AgentCore

OpenClaw is the sole agent runtime. It runs inside a Docker container on Bedrock AgentCore (serverless, zero idle cost). The container (`agentcore/Dockerfile`) runs two processes via `start.sh`:

1. OpenClaw Gateway on port 18789 — the brain. Handles reasoning, tool selection, memory, channels.
2. An HTTP adapter on port 8080 — bridges AgentCore's HTTP contract to OpenClaw's REST API.

The adapter (`adapter.js`) tries `/v1/chat/completions` first (OpenAI-compatible), then falls back to `/hooks/agent`. Both are synchronous — no WebSocket needed inside the container.

### LLMs: Claude on Bedrock

Two models configured in `openclaw.json`:

- Claude Sonnet 4.6 (`us.anthropic.claude-sonnet-4-6`) — primary, for L3-L5 queries and all 23 pipeline stages
- Claude Haiku 4.5 (`us.anthropic.claude-haiku-4-5-20251001-v1:0`) — fast model for simple L1-L2 lookups

All LLM calls go through Bedrock. No GPT, no Comprehend, no FinBERT. The LLM handles all sentiment analysis directly.

### The 23-Stage AutoResearchClaw Pipeline (`pipeline.py`)

This is the core engine. `FSIResearchPipeline` orchestrates everything:

| Phase | Stages | What Happens |
|-------|--------|-------------|
| A — Intake | 1-2 | Parse query (regex for ticker, event type, timeframe), fetch CRM context from Salesforce (company, coverage, watchlist, prior research, FSC holdings) |
| B — Data Collection | 3-6 | MCP calls to market-data (quote, price history, consensus, earnings calendar), news-search (articles, headlines), sec-edgar (10-K, 10-Q, 8-K). LLM summarizes earnings transcripts. |
| C — Validation | 7 | **HITL Gate** — analyst reviews data completeness score before analysis proceeds |
| D — Analysis | 8-12 | Prepare model inputs from collected data, run DCF (`dcf.py`), comps (`comps.py`), Monte Carlo (`monte_carlo.py`), LLM sentiment synthesis |
| E — Review | 13 | **HITL Gate** — analyst reviews model outputs (DCF fair value, comps implied price, MC range) |
| F — Synthesis | 14-18 | LLM generates thesis (bull/bear/base), catalysts, risks, rating (BUY/HOLD/SELL), weighted target price (DCF 40%, Comps 30%, MC 30%) |
| G — Output | 19-20 | Assemble structured brief, run compliance screening (restricted list, MNPI, trading window, concentration), anti-fabrication verification |
| H — Delivery | 21-23 | **HITL Gate** — analyst final approval, write `IR_Research_Note__c` to Salesforce, write `IR_Audit_Log__c`, notify via channels |

The pipeline has self-healing (retry failed stages up to 3 times) and MetaClaw cross-run learning (records lessons from failures/successes for future runs).

Stages 14 and 17 use a dual trust layer — they try Einstein Trust Layer (SF Models API) first, falling back to direct Bedrock if unavailable.


---

## 4. How Ready Is 006?

### Summary Scorecard (71 Design Tasks)

| Phase | Tasks | Done | Partial | Not Done | Broken/Deviated |
|-------|-------|------|---------|----------|-----------------|
| 1 Foundation | 12 | 8 | 1 | 3 | 0 |
| 2 MCP Servers | 8 | 8 | 0 | 0 | 0 |
| 3 Pipeline | 12 | 8 | 2 | 0 | 2 |
| 4 Models | 10 | 8 | 0 | 0 | 2 |
| 5 Production | 14 | 10 | 0 | 4 | 0 |
| 6 MuleSoft | 15 | 0 | 0 | 15 | 0 |
| **Total** | **71** | **42 (59%)** | **3 (4%)** | **22 (31%)** | **4 (6%)** |

### What's Solid and Working (Locally)

- **3 MCP servers** (SEC EDGAR, Market Data, News) — 8/8 tasks done, real APIs, MCP-compliant, deployed via SAM. This is the strongest layer.
- **23-stage pipeline** — all stages implemented, financial models real (DCF, comps, Monte Carlo), HITL gates wired, compliance screening functional, audit logging dual-writes to Langfuse + Salesforce. It's a custom build (not an AutoResearchClaw fork as designed), but it works.
- **Salesforce metadata** — 5 custom objects, 39 fields, Connected App, Permission Set, seed data (5 idempotent Apex scripts). Reproducible from scratch.
- **Financial models** — DCF with sensitivity tables, comps on 5 metrics, Monte Carlo with percentiles, plus bonus stress test, portfolio impact, and rebalance modules.
- **Frontend** — React 19 SPA with WebSocket to OpenClaw, pipeline tracker, HITL panel, brief viewer, SF OAuth PKCE.
- **Security remediation** — 8 of 15 findings resolved, 1 mitigated. Gateway token no longer in browser bundle, MNPI filtering implemented at the data layer, CSP headers, rate limiting, MCP input sanitization.
- **Evaluation framework** — 150-query matrix with LLM-as-Judge, 7-dimension rubric. Ready to run.
- **AgentCore deployment** — real agent ARN, adapter bridges HTTP to OpenClaw Gateway, container builds and deploys.

### What's Config-Ready but Not Connected

- **Slack, WhatsApp, Telegram** — channel YAMLs exist with `enabled: true`, env var references, setup guides. Zero real tokens populated. Zero channels actually connected. Pipeline stage 23 now dispatches via OpenClaw hooks endpoint, but with no channel tokens, notifications go nowhere.
- **Per-user memory** — changed from `NO_MEMORY` to `SESSION_MEMORY` in config, needs AgentCore redeploy.
- **Secrets rotation** — CloudFormation template complete, not deployed.
- **Bedrock Guardrails** — CloudFormation template complete, deployment unverified.

### What's Genuinely Not Done

- **Phase 6 MuleSoft** — all 15 tasks are documentation only. Zero code. Trade execution, wires, KYC, account opening — none of it exists beyond curl examples in a SKILL.md. This is 21% of the entire project.
- **Full eval suite** — only 4 of 150 queries have been run. No performance baseline. No regression data.
- **End-to-end pipeline run** — `test-pipeline.py` exists but there's no evidence of a complete 23-stage run finishing all stages including real HITL gates.
- **FSC objects** — code handles them gracefully (queries with fallback), seed script exists, but actual FSC enablement requires a Salesforce license upgrade.
- **Official salesforce-api skill** — never installed. Pipeline uses inline HTTP calls. Works, but not as designed.

### What Deviated from the Design

- The pipeline is custom-built (~1,400 lines), not an AutoResearchClaw fork. The steering rules explicitly say "do NOT build a custom pipeline." It works well, but it's a design violation.
- Sentiment analysis is inline LLM calls, not a standalone skill. Correct per the tech stack decision (Claude > Comprehend), but different from the original design.
- HITL gates are at stages 7, 13, 21 — not 5, 8, 9, 17, 20 as originally designed. Config and code now match each other, but not the original spec.

### Security Findings Status

| Status | Count | Details |
|--------|-------|---------|
| Resolved | 8 | Gateway token, WebSocket rate limiting, MNPI enforcement, CSP headers, MCP input sanitization, CORS, error leakage, eval auth |
| Mitigated | 1 | Indirect prompt injection (boundary markers, not fully eliminated) |
| Open | 5 | Static SF access token (MEDIUM), Langfuse sensitive data (MEDIUM), MuleSoft HITL prompt-based (MEDIUM, moot — MuleSoft not built), no request signing (LOW), guardrails missing patterns (LOW) |
| N/A | 1 | Memory without encryption (memory was disabled, now SESSION_MEMORY) |

### Readiness by Use Case

**For a demo or proof-of-concept: ~75% ready.** The core loop works locally — query goes in, MCP servers fetch real data, models run, brief comes out, audit trail gets written. You could show this to a stakeholder today.

**For a pilot with real users: ~45% ready.** You'd need real channel tokens (Slack at minimum), a full eval suite run to establish baselines, the AgentCore deployment verified end-to-end, and the remaining security findings closed.

**For production at a regulated firm: ~25% ready.** MuleSoft (the action execution layer that makes 006 different from a research tool) is entirely unbuilt. Self-hosted Langfuse isn't done. No performance baselines exist. The eval suite hasn't been run at scale. FSC requires a license. And the custom pipeline (vs. a real AutoResearchClaw fork) means you're maintaining 1,400 lines of bespoke orchestration code with no upstream community.

### Remaining Work by Priority

**Critical path (blocks production):**

1. Full 23-stage pipeline end-to-end run with real HITL gates
2. Run full 150-query eval suite and establish baselines
3. Record performance measurements
4. Close remaining open security findings

**High priority (design spec gaps):**

5. Slack integration with real tokens + verified pipeline notification delivery
6. WhatsApp + Telegram with real API tokens
7. All 15 MuleSoft tasks (requires Anypoint Platform access)
8. FSC objects on org (requires FSC license)

**Medium priority (hardening):**

9. Deploy secrets rotation Lambda via CloudFormation
10. Deploy Bedrock Guardrails and verify
11. Redeploy AgentCore with SESSION_MEMORY + pipeline hooks changes

### Reproducibility

| Step | Command | Status |
|------|---------|--------|
| Clone repo | `git clone` | Ready |
| Create SF scratch org | `sf org create scratch` | Ready |
| Deploy SF metadata | `sf project deploy start` | Ready |
| Run seed data | `sf apex run --file scripts/apex/seed-*.apex` | Ready (5 scripts) |
| Deploy MCP servers | `sam deploy --guided` | Ready |
| Setup secrets | `./scripts/aws/setup-secrets.sh` | Ready (auto-populates) |
| Deploy Guardrails | `aws cloudformation deploy` | Ready (template) |
| Deploy rotation | `aws cloudformation deploy` | Ready (template) |
| Deploy to AgentCore | `agentcore deploy` | Ready |
| Install frontend | `cd frontend && npm install` | Ready |
| Run eval suite | `python evaluation/run_suite.py` | Ready (needs env vars) |
| Run pipeline test | `python scripts/test-pipeline.py` | Ready (needs env vars) |

Each step has scripts/templates, but no unified "deploy everything" command. Reproducible with manual orchestration.

### The Honest Summary

The data layer (MCP + Salesforce) and analysis layer (pipeline + models) are genuinely built. The integration layer (channels, AgentCore, MuleSoft) and hardening layer (eval, performance, security) are where the gaps live. 42 of 71 tasks done, 22 not done — and 15 of those 22 are MuleSoft, which requires an external platform dependency that hasn't been addressed at all.


---

## Appendix: ASCII Architecture Diagrams

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    PROJECT 006: THE COMPLETE PICTURE                        ║
║              OpenClaw + Salesforce + AWS — FSI Research Agent               ║
╚══════════════════════════════════════════════════════════════════════════════╝


═══════════════════════════════════════════════════════════════════════════════
 1. THE AGENTIC SETUP — HOW IT ALL WIRES TOGETHER
═══════════════════════════════════════════════════════════════════════════════

  Analyst (Slack / WhatsApp / Telegram / Web / Discord / API)
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  OPENCLAW GATEWAY (port 18789)                                      │
  │  Channels: Slack, WhatsApp, Telegram, Web, Discord, API, ...        │
  │  Memory: persistent per-user (SESSION_MEMORY)                       │
  │  Auth: SF OAuth2 PKCE (user identity) + Bearer token (agent comms)  │
  └──────────────────────────┬──────────────────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  AWS BEDROCK AGENTCORE (serverless, zero idle cost)                  │
  │                                                                     │
  │  ┌───────────────────────────────────────────────────────────────┐  │
  │  │  ADAPTER (port 8080)                                          │  │
  │  │  AgentCore HTTP ──► OpenClaw Gateway REST                     │  │
  │  │  POST /invocations ──► /v1/chat/completions (primary)         │  │
  │  │                    ──► /hooks/agent (fallback)                 │  │
  │  │  GET /ping ──► health check                                   │  │
  │  └───────────────────────────────────────────────────────────────┘  │
  │                                                                     │
  │  ┌───────────────────────────────────────────────────────────────┐  │
  │  │  LLMs (Bedrock)                                               │  │
  │  │                                                               │  │
  │  │  Claude Sonnet 4.6 ─── L3-L5 queries, all pipeline stages    │  │
  │  │  Claude Haiku 4.5  ─── L1-L2 simple lookups (fast)           │  │
  │  │                                                               │  │
  │  │  NO GPT. NO Comprehend. NO FinBERT. LLM does sentiment.      │  │
  │  └───────────────────────────────────────────────────────────────┘  │
  │                                                                     │
  │  ┌───────────────────────────────────────────────────────────────┐  │
  │  │  INTENT ROUTER                                                │  │
  │  │                                                               │  │
  │  │  Simple query (L1-L2) ──► Skills directly                     │  │
  │  │  Complex query (L3-L5) ──► 23-Stage Pipeline                  │  │
  │  └──────────┬────────────────────────────┬──────────────────────┘  │
  │             │                            │                         │
  │             ▼                            ▼                         │
  │  ┌──────────────────┐    ┌──────────────────────────────────────┐  │
  │  │  6 SKILLS         │    │  23-STAGE PIPELINE (pipeline.py)    │  │
  │  │                   │    │                                      │  │
  │  │  salesforce-crm   │    │  See pipeline diagram below          │  │
  │  │  financial-analysis│   │                                      │  │
  │  │  compliance-screen│    │  3 HITL gates (7, 13, 21)           │  │
  │  │  audit-logging    │    │  Self-healing (3 retries)           │  │
  │  │  fsi-research     │    │  MetaClaw cross-run learning        │  │
  │  │  mulesoft-api     │    │  Anti-fabrication ledger            │  │
  │  └──────────────────┘    └──────────────────────────────────────┘  │
  │             │                            │                         │
  │             ▼                            ▼                         │
  │  ┌─────────────────────────────────────────────────────────────┐   │
  │  │  3 MCP SERVERS (Lambda + API Gateway)                        │   │
  │  │                                                              │   │
  │  │  ┌────────────┐  ┌─────────────┐  ┌──────────────┐         │   │
  │  │  │ SEC EDGAR  │  │ MARKET DATA │  │ NEWS SEARCH  │         │   │
  │  │  │            │  │             │  │              │         │   │
  │  │  │ get_10k    │  │ get_quote   │  │ search_news  │         │   │
  │  │  │ get_10q    │  │ get_history │  │ get_headlines│         │   │
  │  │  │ get_8k     │  │ get_consens.│  │ get_coverage │         │   │
  │  │  │ get_insider│  │ get_options │  │              │         │   │
  │  │  │ search_fil.│  │ get_earnings│  │              │         │   │
  │  │  │            │  │             │  │              │         │   │
  │  │  │ SEC EDGAR  │  │ Alpha       │  │ Tavily API   │         │   │
  │  │  │ API (free) │  │ Vantage API │  │ (financial   │         │   │
  │  │  │            │  │             │  │  domains)    │         │   │
  │  │  └────────────┘  └─────────────┘  └──────────────┘         │   │
  │  │                                                              │   │
  │  │  Protocol: GET / + POST /tools/list + POST /tools/call       │   │
  │  │  Bridge: mcp-rest-bridge.mjs (stdio JSON-RPC ↔ Lambda REST)  │   │
  │  └──────────────────────────────────────────────────────────────┘   │
  │                                                                     │
  │  ┌─────────────────────────────────────────────────────────────┐   │
  │  │  SECURITY LAYERS                                             │   │
  │  │                                                              │   │
  │  │  Layer 1: Bedrock Guardrails (CloudFormation)                │   │
  │  │    PII masking (names, emails, phones → anonymized)          │   │
  │  │    SSN, credit cards, bank accounts → BLOCKED                │   │
  │  │    CUSIP, ISIN, SWIFT, account numbers → anonymized          │   │
  │  │    Content: hate, insults, violence, prompt attacks           │   │
  │  │    Denied: insider trading, unauthorized trading, audit del.  │   │
  │  │                                                              │   │
  │  │  Layer 2: Einstein Trust Layer (SF Models API)               │   │
  │  │    CRM data reasoning (stages 14, 17)                        │   │
  │  │    Prompt defense, PII masking, toxicity, audit              │   │
  │  │    Graceful fallback to Bedrock if unavailable                │   │
  │  │                                                              │   │
  │  │  Layer 3: MNPI Enforcement (mnpi_filter.py)                  │   │
  │  │    Strips: Shares, MarketValue, Price, Amount, Balance,      │   │
  │  │           Trade_Amount, Wire_Amount, Position_Size            │   │
  │  │    Holdings → ticker + client count only (no dollar amounts) │   │
  │  │                                                              │   │
  │  │  Layer 4: Zero credentials in git (AWS Secrets Manager)      │   │
  │  └──────────────────────────────────────────────────────────────┘   │
  └─────────────────────────────────────────────────────────────────────┘
       │
       │  Salesforce REST API (OAuth 2.0)
       ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │  SALESFORCE ORG                                                      │
  │                                                                      │
  │  ┌───────────────────────────────────────────────────────────────┐  │
  │  │  5 CUSTOM OBJECTS (39 fields total)                           │  │
  │  │                                                               │  │
  │  │  IR_Research_Note__c (12) ── briefs, ratings, target prices   │  │
  │  │  IR_Audit_Log__c    (11) ── FINRA trail, trace_id to Langfuse│  │
  │  │  IR_Company__c       (5) ── company master data               │  │
  │  │  IR_Coverage__c      (6) ── analyst-stock assignments         │  │
  │  │  IR_Watchlist__c     (5) ── tracked stocks, earnings dates    │  │
  │  └───────────────────────────────────────────────────────────────┘  │
  │                                                                      │
  │  Connected App (OpenClaw_Agent) ── OAuth2 PKCE                      │
  │  Permission Set (IR_Agent_Access) ── FLS for all IR_* objects       │
  │  FSC: FinServ__FinancialHolding__c (optional, graceful fallback)    │
  └─────────────────────────────────────────────────────────────────────┘


  OBSERVABILITY (dual-write everywhere):

  ┌──────────────────┐          ┌──────────────────────────┐
  │  LANGFUSE         │          │  IR_Audit_Log__c          │
  │  (engineering)    │◄─────────│  (regulatory / FINRA)     │
  │                   │ shared   │                           │
  │  Traces, spans,   │ Trace_Id │  Who, what, when,         │
  │  costs, latency   │          │  approved by, sources     │
  │                   │          │  7-year retention          │
  └──────────────────┘          └──────────────────────────┘
```



```
───────────────────────────────────────────────────────────────────────────
 THE 23-STAGE PIPELINE
───────────────────────────────────────────────────────────────────────────

  "Deep dive on NVIDIA ahead of earnings"
       │
       ▼
  ┌─── PHASE A: INTAKE (Stages 1-2) ───────────────────────────────────┐
  │  1. Parse: ticker=NVDA, event=earnings, timeframe=near_term        │
  │  2. CRM: company, coverage, watchlist, prior research, holdings    │
  └────────────────────────────────┬────────────────────────────────────┘
                                   │
  ┌─── PHASE B: DATA COLLECTION (Stages 3-6) ──────────────────────────┐
  │  3. Market Data MCP: quote, price history, consensus, earnings     │
  │  4. News Search MCP: articles (20), headlines (15)                 │
  │  5. SEC EDGAR MCP: 10-K, 10-Q, 8-K filings                        │
  │  6. LLM: earnings transcript summarization (no Comprehend)         │
  └────────────────────────────────┬────────────────────────────────────┘
                                   │
  ┌─── PHASE C: VALIDATION (Stage 7) ──────────────────────────────────┐
  │  7. ★ HITL GATE ★ — Data Quality                                   │
  │     Completeness score, missing sources listed                     │
  │     Analyst reviews and approves before analysis                   │
  └────────────────────────────────┬────────────────────────────────────┘
                                   │
  ┌─── PHASE D: ANALYSIS (Stages 8-12) ────────────────────────────────┐
  │  8.  Prepare model inputs from collected data                      │
  │  9.  DCF valuation (dcf.py) → fair value per share                 │
  │  10. Comps analysis (comps.py) → relative valuation                │
  │  11. Monte Carlo (monte_carlo.py) → probability distribution       │
  │  12. LLM sentiment synthesis (news + transcript)                   │
  └────────────────────────────────┬────────────────────────────────────┘
                                   │
  ┌─── PHASE E: REVIEW (Stage 13) ─────────────────────────────────────┐
  │  13. ★ HITL GATE ★ — Analysis Review                               │
  │      DCF fair value, comps implied, MC median + range              │
  │      Analyst reviews model outputs before synthesis                │
  └────────────────────────────────┬────────────────────────────────────┘
                                   │
  ┌─── PHASE F: SYNTHESIS (Stages 14-18) ──────────────────────────────┐
  │  14. LLM thesis (bull/bear/base cases) [Trust Layer]               │
  │  15. LLM catalyst identification (near-term + long-term)           │
  │  16. LLM risk assessment (ranked by probability × impact)          │
  │  17. LLM rating: BUY / HOLD / SELL [Trust Layer]                   │
  │  18. Target price: DCF 40% + Comps 30% + Monte Carlo 30%          │
  └────────────────────────────────┬────────────────────────────────────┘
                                   │
  ┌─── PHASE G: OUTPUT (Stages 19-20) ─────────────────────────────────┐
  │  19. Assemble structured brief (all sections + anti-fab ledger)    │
  │  20. Compliance check: restricted list, MNPI, trading window,      │
  │      concentration limits, anti-fabrication verification           │
  └────────────────────────────────┬────────────────────────────────────┘
                                   │
  ┌─── PHASE H: DELIVERY (Stages 21-23) ───────────────────────────────┐
  │  21. ★ HITL GATE ★ — Final Approval                                │
  │      Rating, target price, compliance status, warnings             │
  │      Analyst approves before publish                               │
  │  22. Write IR_Research_Note__c to Salesforce CRM                   │
  │  23. Write IR_Audit_Log__c + notify analyst via channels           │
  │      MetaClaw: record lessons for future runs                      │
  └────────────────────────────────┬────────────────────────────────────┘
                                   │
                                   ▼
  OUTPUT: Verified research brief in Salesforce CRM
  AUDIT:  Every action logged (FINRA 7-year retention)
  TRACE:  Full LLM trace in Langfuse (engineering observability)


  CROSS-CUTTING CONCERNS:

  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
  │ HITL     │ │ Anti-    │ │ MetaClaw │ │ Self-    │ │ Compliance   │
  │ Co-Pilot │ │ Fabrica- │ │ Learning │ │ Healing  │ │ Screening    │
  │ 3 gates  │ │ tion     │ │ cross-   │ │ 3 retry  │ │ MNPI, restr. │
  │ 7,13,21  │ │ ledger   │ │ run      │ │ cycles   │ │ list, window │
  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────────┘


═══════════════════════════════════════════════════════════════════════════════
 HOW USEFUL IS IT?
═══════════════════════════════════════════════════════════════════════════════

  GENUINELY USEFUL FOR:
  ┌─────────────────────────────────────────────────────────────────────┐
  │  ✓ Demo / proof-of-concept                                         │
  │  ✓ Architecture reference ("how would we build this?")             │
  │  ✓ Integration patterns (auth, MCP bridging, AgentCore, MNPI)      │
  │  ✓ Real data sources → real models → real CRM → real audit trail   │
  │  ✓ Answers hard questions: where do secrets live, how does auth    │
  │    flow, how do you enforce MNPI at the data layer                 │
  └─────────────────────────────────────────────────────────────────────┘

  FALLS SHORT FOR:
  ┌─────────────────────────────────────────────────────────────────────┐
  │  ✗ Financial models are simplified (flat margin DCF, textbook GBM) │
  │  ✗ Alpha Vantage rate-limited (need Bloomberg/Refinitiv for prod)  │
  │  ✗ Compliance screening is directional, not production-grade       │
  │  ✗ MuleSoft (action execution) is entirely spec-only               │
  │  ✗ Eval suite uses LLM-as-Judge (need human baselines for MRM)    │
  │  ✗ Single environment (no dev/staging/prod split)                  │
  └─────────────────────────────────────────────────────────────────────┘

  VERDICT:
  ┌─────────────────────────────────────────────────────────────────────┐
  │  "This is how it works + proof it runs"  ──► GOOD SHAPE            │
  │  "Production at a broker-dealer"         ──► 40-50% THERE          │
  │                                                                     │
  │  Remaining gap: data sourcing, model validation, regulatory sign-off│
  └─────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════
 WHY WOULD AN FSI CUSTOMER CONSIDER 006?
═══════════════════════════════════════════════════════════════════════════════

  THE PITCH (not "better AlphaSense" — it's the integration layer):

  ┌─────────────────────────────────────────────────────────────────────┐
  │                                                                     │
  │  AlphaSense / Brightwave / Hebbia                                   │
  │  ┌─────────────────────────────┐                                   │
  │  │  Research Intelligence      │                                   │
  │  │  (filings, transcripts,     │                                   │
  │  │   sentiment, models)        │                                   │
  │  └─────────────────────────────┘                                   │
  │           │                                                         │
  │           │  ← MANUAL GAP (analyst copies findings into CRM)        │
  │           │                                                         │
  │  ┌─────────────────────────────┐                                   │
  │  │  Salesforce CRM             │                                   │
  │  │  (client data, compliance)  │                                   │
  │  └─────────────────────────────┘                                   │
  │           │                                                         │
  │           │  ← MANUAL GAP (analyst calls broker to execute)         │
  │           │                                                         │
  │  ┌─────────────────────────────┐                                   │
  │  │  Trading / Execution        │                                   │
  │  │  (OMS, wires, KYC)         │                                   │
  │  └─────────────────────────────┘                                   │
  │                                                                     │
  │                        vs                                           │
  │                                                                     │
  │  006: ONE AGENT LOOP                                                │
  │  ┌─────────────────────────────────────────────────────────────┐   │
  │  │  Research ──► CRM ──► Compliance ──► Execution ──► Audit    │   │
  │  │     ▲                                                  │    │   │
  │  │     └──────────────────────────────────────────────────┘    │   │
  │  │                   (all connected, all audited)               │   │
  │  └─────────────────────────────────────────────────────────────┘   │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘


  THE BUSINESS PROBLEMS:

  ┌──────────────────────────────────────────────────────────────┐
  │  $124T wealth transfer ──► 100,000 advisor shortage          │
  │  Advisor spends 18 hrs/wk on prep ──► agent compresses to min│
  │  Goldman: 11% analyst cuts ──► cover 40 stocks, not 15       │
  │  KYC: $3,500/client ──► $500/client (70% reduction)          │
  │  FINRA 2026: audit AI agents like employees ──► built-in     │
  └──────────────────────────────────────────────────────────────┘


  5 DIFFERENTIATORS:

  ┌──┬──────────────────────────────────────────────────────────────────┐
  │1 │ CRM-CONNECTED RESEARCH                                          │
  │  │ Knows your clients, their holdings, coverage history.            │
  │  │ Brief is personalized to the client book, not generic.           │
  ├──┼──────────────────────────────────────────────────────────────────┤
  │2 │ COMPLIANCE-NATIVE                                                │
  │  │ HITL gates, MNPI filtering, restricted list, trading windows.    │
  │  │ Built in from day one, not bolted on.                            │
  ├──┼──────────────────────────────────────────────────────────────────┤
  │3 │ ACTION EXECUTION (Phase 6)                                       │
  │  │ Submit trades, initiate wires, run KYC, open accounts.           │
  │  │ All with HITL approval. No research platform does this.          │
  ├──┼──────────────────────────────────────────────────────────────────┤
  │4 │ CHANNEL REACH (12+)                                              │
  │  │ WhatsApp at 6am: "prep me for Henderson" → personalized brief.   │
  │  │ Agentforce: ~5 channels. 006: 12+.                              │
  ├──┼──────────────────────────────────────────────────────────────────┤
  │5 │ NO VENDOR LOCK-IN                                                │
  │  │ OpenClaw is MIT. MCP servers, models, SF objects all portable.   │
  │  │ Swap the runtime in 2 years, everything survives.                │
  └──┴──────────────────────────────────────────────────────────────────┘


  WHEN NOT TO CONSIDER 006:

  ┌─────────────────────────────────────────────────────────────────────┐
  │  Only need research (no CRM) ──► buy AlphaSense / Brightwave       │
  │  Pure Salesforce shop ──► 005 (Agentforce) is simpler              │
  │  No team for 4 platforms ──► operational complexity is real         │
  │  Need production tomorrow ──► 006 is a prototype                   │
  └─────────────────────────────────────────────────────────────────────┘


  006 vs ALTERNATIVES:

  ┌──────────────────────┬──────────┬──────────┬──────────┐
  │ Capability           │AlphaSense│ 005 (AF) │ 006 (OC) │
  ├──────────────────────┼──────────┼──────────┼──────────┤
  │ SEC filing analysis  │   Yes    │   Yes    │   Yes    │
  │ Financial modeling   │ Partial  │   Yes    │   Yes    │
  │ CRM-connected        │    No    │   Yes    │   Yes    │
  │ Compliance screening │    No    │   Yes    │   Yes    │
  │ Audit trail (FINRA)  │    No    │   Yes    │   Yes    │
  │ Action execution     │    No    │    No    │   Yes    │
  │ 12+ channels         │    No    │    No    │   Yes    │
  │ 23-stage pipeline    │    No    │    No    │   Yes    │
  │ Cross-run learning   │    No    │    No    │   Yes    │
  │ Anti-fabrication     │ Partial  │    No    │   Yes    │
  │ Production-ready     │   Yes    │ Prototype│ Prototype│
  └──────────────────────┴──────────┴──────────┴──────────┘


═══════════════════════════════════════════════════════════════════════════════
 HOW READY IS 006?
═══════════════════════════════════════════════════════════════════════════════

  TASK SCORECARD (71 design tasks):

  ┌──────────────────┬───────┬──────┬─────────┬──────────┬──────────┐
  │ Phase            │ Tasks │ Done │ Partial │ Not Done │ Deviated │
  ├──────────────────┼───────┼──────┼─────────┼──────────┼──────────┤
  │ 1 Foundation     │  12   │   8  │    1    │    3     │    0     │
  │ 2 MCP Servers    │   8   │   8  │    0    │    0     │    0     │
  │ 3 Pipeline       │  12   │   8  │    2    │    0     │    2     │
  │ 4 Models         │  10   │   8  │    0    │    0     │    2     │
  │ 5 Production     │  14   │  10  │    0    │    4     │    0     │
  │ 6 MuleSoft       │  15   │   0  │    0    │   15     │    0     │
  ├──────────────────┼───────┼──────┼─────────┼──────────┼──────────┤
  │ TOTAL            │  71   │  42  │    3    │   22     │    4     │
  │                  │       │ 59%  │   4%    │  31%     │   6%     │
  └──────────────────┴───────┴──────┴─────────┴──────────┴──────────┘


  WHAT'S SOLID (working locally):

  ┌─────────────────────────────────────────────────────────────────────┐
  │  ████████████████████████████████████████ MCP Servers (8/8)        │
  │  ██████████████████████████████████░░░░░░ Pipeline (8/12)          │
  │  ████████████████████████████████░░░░░░░░ Models (8/10)            │
  │  ██████████████████████████░░░░░░░░░░░░░░ Foundation (8/12)        │
  │  ████████████████████████████░░░░░░░░░░░░ Production (10/14)       │
  │  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ MuleSoft (0/15)          │
  └─────────────────────────────────────────────────────────────────────┘
   ████ = done    ░░░░ = not done


  SECURITY FINDINGS:

  ┌──────────────────────────────────────────────────────────────┐
  │  Resolved:  ████████░░░░░░░  8 of 15                        │
  │  Mitigated: █░░░░░░░░░░░░░░  1 (prompt injection)           │
  │  Open:      █████░░░░░░░░░░  5 (MEDIUM + LOW severity)      │
  │  N/A:       █░░░░░░░░░░░░░░  1 (memory encryption)          │
  └──────────────────────────────────────────────────────────────┘


  READINESS BY USE CASE:

  ┌─────────────────────────────────────────────────────────────────────┐
  │                                                                     │
  │  DEMO / POC                                                         │
  │  ████████████████████████████████████░░░░░░░░░░░░  ~75%            │
  │  Core loop works. Show to stakeholders today.                       │
  │                                                                     │
  │  PILOT (real users)                                                 │
  │  ██████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░  ~45%            │
  │  Need: channel tokens, eval baselines, AgentCore verified.          │
  │                                                                     │
  │  PRODUCTION (regulated firm)                                        │
  │  ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  ~25%            │
  │  Need: MuleSoft (15 tasks), eval at scale, perf baselines,          │
  │        FSC license, self-hosted Langfuse, security hardening.       │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘


  WHERE THE GAPS LIVE:

  ┌─────────────────────────────────────────────────────────────────────┐
  │                                                                     │
  │  DATA LAYER (MCP + Salesforce)        ██████████████████  BUILT     │
  │                                                                     │
  │  ANALYSIS LAYER (pipeline + models)   ████████████████░░  MOSTLY    │
  │                                                                     │
  │  INTEGRATION LAYER (channels,         ████████░░░░░░░░░░  GAPS      │
  │   AgentCore, MuleSoft)                                              │
  │                                                                     │
  │  HARDENING LAYER (eval, perf,         ████░░░░░░░░░░░░░░  GAPS      │
  │   security, rotation)                                               │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘


  REMAINING WORK BY PRIORITY:

  ┌─── CRITICAL PATH (blocks production) ──────────────────────────────┐
  │  1. Full 23-stage pipeline end-to-end run with real HITL gates     │
  │  2. Run full 150-query eval suite and establish baselines          │
  │  3. Record performance measurements                                │
  │  4. Close remaining open security findings                         │
  └────────────────────────────────────────────────────────────────────┘

  ┌─── HIGH PRIORITY (design spec gaps) ───────────────────────────────┐
  │  5. Slack integration with real tokens + notification delivery      │
  │  6. WhatsApp + Telegram with real API tokens                       │
  │  7. All 15 MuleSoft tasks (requires Anypoint Platform access)      │
  │  8. FSC objects on org (requires FSC license)                      │
  └────────────────────────────────────────────────────────────────────┘

  ┌─── MEDIUM PRIORITY (hardening) ────────────────────────────────────┐
  │  9.  Deploy secrets rotation Lambda via CloudFormation             │
  │  10. Deploy Bedrock Guardrails and verify                          │
  │  11. Redeploy AgentCore with SESSION_MEMORY + pipeline hooks       │
  └────────────────────────────────────────────────────────────────────┘


  DESIGN DEVIATIONS:

  ┌─────────────────────────────────────────────────────────────────────┐
  │                                                                     │
  │  DESIGN SAID                    REALITY                             │
  │  ─────────────────────────────  ──────────────────────────────────  │
  │  Fork AutoResearchClaw          Custom 1,400-line pipeline.py       │
  │  HITL gates at 5, 8, 9, 17, 20 HITL gates at 7, 13, 21            │
  │  Standalone sentiment skill     Inline LLM calls (correct choice)  │
  │  salesforce-api official skill  Inline HTTP requests.get()          │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘


  REPRODUCIBILITY:

  ┌──────────────────────────────────────────────────────────────┐
  │  git clone                          ✓ Ready                  │
  │  sf org create scratch              ✓ Ready                  │
  │  sf project deploy start            ✓ Ready                  │
  │  sf apex run (5 seed scripts)       ✓ Ready                  │
  │  sam deploy --guided                ✓ Ready                  │
  │  ./scripts/aws/setup-secrets.sh     ✓ Ready (auto-populates) │
  │  aws cloudformation deploy (guard.) ✓ Ready (template)       │
  │  aws cloudformation deploy (rotat.) ✓ Ready (template)       │
  │  agentcore deploy                   ✓ Ready                  │
  │  cd frontend && npm install         ✓ Ready                  │
  │  python run_suite.py                ✓ Ready (needs env vars) │
  │  python test-pipeline.py            ✓ Ready (needs env vars) │
  │                                                              │
  │  Missing: no single "deploy all" script. Manual orchestration│
  └──────────────────────────────────────────────────────────────┘


  THE HONEST SUMMARY:

  ┌─────────────────────────────────────────────────────────────────────┐
  │                                                                     │
  │  42 of 71 tasks done.                                               │
  │  22 not done — 15 of those are MuleSoft (external dependency).      │
  │                                                                     │
  │  Data + Analysis layers:  BUILT                                     │
  │  Integration + Hardening: GAPS                                      │
  │                                                                     │
  │  Demo-ready today. Pilot-ready with channel tokens + eval run.      │
  │  Production-ready after MuleSoft, FSC, perf baselines, security.    │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘
```


---

## 5. Can This Achieve 100% Accuracy?

No. Not with 100% accuracy. And anyone who says otherwise is selling something.

Here's why, broken down by each link in the chain:

### Research → 100% accuracy is impossible

LLMs hallucinate. That's not a bug that gets patched — it's a fundamental property of how probabilistic language models work. 006 mitigates this with anti-fabrication (every number must trace to a tool result), but the synthesis stages (thesis, catalysts, risks, rating) are LLM-generated text. The LLM might misweight a risk factor, miss a nuance in a 10-K footnote, or generate a thesis that sounds compelling but has a logical gap. The financial models (DCF, Monte Carlo) are mathematically deterministic given inputs, but the inputs themselves come from market data APIs that can lag, have gaps, or return stale data. Alpha Vantage free tier data is 15 minutes delayed. SEC EDGAR filings can take hours to appear after submission.

### Client data → accuracy depends on the CRM

Salesforce is the source of truth for client data, but CRM data is only as good as what humans put in. If an advisor didn't update a client's risk profile, or a holdings record is stale because a custodian feed lagged, the agent works with wrong data confidently. The agent can't know what it doesn't know. SOQL queries return what's in the database — garbage in, garbage out.

### Compliance → closest to deterministic, but still not 100%

Restricted list checks are binary lookups — either the ticker is on the list or it isn't. Trading window checks are date math. These can be 100% accurate. But MNPI detection is judgment-based. The 30-day lookback in 006's compliance screening is a heuristic — MNPI restrictions actually persist until public disclosure, which could be 6 months. A real compliance system needs human-maintained disclosure tracking, not a time-based query. Concentration limits depend on accurate portfolio data (see CRM accuracy above).

### Execution → accuracy is the wrong frame

Trade execution isn't about accuracy — it's about correctness of intent and market conditions. You can submit a perfectly accurate order that fills at a bad price because the market moved. Wire transfers can fail due to receiving bank issues. KYC screening depends on sanctions databases that update asynchronously. The HITL gates in 006 exist precisely because execution can't be autonomous — a human must verify intent before irreversible actions.

### Channel reach → this one actually works

Message delivery across Slack, WhatsApp, Telegram is reliable (99.9%+ delivery rates from the platform providers). This is the one link where near-100% is achievable because it's infrastructure, not intelligence.

### What "accuracy" actually means in this context

The right question isn't "can we get 100% accuracy" — it's "can we get high enough accuracy with sufficient guardrails that the system is safer than the human-only process it replaces?"

Consider what happens today without the agent:
- Analysts manually copy numbers from SEC filings into spreadsheets (transcription errors)
- Advisors prep for meetings from memory and stale notes (recency bias, omissions)
- Compliance reviews are manual and sample-based, not exhaustive (coverage gaps)
- Trade orders are phoned in or manually entered (fat finger errors)

The human process isn't 100% accurate either. It's maybe 85-95% accurate with significant variance based on workload, fatigue, and experience.

### What's achievable with this architecture

| Link | Realistic Accuracy | Why Not Higher |
|------|-------------------|----------------|
| Data retrieval (MCP tools) | 98-99% | API availability, rate limits, data lag |
| CRM queries | 99%+ | Deterministic SOQL, but depends on data quality |
| Financial models (DCF, MC) | Deterministic given inputs | Inputs are estimates — model is precise, assumptions aren't |
| LLM synthesis (thesis, rating) | 75-85% | Probabilistic by nature, mitigated by anti-fabrication |
| Compliance checks (binary) | 99%+ | Restricted list, trading window are lookups |
| Compliance checks (judgment) | 85-90% | MNPI detection, suitability are fuzzy |
| Execution (with HITL) | 99%+ | Human approves, system executes correctly |
| Channel delivery | 99.9% | Platform infrastructure |
| End-to-end (full chain) | 80-90% | Weakest link is LLM synthesis |

### The architecture's answer to the accuracy problem

006 doesn't try to be 100% accurate. It tries to be auditable, correctable, and human-supervised at the right moments:

1. Anti-fabrication ledger — every number traces to a source, so you can verify
2. HITL gates at stages 7, 13, 21 — human checks data, models, and final output
3. Dual audit trail — Langfuse + IR_Audit_Log__c, so every decision is explainable
4. MetaClaw learning — the system improves over time from its own failures
5. Compliance screening — binary checks are deterministic, judgment calls are flagged for humans

The goal is not perfection. The goal is "better than the manual process, with a paper trail."

---

## 6. Where Does the Value Lie? Why Will FSI Pay?

### The value is NOT "better research"

AlphaSense, Brightwave, and Bloomberg Terminal already do research well. An FSI firm isn't going to pay for another research tool.

### The value is TIME

That's it. Everything else is a derivative of time.

An equity research analyst spends ~70% of their time gathering data and formatting it. That's a $250K-$400K/year person spending 28 hours a week on work a pipeline can do in minutes. If you give them back even half of that, they go from covering 15 stocks to covering 30. Same headcount, double the output. At a sell-side firm where each stock covered generates $200K-$500K in commission revenue, that's $3M-$7.5M in incremental revenue per analyst.

A wealth advisor spends 45-90 minutes prepping for each client meeting. With 150-200 clients and quarterly reviews, that's 150-300 hours/year on meeting prep alone. Compress that to 5-10 minutes per meeting and you free up 125-275 hours/year per advisor. That's 6-13 weeks of capacity. An advisor managing $200M AUM generating 75bps in fees produces $1.5M/year. If the freed time lets them take on 20% more clients, that's $300K in incremental revenue per advisor.

A compliance team manually reviews every trade recommendation, every research brief, every client communication for MNPI, restricted list violations, and suitability. At a mid-size broker-dealer, that's 3-5 compliance officers at $150K-$200K each doing work that's 60% pattern matching. Automate the pattern matching, keep the humans for judgment calls, and you either cut headcount by 1-2 or (more likely) handle 3x the volume with the same team as the firm grows.

KYC onboarding: $1,500-$3,500 per client, 3-5 days elapsed time. Automate the low-risk 70% and it drops to $500 and 30 seconds. For a firm onboarding 1,000 clients/year, that's $1M-$2M in savings.

### Where the money specifically comes from

The firm doesn't pay for "an AI agent." They pay for one of these outcomes:

1. **Revenue per analyst goes up.** More stocks covered = more research published = more commission revenue. This is the sell-side pitch. The buyer is the head of equity research.

2. **AUM per advisor goes up.** More clients served with the same quality = more assets under management = more fee revenue. This is the wealth management pitch. The buyer is the head of wealth advisory.

3. **Compliance cost per action goes down.** Automated screening + audit trail + HITL gates = fewer compliance officers needed per dollar of AUM, or same team handles growth. This is the COO/CCO pitch.

4. **Client attrition goes down.** The $124T wealth transfer means heirs are choosing new advisors. The advisor who responds to a WhatsApp message at 6am with a personalized portfolio brief keeps the client. The one who says "let me get back to you after I pull up your file" loses them. This is the hardest to quantify but the most strategic. The buyer is the CEO worried about the next decade.

### Why they'd pay for 006 specifically

Because no commercial product closes the full loop. You can buy AlphaSense for research. You can buy Salesforce for CRM. You can buy a compliance tool. You can use MuleSoft for execution. But stitching them together into a single agent workflow where the research knows about the client, the compliance check happens before the recommendation, and the trade executes with one approval — that integration doesn't exist as a product.

The firm pays for the integration, not the components.

### What they'd actually pay

Realistically, this is a build-not-buy play for large firms (Tier 1-2 banks, $500B+ AUM wealth managers, large broker-dealers). They'd fund an internal team to build and maintain it. The cost is 4-6 engineers for 6-12 months ($1.5M-$3M build cost) plus $500K-$1M/year to operate. The ROI math works if it saves even 2-3 analyst FTEs or enables 10-15 advisors to each take on 20% more clients.

For mid-market firms, this would need to be productized — a managed service or SaaS offering where someone else runs the infrastructure. That's a different business model and 006 isn't there yet.

### The honest risks to the value proposition

The biggest risk isn't technical — it's adoption. Analysts and advisors are creatures of habit. If the agent produces a brief that's 90% as good as what the analyst writes manually, some analysts will reject it because it's not their voice, their structure, their judgment. The HITL co-pilot model (analyst steers, agent executes) is designed to address this, but cultural resistance in FSI is real and shouldn't be underestimated.

The second risk is regulatory uncertainty. FINRA 2026 says "supervise AI agents like employees" but doesn't specify exactly how. A firm that builds this and then gets examined might find the examiner has a different interpretation of "adequate supervision" than what the HITL gates provide. The audit trail helps, but regulatory risk is non-zero.

### Bottom line

The value is real, quantifiable, and large enough to justify the build cost — but only for firms big enough to absorb the engineering investment and brave enough to bet on the adoption curve. The firms that move first get a 2-3 year head start on advisor productivity that compounds as the wealth transfer accelerates.
