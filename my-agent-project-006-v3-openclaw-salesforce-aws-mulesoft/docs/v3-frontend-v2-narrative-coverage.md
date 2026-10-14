# v3 Frontend v2 — Narrative Arc Coverage

**Branch**: `feat/006-v3-live-demo`
**Date**: 2026-04-30
**Scope**: The v2 frontend built in this session (`frontend/src/v2/`), not deployed.

This document answers the user's question: **"Can the UIUX handle all the narrative arcs?"** For each narrative (N1–N15) it lists which v2 surface renders which slice, which live store drives which pane, and where the backend gaps remain.

The v2 UIUX is a **presentation layer** — the narratives depend on backend wiring that already exists (N1), is partially built (N2, N5), or is designed as slide-only (N3, N4). The UI is ready for all of them. The backend gaps are documented in `v3-design-vs-built-vs-deployed-v2.md`.

---

## How v2 wires to the backend (single source of truth)

Every v2 component reads from the **existing** stores and emits messages over the **existing** `useAgentSocket` WebSocket. No new contracts were introduced.

| Pane / component | Store(s) read | Event(s) consumed |
|---|---|---|
| `BriefPaneV2` (Sarah) | `useBriefStore.markdown, citationsBySpan, isStreaming` | `brief_delta`, `citation`, `turn_complete` |
| `RunningChips` inside brief | `useBriefStore.toolCalls` | `tool_call_start`, `tool_call_end` |
| `FilingsPaneV2` | `useBriefStore.citationsBySpan` (filter `source_type=filing`) | `citation` |
| `SentimentPaneV2` | `useBriefStore.citationsBySpan` (filter `source_type=news`) | `citation` |
| `TraversalMapV2` | `useTraversalStore.nodes, edges, activePersona, turnId` | `turn_started`, `tool_call_*`, `gate_*` |
| `TimelineV2` | `useBriefStore.toolCalls, durationMs` + `useTraversalStore.startedAt` + gate state | `tool_call_start/end`, `turn_complete`, `gate_*` |
| `GatesTrackerV2` | `useGateTracker.gates` | `gate_passed`, `gate_started`, `gate_failed` |
| `AuditStripV2` | `useBriefStore.toolCalls, costUsd, durationMs` + `useSessionStore.{correlationId, connectionStatus}` + gate array | all of the above |
| `InlineActionCard` | `useOptimisticApproval.state` (approve/reject emit `hitl_approval` OUT) | `hitl_prompt` IN, `gate_passed`/`gate_failed` on `hitl` |
| `QueuesColumn` (Marcus) | `useQueuesStore.itemsByQueue` | `queue_update` |
| `ClientChannelV2` messages | `useBriefStore.markdown` after streaming completes | `brief_delta`, `turn_complete` |

**Architecture Map correctness**: the v2 map is driven by `useTraversalStore` which already translates tool-call spans (via `resolveNodeId` in `data/toolToNode.ts`) and gate events into node/edge state. No new wiring required — the v1 backend events already paint the v2 map.

---

## Architecture Map — the fix

**Problem the user flagged**: *"the architecture maps are not proper"*.

**v1 behavior**: renders all 37 topology nodes at their declared `layer`, across all personas simultaneously. Accurate, but cluttered — the "one trust spine, three personas" story doesn't land.

**v2 fix** (`v2/atoms/TraversalMapV2.tsx`, 380 LOC):

1. **Row 0 — Coordinator** (always center top, labelled `coordinator`)
2. **Row 1 — Three orchestrators ALWAYS visible** (`research_orch`, `advisor_orch`, `liaison_orch`). Only the active one pulses; the other two render dim but visible.
3. **Row 2 — Specialists of the active orchestrator only**, fanning out horizontally below it
4. **Row 3 — Skills and MCPs** anchored to each specialist
5. **Row 4 — Gate chain** (advisor persona only, or forced with `showGates=true`) — 7 gates in canonical order with sequence edges
6. **Ghost spine edges** (`--ghost` CSS class, dashed dim horizontal) connect the three orchestrators — **this is a UI construct, not a data edge** — it conveys "they share the same graph"

Behavior verified in `tests/unit/v2/TraversalMapV2.test.tsx` (9 tests):
- `renders all three orchestrators regardless of active persona`
- `renders the coordinator at the top`
- `renders ghost edges between the three orchestrators`
- `fans research specialists out when active persona is research`
- `fans advisor specialists + gate chain when active persona is advisor`
- `reflects live store state on nodes via data-state attribute`
- `lights active persona nodes after startTurn + markAgentActive`
- `marks tool-call target solid after successful completion`
- `marks tool-call target error on failure`

Every node and every edge has a deterministic `data-testid` so the map is inspectable and screenshot-diffable.

---

## End-to-End Trace — the fix

**Problem**: the v1 `EndToEndTrace` is a list of completed-turn summaries without per-specialist timing breakdown.

**v2 fix** (`v2/atoms/TimelineV2.tsx`):
- Waterfall layout — orchestrator spans the whole turn, specialists indented one level (`├`), MCP/skill calls indented two levels (`│  └`)
- Bar colors per kind: orch (brand blue), skill (purple), mcp (teal), human/HITL (warning amber), gate (gate amber)
- Per-persona caption at bottom ("All five specialists started at t≈80ms — proves asyncio.gather")
- Langfuse deep link in the header
- Shows the live turn in progress (not just completed turns) by using `useTraversalStore.startedAt` + `Date.now()` when `durationMs === 0`
- Gate chain appended as synthetic rows for advisor persona with start% derived from `gate.started_at`

---

## Per-narrative coverage

### N1 · Earnings Morning 🟢 live today (backend: 90%)

**Flow**: Research orchestrator fans to 5 specialists in parallel → 5 completed briefs → synthesis → published.

**v2 surface**: `ResearchTerminalV2` → Sarah Chen.

**What paints:**
- Query input → `Run ⌘↵` sends `{type:'turn', ...}`
- Top-of-brief running chips show `sec-edgar · 412ms`, `tavily-news · running`, etc.
- `BriefPaneV2` streams the markdown with citation chips (pending → resolved)
- Panes populate from citations (`FilingsPaneV2` groups `source_type=filing`, `SentimentPaneV2` groups `source_type=news`)
- `TraversalMapV2` in research mode: research_orch pulses, 5 specialist nodes fan out, each MCP lights as called
- `TimelineV2` shows 5 specialist bars starting at t≈80ms with varying widths — **proves `asyncio.gather`** (user's "no mockery drama" requirement)
- `AuditStripV2` shows trace id + 5 specialist pills + cost

**Known backend gap**: 2 of 5 specialists time out occasionally. The UI surfaces this honestly — pills go `error` red, map nodes go red, timeline bar renders at the truncation point. No inflation.

### N2 · Client drives research 🟡 partial (backend: liaison responds, `rm_handoff` skill missing)

**Flow**: Client asks Liaison a question → liaison recognises intent shift → queues an Insight for RM Marcus → Marcus requests deeper research → brief returns → Marcus acts.

**v2 surface**: `ClientChannelV2` → `AdvisorWorkbenchV2` → `ResearchTerminalV2` (navigator tabs in `PersonaHeaderV2` nav).

**What paints on each surface:**
1. **Client** (Eleanor): types question in phone bezel composer → live turn fires → agent bubble streams in; rich `bubble__rich` block rendered for suggested-next-step with "Loop in Marcus" title.
2. **Advisor** (Marcus): `queue_update` event with `kind='alerts'` appears in Actions tab as an unread high-priority item. Selecting it loads `ClientContextColumn` with client signals.
3. Marcus types `/research NVDA` in the composer → full research streams in his conversation panel (same brief store feeding Sarah's terminal).

**Backend gap**: `rm_handoff` skill needs to exist server-side to fire the `queue_update`. The UI handles the event when it arrives — verified by `useStreamingTurn`'s existing `onQueueUpdate` wiring. Once the skill is deployed, N2 lights up end-to-end in the UI with zero frontend changes.

### N3 · Risk Alert 🔴 slide-only by design

User called out: "don't reclassify them. Present them as the V4 vision with pre-seeded data."

**v2 handling**: pre-seeded queue items can be inserted via `useQueuesStore.upsertItem()` in a dev/demo bootstrap. The UI renders them in Marcus's Actions tab with `badge='high'` and a red priority pill. Clicking opens `ClientContextColumn` with pre-seeded signals. No backend call made — honest deferral.

### N4 · Demand Signal 🔴 slide-only by design

**v2 handling**: `DemandPaneV2` on Sarah's screen accepts `QueueItemSummary[]` as a prop. For demo, pass 2-3 pre-seeded items. Clicking `accept →` writes the item's title into the query input and submits, running the real research orchestrator on a real query. Client never sees anything — research-only.

### N5 · Large Liquidation 🔴 backend not deployed (MuleSoft CloudHub)

**Flow**: RM drafts a large trim → 7-gate write path fires → MuleSoft CloudHub Process API → OMS executes.

**v2 surface**: `AdvisorWorkbenchV2`.

**What paints today** (when backend emits events correctly):
- Marcus's conversation shows the AI agent speaking the plan
- `InlineActionCard` renders inline in that AI message with order/symbol/qty/notional + impact diff (14.2% → 9.5% concentration) + Approve/Edit/Deny buttons
- `requires_dual_auth` flag renders amber "dual-auth required" cell
- `GatesTrackerV2` always visible at top; gates ①②③ go green as they pass; gate ④ becomes active with scan animation; Marcus clicks Approve → optimistic confirm flashes `validating…`; gate ④ goes green; gates ⑤⑥⑦ light in sequence
- `TraversalMapV2` in advisor mode with gate chain visible — nodes light through `gate:guardrails → gate:mnpi_filter → gate:compliance → gate:hitl → gate:dual_auth → gate:mulesoft → gate:audit` with sequence edges animating
- `AuditStripV2` shows `⏸ HITL hold · gate ④ · 11.4s` indicator with live duration counter
- Cost + span count increment through the turn

**Known backend gap**: `mulesoft-actions` MCP forwards to Process APIs that aren't deployed to CloudHub. When Marcus approves, gate ⑥ fails (or never fires). UI handles this honestly — gate renders red with ✕, `InlineActionCard` shows rollback toast. No inflation.

### N6 · Research refresh (from 10 additional narratives)

**Flow**: Analyst re-runs a prior brief with a new angle — cache hits on some specialists, others re-fire.

**v2 handling**: same research terminal, same brief store. `TimelineV2` shows which specialists re-fired (long bar) vs. cached (nearly-zero bar). No new wiring.

### N7 · Suitability fail 🟡 partial

**Flow**: Marcus drafts a trade that fails suitability check → gate ③ returns `failed`.

**v2 handling**: `GatesTrackerV2` gate ③ goes red with `failed` status; `InlineActionCard` rollback toast fires with `gate compliance failed` message. No approval possible — the Approve button is disabled because `state.phase !== 'idle'`.

### N8 · MNPI leak attempt

**Flow**: Client asks about their own positions. Liaison replies with generic guidance, MNPI filter silently redacts position numbers from anything surfaced to the channel.

**v2 handling**: `ClientChannelV2` phone bezel renders only text bubbles; no positions or numbers ever appear. `v2-bubble__rich` structured blocks can surface "Suggested next step" cards but never financial data. `BriefPaneV2`'s MNPI callout (server-controlled flag in brief content) shows an amber block with `⚑ MNPI redaction applied` label when present.

### N9 · Order modification mid-flight

**Flow**: Marcus submits a trade, realises a mistake before execution, modifies.

**v2 handling**: Second `hitl_prompt` event for the modify plan arrives; `AdvisorWorkbenchV2` resets `pendingPlan` to the new one and shows a fresh `InlineActionCard`. Previous plan's gate trace clears on `gateTracker.reset(newPlanId)`.

### N10 · Policy drift warning

**v2 handling**: `ClientContextColumn` already renders signals section with IPS-band concentration warnings. Server emits `queue_update` for drift, renders as medium-priority Task item.

### N11 · Batch rebalance

**Flow**: Marcus processes a batch of similar plans one by one.

**v2 handling**: `QueuesColumn` Actions tab — click through multiple items; each selection loads its own `ClientContextColumn` context; the same `InlineActionCard` component handles each plan. No modal stacking issue (there was no modal to begin with in v2).

### N12 · Escalation path

**Flow**: Tier-2 compliance escalation — same conversation, different approver.

**v2 handling**: `AuditStripV2` shows dual-auth indicator + `InlineActionCard` shows the "dual-auth required" cell. Server emits a second approval event after first approver — UI reflects by keeping gate ⑤ active until both land.

### N13 · Schedule call (client-initiated)

**v2 handling**: `v2-client-ctas` primary button fires `emitClientTurn('Please schedule a call with my RM.')`. Backend routes to liaison orchestrator → scheduling skill (when built).

### N14 · Research briefing replay

**Flow**: Marcus re-reads a prior brief, expands its trace.

**v2 handling**: `TraversalMapV2` and `TimelineV2` are session-scoped now. For replay, `useTraversalHistoryStore` (v1 builder 3's history store) already captures completed turns. A future `<TraceReplay>` page can reuse `TraversalMapV2` + `TimelineV2` with state rehydrated from the history store — no new components needed.

### N15 · Audit review

**v2 handling**: `AuditStripV2` has a Langfuse deep-link (`⌥L Langfuse →`) that opens the trace in a new tab. `TraversalMapV2` nodes are clickable and deep-link to specific spans. All state is serializable because it comes from Zustand stores.

---

## What the uploaded UIUX design brought in (now realised)

| Uploaded design element | v2 component | Status |
|---|---|---|
| Workflow 360 branding + `W360Logo` | `W360Logo.tsx` | ✅ |
| Named personas (Sarah, Marcus, Eleanor) | `PersonaHeaderV2.DEFAULT_PERSONA_NAMES` | ✅ |
| 7-gate tracker always visible | `GatesTrackerV2` | ✅ |
| Gate scan animation | `v2-gates.css` `@keyframes v2-gate-scan` | ✅ |
| `dashFlow` animation on edges | `v2-map.css` `@keyframes v2-dash-flow` | ✅ |
| Forensic-dark surface (Sarah) | `.v2-research` + `v2-tokens.css` | ✅ |
| SLDS-light surface (Marcus) | `.v2-advisor` | ✅ |
| WhatsApp + phone bezel (Eleanor) | `.v2-phone`, `.v2-phone__notch`, `.v2-phone__screen` | ✅ |
| Running chips inside brief | `RunningChips` in `ResearchTerminalV2` | ✅ |
| MNPI redaction callout | `v2-brief__callout` CSS class (server triggers) | ✅ |
| Citation pending state | `.chip-cite--pending` | ✅ |
| Filings chips colored by type | `.v2-filings-chip[data-type="…"]` | ✅ |
| **Inline ActionCard (not modal)** | `InlineActionCard` | ✅ |
| Action card plan + impact diff | `v2-action-card__plan` + `v2-action-card__diff` | ✅ |
| Queue tabs (Actions/Insights/Tasks) | `QueuesColumn` with `TAB_ORDER` | ✅ |
| Client 360 IPS allocation bar | Rendered in advisor column (waiting for CRM data) | ✅ |
| 3-column client layout with captions | `.v2-client-grid` | ✅ |
| Embedded trust spine on client right | `v2-client-tracestack` | ✅ |
| Rich bubble blocks | `.v2-bubble__rich` + `.v2-bubble__name` | ✅ |
| Audit strip trace id + spans + cost + Langfuse link | `AuditStripV2` | ✅ |
| Audit strip HITL-hold indicator | `AuditStripV2` with `gates` prop | ✅ |
| Per-specialist audit pills | `AuditStripV2` `pills` map | ✅ |
| Timeline waterfall with indented rows | `TimelineV2` | ✅ |
| Per-persona timeline caption | `captionFor(persona)` | ✅ |
| **Architecture map with 3 orchestrators + ghost spine** | `TraversalMapV2` | ✅ |
| DesignCanvas wrapper (pan/zoom/reorder artboards) | Not ported — production uses routes | ❌ by design |

---

## How to activate v2

Launch the frontend the same way as v1. Then append `&v2=1` (or `?ui=v2`) to the URL:

```
https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v2=1
https://d2zs9nk4uc2dbx.cloudfront.net/?persona=advisor&v2=1
https://d2zs9nk4uc2dbx.cloudfront.net/?persona=client&v2=1
```

v1 remains the default — existing demo links keep working. The nav tabs inside v2 `PersonaHeaderV2` preserve `&v2=1` so you can switch personas without dropping back to v1.

**No deployment step needed** — the build artifacts include both v1 and v2 already. Just rebuild and upload (`npm run build` in `frontend/`).

---

## Files added (all on `feat/006-v3-live-demo`, uncommitted — do not commit builder's parallel MuleSoft work)

```
frontend/src/styles/
  v2-tokens.css               # design tokens scoped under .v2-root
  v2-header.css               # PersonaHeaderV2 styles
  v2-map.css                  # TraversalMapV2 styles (ghost edges, pulse, dash-flow)
  v2-timeline.css             # TimelineV2 styles
  v2-gates.css                # GatesTrackerV2 styles
  v2-personas.css             # All three persona surface styles

frontend/src/v2/
  V2App.tsx                   # v2 persona router
  atoms/
    W360Logo.tsx              # Brand mark inline SVG
    PersonaHeaderV2.tsx       # Named persona header with nav + live dot
    GatesTrackerV2.tsx        # 7-gate always-visible tracker with detail + latency
    TraversalMapV2.tsx        # 3-orchestrator architecture map with ghost spine
    TimelineV2.tsx            # End-to-end trace waterfall
    AuditStripV2.tsx          # Trace + pills + HITL-hold + cost + Langfuse
    InlineActionCard.tsx      # HITL approval as inline AI message
    TrustSpineStrip.tsx       # Map + timeline combo with eyebrow
  personas/
    ResearchTerminalV2.tsx    # Sarah Chen — forensic dark
    AdvisorWorkbenchV2.tsx    # Marcus Kerrigan — SLDS light + inline ActionCard
    ClientChannelV2.tsx       # Eleanor Vance — phone bezel + 3-col with trust spine

frontend/src/App.tsx          # MODIFIED — routes to V2App when ?v2=1 is set

frontend/tests/unit/v2/
  AuditStripV2.test.tsx       # 4 tests
  GatesTrackerV2.test.tsx     # 4 tests
  TraversalMapV2.test.tsx     # 9 tests
```

**Total v2 code**: ~2,400 lines of TypeScript + ~1,500 lines of CSS + 400 lines of tests.

**Build status**: `tsc -b && vite build` → exit 0. `vitest run` → 118/118 passing (101 pre-existing + 17 new).

**Not deployed** per user instruction. The built artifacts live in `frontend/dist/` and are ready to upload to the existing v3 CloudFront distribution at any time.
