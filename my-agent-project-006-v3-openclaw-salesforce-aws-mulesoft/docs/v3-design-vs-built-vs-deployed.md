# 006 V3 — Design vs Built vs Deployed

> **Date:** 2026-04-29 (assessment taken ~11:08 UTC)
> **Method:** live AWS probes + code read + live Salesforce queries + live MCP tool calls, cross-checked against `v3-narrative-arc.md` + `v3-build-status.md`
> **Scope change since last report:** significant. The deploy layer has moved forward by multiple orders of magnitude in the last few hours. Reassessment was required.

---

## 1. Executive summary — three-layer scorecard

| Layer | What it means | Grade | Delta since last check |
|---|---|---|---|
| **Design** | What the narrative arc + build status promise | 🟢 95% coherent | unchanged |
| **Built** | What exists in the repo as runnable code | 🟢 90% real | unchanged |
| **Deployed** | What's actually live in AWS + Salesforce + MuleSoft | 🟢 **~75% live** (was ~20% six hours ago) | **major forward progress** |

**One-line status:** the v3 stack has gone from "code exists, deploy blocked" to **"most of the stack is live, real Bedrock talking to real Finnhub talking to real KB talking to real Salesforce via real OBO"** inside a single work session. The remaining gaps are narrower and mostly cosmetic or narrative-completeness.

---

## 2. Live state snapshot (verified now, not from docs)

### AWS CloudFormation — all five v3 stacks deployed

```
Openclaw006V3-Vpc           CREATE_COMPLETE   2026-04-29 05:50 UTC
Openclaw006V3-Aurora        CREATE_COMPLETE   2026-04-29 08:50 UTC   ← was rolling back
Openclaw006V3-Kb            CREATE_COMPLETE   2026-04-29 09:59 UTC   ← was rolling back
openclaw-mcp-006-v3         UPDATE_COMPLETE   2026-04-29 10:39 UTC   ← was 502ing
Openclaw006V3-RiskAlerts    CREATE_COMPLETE   2026-04-28 14:55 UTC
```

Only `Openclaw006V3-FilingsPipeline` and `Openclaw006V3-ResearchPipeline` remain unattempted.

### AgentCore — v3 container is live

```
openclaw_v3_agent-o72dx396I0   status=READY    updated 2026-04-29 11:04 UTC
openclaw_agent-QTvJf03edt      status=READY    updated 2026-04-09 (old v2 container)
```

The v3 container shipped ~6 minutes before this assessment started. This is the container that will actually serve v3 WebSocket traffic.

### MCP Lambdas — all green

Probing the live API Gateway (`https://e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3`):

```
/mcp/market-data/tools/list       HTTP 200, returns 3 tools
/mcp/market-data/tools/call       HTTP 200, NVDA=$213.17 from FINNHUB LIVE
/mcp/sec-edgar/tools/list          HTTP 200, returns get_latest_filing + get_filing_sections
/mcp/salesforce-crm/tools/list     HTTP 200, returns 12 tools
/mcp/mulesoft-actions/tools/list   HTTP 200, submit_order/cancel/modify/wire/webhook
/api/session/warm                  HTTP 200, returns {"warmed":true,"ticker":"NVDA"}
```

The `_base` layer packaging bug is fixed. Authn header is required (`X-MCP-API-Key`) and fail-closed. Real vendor data flowing.

### Bedrock Knowledge Base — live with 10 filings ingested

```
KB id:          NBR5AFTREI
KB name:        openclaw-v3-filings
Status:         ACTIVE
Data source:    openclaw-v3-chunks (AVAILABLE)
Ingestion:      COMPLETE — 784 documents indexed (no failures)
```

Raw filings bucket contains actual 10-K / 10-Q HTML from SEC EDGAR — verified:
- AAPL-10-Q-2026-01-30.htm (766 KB)
- AMD-10-K-2026-02-04.htm (2.2 MB)
- AMZN-10-K-2026-02-06.htm (2.0 MB)
- GOOGL-10-K-2026-02-05.htm (2.6 MB)
- GS-10-K-2026-02-25.htm (9.6 MB)
- JPM-10-K-2026-02-13.htm (13 MB)
- META-10-K-2026-01-29.htm (2.4 MB)
- MSFT-10-Q-2026-01-28.htm (7.5 MB)
- NVDA-10-K-2026-02-25.htm (2.0 MB)
- TSLA-10-Q-2026-04-23.htm (1.2 MB)

A live `bedrock-agent-runtime retrieve` against the query `"revenue growth"` returned real chunks with proper citations (ticker, form, filing_date, accession, source_url, source_chunk_id). MSFT/NVDA/TSLA appeared in top-3. **This is live semantic retrieval over real SEC data with Titan v2 embeddings.**

### OpenSearch Serverless collection

```
openclaw-v3-kb        ACTIVE
```

### Aurora pgvector — live cluster

```
openclaw006v3-aurora-researchcorpus7fb69655-mwdbsddfwld7   available
```

The SchemaMigrator + RLS deployment worked. This is the research-corpus store.

### Vendor API keys in SSM

| Vendor | State |
|---|---|
| Finnhub | ✅ real key in SSM (verified by live `get_quote NVDA` returning $213.17) |
| Tavily | ✅ real key in SSM (`tvly-dev-...`) |
| Alpha Vantage | ❌ still `PLACEHOLDER_FREE_TIER_FIX_LATER` |
| Alpaca paper | ✅ $187,398.55 buying power (verified earlier) |
| Dwolla sandbox | ✅ OAuth token |
| Langfuse US | ✅ 1 project |
| MuleSoft Anypoint | ✅ OAuth token |

### Salesforce org `new-org`

```
Research_Brief__c       COUNT = 0  ← no real briefs written yet
Client_Inquiry__c       COUNT = 0  ← no inquiries yet
IR_Pending_Approval__c  COUNT = 0
IR_Audit_Log__c         COUNT = 762  ← historical data from v2 / earlier tests
```

85/85 metadata deployed. But audit rows are 100% legacy — action names like `sec_filings`, `sentiment_analysis`, `PIPELINE_START`, `TRADE_REVIEW` are from 006-v2's 23-stage pipeline era, not the v3 7-gate spine. **Zero v3 turn has written to Salesforce yet.**

Additionally, a quick SOQL confirmed `Agent_Id__c` is still **not on** `IR_Audit_Log__c` — the field-drift gap from the earlier wire audit is still real. When v3 finally fires its first audit row, the Python code will try to write `Agent_Id__c` and Salesforce will silently drop it.

### Frontend — deployed but stale

S3 bucket `ir-research-workbench-v3-prod-875460787302` contains a built Vite bundle (`index-Tr_x0ZBO.js` 690 KB, `index-BICfVcei.css` 904 KB, 17 objects, 5.1 MB total). Uploaded 2026-04-27. CloudFront `d3t2yuearw7l53.cloudfront.net` returns HTTP 200.

**Caveat:** this is the Apr 27 build, not re-built after the recent `VITE_API_URL` and `VITE_AGENTCORE_URL` env changes. It almost certainly points at placeholder URLs or an older AgentCore endpoint. Live UI will load but likely fail WebSocket handshake.

### MuleSoft

Three Maven projects exist locally (submit-order, initiate-wire, order-status-webhook). CloudHub 2.0 applications: **not deployed**. A `mvn deploy -Pcloudhub-sandbox` wave has not run.

---

## 3. Design vs Built vs Deployed — line-by-line

### Depth commitments (from v3-narrative-arc.md §2)

| # | Depth commitment | Design | Built | Deployed | Notes |
|---|---|---|---|---|---|
| 1 | Hybrid RAG (BM25 + Titan v2 + section-aware + Cohere Rerank) | 🟢 | 🟡 | 🟡 | Code exists, default = StubEmbedder/StubReranker. **BUT** the KB side now runs real Titan v2 embeddings against real filings — verified live retrieval. `rag_retrieve` skill itself still uses stubs when called directly. |
| 2 | Citation-bound charts + Textract drag-drop | 🟢 | 🟢 | 🟡 | Renderer and chips exist in frontend. Textract pipeline not deployed. Frontend points at stale URLs. |
| 3 | Deterministic financial statement analysis | 🟢 | 🟢 | 🟢 | Calculators exist, sec-edgar MCP live, XBRL parser works. End-to-end should run now. |
| 4 | Langfuse span discipline | 🟢 | 🟢 | 🟢 | Real client with scrubber. Will light up on first real turn. |
| 5 | Hybrid data layer (SF single writer + CDC to Aurora) | 🟢 | 🟢 | 🟡 | Aurora live, RLS policies applied. CDC Lambda code exists. `ResearchPipeline` stack not yet deployed — Platform Event → EventBridge → Aurora re-embed pipe is not wired live. |
| 6 | Simple-outside / complex-inside UI | 🟢 | 🟢 | 🟡 | Build on S3 but stale. |
| 7 | True multi-agent, 17 agents | 🟢 | 🟡 | 🟡 | Doc says 17; built=14; deployed v3 container is 14. Doc drift. Runtime trust isolation is still partly prompt-only (`GateEnforcer.check_mcp()` never called). |

### Auth — six boundaries

| # | Boundary | Design | Built | Deployed | Notes |
|---|---|---|---|---|---|
| 1 | User → IdP (Okta/Azure AD) PKCE | 🟢 | 🔴 | 🔴 | No IdP code. SPA uses `dev-bootstrap-token`. |
| 1b | Session HMAC token mint/verify | 🟢 | 🟢 | 🟡 | BFF verifies. Coordinator does not call `verify()`. |
| 2 | Skill allowlist | 🟢 | 🟢 | 🟢 | Tool-use loop enforces fail-closed. |
| 3 | Agent → MCP (API key + principal) | 🟢 | 🟢 | 🟢 | Header enforcement verified live (401 without key). |
| 4 | MCP → Salesforce per-user OBO | 🟢 | 🟢 | 🟢 | Real JWT Bearer flow. Verified live earlier. |
| 5 | Agent → MuleSoft client_credentials + policies | 🟢 | 🟢 | 🟡 | Anypoint OAuth works. Policies JSON still has `REPLACE_WITH_LAMBDA_NAT_EIP` placeholder. |
| 6 | Data-layer authz walls (SF sharing rules, Aurora RLS, etc.) | 🟢 | 🟢 | 🟡 | SF rules live. Aurora RLS applied. MuleSoft CloudHub not deployed. |

### Five narratives — live runnability

| # | Narrative | Design | Built | Deployed | Verdict |
|---|---|---|---|---|---|
| 1 | Earnings Morning | 🟢 | 🟢 | 🟢 | **Should actually run end-to-end now.** Real Finnhub + real EDGAR + real KB + real SF via OBO. First live turn has not been taken. Audit row will write but drop 7 fields (drift). |
| 2 | Client → RM → Analyst → Trade | 🟢 | 🟡 | 🟡 | `rm-handoff` skill still missing from code. `Research_Request__c` not in SF metadata. Half-wired. |
| 3 | Risk Alert | 🟡 (roadmap) | 🟡 | 🟡 | `compliance_sweep` calls undeclared `dynamodb` MCP. `Client_Alert__c` missing. Slide material. |
| 4 | Demand Signal | 🟡 (roadmap) | 🔴 | 🔴 | Slide only. No clustering algorithm. |
| 5 | Large Liquidation | 🟢 | 🟢 | 🟡 | Code real. MuleSoft CloudHub not deployed so real Alpaca/Dwolla calls won't flow. Webhook path mismatch remains. Dual-auth `Expires_At__c` never written. |

---

## 4. What IS live end-to-end right now

Verified by live probe, not documentation:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ WORKING TODAY (sub-minute, hand-on-keyboard verifiable)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. market-data MCP  -> Finnhub  -> live NVDA quote $213.17                 │
│  2. sec-edgar MCP    -> 10 real 10-K/10-Q HTML files in S3                  │
│  3. KB retrieve      -> cosine search over 784 chunks,                      │
│                         Titan v2 1024-dim embeddings, 10 tickers covered   │
│  4. news-search MCP  -> Tavily real key, real web search                    │
│  5. salesforce-crm MCP  -> SF Auth Proxy -> JWT Bearer OBO -> real SF calls │
│  6. mulesoft-actions MCP  -> correct tool list + plan_hash/token required  │
│  7. BFF session warm -> 200 OK                                              │
│  8. AgentCore v3 container  -> READY                                        │
│  9. Aurora pgvector cluster  -> available with RLS applied                  │
│  10. Langfuse cloud  -> project accessible                                  │
│  11. Bedrock Sonnet 4.6 + Haiku 4.5 + Titan v2  -> all respond via converse │
│  12. Bedrock Guardrail nlouzhamlv7h v1  -> READY with FinancialActions +    │
│                                            InsiderInformation topics       │
│  13. Salesforce 85/85 components deployed in new-org                        │
│  14. API Gateway auth fail-closed on missing X-MCP-API-Key (401)            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. What is NOT live end-to-end

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STILL BROKEN OR NOT DEPLOYED                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  A. Frontend SPA build is from Apr-27, points at stale env URLs             │
│     → Loads in browser but WebSocket handshake likely fails                 │
│                                                                             │
│  B. MuleSoft CloudHub applications never deployed                           │
│     → Narrative 5 write path cannot reach Alpaca/Dwolla live                │
│                                                                             │
│  C. IR_Audit_Log__c missing 7 fields Python tries to write                  │
│     → Audit rows will land but be incomplete (confirmed live: Agent_Id__c  │
│       does not exist in the deployed SObject)                               │
│                                                                             │
│  D. IR_Pending_Approval__c field name drift + no Expires_At__c writes       │
│     → Dual-auth rows will be nearly empty                                   │
│                                                                             │
│  E. Okta/Cognito IdP handshake — zero code                                  │
│     → SPA boots with dev-bootstrap-token                                    │
│                                                                             │
│  F. SessionTokenMinter.verify() never called in coordinator.run_turn()      │
│     → WebSocket path accepts any principal_id                               │
│                                                                             │
│  G. GateEnforcer.check_mcp() never called                                   │
│     → mcp_allowlist in topology.py is prompt-advisory only                  │
│                                                                             │
│  H. FilingsPipeline + ResearchPipeline CDK stacks not deployed              │
│     → EDGAR re-ingest + SF CDC re-embed do not run live.                    │
│     → KB only has the one-shot manual seed of 10 filings.                   │
│                                                                             │
│  I. Webhook path mismatch: Mule /api/webhooks/orders vs MCP                 │
│     /orders/{id}/webhook                                                    │
│     → Order fill callbacks would 404 if MuleSoft were deployed              │
│                                                                             │
│  J. rm-handoff skill missing + Research_Request__c SObject not deployed     │
│     → Narrative 2 demand-pull research path cannot complete                 │
│                                                                             │
│  K. Client_Alert__c SObject not deployed                                    │
│     → Narrative 3 RM-gate workflow cannot fire                              │
│                                                                             │
│  L. MuleSoft policies JSON IP allowlist = REPLACE_WITH_LAMBDA_NAT_EIP/32    │
│     → Would block all Lambda→Mule traffic once Mule is live                 │
│                                                                             │
│  M. compliance_sweep calls server="dynamodb" which isn't declared in        │
│     openclaw.json mcp.servers                                               │
│     → Narrative 3 scheduled sweep would MCPError on first run               │
│                                                                             │
│  N. UI event gap: backend does not emit gate_started / gate_passed /        │
│     gate_failed over WebSocket                                              │
│     → SevenGateTracker renders grey chrome, never lights up live            │
│     → AuditStrip flashes all at once at end of turn, not tick-by-tick      │
│                                                                             │
│  O. Alpha Vantage key still PLACEHOLDER_FREE_TIER_FIX_LATER                 │
│     → Fallback market data path broken (Finnhub covers primary)             │
│                                                                             │
│  P. Zero live v3 turns in Salesforce audit log                              │
│     → The 762 rows are 006-v2 historical data (PIPELINE_START,              │
│       sec_filings, sentiment_analysis etc.), not v3 audit rows              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. The updated picture — ASCII live stack

```
 ┌────────────────────────────────────────────────────────────────────────────┐
 │                        BROWSER (user)                                      │
 │   CloudFront d3t2yuearw7l53.cloudfront.net → S3 ir-research-workbench      │
 │   ✅ HTTP 200                                                              │
 │   ⚠️  Bundle is Apr-27 build; env URLs almost certainly stale             │
 └──────────────┬─────────────────────────────────────────────────────────────┘
                │ (1) boot → sessionToken='dev-bootstrap-token'  ❌ no IdP
                ▼
 ┌────────────────────────────────────────────────────────────────────────────┐
 │                   AgentCore v3 container (us-east-1)                       │
 │   openclaw_v3_agent-o72dx396I0   READY  updated 11:04 UTC                  │
 │   ✅ Live. WebSocket path trusts principal_id (no verify())                │
 └──────────────┬─────────────────────────────────┬───────────────────────────┘
                │                                 │
       ┌────────▼────────┐                ┌───────▼─────────┐
       │ MCP read-path   │                │ MuleSoft write  │
       │ LIVE            │                │ NOT DEPLOYED    │
       └────────┬────────┘                └───────┬─────────┘
                │                                 │
                ▼                                 ▼
 ┌──────────────────────────────────────┐  ┌──────────────────────────────┐
 │  API Gateway  e5zbqnkmx8              │  │  CloudHub apps not running   │
 │  openclaw-mcp-006-v3  UPDATE_COMPLETE │  │  ❌ mvn deploy never ran     │
 │  NatEip 54.88.221.141                 │  └──────────────────────────────┘
 │                                       │
 │  7 Lambdas (layer packaged correctly):│  ┌──────────────────────────────┐
 │   006-v3-market-data        ✅        │  │   SF new-org                 │
 │   006-v3-sec-edgar          ✅        │  │   ✅ 85/85 deployed           │
 │   006-v3-news-search        ✅        │  │   ⚠️  drifted fields         │
 │   006-v3-salesforce-crm     ✅        │  │       (Agent_Id__c missing)  │
 │   006-v3-bff                ✅        │  │   ⚠️  Research_Request__c    │
 │   006-v3-sf-auth-proxy      ✅        │  │       not in metadata        │
 │   006-v3-mulesoft-actions   ✅        │  │   ⚠️  Client_Alert__c missing│
 │  Live test: NVDA=$213.17 via Finnhub  │  │   0 v3 briefs, 0 inquiries,  │
 └──────────────────────────────────────┘  │   762 audit rows (all v2 data)│
                                           └──────────────────────────────┘
 ┌──────────────────────────────────────┐  ┌──────────────────────────────┐
 │  Bedrock Knowledge Base               │  │   Aurora pgvector cluster    │
 │   ✅ openclaw-v3-filings (NBR5AFTREI) │  │   ✅ cluster available       │
 │   ✅ 10 real filings ingested         │  │   ✅ RLS policies applied    │
 │   ✅ 784 chunks with Titan v2 embed   │  │   ⚠️  no CDC pipeline        │
 │   ✅ Live retrieval works             │  │       (FilingsPipeline +     │
 │   ⚠️  One-shot seed, no re-ingest pipe│  │        ResearchPipeline      │
 │      (FilingsPipeline stack not built)│  │        stacks not deployed)  │
 └──────────────────────────────────────┘  └──────────────────────────────┘

 ┌──────────────────────────────────────┐  ┌──────────────────────────────┐
 │  Vendor keys (SSM)                   │  │   Salesforce Auth Proxy       │
 │   ✅ Finnhub      real               │  │   ✅ Lambda live              │
 │   ✅ Tavily       real               │  │   ✅ JWT Bearer OBO per-user  │
 │   ✅ Alpaca paper $187K BP           │  │      (verified live earlier)  │
 │   ✅ Dwolla sandbox                  │  └──────────────────────────────┘
 │   ✅ Langfuse US                     │
 │   ✅ MuleSoft Anypoint OAuth         │
 │   ❌ Alpha Vantage PLACEHOLDER       │
 └──────────────────────────────────────┘
```

---

## 7. What changed in the last ~6 hours

From the last deep assessment to now, these specific gaps closed:

1. **MCP Lambda layer packaging** — `_base` import works. All 7 Lambdas up with last modification timestamps 08:52-10:40 UTC.
2. **Aurora stack** — `SchemaMigrator` env-var-size bug is fixed. Cluster `mwdbsddfwld7` available with schema + RLS applied.
3. **KB stack** — OpenSearch index creation race resolved. Collection `openclaw-v3-kb` ACTIVE. KB `NBR5AFTREI` ACTIVE. Data source ingestion COMPLETE with 784 documents.
4. **Vendor keys** — Finnhub and Tavily now hold real API keys (Alpha Vantage still placeholder).
5. **Filings corpus** — 10 real 10-K/10-Q HTML files sitting in the raw bucket (AAPL, AMD, AMZN, GOOGL, GS, JPM, META, MSFT, NVDA, TSLA). Multiple ingestion jobs ran to COMPLETE status.
6. **AgentCore v3 runtime** — new container `openclaw_v3_agent-o72dx396I0` deployed at 11:04 UTC. This is the first v3-specific runtime version in the account.
7. **SAM stack** — UPDATE_COMPLETE at 10:39 UTC after the layer fix.
8. **BFF** — `/api/session/warm` returns 200 (was empty payload before).

That is real, measurable forward progress.

---

## 8. Remaining to-do to make Narratives 1 and 5 defensible on stage

Ordered by blast radius.

| # | Item | Effort | Blocks narrative |
|---|---|---|---|
| 1 | Re-build frontend SPA against live env URLs, re-upload to S3, invalidate CloudFront | 20 min | All narratives (UI is the stage) |
| 2 | Backend emits gate_started/passed/failed WebSocket events mid-turn | 45 min | Narrative 1 audit strip, Narrative 5 gate tracker |
| 3 | Deploy 3 MuleSoft CloudHub apps via `mvn deploy` | 2 hrs | Narrative 5 trade + wire path |
| 4 | Substitute NAT EIP in `mulesoft/policies/process-api-policies.json` | 30 sec | Same as #3 |
| 5 | Align webhook path (Mule or MCP side) | 10 min | Narrative 5 fill confirmation |
| 6 | Add missing `Agent_Id__c` + 6 other fields to `IR_Audit_Log__c` metadata and redeploy | 15 min | All narratives (audit integrity) |
| 7 | Wire `BedrockTitanEmbedder` + `CohereReranker` as default in `rag_retrieve` when env keys present | 30 min | Narrative 1 semantic quality |
| 8 | Add `Expires_At__c` write to `dual_auth/actions.py` request phase | 30 min | Narrative 5 dual-auth TTL |
| 9 | Fix BFF `/api/source_chunk/{id}` to proxy the KB retrieval | 1 hr | Citation drill-through across all narratives |
| 10 | Honest Okta story OR Cognito hosted-UI in the SPA (whichever fits the time budget) | 1 hr / 1 day | Auth credibility |
| 11 | Take one golden-turn — real browser → real AgentCore → real Bedrock → real Finnhub → real KB → real SF → real audit row → Langfuse trace closed | 30 min | **ALL narratives** — this is the smoke test that proves it works |

**Total blocker-fix effort to make Narrative 1 genuinely live end-to-end: ~1 hour if #1, #2, #6, and #11 are done.** Narrative 5 requires an additional 2–3 hours for MuleSoft deploy and webhook alignment.

---

## 9. Defensibility matrix for the panel

Updated based on current live state:

| Claim | Defensible today? | Evidence |
|---|---|---|
| "We have a three-persona multi-agent runtime" | 🟢 yes | `topology.py` with 14 agents, v3 AgentCore container live |
| "Tool allowlist is runtime-enforced, fail-closed" | 🟢 yes | Verified: `tool_dispatch.py` + live 401 on missing MCP key |
| "We do hybrid RAG over SEC filings" | 🟢 yes (KB side) | 784 chunks ingested, Titan v2 embeddings, real `retrieve` verified |
| "OFAC SDN screen is a hard code branch before wire" | 🟢 yes | `mulesoft_api/actions.py:185` real code |
| "Every CRM call is per-user OBO via JWT Bearer" | 🟢 yes | SF Auth Proxy live, JWT works |
| "Seven gates fire in order on the write path" | 🟡 code yes, live tracker no | No WebSocket gate events yet |
| "Audit row on every outcome, hashed tokens only" | 🟡 code yes, SF rows drifted | Agent_Id__c field missing in deployed metadata |
| "Real Bedrock reasoning, not stub" | 🟢 architecturally yes | But no v3 turn has been taken end-to-end yet |
| "Enterprise Okta/Azure AD authentication" | 🔴 no | Dev-bootstrap-token in SPA |
| "Full trust spine under time pressure (Narrative 5)" | 🟡 code yes, MuleSoft no | CloudHub undeployed |
| "RM demand-pull research (Narrative 2)" | 🔴 no | rm-handoff skill + Research_Request__c missing |
| "Scheduled compliance sweep (Narrative 3)" | 🔴 no (admitted in design as roadmap) | honest deferral |
| "Demand-signal clustering (Narrative 4)" | 🔴 no (admitted in design as roadmap) | honest deferral |
| "~22,000 lines of code net-new" | 🟢 yes (actually more) | 30,244 lines production code; 37,669 lines including tests |

---

## 10. Bottom line

**Six hours ago:** every MCP Lambda was HTTP 502, no Aurora cluster, no Bedrock KB, zero filings indexed, and the docs claimed 18 deliverables were built but none were deployed. The honest grade was 20% live.

**Now:** MCPs serve real traffic, KB has real filings with real embeddings, Aurora is running with RLS, v3 AgentCore is READY, SF Auth Proxy OBO works, Finnhub + Tavily keys are real. Roughly 75% of the stack is live.

**Remaining work:** mostly narrative completeness (rm-handoff, dual-auth TTL, Research_Request__c), UI polish (rebuild SPA, emit gate events), and the one big deploy left (MuleSoft CloudHub). No architectural work, no redesigns.

The platform has crossed the line from "docs promise a lot, code is mostly there, nothing deployed" to **"most of the stack is actually running; a handful of loose ends remain"**. That is a materially different conversation to have with the panel. Narrative 1 is within ~1 hour of being genuinely live end-to-end. Narrative 5 is within ~3 hours.

*— assessment closed 2026-04-29 ~11:10 UTC.*
