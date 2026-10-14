# 006 V3 — Built vs Designed Assessment

> **Audience:** exec panel prep, internal steering, and whoever is running the next deploy
> **Purpose:** tell the truth about what is real, what is wired, what is mockery drama in the current build
> **Date:** April 29, 2026
> **Method:** code read, live AWS probes (AgentCore, CloudFormation, Lambda, RDS, Bedrock KB, API Gateway), and cross-check against `v3-narrative-arc.md` + `v3-build-status.md`
> **Status:** ground truth as of the last CloudFormation retry cycle on 2026-04-29 06:23 UTC

---

## 1. One-paragraph summary

The architecture and code are about 85% of what the design doc promises. The remaining 15% is not a design problem — it is three deploy-blocking bugs, four runtime contract drifts, three unwired security invariants, and one UI-backend event gap that makes the "live trust spine" look frozen on stage. Nothing needs to be redesigned. About 6–8 hours of focused code work plus one clean redeploy closes the gap between what the doc claims and what the audience sees.

---

## 2. Architecture on one picture — what exists in AWS right now

```
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                           BROWSER (user)                                 │
 │    CloudFront d3t2yuearw7l53.cloudfront.net  →  S3 bucket static SPA     │
 │                              ✅ LIVE                                     │
 └──────────────┬───────────────────────────────────────────────────────────┘
                │  (1) On page load, SPA boots with hardcoded
                │       sessionToken='dev-bootstrap-token'
                │       principalId='dev-principal'                 ❌ NO OKTA/COGNITO
                │       (Okta/PKCE handshake NOT BUILT)
                │
                │  (2) Opens WebSocket to AgentCore
                │       wss://<agentcore>/agent?authorization=Bearer...
                │
                ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                         AgentCore Runtime (us-east-1)                    │
 │   openclaw_agent-QTvJf03edt  status=READY  last updated Apr 9            │
 │                                                                          │
 │   ⚠️  This is the PRE-V3 container. Apr-9 build does NOT have           │
 │       v3 SessionTokenMinter.verify() wired. Any session token            │
 │       passes through.                                                    │
 │                                                                          │
 │   PersonaCoordinator reads `?persona=research|advisor|client`            │
 │   Routes to one of three orchestrators:                                  │
 │                                                                          │
 │     research_orchestrator   advisor_orchestrator   liaison_orchestrator  │
 │     (6 sub-agents)          (5 sub-agents)         (3 sub-agents)        │
 │     asyncio.gather          write path=SERIAL      read-only + rm-handoff│
 │                                                                          │
 │   14 total agents (NOT 17 as docs say). All Sonnet 4.6 / Haiku 4.5.      │
 │   Tool-use loop enforces per-agent tool_allowlist (REAL, fail-closed).   │
 │                                                                          │
 │   ✅ Code exists, wired.                                                 │
 │   ❌ Never exercised end-to-end against real Bedrock.                    │
 └──────────────┬────────────────────────────────┬──────────────────────────┘
                │                                │
                │ (3) Agent calls MCP tool       │ (4) Agent calls MuleSoft
                │     server="market-data"       │     server="mulesoft-actions"
                │     via HTTP POST to API GW    │     (write path, gated)
                ▼                                ▼
 ┌─────────────────────────────────────┐  ┌─────────────────────────────────┐
 │   API Gateway (SAM stack)           │  │   Same API GW, different tool   │
 │   openclaw-mcp-006-v3 CREATE_COMPLETE│  │                                 │
 │   ApiUrl=https://e5zbqnkmx8...      │  │   🔴 WEBHOOK PATH MISMATCH      │
 │   NatEip=54.88.221.141              │  │   MCP calls:                    │
 │                                     │  │     /orders/{id}/webhook        │
 │   Routes to 7 Lambda functions:     │  │   Mule listens on:              │
 │     006-v3-market-data       502    │  │     /api/webhooks/orders        │
 │     006-v3-sec-edgar         502    │  │   → fill callbacks go to 404    │
 │     006-v3-news-search       502    │  └─────────────────────────────────┘
 │     006-v3-salesforce-crm    502    │
 │     006-v3-bff               502    │  ┌─────────────────────────────────┐
 │     006-v3-sf-auth-proxy     502    │  │   Policies JSON has             │
 │     006-v3-mulesoft-actions  502    │  │   "REPLACE_WITH_LAMBDA_NAT_EIP" │
 │                                     │  │   placeholder not swapped       │
 │   🔴 ALL 502 — Layer packaging bug  │  │   → IP allowlist broken         │
 │      Runtime.ImportModuleError:     │  └─────────────────────────────────┘
 │      "No module named '_base'"      │
 │   (ContentUri needs python/ wrapper)│  ┌─────────────────────────────────┐
 └─────────────────────────────────────┘  │   MuleSoft CloudHub             │
                                          │   3 Process APIs written as     │
 ┌─────────────────────────────────────┐  │   code (submit-order,           │
 │   Bedrock Knowledge Base            │  │   initiate-wire, webhook)       │
 │   🔴 ZERO KBs exist in account      │  │                                 │
 │   Kb CDK stack rolled back 2x       │  │   🔴 NOT DEPLOYED to CloudHub   │
 │   "no such index                    │  │                                 │
 │     [openclaw-v3-kb-index]"         │  │   (Anypoint creds work, but     │
 │   (OSS collection/index race)       │  │    mvn deploy never run)        │
 └─────────────────────────────────────┘  └─────────────────────────────────┘

 ┌─────────────────────────────────────┐  ┌─────────────────────────────────┐
 │   Aurora pgvector                   │  │   Salesforce org "new-org"      │
 │   🔴 ZERO clusters exist            │  │   ✅ 85/85 components deployed  │
 │   Aurora CDK stack rolled back 4x   │  │      5 SObjects, 3 triggers,    │
 │   "env variables exceeded 4KB"      │  │      3 permsets, 71/72 Apex     │
 │   (INIT_SQL + RLS_SQL as env vars)  │  │      tests pass                 │
 │                                     │  │                                 │
 │   Schema + RLS policies exist in    │  │   Research_Brief__c             │
 │   SQL files but never ran           │  │   Client_Inquiry__c             │
 └─────────────────────────────────────┘  │   Client_Preferences__c         │
                                          │   IR_Audit_Log__c               │
 ┌─────────────────────────────────────┐  │   IR_Pending_Approval__c        │
 │   Vendor APIs (SSM)                 │  │                                 │
 │   ✅ Alpaca paper       $187K BP    │  │   🟡 Research_Request__c        │
 │   ✅ Dwolla sandbox                 │  │      NOT in metadata            │
 │   ✅ Langfuse US cloud  1 project   │  │   🟡 Client_Alert__c            │
 │   ✅ MuleSoft Anypoint OAuth ok     │  │      NOT in metadata            │
 │                                     │  └─────────────────────────────────┘
 │   ❌ Finnhub    PLACEHOLDER_FREE... │
 │   ❌ Tavily     PLACEHOLDER_FREE... │
 │   ❌ Alpha V.   PLACEHOLDER_FREE... │
 └─────────────────────────────────────┘
```

---

## 3. Flow map — what SHOULD happen on one user turn (design doc)

```
Sarah types "Research NVDA ahead of earnings"
│
▼
SPA sends query over WebSocket to AgentCore
│
▼
PersonaCoordinator.run_turn(persona=research)
│
▼
research_orchestrator dispatches 5 specialists in parallel (asyncio.gather):
│
├── market_specialist     → market-data MCP   → Finnhub API
├── filings_specialist    → sec-edgar MCP + rag_retrieve → EDGAR + Bedrock KB
├── sentiment_specialist  → news-search MCP   → Tavily API
├── compliance_specialist → compliance_screening skill (local)
└── statement_specialist  → financial_statement_analysis skill (local XBRL math)
│
▼ (results join)
│
orchestrator synthesizes with citation-enforcement harness
│
▼
publish_brief skill → salesforce-crm MCP → writes Research_Brief__c
│
▼
audit_logging skill → salesforce-crm MCP → writes IR_Audit_Log__c
│
▼
Langfuse trace closes with full span tree
│
▼
SPA renders streaming brief with clickable citation chips
```

---

## 4. Reality map — what ACTUALLY happens today

```
Sarah types "Research NVDA ahead of earnings"
│
▼
SPA boots with dev-bootstrap-token (no Okta)                     ❌ FAKE AUTH
│
▼
WebSocket to AgentCore Apr-9 container
│
▼
PersonaCoordinator routes the turn (trusts whatever principal_id arrives)
│                                                                 ❌ NO verify()
▼
research_orchestrator dispatches 5 specialists in parallel
│
├── market_specialist → POST https://e5zbqnkmx8.../mcp/market-data/tools/call
│                       ❌ HTTP 502 — _base module not found
│
├── filings_specialist → same 502 on sec-edgar
│                       rag_retrieve would use StubEmbedder (64-dim hash)
│                       ❌ No KB = no real documents to retrieve
│
├── sentiment_specialist → same 502 on news-search
│                       Tavily key is PLACEHOLDER anyway
│
├── compliance_specialist → runs locally (restricted_list.json) ✅ WORKS
│
└── statement_specialist → runs locally (XBRL parser) ✅ WORKS if 10-Q came back
│
▼ (4 of 5 specialists returned errors or empty)
│
orchestrator synthesizes → "I couldn't retrieve..." failure text
│
▼
publish_brief → 502 (salesforce-crm Lambda also broken)
│
▼
No Research_Brief__c written. No audit row. SPA shows an error toast.
```

---

## 5. UI wiring — does the live flow show the stages?

This is where the illusion is sharpest. Be blunt here:

```
AdvisorScreen.tsx
├── <PersonaHeader persona="fsi_advisor" />                    ✅ real
├── <SevenGateTracker gates={gateTracker.gates} />             ⚠️  real component
│   │                                                              rendered
│   ├── visual: ①Guard ②MNPI ③Comp ④HITL ⑤DualAuth ⑥Audit
│   │
│   └── data source: gateTracker.gates  ←  initial state is emptyGates
│                                          (6 × {status: 'pending'})
│
├── useGateTracker()                                           ✅ hook exists
│   │   listens for: InboundMessage type ∈ {gate_started,
│   │                                       gate_passed,
│   │                                       gate_failed}
│   │   updates state via handleGateEvent(ev)
│
├── useStreamingTurn()                                         ✅ parses
│   │   routes gate_started/passed/failed → gateTracker
│
└── Backend emits gate_started/gate_passed/gate_failed?
    └── 🔴 grep across openclaw/*.py → ZERO matches.
         Backend never emits these WebSocket events.
         The tool-use loop records a trace ARRAY returned at end of turn.
         It does NOT send per-gate events down the WebSocket in real time.

┌─────────────────────────────────────────────────────────────────┐
│ So what does the SevenGateTracker show on stage?                │
│                                                                 │
│ It shows the CHROME — six greyed-out gate pills — that never    │
│ light up because nothing pushes events into useGateTracker.     │
│                                                                 │
│ The panel sees the design, not the behavior.                    │
│                                                                 │
│ To make the tracker light up live, you need ONE of:             │
│                                                                 │
│ (A) Backend change: coordinator emits                           │
│     `{"type":"gate_started","gate":"compliance",...}` after     │
│     each tool_dispatch step. Probably 40 lines in               │
│     orchestration/coordinator.py.                               │
│                                                                 │
│ (B) Frontend workaround: after the turn's trace[] array arrives │
│     in the final synthesis payload, REPLAY it locally with      │
│     400ms delays to animate the tracker. Demo-acceptable, not   │
│     truly live.                                                 │
└─────────────────────────────────────────────────────────────────┘
```

The same pattern applies to the rest of the "live" surfaces:

```
AuditStrip.tsx       → wired to WebSocket tool_trace events
                       🟡 backend emits tool trace entries at END of turn
                          (in the WorkerResponse.result payload),
                          NOT streaming mid-turn

CitationChip.tsx     → click handler calls GET /api/source_chunk/{id}
                       🔴 BFF handler returns empty payload
                          (sec-edgar MCP never registers get_source_chunk)
                       → citations appear, click them → "Source not available"

StreamingText.tsx    → expects agent_text deltas streamed via WebSocket
                       🟡 scaffolded in useStreamingTurn, but backend
                          returns one complete response, not streaming chunks
                          (at least for tool-use turns)

DeterministicChart   → expects chart_intent blocks from LLM
                       🟡 ready on the UI side. Backend doesn't emit
                          structured chart intent yet.
```

**Short answer on the live flow question:** the UI is wired to *show* the stages, but the backend is not wired to *report* them live. The tracker renders six grey pills that never light up in real time.

### Event-by-event wiring table

```
SPA EXPECTS                      BACKEND PRODUCES           MATCH?
──────────────                    ────────────────           ──────
gate_started event   ────────→   nothing                    🔴 no
gate_passed event    ────────→   nothing                    🔴 no
gate_failed event    ────────→   nothing                    🔴 no
tool_call event      ────────→   trace array at end of turn 🟡 post-hoc
tool_result event    ────────→   trace array at end of turn 🟡 post-hoc
agent_text delta     ────────→   partial (Bedrock stream)   🟡 if real BDRK
queue_update event   ────────→   nothing                    🔴 no
hitl_prompt event    ────────→   nothing                    🔴 no
error event          ────────→   nothing live               🔴 no
```

### What the audience sees today vs what the design promises

**Today:**
- Sarah types a query
- Spinner spins
- (silent backend work)
- Final brief renders — or error toast
- Audit strip either stays empty or flashes all 7 gates at once

**Promised:**
- Sarah types a query
- Audit strip ticks through: `compliance ✓` → `sec-edgar ✓` → `news ✓` → `sonnet ✓` → `publish ✓`
- Brief streams in letter by letter with citation chips appearing inline
- Charts render deterministically as their source tables arrive
- Gate tracker advances live for Narrative 5

This is the gap between "a demo that convinces the panel" and "a demo that looks like a screenshot."

---

## 6. Narrative-by-narrative readiness

### Narrative 1 — Earnings Morning (Sarah → Brief → RM → Client)

```
Needs                                  Built?
─────                                  ──────
Sarah's terminal UI                    ✅ ResearchTerminal.tsx exists
research_orchestrator + 5 specialists  ✅ code exists
Parallel asyncio.gather fanout         ✅ real code
market-data MCP live                   🔴 HTTP 502
sec-edgar MCP live                     🔴 HTTP 502
news-search MCP live                   🔴 HTTP 502
RAG with real Titan embeddings         🔴 StubEmbedder by default
Bedrock KB with filings                🔴 No KB exists
Finnhub / Tavily live keys             🔴 PLACEHOLDER_FREE_TIER_FIX_LATER
publish-brief writes Research_Brief__c 🟡 code OK, Lambda 502
Audit row                              🟡 code OK, Lambda 502
Langfuse trace                         ✅ scrubber + client wired
Citation chips drill through           🔴 BFF source_chunk handler empty
Streaming UI                           🟡 mostly hand-wavy today
```

**Verdict:** Narrative 1 does NOT run end-to-end today. Fixes needed: 3 deploy bugs + 3 vendor keys + real embedder = ~4 hours.

### Narrative 2 — Client → RM → Analyst → RM → Client → Trade

```
Needs                                  Built?
─────                                  ──────
Client WhatsApp-style channel          ✅ ClientChannel.tsx exists
liaison-orchestrator + 3 agents        ✅ code exists
rm-handoff skill                       🔴 MISSING from openclaw/skills/
  (referenced in topology but no code)
Client_Inquiry__c routing              ✅ SObject deployed, works
Research_Request__c queue for Sarah    🔴 SObject NOT deployed
RM's queue + inquiry context panel     ✅ QueuesPanel.tsx exists
Follow-up trade path                   🟡 = Narrative 5's gates
```

**Verdict:** Narrative 2 is HALF-WIRED. "Client inquiry → RM queue" works if you pre-seed the inquiry. "RM requests research from Sarah" does NOT work (no `Research_Request__c` and no rm-handoff skill).

### Narrative 3 — Risk Alert (system → RM → Client)

Design doc itself says: "roadmap, shown as slide, not live." Honest deferral. `compliance_sweep` skill exists but calls an undeclared `dynamodb` MCP server. `Client_Alert__c` SObject not deployed.

**Verdict:** Run it as a slide. Do not demo live.

### Narrative 4 — Demand Signal (behavior → research agenda)

Design doc itself says: "roadmap, shown as slide, not live." Sarah's UI has a "Client demand signals" tab that shows pre-seeded rows. No clustering algorithm built.

**Verdict:** Already scoped as slide. No drama.

### Narrative 5 — Large Liquidation (full 7-gate spine)

```
Needs                                  Built?
─────                                  ──────
action_specialist serial-by-design     ✅ topology marks it serial
7-gate tool-use loop                   ✅ tool_dispatch.py enforces
  compliance → HITL → dual-auth →
  mulesoft (submit) → mulesoft (wire)
  → audit
OFAC SDN screen hard-branch             ✅ in mulesoft_api/actions.py
HITL HMAC tokens, 5-min TTL, plan_hash  ✅ in hitl/_tokens.py
Dual-auth $500K / $100K thresholds      ✅ logic exists
Senior_Compliance_Approver permset      ✅ deployed
SevenGateTracker lights up gate-by-gate 🔴 BACKEND DOESN'T EMIT
  on the advisor screen                    gate events live
Audit cross-stitch (brief→trade→wire)   ✅ fields exist in IR_Audit_Log__c
MuleSoft submit_order → Alpaca          🔴 Mule not deployed to CloudHub
MuleSoft initiate_wire → Dwolla         🔴 Mule not deployed
MuleSoft order_status_webhook callback  🔴 path mismatch would 404
Dual-auth Expires_At__c timeout         🔴 never written
```

**Verdict:** Narrative 5 has the MOST real code and the MOST visible blockers. The trust spine IS real in code. The visible live tracker, the MuleSoft pipeline, and the fill confirmation are all broken or unwired. Fixes needed: ~1 day of focused work to make it visually land.

---

## 7. Stages and tools per narrative — summary tables

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                        NARRATIVE 1 — Earnings Morning                     ║
╠═══════════╦══════════════════════╦═══════════════════════╦════════════════╣
║ Stage     ║ Tool / Skill         ║ External              ║ Real?          ║
╠═══════════╬══════════════════════╬═══════════════════════╬════════════════╣
║ Plan      ║ research_orchestrator║ Bedrock Sonnet 4.6    ║ 🔴 untested    ║
║ Fanout    ║ market_specialist    ║ Finnhub, market-data  ║ 🔴 502+placeh. ║
║           ║ filings_specialist   ║ EDGAR, sec-edgar MCP  ║ 🔴 502         ║
║           ║ sentiment_specialist ║ Tavily, news-search   ║ 🔴 502+placeh. ║
║           ║ compliance_specialist║ restricted_list.json  ║ ✅ local       ║
║           ║ statement_specialist ║ XBRL parser           ║ ✅ local       ║
║ RAG       ║ rag_retrieve         ║ Titan v2, Cohere 3.5  ║ 🟡 stubs only  ║
║ Synth     ║ orchestrator + harns ║ Sonnet 4.6            ║ 🔴 untested    ║
║ Publish   ║ publish_brief        ║ Salesforce MCP        ║ 🔴 502         ║
║ Audit     ║ audit_logging        ║ Salesforce MCP        ║ 🔴 502         ║
║ Trace     ║ Langfuse client      ║ Langfuse cloud        ║ ✅ wired       ║
║ UI        ║ ResearchTerminal     ║ streaming + citations ║ 🟡 chrome only ║
╚═══════════╩══════════════════════╩═══════════════════════╩════════════════╝

╔═══════════════════════════════════════════════════════════════════════════╗
║                     NARRATIVE 5 — Large Liquidation                       ║
╠═══════════╦══════════════════════╦═══════════════════════╦════════════════╣
║ Stage     ║ Tool / Skill         ║ External              ║ Real?          ║
╠═══════════╬══════════════════════╬═══════════════════════╬════════════════╣
║ ①Guard    ║ Bedrock Guardrails   ║ Bedrock Guardrails    ║ ✅ ready v1    ║
║ ②MNPI     ║ MNPIFilter scrub     ║ local                 ║ ✅ both paths  ║
║ ③Comp     ║ compliance_screening ║ restricted_list.json  ║ ✅ local       ║
║ ④HITL     ║ hitl skill           ║ HMAC token, plan_hash ║ ✅ code        ║
║ ⑤DualAuth ║ dual_auth skill      ║ IR_Pending_Approval__c║ 🟡 no TTL      ║
║ ⑥Wire     ║ mulesoft_api skill   ║ OFAC JSON + Mule API  ║ 🔴 Mule undepl ║
║ ⑦Audit    ║ audit_logging skill  ║ IR_Audit_Log__c       ║ 🟡 Lambda 502  ║
║ Submit    ║ Mulesoft submit-order║ Alpaca paper          ║ 🔴 Mule undepl ║
║ Callback  ║ order-status-webhook ║ Mule → SF Position    ║ 🔴 path mismatch║
║ Tracker   ║ SevenGateTracker UI  ║ WebSocket events      ║ 🔴 NO EVENTS   ║
╚═══════════╩══════════════════════╩═══════════════════════╩════════════════╝
```

---

## 8. Auth — the six-boundary promise vs reality

| Boundary | Promised | Built |
|---|---|---|
| 1 Okta/Azure AD → session | OAuth 2.0 PKCE | ❌ **No IdP code exists at all.** Grep finds zero implementations of PKCE, code_verifier, JWKS validation. `.env.example` declares `IDP_ISSUER/IDP_CLIENT_ID/IDP_CLIENT_SECRET` but nothing consumes them. SPA ships with hardcoded `dev-bootstrap-token` + `dev-principal`. |
| 1b Session HMAC token | HMAC-SHA256 mint/verify | 🟡 `SessionTokenMinter.mint()` + `.verify()` exist, keyed from env. BFF calls `verify()` on every REST request. **`PersonaCoordinator.run_turn()` never calls `verify()`** — WebSocket path trusts whatever principal_id the channel adapter injects. Grep-confirmed: zero production callers of `SessionTokenMinter.verify()`. |
| 2 Skill allowlist | Per-persona, fail-closed, audit row on deny | 🟡 Tool-use loop at `tool_dispatch.py:295-310` DOES enforce per-agent `tool_allowlist` for model tool calls. Returns `tool_not_allowed` toolResult. This IS real. But `GateEnforcer.check_tool()` is defined separately and never called. Two paths: one real, one dead. |
| 3 MCP API key + principal | X-MCP-API-Key + X-Principal-Id | ✅ Real. `_base/mcp_server.py:194-198` extracts principal_id + agent_id + persona + session_id from headers. API key enforced unless `MCP_DEV_MODE=true`. |
| 4 SF per-user OBO | JWT-Bearer OAuth, subject from principal_id | ✅ Real. `sf-auth-proxy/app.py:70-95` uses `subject_pattern.format(principal_email=principal_id)` for JWT `sub`. Private key in Secrets Manager. Caching 2h. Verified live earlier. |
| 5 MuleSoft client_credentials | OAuth2 + principal in header + policy stack | 🟡 MuleSoft client_credentials works (earlier live probe confirmed). Policy stack JSON has `REPLACE_WITH_LAMBDA_NAT_EIP/32` placeholder — **IP allowlist effectively disabled** until someone substitutes `54.88.221.141/32`. |
| 6 Data-layer authz | SF sharing rules, Aurora RLS, MuleSoft audit, Langfuse RBAC | 🟡 SF sharing rules real (three permsets deployed Apr 28). Aurora RLS policies real in SQL but never deployed (stack rolls back). MuleSoft audit real. Langfuse RBAC is Langfuse-side operator config. |

**Okta/Cognito specifically.** Not wired. The SPA literally says in a comment: *"in production this comes from the channel adapter which performs OAuth 2.0 PKCE against VITE_IDP_ISSUER before this SPA loads."* That channel adapter layer does not exist in the repo. The pre-v3 AgentCore container (`openclaw_agent-QTvJf03edt`, Apr 9) that's deployed in AWS is older than the v3 trust layer anyway.

---

## 9. The "mockery drama" inventory

Direct contradictions between design doc and built code — these would collapse if a reviewer pokes.

1. **"Real Bedrock reasoning"** — 244 backend + 104 frontend tests all run against `StubBedrockClient`. Zero turn has ever gone through real Sonnet 4.6 end-to-end.
2. **"15-second briefs (vs 40s)"** — parallelism structure is real. 15s is a guess — never measured against real Bedrock.
3. **"Cohere Rerank 3.5 + Titan v2 embeddings"** — default wiring is `StubEmbedder` (64-dim hash) + `StubReranker` (Jaccard). Real classes exist but require explicit injection that no production code does.
4. **"Knowledge Base with SEC filings"** — pipeline code exists. Bedrock KB stack rolled back twice. **Zero documents in any KB in the account.** Live probe: `aws bedrock-agent list-knowledge-bases` returns `[]`.
5. **"Aurora pgvector with Salesforce sharing-rule RLS"** — Aurora stack has rolled back 4x in 3 hours. RLS SQL file is well-written but has never run against a database.
6. **"Okta / Azure AD OAuth PKCE"** — zero IdP-handshake code. SPA uses `sessionToken: 'dev-bootstrap-token'`.
7. **"17 agents"** — `_SKILL_MODULES` has 14 skills, `topology.py` has 14 agents. The doc you're looking at (`v3-narrative-arc.md`) still says 17. Documentation drift, not a code defect.
8. **"Trust enforcement at the runtime boundary — cannot be accidentally bypassed"** — partially true. Tool-use loop fail-closes on tool allowlist. But MCP server allowlist (`mcp_allowlist`) is not enforced anywhere — `GateEnforcer.check_mcp()` is defined, never called.
9. **"Real WhatsApp Business / WeChat"** — web mockup. No Meta API, no SMS gateway, no WeChat. Design acknowledges this contingency, so it's honest.
10. **"HITL TokenStore — single-use, Redis-ready"** — the store is `Dict[str, float]` in-memory. On AgentCore pod restart, all minted tokens become usable again.

---

## 10. What IS defensible to show the panel

If narrated carefully, these ARE real and on-camera:

1. **Three-persona multi-agent topology** — show `topology.py`, 14 agents, three orchestrators with distinct system prompts.
2. **Tool-use dispatch with fail-closed allowlist** — show `tool_dispatch.py:280-310`. The LLM tries to call a non-allowlisted tool → code returns `tool_not_allowed` toolResult. This is runtime-enforced, not prompt.
3. **Seven-gate code order on write path** — show the serial calls in `mulesoft_api/actions.py` and `dual_auth/actions.py`. OFAC is a hard branch. Audit row fires on every outcome.
4. **MNPI filter server-side on CRM MCP and on tool-use output** — show `salesforce-crm/_mnpi_redact.py` + the scrub at `coordinator.py:450`. Bypass-resistant.
5. **SF per-user OBO to Salesforce** — show `sf-auth-proxy/app.py`. Real JWT-Bearer flow. Verified live against the target org.
6. **Langfuse span discipline + cross-persona stitching** — real client wiring with fallback stub. Session/turn/persona/skill/tool_call taxonomy is disciplined.
7. **Deterministic financial calculators** — `_calculators.py`. Actual math, not LLM pretend.
8. **Salesforce Wave 3 deployment** — 85/85 components, 99% Apex test pass rate.
9. **Frontend components** — SLDS imports, SevenGateTracker, CitationChip, exponential backoff WebSocket, optimistic approval with rollback toasts, 4-tier error handling.
10. **Trust primitives exist even if not all wired** — `SessionTokenMinter`, `GateEnforcer`, `MNPIFilter`, HITL token store all have proper implementations.

---

## 11. What you should NOT claim on stage

Direct contradictions that would collapse under a reviewer's question.

1. ❌ "Every query goes through real Bedrock Sonnet 4.6." → MCPs 502; no end-to-end turn has ever run real.
2. ❌ "Sessions are verified at AgentCore with HMAC tokens." → WebSocket path never calls `verify()`.
3. ❌ "Okta / Azure AD OAuth PKCE authenticates every user." → No IdP code exists.
4. ❌ "Hybrid RAG with Titan v2 + Cohere Rerank." → Default is StubEmbedder + StubReranker.
5. ❌ "Bedrock Knowledge Base has the filings corpus indexed." → KB stack rolled back; zero KBs.
6. ❌ "Aurora pgvector with row-level security for research corpus." → Stack rolled back 4x.
7. ❌ "Every MCP call is allowlist-checked at the runtime boundary." → Only tool names are; MCP server names are not.
8. ❌ "Order fills auto-update Position__c via webhook." → Webhook path mismatch, will 404.
9. ❌ "17 agents." → 14 agents.
10. ❌ "Dual-auth has 30-min approval TTL." → No `Expires_At__c` writes; approvals hang forever.

---

## 12. Fix plan to close the gap

```
╔═════════════════════════════════════════════════════════════════╗
║  PRIORITY     TASK                               EFFORT         ║
╠═════════════════════════════════════════════════════════════════╣
║  P0 (must do before any live turn works)                        ║
║  ───                                                            ║
║  Fix _base Lambda layer (add python/ wrapper)    5 min          ║
║  Fix Aurora SchemaMigrator (SQL → S3 asset)      15 min         ║
║  Fix KB stack (extend OSS index retry timeout)   30 min         ║
║  Redeploy SAM + CDK                              15 min wall    ║
║  Populate Finnhub + Tavily SSM keys              5 min (if keys)║
║                                                                 ║
║  P1 (must do for stage-quality live events)                     ║
║  ───                                                            ║
║  Emit gate_started/passed/failed over WebSocket  45 min         ║
║    from orchestration/coordinator.py                            ║
║  Fix BFF /api/source_chunk/{id} handler          1 hr           ║
║  Fix webhook path mismatch (Narrative 5)         10 min         ║
║  Wire BedrockTitanEmbedder + CohereReranker      30 min         ║
║    as default when env keys present                             ║
║                                                                 ║
║  P2 (honest narrative tightening)                               ║
║  ───                                                            ║
║  Add dev login page OR pre-brief Okta story      1 hr / 0       ║
║  Emit dual-auth Expires_At__c                    30 min         ║
║  Deploy 3 MuleSoft apps to CloudHub              2 hrs          ║
║  Substitute NAT EIP in policies JSON             30 sec         ║
║                                                                 ║
║  TOTAL                                           ~6-8 hours     ║
╚═════════════════════════════════════════════════════════════════╝
```

---

## 13. Bottom line

- **What you can defensibly claim today:** three-persona multi-agent topology, code-enforced tool allowlist, real OFAC hard branch, real HITL HMAC tokens, real MNPI scrub on both read and write paths, real SF per-user OBO (verified live), 85/85 Salesforce components deployed, 244 backend + 104 frontend tests passing against stubs.

- **What is "mockery drama" in the current build:**
  1. MCP Lambdas all return 502 — nothing actually talks to Bedrock, EDGAR, Tavily, or Salesforce end-to-end.
  2. No Knowledge Base, no Aurora pgvector — RAG is hash-based pretend retrieval.
  3. No IdP handshake — SPA uses hardcoded dev token.
  4. SevenGateTracker renders chrome but backend never emits gate events live.
  5. Citation chips click through to empty responses.
  6. MuleSoft is code-only, not deployed.
  7. Narrative 2's `rm-handoff` skill doesn't exist; `Research_Request__c` is not deployed.

- **The gap between design doc and code is about 6–8 hours of focused work, not architecture.** Nothing is missing at the design level. The wiring is 85% there and 15% illusion.

*— assessment closed out 2026-04-29.*
