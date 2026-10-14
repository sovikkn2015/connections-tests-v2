# V4 Frontend — Build + Deploy Status

**Branch:** `feat/006-v3-live-demo`
**Live:** 2026-05-01
**Bundle:** `index-BCeDx6us.js` (454 KB · 139 KB gzip)
**Commit chain:**
  - Merge commit `fea4e7d0` — brings V4 together with builder's Mule deploy work
  - V4 source landed inside the merge (files tracked via merge parents)

---

## What V4 is

A disciplined rebuild of the UI that ports the uploaded designer's system
(`docs/UIUX Design.zip`) **verbatim**, scoped to an independent `v4/`
subtree. Activated via `?v4=1` on the URL. Preserves v1 / v2 / v3
completely.

### The discipline gap V4 closes

V3 was hand-tuned — ad-hoc blues, 24px padding, 13px body, inline styles
leaking through. Looked amateurish next to SLDS, FactSet, Bloomberg.
V3 effectively ignored the CSS tokens in the uploaded zip.

V4 treats the designer's CSS as the single source of truth. Specifically:

| Dimension | V4 rule (from designer) | V3 (what we had) |
|---|---|---|
| Header height | 44px exact | 48px |
| Audit strip | 28px exact | variable |
| Toolbar | 44px exact | variable |
| Grid gap | 8px | 24px |
| Base font | 13px (body), 11px (labels), 10-11px (meta) | mostly 13-14px |
| Labels | UPPERCASE + 0.06em letter-spacing | sentence case |
| Numbers | JetBrains Mono + tabular-nums everywhere | mixed |
| Borders | 1px, flat | sometimes shadows |
| Radius | 2-4px | up to 6px |
| Theme toggle | Removed (Bloomberg / FactSet don't ship one on analyst surfaces) | Light + dark |

### What's live per persona

**Research (`?persona=research&v4=1`)** — Sarah Chen, forensic dark canvas
  - 44px header with Workflow 360 brand, connection live-dot, avatar
  - 44px toolbar with query input + Run ⌘↵ button + JSON toggle
  - 3-column body at `minmax(560px,1fr) 380px 320px`:
    - Brief pane (citation-enforced, specialist chips, streaming markdown)
    - Market pane + Specialists summary pane (live tool-call summary)
    - Demand Signals pane (from queues store)
  - Trust-spine strip: Architecture Map + End-to-End Timeline side-by-side
  - 28px audit strip at bottom — live trace id, WS status, span pills, cost

**Advisor (`?persona=advisor&v4=1`)** — Marcus Kerrigan, SLDS-like light neutral
  - 44px header with advisor-tone blue
  - Seven-gate tracker (renders only when pendingPlan in flight — progressive disclosure)
  - 3-column body at `280px 1fr 380px`:
    - Queue tabs (Actions / Insights / Tasks) with live count badges, priority chips (high/med/low)
    - Conversation column with AI/Client/RM avatars, inline action card on hitl_prompt
    - Client 360 column with IPS allocation bar + concentration warnings
  - Composer at bottom of conversation with ⌘↵ send
  - Trust-spine + audit strip below

**Client (`?persona=client&v4=1`)** — Eleanor Vance, WhatsApp-native
  - Full-bleed navy gradient stage with radial brand glow
  - 3-column grid: Client-surface caption · Phone bezel (380×800) · Behind-the-scenes caption
  - Phone = notch + status bar + channel header + thread + disclaimer + CTAs + composer
  - Behind-the-scenes trace-stack (compact TraversalMap + Timeline)

---

## Live wiring — same contracts as V3

V4 changes the visual skin only. Backend contracts are unchanged:
  - `useAgentSocket` for WebSocket turn lifecycle
  - `useStreamingTurn` for span dispatching
  - `useBriefStore` for streaming markdown + tool spans + citations
  - `useTraversalStore` for map state
  - `useQueuesStore` for advisor queue tabs
  - `useGateTracker` for HITL gate chain
  - `useOptimisticApproval` for approve/deny round-trip
  - `useSessionStore` for auth + connection status

No new envelope fields. No new MCP calls. No coordinator changes.

---

## URLs (live now)

```
v1 research:  https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research
v2 research:  https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v2=1
v3 research:  https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v3=1
v4 research:  https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v4=1

v1 advisor:   https://d2zs9nk4uc2dbx.cloudfront.net/?persona=advisor
v2 advisor:   https://d2zs9nk4uc2dbx.cloudfront.net/?persona=advisor&v2=1
v3 advisor:   https://d2zs9nk4uc2dbx.cloudfront.net/?persona=advisor&v3=1
v4 advisor:   https://d2zs9nk4uc2dbx.cloudfront.net/?persona=advisor&v4=1

v1 client:    https://d2zs9nk4uc2dbx.cloudfront.net/?persona=client
v2 client:    https://d2zs9nk4uc2dbx.cloudfront.net/?persona=client&v2=1
v3 client:    https://d2zs9nk4uc2dbx.cloudfront.net/?persona=client&v3=1
v4 client:    https://d2zs9nk4uc2dbx.cloudfront.net/?persona=client&v4=1
```

All four variants coexist on the same bundle. Selection is query-string
only; no build flag needed.

---

## Files added

```
frontend/src/v4/
├── V4App.tsx                          41 LOC — router
├── styles/
│   ├── fonts.css                        6 LOC — Google Fonts import
│   └── fsi-design-system.css          871 LOC — ported designer CSS
├── atoms/
│   ├── W360Logo.tsx                    19 LOC
│   ├── PersonaHeaderV4.tsx             89 LOC
│   ├── TraversalMapV4.tsx             378 LOC
│   ├── TimelineV4.tsx                 275 LOC
│   ├── TrustSpineV4.tsx                47 LOC
│   ├── AuditStripV4.tsx                87 LOC
│   ├── GatesTrackerV4.tsx              73 LOC
│   └── InlineActionCardV4.tsx         175 LOC
└── personas/
    ├── ResearchTerminalV4.tsx         394 LOC
    ├── AdvisorWorkbenchV4.tsx         432 LOC
    └── ClientChannelV4.tsx            264 LOC

frontend/tests/unit/v4/
└── V4App.smoke.test.tsx               108 LOC — 5 tests
```

App.tsx gains a `useV4` branch (25 LOC diff). No other files touched.

---

## Verification checklist

- [x] `npm run build` → `index-BCeDx6us.js` (454 KB / 139 KB gzip), clean
- [x] `npm run test --run` → 133/133 tests pass (128 existing + 5 V4)
- [x] `deploy-frontend-cloudfront.sh` → S3 sync + OAC + CloudFront invalidation
- [x] Invalidation `IT9HD5GQYH016FJX5G4CK9YRU` Completed
- [x] `curl` returns 200 on all three V4 persona URLs
- [x] Served bundle matches built bundle (`index-BCeDx6us.js`)
- [x] `git push` merged into `origin/feat/006-v3-live-demo` (merge commit `fea4e7d0`)

---

## What's NOT in V4 yet — deferred

These didn't make the pass. Each is tagged for a later iteration, not
a regression.

1. **Brief markdown → rich sections.** The designer's BriefContent
   had bold inline stats, MNPI callout box, embedded SVG quarterly
   bar chart. V4 pours the agent's streaming markdown as-is. A v4.1
   would parse specific section markers (`## RISK`, `$(chart:…)`)
   to render the designed chart and callout blocks.
2. **Filings pane.** The designer drew a filings table with type /
   date / section / page columns. V4 shows a Specialists summary
   instead (same column slot) because the backend doesn't emit a
   filings-index payload yet — would need a new `filings_index`
   channel from the research specialist.
3. **Sentiment sparkbar.** Replaced by the Specialists summary in
   the same slot. Same reason — backend emits sentiment score as a
   number in the markdown, not a per-hour histogram.
4. **Client 360 holdings payload.** Rendered as placeholders — the
   CRM MCP call chain to pull household holdings isn't wired to
   queue-item selection. Works the moment the backend writes that.
5. **Citation drill-down drawer.** V3 had a side-panel drawer on
   chip-click. V4 renders chips but the drawer is deferred to V4.1
   pending the sec-edgar `get_source_chunk` backend fix documented
   in `docs/v3-p0-source-chunk-citation-drift.md`.

---

## Honest note on the commit

My V4 commit got rolled into builder's `fea4e7d0` merge commit
(commit message reads "Mule deploy..." because the parent was
builder's Mule work). The V4 code IS on the branch — you can see
every V4 file via `git ls-files frontend/src/v4/`. Just the commit
message isn't "v4:".

If a clean V4 commit message is wanted for record-keeping,
`git log -p fea4e7d0 -- frontend/src/v4/` shows the full V4 delta.

---

*Written 2026-05-01 during the autonomous V4 build session.*
