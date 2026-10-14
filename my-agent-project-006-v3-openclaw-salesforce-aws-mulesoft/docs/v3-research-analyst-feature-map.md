# 006 V3 — Research Analyst Persona Feature Map

> **Date:** 2026-05-01
> **Author:** research study, not a build plan
> **Audience:** exec panel, product, engineering steering
> **Scope:** `fsi-research` persona only (Sarah Chen). What a real equity research analyst does, what V3 already ships, what V3 is missing, what is demo-worthy, and an executable feature backlog ranked by demo value × build cost.
>
> **Status:** research → prioritized backlog. No code changed.

---

## 1. What a financial research analyst actually does

Based on [CFI's equity research analyst career guide](https://corporatefinanceinstitute.com/resources/career/equity-research-overview/), the [BLS occupational outlook](https://www.bls.gov/ooh/business-and-financial/financial-analysts.htm), the [Series 86 reference](https://securitiesexamsmastery.com/finra/series86/cheat-sheet/), and sell-side workflow descriptions from [Mergers & Inquisitions](https://mergersandinquisitions.com/equity-research-careers/) and [InterviewPrep](https://interviewprep.org/equity-research-analyst-job-description/). Content paraphrased to comply with licensing restrictions.

### 1.1 The job, in one paragraph

A financial research analyst (sell-side or buy-side) covers a defined universe of companies in a sector. They build and maintain detailed financial models, publish recommendations (buy / hold / sell) with price targets, issue notes around catalysts (earnings, guidance, M&A, regulatory events), take client calls, and maintain relationships with company IR teams and industry experts. The output is a mix of deep-dive initiation reports (30–80 pages), quarterly earnings notes (2–8 pages), flash notes on breaking news (half a page), and internal morning notes.

### 1.2 The daily rhythm

Typical day for a sell-side analyst covering ~10–25 tickers:

| Time block | Activity | What's produced |
|---|---|---|
| 05:30–07:00 | Pre-market scan: overnight news, Asia/Europe moves, after-hours prints, futures | Morning note, updated model cells |
| 07:00–08:00 | Morning meeting with sales & trading — walk through overnight calls | Verbal brief, trade ideas |
| 08:00–12:00 | Deep work: earnings models, industry analysis, channel checks, filing review | Model updates, draft notes |
| 12:00–14:00 | Client calls — walk investors through thesis, answer questions | Call notes |
| 14:00–17:00 | Second deep-work block. Company meetings, expert network calls, write-ups | Expert-call notes, draft notes |
| 17:00–19:00 | Review markets, respond to emails, prep next day's morning note | Morning-note draft |
| Earnings weeks | 12–16 hour days: preview → listen to call → rapid note within 2h of print | Preview + recap notes |

### 1.3 The analytical primitives — what the work actually consists of

Six repeating work units:

1. **Model maintenance.** Three-statement model (IS / BS / CF) per covered ticker, rolled forward every quarter. Assumption layer (revenue growth, gross margin, opex, capex, working capital). Sensitivity tables. DCF valuation output. Consensus-vs-mine delta.
2. **Fundamental analysis.** Margin trends, returns on capital (ROE/ROIC/ROA), working-capital discipline, cash conversion, leverage, liquidity, share count drift. Peer comparison on the same metrics.
3. **Valuation.** Multiples (P/E, EV/EBITDA, EV/Sales, P/B) vs. history, peers, sector. DCF with scenarios. Sum-of-the-parts for conglomerates. Dividend discount for financials/utilities. Price target triangulation.
4. **Catalyst mapping.** Earnings dates, guidance checkpoints, product launches, analyst days, regulatory deadlines, M&A rumors. "What moves the stock in the next 0–90 days."
5. **Qualitative research.** Read the 10-K/10-Q (Item 1A Risk Factors, MD&A, footnotes), read competitor filings, read earnings call transcripts, read sell-side competitor notes, talk to IR, talk to channel experts, read industry press.
6. **Writing and communication.** The note. The morning meeting. The client call. Distillation is the job — not data collection. The senior skill is knowing what to cut.

### 1.4 Who they talk to

- Portfolio managers (buy-side) or institutional clients (sell-side) — primary audience
- Company management and IR — the data source and reality check
- Industry experts via expert networks (GLG, Third Bridge, AlphaSights)
- Internal sales/trading desk — distribution channel
- Compliance (restricted list, MNPI, Reg FD, Reg BI) — the guardrails
- Other sector analysts — cross-reads (semis analyst talks to hyperscaler analyst about capex)

### 1.5 The reality of AI in their workflow, 2026

Current state based on [AlphaSense's 2025 platform evolution](https://www.alpha-sense.com/solutions/generative-ai-investment-research/), [Bloomberg's agentic terminal rollout](https://www.tradersmagazine.com/xtra/bloomberg-introduces-agentic-ai-to-the-terminal/), and the [AWS Bedrock multi-agent investment research blog](https://aws.amazon.com/blogs/machine-learning/part-3-building-an-ai-powered-assistant-for-investment-research-with-multi-agent-collaboration-in-amazon-bedrock-and-amazon-bedrock-data-automation/):

- Filing search, earnings transcript Q&A, and cross-document synthesis are the top three AI use cases at firms deploying LLM tools in research.
- Analysts still build the model themselves. AI suggests revisions, flags inconsistencies with the filing, and drafts the note — the model is the analyst's IP.
- Trust model: every AI-generated sentence must cite the source sentence or cell. Uncited output is discarded.
- Speed claim: firms report 30–50% reduction in time-to-first-draft for earnings notes (AlphaSense case studies). The absolute human hours saved is measured in tens per analyst per month, not hundreds.

---

## 2. What 006 V3 already has for Sarah

Cross-checked against `docs/v3-narrative-arc.md`, `docs/v3-design-vs-built-vs-deployed-v2.md`, `frontend/src/v3/personas/ResearchTerminalV3.tsx`, and `openclaw/skills/`.

### 2.1 Analytical primitives currently covered

| Primitive | V3 status | Evidence |
|---|---|---|
| Single-turn research query → brief | 🟢 **LIVE** (Narrative 1, 26s end-to-end turn proven) | `research_orchestrator` + 5 specialists; Research_Brief__c writes |
| Market quote | 🟢 built + deployed | `market_specialist` → Finnhub MCP |
| SEC filing retrieval + section-aware RAG | 🟡 built, one specialist sometimes times out | `filings_specialist` + Bedrock KB (784 chunks) |
| News sentiment (30-day) | 🟢 built + deployed | `sentiment_specialist` → Tavily MCP |
| Compliance / restricted list / MNPI screen | 🟢 built + deployed | `compliance_specialist` → `compliance-screening` skill |
| Deterministic financial statement math | 🟡 built but the specialist times out in live turns | `statement_specialist` + `financial_statement_analysis` skill |
| Publishing a brief to the CRM | 🟡 writes exist but `Published_At__c` is left null → Platform Event never fires | `publish_brief` skill |
| Citation-bound chart intent | 🟡 designed, visx installed, no live chart renderer on Research terminal | Narrative depth §2 of arc doc |
| Drag-drop filing ingestion (multimodal) | 🔴 designed only | Narrative depth §2 of arc doc |
| Demand signals (RM → Sarah queue) | 🟡 slide-only, pre-seeded rows | Narrative 4 |
| Live traversal / architecture map | 🟡 TraversalMapV3 atom exists, rendered | `v3/atoms/TraversalMapV3.tsx` |

### 2.2 What the Research Terminal UI looks like today

Reading `ResearchTerminalV3.tsx` the actual surface is:

- **Top:** PersonaHeaderV3 with persona badge, forensic dark theme
- **Toolbar:** single query input, Cmd-Enter submit, placeholder "Research NVDA ahead of earnings…"
- **Main body split 60/40:**
  - **Left pane:** Brief Markdown streaming with citation chips + running tool-call chips
  - **Right stack:**
    - Market · live (empty placeholder, "loads from research_orchestrator's market_specialist on first turn")
    - Demand Signals (pre-seeded list with "accept →" buttons)
- **Collapsible:** Architecture map panel (TraversalMapV3)
- **Collapsible:** End-to-end trace panel
- **Bottom strip:** AuditStripV2 (correlation_id, WebSocket status, latencies)
- **Right drawer on citation click:** source chunk drill-down (filing type, date, section, page, text)

### 2.3 What's genuinely impressive about the current terminal

- Single input, fan-out to 5 parallel sub-agents visible in the map panel — this is the money shot of multi-agent
- Every claim in the brief has a citation chip → one-click drill to source chunk
- Running tool-call chips show which MCP is in flight ("sec-edgar… · running")
- Keyboard-first (Cmd-Enter, `/` to focus input)
- The architecture map genuinely lights up in real time during a turn

### 2.4 What the current terminal is missing to feel like an analyst's workstation

What a practitioner looking at the screen would ask for in the first 30 seconds:

1. "Where is my coverage list?" — no persistent watchlist of the tickers Sarah covers
2. "Where is the earnings calendar?" — no view of what's printing this week
3. "Where is the model?" — the brief has narrative, not numbers in an editable grid
4. "Where are my prior notes?" — no history of briefs she's written; each turn is stateless to the UI
5. "Where is my peer comparison?" — sector context is prose, not a table
6. "Where is the price chart?" — right pane says "Market · live" but renders nothing pre-turn
7. "Where can I pin something?" — no way to save a passage, citation, or finding for later
8. "Where is the catalyst list?" — no surface for "what's coming up that moves this stock"
9. "Where does my morning note go?" — no concept of "publish this to sales/trading" distinct from "publish to RM"
10. "Why do I have to retype the ticker every query?" — no ticker-bound session state

These are the gaps a Salesforce FSC / sell-side panel will see instantly. Fortunately, none of them require LLM research — they're UI and state-shape work on top of the existing specialist fan-out.

---

## 3. Enhancement directions, grouped by theme

Six themes. Each theme has 2–4 concrete features. Every feature is scored for demo value (1–5), build cost in half-days (0.5 = 2h, 5 = a week), and dependency on anything currently broken in the stack.

### Theme A — Coverage + context (the "workstation" feel)

The gap: today Sarah types a ticker cold every turn. A real analyst has a coverage list she lives inside for weeks.

| # | Feature | What it shows | Demo value | Build cost | Depends on |
|---|---|---|---|---|---|
| A1 | **Coverage list rail** (left sidebar) with the analyst's covered tickers, last brief date, last price, 1-day %, next catalyst date | The analyst has a book. Click a ticker → preloads context into the query input and prefetches filings + quote. | 5 | 1.5 | Static JSON + market-data MCP |
| A2 | **Earnings calendar** strip at top showing next 7 days of prints from covered tickers, color-coded (pre-market / after-hours) | "Here's my week" — matches real terminals [Koyfin](https://www.koyfin.com/blog/top-earnings-calendar-platforms/), [AlphaSense](https://help.alpha-sense.com/hc/en-us/articles/42283041818899-Create-an-Earnings-Dashboard) | 4 | 1 | Finnhub `/calendar/earnings` (already in MCP toolset) |
| A3 | **Ticker-bound session** — once you click AAPL in the rail, everything scopes to AAPL until you switch. Query input shows `AAPL · ` prefix. | Shows the session is stateful and agent memory actually works. | 3 | 0.5 | AgentCore session memory (already wired) |
| A4 | **"What changed since my last brief"** chip on covered tickers — pulls price delta, news delta, 8-K since last publish | Makes the coverage list living. Triggers demand signal replacement. | 4 | 1.5 | Research_Brief__c SOQL + market-data |

### Theme B — Catalysts + calendar (the "what's coming" feel)

| # | Feature | What it shows | Demo value | Build cost | Depends on |
|---|---|---|---|---|---|
| B1 | **Catalyst map** right-side panel listing upcoming events per ticker: earnings, guidance, product launches, regulatory deadlines, investor days | "The job is forward-looking, not historical summarization." | 4 | 2 | News MCP + EDGAR 8-K calendar |
| B2 | **Consensus snapshot** — EPS, revenue, margin consensus with N estimates, high/low/mean, revision trend | [Zacks](https://www.zacks.com/topics/zacks-consensus-estimate) / [WSJ](https://www.wsj.com/market-data/quotes/GOOG/research-ratings) equivalent. Shows the analyst is in the institutional flow. | 4 | 1.5 | Finnhub `/stock/recommendation` + `/stock/earnings` (paid tier — may need stub for demo) |
| B3 | **Earnings preview template** — one click from calendar row → pre-filled query: "Preview {ticker} {quarter} — consensus {eps/rev}, focus on {top 3 segments from last call}" | Turns the calendar from display into a query launcher. | 3 | 0.5 | B2 |

### Theme C — The note, not just the brief

Today's brief is a live streaming Markdown doc, discarded at session end (except for the Salesforce write). A real analyst's note is a versioned artifact she edits, publishes, and cites.

| # | Feature | What it shows | Demo value | Build cost | Depends on |
|---|---|---|---|---|---|
| C1 | **Draft → Publish toggle** — the brief lands in a "Drafts" tray by default. Sarah reviews, edits markdown inline, clicks Publish. This is what actually sets `Published_At__c` and fires the Platform Event to RM. | Fixes the current silent-null bug AND matches how analysts actually work. The button is the gate. | 5 | 1.5 | Fix `publish_brief` to honor `Published_At__c` (already in fix list item #2) |
| C2 | **Prior briefs drawer** — searchable list of every brief Sarah has published, grouped by ticker | "I wrote a note on NVDA on March 15, let me pull it up" — the table stakes of any analyst workstation. | 4 | 1 | SOQL against Research_Brief__c (already writable) |
| C3 | **Note versioning** — each publish creates a `Research_Brief__c` with `version__c` incrementing. Show diff between v2 and v1 on hover. | Compliance audit + analyst memory in one. | 3 | 1.5 | Schema change on Research_Brief__c |
| C4 | **Pin-to-note** — while browsing a citation drill-down or peer table, click "pin" to drop the element into the current draft | The "collect evidence, then write" pattern every analyst uses. | 4 | 2 | Zustand store extension for pinned items |

### Theme D — Numbers, not just narrative

Today the brief is all prose. A Principal-level practitioner knows the narrative is the wrapper; the real work is the numbers.

| # | Feature | What it shows | Demo value | Build cost | Depends on |
|---|---|---|---|---|---|
| D1 | **Financial statement panel** — when `statement_specialist` returns, render a small three-statement grid (revenue / gross margin / op margin / net margin / EPS, last 5Y + next 2Y forecast) instead of prose | Proves deterministic math from §1.4 of the arc doc actually reaches the screen. This is the single biggest "Principal-level" visual upgrade. | 5 | 2.5 | `financial_statement_analysis` skill + visx Table (already installed) |
| D2 | **Peer comparison table** — pick 3 peers on an axis (gross margin, R&D intensity, ROIC), render as a bar chart with covered ticker highlighted | Standard analyst comp table. Matches the `compare_peers` tool contract already in the arc doc §1.3. | 4 | 2 | D1 |
| D3 | **Valuation band** — forward P/E vs. 5Y history, with current reading marked | One chart that tells a pricing story. Visx scale + shape already installed. | 3 | 1 | Finnhub historical P/E (may need vendor upgrade or synthetic for demo) |
| D4 | **DCF sensitivity heatmap** — grid of growth rate × WACC → intrinsic value | Iconic analyst visual. Shows deterministic math orchestration. | 4 | 2.5 | `financial_statement_analysis.run_dcf` (exists as code path per arc doc) |

### Theme E — Inbound flow (news, filings, channel checks)

| # | Feature | What it shows | Demo value | Build cost | Depends on |
|---|---|---|---|---|---|
| E1 | **Live news ticker** — right rail, 30s auto-refresh, filtered to covered tickers | Pre-turn context. Makes the screen feel alive when no one is typing. | 3 | 1.5 | Tavily MCP (already live) |
| E2 | **Filings feed** — auto-poll EDGAR for new 8-K / 10-Q on covered tickers, badge count on ticker in rail | The "a filing dropped 3 minutes ago" moment. | 4 | 2 | sec-edgar MCP + EventBridge scheduler |
| E3 | **Drag-drop PDF** — drop a broker PDF or sell-side note onto the terminal → Textract → queryable source | Multimodal depth commitment from arc doc §1.2. Biggest "wow" in the depth doc, zero-built. | 5 | 3 | New skill: `ingest_document` + S3 + Textract |
| E4 | **Expert call / channel check notes** — a simple rich-text field saved to Research_Brief__c with `note_type = 'channel_check'` | Matches the real workflow (expert calls land in the research system) | 2 | 1 | Schema change |

### Theme F — Trust visibility (what Principal-level actually looks like on screen)

| # | Feature | What it shows | Demo value | Build cost | Depends on |
|---|---|---|---|---|---|
| F1 | **Specialist gantt** — waterfall timeline of the 5 specialists in the current turn, side-by-side, proving `asyncio.gather` parallelism | §3 of `v3-live-traversal-ui-design.md` Option 3. Seniors ship this, juniors ship a spinner. | 5 | 2 | Existing WebSocket span events |
| F2 | **Cost meter** — running $ this session, tokens consumed, per-specialist breakdown, cost-per-brief target | Langfuse already emits; surface it. Makes unit economics visible. | 3 | 1 | Langfuse span taxonomy (already correct) |
| F3 | **MNPI / restricted-list banner** — red strip at top when the query ticker is on the restricted list, with explanation | The trust spine visibly catching a bad query. Narrative 3 in the making. | 4 | 1.5 | `compliance_screening` skill already returns the restriction reason |
| F4 | **Provenance density score** on each section of the brief — "this paragraph has 4 citations covering 92% of claims" | The citation-enforcement harness made legible. Differentiator vs. every ChatGPT demo. | 4 | 1.5 | Citation stream already flows per `StreamingText` component |

---

## 4. Demo-worthiness ranking

Applying the rubric: demo value × (1 / build cost), weighted by whether the feature tells a story the panel hasn't seen before from any other vendor.

### 4.1 Tier 1 — ship for the next demo (high value, low cost, story-critical)

| Rank | Feature | Why it earns the slot |
|---|---|---|
| 1 | **A1 — Coverage list rail** | Transforms the terminal from "search box" to "workstation." Panel sees persistence. 1.5 half-days. |
| 2 | **C1 — Draft → Publish toggle** | Fixes the `Published_At__c` bug in the course of shipping a better UX. The button IS the HITL gate for publishing. Fires the Platform Event to RM → makes Narrative 2 cleaner. |
| 3 | **F1 — Specialist gantt** | The single best visual proof of "true multi-agent, not costume change." Data is already flowing on the WebSocket. |
| 4 | **D1 — Financial statement panel** | Replaces "statement_specialist returned prose" with a grid of numbers. Makes §1.3 of the arc doc (deterministic math) visible. |
| 5 | **A2 — Earnings calendar strip** | Context at the top of the screen. Makes the terminal feel alive before the first turn. |

### 4.2 Tier 2 — second wave (high value, medium cost, deepen the story)

| Rank | Feature | Why |
|---|---|---|
| 6 | E3 — Drag-drop PDF | Multimodal depth commitment goes from slide to live. |
| 7 | D4 — DCF sensitivity heatmap | Iconic analyst visual. Proves deterministic math further. |
| 8 | C2 — Prior briefs drawer | Session persistence story. |
| 9 | F3 — MNPI/restricted banner | Trust-spine visibility. Teasers Narrative 3 live. |
| 10 | B1 — Catalyst map | Forward-looking surface. |

### 4.3 Tier 3 — nice-to-haves

A3, A4, B2, B3, C3, C4, D2, D3, E1, E2, E4, F2, F4 — all defensible, none panel-critical for the 006 V3 story arc.

---

## 5. What SHOULD and SHOULD NOT go into the demo

### 5.1 Go

1. **Coverage list with click-to-prefetch** (A1) — the panel instantly understands what an analyst workstation is.
2. **Draft → Publish flow with the Platform Event visibly firing** (C1) — one animation: Sarah clicks Publish → toast "Brief published to RM" → split-screen RM tab: new item in queue. Two personas, one click, sub-second. This is the cross-persona handshake sold as a UI moment.
3. **Specialist gantt during the turn** (F1) — on screen while Sarah waits her 15 seconds. Five bars, not a spinner. "Four of five specialists finished in parallel."
4. **Financial statement panel with numbers** (D1) — when `statement_specialist` returns, render the grid. Even a 5x5 grid of five years of margins is enough.
5. **Citation drill-down preserved** — already built, already works; keep foregrounding it.
6. **One multimodal moment** (E3) — if there's time: drop a PDF, watch it become a citable source. Single highest "seniors vs juniors" visual in the depth doc.

### 5.2 Do NOT go

1. **Do not add a model editor grid.** Analysts build models in Excel. Trying to replace Excel in a demo is a losing trade and not what V3 is about.
2. **Do not add live co-authoring.** Scope creep, zero marginal story.
3. **Do not add sector-rotation / portfolio-construction.** That's a portfolio manager, not a research analyst. Wrong persona.
4. **Do not add options analytics.** Distraction.
5. **Do not invent consensus data if we can't source it honestly.** B2 needs a paid vendor tier or an explicit stub labeled as such in the UI. If we can't get real Finnhub consensus, drop B2 rather than fake it.

### 5.3 The one-slide framing

> "V3 Research Terminal — the analyst workstation, but every number is cited, every agent is visible, every publish is auditable. Sarah's coverage list on the left. Her live turn in the middle with five specialists fanning out in parallel on a gantt. Her deterministic-math statement grid on the right. One click to publish → the RM queue lights up."

---

## 6. Executable feature map

### 6.1 Stories, not just features

Eight epics. Each has a story statement, acceptance test, and rough size in half-days (0.5 days = 2 hours of focused work).

| ID | Epic | Story | Acceptance | Size |
|---|---|---|---|---|
| R-E1 | Coverage list | As Sarah, I can see my covered tickers in a left rail, click one, and have my next query scoped to that ticker with prefetched quote + filings | Click AAPL → toolbar shows `AAPL ·` prefix; quote renders in Market panel without user typing; next turn respects ticker scope | 2 |
| R-E2 | Draft → Publish | As Sarah, my brief lands as a draft I can edit and explicitly publish; publishing writes `Published_At__c`, fires the Platform Event, and notifies the RM queue | After turn completes: brief in "Drafts" tab; edit → save → Publish → toast "Brief published"; on RM tab the Actions queue increments within 2s | 3 |
| R-E3 | Specialist gantt | As Sarah, during a turn I see a horizontal gantt of specialists running in parallel with real latencies | Turn in progress → gantt renders 5 bars, bars grow left-to-right with elapsed time, completed bars turn green, timed-out bars turn red; total wall-clock matches brief latency | 2.5 |
| R-E4 | Statement grid | As Sarah, when `statement_specialist` returns, I see a 5Y + 2Y forecast grid of core financials, not prose | Statement panel replaces prose; cells are clickable → drill to filing line item; hover shows source citation | 3 |
| R-E5 | Earnings calendar | As Sarah, I see the next 7 days of earnings prints for covered tickers at the top of my screen | Calendar strip above toolbar; each cell shows ticker + date + time + (consensus EPS if available); click cell → pre-populates an earnings-preview query | 1.5 |
| R-E6 | Prior briefs | As Sarah, I can search and open my prior briefs via a right-drawer drawer | Drawer button in PersonaHeaderV3; drawer opens, searchable list (ticker, date, title), click to load into brief pane read-only | 2 |
| R-E7 | Drag-drop PDF ingest | As Sarah, I can drop a PDF onto the terminal and have it become a citable source within 10s | Drop PDF → progress toast → new "uploaded filings" chip → next query can cite it via `[src:upload-xxx]` | 4 |
| R-E8 | MNPI restricted banner | As Sarah, if my query touches a restricted ticker, I see a prominent banner with the reason and the brief generation is blocked | Query "Research TSLA…" (if TSLA restricted in dev) → red banner → no brief streams → audit row writes `compliance: BLOCK` | 2 |

**Total:** 20 half-days = 10 focused build-days across R-E1 through R-E8. Realistically half of these (R-E1, R-E2, R-E3, R-E4, R-E5 = 12 half-days = 6 build-days) is the sensible Tier-1 scope.

### 6.2 Sequencing

Suggested execution order if one engineer owns it over ~2 calendar weeks:

```
Day 1–2 (R-E1)    Coverage list rail + ticker-bound session scope
Day 3 (R-E5)      Earnings calendar strip (depends on market-data MCP extension)
Day 4–5 (R-E3)    Specialist gantt (data already flowing; pure rendering)
Day 6–8 (R-E2)    Draft → Publish flow + fix the Published_At__c silent-null bug
Day 9–11 (R-E4)   Statement grid (touches financial_statement_analysis skill + new panel)
[Demo-ready checkpoint — ship here if time constrained]
Day 12 (R-E6)     Prior briefs drawer (SOQL + drawer atom)
Day 13–14 (R-E8)  MNPI banner + blocked-turn path
Day 15–18 (R-E7)  Drag-drop PDF (Textract + skill + UI affordance)
```

### 6.3 What breaks if we do NOTHING

- The panel sees the current terminal as a ChatGPT variant with citations. That's 2023's demo, not 2026's.
- `Published_At__c = null` silently means Sarah's briefs never reach RM. Narrative 2 is weaker than the slide suggests.
- `statement_specialist` timing out + returning prose means §1.3 of the arc doc ("deterministic math, LLM orchestration") is not observable.
- No coverage list means every turn starts from zero — the session-memory claim has no on-screen evidence.
- No specialist gantt means the multi-agent claim is an assertion, not a demonstration.

### 6.4 What's intentionally out of scope

- Internal HITL gates during research generation (that's V3 non-goal per arc doc)
- LangGraph / pipeline architecture (V2-only)
- Real-time co-editing of the brief (not an analyst workflow)
- Portfolio-construction features (wrong persona)
- Compliance approval of publish (RM-side, different persona, Narrative 3/5)

---

## 7. Dependencies on the current broken state

The Tier-1 features depend on three items from the fix list in `v3-design-vs-built-vs-deployed-v2.md §9`:

- Item #6 — "Increase per-worker timeout from 25s to 60s" → unblocks `statement_specialist` returning on time → D1 / R-E4 works end-to-end
- Item #2 — "Investigate why `publish_brief` doesn't set `Published_At__c`" → is solved organically by R-E2 (the Publish button is where that field should be set)
- Item #7 — "Wire specialists through `run_tool_loop()`" → not strictly a blocker for the UI changes, but the statement grid will render synthetic data until the specialist returns structured output instead of Python code

Nothing in the Tier-1 scope depends on MuleSoft being deployed, Cognito being wired, or the CloudFront origin being fixed — all orthogonal issues.

---

## 8. Summary

Sarah's terminal today does the hardest thing (multi-agent fan-out with citation-bound streaming over real Bedrock). It's missing the things that make a research workstation feel like one: a coverage list, a calendar, a draft/publish loop, visible parallelism, and a numbers grid when the math specialist returns.

Ten build-days of focused work — one rail, one strip, one gantt, one grid, one publish button — transforms the demo from "impressive chat" to "the workstation an analyst would actually adopt." None of it requires new agents, new MCPs, or new trust infrastructure. All of it is on-ramps onto plumbing that already exists.

The Principal-level bet in this feature map is that the panel is not looking for more AI capability — they are looking for more evidence of what the AI is already doing. Coverage list, gantt, statement grid, and a visible Publish button are four pieces of evidence. Ship them in that order.

---

## 9. References

Industry practice and analyst role:
- [Corporate Finance Institute — Equity Research Overview](https://corporatefinanceinstitute.com/resources/career/equity-research-overview/)
- [Mergers & Inquisitions — Equity Research Careers: Day in the Life](https://mergersandinquisitions.com/equity-research-careers/)
- [InterviewPrep — Equity Research Analyst Job Description](https://interviewprep.org/equity-research-analyst-job-description/)
- [BLS — Financial Analysts Occupational Outlook](https://www.bls.gov/ooh/business-and-financial/financial-analysts.htm)
- [CFA Institute — Research Analyst Careers](http://cfainstitute.org/programs/cfa-program/careers/research-analyst)
- [FINRA Series 86 Reference](https://securitiesexamsmastery.com/finra/series86/cheat-sheet/)

AI in research:
- [AlphaSense — Generative AI for Investment Research](https://www.alpha-sense.com/solutions/generative-ai-investment-research/)
- [Bloomberg Agentic AI on the Terminal](https://www.tradersmagazine.com/xtra/bloomberg-introduces-agentic-ai-to-the-terminal/)
- [AWS Bedrock — Multi-Agent Investment Research (Part 3)](https://aws.amazon.com/blogs/machine-learning/part-3-building-an-ai-powered-assistant-for-investment-research-with-multi-agent-collaboration-in-amazon-bedrock-and-amazon-bedrock-data-automation/)
- [FinRobot — Equity Research with LLMs (arXiv 2411.08804)](https://arxiv.org/html/2411.08804v1)
- [Pathway — AI Tools for Equity Research](https://pathway.com/blog/ai-tools-for-equity-analysis)

Calendars and consensus:
- [Koyfin — Earnings Calendar Platforms 2026](https://www.koyfin.com/blog/top-earnings-calendar-platforms/)
- [Zacks — Consensus Estimates](https://www.zacks.com/topics/zacks-consensus-estimate)
- [LSEG — Consensus Ratings & Forecasts](https://www.lseg.com/en/investor-relations/consensus)

V3 internal references:
- `docs/v3-narrative-arc.md`
- `docs/v3-design-vs-built-vs-deployed-v2.md`
- `docs/v3-live-traversal-ui-design.md`
- `docs/v3-demo-queries-by-narrative.md`
- `frontend/src/v3/personas/ResearchTerminalV3.tsx`
- `frontend/src/v3/atoms/TraversalMapV3.tsx`
- `openclaw/skills/financial_statement_analysis/`, `openclaw/skills/publish_brief/`

Content was rephrased for compliance with licensing restrictions.
