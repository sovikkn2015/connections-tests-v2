# V6 Frontend Forensic Audit — Independent Assessment

> **Auditor:** Independent frontend assessor
> **Date:** 2026-05-02
> **Scope:** Every source file in `frontend/src/v6/`, `frontend/src/shared/`, build config, tests, and V4 comparison
> **Method:** Line-by-line code read of 50+ files. No live probes — code-only forensic analysis.
> **Verdict:** The frontend is **substantially real engineering, not theater** — but contains specific hardcoded fallbacks and empty-state placeholders that must be disclosed.

---

## 1. FRONTEND WIRING TRUTH TABLE

| UI Feature | Wired to Backend? | Transport | Evidence |
|---|---|---|---|
| Research query → brief | **YES** | `POST /agent/invoke` via `HttpAgentTransport` | `ResearchTerminalV6.tsx` → `useAgentSocket` → `httpAgentTransport.ts` sends real HTTP POST to `VITE_API_URL/agent/invoke` |
| Advisor query → draft/action plan | **YES** | `POST /agent/invoke` via `HttpAgentTransport` | `AdvisorWorkbenchV6.tsx` → same socket hook → same transport |
| Client message → liaison response | **YES** | `POST /agent/invoke` via `HttpAgentTransport` | `ClientChannelV6.tsx` → same socket hook → same transport |
| HITL Approve/Reject | **YES** | `POST /agent/approve` via `HttpAgentTransport.postApproval()` | `useOptimisticApproval` → sends `hitl_approval` message → transport POSTs to `/agent/approve` |
| Citation drill-down | **YES** | `GET /api/source_chunk/:id` | `ResearchTerminalV6.tsx` `openCitation()` fetches from `VITE_API_URL/api/source_chunk/` |
| Client 360 household data | **YES** | `POST /mcp/salesforce-crm/tools/call` | `AdvisorWorkbenchV6.tsx` `fetchHousehold()` — real `fetch()` to CRM MCP endpoint with `read_household_summary` |
| Document upload/ingest | **YES** | `POST /api/ingest-document` | `ResearchTerminalV6.tsx` `handleDrop()` — real FormData POST. Catch block shows graceful fallback message. |
| Session warm/prefetch | **YES** | `POST /api/session/warm` | `restClient.ts` `warmSession()` — real endpoint |
| WebSocket streaming | **YES** (dual transport) | `wss://` OR `POST /agent/invoke` | `useAgentSocket.ts` selects `AgentSocket` (real WebSocket with backoff) or `HttpAgentTransport` based on env vars |
| Persona switching | **YES** (changes backend agent) | Query param `persona=` sent in every transport call | `HttpAgentTransport` sends `persona` field in POST body; `AgentSocket` sends `x-persona` query param |
| 7-gate tracker animation | **YES** | Gate events from backend | `useGateTracker` + `useStreamingTurn` process `gate_passed/started/failed` events; `turn_complete.gate_trace` replayed at 400ms intervals |
| Traversal map node lighting | **YES** | Tool call events from backend | `useTraversalStore` transitions nodes dim→pulse→solid based on `tool_call_start/end` events |
| Queue updates (advisor) | **YES** (wired, but depends on backend emitting events) | `queue_update` events | `useStreamingTurn` → `useQueuesStore.upsertItem/removeItem` |
| Voice input | **YES** (browser-native) | Web Speech API | `VoiceButton.tsx` — no external API, uses browser SpeechRecognition |
| Theme toggle | **LOCAL ONLY** | `localStorage` | `V6App.tsx` — persists to `v6.theme`, applies `data-theme` attribute. No backend call. |
| Langfuse deep-link | **YES** (link generation) | URL construction | `TraversalMapV4` + `TimelineV4` + `AuditStripV4` use `langfuseBaseUrl` env var |

**Summary: 15 of 16 features are wired to real backend endpoints. Theme toggle is correctly local-only.**

---

## 2. MOCK/FAKE REGISTRY — Every Hardcoded Value Found

### 2.1 HARDCODED ALLOCATION BAR (CRITICAL FINDING)

**File:** `AdvisorWorkbenchV6.tsx`, `ClientContextPanel`, lines ~290-310

When `allocation.length === 0` (no household data loaded), the component renders a **hardcoded fallback allocation bar**:
```
Equity 62% | Fixed 22% | Alts 9% | RE 4% | Cash 3%
```
These are not real numbers. They are static CSS widths. **This is the single most dishonest element in the V6 frontend.** The V4 version has the identical hardcoded bar — V6 inherited it.

**Mitigation:** When real household data IS loaded (via the `fetchHousehold` CRM MCP call), the `buildAllocation()` function computes real percentages from `positions[].pct_of_portfolio`. The hardcoded bar only shows as a fallback.

**Verdict:** Partially dishonest. The real data path exists and works. The fallback should show "Loading…" or "No data" instead of fake numbers.

### 2.2 HARDCODED PERSONA IDENTITIES

**File:** `PersonaHeaderV6.tsx`

```typescript
const DEFAULT_IDENTITY: Record<Persona, { name: string; role: string; initials: string }> = {
  fsi_research: { name: 'Sarah Chen', role: 'Sr. Equity Analyst', initials: 'SC' },
  fsi_advisor: { name: 'Marcus Kerrigan', role: 'Sr. Wealth Advisor', initials: 'MK' },
  fsi_client_liaison: { name: 'Eleanor Vance', role: 'Tier-A · since 2009', initials: 'EV' },
};
```

**Verdict:** Acceptable demo convention. When a real Cognito user is authenticated (`principalId !== 'dev-principal'`), the header shows the real user's name. The designed identities are only shown in dev-bootstrap mode. This is clearly intentional and documented.

### 2.3 HARDCODED SAMPLE QUERIES

**Files:** `AdvisorWorkbenchV6.tsx`, `ResearchTerminalV6.tsx`, `ClientChannelV6.tsx`

Each persona has 15-30 hardcoded sample queries with `hint` strings explaining what they demonstrate. These are rendered in a collapsible `<details>` panel.

**Verdict:** Not fake — these are demo affordances. Clicking them triggers real backend calls via `send({ type: 'turn', ... })`. The hints are documentation, not fake data.

### 2.4 WELCOME MESSAGE IN CLIENT CHANNEL

**File:** `ClientChannelV6.tsx`, line ~240

When `messages.length === 0`, a hardcoded welcome bubble renders:
```
"Good morning, Eleanor. Markets opened mixed; Asia was choppy on chip-export headlines. I'm here if you have any questions."
```

**Verdict:** Cosmetic placeholder. Disappears as soon as any real message is sent. Standard chat UX pattern.

### 2.5 PHONE STATUS BAR

**File:** `ClientChannelV6.tsx`

```
9:41 | ●●●●● 5G | 96%
```

**Verdict:** Cosmetic. This is a phone bezel mockup — the status bar is decorative, matching WhatsApp's visual language. Not a data claim.

### 2.6 TOPOLOGY FALLBACK

**File:** `useTopologyData.ts`

`FALLBACK_TOPOLOGY` contains 4 placeholder nodes (coordinator + 3 orchestrators) used when `topology.json` hasn't been generated.

**Verdict:** Legitimate fallback. The real `topology.json` exists with 43 nodes and 53 edges (verified — it's a real generated file with timestamp `2026-04-28T12:32:15`). The fallback is dead code in production.

### 2.7 DEV BOOTSTRAP TOKEN

**File:** `App.tsx`

```typescript
session.setAuth({
  sessionToken: 'dev-bootstrap-token',
  principalId: 'dev-principal',
  ...
});
```

**Verdict:** Documented dev-mode behavior. `.env.production` has `VITE_AUTH_DEV_BOOTSTRAP=1`. When Cognito is configured (and it IS — the `.env.production` has real Cognito domain, client ID, redirect URI, user pool ID), the real auth flow runs. The dev bootstrap is a fallback.

### 2.8 EMPTY STATE MESSAGES

Multiple components show italic placeholder text when no data has arrived:
- "Market data loads once the market_specialist fires on the next turn."
- "10-K / 10-Q / 8-K chunks appear as the filings_specialist cites them."
- "Sentiment score and sparkline render when sentiment_specialist emits a chart_intent."
- "No suggestions from the field yet."
- "Holdings populate when the CRM MCP call for this household returns."

**Verdict:** Honest empty states. They accurately describe what triggers data population. Not fake data.

---

## 3. PERSONA INTEROPERABILITY — Can Data Flow Between the 3 Personas?

### 3.1 Architecture

All three personas share:
- **Same Zustand stores:** `session.ts`, `brief.ts`, `queues.ts`, `traversal.ts`, `traversalHistory.ts`
- **Same transport layer:** `useAgentSocket` → `HttpAgentTransport` or `AgentSocket`
- **Same backend endpoint:** `POST /agent/invoke` with `persona` field differentiating routing
- **Same topology:** `topology.json` with 43 nodes spanning all personas

### 3.2 Cross-Persona Data Flow

| Flow | Mechanism | Status |
|---|---|---|
| Research brief → Advisor queue | Backend `queue_update` event with `queue: 'briefs'` | **WIRED** — `useStreamingTurn.onQueueUpdate` → `useQueuesStore.upsertItem`. Depends on backend emitting the event. |
| Client inquiry → Advisor alert | Backend `queue_update` event with `queue: 'alerts'` | **WIRED** — same mechanism |
| Advisor RM reply → Client inbox | Backend `queue_update` event with `queue: 'inbox'` | **WIRED** — `ClientChannelV6.tsx` listens for `inbox` queue updates and renders them as RM messages |
| Research demand signals | `useQueuesStore.itemsByQueue.briefs` + `alerts` filtered | **WIRED** — `DemandPane` in research terminal reads from queue store |

### 3.3 Limitation

Cross-persona flow requires **the backend to emit `queue_update` events**. The frontend wiring is complete. The `v6-query-test-results.md` confirms the backend does NOT currently emit these events for most flows — the queue store stays empty.

**Verdict:** The plumbing is real. The pipes are connected. The water isn't flowing because the backend faucet isn't turned on yet.

---

## 4. DEMO READINESS

### 4.1 What Works Live (No Script Needed)

| Feature | Confidence | Evidence |
|---|---|---|
| Research query → streamed brief with citations | **HIGH** | `v6-query-test-results.md`: 8/8 research queries returned ok, 18-23s, real citations |
| Advisor draft → action plan with HITL card | **HIGH** | `v6-query-test-results.md`: "Trim NVDA" returned action plan AP-20250114-8f7e2c91 in 8.5s |
| HITL approve → gate trace animation | **HIGH** | Approve round-trip confirmed: hitl(passed), dual_auth(passed), mulesoft(passed), audit(passed) |
| Client FAQ → fast response | **HIGH** | "What are your office hours?" returned in 2.2s |
| Client escalation → hand-off detection | **HIGH** | "I want to sell all my NVDA shares" returned in 19.8s |
| Trust spine (traversal map + timeline) | **HIGH** | Real topology.json (43 nodes, 53 edges), real tool_call events drive node lighting |
| Theme toggle (light/dark) | **HIGH** | Pure frontend, no backend dependency |
| Persona switching | **HIGH** | URL-based with `v6=1` preserved in all nav links |
| Citation chip click → source drill-down | **MEDIUM** | Endpoint exists; depends on backend returning real chunk text |
| Voice input | **MEDIUM** | Browser-native; works in Chrome/Edge/Safari |

### 4.2 What Needs a Script / Seed Data

| Feature | Issue | Workaround |
|---|---|---|
| Advisor queues populated | Backend doesn't emit `queue_update` events | Pre-seed via `useQueuesStore.setState()` in console, or wait for backend fix |
| Client 360 real holdings | CRM MCP call may fail if SF OBO is broken | Hardcoded allocation bar shows as fallback (see §2.1) |
| Demand signals in research | Empty until backend emits queue events | Narrate the architecture |
| Sentiment sparkline | Backend doesn't emit `chart_intent` | Text placeholder shown |

### 4.3 What Will Crash / Degrade

| Scenario | Behavior | Severity |
|---|---|---|
| Backend completely down | `HttpAgentTransport` emits `error` event with `tier: 'recoverable'`. UI shows error in brief store. No crash — `ErrorBoundary` catches React errors. Connection status shows "error" in header. | **Graceful degradation** |
| WebSocket disconnect | `AgentSocket` reconnects with exponential backoff (1s→2s→4s→8s ceiling, jittered). Status shows "reconnecting". | **Graceful** |
| Auth token expired | `4401` close code triggers `onAuthExpired` → Cognito re-login flow | **Graceful** |
| CRM MCP call fails | `ClientContextPanel` shows "Failed to load household data" with error message | **Graceful** |
| Invalid JSON from backend | `wsClient.ts` catches parse errors, logs warning, continues | **Graceful** |

---

## 5. V6 vs V4 REGRESSION ANALYSIS

### 5.1 What V6 Gained Over V4

| Feature | V4 | V6 |
|---|---|---|
| Light/dark theme | Dark only (Bloomberg aesthetic) | Light default + dark toggle, persisted |
| Nav link version lock | **BROKEN** — links went to `&v4=1` from other versions | **FIXED** — all links include `v6=1` |
| Client 360 CRM fetch | Hardcoded "—" for AUM, no fetch | **Real `fetchHousehold()` call** to CRM MCP with abort controller |
| Client 360 allocation | Always hardcoded 62/22/9/4 | **Dynamic** from `buildAllocation()` when data available; hardcoded fallback |
| Client 360 error states | None — always shows "synced" | Loading/error/idle states with real error messages |
| Document drag-drop ingest | Not present | **New** — drop PDF/DOCX/XLSX/CSV → `POST /api/ingest-document` |
| Voice input | Not present | **New** — `VoiceButton` with Web Speech API |
| Sample queries | Present but less organized | **Improved** — categorized with narrative badges and hints |
| Client thread persistence | In-memory only | **localStorage persistence** (last 50 messages) |
| Designed identities | Shows "Dev User" | Shows Sarah Chen / Marcus Kerrigan / Eleanor Vance in dev mode |

### 5.2 What V6 Lost From V4

| Feature | V4 | V6 | Impact |
|---|---|---|---|
| `TrustSpineV4` wrapper component | Dedicated component with eyebrow props | Inline `<details>` with V4 atoms imported | **No regression** — same atoms, different wrapper |
| `useTheme` hook | V4 has its own theme hook | V6 manages theme in `V6App.tsx` directly | **No regression** — equivalent functionality |
| Citation drill-down in advisor | `onOpenCitation={() => {}}` (no-op comment: "follows v5") | Same no-op in V6 advisor | **Parity** — neither V4 nor V6 wired this for advisor |

### 5.3 Verdict

**V6 is a strict superset of V4 functionality.** No regressions found. V6 adds CRM fetch, document ingest, voice input, theme toggle, localStorage persistence, and better error handling.

---

## 6. BUNDLE SIZE / PERFORMANCE

### 6.1 Six UI Versions Shipping

The `App.tsx` router imports all six versions:
```typescript
import { V1App } from './v1/V1App';
import { V2App } from './v2/V2App';
import { V3App } from './v3/V3App';
import { V4App } from './v4/V4App';
import { V5App } from './v5/V5App';
import { V6App } from './v6/V6App';
```

**These are static imports, not lazy/dynamic.** All six bundles ship to every user regardless of which version they use.

### 6.2 Impact Assessment

| Concern | Severity | Detail |
|---|---|---|
| Bundle size | **MEDIUM** | 6 persona components × 6 versions = 36 component trees in the bundle. V6 imports V4 atoms, so V4 code ships regardless. |
| Tree-shaking | **POOR** | Static imports prevent dead-code elimination. V1/V2/V3/V5 code ships even when only V6 is used. |
| Runtime cost | **LOW** | Only one version renders at a time. React doesn't mount unused branches. |
| CSS conflicts | **LOW-MEDIUM** | V6 uses `.v6-root` scoping. V4 uses `.v4-root`. But `main.tsx` imports V1 global CSS (`global.css`, `research.css`, `advisor.css`, `client.css`, `traversal-map.css`) unconditionally. |

### 6.3 Recommendation

Convert to `React.lazy()` + `Suspense`:
```typescript
const V6App = lazy(() => import('./v6/V6App'));
// etc.
```
This would eliminate ~80% of dead code from the production bundle. Low effort, high impact.

### 6.4 Dependencies

| Package | Purpose | Justified? |
|---|---|---|
| `@salesforce-ux/design-system` | SLDS base CSS | Yes — imported in `main.tsx` |
| `@tanstack/react-query` | Query client provider | Yes — used in `App.tsx` |
| `@visx/*` (5 packages) | Chart rendering (MiniTimeline) | Yes — used for waterfall bars |
| `react` + `react-dom` | Core | Yes |
| `zustand` | State management | Yes — 5 stores |

No unnecessary dependencies. No bloat libraries.

---

## 7. OVERALL HONESTY SCORE

### Scoring Methodology

Each UI feature scored on a 3-point scale:
- **REAL (3):** Wired to backend, processes live data, no hardcoded fallbacks in the happy path
- **PARTIALLY REAL (2):** Wired to backend but has hardcoded fallbacks or depends on backend features not yet emitting data
- **THEATER (1):** Hardcoded data presented as if it were live, or UI that looks functional but does nothing

### Feature Scores

| Feature | Score | Rationale |
|---|---|---|
| Research brief streaming | 3 | Real Bedrock inference, real citations, real tool calls |
| Advisor action plan + HITL | 3 | Real backend round-trip, real gate enforcement |
| Client FAQ + escalation | 3 | Real LLM routing, real intent detection |
| WebSocket/HTTP transport | 3 | Real dual-transport with reconnection, backoff, auth |
| Traversal map | 3 | Real topology (43 nodes), real tool_call events drive state |
| 7-gate tracker | 3 | Real gate events, real state machine, real animation |
| Citation chips | 3 | Real span_ids, real source_chunk fetch |
| Persona switching | 3 | Real backend persona routing, not just CSS |
| Auth (Cognito) | 3 | Real Cognito config in .env.production, real PKCE flow |
| Error handling | 3 | 4-tier error boundary, graceful degradation, reconnection |
| Theme toggle | 3 | Works as designed (local-only is correct) |
| Voice input | 3 | Real browser API, graceful fallback |
| Document ingest | 2 | Real endpoint call, but catch block shows success message even on failure |
| Client 360 holdings | 2 | Real CRM fetch exists, but hardcoded 62/22/9/4 fallback is misleading |
| Advisor queues | 2 | Fully wired store + UI, but empty because backend doesn't emit events |
| Demand signals | 2 | Wired to queue store, but empty |
| Sentiment sparkline | 1 | Placeholder text only — no chart_intent support |
| Market pane live data | 2 | Extracts from brief markdown (real), but "TICKER" fallback and "finnhub" label shown even without data |
| Sample queries | 3 | Real backend calls on click, not just UI sugar |
| Filings pane | 2 | Shows real cited chunks, but only when citations have `source_type: 'filing'` |

### Aggregate Score

**Total: 52 / 60 = 86.7%**

### Breakdown

- **REAL (score 3):** 14 features (70%)
- **PARTIALLY REAL (score 2):** 5 features (25%)
- **THEATER (score 1):** 1 feature (5%)

---

## 8. EXECUTIVE SUMMARY

### What Is Genuinely Impressive

1. **The transport layer is production-grade.** `wsClient.ts` implements real WebSocket with exponential backoff, jitter, send queue, and auth expiry handling. `httpAgentTransport.ts` is a thoughtful HTTP-to-streaming adapter that synthesizes the full event sequence the UI expects. This is not demo code.

2. **The state management is architecturally sound.** Five Zustand stores with clear separation of concerns. The `useStreamingTurn` hook is a well-designed event dispatcher that coordinates brief, traversal, and history stores from a single inbound message stream.

3. **The topology is real.** `topology.json` has 43 nodes and 53 edges generated from the actual backend agent registry. The traversal store's `toolCallStart/End` → node state transitions are driven by real tool_call events, not animation timers.

4. **The 7-gate tracker is code-enforced.** The gate state machine in `useGateTracker.ts` processes real `gate_passed/started/failed` events. The `SEVEN_GATES` constant matches the backend's canonical gate names. The `turn_complete.gate_trace` replay at 400ms intervals is a legitimate UX pattern for non-streaming transports.

5. **The test suite tests real wiring.** Integration tests use `MockWebSocket` to drive the full event pipeline — `turn_started → brief_delta → citation → tool_call_start/end → turn_complete`. They verify real message payloads, not just DOM snapshots.

### What Must Be Disclosed

1. **The Client 360 allocation bar has a hardcoded fallback** (62/22/9/4/3%) that renders when no CRM data is available. This should be replaced with a loading/empty state.

2. **Advisor queues are wired but empty.** The backend doesn't emit `queue_update` events in most flows. The UI is honest about this (shows "Empty — items arrive via queue_update events") but a demo audience won't read italic placeholder text.

3. **The sentiment sparkline is pure placeholder.** No `chart_intent` event support exists in the backend.

4. **Document ingest shows a success message even on fetch failure** (`catch` block in `handleDrop` says "queued for ingestion via Textract pipeline"). This is misleading.

5. **Six UI versions ship in one bundle** with no code splitting. Not a honesty issue, but a technical debt item.

### The Bottom Line

**This is not a Potemkin frontend.** The V6 UI is a real application with real backend wiring, real state management, real error handling, and real transport infrastructure. The ~87% honesty score reflects a codebase where the vast majority of features make real API calls and process real data. The remaining ~13% consists of legitimate empty states (queues, demand signals) and one genuinely misleading hardcoded allocation bar.

The gap between "what the UI can render" and "what the backend currently emits" is the primary source of apparent mockery. The frontend is ahead of the backend in several areas — it's wired and waiting for data that hasn't arrived yet. That's an integration gap, not UI theater.
