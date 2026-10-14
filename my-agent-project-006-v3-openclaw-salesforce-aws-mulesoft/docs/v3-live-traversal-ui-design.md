# 006 V3 — Live Traversal UI (Design Thinking, Not Build)

**Goal:** For any query, show which components lit up, in what order, with what latency, and ideally stream it live on screen as it happens. Make the architecture self-explanatory.

**Status:** design only. No code changes proposed here. The point is to pick the right shape before building.

---

## What we already have (the 80% you don't realize is there)

The plumbing for a live traversal UI is mostly already wired:

1. **Inbound WebSocket event stream** (`frontend/src/types/agent.ts`) emits a discriminated union that already carries the traversal signals:
   - `turn_started { turn_id, agent_id, plan_summary }` — who picked up the turn
   - `tool_call_start { tool: ToolCall }` — a skill / MCP call begins (has span_id, agent_id, tool_name)
   - `tool_call_end { span_id, status, latency_ms, error? }` — that same span closes
   - `gate_started | gate_passed | gate_failed { gate, status, detail? }` — seven-gate progress
   - `brief_delta` — text streams in
   - `citation { source_chunk_id, label }` — provenance chip
   - `turn_complete { cost_tokens, cost_usd, duration_ms }` — turn closes

2. **`SevenGateTracker`** (`frontend/src/components/SevenGateTracker.tsx`) — already renders the 7-gate horizontal bar, each cell lights up from gate events. This is the write-path live view.

3. **`AuditStrip`** (`frontend/src/components/AuditStrip.tsx`) — always-on bottom strip showing correlation_id, WS connection status, and active/completed tool-call spans with real latencies. This is the "what lit up" strip.

4. **Langfuse spans** are emitted on every converse call + every skill invocation + every MCP call (`openclaw/orchestration/coordinator.py::_ScrubbingLangfuseWrapper`). The post-hoc trace graph already works — Langfuse has a dedicated "graph view" for LangGraph-style agent execution (`langfuse.com/changelog/2025-02-14-trace-graph-view`). That gives you the rewind story for free.

5. **Gate trace recorded server-side** — `tool_dispatch.run_tool_loop` records an ordered `trace: List[ToolTraceEntry]` with `tool_name, status, elapsed_ms, error` per gate. Post-turn, that's stamped onto the audit row.

6. **Correlation id** (`useSessionStore`) ties the browser turn to the Langfuse trace, so there's a one-click deep link.

**Gap:** what's missing isn't plumbing, it's a unified **topology view** that renders the whole 17-agent graph and highlights traversed nodes/edges as the events arrive.

---

## What industry does (and what fits this architecture)

Real options, in rough order of increasing effort vs. payoff:

### Option 1 — Langfuse trace graph view (FREE, post-hoc)
What it is: Langfuse already renders a hierarchical graph for multi-agent traces. Click a span, see inputs/outputs/latency/cost. ([langfuse.com/changelog/2025-02-14-trace-graph-view](https://langfuse.com/changelog/2025-02-14-trace-graph-view))

Pros: Zero build. Already emitted. Shows the architecture in its natural shape.

Cons: Lives outside the demo UI. Post-hoc, not real-time during the turn. Every panel transition asks the viewer to switch tabs.

Good for: debugging + audit review. Not the demo hero.

### Option 2 — In-app "Architecture Map" panel with React Flow overlay
What it is: a right-side panel that renders the 17-agent topology as a fixed graph (React Flow or Reaflow). As `tool_call_start / tool_call_end / gate_*` events arrive, nodes light up (pulse → green when complete → red on error), edges animate the hop. Persona orchestrator → specialist → skill → MCP → back.

Pros: Direct, explainable, hero-worthy. Matches the mental model. "The query you typed just made these five boxes light up." Works for reads AND writes (7-gate is one slice of this same graph).

Cons: ~2 days of frontend work. Needs a static topology graph (already derivable from `openclaw/orchestration/topology.py`).

Good for: the demo. This is the "wow" view.

References for the pattern:
- LangGraph Studio / LangSmith Studio — live step-through of agent graphs with state inspection. Same idea, different target. ([docs.langchain.com/oss/javascript/langgraph/studio](https://docs.langchain.com/oss/javascript/langgraph/studio))
- Reaflow / React Flow are the standard React canvases for this. React Flow is the de-facto choice for Langflow, n8n UI, and most agent-canvas products today.

### Option 3 — Timeline waterfall (Chrome DevTools-style)
What it is: a timeline view under the chat where each span is a horizontal bar, stacked by layer (orchestrator → specialist → skill → MCP). Each bar has a latency label. Shows parallelism visually: 5 research specialists are 5 side-by-side bars on the same time axis; the 7-gate write path is 7 bars end-to-end.

Pros: Shows parallel vs. serial at a glance. Proves asyncio.gather visually. Very developer-friendly. Easy to implement: the span data is already in AuditStrip's feed.

Cons: Less "architecture as a diagram" and more "execution as a gantt chart." Good second hit, not primary.

### Option 4 — Sankey / flow diagram
What it is: width of ribbons = token count or latency across agent → skill → MCP.

Pros: Shows relative cost and hot paths.

Cons: Only makes sense AFTER a turn (cumulative). Not live. Better as a post-turn summary card than a live view.

---

## Reconciling with what 006 v1 already has

006 v1 ships a "End-to-End Trace" collapsible strip at the bottom of the UI. Each row is one query; expanded it shows a linear pill chain (`Query → Agent → Sonnet → MCP → Response`), a per-tool table (Tool · MCP · Data Source · Status · Duration), and a Langfuse deep-link.

That pattern is the right shape for **post-hoc audit**. Keep it. The two things v1 can't do:

1. It's linear. A pill-chain row of 5 MCP pills looks identical whether those 5 calls ran in parallel (`asyncio.gather`) or sequentially. You can't tell the 7-gate serial spine from a parallel research fan-out.
2. It appears after the turn. For short turns that's fine; for the 7-gate HITL path where a human holds a gate for seconds, the audience can't see what's happening live.

So the v3 UI is **not** "two new panels stacked on top of v1's trace" — that would be three competing trace-ish views. It's:

- **Keep v1's collapsible end-to-end trace** as the post-hoc audit log at the bottom.
- **Replace the linear pill chain inside each expanded row** with a compact mini-timeline waterfall. Proves parallel vs. serial in the same vertical space.
- **Add one NEW panel above it: the live Architecture Map.** That's the only net-new visual. It's the thing v1 genuinely doesn't have.

## Recommendation

Two views total, both earn their space, zero redundancy with v1.

### The resulting layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│  chat + brief (existing personas)                                        │
│                                                                          │
│   User: "Deep dive on NVIDIA pre-earnings"                               │
│                                                                          │
│   Sarah's brief streaming in here ...                                    │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ARCHITECTURE MAP  — live during turn (NEW)                              │
│                                                                          │
│      ┌─────────────┐                                                     │
│      │ COORDINATOR │  ← lit                                              │
│      └──────┬──────┘                                                     │
│             │                                                            │
│      ┌──────▼───────────┐                                                │
│      │ research_orch.   │  ← lit, currently streaming                    │
│      └──────┬───────────┘                                                │
│             │                                                            │
│      ┌──────┼─────┬─────┬─────┬─────┐                                    │
│      ▼      ▼     ▼     ▼     ▼                                          │
│    market filings sent compl stmt  ← all five pulsing (parallel)         │
│      │     │     │     │     │                                           │
│      ▼     ▼     ▼     ▼     ▼                                           │
│   finnhub edgar tavily compl-  edgar                                     │
│    MCP    MCP   MCP   screen  MCP                                        │
│                                                                          │
│    dim  = not touched this turn                                          │
│    solid= completed                                                      │
│    pulse= in-flight                                                      │
│    red  = error                                                          │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  END-TO-END TRACE  (v1 pattern, kept + enhanced) — post-hoc audit        │
│                                                                          │
│   ▸ 06:14:25  Who covers NVDA?           1 tool, 340ms  ...              │
│   ▾ 06:14:30  What's happening with NVDA? 5 tools, 7.9s                  │
│      ┌─ mini-timeline (REPLACES v1 pill chain) ─────────────────┐        │
│      │  orch         ████████████████████████████████▌  7.9s    │        │
│      │  crm_mcp       ██▌                              320ms    │        │
│      │  mkt_mcp       ██▌   █▌                          680ms   │        │
│      │  sec_mcp              ████████▌                  3.2s    │        │
│      │  news_mcp       █████▌                           2.8s    │        │
│      └─────────────────────────────────────────────────────────┘        │
│      Tool · MCP Server · Data Source · Status · Duration   (kept)        │
│      Langfuse deep-link (kept)                                           │
│                                                                          │
│   ▸ 06:14:45  Deep dive on NVIDIA       7 tools, 12s  ...               │
├──────────────────────────────────────────────────────────────────────────┤
│  AUDIT STRIP  (existing — keep)    trace: 4f8c · ws: open · 5 spans ...  │
└──────────────────────────────────────────────────────────────────────────┘
```

### Why not three trace-ish panels

A separate standalone timeline panel would duplicate what's now nested inside each expanded trace row. Three trace views compete for the viewer's eyes. Two is the right number: **Map = shape, live.  Trace = log, post-hoc.**

Why both: the map answers "which pieces of my architecture does this query touch" (the explainability story). The timeline answers "what ran in parallel vs. serial and how long" (the narrative for asyncio.gather + seven-gate serial). The audit strip stays as the always-on trace handle.

### Behavior per event

| Event | Architecture Map effect | Timeline effect |
|---|---|---|
| `turn_started` | coordinator + persona orchestrator glow | new row per agent appears |
| `tool_call_start` | skill/MCP node starts pulsing; edge orchestrator→skill animates | bar starts extending |
| `tool_call_end ok` | node goes solid green, edge settles | bar freezes with latency label |
| `tool_call_end error` | node red, tooltip shows error_type | bar turns red |
| `gate_started/passed/failed` | 7-gate track (already existing `SevenGateTracker`) updates; map also lights the corresponding trust-layer node | 7 gates appear as sequential bars |
| `brief_delta` | no-op on map | no-op |
| `citation` | source node on map pulses briefly (proves citation -> source) | no-op |
| `turn_complete` | everything settles; cost + duration badge appears | summary row with totals |

### Key design decisions

1. **Render the topology statically from code, not from runtime.** Export the topology from `openclaw/orchestration/topology.py` (already Pydantic) at build time into a JSON the frontend imports. One source of truth. When someone adds a specialist, the map updates automatically. This is the explainability lock.

2. **Dim-by-default.** Every node starts dim. A node only lights up if it's actually visited this turn. This matters: for a simple L1 query ("quote for NVDA") the map should show *one* node pulsing, proving the agent didn't grind through the whole pipeline for a cheap question. That's a huge architecture-explainability win.

3. **Three-persona filter.** The map has three overlays (research / advisor / liaison). The default view is "auto — highlight the persona currently active." The advisor view specifically expands the 7-gate inline inside the `action_specialist` box when an action plan is live, so you get "here's the write path, and these seven gates are real code, not prose." This is the critical narrative.

4. **Use React Flow.** Standard choice for agent canvases (Langflow, n8n, most modern agent-graph UIs). Already ~50KB gzipped. ELK layout for automatic edge routing so we don't hand-place 17 nodes + 30+ edges. ([reaviz/reaflow](https://github.com/reaviz/reaflow) is the alternative; React Flow has better community and perf.)

5. **Event bus, not more WS plumbing.** The frontend already has `useAgentSocket` dispatching discriminated events into Zustand stores. Add one more store `useTraversalStore` that consumes `tool_call_*`, `gate_*`, `turn_started`, `turn_complete` and maintains a lit-up-nodes set + in-flight set + edge-animation queue. Both panels subscribe. No new backend wire protocol needed.

6. **Langfuse deep-link.** Every node click opens the Langfuse span in a new tab (the span_id is already in the event). You don't need to rebuild what Langfuse already does well (inputs/outputs/full payload inspection). Best of both.

7. **Skills vs MCPs as layered nodes.** Two-layer rendering: orchestrator row → specialist row → skill row → MCP row. Clean left-to-right flow. Write path inverts: orchestrator → action_specialist → [7-gate column].

8. **Time-travel slider (P2).** Langfuse can drive a scrubber: "rewind to 00:02.1, replay the turn." Real-time on first pass, replay in v2.

---

## What this answers for the demo narrative

| Narrative moment | What the map shows |
|---|---|
| "Sarah types a research query" | coordinator lights up, research_orchestrator lights up, **five specialist nodes pulse simultaneously** — visual proof of `asyncio.gather` parallelism |
| "Each specialist calls its own MCP" | five parallel edges animating downward to distinct MCP nodes (Finnhub, EDGAR, Tavily, EDGAR, compliance-screen skill) |
| "The brief streams back" | the five specialists go solid, the orchestrator pulses as it synthesizes, brief_delta events paint the text panel |
| "RM asks to submit an order" | advisor_orchestrator lights up, single edge to `action_specialist`, the 7-gate strip inside action_specialist lights up ONE AT A TIME — visual proof of `serial_by_design` |
| "Compliance DENY" | gate 3 turns red, gates 4-7 stay dim, audit gate (7) still turns green (audit always fires, even on block) — visual proof of "audit on every outcome" |
| "Liaison handles an FAQ" | liaison_orchestrator + faq_specialist light up, zero MCP hops — visual proof of "Haiku FAQ path is cheap, read-only, no vendor calls" |
| "MNPI in the research path" | CRM MCP node shows a small shield icon when redaction fires (new `mnpi_redactions_applied` field in `tool_call_end.detail`) — visual proof of server-side MNPI defense |

Every one of those is a one-sentence explanation + the diagram proving it.

---

## Scope / effort estimate (for later, when we build)

| Work | Size |
|---|---|
| Export topology JSON at build time (Python -> JSON) | 0.25 day |
| `TraversalMap.tsx` React Flow panel + ELK layout | 1 day |
| `Timeline.tsx` waterfall | 0.5 day |
| `useTraversalStore.ts` + event-to-state reducers | 0.5 day |
| Visual polish (node icons, pulse animation, legend) | 0.5 day |
| Deep-link to Langfuse span on node click | 0.25 day |
| Tests (store reducer, state transitions, render) | 0.5 day |
| **Total** | ~3.5 days |

No backend changes needed. All signals already emitted.

---

## What this is NOT

- Not a rebuild of Langfuse. Langfuse stays the source of truth for the full trace tree, replayability, cost aggregation, and eval. The in-app map is a **visual summary** tied to the live turn, with a one-click handoff to Langfuse for depth.
- Not a general-purpose node editor (no drag-and-drop, no edit). This is a **read-only live execution view**. Langflow and n8n solve a different problem (authoring). We're solving explaining.
- Not an alternative to the existing `SevenGateTracker`. That component stays; the map embeds a synchronized view of it inside the action_specialist node when a write plan is live.

---

## Bottom line

- You already have the events, the correlation id, the Langfuse scrubber, the gate tracker, and the audit strip.
- The honest gap is a topology map that renders the 17-agent graph and lights up what this turn touched.
- Three extra days of frontend, zero backend changes, and the architecture becomes self-demonstrating.
- On stage: type a query, watch the graph traverse in front of the audience. That's the narrative. No mockery drama — the map visualizes real spans from real code.


---

## ASCII gallery — what each view looks like at a glance

### Architecture Map — three query examples on the same graph

Full-fanout research turn (`asyncio.gather` proves itself visually):

```
╔════════════════════════════════════════════════════════════════════════════╗
║  ARCHITECTURE MAP — live                                                   ║
║  persona: research   turn: 4f8c-2a11   ⬤ dim  ◐ pulse  ● solid  ⨯ error    ║
╠════════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║                          ●  COORDINATOR                                    ║
║                               │                                            ║
║                               ▼                                            ║
║                ●  research_orchestrator (Sonnet · parallel)                ║
║                ╱  ╱  │  ╲  ╲                                               ║
║               ╱  ╱   │   ╲  ╲                                              ║
║              ◐  ◐   ◐   ◐   ◐    ← 5 specialists pulsing in parallel       ║
║            mkt  fil  sen  cmp  stmt                                        ║
║              │   │   │    │    │                                           ║
║              ▼   ▼   ▼    ▼    ▼                                           ║
║             ◐   ◐   ◐    ◐    ◐     (skills: rag_retrieve, fsa, etc.)      ║
║              │   │   │    │    │                                           ║
║              ▼   ▼   ▼    ▼    ▼                                           ║
║             ◐   ◐   ◐    ●    ◐     (MCPs: Finnhub EDGAR Tavily ...)       ║
║                                                                            ║
║   ─────  advisor_orchestrator  ⬤ (dim, not touched this turn)              ║
║   ─────  liaison_orchestrator  ⬤ (dim, not touched this turn)              ║
║                                                                            ║
║   TRUST LAYER: mnpi_filter ●   gate_enforcer ●   idp_session ●             ║
║                                                                            ║
║   click any node  →  Langfuse span opens in new tab                        ║
╚════════════════════════════════════════════════════════════════════════════╝
```

Simple L1 quote query ("quote NVDA") — proves the agent isn't over-engineered:

```
                          ●  COORDINATOR
                               │
                               ▼
                ●  research_orchestrator
                               │
                               ▼
                          ●  market_specialist
                               │
                               ▼
                          ●  market-data MCP (Finnhub)

                (everything else dim — one query, one path)
```

RM action with a compliance DENY — the serial 7-gate spine lights up one at a time inside `action_specialist`:

```
                ●  advisor_orchestrator
                               │
                               ▼
   ┌───────────────────────────────────────────────────────────────┐
   │                 ●  action_specialist                          │
   │                                                               │
   │   ①Guardrails ②MNPI ③Compl ④HITL ⑤DualAuth ⑥MuleSoft ⑦Audit   │
   │      ●        ●      ⨯    ⬤      ⬤         ⬤        ●         │
   │                    DENY                                       │
   │                                                               │
   │   Compliance blocked at gate 3.                               │
   │   Gate 7 (audit) still fired — every outcome is logged.       │
   └───────────────────────────────────────────────────────────────┘
```

### Mini-timeline (inside each expanded trace row, replaces v1's pill chain)

Research turn — the five bars START AT THE SAME TIME = `asyncio.gather`:

```
time ▶   0ms       500ms      1000ms     1500ms     2000ms     2500ms
         │          │           │          │          │          │
research_orchestrator ████████████████████████████████████████████▌ 2310ms
  ├ market_specialist     ██████████▌                                 920ms
  │   └ finnhub MCP        ████▌                                      280ms
  ├ filings_specialist    ████████████▌                              1180ms
  │   └ sec-edgar MCP      ██████▌                                    410ms
  ├ sentiment_specialist  █████████▌                                  840ms
  │   └ tavily MCP         █████▌                                     340ms
  ├ compliance_specialist ███████▌                                    620ms
  │   └ compliance_screen   ██▌                                       110ms
  └ statement_specialist  ██████████████▌                            1320ms
      └ sec-edgar MCP      ███████▌                                   490ms

  All five started at t≈80ms — proves asyncio.gather.
  Orchestrator total ≠ sum of children — proves parallelism.
```

RM action — 7 bars IN SEQUENCE (no overlap) = `serial_by_design`:

```
time ▶   0ms    500ms   1000ms  1500ms  2000ms  2500ms  3000ms
         │       │        │       │       │       │       │
action_specialist ████████████████████████████████████████▌ 2950ms
 ①Guardrails  █▌                                              80ms
 ②MNPI filter   █▌                                            60ms
 ③Compliance      ███▌                                       220ms
 ④HITL (wait)        ████████████████████▌                  1620ms ← human
 ⑤Dual-Auth                               ███▌               240ms
 ⑥MuleSoft                                   ████▌           310ms
 ⑦Audit                                          ██▌         140ms

  Each bar starts AFTER the previous ends — proves serial.
  HITL is the longest bar because a human approved it.
```

---

## Latency — honest answer

**No meaningful latency added to the agent turn. No new backend load.**

1. **The events already exist.** `tool_call_start`, `tool_call_end`, `gate_*`, `turn_started`, `turn_complete` are in the WebSocket protocol today (`frontend/src/types/agent.ts`). `AuditStrip` + `SevenGateTracker` already consume them. The server doesn't do more work — it broadcasts what's already being traced for Langfuse.

2. **Langfuse spans are already the hot path.** The `_ScrubbingLangfuseWrapper` in `coordinator.py` already runs on every converse + every skill call + every MCP call. That scrubber is the cost you've already paid. Showing those same spans in a UI panel doesn't add server cost.

3. **Client-side render cost is tiny.** A React Flow canvas with ~17 nodes + ~30 edges at 60fps is nothing on a laptop. For reference, Langflow renders hundreds of nodes live.

4. **Concrete numbers:**
   - Per-event render cost: <1ms on main thread (state update + 1–2 node re-renders)
   - Per-turn added cost on the server: **0ms** (no new emissions, no new trace writes)
   - Per-turn added cost on the wire: **0 bytes** (events already flowing)
   - Bundle size addition: ~50KB gzipped for React Flow + ~10KB for ELK layout
   - First paint of the map: ~100–150ms one-time when the map mounts (ELK layout pass)

5. **The one thing that could add latency if done wrong:** running a full layout pass on every event. Don't — lay out once on mount, then only animate fills/colors. React Flow does this correctly by default.

6. **Offload to a Web Worker if paranoid.** For a worst-case graph (say 100+ nodes), push ELK layout into a worker. With 17 nodes this is unnecessary.

**Net:** the live map is observability, not instrumentation. It shows what Langfuse already sees, just on the same screen as the demo instead of in another tab. Zero impact on the agent, real impact on the story.

---

## One-line comparison to 006 v1

| Concern | 006 v1 (today) | 006 v3 (proposed) |
|---|---|---|
| Post-hoc audit log with Langfuse link | ✅ Collapsible trace rows | ✅ **Kept, unchanged pattern** |
| Shows which tools ran per query | ✅ Pill chain + tool table | ✅ Tool table kept; pill chain → mini-timeline |
| Shows parallel vs serial | ❌ Pill chain can't | ✅ Mini-timeline shows overlap |
| Shows the architecture shape | ❌ | ✅ Architecture Map (new) |
| Live during the turn | ❌ Appears when turn ends | ✅ Map updates as events arrive |
| Works for the 7-gate write path | Partial (shows tools called) | ✅ Map + timeline both show the spine |
| Net new panels vs v1 | — | **+1: Architecture Map**  (trace row internals swap pill→timeline) |
