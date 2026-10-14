# 006 V3 — Advisor (Relationship Manager) Persona Feature Map

> **Date:** 2026-05-01
> **Author:** research study, not a build plan
> **Audience:** exec panel, product, engineering steering
> **Scope:** `fsi-advisor` persona only (Marcus Kerrigan). What a real RM does, what V3 already ships for the advisor surface, what's missing, what's demo-worthy, and an executable feature backlog ranked by demo value × build cost.
>
> **Status:** research → prioritized backlog. No code changed.
> **Companion:** `v3-research-analyst-feature-map.md` (Sarah) and `v3-advisor-there-vs-not.md` (at-a-glance table).

---

## 1. What a relationship manager / wealth advisor actually does

Based on the Bank of America / Merrill [Private Wealth Client Relationship Manager job description](https://careers.bankofamerica.com/en-us/job-detail/25020136/private-wealth-client-relationship-manager-los-angeles-california-united-states), the [Nextvestment analysis of large-book RM workflows](https://nextvestment.com/resources/blog/how-relationship-managers-manage-large-client-books), [Salesforce's Financial Services Cloud agentic adviser framing](https://www.salesforce.com/ca/financial-services/wealth-asset-management-agentic-advisor/), and [Morgan Stanley's IPS guidance](https://www.morganstanley.com/articles/investment-policy-statement). Content paraphrased to comply with licensing restrictions.

### 1.1 The job, in one paragraph

A relationship manager (or financial advisor / wealth advisor / private banker) owns a book of clients — typically 80–300 households for a mass-affluent RM, 20–60 for a private banker, and 10–30 for an ultra-high-net-worth (UHNW) RM. They are the single point of contact for every client. They translate research and market events into client-specific recommendations, execute or supervise trades, monitor portfolio drift against an Investment Policy Statement (IPS), handle servicing questions (wire, statements, tax documents), run periodic reviews, and document every recommendation under Reg BI / suitability obligations. They don't pick stocks cold — that's research. They don't build portfolios from scratch every day — that's the CIO / model desk. Their work is **per-client contextualization** of everything upstream.

### 1.2 The daily rhythm

| Time block | Activity | Deliverable |
|---|---|---|
| 07:30–08:30 | Read overnight research, flag clients impacted | Mental list of calls to make |
| 08:30–09:30 | Morning huddle with sales desk / planning team | Call list for the day |
| 09:30–12:00 | Proactive client calls: explain market moves, suggest rebalancing, follow up on open items | Notes to CRM, trade tickets drafted |
| 12:00–13:00 | Lunch / networking (HNW+) | Relationship building |
| 13:00–16:00 | Inbound client requests, review pending trades, approve suitability, document rationale | Approved trades, suitability memos |
| 16:00–17:00 | Admin: update CRM, ActionPlans, check compliance queue, respond to ops | Closed tasks |
| 17:00–18:00 | Prep next-day outbound list, review upcoming reviews / birthdays / anniversaries | Tomorrow's plan |
| Monthly/quarterly | Client reviews: IPS check, rebalancing, tax-loss harvest, goal check-in | Review deck, recorded recommendation |

### 1.3 The functional primitives — what the work actually consists of

Seven repeating work units:

1. **Book management.** 80–300 clients / households on a single screen, sorted by revenue, concentration risk, next-action date, or recency of contact. Segmentation by tier (core / growth / UHNW), product mix, life-stage.
2. **Client 360 on demand.** Positions, allocation, IPS bands, goals, tax-lots, margin status, beneficiaries, recent activity, linked accounts, household tree, open tasks. Every meaningful client interaction starts here.
3. **Portfolio analytics.** Drift vs. target allocation, concentration breaches, sector tilt, cash drag, tax-lot analysis, hypothetical trade impact, performance vs. benchmark, what-if scenarios.
4. **Recommendations and trade origination.** Draft a trade → check suitability (Reg BI) → check compliance / restricted list → document rationale → submit for approval (dual-auth for large or unusual trades) → route to operations or OMS → confirm execution.
5. **Task / Action Plan management.** Scheduled reviews, required disclosures, onboarding steps, regulatory affirmations, birthdays, anniversary, educational milestones, estate updates. Salesforce FSC's Action Plans are the canonical model.
6. **Inbound servicing.** Client message / call / email → triage → answer directly, escalate to specialist, or create task. Much of this is non-advice: wire status, tax-document requests, login help.
7. **Documentation and compliance.** Every recommendation documented with rationale, every trade logged with suitability determination, every client interaction captured. Reg BI care / disclosure / conflict / compliance obligations. Supervisory review chain.

### 1.4 What makes it hard

From [Nextvestment's analysis of large RM books](https://nextvestment.com/resources/blog/how-relationship-managers-manage-large-client-books): the fundamental tension is keeping personalized, meaningful engagement with a large number of clients while staying on top of market movements, compliance obligations, and individual circumstances — all at once.

What breaks first under load:
- **Proactive outreach** becomes reactive. RM only calls clients who called first.
- **Drift monitoring** becomes post-hoc. Breaches found at quarterly review, not when they happen.
- **Documentation** becomes retrospective and thin. Reg BI audit finds memos written weeks after the trade.
- **Cross-sell and planning** get deprioritized under servicing load.

### 1.5 Reality of AI in RM workflow, 2026

From [RBC Wealth's AI deployment announcement](https://www.rbcwealthmanagement.com/en-ca/newsroom/2026-04-27/rbc-wealth-management-wins-dual-recognition-for-its-use-of-ai-to-better-empower-advisors), [Finantrix's rebalancing automation study](https://www.finantrix.com/articles/how-to-automate-client-rebalancing-notifications-and-approval-workflows), and [Salesforce's Agentic Adviser positioning](https://www.salesforce.com/ca/financial-services/wealth-asset-management-agentic-advisor/):

- The dominant use case is **meeting prep and post-call documentation** — draft the review deck from CRM data, draft the follow-up memo from the call transcript, flag IPS-relevant discussion points for the next review.
- Second is **proactive signal surfacing**: which clients in my book are impacted by today's news / this morning's research / this quarter's rebalance; who's drifted; who's about to roll a CD.
- Third is **trade drafting**: convert a conversational instruction into a compliant trade ticket with suitability memo pre-drafted.
- Human approval remains mandatory. The RM is still the regulated person of record.
- Trust guardrails: no AI-generated recommendation can be surfaced to client without RM review; every AI output must be auditable.
- Measured wins: rebalancing studies cite 67% advisor-time reduction on routine tasks; 73% of clients approve rebalances within 24h when the notification has clear cost breakdowns.

---

## 2. What 006 V3 already has for Marcus

Cross-checked against `docs/v3-narrative-arc.md`, `docs/v3-design-vs-built-vs-deployed-v2.md`, `frontend/src/v3/personas/AdvisorWorkbenchV3.tsx`, `frontend/src/v2/personas/AdvisorWorkbenchV2.tsx`, `frontend/src/v2/atoms/`, and the `openclaw/skills/` directory.

### 2.1 Functional primitives currently covered

| Primitive | V3 status | Evidence |
|---|---|---|
| Trade draft → 7-gate approval with dual-auth | 🟢 **code live**, Narrative 5 partial (no MuleSoft) | `action_specialist` + `hitl` + `dual_auth` + `mulesoft_api` skills |
| HITL inline action card in the conversation | 🟢 built | `InlineActionCard` atom (v2, reused) |
| 7-gate tracker with progressive disclosure (only when plan in flight) | 🟢 built | `GatesTrackerV2` + `planInFlight` gate in V3 |
| Optimistic-approval UI with rollback on backend failure | 🟢 built | `useOptimisticApproval` hook |
| Compliance / restricted-list screen before write | 🟢 live | `compliance_screening` skill |
| Audit row on every outcome | 🟡 **fails silently** — 3 stitching fields missing from SObject (`Agent_Id__c`, `Session_Id__c`, `Research_Brief_Id__c`) | per `v3-design-vs-built-vs-deployed-v2.md §4d` |
| Research brief awareness (RM reads Sarah's brief) | 🟡 built but `Published_At__c=null` blocks Platform Event → RM queue never notified | `research_awareness` skill, PE trigger on Research_Brief__c |
| Portfolio analytics (drift, concentration, scenario) | 🟡 skill code exists; no RM-side UI surface | `portfolio_analytics` + `scenario_modeling` skills |
| Suitability check (Reg BI) | 🟡 skill code exists; not visible in UI | `suitability_check` skill |
| Client summary / Client 360 | 🟡 skill code exists (`client_summary`); V3 workbench shows placeholder text "V3.1 roadmap" | UI stubbed in V3 |
| Actions queue (inbound from liaison) | 🟡 V2 has a working `ActionsQueueColumn`; V3 replaced it with placeholder text | V3 file line ~75 |
| Live trade execution via MuleSoft (Alpaca / Dwolla) | 🟡 code complete; CloudHub deploy never ran | per §9 fix list item #8 |
| Client 360 IPS allocation bar + concentration warnings | ❌ | explicitly deferred to "V3.1" in V3 file comments |
| Per-client drift / breach detection | ❌ | not built |
| Meeting prep / review-deck draft | ❌ | not built |
| Rebalancing wizard / model-portfolio diff | ❌ | not built |
| Proactive signal surfacing (who's impacted by today's news) | ❌ | demand-signal is research-side only |
| Task / ActionPlan management (FSC Action Plans) | ❌ | not built |
| Reg BI / suitability memo auto-draft | ❌ | suitability skill runs but no UI capture of rationale |
| Household tree view | ❌ | not built |
| Per-client activity timeline | ❌ | not built |
| Book-level analytics (AUM, revenue, concentration heatmap across book) | ❌ | not built |

### 2.2 What the Advisor Workbench UI actually shows today

Reading `AdvisorWorkbenchV3.tsx`:

- **Top:** PersonaHeaderV3 (SLDS light theme, Cognito sign-out optional)
- **Gate tracker:** renders only when a plan is in flight (progressive disclosure)
- **Three-column body:**
  - **Left — Actions:** placeholder text "Actions queue will populate as liaison hands off client inquiries. Details in V3.1." (V2 had a working queue; V3 regressed to a stub)
  - **Center — Conversation:** single AI message bubble with streaming text, `InlineActionCard` for HITL approval, free-text reply textarea at the bottom with Cmd-Enter submit
  - **Right — Client 360:** placeholder text "Client 360 populates when an Actions item is selected. V3.1 brings the IPS allocation bar + concentration warnings."
- **Collapsible:** Architecture map (TraversalMapV3, `gateChainVisible={planInFlight}`)
- **Collapsible:** End-to-end trace panel
- **Bottom strip:** AuditStripV2 with gates
- **In-flight overlay:** 7-gate progress bar during approval

### 2.3 What's genuinely impressive about the current advisor workbench

- **Inline HITL card inside the conversation thread** — the approval surface is the chat, not a separate modal. This is the "one place to work" pattern FSC Actions aspire to.
- **7-gate tracker with progressive disclosure** — dim when idle, alive when a plan is in flight. Shows trust spine visibly.
- **Optimistic approval with rollback** — Cmd-Enter approves, UI updates instantly, toast rolls back on failure.
- **Architecture map with gate-chain highlight** — the write-path through the 17 agents is visible.
- **Dual-auth gate is serial by design** — demo-able, auditable.

### 2.4 What the current workbench is missing to feel like an RM's workstation

A Salesforce FSC / wealth-mgmt panel would immediately ask:

1. "Where is my book?" — no client list / segmentation / filter
2. "Where is Client 360?" — stubbed placeholder, V2 had a working version
3. "Where is the Actions queue?" — stubbed placeholder, V2 had a working version
4. "Where are my positions?" — no holdings table, no allocation chart
5. "Where is drift monitoring?" — no drift / IPS band view
6. "Where is my day?" — no morning brief / call list / scheduled reviews
7. "Where is the suitability memo?" — suitability runs but doesn't produce a visible artifact
8. "Where is the rebalance wizard?" — the single highest-leverage RM workflow
9. "Where is my pipeline / AUM dashboard?" — no book-level analytics
10. "Where are Salesforce Action Plans?" — the canonical FSC feature isn't surfaced

Unlike the research terminal, where gaps are mostly additive, **the advisor workbench in V3 is a regression from V2** for the Actions queue and Client 360. V3.1 roadmap comments acknowledge this explicitly. That's the first thing to fix.

---

## 3. Enhancement directions, grouped by theme

### Theme A — Book of business (the "workstation" feel)

| # | Feature | What it shows | Demo value | Build cost |
|---|---|---|---|---|
| A1 | **Client list rail** (left column, replacing Actions placeholder or below it) — ranked by AUM, flagged for drift, last-contact date | "RM has a book, not a chat." | 5 | 2 |
| A2 | **Book-level heatmap** — concentration, drift, at-risk clients across the book | "I can see my 200 clients in one glance" | 4 | 2.5 |
| A3 | **Filter / segment** — tier, product, next-review, last-touch | Standard CRM segmentation | 3 | 1 |
| A4 | **Household tree** — primary + joint + trust + minor accounts rolled up | Matches FSC Householding | 3 | 2 |

### Theme B — Restore the V2 queue + Client 360 (no regression)

| # | Feature | What it shows | Demo value | Build cost |
|---|---|---|---|---|
| B1 | **Re-port ActionsQueueColumn from V2 to V3** | Removes "V3.1 roadmap" stub; makes Narrative 2 click-through work | 5 | 0.5 |
| B2 | **Re-port ClientContextColumn from V2 to V3** | Same | 4 | 0.5 |
| B3 | **Queue real-time via WebSocket `queue_update`** | "I saw the RM tab light up when Eleanor messaged" — narrative 2 payoff | 5 | 1 |

### Theme C — Client 360 (what RM actually looks at)

| # | Feature | What it shows | Demo value | Build cost |
|---|---|---|---|---|
| C1 | **Positions table** — ticker, quantity, market value, % of portfolio, 1-day Δ | Table stakes | 4 | 1.5 |
| C2 | **IPS allocation bar** — target vs actual with concentration warnings when outside band | Narrative 3 foundation. Explicitly deferred in V3 comments. | 5 | 2 |
| C3 | **Tax-lot view** — per-position lots, short/long, unrealized gain | Serious wealth tool | 3 | 2 |
| C4 | **Activity timeline** — recent trades, calls, emails, brief reads | Relationship context | 4 | 2 |
| C5 | **Goals / objectives display** | Planning context | 3 | 1.5 |

### Theme D — Portfolio analytics (deterministic, Principal-level)

| # | Feature | What it shows | Demo value | Build cost |
|---|---|---|---|---|
| D1 | **Drift dashboard** — per-client drift against IPS bands, breach flagging | Proactive monitoring, not reactive | 5 | 2.5 |
| D2 | **Hypothetical trade impact** — "if we sell X, what happens to allocation, concentration, tax cost" | Planning pane that justifies the trade | 4 | 2 |
| D3 | **Scenario modeling display** — rate shock, sector shock, recession scenario | `scenario_modeling` skill exists; surface it | 4 | 2 |
| D4 | **Cost breakdown on rebalance** — fees, tax impact, spread | Matches Finantrix "clients approve 73% when costs clear" finding | 3 | 1.5 |

### Theme E — The trade path (what V3 already does well — extend)

| # | Feature | What it shows | Demo value | Build cost |
|---|---|---|---|---|
| E1 | **Fix audit silent-null** — add missing `Agent_Id__c`, `Session_Id__c`, `Research_Brief_Id__c` to IR_Audit_Log__c | Trust spine has integrity; every write has audit row | 5 | 0.5 |
| E2 | **Suitability memo card** — at gate 2 of the 7-gate path, render the Reg BI rationale with client context, risk tolerance, concentration impact | Reg BI-grade documentation artifact in the UI | 5 | 2 |
| E3 | **Dual-auth approver inbox for senior compliance** — queue of pending approvals with reason for dual-auth trigger | Makes the dual-auth gate observable, not just logged | 4 | 2 |
| E4 | **Execution confirmation card** — post-MuleSoft receipt with exchange fill details, cost, settlement | Closes the loop. Ship when MuleSoft deploys. | 4 | 1.5 |
| E5 | **Deploy MuleSoft CloudHub apps** | Makes Narrative 5 fully live | 5 | 2 |

### Theme F — Proactive RM (the Agentforce differentiator)

| # | Feature | What it shows | Demo value | Build cost |
|---|---|---|---|---|
| F1 | **Morning brief card** — "Good morning Marcus. Last night: 3 briefs affecting 11 clients. 2 drift breaches overnight. 1 earnings call at 11am on a top-5 holding." | The "proactive, not reactive" pitch | 5 | 2.5 |
| F2 | **"Who's impacted" cross-reference** — new Sarah brief on NVDA → list of RM's clients with NVDA exposure → one-click draft outreach | The cross-persona handshake made useful. This is what a research brief IS to an RM. | 5 | 2.5 |
| F3 | **Client alert queue** — Client_Alert__c rows from compliance_sweep (Narrative 3) | Narrative 3 becomes live-capable | 4 | 2 |
| F4 | **Outreach drafting** — "Draft a note to all 11 NVDA-exposed clients explaining the brief" with per-client personalization | AI-assisted mass-personalization, still gated by RM review | 4 | 3 |

### Theme G — Servicing and review workflow

| # | Feature | What it shows | Demo value | Build cost |
|---|---|---|---|---|
| G1 | **Meeting prep assistant** — select client + meeting type → draft deck with allocation, performance, goals, suggested talking points | RBC/Morgan Stanley style use case | 4 | 3 |
| G2 | **Post-call documentation** — upload or paste transcript → draft CRM note + flag suitability changes | Second-most-cited RM AI use case | 4 | 3 |
| G3 | **Salesforce Action Plans surface** — FSC Action Plan templates visible in the workbench | Matches native FSC | 3 | 2.5 |
| G4 | **Upcoming reviews / birthdays** rail | Relationship continuity | 2 | 1 |

---

## 4. Demo-worthiness ranking

### 4.1 Tier 0 — regression fixes (these are embarrassing if left)

| Rank | Feature | Why |
|---|---|---|
| 0 | **B1 + B2** — restore Actions queue and Client 360 from V2 | V3 stubbed out two working components. Must fix before demo. 1 day. |
| 0 | **E1** — add missing audit fields | Trust spine has silent holes. Half a day. |
| 0 | **Fix `Published_At__c = null`** (shared with Sarah's R-E2) | Platform Event to RM never fires. |

### 4.2 Tier 1 — ship for the next demo (high value, medium cost, story-critical)

| Rank | Feature | Why |
|---|---|---|
| 1 | **F2** — "Who's impacted" cross-reference on brief arrival | The single best story for the cross-persona handshake. Sarah publishes → RM sees who cares → one click to outreach. |
| 2 | **C2** — IPS allocation bar + concentration warnings | Explicitly deferred in V3 code comments. Unblocks Narrative 3. |
| 3 | **A1** — Client list rail | RM has a book. Panel sees the workstation, not a chat. |
| 4 | **D1** — Drift dashboard | Proactive monitoring on screen. Fits with IPS bar. |
| 5 | **E2** — Suitability memo card inside the gate path | Reg BI grade documentation made visible during the demo. |
| 6 | **F1** — Morning brief card | Opens the RM session with a proactive summary. Hero shot. |

### 4.3 Tier 2 — second wave

C1, C4, D2, D3, E3, E4, E5 (MuleSoft deploy), F3, F4

### 4.4 Tier 3 — nice-to-haves

A2, A3, A4, C3, C5, D4, G1, G2, G3, G4

---

## 5. What SHOULD and SHOULD NOT go into the demo

### 5.1 Go

1. **Restored Actions queue + Client 360** (B1, B2) — no regression from V2
2. **Fixed audit stitching + `Published_At__c`** (E1 + shared fix) — trust spine credible
3. **"Who's impacted" view triggered by a new brief** (F2) — the cross-persona story gets its best visual
4. **IPS allocation bar with concentration warning** (C2) — Narrative 3 becomes live
5. **Client list rail** (A1) — workstation feel
6. **Drift dashboard** (D1) — proactive monitoring
7. **Suitability memo card in the 7-gate path** (E2) — Reg BI visible
8. **Morning brief card on workbench open** (F1) — first-impression moment
9. **MuleSoft deployed** (E5) — Narrative 5 becomes live, not draft-only

### 5.2 Do NOT go

1. **Do not build a full FSC Action Plans clone.** FSC already has it; we're augmenting, not replacing.
2. **Do not build a portfolio optimizer.** That's a CIO/model-desk tool, wrong persona.
3. **Do not build live quoting.** Latency-critical; reuse Finnhub at refresh cadence.
4. **Do not build trading analytics (TCA, Implementation Shortfall).** Wrong seniority of user.
5. **Do not invent mock drift data without sourcing IPS bands honestly.** Need real IPS bands per household in FSC; if not in the seed data, scope B2/D1 to a single household.
6. **Do not add a full compliance surveillance UI.** The compliance-sweep job owns Narrative 3; RM only sees alerts.

### 5.3 The one-slide framing

> "V3 Advisor Workbench — the RM's workstation with every client in a book, every drift on a dashboard, every recommendation memo-drafted for Reg BI, and every trade gated by the seven-step trust spine. When Sarah publishes a brief, the workbench instantly shows which of Marcus's 200 clients are affected and offers one-click personalized outreach. Approve a trade: the seven gates fire in sequence, the suitability memo writes itself, MuleSoft submits to Alpaca, and the audit row lands in Salesforce with full cross-persona stitching."

---

## 6. Executable feature map

### 6.1 Epics

| ID | Epic | Story | Acceptance | Size (half-days) |
|---|---|---|---|---|
| M-E0a | Restore V2 queue | As Marcus, I see a working Actions queue replacing the V3 "roadmap" placeholder | Queue renders; click item → Client 360 loads; matches V2 behavior parity | 1 |
| M-E0b | Restore V2 Client 360 | As Marcus, I see a working Client 360 instead of the V3 placeholder | Loads household snapshot when queue item clicked | 1 |
| M-E0c | Fix audit fields | Every write lands an IR_Audit_Log__c row with principal_id, session_id, agent_id, research_brief_id | Query count of audit rows per session = expected; no silent drops | 0.5 |
| M-E1 | Client list rail | As Marcus, I see my book of clients on the left, sortable by AUM / drift / last contact | Rail renders 200 clients; sort works; click loads Client 360 | 4 |
| M-E2 | IPS allocation bar | As Marcus, I see each client's actual vs. target allocation with breach chips | Bar renders with 4-6 asset-class buckets; concentration chip appears when >2% over band | 4 |
| M-E3 | Drift dashboard | As Marcus, I see a drift table across my book, sorted by biggest breach | Table with client / ticker / target / actual / Δ / days-out-of-band | 5 |
| M-E4 | "Who's impacted" on brief arrival | As Marcus, when Sarah publishes NVDA brief, my workbench surfaces a list of NVDA-exposed clients with one-click "draft outreach" | New brief event → list renders within 2s → clicking one queues an outreach draft | 5 |
| M-E5 | Suitability memo card | At gate 2 of the approval path, a card shows the Reg BI rationale drafted by the suitability skill | Card renders; editable; saved to Salesforce Suitability_Memo__c on approval | 4 |
| M-E6 | Morning brief card | Workbench opens with a card summarizing overnight briefs / drift / catalysts relevant to the book | Card renders on load; data populated from the prior 16 hours | 5 |
| M-E7 | MuleSoft deploy | 3 MuleSoft Process APIs deployed to CloudHub, Alpaca paper + Dwolla sandbox reachable | `mvn deploy -Pcloudhub-sandbox` succeeds; health endpoints respond | 4 |

### 6.2 Sequencing

Suggested execution order (~3 calendar weeks for one engineer):

```
Day 1        (M-E0a + M-E0b + M-E0c)  restore V2 + audit fields  — no regression, trust integrity
Day 2–3      (M-E1)                   client list rail
Day 4–5      (M-E2)                   IPS allocation bar
Day 6–8      (M-E3)                   drift dashboard
Day 9–10     (M-E7)                   deploy MuleSoft → Narrative 5 live
Day 11–13    (M-E4)                   "who's impacted" view + outreach draft
[Demo-ready checkpoint]
Day 14–15    (M-E5)                   suitability memo card
Day 16–18    (M-E6)                   morning brief card
```

Total ~ 28 half-days = 14 build-days. Demo-ready checkpoint at day 13 (26 half-days).

### 6.3 What breaks if we do NOTHING

- Panel sees a chat with a 7-gate bar. That's the 2024 V2 demo.
- RM surface is strictly worse than V2 for Actions queue and Client 360 — a live regression.
- Audit rows continue to drop silently for the advisor persona.
- Narrative 2 claim ("RM queue lights up when client messages") is falsified because `Published_At__c=null` breaks the Platform Event and the queue column is a stub.
- Narrative 3 (IPS breach / compliance sweep) has no surface to land on.
- Narrative 5 can only run in draft mode — MuleSoft isn't deployed.

### 6.4 What's intentionally out of scope for this persona cycle

- Client-side UI changes (that's `fsi-client-liaison` persona)
- Research-side changes (separate feature map)
- FSC Action Plans deep integration (defer to a V3.2 or V4)
- Multi-RM supervisor / team views (different persona)
- Trading desk / OMS direct integration (MuleSoft is the abstraction)

---

## 7. Summary

The V3 advisor workbench has a **strong trust spine** (7 gates, HITL card, optimistic approval, dual-auth) and a **weak daily-workstation surface** (queue and Client 360 regressed from V2 to placeholder; no book view; no drift; no IPS). The trade-path demo is the best in V3; the pre-trade life of an RM is barely represented.

Ten build-days of focused work fixes the regressions, adds the three workstation primitives (book, IPS bar, drift), and lights up the cross-persona handshake ("who's impacted" on brief arrival). That changes the demo from "impressive trade approval with seven gates" to "an actual wealth advisor workbench with the agents inside it."

The Principal-level bet on this persona: the panel is not skeptical that the agent can draft a trade — V3 already shows that. They're skeptical that the agent fits into the RM's real day. Morning brief, book view, drift, "who's impacted", suitability memo — that's the day. Ship those and the persona story holds.

---

## 8. References

RM / advisor role and workflow:
- [Bank of America / Merrill — Private Wealth Client Relationship Manager](https://careers.bankofamerica.com/en-us/job-detail/25020136/private-wealth-client-relationship-manager-los-angeles-california-united-states)
- [Nextvestment — How RMs Manage Large Client Books](https://nextvestment.com/resources/blog/how-relationship-managers-manage-large-client-books)
- [Spears Wealth Management — Charlie Hoffman at HSBC Private Bank](https://spearswms.com/wealth/wealth-management/charlie-hoffman-20bn-client-book/)
- [Finantrix — Streamline Client Onboarding](https://www.finantrix.com/articles/streamline-client-onboarding-for-private-banks-wealth-managers)

Rebalancing / drift / suitability:
- [Finantrix — Rebalancing Notifications & Approval Workflows](https://www.finantrix.com/articles/how-to-automate-client-rebalancing-notifications-and-approval-workflows)
- [MEMA Consultants — Wealth Management Suitability Framework](https://memaconsultants.com/resources/explainers/wealth-suitability-oversight)
- [NASAA — Documenting Suitability](https://www.nasaa.org/industry-resources/investment-advisers/resources/compliance-matters-documenting-suitability/)
- [CIRO — KYC and Suitability Guidance](https://www.ciro.ca/newsroom/publications/know-your-client-and-suitability-guidance)
- [Schwab Advisor Services — Trading & Investment Management](https://advisorservices.schwab.com/whats-new/trading-and-investment-management)
- [Morgan Stanley — Importance of an Investment Policy Statement](https://www.morganstanley.com/articles/investment-policy-statement)

Reg BI:
- [FINRA — Regulation Best Interest](https://www.finra.org/rules-guidance/key-topics/regulation-best-interest)
- [SEC — Standards of Conduct for BDs and IAs, Care Obligations](https://www.sec.gov/about/divisions-offices/division-trading-markets/broker-dealers/staff-bulletin-standards-conduct-broker-dealers-investment-advisers-care-obligations)
- [InnReg — Reg BI Explained](https://www.innreg.com/blog/regulation-best-interest-explained)

FSC and AI for advisors:
- [Salesforce — Financial Services Cloud Action Plans Module](https://trailhead.salesforce.com/content/learn/modules/action-plans-for-financial-advisors-in-financial-services-cloud/explore-action-plans)
- [Salesforce — Agentic Adviser for Wealth & Asset Management](https://www.salesforce.com/ca/financial-services/wealth-asset-management-agentic-advisor/)
- [RBC Wealth — AI Recognition](https://www.rbcwealthmanagement.com/en-ca/newsroom/2026-04-27/rbc-wealth-management-wins-dual-recognition-for-its-use-of-ai-to-better-empower-advisors)

V3 internal references:
- `docs/v3-narrative-arc.md`
- `docs/v3-design-vs-built-vs-deployed-v2.md`
- `docs/v3-demo-queries-by-narrative.md`
- `frontend/src/v3/personas/AdvisorWorkbenchV3.tsx`
- `frontend/src/v2/personas/AdvisorWorkbenchV2.tsx`
- `frontend/src/v2/atoms/` (GatesTrackerV2, InlineActionCard, AuditStripV2)
- `openclaw/skills/` (`portfolio_analytics`, `scenario_modeling`, `suitability_check`, `client_summary`, `research_awareness`, `hitl`, `dual_auth`, `mulesoft_api`)

Content was rephrased for compliance with licensing restrictions.
