# 006 V3 — Original Story + Narratives vs Current Deployment: Deviation Ledger

> **Date:** 2026-04-29 ~12:05 UTC
> **Question:** What's the original v3 story, and how much does the current deployment deviate?
> **Method:** read every v3 design doc (`v3-narrative-arc.md`, `v3-demo-choreography.md`, `v3-reproducibility-plan.md`, `v3-scalability-and-hooks-assessment.md`, `v3-live-traversal-ui-design.md`, `v3-build-status.md`) + live probes of the deployed stack + code paths that would fire during the advertised narratives
> **Scope:** v3 only. No v2 comparison.

---

## 1. The original story — in one paragraph

> **"Workflow 360 — research to advisory to client to settled trade, all on one agent runtime, all audited, with regulated hops gated behind MuleSoft where compliance officers expect them."** Three personas (Sarah the analyst, the RM, the client), one OpenClaw runtime on Bedrock AgentCore, 17 agents (3 orchestrators + 14 specialists) in an orchestrator-workers topology. Writes go through a serial seven-gate spine (Guardrails → MNPI → compliance → HITL → dual-auth → MuleSoft → audit). Reads fan out via `asyncio.gather`. Salesforce is the single system of record and the cross-persona handoff surface. Five demo narratives chain: earnings morning, client-drives-research, risk-alert, demand-signal, large-liquidation.

That's the story. Everything else in the design docs is support for that story.

---

## 2. The seven design commitments and their deployment state

| # | Commitment (verbatim from narrative arc) | Deployed today? | Deviation |
|---|---|---|---|
| 1 | **Three personas, one runtime, zero direct agent-to-agent communication. Every cross-persona interaction lands in a Salesforce SObject.** | 🟡 partial | AgentCore `openclaw_v3_agent-o72dx396I0` READY. Research_Brief__c and Client_Inquiry__c rows wrote live today. BUT Published_At__c is null on every brief, so the Platform Event that makes it cross-persona **never fires**. Handoff is broken in live traffic. |
| 2 | **Orchestrator-workers topology via asyncio.gather, visible 5-way parallel fanout in Sarah's audit strip.** | 🟡 partial | Code is real, fanout is real (verified in 26s live turn). BUT the audit strip in the deployed SPA can't show it — CloudFront serves v2's bucket, not v3's. Parallelism is there, panel can't see it. |
| 3 | **Seven-gate serial spine on writes, code-enforced not prompt-advisory.** | 🟡 partial | Code is real in `action_specialist` via `run_tool_loop()`. BUT MuleSoft is not deployed to CloudHub, so gates 6-7 (mulesoft_api + audit) cannot complete a full write path live today. |
| 4 | **Controlled autonomy — every LLM decision has a visible trace. Seven-gate tracker lights up on stage.** | 🔴 not live | Frontend components exist (`SevenGateTracker.tsx`). Backend emits **zero** `gate_started`/`gate_passed`/`gate_failed` WebSocket events. Tracker renders grey chrome that never lights up. |
| 5 | **Hybrid RAG: BM25 + Titan v2 + section-aware + Cohere Rerank, citation-bound generation with unsourced-sentence stripping.** | 🟡 partial | KB side is live (784 chunks from 10 real filings, Titan v2 embeddings, real retrieve API works). BUT `rag_retrieve` skill uses `StubEmbedder` + `StubReranker` by default; real Titan/Cohere code exists but isn't injected at the specialist level. Citation-enforcement harness exists in `research_orchestrator` prompt; untested in live turn. |
| 6 | **Salesforce is the cross-persona exchange: `Research_Brief__c`, `Client_Inquiry__c`, `IR_Audit_Log__c` with cross-stitched links.** | 🟡 partial | 85/85 SF components deployed. 2 Research_Brief__c rows live. 1 Client_Inquiry__c live. **But `IR_Audit_Log__c` is missing 3 of the stitching fields: `Agent_Id__c`, `Session_Id__c`, `Research_Brief_Id__c` — and zero audit rows landed from today's live turn.** The "cross-stitched audit trail" story cannot be demonstrated. |
| 7 | **One IdP. Okta or Azure AD OAuth PKCE.** | 🔴 not live | Zero IdP code. SPA boots with `sessionToken: 'dev-bootstrap-token'`. Channel adapter layer that would mint the session token doesn't exist. |

---

## 3. The five narratives — deployed runnability

### Narrative 1 — Earnings Morning *(analyst → RM → client)*

**Story:** *"It's 6:45 AM Singapore. NVDA reports in 73 minutes. Sarah types one query. 5 specialists fan out in parallel. 15-second brief published. RM opens Salesforce at 7:15. Client asks on WhatsApp at 9:00. Same research cited across three personas in under 2.5 hours."*

| Promised stage | Deployed? | Deviation |
|---|---|---|
| Sarah types query, Bedrock Guardrails input scan | 🟡 | Runtime live. Guardrail READY (id `nlouzhamlv7h` v1). Not verified fires on input today. |
| 5 specialists fan out in parallel via asyncio.gather | 🟢 | Verified live in 26-second NVDA turn. |
| market-data MCP → Finnhub live quote | 🟢 | Live. NVDA=$213.17 probed successfully. |
| sec-edgar MCP → 10-Q risk factors from EDGAR | 🟢 | Live. sec-edgar MCP responds, 10 real 10-K/10-Q HTML files ingested. |
| news-search MCP → 30-day sentiment via Tavily | 🟢 | Tavily key real. |
| compliance-screening skill → restricted list + MNPI scan | 🟢 | Ran live in 26s turn (returned ALLOW). |
| Sonnet 4.6 composes brief with citation harness | 🟡 | Produced brief-shaped output in 26s. But `market_specialist` response was Python code describing MCP calls, not tool-use blocks. **Specialists bypass the tool-use loop** (`serial_by_design=False` on research specialists). So RAG/skills don't actually fire. |
| publish-brief writes Research_Brief__c | 🟢 | Verified: RB-00000000 (NVDA), RB-00000001 (MSFT) landed today. |
| Published_At__c set → Research_Brief_Published__e Platform Event | 🔴 | `Published_At__c = null` on both briefs. PE trigger gates on that field. **No cross-persona notification fires.** |
| audit-logging writes IR_Audit_Log__c with Action=RESEARCH_PUBLISHED | 🔴 | Zero audit rows from today's live turn. audit_logging skill not on research specialists' allowlist. |
| 15-second briefs (vs 40s single-agent baseline) | 🟡 | 26s measured. 2 of 5 specialists timed out — plain-converse specialists have no tool budget discipline. |
| RM sees call list with inline citation of brief, via Data Cloud DLM join | 🔴 | DLM join config not verified in new-org. RM screen in SPA unreachable via CloudFront (wrong origin). |
| Client WhatsApp message → liaison returns brief-cited answer with disclaimer | 🟡 | Client_Inquiry__c wrote today (type=L2, channel=Email, not WhatsApp). ClientChannel.tsx exists but unreachable via CloudFront. |

**Verdict:** Narrative 1 is **65% live end-to-end**. The fanout happens. The brief writes. But:
- The specialists hallucinate code instead of calling tools (tool-use bypass bug)
- Publish doesn't fire the Platform Event (field bug)
- No audit row is produced (field drift + allowlist)
- SPA serves v2 frontend (CloudFront origin bug)

### Narrative 2 — Client Question That Drives Research *(client → RM → analyst → RM → client → trade)*

**Story:** *"Client asks about semis. Client-liaison writes Client_Inquiry__c to RM queue. RM creates Research_Request__c for Sarah. Sarah runs the brief. RM sees it, tailors, responds. Client says 'do it.' ActionPlan → HITL → compliance → MuleSoft → filled in 40 minutes."*

| Stage | Deployed? | Deviation |
|---|---|---|
| Client message → client-liaison classifies as beyond-FAQ | 🟡 | liaison_orchestrator code exists; live turn has not been taken |
| `rm-handoff` skill writes Client_Inquiry__c | 🔴 | **The `rm-handoff` skill does not exist in the codebase.** Narrative arc even footnotes it as "handled by the client-liaison system prompt" — but that means it's prompt-only, not a skill. |
| `Research_Request__c` SObject to queue Sarah's new work | 🔴 | **SObject not in deployed metadata.** Narrative 2's "RM creates Research_Request__c" has no target table. |
| Sarah accepts request, runs brief, publishes | 🟡 | Would work via direct query but there's no queue mechanism for Sarah to see the request |
| RM tailors response, client approves, trade fires | 🟡 | Same gates as Narrative 5 — and MuleSoft undeployed |

**Verdict:** Narrative 2 is **~25% live**. The two load-bearing pieces (`rm-handoff` skill, `Research_Request__c`) are both missing. Narrative arc itself scoped `rm-handoff` as prompt-only, so this is partly by design, but then the narrative in the story can't complete — there's no queue for Sarah to pull from.

### Narrative 3 — Risk Alert *(system → RM → client)*

**Story (with honest deferral in the doc):** *"Roadmap, shown as slide, not live. A `Simulate NVDA -8%` button inserts alert rows. RM gates whether client-liaison auto-responds."*

| Stage | Deployed? | Deviation |
|---|---|---|
| Scheduled `compliance-sweep` on EventBridge | 🔴 | By design: V4 |
| Demo-button-triggered alert rows | 🔴 | `compliance_sweep` skill exists but calls `server="dynamodb"` which isn't declared in `openclaw.json` MCP servers. MCPError on invocation. |
| `Client_Alert__c` SObject | 🔴 | **Not in deployed metadata.** |
| RM gate decides auto-send policy | 🔴 | No Client_Alert__c to gate |
| Client-liaison auto-responds with volatility framing | 🔴 | Dependent on above |

**Verdict:** Narrative 3 is **0% live**. The doc is honest that this is roadmap — but the slide shown today would claim the RM-gate workflow is "real and runs off Client_Inquiry__c with type=alert" which is partly but not fully true. The SObject class used is Client_Inquiry__c not Client_Alert__c, so this narrative needs to be renarrated on stage if shown.

### Narrative 4 — Demand Signal *(clients aggregate → system → analyst → RMs → clients)*

**Story (with honest deferral in the doc):** *"Roadmap, shown as slide. Sarah's 'client demand signals' tab shows pre-seeded rows. Behavioral clustering is V4."*

| Stage | Deployed? | Deviation |
|---|---|---|
| Client inquiries cluster into research-demand signals | 🔴 | By design: V4 |
| Sarah's terminal UI shows the demand tab | 🔴 | Frontend build is Apr-27 on v3 bucket; CloudFront serves v2 bucket; the v3 UI is unreachable |
| `Research_Suggestion__c` SObject | 🔴 | **Not in deployed metadata** |

**Verdict:** Narrative 4 is **0% live**. Design is honest about this. Demo plan is to talk through a pre-seeded scenario. That's defensible — just don't click buttons.

### Narrative 5 — Large Liquidation *(full 7-gate spine)*

**Story:** *"RM says 'liquidate Patel's NVDA, wire $1.2M to HSBC Singapore.' Compliance passes. Dual-auth triggered ($1.2M > $500K trade AND > $100K wire). HITL gate 1: RM approves. HITL gate 2: senior compliance. OFAC screens. Alpaca fills. Dwolla wires. 7 minutes, 2 humans, 1 machine, 4 external systems, 1 audit trail."*

| Stage | Deployed? | Deviation |
|---|---|---|
| RM types liquidation instruction | 🟡 | `advisor_orchestrator` routes to `action_specialist` |
| Agent builds ActionPlan | 🟢 | Code exists |
| ①Guardrails screens | 🟢 | Guardrail READY |
| ②MNPI filter | 🟢 | Both read and write paths scrub (code confirmed) |
| ③Compliance screening | 🟢 | Local skill runs deterministically |
| ④HITL — HMAC token minted, 5-min TTL, plan_hash bound | 🟢 | Code real (`hitl/_tokens.py`) |
| ⑤Dual-auth — second HMAC token by Senior_Compliance_Approver | 🟡 | Logic exists, but `Expires_At__c` never written → approvals hang forever |
| ⑥MuleSoft submit-order → Alpaca paper | 🔴 | MuleSoft apps not deployed to CloudHub. `mulesoft-actions` MCP exists but has nothing to call. |
| ⑥MuleSoft initiate-wire → Dwolla sandbox, OFAC SDN | 🔴 | Same |
| ⑦Audit row cross-stitched with research_brief_id, linked_trade_id, linked_wire_id | 🔴 | 3 stitching fields missing from SObject. OFAC hard-branch is real in code. |
| SevenGateTracker lights up gate-by-gate on RM's screen | 🔴 | Backend emits no gate events |

**Verdict:** Narrative 5 is **~35% live**. Every gate exists as code. The live layer has Guardrails, MNPI scrub, compliance, HITL, dual-auth logic, OFAC branch. Missing: MuleSoft deploy (so no real trade/wire), audit field drift, dual-auth TTL, gate events on the wire, working UI. Cannot be demoed live today.

---

## 4. The 18 deliverables — what landed

The narrative arc's deliverables list (re-numbered to match the doc's §9):

| # | Deliverable | Designed | Built | Deployed |
|---|---|---|---|---|
| 1 | Orchestrator-workers topology (3 + 14 = 17 → 14 actual) | 🟢 | 🟢 14 | 🟢 14 |
| 2 | Inter-agent message schema (Pydantic) | 🟢 | 🟢 | 🟢 |
| 3 | fsi-research persona (6 agents) | 🟢 | 🟢 | 🟢 runtime, 🔴 UI |
| 4 | fsi-advisor persona (5 agents) | 🟢 | 🟢 | 🟢 runtime, 🔴 UI |
| 5 | fsi-client-liaison persona (3 agents) | 🟢 | 🟢 | 🟢 runtime, 🔴 UI |
| 6 | publish-brief skill | 🟢 | 🟢 | 🟡 runs but doesn't set Published_At__c |
| 7 | rag-retrieve skill (BM25 + Titan + structural + Cohere) | 🟢 | 🟢 code | 🟡 stubs run by default; real embedders unsed |
| 8 | financial-statement-analysis skill | 🟢 | 🟢 | 🟡 code live but specialist bypasses tool-use |
| 9 | portfolio-analytics skill | 🟢 | 🟢 | 🟡 same |
| 10 | scenario-modeling skill | 🟢 | 🟢 | 🟡 same |
| 11 | suitability-check skill (deterministic) | 🟢 | 🟢 | 🟡 same |
| 12 | client-summary skill | 🟢 | 🟢 | 🟡 same |
| 13 | research-awareness skill | 🟢 | 🟢 | 🟡 same |
| 14a | Research_Brief__c SObject | 🟢 | 🟢 | 🟢 deployed, 2 rows today |
| 14b | Client_Inquiry__c SObject | 🟢 | 🟢 | 🟢 deployed, 1 row today |
| 14c | IR_Audit_Log__c + 2 new fields | 🟢 | 🟢 | 🔴 3 load-bearing fields still missing (Agent_Id__c, Session_Id__c, Research_Brief_Id__c) |
| 15 | Filings corpus pipeline (EDGAR → Titan v2 → Bedrock KB) | 🟢 | 🟢 | 🟢 **KB active, 784 chunks ingested, retrieval verified live** |
| 16 | Research corpus pipeline + CDC (Aurora pgvector) | 🟢 | 🟢 | 🟡 Aurora + RLS deployed; CDC Lambda not wired to EventBridge |
| 17a | initiate-wire MuleSoft Process API | 🟢 | 🟢 | 🔴 Maven project exists, not deployed to CloudHub |
| 17b | order-status-webhook MuleSoft Process API | 🟢 | 🟢 | 🔴 Same + path-mismatch bug |
| 18a | Sarah's terminal + RM's queue screen | 🟢 | 🟢 | 🔴 Built into S3 bucket, **but CloudFront serves the WRONG bucket (v2's)** |
| 18b | Client channel-native experience | 🟢 | 🟢 | 🔴 Same |
| 18c | Langfuse span discipline + auth + glue | 🟢 | 🟢 | 🟡 Langfuse client wired, cross-persona stitch untested today |

**Count:**
- **Designed:** 18 items
- **Built (code in repo):** 18 items
- **Deployed green:** 5 items (topology, message schema, 3 personas, filings pipeline, Research_Brief__c, Client_Inquiry__c)
- **Deployed yellow (partial):** 11 items
- **Deployed red (blocked or broken):** 6 items (IR_Audit_Log__c drift, initiate-wire, order-status-webhook, frontend misrouting, 7-gate events, auth)

---

## 5. Demo choreography — Act-by-Act alignment

The demo choreography doc commits to a specific four-act 15-minute script. How does each Act hold up today?

### Act 0 — Cold Open (60 seconds)
> *"Screen is already on Sarah's terminal. Press Enter. Within 2 seconds, 5 tool-call spans open in parallel. Brief streams. Finishes at ~0:15."*

**Live reality today:** 🔴 blocked
- CloudFront serves v2 SPA, not v3. Sarah's terminal is not reachable via the advertised URL.
- Even if frontend were correct, SevenGateTracker shows grey chrome — no gate events flow.
- Turn takes 26s not 15s, with 2 of 5 specialists timing out.
- Specialist output is Python code, not real data — would show on screen as hallucinated code blocks.

### Act 1 — The Handoff (4 minutes)
> *"RM screen appears. Type 'Which of my clients have NVDA exposure above 5%?'. Result cites Sarah's brief as a clickable chip. Click chip → pane opens showing the brief. Client WhatsApp arrives. Liaison responds citing the brief."*

**Live reality today:** 🔴 blocked
- Same CloudFront issue.
- research_awareness skill exists but specialist bypasses tool-use — would generate code text, not a real SOQL→DLM join.
- Platform Event on brief publish is broken (Published_At__c null), so "RM sees brief" queue update doesn't actually fire.

### Act 2 — The Trust Spine (6 minutes, panel wildcard)
> *"Hand a panelist the keyboard. Any reasonable sell instruction. Seven gates light up in real time. Dual-auth triggers. OFAC screens. Alpaca fills. Dwolla initiates. Click the audit row → cross-stitched chain."*

**Live reality today:** 🔴 blocked
- Gate events don't emit live.
- MuleSoft not deployed → no real Alpaca, no real Dwolla.
- Audit row would be written with 3 stitching fields dropped silently.
- Panel demo would fall over visibly on the first Approve click.

### Act 3 — One More Thing (2 minutes)
> *"Client asks about ticker Sarah hasn't researched. Client_Inquiry__c appears in Sarah's queue. She accepts. New brief publishes. RM sees answer."*

**Live reality today:** 🔴 blocked
- `rm-handoff` skill doesn't exist.
- `Research_Request__c` SObject not deployed.
- Queue UI on Sarah's screen not reachable via CloudFront.

### Act 4 — Close with Three Numbers (2 minutes)
> *"1,600× analyst cost delta. 15 seconds to brief. 7 minutes from query to settled trade."*

**Live reality today:** 🟡 defensible with caveats
- 1,600× is cost arithmetic, not live.
- 15 seconds — live measurement is 26s with 2 timeouts.
- 7 minutes — cannot be demoed; MuleSoft not live.

---

## 6. The deviation summary — headline numbers

```
╔═══════════════════════════════════════════════════════════════╗
║ DIMENSION                 DESIGNED  BUILT  DEPLOYED  LIVE    ║
╠═══════════════════════════════════════════════════════════════╣
║ Depth commitments (7)        7/7    6/7    4/7      3/7     ║
║ Narratives (5)               5/5    5/5    1.75/5   0.5/5   ║
║ Deliverables (18 items)     18/18  18/18   5/18    5/18    ║
║ Auth boundaries (6)          6/6    6/6    4/6      3/6     ║
║ Demo Acts (5)                5/5    5/5    ~1/5     0/5     ║
║ Skills utilized in traffic  14/14  14/14  14/14     2/14    ║
╚═══════════════════════════════════════════════════════════════╝
```

Overall: **the story is intact, the code is 90%+ built, the deployment is ~75% up, but the live runnability of the narratives is ~20%.** The deviation is concentrated in four specific places:

1. **CloudFront origin** — serves v2's bucket → v3 UI unreachable
2. **Specialist tool-use bypass** — `_run_one()` branches on `serial_by_design` so only 1 of 14 agents uses skills via tool-use → research specialists generate code instead of calling tools
3. **Salesforce field drift** — IR_Audit_Log__c missing Agent_Id__c / Session_Id__c / Research_Brief_Id__c; publish_brief not setting Published_At__c → audit broken, PE doesn't fire
4. **MuleSoft CloudHub not deployed** → Narrative 5 wire/trade cannot run live

---

## 7. How to close the deviation — priority list

```
╔════════════════════════════════════════════════════════════════╗
║ #  FIX                                           EFFORT         ║
╠════════════════════════════════════════════════════════════════╣
║ 1  Repoint CloudFront origin → v3 bucket;                      ║
║    invalidate cache                               10 min        ║
║ 2  Rebuild SPA with live env URLs, upload        15 min         ║
║ 3  coordinator._run_one(): remove serial_by_design              ║
║    gate, ALL agents with tool_allowlist use                    ║
║    run_tool_loop()                                5 min         ║
║ 4  Bump specialist timeout 25s → 60s              5 min         ║
║ 5  Emit gate_started/passed/failed WebSocket     45 min         ║
║    events from coordinator                                     ║
║ 6  Backfill IR_Audit_Log__c metadata:            20 min         ║
║    Agent_Id__c, Session_Id__c, Research_Brief_Id__c            ║
║ 7  Fix publish_brief to set Published_At__c      15 min         ║
║ 8  Deploy MuleSoft apps to CloudHub               2 hrs         ║
║ 9  Align webhook path (Mule vs MCP)              10 min         ║
║ 10 Substitute NAT EIP in policies JSON           30 sec         ║
║ 11 Golden-turn rehearsal with real panel-style                 ║
║    query; verify all gate events fire, Platform                ║
║    Event fires, audit row lands with all fields  30 min         ║
╠════════════════════════════════════════════════════════════════╣
║ TOTAL TO MAKE NARRATIVE 1 DEFENSIBLE              ~2 hrs        ║
║ TOTAL TO MAKE NARRATIVE 5 DEFENSIBLE              ~4 hrs        ║
║ TOTAL TO HIT THE FULL 4-ACT CHOREOGRAPHY          ~5 hrs        ║
╚════════════════════════════════════════════════════════════════╝
```

---

## 8. The honest summary

**The original v3 story is defensible.** The architecture is coherent, the narratives are realistic, the design doc is explicit about what's roadmap vs in-scope, and the demo choreography follows good 2026 enterprise-AI playbook.

**The code built matches the design.** 18 of 18 deliverables exist in the repo. No architectural corners cut. Trust-spine code is real.

**The deployment has landed more than half of it.** 5 CDK stacks, Bedrock KB with real filings, Aurora with RLS, all 7 Lambdas serving real traffic, Salesforce 85/85 components, vendor APIs live, AgentCore v3 container READY.

**The gap is in the last mile — live runnability of the advertised narratives.**

The four deviation points (CloudFront origin, specialist tool-use bypass, Salesforce field drift, MuleSoft undeployed) are all short-effort fixes, none requiring redesign. ~5 hours of focused work and the 4-act demo choreography becomes executable as written.

Until those fixes land, the live system runs turns but the turns don't show the story. The panel would see a hallucinated-code brief without audit rows on a v2-styled UI, not the "fifteen seconds, five specialists, citation-bound brief" that the cold open promises.

**Net deviation from design: ~25% of the advertised user-visible behavior is missing in today's live deployment.** Mostly concentrated in UI wiring + one coordinator branch + Salesforce metadata drift + one undeployed wave. Everything else honors the design.

*— deviation ledger closed at 2026-04-29 ~12:10 UTC.*
