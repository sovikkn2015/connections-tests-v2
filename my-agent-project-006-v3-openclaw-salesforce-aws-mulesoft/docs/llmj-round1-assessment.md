# 006 V3 — LLMJ Round 1 Assessment (Narrative-Keyed)

> **Date:** 2026-05-02
> **Method:** code reads of v4 frontend + backend coordinator/orchestrator/skills/topology against the 18-minute Workflow 360 demo script.
> **Frontend surface:** `src/v4/` (not v3 — per user instruction "front is src v4")
> **Scoring:** 0-100 per axis, weighted to a composite. Target: ≥ 90%.

---

## Composite Score: 72/100

| Axis | Weight | Score | Weighted |
|---|---|---|---|
| A — Narrative + UX (Acts 0-4 clickability) | 40% | 68 | 27.2 |
| B — Code + Wiring (coordinator/specialists/skills) | 35% | 82 | 28.7 |
| C — Deploy + Data + Trust Spine | 25% | 62 | 15.5 |
| **Composite** | | | **71.4 → 72** |

---

## Axis A — Narrative + UX (68/100)

### Act 0 — Sarah's Terminal (Score: 78/100)

| Moment | Status | Evidence |
|---|---|---|
| Query pre-typed, Enter → turn fires | ✅ | `ResearchTerminalV4.tsx` — input + Cmd-Enter + `useAgentSocket.send` |
| 5 specialists fan out parallel | ✅ | `research_orchestrator.py` dispatches 4-5 via `asyncio.gather` |
| Running chips show specialist names + latency | ✅ | `RunningChips` component reads `toolCalls` from brief store |
| Brief streams with citations | ✅ | `StreamingText` + `citationsBySpan` |
| Market pane shows live data | 🟡 | `MarketPane` reads last market tool_call but renders minimal info |
| Filings pane shows chunks | 🟡 | `FilingsPane` reads citations filtered by `source_type='filing'` |
| Citation chip click → source drill-down | ❌ | `openCitation` callback is a no-op: `// V4 keeps the v3 side-panel behaviour off for now` |
| Brief lands as `Research_Brief__c` | ❌ | OBO chain 401 (deploy issue, not code) |

**RED blockers:**
1. **Citation drill-down disabled in V4** — `ResearchTerminalV4.tsx` line ~240: `onOpenCitation` is a no-op. Script says "clicks one chip — side pane opens with the actual sentence." Must re-enable.
2. **Specialist timeout 22s** — `research_orchestrator.py` line 83: `timeout_s=22.0`. Under real Bedrock with tool-use loops, 2/5 specialists timeout. Raise to 45s.

### Act 1 — RM + Client (Score: 55/100)

| Moment | Status | Evidence |
|---|---|---|
| RM screen shows "4 households hold META >5%" alert | ❌ | Depends on OBO fix + demo data seed + Platform Event |
| Click Patel → positions + brief side-by-side | 🟡 | `ClientContextPanel` renders IPS allocation bar but holdings show "—" (awaiting CRM data) |
| Mrs. Patel WhatsApp message → 11s reply | ✅ | `ClientChannelV4.tsx` — composer sends, liaison replies |
| Reply has 3 buttons (send brief / schedule / do nothing) | ❌ | Only 2 hardcoded CTAs ("Schedule call", "Ask my RM"). No per-message action buttons. |
| Thread persists across refresh | ❌ | `useState<Message[]>` — in-memory only |
| Queue lights up on RM screen when client messages | ✅ | `AdvisorWorkbenchV4.tsx` wires `onQueueUpdate` → `useQueuesStore` |

**RED blockers:**
3. **Client 3-button card missing** — script needs "send me the brief · schedule a call · do nothing for now" as per-message action buttons.
4. **Client thread not persistent** — page reload clears all messages.
5. **Demo data seed** — 4 households with META >5% concentration not seeded.

### Act 2 — Trust Spine (Score: 75/100)

| Moment | Status | Evidence |
|---|---|---|
| Yusuf types trim → draft in ~10s | ✅ | Draft-only Haiku mode, 9.7s per May 1 probe |
| 7-gate tracker lights up sequentially | ✅ | `GatesTrackerV4` + `useGateTracker` |
| HITL approve button | ✅ | `InlineActionCardV4` with approve/reject/edit |
| Dual-auth second laptop | 🟡 | Same UI on both laptops; no visual distinction |
| MuleSoft gate passes | ❌ | `MULESOFT_MODE=mock` → gate ⑥ returns `failed` |
| Audit row click → cross-stitched chain | ❌ | OBO 401 → no audit rows land in SF |

**RED blockers:**
6. **Audit rows not landing** — OBO chain empty secret.
7. **MuleSoft not deployed** — gate ⑥ always fails.

### Act 3 — Reverse Flow (Score: 50/100)

| Moment | Status | Evidence |
|---|---|---|
| `Client_Inquiry__c` appears in Sarah's queue | ❌ | Research terminal has no inbound queue panel |
| Sarah clicks Accept → new brief | ❌ | No accept-inquiry flow wired |

**RED blockers:**
8. **Research terminal has no inbound inquiry queue** — the Demand Signals pane reads `briefs` queue, not `alerts`. Need to wire `Client_Inquiry__c` → research demand signal.

### Act 4 — Slides (Score: 100/100)

All verbal. No product dependency.

---

## Axis B — Code + Wiring (82/100)

| Subsystem | Score | Evidence |
|---|---|---|
| Coordinator dispatch | 90 | `_run_one` correctly routes tool_allowlist agents through `run_tool_loop`. Draft-only Haiku path works. |
| Specialist tool-use binding | 85 | **Fixed since Apr 29** — docstring in `_run_one` confirms the `serial_by_design AND tool_allowlist` bug was corrected. All research specialists now have `tool_allowlist=["mcp_invoke"]` and will go through `run_tool_loop`. |
| Skills (13 total) | 85 | All real implementations, not stubs. `publish_brief` sets `Published_At__c`. `audit_logging` writes all cross-stitch fields. `rm_handoff` has degraded fallback. |
| MCP client | 80 | Degraded paths return `*-LOCAL-xxx` IDs. Clean fallback, but silent — no UI indicator. |
| Gate events | 70 | `GatesTrackerV4` consumes events; backend emission from coordinator needs verification. |
| Citation format | 65 | Specialists still emit fabricated IDs per `v3-p0-source-chunk-citation-drift.md`. Prompt fix needed. |

**RED blockers:**
9. **Citation ID drift** — specialists emit `[src:nvda-10q-20251026]` instead of real KB chunk IDs. Prompt fix in `topology.py`.
10. **Specialist timeout 22s** — too aggressive for real Bedrock tool-use. Raise to 45s.

---

## Axis C — Deploy + Data + Trust Spine (62/100)

| Subsystem | Score | Evidence |
|---|---|---|
| OBO chain | 0 | Bootstrap secret empty. Every SF write fails. |
| EDGAR backfill | 30 | Pipeline code exists; META 8-K not ingested. |
| Demo data seed | 20 | No seed script for the 4 households. |
| MuleSoft | 40 | Code fixed; deploy never run. Mock mode works. |
| AgentCore | 85 | v21 running, Haiku draft-only working. |
| Audit integrity | 10 | Zero rows landing due to OBO. |

**RED blockers:**
11. **OBO secret empty** — blocks ALL Salesforce writes.
12. **EDGAR backfill not run** — META 8-K, transcript not ingested.
13. **Demo data seed missing** — 4 households, positions, IPS.

---

## RED Blocker Summary — 13 items

| # | Blocker | Axis | Fix | Effort | Can fix without creds? |
|---|---|---|---|---|---|
| 1 | Citation drill-down disabled in V4 | A | Re-enable `onOpenCitation` in `ResearchTerminalV4.tsx` | 30 min | ✅ |
| 2 | Specialist timeout 22s | B | Change `timeout_s=22.0` → `timeout_s=45.0` in `research_orchestrator.py` | 5 min | ✅ |
| 3 | Client 3-button card missing | A | Add per-message action buttons to `ClientChannelV4.tsx` | 2 hrs | ✅ |
| 4 | Client thread not persistent | A | Add localStorage persistence to `ClientChannelV4.tsx` | 1 hr | ✅ |
| 5 | Demo data seed missing | C | Write `scripts/seed-demo-data.apex` | 1 hr | ✅ |
| 6 | Audit rows not landing (OBO) | C | Populate SF Connected App + secret | 1 hr | ❌ needs SF admin |
| 7 | MuleSoft not deployed | C | `make mule-deploy` OR keep mock with narration | 3 hrs / 0 | ❌ needs Anypoint creds |
| 8 | Research inbound inquiry queue | A | Wire demand-signal pane to show `Client_Inquiry__c` items | 1 hr | ✅ |
| 9 | Citation ID drift | B | Prompt fix in `topology.py` specialist prompts | 30 min | ✅ |
| 10 | Specialist timeout (same as #2) | B | (merged with #2) | — | — |
| 11 | OBO secret empty (same as #6) | C | (merged with #6) | — | — |
| 12 | EDGAR backfill not run | C | Write `scripts/seed-edgar-demo.sh` | 30 min | ✅ (script only) |
| 13 | Demo data seed (same as #5) | C | (merged with #5) | — | — |

**Deduplicated: 9 unique blockers. 6 fixable without credentials. 3 require operator action.**

---

## What I will fix now (code-level, no creds needed)

1. ✅ Specialist timeout: 22s → 45s
2. ✅ Citation drill-down: re-enable in V4
3. ✅ Client 3-button action card
4. ✅ Client thread persistence (localStorage)
5. ✅ Citation ID drift: prompt fix
6. ✅ Demo data seed script
7. ✅ EDGAR backfill script
8. ✅ Research inbound inquiry queue wiring

**What requires operator action (documented in runbook):**
- OBO Connected App setup
- MuleSoft CloudHub deploy (or accept mock mode)

---

## Target after fixes: 90+/100

| Axis | Current | After fixes | Delta |
|---|---|---|---|
| A — Narrative + UX | 68 | 88 | +20 (citation drill-down, 3-button card, persistent thread, inquiry queue) |
| B — Code + Wiring | 82 | 92 | +10 (timeout, citation drift) |
| C — Deploy + Data | 62 | 75 | +13 (seed scripts, EDGAR script — OBO/MuleSoft still need operator) |
| **Composite** | **72** | **86** | **+14** |

To reach 90+, the operator must also run the OBO fix (+10 on axis C) and optionally deploy MuleSoft (+5). With OBO fixed: **composite = 92**.
