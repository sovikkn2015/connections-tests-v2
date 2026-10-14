# 006 V3 Research Analyst — What's There vs What's Not

> **Date:** 2026-05-01
> **Companion to:** `v3-research-analyst-feature-map.md`
> **Purpose:** the at-a-glance table a panel can read in 60 seconds. No prose, three tables, one priority ranking.
>
> Legend: ✅ live, 🟡 partial/broken, ❌ not built. P0 = ship for next demo, P1 = second wave, P2 = depth, P3 = nice-to-have.

---

## Table 1 — Analytical capabilities (what Sarah can do)

| # | Capability | There? | State | Priority |
|---|---|---|---|---|
| 1 | Single-turn research query → brief | ✅ | Live, 26s end-to-end, 5 specialists fan out | — |
| 2 | Market quote | ✅ | Live via Finnhub MCP | — |
| 3 | News sentiment (30d) | ✅ | Live via Tavily MCP | — |
| 4 | Compliance / restricted-list / MNPI screen | ✅ | Live, returns ALLOW/BLOCK | — |
| 5 | Citation-bound streaming brief | ✅ | Live, chips drill to source chunk | — |
| 6 | SEC filing RAG | 🟡 | Built, specialist sometimes times out | **P1** — raise worker timeout to 60s |
| 7 | Deterministic financial math (statements, DCF, peers) | 🟡 | Skill code exists; specialist returns prose + times out | **P0** — wire through `run_tool_loop` + render as grid |
| 8 | Brief publishing to CRM | 🟡 | Writes row but `Published_At__c=null` → Platform Event never fires → RM queue never notified | **P0** — fix in course of shipping Draft→Publish button |
| 9 | Coverage list / watchlist | ❌ | Not built | **P0** — biggest workstation-feel gap |
| 10 | Earnings calendar | ❌ | Not built | **P1** |
| 11 | Consensus estimates (EPS, rev, revisions) | ❌ | Not built; needs vendor tier | **P2** — may need stub |
| 12 | Catalyst map (guidance, launches, regulatory) | ❌ | Not built | **P2** |
| 13 | Peer comparison table | ❌ | Not built; `compare_peers` contract exists in arc doc only | **P2** |
| 14 | Valuation band (fwd P/E vs history) | ❌ | Not built | **P3** |
| 15 | DCF sensitivity heatmap | ❌ | Not built | **P2** |
| 16 | Prior briefs history / search | ❌ | Not built; data exists in `Research_Brief__c` | **P1** |
| 17 | Note versioning / diff | ❌ | Not built | **P3** |
| 18 | Pin-to-note (collect evidence → write) | ❌ | Not built | **P2** |
| 19 | Drag-drop PDF → citable source (multimodal) | ❌ | Designed in arc doc §1.2; zero code | **P1** — biggest "wow" in depth doc |
| 20 | Live news ticker on covered tickers | ❌ | Not built | **P3** |
| 21 | Filings feed / 8-K polling | ❌ | Not built | **P3** |
| 22 | Expert-call / channel-check notes | ❌ | Not built | **P3** |

---

## Table 2 — UI surfaces (what Sarah sees on screen)

| # | Surface | There? | State | Priority |
|---|---|---|---|---|
| 1 | PersonaHeaderV3 with forensic dark theme | ✅ | Rendered | — |
| 2 | Single query input, Cmd-Enter, `/` focus | ✅ | Works | — |
| 3 | Brief pane with streaming Markdown | ✅ | Works | — |
| 4 | Running tool-call chips ("sec-edgar · running") | ✅ | Works | — |
| 5 | Architecture map (TraversalMapV3) live | ✅ | Collapsible panel; nodes pulse | — |
| 6 | End-to-end trace collapsible | ✅ | Langfuse deep-link works | — |
| 7 | Audit strip bottom (correlation_id, latencies) | ✅ | Works | — |
| 8 | Citation drill-down right drawer | ✅ | Works | — |
| 9 | Demand signals right pane (pre-seeded) | 🟡 | UI renders; data is seeded, not real | **P3** — honest scoping |
| 10 | Market · live right pane | 🟡 | Placeholder text, renders nothing until first turn | **P1** — render price chart pre-turn |
| 11 | Coverage list rail (left sidebar) | ❌ | Not built | **P0** |
| 12 | Earnings calendar strip (top) | ❌ | Not built | **P1** |
| 13 | Specialist gantt / waterfall during turn | ❌ | Data on WebSocket, no renderer | **P0** — best multi-agent proof |
| 14 | Financial statement grid | ❌ | Not built; currently prose-only | **P0** |
| 15 | Draft → Publish button | ❌ | Briefs auto-publish to draft-only state | **P0** |
| 16 | Prior briefs drawer | ❌ | Not built | **P1** |
| 17 | MNPI / restricted banner (red) | ❌ | Not built; compliance result buried in brief text | **P1** |
| 18 | Cost meter (tokens, $/session) | ❌ | Langfuse has it; not surfaced | **P3** |
| 19 | Ticker-bound session state (`AAPL ·` prefix) | ❌ | Not built | **P1** |
| 20 | Drag-drop zone for PDFs | ❌ | Not built | **P1** |

---

## Table 3 — Consolidated priority map (ship in this order)

| Rank | Item | Refs | Build cost | Why it earns the slot |
|---|---|---|---|---|
| **P0-1** | Coverage list rail | T2 #11 | 2 days | Workstation vs. search-box. Panel sees persistence instantly. |
| **P0-2** | Draft → Publish button (fixes `Published_At__c` bug) | T1 #8, T2 #15 | 3 days | One fix, two wins: cleaner UX + RM queue actually lights up → Narrative 2 works |
| **P0-3** | Specialist gantt during turn | T2 #13 | 2.5 days | Single best visual proof of multi-agent. Data already flowing. |
| **P0-4** | Financial statement grid | T1 #7, T2 #14 | 3 days | Makes "deterministic math, LLM orchestration" claim observable |
| **P1-1** | Earnings calendar strip | T1 #10, T2 #12 | 1.5 days | Context at top of screen; makes terminal feel alive pre-turn |
| **P1-2** | Prior briefs drawer | T1 #16, T2 #16 | 2 days | Session persistence; table stakes of any analyst tool |
| **P1-3** | MNPI restricted banner | T2 #17 | 1.5 days | Trust-spine visibly catching a bad query |
| **P1-4** | Ticker-bound session scope | T2 #19 | 0.5 days | Cheap; proves session memory works |
| **P1-5** | Drag-drop PDF ingest | T1 #19, T2 #20 | 4 days | Multimodal depth commitment — slide → live |
| **P1-6** | Filings RAG timeout fix | T1 #6 | 0.5 days | Unblocks statement grid |
| **P2** | Catalyst map, peers table, DCF heatmap, pin-to-note, consensus | T1 #11–15, #18 | 8 days total | Deepen the story once Tier 1 lands |
| **P3** | Everything else (news ticker, filings feed, versioning, cost meter, channel-check notes, demand-signal real scoring) | T1 #17, #20–22, T2 #9, #18 | 6+ days | Nice-to-have, not panel-critical |

---

## The one-line read

**What's there:** plumbing, multi-agent fan-out, citation discipline, audit spine. Impressive under the hood.

**What's missing:** every visible thing a working analyst expects on screen — coverage list, calendar, gantt, statement grid, a Publish button. All UI on top of existing plumbing.

**Ship P0-1 through P0-4 (10.5 build-days).** That's the whole story. Everything else is bonus.

---

## Companion docs

- `v3-research-analyst-feature-map.md` — full stories, acceptance criteria, industry research, citations
- `v3-narrative-arc.md` — the V3 story
- `v3-design-vs-built-vs-deployed-v2.md` — current live stack reality
- `v3-live-traversal-ui-design.md` — specialist gantt / architecture map design thinking
