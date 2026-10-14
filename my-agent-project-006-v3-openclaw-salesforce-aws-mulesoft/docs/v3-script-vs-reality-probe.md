# 006 V3 — Script vs Reality Probe

> **Date:** 2026-05-01
> **Method:** code reads + design-doc triangulation (no live AWS or Salesforce calls from this session). Anchored in the Apr 29 2026 live-probe evidence in `v3-design-vs-built-vs-deployed-v2.md` and the May 1 diagnostic in `v3-pending-mock-vs-real.md` (both live-probed against the deployed stack).
> **Subject:** the 18-minute Workflow 360 demo script (META Q1 2026 Singapore morning narrative) — can it run live today, and what is the smallest gap?
>
> **Companion docs:** `v3-narrative-arc.md` (architecture), `v3-design-vs-built-vs-deployed-v2.md` (live probe), `v3-pending-mock-vs-real.md` (May 1 state), `v3-research-analyst-there-vs-not.md`, `v3-advisor-there-vs-not.md`, `v3-client-there-vs-not.md` (persona-level gaps).

---

## Section 1 — Probe methodology

**What I read:**
- `RUNBOOK.md` (all 938 lines) — deploy path, troubleshooting, P0 closure instructions
- `docs/v3-demo-readiness.md` — board-critical readiness report
- `docs/v3-pending-mock-vs-real.md` — May 1 live-probe diagnostic (canonical)
- `docs/v3-design-vs-built-vs-deployed-v2.md` — Apr 29 live-probe diagnostic
- `docs/v3-build-status.md` — autonomous build summary
- `docs/v3-p0-sf-obo-fix.md` — the single Salesforce OBO secret fix
- `docs/v3-p0-source-chunk-citation-drift.md` — research specialist citation bug
- `docs/v3-mulesoft-boot-crash-remediation.md` — MuleSoft historical + current state
- `openclaw/skills/publish_brief/actions.py` — to verify `Published_At__c` bug
- `openclaw/skills/audit_logging/actions.py` — to verify audit-field bug
- `openclaw/skills/rm_handoff/actions.py` — to verify Research_Request__c handling
- `frontend/src/v3/personas/ResearchTerminalV3.tsx`, `AdvisorWorkbenchV3.tsx`, `ClientChannelV3.tsx` — UI surface state

**What I did NOT do:**
- No live AWS calls (no credentials in this session)
- No live Salesforce SOQL
- No real-Bedrock smoke test
- No browser-based E2E

**What the probe docs I relied on DID do:**
- `v3-pending-mock-vs-real.md` captured a live HTTP turn against AgentCore v21 **~hours ago on 2026-05-01**
- Both probe docs report live evidence with curl command + exact response bodies
- The stack state as of those probes: AgentCore v21, SAM stack `openclaw-mcp-006-v3`, CloudFront `d2zs9nk4uc2dbx.cloudfront.net`, API Gateway `e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3`. All live and reachable.

**Where I found contradictions:** two, both material and flagged below. Both are cases where design docs lagged the code.

---

## Section 2 — The 18-minute narrative, moment by moment

Legend: ✅ works live · 🟡 works with caveat · ❌ does not work live today. Evidence is cited inline.

### Act 0 — Cold Open (0:00–2:00)

| # | Moment | What script needs | Code | Wiring | Deployed | Gap | Effort |
|---|---|---|---|---|---|---|---|
| 0.1 | Sarah's terminal already up, query pre-typed | V3 frontend routes to ResearchTerminalV3 via `?persona=research&v3=1` | ✅ `ResearchTerminalV3.tsx` | ✅ V3App router | ✅ CloudFront serves v3 bundle ([v3-pending §B1](./v3-pending-mock-vs-real.md#b1)) | None | 0 |
| 0.2 | Press Enter → audit strip "blooms — five spans open in parallel" | WebSocket must emit `tool_call_start` for 5 specialists concurrently | ✅ research_orchestrator uses asyncio.gather | 🟡 Events emitted; AuditStrip renders pills not a gantt | 🟡 Chips appear but serial-looking | **Specialist gantt not built** — the "parallel, not serial" claim lands as text pills, not a visual waterfall | **2.5 days** (data already on WS; need Visx renderer) |
| 0.3 | "Five sub-agents working concurrently — market, filings, sentiment, compliance, statement" | 5 specialists actually fan out | 🟡 Code-ready; **3/5 fire reliably** per [v3-pending §B2](./v3-pending-mock-vs-real.md#b2); **2 of 5 timeout** (filings + statement) | 🟡 Timeout 25s too aggressive | 🔴 Live turn evidence 2026-04-29: "gaps: filings_specialist(timeout), statement_specialist(timeout)" | **Two fixes needed:** raise per-worker timeout to 60s; wire specialists through `run_tool_loop()` so they emit real `toolUse` instead of hallucinated Python code (§4b of v2 probe) | **2 hours total** |
| 0.4 | Brief streams ~15 seconds, thesis on-screen | Sonnet reasoning + streaming | ✅ Real Bedrock Sonnet; N1 22s @ 10,052 tokens per May 1 probe | ✅ Streaming works | ✅ Proven live | None — though narrative says 15s, May 1 probe was 22s. Close enough for stage. | 0 |
| 0.5 | "Eleven cents" cost call-out | Langfuse trace with token cost | ✅ Scrubbing wrapper | ✅ Real Langfuse transport | 🟡 Emits; not surfaced in UI | Verbal narration only. Cost meter is P3, skip for demo. | 0 (narrate) |
| 0.6 | Citation chips populate; click opens source chunk side pane | `/api/source_chunk/{id}` returns real 10-Q chunk text | ✅ Frontend `StreamingText` citations | ✅ Backend `get_source_chunk` tool exists on sec-edgar MCP | ❌ **Returns empty stub** per [v3-p0-source-chunk-citation-drift.md](./v3-p0-source-chunk-citation-drift.md). Drawer shows "(source not available)". | **Two layers of fix:** (a) `get_source_chunk` Lambda implementation; (b) prompt fix so specialists cite real chunk IDs (`NVDA-000104581025000230-c0042`) not fabricated human-readable ones (`nvda-10q-20251026`) | **1.5-2 hours** |
| 0.7 | "Read with me" — highlighted thesis line with META + Alphabet + MSFT cross-asset comparison | Brief must contain this specific thesis shape with real numbers | 🟡 Sonnet will produce prose but needs anchors | 🟡 Depends on ingested filings + transcripts being present | ❌ **META Q1 2026 8-K + call transcript not ingested.** EDGAR backfill targeted at the 8 tickers never run per [RUNBOOK.md §T-5](./RUNBOOK.md) | **Ingest EDGAR 8-K (real, public) + drag-drop META call transcript PDF (real, IR-site).** Also ingest GOOGL/MSFT/NVDA/AVGO/QCOM 8-Ks. Ingestion Lambda + Textract handler already exist in `aws/data-pipelines/filings-corpus/`. | **2 hours** of ingestion runs |
| 0.8 | Brief lands as `Research_Brief__c` row (clickable, real SF record) | `publish_brief` writes to Salesforce | ✅ Full skill code in `openclaw/skills/publish_brief/actions.py` — **`Published_At__c` IS set** (line 99 writes `datetime.now(timezone.utc).isoformat()`) | 🟡 Skill → CRM MCP → sf-auth-proxy OBO chain | ❌ **SF OBO chain is 401'ing** per [v3-p0-sf-obo-fix.md](./v3-p0-sf-obo-fix.md). Secret `/006-v3/sf/bootstrap-creds` is empty (no client_id, no private_key). Writes return 401. | **One-time Salesforce Connected App setup** + populate secret. Detailed in v3-p0-sf-obo-fix.md §Steps 1-7. | **1 hour SF admin work + 5min AWS** |

**⚠ Contradiction flagged:** `v3-design-vs-built-vs-deployed-v2.md §4c` claims `publish_brief` sets `Published_At__c = null`. **That is wrong.** Reading the code directly: `openclaw/skills/publish_brief/actions.py` line 99 explicitly writes `datetime.now(timezone.utc).isoformat()` into the record. The live observation of null in the SF row is caused by the **OBO 401 failure** — the write is not reaching SF at all, so the audit and brief-publish code paths hit the degraded fallback. The Apr 29 probe misattributed this. The `v3-pending-mock-vs-real.md` doc gets it right: the root cause is the empty Secrets Manager bootstrap secret.

### Act 1 — The Handoff (2:00–6:30)

| # | Moment | What script needs | Code | Wiring | Deployed | Gap | Effort |
|---|---|---|---|---|---|---|---|
| 1.1 | "One hour later" — Yusuf's screen shows alert "4 households hold META above 5%" | `Research_Brief_Published__e` Platform Event fires → EventBridge → per-book concentration query → RM queue populated | ✅ Apex trigger `ResearchBriefTrigger` exists; fires on `Rm_Consumable__c=true AND Published_At__c != null` | ✅ Aurora CDC pipeline code exists per [v3-build-status.md](./v3-build-status.md) | ❌ **Depends on Act 0.8.** When OBO fails → brief never lands → PE never fires → RM queue stays empty. When OBO is fixed, PE fires. Aurora CDC pipeline **not deployed** per [v3-pending §B3](./v3-pending-mock-vs-real.md). | **Fixes Act 0.8 fixes this.** Additionally need CDC-side "who's impacted" query. For demo, hand-seed 4 households in SF + a stub flow. | **1 hour seed + Act 0.8 fixes** |
| 1.2 | "Different RMs see different counts — 4, 0, 14" | Per-book concentration query scoped via FSC sharing rules | ✅ SF sharing rules enforce this natively | ✅ sf-auth-proxy per-user OBO | ❌ **Advisor UI regressed to placeholder text "V3.1 roadmap"** per `AdvisorWorkbenchV3.tsx` lines 78-85. No queue column renders. | **Restore V2 ActionsQueueColumn component to V3**. V2 has a working implementation; V3 stubbed it. | **0.5 days** (copy/paste port) |
| 1.3 | Click Patel household → position panel + brief side-by-side | Client 360 populates with positions, allocations, IPS | 🟡 `client_summary` skill exists | ❌ **Client 360 column regressed** same as above — placeholder text "V3.1 roadmap" | ❌ Not rendered | **Restore V2 ClientContextColumn component.** Also need IPS allocation bar. | **0.5 days port + 2 days IPS bar** |
| 1.4 | Mrs. Patel sends WhatsApp "Should I be worried about META?" at 08:12 SGT | Confederate sends real WhatsApp to ClientChannelV3 thread | ✅ ClientChannelV3 render phone frame | ✅ WebSocket turn wire | 🟡 **Thread doesn't persist across refresh** — per code read. | Not blocker for demo (confederate sends live). But demo-day risk: if a page reload happens, context dies. | **1 day** persistence (optional for demo) |
| 1.5 | Reply lands in 11 seconds with cross-asset nuance, inline brief citation, 3 buttons | Haiku liaison produces response; rich message card renders | ✅ liaison_orchestrator code; faq_specialist uses Haiku | 🟡 Rich-card rendering absent; generic bubble only | ❌ **Three-button card not built** in `ClientChannelV3.tsx` | **Rich RM identity card** (Marcus avatar + 3 buttons). Use existing 2 hardcoded CTAs as starting point. | **1.5 days** |
| 1.6 | "Mrs. Patel taps **schedule a call**" | Button → `Client_Inquiry__c` write → RM queue entry | ✅ rm_handoff skill code (read `openclaw/skills/rm_handoff/actions.py`) | ✅ MCP chain to SF | 🟡 **Client_Inquiry__c DOES write** per [v3-pending §B1](./v3-pending-mock-vs-real.md#b1) — 3 rows today. But **RM queue column is a placeholder** (Act 1.2) so "the RM tab lights up" cannot land visually. | Fix 1.2 and this works end-to-end. | shares with 1.2 |

### Act 2 — The Trust Spine (6:30–13:00)

| # | Moment | What script needs | Code | Wiring | Deployed | Gap | Effort |
|---|---|---|---|---|---|---|---|
| 2.1 | Yusuf types "Trim Patel META 6.8→4.5, VWAP, US open" | Advisor action_specialist detects verb → DRAFT_ONLY mode | ✅ Two-turn architecture per [RUNBOOK §3.6](./RUNBOOK.md) | ✅ `/agent/invoke` + `/agent/approve` routes live | ✅ **Working live** — May 1 probe: advisor draft returns in 9.7s with action_plan per [v3-pending §B4](./v3-pending-mock-vs-real.md#b4) (was 25s Sonnet, now Haiku). | None. | 0 |
| 2.2 | 7 gates light up sequentially 3-5s each | `gate_started/gate_passed/gate_failed` WebSocket events per gate | ✅ `GatesTrackerV2` component consumes these | 🟡 **Gate events may not be emitted from coordinator** — frontend renders progressive disclosure when `pendingPlan` is set; the per-gate pulse depends on backend event emission | 🟡 Smoke test [7/8] shows action_plan; [8/8] shows `mulesoft: failed` honestly but doesn't verify gate-by-gate streaming | **Verify coordinator emits per-gate WS events** during approval. If not, add to coordinator's tool_loop wrapper (~45 min per [v3-design-vs-built-vs-deployed §9 item 9](./v3-design-vs-built-vs-deployed-v2.md)). | **45 min** |
| 2.3 | Gate ① Guardrails passed | Bedrock Guardrails on LLM input | ✅ Wired per Wave 2 improvements in [v3-build-status.md](./v3-build-status.md) | ✅ GuardrailInterventionError surfacing | 🟡 `BEDROCK_GUARDRAIL_ID` env var — need to confirm non-empty in AgentCore runtime | Verify env var set; else gates to safe no-op | **10 min** config check |
| 2.4 | Gate ② MNPI filter passed | Restricted-list + MNPI check | ✅ `compliance_screening` skill | ✅ Non-bypassable per [v3-demo-readiness.md](./v3-demo-readiness.md) | ✅ Live | None | 0 |
| 2.5 | Gate ③ Compliance and suitability passed | Real ticker + household IPS check | ✅ `compliance_screening` + `suitability_check` skills | 🟡 Suitability skill runs but result not visibly attached to UI card | 🟡 Result goes into gate trace; no Reg BI memo artifact | **Suitability memo card** (RM side) — not script-critical if narrated, but weak visually. | **2 days** (optional) |
| 2.6 | Gate ④ HITL — Yusuf clicks Approve | InlineActionCard in chat | ✅ Wired per [v3-build-status.md](./v3-build-status.md), optimistic approval | ✅ Cmd-Enter approves | ✅ Working — May 1 probe proves round-trip | None | 0 |
| 2.7 | Gate ⑤ Dual-auth — **second laptop**, different cursor, senior compliance officer | Distinct SF user with `Senior_Compliance_Approver` permset; visible second session | ✅ Pydantic `frozen=True` validator enforces distinct approvers | ✅ Permset metadata exists | 🟡 **No distinct UI surface** — both approvers use the same AdvisorWorkbenchV3. Panel sees two laptops with identical UIs. | **Low-effort workaround:** permset-scoped banner "Senior Compliance Approver" on the second laptop's header. **High-effort option:** dual-auth approver inbox. | **2 hrs workaround / 2 days full** |
| 2.8 | Gate ⑥ MuleSoft write passes; "Order accepted by PB. Staged 21:30 SGT. Trace #c41a-7e02" | MuleSoft `submit-order` CloudHub app live | ✅ Mule 4.9 code complete. All three apps fixed per [v3-mulesoft-boot-crash-remediation.md](./v3-mulesoft-boot-crash-remediation.md) with secure-properties refactor **done** | 🟡 Code-ready; never deployed to CloudHub | ❌ **Gate ⑥ returns `mulesoft: failed` on live runs** per smoke test [8/8]. MuleSoft mode is `mock`. | **Option A (honest):** keep `MULESOFT_MODE=mock` — writes audit rows, vendor-boundary narration is legitimate. **Option B (live):** `make verify-mule && make mule-deploy` + 3 Runtime Manager property configs per [RUNBOOK §3.3.1](./RUNBOOK.md). | **0 hrs (mock) / 3 hrs (live)** |
| 2.9 | Gate ⑦ Audit row written | `audit_logging` writes to `IR_Audit_Log__c` with full cross-stitching | ✅ Skill code has **all** cross-stitch fields: `Agent_Id__c`, `Session_Id__c`, `Research_Brief_Id__c`, `Client_Contact_Id__c`, `Linked_Trade_Id__c`, `Linked_Wire_Id__c`, `Approval_Token_Hash__c`, etc. per `openclaw/skills/audit_logging/actions.py` lines 166-181. | 🟡 Chain to SF hits same OBO 401 | ❌ **Zero audit rows from today** per May 1 SOQL. Skill hits `audit_write_degraded` branch → returns `AUDIT-LOCAL-xxx`. | **Same fix as Act 0.8** — populate OBO bootstrap secret. | shares with 0.8 |
| 2.10 | Click audit row → cross-stitched chain reveals all links | SOQL join `Research_Brief__c → IR_Audit_Log__c → HITL_Approval__c → MuleSoft order id` | ✅ Relationships designed; fields on objects | 🟡 Depends on all prior rows landing | ❌ If rows don't land, nothing to click | Fixes 0.8, 2.8, 2.9 make this work | shares |

**⚠ Contradiction flagged #2:** `v3-design-vs-built-vs-deployed-v2.md §4d` (Apr 29) claims 3 audit fields "are not in the SObject at all" — `Session_Id__c`, `Research_Brief_Id__c`, `Agent_Id__c`. The RUNBOOK §5.2 "Salesforce deploy fails with `INVALID_FIELD` on Agent_Id__c or Session_Id__c" section implies the fields ARE deployed via `V3_Audit_Fields` permset. And `salesforce/` metadata has them per [v3-build-status.md](./v3-build-status.md). **Most likely reality:** the fields exist in code/metadata; the silent-drop was caused by **OBO-401 preventing writes entirely**, not missing fields. The Apr 29 probe misidentified the symptom. The May 1 probe and v3-p0-sf-obo-fix.md get it right.

### Act 3 — One More Thing (13:00–15:00)

| # | Moment | What script needs | Code | Wiring | Deployed | Gap | Effort |
|---|---|---|---|---|---|---|---|
| 3.1 | Switch to Sarah's terminal; `Client_Inquiry__c` row appears in her queue (TSMC from different RM's client) | Inquiry → research-queue demand signal wire | 🟡 Client_Inquiry__c writes real (§B1); but `Research_Request__c` writes degraded to `RREQ-LOCAL-xxx` per [v3-pending §B3](./v3-pending-mock-vs-real.md#b3) | 🟡 OBO 401 on `Research_Request__c` create | ❌ Queue entry in Sarah's UI not wired | **Same OBO fix** clears this. **Also need** to wire research-queue demand-signal component. Currently pre-seeded slide only. | **1 hour** after OBO fix |
| 3.2 | Sarah clicks Accept → 5 specialists fan out → new brief | Same flow as Act 0 | ✅ Research orchestrator can handle any ticker | 🟡 TSMC is foreign — EDGAR doesn't carry Taiwanese filings | ❌ TSMC's 20-F (ADR form) is on EDGAR but not in backfill set | **Extend EDGAR backfill to include TSMC** (CIK 0001046179). Public form 20-F. | **15 min ingestion** |
| 3.3 | Publishes; 4 other RMs' screens visibly update | Platform Event fans out; multi-screen stage setup | ✅ Same publish_brief path | 🟡 Same OBO dependency | ❌ Same as Act 1.1 | Clears when OBO fixed | shares |

### Act 4 — Three Numbers (15:00–18:00)

All-verbal with slides. No product dependency. ✅ fully ready.

---

## Section 3 — The critical bugs inventory

Re-verified against code (May 1).

| # | Bug | Status | Evidence | Fix |
|---|---|---|---|---|
| 1 | `Published_At__c = null` on brief publish | **False positive (design-doc drift)** — code writes field. Apparent null is caused by OBO-401 preventing the write entirely. | `openclaw/skills/publish_brief/actions.py` line 99 | N/A — fix the OBO chain |
| 2 | 3 audit stitching fields "missing from SObject" | **False positive** — metadata has them via `V3_Audit_Fields` permset; silent drop is OBO-401 → degraded path | `openclaw/skills/audit_logging/actions.py` lines 166-181 + RUNBOOK §5.2 | N/A — fix the OBO chain |
| 3 | **OBO chain 401 on all SF writes** | **REAL and blocks everything in the live narrative** | [v3-p0-sf-obo-fix.md](./v3-p0-sf-obo-fix.md) | **1 hour SF admin + 5 min AWS** |
| 4 | Source chunk drill-down returns "(source not available)" | **REAL** | [v3-p0-source-chunk-citation-drift.md](./v3-p0-source-chunk-citation-drift.md) | 1-2 hrs (prompt + Lambda) |
| 5 | Specialists bypass tool-use loop → emit Python code | **REAL** on research path | [v3-design-vs-built-vs-deployed-v2.md §4b](./v3-design-vs-built-vs-deployed-v2.md) | 1-2 hrs |
| 6 | 25s per-worker timeout too aggressive under real Bedrock | **REAL** — filings + statement specialists drop | [v3-pending §B2](./v3-pending-mock-vs-real.md#b2) | 10 min (raise to 60s) |
| 7 | MuleSoft CloudHub apps never deployed | **REAL** — all code fixed + verified locally; deploy step not run | [v3-mulesoft-boot-crash-remediation.md Checklist](./v3-mulesoft-boot-crash-remediation.md#5-checklist--track-work-here) | 2-3 hrs OR keep `mock` mode |
| 8 | Coordinator `gate_*` WebSocket events may not emit | **UNVERIFIED** — frontend expects them; need to confirm backend side | — | 45 min verify+fix |
| 9 | CloudFront origin correct | **Fixed** — v2 bundle now served per [v3-pending §B4](./v3-pending-mock-vs-real.md#b4) | — | 0 |
| 10 | Advisor action_write 25s timeout | **Fixed May 1** — Haiku draft-only mode ships in AgentCore v21 | — | 0 |

**Real bugs blocking the narrative:** #3 (OBO), #4 (citation drill-down), #5 (specialist tool-use), #6 (timeout), plus #7 (MuleSoft) if we want live trade execution instead of mock mode.

**False positives in older design docs:** #1, #2. The code is correct; the chain is broken at the OBO layer. Fixing #3 fixes #1 and #2.

---

## Section 4 — What runs live today (honest, beat by beat)

If we ran the demo **right now, no more work, straight from current deployed state**:

**Act 0** — 🟡 **Partial.** Brief streams (22s, real Bedrock). 3 of 5 specialists return; 2 timeout visibly. `market_specialist` may emit Python code fragment per §4b. Citation chips appear but **every click shows "(source not available)"**. Brief does not persist to Salesforce (OBO 401). When presenter says "filed as a record" and clicks it — no record exists.

**Act 1** — ❌ **Dark for most of it.** Yusuf's screen has **placeholder text "V3.1 roadmap"** where the Actions queue should be and where Client 360 should be. Mrs. Patel's confederate message sends; liaison replies with a generic bubble in ~10s — no rich card, no 3 buttons. Client_Inquiry__c DOES write (unlike everything else — it goes through a different mock path). But the "RM queue lights up" moment on Yusuf's screen is the placeholder text, not a queue item.

**Act 2** — 🟡 **The money shot works.** Yusuf types the trim; draft returns in ~10s (Haiku). HITL card renders with approve button. 7-gate tracker is progressive-disclosure — **unclear whether per-gate events animate live** without backend verification. Click approve → /agent/approve runs. Gate ⑥ `mulesoft` returns **`failed` honestly** (mock mode reports this; live has no CloudHub apps). Gate ⑦ `audit` returns success at the envelope level but **no `IR_Audit_Log__c` row writes** (OBO 401) — so clicking the audit row afterward reveals nothing. Dual-auth approver is the same UI; second laptop looks identical.

**Act 3** — ❌ **Mostly dark.** The reverse-flow inquiry card in Sarah's queue is not wired (`Research_Request__c` 401-degrades). TSMC ticker not in backfill. Even if Sarah hits accept, the specialist citation drift returns another brief with "(source not available)" on every drill-down.

**Act 4** — ✅ **Slides and narration. Works.**

**Overall demo credibility if run right now:** around 40% of the narrative beats work visually. The multi-agent fanout (the single strongest story) lands partially. The trust spine (the money shot) lands structurally but produces failed/degraded results at gates ⑥ and ⑦. Every claim about "filed as a record, joined at the data layer, cross-stitched audit" collapses on click because of the OBO chain.

**The honest verdict:** this demo cannot run live today. But the gap is not build — it is three specific deploy/ingest actions plus two code fixes totalling **~8 hours of work**.

---

## Section 5 — The recalibrated 4-to-5 day deploy path

The `Narrative Arc - 1 - Requirements.docx` claim — *"half a week of deploy work plus a 48-hour BYOD pre-load, no new build"* — is **substantially correct with three caveats**.

### Validated against code:
- ✅ AgentCore + SAM stack + Salesforce metadata are code-complete
- ✅ All 3 MuleSoft apps' boot-crash issues are **fixed** (secure-properties refactor done, `make verify-mule` green locally)
- ✅ EDGAR ingestion Lambda + XBRL parser + chunker + Titan v2 embedder + KB loader **exists** in `aws/data-pipelines/filings-corpus/`
- ✅ Textract drag-drop handler **exists** in the same path
- ✅ CDK stacks for Aurora pgvector + KB + Research/Filings pipelines exist

### Caveats the requirements doc underplays:
1. **The OBO chain is broken right now** (v3-p0-sf-obo-fix.md). Not a deploy issue — requires a Salesforce admin to create a Connected App and upload a cert. ~1 hour of human time, but only a Salesforce admin can do it. If that admin is unavailable, everything else is moot.
2. **Specialist tool-use bypass + citation drift** are real backend code fixes, not config. Small (~3 hours total) but they are code changes, not deploys.
3. **Specialist gantt** (my earlier insistence) is the one frontend build I still recommend — ~2 days. Without it, Act 0's "concurrently, not sequentially" claim lands as sequential-looking pills. The data is on the WebSocket; the renderer isn't.

### Revised T-7 to T-0 checklist

| When | Action | Owner | Blocker if skipped |
|---|---|---|---|
| **T-7** | Bedrock model access enabled for Sonnet 4.5, Haiku 4.5, Titan v2 in target account/region | Infra | All agent turns fail |
| **T-7** | Run `bash scripts/0-preflight.sh` — validates env + AWS + SF auth | Operator | Catches drift before deploys waste time |
| **T-7** | **Create Salesforce Connected App + populate bootstrap secret** per [v3-p0-sf-obo-fix.md Steps 1-7](./v3-p0-sf-obo-fix.md) | SF admin + Infra | Every SF write fails silently. Acts 0/1/2/3 all degrade. |
| **T-6** | `bash scripts/deploy-all.sh` (CDK + SAM + SF + AgentCore + Frontend). Keep `--skip-mulesoft` if mock mode accepted. | Infra | Stack gap |
| **T-5** | Fix 3 backend code issues: specialist timeout (10 min), tool-use binding for research specialists (1-2h), citation drift prompt (30 min). Rebuild + push container. | Backend | Acts 0.3, 0.6 visible breakage |
| **T-5** | Deploy 3 MuleSoft apps (optional): `make verify-mule && make mule-deploy` + Runtime Manager secure-properties per [RUNBOOK §3.3.1](./RUNBOOK.md). Or keep `MULESOFT_MODE=mock` with honest narration. | Infra | Gate ⑥ stays `failed` in mock; narration legitimate |
| **T-5** | EDGAR backfill: META, GOOGL, MSFT, NVDA, AVGO, QCOM, AMD, TSM — 8-Ks from Apr 29 2026, 10-Ks FY25, 10-Qs Q3 2025. Transcripts drag-drop or one-off script. | Data | Act 0 thesis anchors + Act 3 ticker |
| **T-5** | Demo data seed: 4 households above 5% META, positions, IPS, touchpoint history, restricted list | SF admin | Act 1 cannot render 4 households |
| **T-4** | Specialist gantt frontend build (optional but recommended) | Frontend | Act 0 parallel-not-serial claim weaker without it |
| **T-3** | Real-Bedrock smoke on each persona: `bash scripts/smoke-test.sh`. Expect 1-2 prompt fixes on tool_use format. | Backend | First live surprises caught pre-stage |
| **T-3** | Restore V2 ActionsQueueColumn and ClientContextColumn to V3 (port 2 components, ~1 day) | Frontend | Act 1.2 and 1.3 visually dark |
| **T-2** | Restore V2 InlineActionCard is already done. | — | — |
| **T-2** | Rich RM identity card + persistent thread on ClientChannelV3 (1.5 days) | Frontend | Act 1.5 visual quality |
| **T-2** | **BYOD ingest** — firm's top-10 holdings + book structure overnight | Data | Act 4 Slide 2 lands as procurement decision, not sales pitch |
| **T-2** | Full dress rehearsal with confederate + second-laptop dual-auth + operator | All | Last chance to catch UI drift |
| **T-1** | Recorded fallback captured (kill-switch tape) | Operator | If live fails stage-day, narration continues |
| **T-10 min** | `bash scripts/warm-start.sh` fires; AgentCore + WebSockets + auth proxy primed | Operator | First-turn cold start avoidance |
| **T-0** | Presenter on stage; query pre-typed on Sarah's screen | Presenter | — |

**Total effort:** 4-5 days with 1-2 engineers. 1 day for SF admin + infra (T-7 to T-6). 1 day backend fixes (T-5). 1-2 days frontend polish (T-4 to T-2). 1 day ingest + rehearsal (T-2 to T-1).

### Validation of the requirements doc's claim

**Claim:** "half a day of deploy work plus a 48-hour BYOD pre-load. No new build."

**My verdict:** 80% correct. The build is indeed done. The deploy is closer to **2-3 days** than "half a day" because:
- SF Connected App + certs can't be scripted (+4 hours)
- First SF scratch-org deploy will surface 2-4 metadata mismatches per [v3-demo-readiness §2](./v3-demo-readiness.md) (+2-4 hours)
- Real-Bedrock smoke will surface 1-2 prompt fixes (+1-2 hours)
- EDGAR backfill + transcripts (+2 hours)

Plus I still recommend **~2 days of targeted frontend work** — specialist gantt (Act 0), V3-queue restore (Act 1.2), rich RM card (Act 1.5). None are "new features" in the feature-map sense; they are wiring existing backend data into existing component patterns.

**Honest number:** 4-5 working days, 1-2 engineers, 1 SF admin.

---

## Section 6 — The 3 pieces of net-new frontend build

### 6.1 Specialist gantt for Act 0 (VERIFIED missing)

**Script needs:** "Audit strip blooms — five spans open in parallel."

**Data state:** ✅ WebSocket emits `tool_call_start / tool_call_end` with span_id + agent_id + tool_name + latency_ms for every specialist call. Confirmed via frontend type `ToolCall` in `shared/types/agent.ts` and usage in `AuditStripV2`.

**Renderer state:** ❌ Currently renders chips in a horizontal row. Looks sequential even when concurrent. There is no timeline waterfall component.

**Fix:** One new component, `SpecialistGantt.tsx`, that consumes `toolCalls` from the brief store and renders horizontal bars on a time axis. Visx (installed) handles scales + shapes. 2.5 days of work per the research analyst feature map (R-E3).

**Verdict:** Truly missing. Ship it for Act 0 to land.

### 6.2 Client Act 1 rich card + persistent thread + brief-summary delivery

**Script needs:** 3-button card ("send brief / schedule call / do nothing"), inline brief citation, persistent thread.

**Code state:**
- Persistent thread: ❌ `ClientChannelV3.tsx` uses in-memory `useState<Message[]>`. Page reload clears it.
- 3-button card: ❌ Only 2 hardcoded CTAs ("Schedule call", "Ask my RM"). No message-specific action buttons.
- Inline brief citation: ❌ Messages are plain text. No citation chip support.
- MNPI-stripped brief summary delivered to Eleanor when Sarah publishes: ❌ Not wired.

**Fix:** One new component cluster — rich bubble types, persistent storage hook, brief-summary-delivery subscription to `Research_Brief_Published__e`. Per client feature map (E-E1, E-E2, E-E5). **9 days** if all three; **5 days** if just rich card + persistence (skip the MNPI-summary auto-delivery for v1 demo and narrate it).

**Verdict:** Truly missing. Ship at least rich card + persistence for Act 1.5 to land.

### 6.3 Dual-auth distinct UI surface for Act 2

**Script needs:** Senior compliance officer visible on second laptop, "different cursor, visibly different person."

**Code state:**
- Distinct SF user via `Senior_Compliance_Approver` permset: ✅ exists in metadata
- Distinct UI banner/surface on the second laptop: ❌ Both open `AdvisorWorkbenchV3` identically
- Dual-auth approver inbox with queue of pending approvals: ❌ Not built

**Fix (cheap workaround):** Permset-aware banner on `PersonaHeaderV3` — if session user has `Senior_Compliance_Approver` permset, header renders "Senior Compliance" badge + distinct color. **2 hours.**

**Fix (proper):** Separate dual-auth approver inbox view. **2 days.** Per advisor feature map.

**Verdict:** Workaround is enough for a 60-second moment in Act 2 gate ⑤. Go cheap, skip the full inbox unless the panel is specifically looking for an approver workflow view.

---

## Section 7 — Risk ledger for stage day

Top 10 things most likely to fail, ranked by probability × impact:

| # | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **OBO chain still 401'ing because Connected App setup incomplete** | High if not done at T-7; **catastrophic** if it hits on stage | All SF writes fail; Acts 0.8, 1.1, 2.9, 3.1 all go dark | Verify at T-3 with `scripts/narrative-e2e-test.sh`. Expect `IR_Audit_Log__c WHERE CreatedDate = TODAY > 0`. |
| 2 | **Specialist timeout (25s ceiling too tight)** | **High** — proven to hit on 2/5 per Apr 29 probe | Brief shows "gaps: X(timeout), Y(timeout)" — visible "weakness" on screen | Raise to 60s pre-demo. 10-min code change. |
| 3 | **Citation drill-down returns "(source not available)"** | **High** — current state | Every chip click is a broken promise. Presenter said "every sentence cites its source" then demonstrates the opposite. | Fix at T-5 (prompt + Lambda). **Do not demo chip drill-down if not fixed.** |
| 4 | **First real-Bedrock turn surfaces tool_use parse error** (stub-only tested to date) | Medium | Agent hangs or errors on stage | T-3 real-Bedrock smoke run. Budget 1-2 prompt fixes. |
| 5 | **MuleSoft gate ⑥ fails live** (apps not deployed) | **High if not deployed** | Gate ⑥ shows `failed` on screen. Presenter must narrate "this is the vendor boundary in mock mode." | Honest narration works. Audience accepts it IF framed. Alternative: deploy live (3 hrs). |
| 6 | **Mrs. Patel's thread doesn't persist across refresh** | Medium — confederate might reload | Act 1 goes dark if phone frame reloads | Don't reload during Act 1. Or build persistence at T-2 (1 day). |
| 7 | **Live probe last successful Apr 29; state may have drifted by stage day** | Medium | Unknown breakage between now and stage | Re-run all probe curls at T-3. Narrative E2E test expects `23/23`. |
| 8 | **Dual-auth second laptop looks identical to first** | Medium | Panel may not register "different person" signal | T-2 permset banner workaround. 2 hours. |
| 9 | **ActionCard empty on advisor after action_plan detection** | Medium — envelope wiring bug per RUNBOOK §5.2 | Act 2 HITL approval card missing | Verify smoke test [7/8] passes. Rebuild container if stale. |
| 10 | **Frontend/backend contract drift** (frontend tests run against `MockWebSocket`) | Low-Medium | UI shows stale/missing fields | Real-browser smoke on all 3 personas at T-3. |

**Note on #5:** The requirements doc calls `mock mode` a "legitimate vendor boundary." That is true, but it requires the presenter to **name it explicitly** before gate ⑥ fires, otherwise a panelist will see `mulesoft: failed` and ask. The narration in the 18-minute script already covers this ("formatted to spec, packaged with the audit reference in a single API call to the system the firm already owns") — but it does not explicitly say "in this demo we're running mock mode against the paper broker." Add one sentence: "In this demo the MuleSoft gate writes an audit row but holds the actual PB call at the vendor boundary — that's the `mock_mode=true` setting, a one-flag flip to live." That sentence closes the gap.

---

## The one-line truth

**V3 is 3-5 focused engineering-days and 1 hour of Salesforce admin work away from running the 18-minute demo script live end-to-end with credibility.**

The build is done. The gap is:
- **1 SF admin hour** (OBO Connected App)
- **3 hours** of backend bugfixes (timeout, specialist tool-use, citation drift)
- **2 hours** of infra deploy (SF + AgentCore rebuild + BYOD ingest)
- **~2 days** of targeted frontend work (specialist gantt, restore V2 queue + Client 360, rich RM card)
- **1 day** dress rehearsal

If stage day is 5 business days out, we hit it with breathing room. If it is tomorrow, the demo runs at ~60% credibility — the opening specialist-parallel moment lands partially, the trust-spine 7-gate lands with honest `mulesoft: failed`, the cross-stitched audit click-through is dark. That's the choice matrix.

**Recommended:** set stage day at T+5 business days. Clear out the 3-5 day gap. Go live with the real narrative.

---

## Appendix — what I could NOT verify without AWS/SF credentials

- Whether `BEDROCK_GUARDRAIL_ID` env var is populated in AgentCore runtime today
- Whether the 4 MuleSoft Runtime Manager secure-property fields are set (requires Anypoint UI)
- Whether the current AgentCore container is v21 (last observed) or has advanced since
- Whether `Research_Request__c` SObject is deployed in the live org (docs say yes; v3-pending observation says 401 on create, which could mean either "field missing" or "permset missing")
- Whether the Aurora pgvector indexer is actually running today or just deployed

The May 1 probe doc asserts all five of the above are in a known state; I am deferring to that probe as authoritative for items I could not re-verify from code alone.

Every other claim in this document is anchored in code reads or direct quotes from the two probe docs dated Apr 29 and May 1.

---

*Probe closed 2026-05-01. Recommend re-running `scripts/narrative-e2e-test.sh` on the day before stage and comparing its output against the state documented here.*
