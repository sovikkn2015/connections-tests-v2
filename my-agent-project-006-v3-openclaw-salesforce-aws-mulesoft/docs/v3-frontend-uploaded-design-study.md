# v3 Frontend — Uploaded UIUX Design Study

**Source**: `UIUX Design.zip` uploaded by user on `feat/006-v3-live-demo` → extracted to `.kiro-tmp-005-e2e/uiux-design/UIUX Design/`
**Date**: 2026-04-30
**Branch**: `feat/006-v3-live-demo`
**Status**: study only — no frontend code changed

---

## What was uploaded

Seven files, 2,666 lines total, self-contained browser-loadable design mockup:

| File | Lines | Role |
|---|---|---|
| `FSI Wealth Platform (1).html` | 44 | Shell. Loads React 18 + Babel-standalone UMD, wraps the three personas in `DesignCanvas` |
| `styles.css` | 813 | All design tokens + every component's CSS. Single file, no build step |
| `design-canvas (1).jsx` | 622 | Figma-like wrapper: pan/zoom, reorderable artboards, focus overlay, keyboard nav |
| `trace-shared.jsx` | 284 | Shared `TraversalMap` + `Timeline` + per-persona lit patterns |
| `research.jsx` | 429 | Sarah Chen's research terminal (brief, market pane, filings, sentiment, demand) |
| `advisor.jsx` | 323 | Marcus Kerrigan's advisor workbench (7-gate tracker, queues, conversation, client 360) |
| `client.jsx` | 143 | Eleanor Vance's WhatsApp channel inside a phone bezel + trace stack |

The HTML loads all five JSX files via `<script type="text/babel" src=…>` so anyone can just double-click the HTML and see the full design in a browser. That's deliberate — it's a design artifact first, not production code.

---

## Design system (what the user wants)

### Named personas
- **Sarah Chen** — Sr. Equity Analyst → research terminal
- **Marcus Kerrigan** — Sr. Wealth Advisor → advisor workbench
- **Eleanor Vance** — Client (Tier-A, Boston, since 2009) → liaison channel

These are explicit in the uploaded files. Current v3 frontend has no named personas.

### Tokens (partial extract from styles.css)
- **Brand**: `--w360-brand-*` (Workflow 360 blue, `#1B96FF` primary)
- **Forensic dark**: `--forensic-bg-0…5`, `--forensic-text-0…6`, `--forensic-line`, `--forensic-elevated`
- **Neutral SLDS**: `--n-000…900` (for advisor light surface)
- **Semantic**: `--success-{300,500}`, `--warning-{300,500}`, `--error-{300,500}`
- **Trust-spine**: separate colors per role — skill, mcp, gate, coord
- **Channel**: `--channel-header` (WhatsApp green `#075E54`), `--channel-accent`
- **Fonts**: Inter (UI), JetBrains Mono (traces + metrics), Source Serif 4 (brief prose)

### Animations
- `pulse` — node breathing at 1B96FF glow
- `nodePulse` — specialist "in-flight" signal
- `dashFlow` — edge stroke animates along dashed path (proves traffic is moving)
- `gateScan` — active gate sweep line

### Three shared atoms
1. `PersonaHeader` — W360 logo, persona label, nav (Research / Advisor / Liaison), `connected` dot, user badge
2. `TraversalMap` — always three orchestrators across the top, specialists fan out below the **active** one, dim/lit pattern parameterized by `persona`
3. `Timeline` — end-to-end waterfall, indented rows, per-kind bar colors (`orch`, `skill`, `mcp`, `human`), per-persona data

### Trust-spine strip
A grid `1.35fr : 1fr` with an eyebrow row. Every persona screen ends with:
- trust-spine strip (map + timeline side-by-side or stacked)
- audit strip at the bottom (trace ID, WS state, spans, cost, Langfuse link)

---

## Persona-by-persona: uploaded vs live v3

### 1 · Research Terminal — Sarah Chen

**Uploaded design** (`research.jsx`, 429 LOC):
- Dark forensic surface, 1440×1024 artboard
- Toolbar: query input + `Run ⌘↵` + `{ }` JSON + `⤓ export brief`
- Body grid: brief pane (wide) · market+filings (col 2) · sentiment+demand (col 3)
- Brief pane has: running chips ("sec-edgar · 412ms", "tavily-news · running"), serif prose, citation chips (pending + resolved states), MNPI redaction callout block, inline SVG bar chart with guide bar for Q1e (dashed outline), risk dispersion section
- Market pane: NVDA $211.27 + spark line area fill + `1D/5D/1M/YTD` grid
- Filings: 5-row table with filing type chips (10-Q, 10-K, 8-K, DEF 14A), section + page, live EDGAR indicator
- Sentiment: `+0.41` number + 30 bar chart (green/red per day) + top topics chips
- Demand signals: 3 clickable items with `accept →` button
- Bottom: `TraversalMap persona="research"` + `Timeline persona="research"` + `AuditStrip`

**Live v3** (`ResearchTerminal.tsx`, 192 LOC):
- `PersonaHeader` (not named)
- Toolbar: query input + `Run ⌘↵` (no JSON/export)
- Body grid: `BriefPane` (left) + `research-right` column of 4 panes (`MarketPane`, `FilingsPane`, `SentimentPane`, `DemandSignalsTab`)
- `TraversalMapPanel` + `EndToEndTrace` + `AuditStrip` at bottom
- Drill-down side drawer for citation chunks (uploaded design has no drill-down — it uses `onCiteClick` modal)
- **Real WebSocket streaming via `useAgentSocket` + `useStreamingTurn`**

**Gap summary** — visual delta is big, structural delta is small. The v3 code already has most of the pieces (brief, market, filings, sentiment, demand, traversal map, trace, audit strip). What's missing is:
1. Named analyst in header ("Sarah Chen · Sr. Equity Analyst")
2. Running-chip row inside brief showing live specialist latencies
3. MNPI redaction callout component inside brief
4. Serif font on brief prose (design uses Source Serif 4)
5. Inline SVG deterministic chart with a guide (dashed outline) bar for forward estimate
6. Citation chips have `--pending` visual state
7. Market pane uses area-fill sparkline (current is ?)
8. Filings chips colored by filing type
9. Running-chip states in audit strip pills (`market-spec [ok]`, `sent-spec [running]`)
10. Demand signals have inline `accept →` button

### 2 · Advisor Workbench — Marcus Kerrigan

**Uploaded design** (`advisor.jsx`, 323 LOC):
- SLDS light surface, 1440×1280 artboard (taller than research because of the 7-gate strip)
- 7-gate tracker at top, `activeIdx=3` (gate ④ HITL active, ①②③ passed, ⑤⑥⑦ pending) — each gate has num + name + detail + latency
- Body grid: `QueuesPanel` (Actions/Insights/Tasks tabs) · `ConversationPanel` (messages + action card + composer) · `ClientContextPanel` (Client 360)
- `ActionCard` is the crown jewel — sit inside the conversation as an AI message — with plan details (order/symbol/qty/proceeds/TIF/venue), concentration diff (`14.2% → 9.5%` with policy-band check), and 3 buttons (`Approve & submit`, `Edit plan`, `Deny`) + keyboard hints (`⌘↵ approve · ⌘⌫ deny · dual-auth required`)
- `ClientContextPanel` has: avatar, tier, holdings overview ($8.42M AUM, +$1.91M P/L, $284K cash), IPS allocation bar (stacked segments) + legend with policy band, top concentrations (NVDA 14.2% ⚠, MSFT 11.8%…), recent signals (concentration breach + suitability re-attestation)
- Trust-spine strip below: map + timeline, dedicated eyebrow `"Trust spine · same orchestrator graph as Sarah's research, now lit through advisor_orch"` with `"conversation 4f8c-2a11 → plan 9d3a-71fc · gate ④ HITL"`
- `AdvisorAuditStrip` is forensic-dark even though the advisor surface is light — deliberate contrast

**Live v3** (`AdvisorScreen.tsx`, 102 LOC + `SevenGateTracker.tsx` 36 LOC + `QueuesPanel.tsx` + `ConversationPanel.tsx` + `ClientContextPanel.tsx` + `HitlApprovalDialog.tsx`):
- `PersonaHeader` (not named)
- `SevenGateTracker` — only shows when `planInFlight` (uploaded shows always, just dim when idle)
- Body grid is right — `QueuesPanel` · `ConversationPanel` · `ClientContextPanel`
- `HitlApprovalDialog` is a modal (uploaded design puts the action card **inline in the conversation** as an AI agent message — big UX difference)
- `TraversalMapPanel` + `EndToEndTrace` + `AuditStrip` at bottom
- Real WS streaming + optimistic approval + gate tracker hook

**Gap summary** — advisor is where the biggest UX redesign lives:
1. **Action card must move from modal → inline AI message in conversation** (the uploaded design is intentional: the plan is presented *by the agent, in the conversation*, not as an interrupt)
2. 7-gate tracker should be always visible (dim when idle), with gate detail + latency per cell
3. Queue tabs: Actions / Insights / Tasks (current is Alerts-only)
4. Queue items need unread + selected + priority color coding
5. Client 360 needs IPS allocation bar with policy bands, recent signals list, concentration breach warnings
6. Conversation needs named speakers (EV, MK, AI) + message structure (avatar, header row, body, attached action card as child of an agent message)
7. Composer needs slash-command affordance (`/research /draft /schedule`)
8. Audit strip includes HITL hold indicator (`⏸ HITL hold · gate ④`) + plan-held-duration counter (`plan held 11.4s`)
9. Trust-spine eyebrow text that explicitly references cross-persona trace IDs

### 3 · Client Liaison — Eleanor Vance

**Uploaded design** (`client.jsx`, 143 LOC):
- WhatsApp surface at 1440×1024, with a **3-column caption grid** — left caption ("Channel surface") + phone in middle + right caption ("Behind the scenes: One trust spine, three surfaces") with `TraversalMap compact` + `Timeline`
- Phone bezel with notch, status bar (`9:41 · 5G · 96%`), WhatsApp header (back arrow, W360 avatar, name, online, phone+menu icons)
- Thread has `TODAY` date divider, `bubble--in` / `bubble--out` for agent vs client
- Agent bubbles have `bubble__rich` nested block for structured payloads (e.g. "Suggested next step: Loop in Marcus")
- Named speaker badges when RM Marcus chimes in (agent-bot vs human-RM in same thread)
- Permanent yellow disclaimer: `ⓘ For informational purposes. Your RM makes recommendations.`
- CTA row: `📅 Schedule call` (primary green) + `👤 Ask my RM` (outline green)
- Composer: emoji + text input + attachment + camera + send circle

**Live v3** (`ClientChannel.tsx`, 148 LOC + `ChatBubble.tsx` + `CtaButtons.tsx`):
- Single-column layout (no captions beside phone, no phone bezel)
- Basic WhatsApp header, no status bar / notch
- Thread from agent + client
- Disclaimer row
- CTA buttons + composer
- Real WS streaming via `useAgentSocket`

**Gap summary** — client is the simplest screen but the uploaded design adds context:
1. Phone bezel with notch + status bar (design artifact quality)
2. 3-column grid with explanatory captions and **embedded traversal map + timeline on the right** ("same trust spine, three surfaces" — this is the payoff shot)
3. Named RM bubble inside the thread (human hand-off visible in the channel)
4. Rich structured bubbles (`bubble__rich`) for "Suggested next step" + future extensions
5. `TODAY` date divider in thread
6. CTA styling as primary (filled green) + secondary (outline green)

---

## Shared components — uploaded vs live

### TraversalMap

**Uploaded** (`trace-shared.jsx` `TraversalMap`, ~150 LOC):
- **Always shows 3 orchestrators across the top** (`research_orch`, `advisor_orch`, `liaison_orch`) — with only the active one "pulse" and the other two "dim" but visible
- **Ghost edges between orchestrators** (dashed dim horizontal lines) — shows the trust spine is one graph, even when only one persona is lit
- Specialists fan out below the active orchestrator only (positioned by `activeOrchX`)
- MCPs below specialists, one per specialist by array index
- Per-persona `lit` config (`specs` + `mcps` dicts of state strings: `solid`, `pulse`, `dim`)
- Fixed-width 1240 viewBox, absolute positioning, bezier edges with `dashFlow` animation for dashed-lit state
- Node chip + label, node color by status via `data-status` attr

**Live v3** (`TraversalMap.tsx`, 356 LOC):
- Pure function layout `layoutTopology` — 7 rows (6 layer rows + 1 trust row)
- Nodes bucketed by `layer` field from topology.json
- Persona dimming via `isPersonaDimmed` predicate
- Deterministic layout (sort by persona, then id)
- Correlation ID in legend
- Click + keyboard handler for node interaction
- **No ghost edges between orchestrators**
- **Shows ALL nodes for ALL personas at all times** (the uploaded design shows all 3 orchs but only the active persona's specialists+MCPs)

**Verdict**: the live implementation is more powerful (loads from topology.json, supports any graph shape) but the uploaded design is more *legible* (always-3-orchs layout makes "trust spine" idea obvious at a glance). To adopt the uploaded look while keeping the live data-driven approach:
- Add `orchestrator-row` as layer 0 sibling so all 3 orchs always render at top
- Render ghost edges between orchestrators explicitly (they're not in topology.json — they're a **UI construct** that says "these share context")
- Hide non-active personas' specialists + MCPs when `activePersona !== null` (they exist in the graph but are not lit)

### Timeline

**Uploaded** (`trace-shared.jsx` `Timeline`, ~60 LOC of component + per-persona row data):
- Fixed row data per persona (`research`, `advisor`, `client`)
- Research: 11 rows (orch + 5 specialists + 5 MCPs), indented with `├│└` chars
- Advisor: 10 rows including `HITL hold (gate ④)` as a `human`-kind bar (color coded differently) + `on approve → mulesoft-mcp` queued
- Client: 10 rows with refusal path explicit (`intent_classifier → scope check: 'recommend' → refusal_template → handoff_specialist`)
- Per-persona caption at bottom explaining what the timeline proves
- `⎋ open in Langfuse` ghost button top-right

**Live v3** (`EndToEndTrace.tsx` + `MiniTimeline.tsx`):
- Not studied yet (file inventory shows they exist). Likely data-driven from traversal store.

**Verdict**: adopt the uploaded per-persona captions ("proves `asyncio.gather`", "execution gated, not advisory", "intent shift caught client-side — refusal returns before any MCP touch"). They turn the timeline from telemetry into a *legend* for what the audience is supposed to see.

### PersonaHeader

**Uploaded**: brand logo (inline SVG `W360Logo`) + persona label + nav tabs (Research / Advisor / Liaison) with active state + user badge + avatar circle + `connected` dot.

**Live v3**: exists (`PersonaHeader.tsx`) — not studied in detail, but known from earlier reads it doesn't include named users.

### AuditStrip

**Uploaded**: trace ID (8 chars), WS state (`● ws: open`), per-specialist pills with status (`market-spec [ok]`), right-aligned summary (`turn 2.31s · 11 spans · cost $0.082 · ⌥L Langfuse`). Advisor variant adds `⏸ HITL hold · gate ④` + `plan held 11.4s`.

**Live v3**: exists (`AuditStrip.tsx`) — structure not yet verified against design.

---

## DesignCanvas wrapper (pan/zoom/reorderable artboards)

The uploaded `design-canvas (1).jsx` is a 622-LOC Figma-like wrapper that presents the three persona screens as **artboards on an infinite canvas**:
- Pan with space+drag or middle mouse
- Zoom with `Cmd/Ctrl + scroll` or `±` keys, fit with `0`
- Reorder artboards by dragging
- Click an artboard label to focus (Esc to unfocus, arrows to navigate)
- Section titles, subtitles, screen labels at top-left of each artboard

**This is a presentation/design-review wrapper, not a production shell.** In the live app we'd route `/research`, `/advisor`, `/client` — not show all three on one canvas. The wrapper is for walking a stakeholder through the three surfaces in one browser window.

**Recommendation**: keep the DesignCanvas as a **separate design-review route** (e.g. `/canvas`) that loads the same React components but wraps them in the canvas shell. That gives us:
- Production app: three separate routes, each full-screen
- Design review: `/canvas` that shows all three artboards for stakeholders / investors / demos

---

## Comparison to my earlier v2 UX design doc

`docs/v3-frontend-v2-ux-design.md` (written earlier, 42KB) proposed a different direction — LangSmith-Studio-inspired split panes, Linear-like keyboard density, Bloomberg-dense data grids. The uploaded design **supersedes** it. Key differences:

| Axis | My earlier v2 proposal | Uploaded design (user's pick) |
|---|---|---|
| Research surface treatment | Terminal-style with REPL input history | Brief-first, data panes in sidebar, citation-enforced |
| Advisor ActionCard | Modal approval (consistent with current v3) | **Inline in conversation** (big shift) |
| Client channel | Standalone chat | Phone bezel + captioned trust-spine reveal |
| Traversal map | Unified topology always | 3-orch layout with ghost spine edges |
| Named personas | No | Yes (Sarah, Marcus, Eleanor) |
| Design review mode | N/A | DesignCanvas wrapper for stakeholder walkthroughs |
| File format | Markdown doc | Runnable HTML + JSX mockup |

The uploaded design is more *stageable* — the user can show it to a client tomorrow without us shipping any code. My earlier doc was more abstract. **The uploaded one wins** — treat `v3-frontend-v2-ux-design.md` as superseded.

---

## Migration plan — uploaded design → live v3 frontend

Ordered from safest (style-only) to most invasive (structural).

### Phase 1 · Tokens and typography (low risk, 2–4 h)
1. Port `styles.css` CSS custom properties into `frontend/src/styles/global.css` — `--w360-brand-*`, `--forensic-*`, `--n-*`, `--success/warning/error-*`, `--channel-*`
2. Load Inter + JetBrains Mono + Source Serif 4 via Google Fonts (or self-host)
3. Wire `.w360-mono`, `.w360-label`, utility classes globally
4. No behavior changes — only visual refresh

### Phase 2 · PersonaHeader redesign (low risk, 1–2 h)
1. Inline `W360Logo` SVG (18×18)
2. Add nav tabs (Research / Advisor / Liaison) with `is-active` state tied to current route
3. Add user name + avatar (sourced from session store `principalId` → render first initials)
4. Add `connected` dot that reacts to WS state

### Phase 3 · AuditStrip redesign (low risk, 1 h)
1. Add per-specialist pills with running/ok/error status sourced from traversal store
2. Add right-aligned summary: span count, turn duration, cost estimate, `⌥L Langfuse` link
3. Add advisor-only HITL-hold indicator + held-duration counter

### Phase 4 · TraversalMap — 3-orchestrator layout (medium risk, 4–6 h)
1. Add layer-0 `orchestrator-row` that always renders all three orchestrators side by side
2. Add ghost edges between orchestrators as a UI construct (not in topology.json — construct them in component)
3. Add persona-dimming: specialists + MCPs of inactive personas are dim but present
4. Keep the existing `layoutTopology` pure function; add a 3-orch-top variant gated by a prop
5. Dash-flow animation for pulsing edges (add CSS keyframe `dashFlow` in `traversal-map.css`)

### Phase 5 · Research terminal polish (medium risk, 3–5 h)
1. Name Sarah in header
2. Running-chip row inside BriefPane fed by traversal spans (`market_spec [ok, 920ms]`, `sentiment_spec [running]`)
3. MNPI redaction callout component (always check `brief.mnpi_redactions_applied` flag before showing)
4. Serif font on brief prose (Source Serif 4)
5. Citation chips `--pending` state while resolve is in-flight
6. Filings table chip colors per filing type (10-Q blue, 10-K darker blue, 8-K amber, DEF 14A purple)

### Phase 6 · Advisor ActionCard as inline AI message (higher risk, 6–8 h)
This is the biggest UX shift. Currently `HitlApprovalDialog` is a modal interrupt. Uploaded design renders the action card **inline as an AI message** inside the conversation.

1. Create `InlineActionCard.tsx` — takes the same `ActionPlan` shape as `HitlApprovalDialog`
2. Modify `ConversationPanel.tsx` to:
   - Show AI-attributed message bubbles when an agent speaks ("Workflow 360 · Advisor · action_specialist")
   - Render `InlineActionCard` as a child of the AI message when `pendingPlan !== null`
   - Scroll new action cards into view
3. Keep `HitlApprovalDialog` as a fallback (e.g. for focused approve-only sessions)
4. `SevenGateTracker` becomes always-visible at top, dim when no plan in flight (instead of conditionally rendered)
5. Queue tabs: Actions / Insights / Tasks (add Insights + Tasks tabs — only Actions is wired today)
6. Client 360 — add IPS allocation bar with policy bands + recent signals list

### Phase 7 · Client channel — phone bezel + trust-spine reveal (medium risk, 3–4 h)
1. Wrap `ClientChannel` body in a phone bezel (notch + status bar)
2. Change layout from single-column to 3-column grid with side captions (design-review or production mode toggle)
3. Add `TODAY` date divider in thread
4. Add named RM bubble support (when a real RM replies via WhatsApp Business API bridge)
5. Rich `bubble__rich` structured bubble component for "Suggested next step"
6. Embed `TraversalMap compact` + `Timeline` as a stack on the right (showing the same trust spine is lit)

### Phase 8 · DesignCanvas (optional, design-review-only, 4–6 h)
1. New route `/canvas` behind a feature flag `VITE_DESIGN_CANVAS=1`
2. Port `DesignCanvas` + `DCSection` + `DCArtboard` components (maybe adapted from the uploaded JSX)
3. Wrap `<ResearchTerminal/>`, `<AdvisorScreen/>`, `<ClientChannel/>` as artboards
4. Use this route for stakeholder walkthroughs and demo dry-runs

### Total estimate
- Phases 1–3: ~5 h (style-only pass, no behavior change, safe to deploy)
- Phases 4–5: ~8 h (visual refresh of traversal map + research brief)
- Phase 6: ~7 h (biggest UX shift — inline action card)
- Phase 7: ~4 h (client polish)
- Phase 8: ~5 h (design-review wrapper, optional)

**Total: 20–30 h for a full port**, or 5 h for Phases 1–3 to get a visual refresh without behavior risk.

---

## What the uploaded design does NOT solve

Be honest: this is a visual+interaction design. It does not fix any of the backend narrative gaps documented in `v3-design-vs-built-vs-deployed-v2.md`:

- Narrative 1 still has 2 specialists timing out
- Narrative 2 still needs `rm_handoff` skill + `Research_Request__c` SObject
- Narrative 5 still needs MuleSoft CloudHub deployed
- MNPI redaction callout is a UI component — the actual redaction already works server-side

A better frontend won't make a broken narrative demoable. Run the backend fixes (`rm_handoff`, MuleSoft deploy, specialist timeouts) in parallel with this UX port.

---

## Files to reference when implementing

**Uploaded source (read-only, don't commit):**
- `.kiro-tmp-005-e2e/uiux-design/UIUX Design/styles.css` — design tokens + all component CSS
- `.kiro-tmp-005-e2e/uiux-design/UIUX Design/trace-shared.jsx` — TraversalMap + Timeline visual logic
- `.kiro-tmp-005-e2e/uiux-design/UIUX Design/research.jsx` — research surface composition
- `.kiro-tmp-005-e2e/uiux-design/UIUX Design/advisor.jsx` — advisor surface + ActionCard
- `.kiro-tmp-005-e2e/uiux-design/UIUX Design/client.jsx` — client surface + phone bezel

**Live targets (edit here):**
- `frontend/src/styles/global.css` — absorb uploaded tokens
- `frontend/src/components/PersonaHeader.tsx` — rewrite with W360 branding
- `frontend/src/components/TraversalMap.tsx` — add 3-orch-top layout variant
- `frontend/src/components/AuditStrip.tsx` — add per-specialist pills
- `frontend/src/personas/research/BriefPane.tsx` — add running-chip row + MNPI callout
- `frontend/src/personas/advisor/ConversationPanel.tsx` — inline ActionCard
- `frontend/src/personas/client/ClientChannel.tsx` — add phone bezel + side captions

---

## Recommendation

Start with **Phase 1 + Phase 2 + Phase 3** (tokens + PersonaHeader + AuditStrip) as a single commit. That delivers ~80% of the visual shift with zero behavior change and is safe to roll back. The rest (map layout, inline ActionCard, phone bezel) can land as separate PRs behind feature flags if needed.

Defer or skip Phase 8 (DesignCanvas) unless the team wants a stakeholder-walkthrough mode — it's design-review infrastructure, not production.

One open question for the user:
**Should the ActionCard move inline (uploaded design's stance) or stay as a modal (current v3)?** This is the most opinionated shift and affects how HITL works. The uploaded design's answer is "inline, because the plan is the agent's speech act — not a system interrupt." That reframes HITL from approval-modal to conversation-turn. Worth confirming before doing Phase 6.
