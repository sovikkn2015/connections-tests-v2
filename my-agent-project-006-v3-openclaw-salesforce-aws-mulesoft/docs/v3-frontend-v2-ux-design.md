# 006 V3 — Frontend/UX v2 Design Doc

> **Status:** design only. No build. This is the doc to argue about before writing code.
> **Date:** 2026-04-30
> **Companion to:** `v3-narrative-arc.md`, `v3-demo-choreography.md`, `v3-live-traversal-ui-design.md`
> **Scope:** three-persona SPA replacement — research terminal, RM workbench, client channel. Same backend, same WebSocket events, same AgentCore.

---

## 1. The problem with v1

Before designing v2, honest about what's not working in the current UI.

### What the current SPA gets right (keep these)

- **Three visual treatments, one design language.** Research terminal is dense. RM workbench is queue-driven. Client channel is chat. This is fine and differentiated.
- **SLDS design system.** Salesforce-native feel where it matters.
- **Zustand + TanStack Query + Vite + TS strict.** Stack is modern, fast, type-safe.
- **Component library** — `SevenGateTracker`, `CitationChip`, `DeterministicChart`, `AuditStrip`, `TraversalMap`. All there, all wired. None of this needs rebuilding.
- **Real WebSocket transport** (`useAgentSocket`, event discriminated union).

### What's not working

Based on the live demo observations + this assessment session:

1. **The live turn is invisible.** 25 seconds of silence between "Send" and the final brief. Panel sees a spinner. No streaming. No gate-by-gate lighting. No specialist "currently running" indicator. The "show the work" principle (2026 AI demo must-have) isn't landing.

2. **SevenGateTracker renders grey chrome that never lights up during the turn.** The backend doesn't emit gate events live (known gap). Even after the turn, the map fills all at once.

3. **TraversalMap does the same** — fills post-turn, not during. Viewer sees the shape but not the flow.

4. **Audit strip is an afterthought** — tucked at the bottom, shows `correlation_id · ws: open · 5 spans` in mono text. Hard to read on stage.

5. **Research terminal is busy but thin.** The 3-pane layout (brief | market/filings/sentiment) has dead space when a pane hasn't returned yet. When it does return, the panes fill with minimal output because specialists are brief.

6. **RM's screen has 4 queues but they're all stub data.** The working queue items are a single live `Client_Inquiry__c` row; the rest are seeds. Bounces between "impressive" and "mock."

7. **Client channel looks like WhatsApp but isn't.** The panel reads this as a tell. Without a real channel integration, the mimic is weaker than being upfront about the fact it's a web mockup.

8. **No cross-persona visualization.** The platform's biggest differentiator — Workflow 360, one brief cited across three personas — is nowhere on screen. The audit chain is only visible via SOQL.

9. **No way to inspect what just happened.** No hover-to-see-source-chunk, no click-to-see-Langfuse-span, no "why did this happen" explainability surface during the demo.

10. **Dense doesn't mean Bloomberg-dense.** Bloomberg packs 80×25 of meaningful info per screen. Our research terminal has 3 panes of 300 characters each and lots of whitespace.

---

## 2. Design principles for v2 — grounded in 2026 research

Eleven research-backed principles, each tied to a source. (All content rephrased for licensing compliance.)

### 2.1 Controlled autonomy, not autonomy
The 2026 enterprise AI bar is *bank-ready agents*, not raw model power. Demos that show visible human inspection points, deterministic guardrails, and explicit override surfaces read as production-capable. ([Virtido, 2026 Agentic Workflows](https://virtido.com/blog/agentic-workflows-patterns-best-practices-enterprise); [Forrester Finovate Europe 2026](https://www.forrester.com/blogs/finovateeurope-2026-from-ai-hype-to-bank-ready-execution/))

**v2 consequence:** every agent decision is visibly associated with a gate or a token. The UI shows "what the agent was allowed to do" as clearly as it shows "what the agent decided."

### 2.2 Show the work — the agent-canvas pattern
LangGraph Studio / LangSmith Studio set the bar: a *visual, walkable execution graph* where every step the agent takes is inspectable — prompt, tool call, result. This is now the industry-standard explainability surface. ([LangSmith Studio docs](https://docs.langchain.com/oss/javascript/langgraph/studio); [LangSmith Observability](https://docs.langchain.com/oss/python/langgraph/observability))

**v2 consequence:** the Architecture Map (planned in `v3-live-traversal-ui-design.md` but not fully realized) is promoted from a side panel to a primary persistent surface.

### 2.3 Tiered HITL approval — risk-proportional
2026 HITL research converges on: classify actions by risk, apply oversight proportionally, use tiered thresholds, make approval tokens and audit trails first-class citizens. One-size HITL overwhelms the reviewer and slows everything. ([Peakflo HITL Finance framework](https://peakflo.co/blog/human-in-the-loop-ai-finance-governance-framework); [Prometeo Agentic Banking](https://prometeoapi.com/en/blog/human-in-the-loop-agentic-banking); [Infolitz HITL matrix](https://www.infolitz.com/blog-post/human-in-the-loop-an-approval-matrix-for-ai-agents))

**v2 consequence:** the approval dialog isn't a single modal — it's an inline, tier-aware component that shows the risk class, threshold triggered, and required authority (RM solo vs dual-auth vs senior compliance) up front. Same component renders differently based on plan content.

### 2.4 Streaming everything the LLM does
Silence in a live demo reads as broken. The cold-open principle applies everywhere: every LLM-adjacent state change must surface *within milliseconds*. Even if the result is only 200ms away, the user sees progression, not a spinner. ([Luke Wroblewski, Showing the Work of Agents](https://lukew.com/ff/entry.asp?2142=); [Kawasaki, Demo God](https://guykawasaki.com/how-to-be-a-demo-god/))

**v2 consequence:** every node on the Architecture Map has four states (dim, pulsing, solid, error). The brief streams character-by-character. Skeleton states show tool names, not generic spinners.

### 2.5 Keyboard-first for power users
Linear, Raycast, VSCode-style command palette + keyboard nav is the 2026 norm for dense workflow apps. Analysts and RMs are the target users. They work in keyboard, not mouse. ([Linear Design System](https://blakecrosley.com/guides/design/linear); [UX Patterns command palette guide](https://uxpatterns.dev/patterns/advanced/command-palette))

**v2 consequence:** Cmd-K opens a command palette with actions across all three personas (switch persona, run query against ticker, open Langfuse trace, approve pending action, etc.). Arrow-key navigation through queues. No `/` shortcuts that require a mouse fallback.

### 2.6 Optimistic UI with reconciler
Modern action-heavy UIs (Linear, Notion, GitHub) show the result instantly; backend validation catches up async; a toast/inline marker rolls back on failure. This is the only way to make a latency-bound system feel crisp. ([Linear Design System](https://blakecrosley.com/guides/design/linear))

**v2 consequence:** clicking Approve on a HITL gate shows ✓ instantly; the gate event confirms or rolls back within seconds. Already partially wired via `useOptimisticApproval`; v2 formalizes this across every action path.

### 2.7 Bloomberg-density, not Bloomberg-black
Bloomberg's power isn't its color palette — it's the *meaningful grid*. Every character position on screen is signal. ([Natural20 on Bloomberg density](https://natural20.com/coverage/architecture-of-cognitive-efficiency-designing-ai-news-aggregators))

**v2 consequence:** research terminal gets a character-grid layout. Every pixel has a job. No decorative empty panes. If a specialist hasn't returned, its slot shows a labeled skeleton *with the tool name and expected latency*, not a blank box.

### 2.8 Headless 360 / API-first
Salesforce's own Spring 2026 direction is "Headless 360" — expose capabilities, don't bury them behind a UI. The frontend is a *client*, not the product. ([Salesforce Headless 360 announcement](https://www.salesforce.com/news/stories/salesforce-headless-360-announcement/))

**v2 consequence:** every UI component can be embedded elsewhere (Slack, Teams, SF mobile, standalone tablet dashboard). State lives in Zustand + WebSocket subscription; no DOM-coupled logic. Already mostly true; v2 makes it explicit.

### 2.9 Three-persona rigor
Advisor Winter '26 UI/UX upgrades from Salesforce drive the same conclusion: *advisor-productivity UIs are a distinct design target from client-facing UIs*. Mixing them hurts both. ([Vantagepoint on Salesforce Winter '26](https://vantagepoint.io/blog/sf/salesforce-winter-26-ui/ux-upgrades-boosting-advisor-productivity-at-scale))

**v2 consequence:** the three personas stay visually distinct but share a grid discipline. The design language is one language; the density and vocabulary differ by persona. Advisor gets Salesforce-dense. Research gets Bloomberg-dense. Client stays sparse and chat-first.

### 2.10 The audit trail is a product feature, not a log
HITL + compliance research all agrees: the audit trail must be queryable, human-readable, and accessible to the business user (not just ops). It's part of the demo. ([Evolution.ai on audit trails](https://www.evolution.ai/post/designing-human-in-the-loop-guardrails-for-agentic-financial))

**v2 consequence:** the End-to-End Trace strip at the bottom is elevated to a first-class "Audit Console" — collapsible but tagged, filterable by persona/gate/status, with one-click Langfuse handoff.

### 2.11 Cross-persona visualization is the moat
Most competitor demos are single-persona (Sarah OR RM OR client). The v3 platform's whole value prop is Workflow 360 — research cites through advisory cites through client messaging. That loop must be visible on screen.

**v2 consequence:** a net-new "Workflow 360" overview surface. Renders a cross-persona timeline: research brief at 6:45 → RM consumed at 7:15 → client messaged at 9:00 → action plan at 11:05. Same `Research_Brief_Id__c` threading through. Built from SOQL over `IR_Audit_Log__c` with `Research_Brief_Id__c` joins.

---

## 3. The v2 layout — three personas, one shell

### 3.1 The persistent shell (all three personas)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ▎ V3 Workflow 360                         🟢 sarah@firm · fsi-research · ⌘K │ ← 36px header
│     · Sarah · RM · Client                                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                          [persona-specific surface]                          │
│                                                                              │
│                                                                              │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  ARCHITECTURE MAP                                              ▾ expand       │ ← 200px
│   [ coord → research_orch → (5 specialists pulsing) → (4 MCPs) ]             │
│   [ 1.2s market-data  ·  3.0s sec-edgar  ·  2.1s news  ·  122ms compliance ] │
├──────────────────────────────────────────────────────────────────────────────┤
│  AUDIT CONSOLE      filter: [ research ] [ all gates ▾ ] [ today ]   ▾ 5 rows│ ← 36px collapsed
└──────────────────────────────────────────────────────────────────────────────┘
```

- Top: persona header with identity pill + persona switch + ⌘K command palette trigger
- Middle: 60–70% of vertical — the persona-specific surface
- Architecture Map: fixed 200px horizontal strip, collapsible to 32px
- Audit Console: collapsible to 36px; expands to full-screen modal when clicked

### 3.2 Sarah — Research Terminal

Bloomberg-density. Every grid cell earns its place.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  MY RESEARCH   |  CLIENT DEMAND (12 new)  |  WATCHLIST   |   +              │
├──────────┬───────────────────────────────────────────────────────────────────┤
│  QUERY   │                                                                   │
│  [ >_ ]  │  BRIEF  ▎ NVDA Pre-Earnings Research                              │
│          │                                                                   │
│ inline Q │  Thesis:                       [cites 7 · sources: SEC, Finnhub] │
│ suggest: │  NVDA's AI/data-center trajectory remains intact. Q4              │
│ "NVDA 52 │  guidance at $37B vs $33B consensus implies 14% upside            │
│  week"   │  to current print[¹]. Sentiment has shifted positive              │
│          │  over past 30d (+0.22 vs -0.15 prior window)[²].                  │
│          │                                                                   │
│          │  Risks:                                                           │
│          │  · Supply chain concentration on CoWoS capacity[³]               │
│          │  · Export controls to China (10-Q Item 1A.7)[⁴]                  │
│          │                                                                   │
│          │  Compliance: ALLOW   rm_consumable: true   mnpi: clean            │
│          │                                                                   │
│          │  [publish brief ▸]   [export to slack ▸]   [save draft ▸]        │
│          │                                                                   │
├──────────┼─────────────────┬────────────────────┬──────────────────────────┤
│          │  MARKET · NVDA  │  FILINGS  10-Q     │  SENTIMENT  30d          │
│          │  $213.17 -1.01% │  Filed 2026-01-28  │  chart -0.15 → +0.22     │
│          │  [sparkline]    │  Items 1A, 7 ready │  [news dots with click]  │
│          │  vol 42M/38M    │  ▸ Risk factors    │  headlines:              │
│          │  impl move 4.2% │  ▸ MD&A            │   · "NVDA crushes Q3"    │
│          │                 │  [drag PDF here]   │   · "Blackwell ramps..."│
└──────────┴─────────────────┴────────────────────┴──────────────────────────┘
```

Notes:
- **Left rail (48-char):** query input + inline typeahead suggestions from history. Cmd-Enter submits.
- **Main brief pane:** Markdown rendered, citations are live chips ([¹], [²]). Hover shows source; click opens Langfuse span inline.
- **Bottom three cells:** Market / Filings / Sentiment. Each shows something real even before the turn fires — live NVDA quote, last filing metadata, rolling sentiment. After the turn, they fill with the specialist's output.
- **Drag target:** the Filings cell accepts dragged PDFs (Textract pipeline integration — already built server-side).
- **Primary action buttons** render inline at end of brief, not in a toolbar.

### 3.3 RM — Advisor Workbench

Queue-driven, Salesforce-dense, action-primary.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  WRITE PATH GATES  ① Guard · ② MNPI · ③ Comp · ④ HITL · ⑤ Dual · ⑥ Mule · ⑦ │ ← sticky top bar
├──────────────────────────────────────────────────────────────────────────────┤
│  QUEUES               │  CONVERSATION                    │  CLIENT CONTEXT   │
│                       │                                  │                   │
│  INBOX (3)            │  > NVDA exposure for my book?    │  PATEL HOUSEHOLD  │
│  ▸ Patel · 4m         │                                  │  NAV $2.1M        │
│  ▸ Chen · 1h          │  [advisor_orch dispatched ·      │  ───────          │
│  ▸ Okafor · today     │   2 specialists · 1.1s]          │  Positions:       │
│                       │                                  │  · NVDA  6.2% ⚠  │
│  BRIEFS (1 new)       │  Based on Sarah's 7:08AM NVDA    │  · AMD   3.1%    │
│  ▸ NVDA pre-earnings  │  brief[¹], 3 of your clients     │  · AAPL  2.8%    │
│    (rm_consumable)    │  have exposure > 5%:             │                   │
│                       │                                  │  Last contact:    │
│  ALERTS (2)           │  · Patel   6.2%  no-contact 9d   │  9 days ago       │
│  ▸ NVDA -8% flagged   │  · Chen    7.8%  no-contact 12d  │                   │
│    3 clients (1 auto) │  · Kim     5.4%  no-contact 4d   │  Suitability:     │
│                       │                                  │  Moderate         │
│  PENDING (1)          │  [generate outreach drafts ▸]   │                   │
│  ▸ $1.2M NVDA sell    │  [start action plan ▸]           │  Cash: $38K       │
│    ↑ senior-compl     │  [ask Sarah for update ▸]        │                   │
│                       │                                  │                   │
└───────────────────────┴──────────────────────────────────┴───────────────────┘
```

Notes:
- **Sticky top bar:** the 7-gate tracker lives here, *always* visible, idle (grey) by default, lights up when an action plan is live. Panel sees gate progression without losing context.
- **Left queue column:** 4 queues, arrow-key navigable, badge counts reflect live SOQL.
- **Center conversation:** inline tool badges show agent activity (`[advisor_orch dispatched · 2 specialists · 1.1s]`). Brief citations ([¹]) click to open the source brief.
- **Primary action:** `[start action plan ▸]` inline, not in a toolbar. Opens a sidesheet with the action plan draft.
- **Right client context:** positions with inline warnings (⚠ at 6.2% because concentration exceeds threshold), last contact timestamp, suitability pill, cash.

### 3.4 Action Plan Sidesheet — HITL

When RM starts an action plan, a right-edge sheet slides in. No modal (modals break live demos). Tier-aware.

```
                               ┌─────────────────────────────────────────────┐
                               │  ACTION PLAN · $1.2M NVDA Liquidation       │
                               │  ────────────────────────────────────────   │
                               │                                              │
                               │  Risk class:    HIGH                         │
                               │  Thresholds:    > $500K trade (true)         │
                               │                 > $100K wire (true)          │
                               │  Approvals:     YOU + Senior Compliance      │
                               │                                              │
                               │  ── Plan Summary ──                          │
                               │  Sell 4,000 NVDA @ market                    │
                               │  Est. proceeds: $852,680                     │
                               │  Wire $1.2M → HSBC Singapore                 │
                               │  Suitability: REVIEW (cash hold rationale)   │
                               │                                              │
                               │  ── Gates ──                                 │
                               │  ①Guard  · passed                            │
                               │  ②MNPI   · passed                            │
                               │  ③Comp   · passed (check trading window)     │
                               │  ④HITL   · awaiting YOUR approval            │
                               │  ⑤Dual   · will fire (Senior required)       │
                               │  ⑥Mule   · queued                            │
                               │  ⑦Audit  · queued                            │
                               │                                              │
                               │  Token preview:                              │
                               │  sha256:48e2...3fa1  (plan_hash)             │
                               │  TTL: 4:43 remaining                         │
                               │                                              │
                               │  [ ✗ Reject ]            [ ✓ Approve ]      │
                               └─────────────────────────────────────────────┘
```

Notes:
- **Tier-aware header:** reads the plan, shows the risk class + thresholds + required authorities inline. RM knows upfront whether they can approve solo or need senior compliance.
- **Gates list live:** each gate shows status (passed/awaiting/queued) and updates as events arrive.
- **Plan-hash preview:** the SHA-256 of the canonical plan is shown before approval. Compliance-officer-friendly.
- **TTL countdown:** approval token has 5-min TTL; visible countdown.
- **Primary action is Approve**, not a row of 6 options. Reject is secondary. No dropdown menus.

### 3.5 Client — Channel

The simplest surface. WhatsApp-feel but honest about being a web mockup.

```
┌───────────────────────────────────────────────────────┐
│  ▎ Patel × Wealth Advisor · online                    │ ← 44px
├───────────────────────────────────────────────────────┤
│                                                       │
│                                   Yesterday, 9:00 AM  │
│                                     Should I be       │
│                                     worried about     │
│                                     NVDA?             │
│                                                       │
│                     9:02 AM                           │
│   Based on our research team's pre-earnings review    │
│   this morning, NVDA's thesis is intact. There's      │
│   short-term volatility around tonight's earnings.    │
│                                                       │
│   Your RM is available at 10 AM.                      │
│   [ Schedule call ]  [ Ask my RM ]                    │
│                                                       │
│   ⓘ For informational purposes. Your RM makes         │
│     recommendations.                                  │
│                                                       │
│                                          Today, 2:18 PM│
│                                     Yes, please call. │
│                                                       │
│                     2:19 PM                           │
│   Your RM is on the way.                              │
│   Reference: a0DgKDD327FD                             │
│                                                       │
├───────────────────────────────────────────────────────┤
│  [ 💬 Type a message... ]                      [▸]   │
└───────────────────────────────────────────────────────┘
```

Notes:
- **Small chat-only footprint.** Meant to live in an iframe for a tablet or be embedded in a kiosk.
- **CTA buttons inline** inside bot messages, not in a separate toolbar.
- **Reference IDs shown** so the RM can look up the inquiry in their queue.
- **Permanent disclaimer** in italics, below every advisory message.
- **No traversal map, no audit console** on this persona. The client doesn't need to see them.

---

## 4. The net-new surfaces — three pieces

### 4.1 The Architecture Map (promoted from side panel)

Already described well in `v3-live-traversal-ui-design.md`. v2 changes:

- **Promotes it to a persistent bottom strip** across all personas (except client)
- **Dim-by-default** — all 14 agents visible, only the ones this turn touched light up
- **Four states per node:** dim (not visited), pulsing (in-flight), solid-green (completed), red (error)
- **Edge animation:** when data flows orchestrator→specialist→MCP, the edge pulses in the direction of the call
- **Click any node →** opens the Langfuse span inline (no tab switch)
- **Persona filter:** 3 tabs at top right — `auto` (current persona), `research`, `advisor`, `liaison`. `auto` follows whoever's active.
- **Typo-safe topology:** renders from a JSON export of `topology.py` at build time; adding an agent to the Python registry automatically updates the map without frontend changes.

Research library references: LangSmith Studio graph view, Reaflow, React Flow. Standard pattern now.

### 4.2 The Workflow 360 Surface (new)

The cross-persona differentiator. **This is the demo moat.**

Renders a horizontal swim-lane timeline:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  WORKFLOW 360 · NVDA · 2026-04-30                           brief_id a0G...  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   SARAH         ●───────────┐                                                │
│   research                  │                                                │
│                             ▼                                                │
│   RM                        ●──────────┐                                     │
│   advisor                              │                                     │
│                                        ▼                                     │
│   CLIENT                               ●──────────┐                          │
│   liaison                                         │                          │
│                                                   ▼                          │
│   EXECUTION                                       ●───── filled              │
│                                                                              │
│   6:45 AM        7:15 AM          9:00 AM      11:05 AM     11:09 AM         │
│                                                                              │
│   ● click any node to expand the audit row                                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

- Built entirely from SOQL: `SELECT * FROM IR_Audit_Log__c WHERE Research_Brief_Id__c = 'a0G...' ORDER BY CreatedDate`
- Every node is a real audit row — click expands the full record
- Hover shows: persona, principal_id, agent_id, tool_names used, latency_ms
- Works retroactively for any brief in history
- **Addressable URL:** `/workflow360/a0GgK000009JPFHUA4` — shareable link to any past turn chain

This is what no competitor demo has. AWS's AI Advisor demo is single-persona. Anthropic's demos are single-persona. We show the thread.

### 4.3 The Audit Console (elevated)

Current v1 bottom strip is `correlation_id · ws: open · 5 spans`. v2 turns it into a first-class collapsible console.

Collapsed (36px):
```
│  🟢 AUDIT · 12 events today · filter: all ▾                           ⌃⎵ ▴  │
```

Expanded (modal or split-view):
```
┌──────────────────────────────────────────────────────────────────────────────┐
│  AUDIT CONSOLE                       filter:[persona]  [gate]  [status]  [✕] │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  TIME       PERSONA    AGENT              ACTION              LINKS          │
│  14:30:47  research    research_orch      RESEARCH_PUBLISHED  [brief][langf] │
│  14:30:12  research    publish_brief      ADVISORY_QUERY      [langf]        │
│  14:30:11  research    compliance_screen  ALLOW               [langf]        │
│  14:30:05  research    market_specialist  TOOL_CALL_OK        [span][langf] │
│  14:30:05  research    filings_specialist TOOL_CALL_OK        [span][langf] │
│  14:30:04  research    sentiment_spec     TOOL_CALL_OK        [span][langf] │
│  14:30:03  research    research_orch      TURN_STARTED        [langf]        │
│                                                                              │
│  expand row → shows gate_trace JSON, payload preview, MuleSoft ref if any    │
└──────────────────────────────────────────────────────────────────────────────┘
```

- Backed by live SOQL over `IR_Audit_Log__c`
- Filter by persona, gate, status, date range
- Click [langf] → opens Langfuse span in new tab
- Click [brief] → opens the related brief in-context
- Expand row → shows gate_trace JSON + payload preview (MNPI-scrubbed)

This is the compliance-officer view. Most competitor demos hide this. We surface it.

---

## 5. Interaction discipline — v2 rules

### 5.1 Keyboard-first (Linear pattern)

```
⌘K           command palette — search actions, personas, queries, trace IDs
⌘1 ⌘2 ⌘3     switch to Sarah / RM / Client
⌘⏎          submit query (all personas)
⌘K then "approve <id>"    approve a HITL action
⌘K then "langfuse"        open current trace in Langfuse
⌘/           toggle audit console
j/k          move up/down queue rows
enter        open selected queue item
esc          close sidesheet / modal
⌘Y           yes (on approve dialog)
⌘N           no
```

### 5.2 Streaming everywhere

Every turn has four visible progression signals:
1. Architecture Map lights up node-by-node (requires backend gate events, one known gap)
2. Specialist skeletons in the research terminal show tool-name + spinner with latency counter ("sec-edgar · 2.3s ...")
3. Brief text streams character-by-character (already wired via `useStreamingTurn`)
4. Citations pop in as each source is resolved (span_id matches)

### 5.3 Optimistic UI with four-tier error handling

Four error tiers (Linear/Kindatechnical HITL convention):
- **Transient** — silent retry (network blip)
- **Degraded** — inline marker: "limited data — sec-edgar timed out; brief generated from 4 of 5 sources"
- **Recoverable** — retry button inline: "Finnhub rate-limited — [retry in 30s]"
- **Fatal** — preserve user input, show escape hatch: "AgentCore unreachable. Copy query: ... Open Langfuse: ..."

Already partially wired via `ErrorBoundary.tsx`; v2 makes the 4 tiers explicit and consistently applied.

### 5.4 No modals. Sidesheets only.

Modals break live demos — they steal the viewport, block background updates, and hurt recovery. Every state change happens inline or in a sidesheet. Action plan = right sidesheet. Trace detail = right sidesheet. Queue item expand = inline.

### 5.5 Three visual treatments, one token system

Shared design tokens (CSS vars):
- Type scale, spacing grid (4px), color palette (SLDS base + accent by persona)
- Component primitives (Button, Chip, Skeleton, Card) used by all three personas with persona-level style overrides
- **Persona visual differentiators:**
  - Research: mono type for data, high-contrast greens on charcoal
  - Advisor: SLDS sans, Salesforce blue accents, queue-first
  - Client: Inter type, soft greys, chat-first, no dense chrome

---

## 6. Tech stack — keep mostly, swap two things

### Keep
- **Vite + React 18 + TypeScript strict** — nothing wrong with this.
- **SLDS design tokens** where Salesforce-native feel is wanted (advisor).
- **Zustand** — session, brief, queues, traversal stores.
- **TanStack Query** — for SOQL + REST fetches.
- **WebSocket transport** — AgentSocket.
- **Visx** — deterministic chart renderer.

### Swap
- **React Flow → still React Flow** for the Architecture Map (already planned). No change.
- **cmdk** — new addition. The `cmdk` library (used by Linear, Vercel, most modern command palettes). Pair with `shadcn/ui` for the palette UX. ([cmdk + shadcn pattern](https://playbooks.com/skills/gwenwindflower/.charmschool/web-ux-command-palette))

### New additions
- **Radix UI** primitives for sidesheets, tooltips, popovers (headless, accessible by default — WCAG AA).
- **framer-motion** for the gate-by-gate animation (lightweight, only used on map + skeleton states).
- **tailwindcss** — opt-in for v2 surfaces only, coexists with SLDS. Sparingly.

### Dependencies removed
- None immediately. Keep current deps; deprecate unused ones in a cleanup pass later.

---

## 7. Open questions (decisions needed before build)

1. **Persona switcher: URL-based or in-app?** v1 uses `?persona=`. v2 could let one logged-in user switch personas without reloading. Cleaner demo, but conflicts with per-user-per-persona AgentCore session semantics. Leaning URL-based for correctness.

2. **Real-time gate events: wire the backend, or replay from final payload?** Building real WebSocket gate emission (45 min backend work) is the right fix. Replaying from the final turn payload with 400ms delays is the workaround. For the panel demo the workaround is acceptable; for "controlled autonomy" credibility the real thing is better.

3. **Workflow 360 URL sharing: require auth or public?** If the link `/workflow360/a0G...` is shareable, we must guard against MNPI leakage (the brief itself is MNPI-filtered server-side, but audit rows might still leak metadata). Suggest: require auth via IdP; use principal-scoped redaction even on this view.

4. **Should we keep the existing `TraversalMap` component or replace with React Flow?** Current `TraversalMap` is 356 LOC of custom SVG. Replacing with React Flow is ~400 LOC diff but gives us auto-layout, minimap, zoom, panning for free. Lean toward replace.

5. **Mobile footprint?** v1 is desktop-only. v2 could make the Client channel responsive for mobile web (tablet in a branch, phone at home). The advisor and research personas stay desktop by design. Minimal effort, strong demo value (the client-liaison on a phone in the middle of a trade narrative).

6. **Dark mode?** Bloomberg-density suggests dark-themed terminal for research. SLDS advisor surface is light by default. Client channel light. One app, two themes? Or three persona-themed palettes? Tentatively: research dark, advisor light, client light. Research is the only one that benefits from dark.

---

## 8. Scope & effort estimate

Not a full rebuild. v1 → v2 is a **layered evolution** — keep 60% of components, reshape 30%, add 10% new.

| Work | Size | Risk |
|---|---|---|
| Persistent shell (header, ⌘K palette, audit console handle) | 1 day | Low |
| Architecture Map promoted to bottom strip + topology export | 1.5 days | Med (React Flow edge-routing) |
| Workflow 360 surface (new) | 1.5 days | Low (SOQL + timeline render) |
| Action Plan sidesheet (v2 HITL component) | 1 day | Med (tier logic) |
| Research terminal grid overhaul | 2 days | Med (Bloomberg-density tuning) |
| RM workbench layout + sticky 7-gate bar | 1.5 days | Low |
| Client channel polish + reference-ID surfacing | 0.5 day | Low |
| Keyboard shortcuts + ⌘K actions across personas | 1 day | Low |
| Optimistic UI + 4-tier error taxonomy | 1 day | Low |
| Audit Console (elevate from strip) | 1 day | Low |
| WebSocket gate event emission (backend — NOT frontend, but required) | 0.75 day | Low |
| Theme (research dark, advisor light, client light) | 0.5 day | Low |
| Accessibility pass (WCAG AA) | 0.5 day | Low |
| Tests (component + integration) | 1.5 days | Low |
| **Total** | **~15 days** | — |

For a single focused frontend engineer. Backend gate emission is the only non-frontend dependency.

---

## 9. What v2 explicitly does NOT do

- **No new agent types.** Topology is the topology. UI is about surfacing what's there.
- **No new backend APIs.** Every data source already exists (WebSocket events, SOQL, Langfuse API, KB retrieve).
- **No LLM UI-generation.** No "AI builds the dashboard for you." The architecture is deterministic by design; the UI reflects that.
- **No Agentforce UI integration.** Respect the scope boundary — AWS-hosted platform, Salesforce as data layer. The UI lives in its own CloudFront.
- **No real-mobile-native app.** Responsive web for client persona only. Native apps are V4.
- **No WebSocket rewrite.** Current `useAgentSocket` + event discriminated union is fine.

---

## 10. Why this v2 will land

Three reasons the panel will read this as a different category of product than the current v1:

1. **The Architecture Map becomes the hero.** Every other demo is a chat window. Ours shows the live execution graph. When a research turn fires five specialists in parallel, the panel sees five nodes pulse simultaneously — visual proof of `asyncio.gather`. When a trade fires the 7-gate spine, the gates light up one at a time — visual proof of `serial_by_design`. The architecture becomes self-demonstrating.

2. **Workflow 360 timeline makes the moat visible.** AWS, Anthropic, every competitor demo is single-persona. Ours shows the thread through all three personas in one timeline tied to one brief_id. Panel realizes: "this isn't three bots stapled together, this is one platform."

3. **The audit console is the compliance-officer handshake.** By making `IR_Audit_Log__c` queryable in-app with Langfuse deep-links, the demo answers "how would compliance review this?" without ever leaving the app. That's the question enterprise panels actually ask.

The other patterns — ⌘K, optimistic UI, 4-tier errors, sidesheets, keyboard-first — are hygiene. Not differentiators. Just raising the floor to what 2026 panels expect.

---

## 11. Open for input before we build

This is a design doc, not a build brief. Four things I want input on before touching code:

1. **Priority ordering.** If I can only build 3 of the v2 surfaces in a week, which ones? My vote: Architecture Map + Workflow 360 + Action Plan sidesheet.
2. **Command palette scope.** How deep does ⌘K go? Bare minimum ({switch persona, submit query, open trace}) or full-power Linear-style?
3. **Theme.** Research dark, everything else light. Or one unified theme?
4. **Mobile.** Client-only responsive, or skip entirely for v2?

Once those four decisions are nailed, I can write a build brief and commit to a 15-day sprint plan.

---

*Content was rephrased for licensing compliance with all cited sources.*

*Design doc v1 closed at 2026-04-30.*
