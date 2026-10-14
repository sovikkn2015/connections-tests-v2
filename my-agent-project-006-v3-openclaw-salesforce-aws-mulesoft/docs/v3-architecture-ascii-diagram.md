# 006 V3 — Full System Architecture (ASCII Diagram)

> **Date:** 2026-05-02
> **Scope:** Designed vs Built vs Deployed vs Live — every layer, every integration, every isolation boundary.

```
╔══════════════════════════════════════════════════════════════════════════════════╗
║                    006 V3 — FULL SYSTEM ARCHITECTURE                           ║
║                    Designed vs Built vs Deployed                                ║
╚══════════════════════════════════════════════════════════════════════════════════╝


═══════════════════════════════════════════════════════════════════════════════════
 LAYER 1 — FRONTEND V6 (CloudFront d2zs9nk4uc2dbx.cloudfront.net)
═══════════════════════════════════════════════════════════════════════════════════

  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
  │  SARAH (Research)   │  │  MARCUS (Advisor)    │  │  ELEANOR (Client)   │
  │  ResearchTerminalV6 │  │  AdvisorWorkbenchV6  │  │  ClientChannelV6    │
  │                     │  │                      │  │                     │
  │ ✅ Query bar+Cmd-↵  │  │ ✅ Conversation col  │  │ ✅ WhatsApp phone   │
  │ ✅ Brief streaming  │  │ ✅ HITL ActionCard   │  │ ✅ Bubbles+composer │
  │ ✅ Citation chips   │  │ ✅ 7-gate tracker    │  │ ✅ 3-button card    │
  │ ✅ Citation drawer  │  │ ✅ Queue tabs (3)    │  │ ✅ Persistent thread│
  │ ✅ Running chips    │  │ ✅ Client 360+IPS    │  │ ✅ 2 CTAs           │
  │ ✅ Market pane      │  │ ✅ queue_update live │  │ ✅ Disclaimer bar   │
  │ ✅ Filings pane     │  │ ✅ Approve/Reject    │  │ ✅ Trust spine      │
  │ ✅ Sentiment pane   │  │ ✅ Trust spine       │  │ ❌ RM reply inbound │
  │ ✅ Demand signals   │  │ 🟡 Holdings = "—"   │  │                     │
  │ ❌ PDF drag-drop    │  │                      │  │                     │
  │ 🟡 Sentiment chart  │  │                      │  │                     │
  └─────────┬───────────┘  └──────────┬───────────┘  └──────────┬──────────┘
            │                         │                          │
            └─────────────┬───────────┘──────────────────────────┘
                          │
                    useAgentSocket (WebSocket)
                    useStreamingTurn (events: turn_start, turn_chunk,
                      turn_end, hitl_prompt, gate_event, queue_update)
                          │
                          ▼

═══════════════════════════════════════════════════════════════════════════════════
 LAYER 2 — API GATEWAY + AGENT PROXY (us-east-1)
═══════════════════════════════════════════════════════════════════════════════════

  ┌───────────────────────────────────────────────────────────────────────────┐
  │  API Gateway  e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3         │
  │                                                                          │
  │  /agent/invoke  ──► agent-proxy Lambda ──► AgentCore v35 (Bedrock)      │
  │  /agent/approve ──► agent-proxy Lambda ──► gates 4-7 (deterministic)    │
  │  /api/session/warm                                                       │
  │  /api/source_chunk/{id}                                                  │
  │  /mcp/market-data/tools/{list,call}                                      │
  │  /mcp/sec-edgar/tools/{list,call}                                        │
  │  /mcp/news-search/tools/{list,call}                                      │
  │  /mcp/salesforce-crm/tools/{list,call}                                   │
  │  /mcp/mulesoft-actions/tools/{list,call}                                 │
  └───────────────────────────────────────────────────────────────────────────┘
                          │
                          ▼

═══════════════════════════════════════════════════════════════════════════════════
 LAYER 3 — OPENCLAW ON AGENTCORE (the agent PLATFORM)
═══════════════════════════════════════════════════════════════════════════════════

  ┌───────────────────────────────────────────────────────────────────────────┐
  │                                                                          │
  │   PersonaCoordinator.run_turn(query, ctx)                                │
  │       │                                                                  │
  │       ├── orchestrator_for_persona(ctx.persona)                          │
  │       │       │                                                          │
  │       │       ├── "fsi_research"  → ResearchOrchestratorImpl             │
  │       │       ├── "fsi_advisor"   → AdvisorOrchestratorImpl              │
  │       │       └── "fsi_client"    → LiaisonOrchestratorImpl              │
  │       │                                                                  │
  │       ├── plan()   → List[OrchestratorDispatch]                          │
  │       ├── fanout() → asyncio.gather (parallel) OR serial                 │
  │       └── synthesize() → cited brief / response                          │
  │                                                                          │
  └───────────────────────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────────────────┐
          ▼               ▼                           ▼

  ┌─── RESEARCH ────────────────┐  ┌─── ADVISOR ──────────────────────────┐
  │ research_orchestrator       │  │ advisor_orchestrator                  │
  │   │                         │  │   │                                   │
  │   ├─► market_specialist ────┤  │   ├─► portfolio_specialist            │
  │   │   [mcp_invoke]         │  │   │   [portfolio_analytics,            │
  │   │   MCP: market-data     │  │   │    scenario_modeling]              │
  │   │   ✅ Finnhub live      │  │   │   ✅ pure Python                   │
  │   │                         │  │   │                                   │
  │   ├─► filings_specialist ──┤  │   ├─► suitability_specialist           │
  │   │   [mcp_invoke]         │  │   │   [suitability_check]              │
  │   │   MCP: sec-edgar       │  │   │   ✅ deterministic PASS/FAIL       │
  │   │   ✅ 784 KB chunks     │  │   │                                   │
  │   │                         │  │   ├─► client_context_specialist        │
  │   ├─► sentiment_specialist ┤  │   │   [client_summary,                 │
  │   │   [mcp_invoke]         │  │   │    research_awareness]             │
  │   │   MCP: news-search     │  │   │   ✅ MNPI-filtered                 │
  │   │   ✅ Tavily live       │  │   │                                   │
  │   │                         │  │   └─► action_specialist ◄── SERIAL    │
  │   ├─► compliance_specialist┤  │       [compliance_screening,           │
  │   │   [compliance_screening]│  │        hitl, dual_auth,               │
  │   │   ✅ ALLOW/DENY        │  │        mulesoft_api, audit_logging]    │
  │   │                         │  │       ✅ 7-GATE WRITE PATH            │
  │   └─► statement_specialist ┤  │                                        │
  │       [financial_statement_ │  └────────────────────────────────────────┘
  │        analysis]            │
  │       ✅ XBRL + Python     │  ┌─── LIAISON ────────────────────────────┐
  │                             │  │ liaison_orchestrator (HAIKU)           │
  │  asyncio.gather ═══════╗   │  │   │                                    │
  │  4 specialists parallel║   │  │   ├─► faq_specialist (HAIKU)           │
  │  16s total (not 60s+)  ║   │  │   │   tools: NONE  mcp: NONE          │
  │  ════════════════════════   │  │   │   ✅ strongest isolation           │
  └─────────────────────────────┘  │   │                                    │
                                   │   └─► context_specialist               │
                                   │       [client_summary]                 │
                                   │       ✅ MNPI-filtered reads           │
                                   └────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════════
 LAYER 4 — 7-GATE TRUST SPINE (action_specialist, serial_by_design=True)
═══════════════════════════════════════════════════════════════════════════════════

  Query: "Trim Patel META from 6.8% to 4.5%, VWAP, US open"

  ①──────────►②──────────►③──────────►④──────────►⑤──────────►⑥──────────►⑦
  Guardrails   MNPI        Compliance  HITL        Dual-Auth   MuleSoft    Audit
  (Bedrock)    Filter      Screening   Approve     2nd Laptop  Write       Row
                                       ⌘↵                      ▼
  ✅ live      ✅ live     ✅ live     ✅ live     ✅ code     🟡 mock     ✅ live
                                                                │
  Code-enforced by run_tool_loop(). LLM cannot skip a gate.    │
  Non-recoverable error at any gate → chain stops, audit writes.│
                                                                ▼
                                                    ┌──────────────────┐
                                                    │ Alpaca Paper     │
                                                    │ (submit-order)   │
                                                    │ Dwolla Sandbox   │
                                                    │ (initiate-wire)  │
                                                    │ 🟡 mock mode     │
                                                    │ CloudHub pending │
                                                    └──────────────────┘


═══════════════════════════════════════════════════════════════════════════════════
 LAYER 5 — 16 SKILLS
═══════════════════════════════════════════════════════════════════════════════════

  ┌─────────────────────────────────────────────────────────────────────────┐
  │                                                                         │
  │  RESEARCH PATH (read)          WRITE PATH (7-gate)    SHARED            │
  │  ─────────────────────         ──────────────────     ──────            │
  │  ✅ publish_brief              ✅ compliance_screen   ✅ audit_logging  │
  │  ✅ rag_retrieve (hybrid)      ✅ hitl (HMAC tokens)  ✅ mcp_invoke    │
  │  ✅ financial_stmt_analysis    ✅ dual_auth            ✅ client_summary│
  │  ✅ research_awareness         🟡 mulesoft_api (mock) ✅ rm_handoff    │
  │  ✅ portfolio_analytics                                                 │
  │  ✅ scenario_modeling          COMPLIANCE              STUB             │
  │  ✅ suitability_check          ✅ compliance_screening 🟡 compliance_  │
  │                                                           sweep        │
  │  All skills: Pydantic v2 input validation, async, MNPI-aware           │
  │  Fail-closed: tool_not_allowed returned to LLM on unauthorized call    │
  └─────────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════════
 LAYER 6 — MCP SERVERS (6 external-facing Lambdas)
═══════════════════════════════════════════════════════════════════════════════════

  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │ market-data  │  │ sec-edgar    │  │ news-search  │
  │              │  │              │  │              │
  │ get_quote    │  │ get_filing   │  │ search_news  │
  │ get_history  │  │ kb_retrieve  │  │ score_sent.  │
  │ get_technics │  │              │  │              │
  │              │  │              │  │              │
  │ ✅ Finnhub   │  │ ✅ EDGAR API │  │ ✅ Tavily    │
  │ ✅ AlphaVant │  │ ✅ Bedrock KB│  │ ✅ Bedrock   │
  └──────────────┘  └──────────────┘  └──────────────┘

  ┌──────────────────────────────┐  ┌──────────────────────────────┐
  │ salesforce-crm (12 tools)    │  │ mulesoft-actions (5 tools)   │
  │                              │  │                              │
  │ query_soql                   │  │ submit_order                 │
  │ get/create/update_object     │  │ cancel_order                 │
  │ write_audit_log              │  │ modify_order                 │
  │ write_research_brief         │  │ initiate_wire                │
  │ write_pending_approval       │  │ order_status_webhook         │
  │ read_household_summary       │  │                              │
  │ read_household_positions     │  │ 🟡 mock mode                 │
  │ read_research_briefs_w_exp   │  │ ✅ OFAC SDN non-bypassable   │
  │                              │  │                              │
  │ ✅ MNPI field redaction      │  └──────────────────────────────┘
  │   (shares, mkt_val, cost)    │
  │ ✅ Per-user OBO via          │
  │   sf-auth-proxy JWT Bearer   │
  └──────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════════
 LAYER 7 — DATA + TRUST + OBSERVABILITY
═══════════════════════════════════════════════════════════════════════════════════

  ┌─── SALESFORCE (system of record) ──────────────────────────────────────┐
  │                                                                         │
  │  Research_Brief__c ◄── Sarah writes, Marcus reads (DLM join)           │
  │    ✅ 8+ rows, Published_At__c set, RM_Consumable=true                 │
  │                                                                         │
  │  IR_Audit_Log__c ◄── ALL personas write                                │
  │    ✅ 5 rows with Agent_Id, Session_Id, Principal_Id cross-stitch      │
  │                                                                         │
  │  Client_Inquiry__c ◄── Eleanor writes via rm_handoff                   │
  │    ✅ rows from client turns                                            │
  │                                                                         │
  │  IR_Pending_Approval__c ◄── dual_auth writes                           │
  │    ✅ code-verified                                                     │
  │                                                                         │
  │  FSC Sharing Rules ──► per-RM book isolation (enforced by SF natively)  │
  └─────────────────────────────────────────────────────────────────────────┘

  ┌─── AWS (compute + data) ───────────────────────────────────────────────┐
  │                                                                         │
  │  Bedrock AgentCore v35 ──── ✅ READY, container rebuilt                │
  │  Bedrock Sonnet 4.5 ─────── ✅ 16s research turns                     │
  │  Bedrock Haiku 4.5 ──────── ✅ 8.5s advisor drafts                    │
  │  Bedrock Guardrails ─────── ✅ GuardrailInterventionError on block     │
  │  Bedrock KB (784 chunks) ── ✅ retrieve API returns real filings       │
  │  Aurora pgvector + RLS ──── ✅ per-principal row-level security        │
  │  11 Lambda functions ────── ✅ all deployed                            │
  │  API Gateway (13 routes) ── ✅ all responsive                          │
  │  CloudFront ─────────────── ✅ V6 bundle live                          │
  └─────────────────────────────────────────────────────────────────────────┘

  ┌─── TRUST ──────────────────────────────────────────────────────────────┐
  │                                                                         │
  │  MNPI Filter ──── regex scrub on all client output + LLM re-scrub      │
  │  Gate Enforcer ── fail-closed tool_allowlist + mcp_allowlist per agent  │
  │  HITL Tokens ──── HMAC-SHA256, 5-min TTL, single-use, plan_hash bind  │
  │  Dual-Auth ────── distinct approver enforced (Pydantic frozen=True)    │
  │  OFAC SDN ─────── non-bypassable screen before wire                    │
  │  IdP Session ──── HMAC session tokens (dev-bootstrap for demo)         │
  └─────────────────────────────────────────────────────────────────────────┘

  ┌─── LANGFUSE (observability) ───────────────────────────────────────────┐
  │                                                                         │
  │  _ScrubbingLangfuseWrapper ── recursive MNPI + PII + token scrub       │
  │  Span per: converse call, skill invocation, MCP call, gate             │
  │  Cost attribution by persona, user, skill                              │
  │  Trace replay as audit artifact                                         │
  └─────────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════════
 CROSS-PERSONA HANDOFFS (Salesforce is the exchange — no agent-to-agent)
═══════════════════════════════════════════════════════════════════════════════════

  SARAH                        MARCUS                       ELEANOR
  (research)                   (advisor)                    (client)
     │                            │                            │
     │  publish_brief             │                            │
     │──► Research_Brief__c ─────►│ queue_update (briefs)      │
     │    Platform Event fires    │ "4 households hold META"   │
     │                            │                            │
     │                            │                            │  "worried
     │                            │◄── queue_update (alerts) ──│   about
     │                            │    Client_Inquiry__c       │   META"
     │                            │                            │
     │◄── Research_Request__c ────│                            │
     │    demand signal           │                            │
     │    (reverse flow)          │                            │
     │                            │                            │
     │                            │──► ❌ RM reply to client   │
     │                            │    (not yet wired)         │


═══════════════════════════════════════════════════════════════════════════════════
 DATA ISOLATION
═══════════════════════════════════════════════════════════════════════════════════

  INTRA-RM (RM A can't see RM B's clients):

    Browser ──► API Gateway ──► agent-proxy ──► AgentCore
                                    │
                              X-Principal-Id: "marcus"
                                    │
                                    ▼
                              sf-auth-proxy
                              JWT Bearer grant
                              sub=marcus@firm.com
                                    │
                                    ▼
                              Salesforce
                              sharing rules enforce
                              Marcus sees ONLY his book
                              RM B's clients invisible


  INTER-PERSONA (client can't see raw research):

    ┌─────────────────────────────────────────────────────┐
    │  faq_specialist                                      │
    │    tools: []          ◄── ZERO tools                 │
    │    mcp: []            ◄── ZERO MCP access            │
    │    memory: READ_ONLY  ◄── can't write anything       │
    │                                                      │
    │  Can only respond from Haiku pretrained knowledge.   │
    │  Cannot call Salesforce. Cannot read positions.      │
    │  Cannot access research briefs. Cannot recommend.    │
    │  This is ARCHITECTURAL isolation, not prompt-based.  │
    └─────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────┐
    │  salesforce-crm MCP (_mnpi_redact.py)               │
    │                                                      │
    │  BEFORE any record leaves the Lambda:                │
    │    shares_held    → [REDACTED:mnpi]                  │
    │    market_value   → [REDACTED:mnpi]                  │
    │    cost_basis     → [REDACTED:mnpi]                  │
    │    wire_amount    → [REDACTED:mnpi]                  │
    │    beneficiary_ac → [REDACTED:mnpi]                  │
    │                                                      │
    │  The LLM never sees dollar amounts or share counts.  │
    │  It works in percentages and bands.                  │
    └─────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════════
 RAG PIPELINE (Advanced Hybrid Retrieval)
═══════════════════════════════════════════════════════════════════════════════════

  SEC EDGAR ──► XBRL Parser ──► Section-Aware Chunker ──► Bedrock KB
                                     │
                                     ├── Item 1A (Risk Factors)
                                     ├── Item 7 (MD&A)
                                     ├── Financial Tables
                                     └── 784 chunks indexed

  Query arrives at rag_retrieve skill:
     │
     ├──► BM25 Lexical Search (_bm25.py)
     │    keeps ticker/CUSIP honest ("GS" ≠ "Goldman Sachs")
     │
     ├──► Dense Titan v2 Embeddings (_dense.py)
     │    semantic recall across filing sections
     │
     └──► Reranker (_rerank.py)
          collapses top-30 → top-5
          │
          ▼
     source_chunk_ids returned for citation enforcement


═══════════════════════════════════════════════════════════════════════════════════
 SCORECARD — DESIGNED vs BUILT vs DEPLOYED vs LIVE
═══════════════════════════════════════════════════════════════════════════════════

  Agents:          14 designed │ 14 built │ 14 deployed │ 14 live
  Skills:          16 designed │ 16 built │ 16 deployed │ 14 live (2 mock/stub)
  MCP servers:      6 designed │  6 built │  6 deployed │  5 live (mulesoft mock)
  Narratives:       5 designed │  3 live  │  2 slide    │  3 verified
  Auth boundaries:  6 designed │  5 built │  5 deployed │  4 live (IdP deferred)
  Trust gates:      7 designed │  7 built │  7 deployed │  6 live (mulesoft mock)
  SF SObjects:      5 designed │  5 built │  5 deployed │  3 with rows
  Tests:                       │ 389 pass │             │ 389 pass
  Smoke test:                  │          │             │ 10/10

  ┌──────────────────────────────────────────────────────────────────────┐
  │  OVERALL: 90% of the designed system is live and verified.           │
  │  The 10% gap: MuleSoft CloudHub (3h), IdP (1d), CDC pipeline (1d), │
  │  compliance_sweep stub (2d), RM→client reply (2d).                  │
  └──────────────────────────────────────────────────────────────────────┘
```
