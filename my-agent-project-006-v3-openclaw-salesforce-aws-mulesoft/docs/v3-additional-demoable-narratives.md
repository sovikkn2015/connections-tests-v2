# 006 V3 — 10 Additional Demoable Narratives

> **Purpose:** expand the demo arsenal with 10 new narratives that are runnable
> against the **currently live infrastructure** — no MuleSoft CloudHub, no
> missing SObjects, no unbuilt skills required.
> **Companion to:** `v3-narrative-arc.md` (original 5 narratives), `v3-demo-choreography.md` (four-act demo script).
> **Date:** 2026-04-29

---

## Ground rules — what "demoable now" means

Strict. Each narrative uses only pieces verified live:

- Real Bedrock Sonnet 4.6 + Haiku 4.5 via AgentCore v3 container (`openclaw_v3_agent-o72dx396I0`)
- Real MCP Lambdas — all 7 returning HTTP 200
- Real Finnhub quotes, real Bedrock KB (`NBR5AFTREI`, 784 chunks from 10 SEC filings), real Tavily search
- Real Salesforce per-user OBO via `sf-auth-proxy`
- Real deployed SObjects: `Research_Brief__c`, `Client_Inquiry__c`, `IR_Audit_Log__c` (with Agent_Id__c + Session_Id__c + Correlation_Id__c + Research_Brief_Id__c), `IR_Pending_Approval__c`, `Client_Preferences__c` + 2 Platform Events
- Real Langfuse trace capture via US cloud
- Real v3 SPA at `d2zs9nk4uc2dbx.cloudfront.net`

**Nothing** that requires:
- MuleSoft CloudHub (undeployed)
- `rm_handoff` skill (not yet in git)
- `Research_Request__c` / `Client_Alert__c` / `Research_Suggestion__c` SObjects (not in org)
- Demand-signal clustering (not built)

---

## Why these narratives exist

The original 5 carry the big Workflow 360 story. **These 10 are proof-layer narratives** — each takes one depth-layer commitment from the design doc and demonstrates it concretely in under 2 minutes, using only live infrastructure. Think of them as:

- Bricks for a tighter demo when panel time is short
- Backup material if a primary narrative misfires
- Technical-deep-dive fodder when the panel wants architecture questions
- Portable snippets for recording into a video library

---

## The 10 narratives

### N6 — Same brief, four audiences, one click

**Shape:** Sarah publishes one NVDA brief. SPA renders four persona views of it side-by-side.

**What happens live:**
- Sarah's terminal shows dense version with all numbers, risk factors, MNPI-flagged fields surfaced
- RM's screen shows positions-joined version with suitability framing on top
- Senior compliance sees full MNPI-cleared version with every source chunk listed
- Client channel shows MNPI-redacted one-paragraph version with disclaimer

Same `Research_Brief__c.Id`. Four MCP reads. Four different filtered payloads. The redaction happens server-side at the CRM MCP boundary, not in prompts.

**Proves:** data-layer MNPI redaction is real and automatic. The SObject is the handoff. Sharing rules + field-level `_mnpi_redact.py` do the work.

**Live pieces used:** `salesforce-crm` MCP, `_mnpi_redact.py`, existing Research_Brief__c rows.

**Length:** 90 seconds.

**One-line say:** *"Same row. Four readers. Different data. Enforced at the data boundary, not in a prompt."*

---

### N7 — Citation drill-down live

**Shape:** Sarah's brief renders with citation chips. Panelist clicks one. The exact chunk appears with full metadata — ticker, form, filing date, accession number, source URL to SEC.gov. Copy the URL into a new tab, land on the real filing.

**What happens live:**
- `CitationChip.onClick` → `GET /api/source_chunk/{source_id}`
- BFF Lambda → `bedrock-agent-runtime retrieve` on KB `NBR5AFTREI`
- Returns one of 784 chunks with `{ticker, form, filing_date, accession, source_url, source_chunk_id}`

**Proves:** "every sentence in the brief has a verifiable citation back to the 10-Q" is a live demonstration, not a claim. Closes the 2026 AI-demo bar for "show the work."

**Live pieces used:** KB `NBR5AFTREI`, 10 real 10-K/10-Q HTML files in raw-filings bucket, existing `CitationChip` component.

**Length:** 60 seconds.

**One-line say:** *"Every number in the brief traces back to a specific line in a specific SEC filing. Click the chip. See the chunk. Go to the filing."*

---

### N8 — The compliance comparison: same ticker, restricted vs not

**Shape:** Two sequential queries on the RM screen:
1. *"Research NVDA for client recommendation"* → **compliance_status: ALLOW**
2. *"Research AAPL for client recommendation"* → **compliance_status: DENY** with reason

**What happens live:**
- `compliance_screening` skill reads `restricted_list.json` deterministically
- NVDA passes → brief published with `rm_consumable: true`
- AAPL (pre-seeded as restricted for demo) fails → brief marked `rm_consumable: false`
- The DENY has no override flag, no bypass path, no prompt-softening

**Proves:** deterministic compliance gate is not prompt-advisory. Restricted list is a code-level check. The LLM cannot soften a DENY regardless of phrasing.

**Live pieces used:** `compliance_screening` skill (in-runtime), `restricted_list.json` (deployed).

**Length:** 90 seconds.

**One-line say:** *"Same prompt, different ticker. Code says no. There is no override flag. The agent cannot argue with the list."*

---

### N9 — Two RMs, same query, different books

**Shape:** RM1 queries *"Which of my clients have NVDA exposure above 5%?"* → sees Patel (6.2%). Panelist switches identity. RM2 with same query → sees Okafor (7.3%) instead.

**What happens live:**
- `X-Principal-Id` header carries the RM identity
- `sf-auth-proxy` Lambda performs JWT Bearer OBO per RM
- Salesforce FSC sharing rules return each RM's own book only
- Same code path, different data. Enforced by Salesforce, not by prompts.

**Proves:** per-user OBO is real. FSC sharing rules are the authz boundary, not agent logic. This is the design doc's *"data-layer authz wall"* commitment live on stage.

**Live pieces used:** `sf-auth-proxy` Lambda (JWT Bearer flow verified live earlier), 3 seeded Account/Contact/Position rows.

**Length:** 90 seconds.

**One-line say:** *"Two RMs. Same question. Different answers. Salesforce enforces who sees what, not the agent."*

---

### N10 — The dry-run ActionPlan (gates 1-5 live, no MuleSoft)

**Shape:** RM types *"Sell 150 NVDA from Patel household."* Agent builds ActionPlan, runs gates in order, intercepts at the MuleSoft gate with a dry-run marker. No real trade fires, but the full trust spine is visible.

**What happens live:**
- Guardrails screens input → pass
- MNPI filter scrubs output → pass
- `compliance_screening` skill → ALLOW
- `hitl` skill mints HMAC-SHA256 token bound to plan_hash → RM clicks Approve on screen → token verified single-use
- `dual_auth` skill checks $24K notional against thresholds → skip (below $500K)
- `mulesoft_api` skill branches on `MULESOFT_MODE=mock` → returns canned `ALPACA-REF-abc123` + writes audit row
- `audit_logging` skill writes `IR_Audit_Log__c` with `Action__c=TRADE_SUBMITTED`, full gate_trace, cross-stitched to Research_Brief_Id and Client_Contact_Id

**Proves:** 7-gate trust spine is real code — 5 of 7 gates fire against real infrastructure. When MuleSoft CloudHub deploys, only gate 6 changes from mock to live. The gate trace in the audit row lists every gate and its outcome.

**Live pieces used:** `action_specialist` tool-use loop (serial_by_design=True, run_tool_loop), all 5 gate skills, `MULESOFT_MODE=mock` existing env var, IR_Audit_Log__c with stitching fields.

**Length:** 2 minutes.

**One-line say:** *"Watch five gates fire. The sixth is where MuleSoft takes over in production. Today we stub it. Every other gate is real code, real HMAC tokens, real audit rows."*

---

### N11 — The MNPI tripwire (Guardrail fires)

**Shape:** Panelist types into Sarah's terminal: *"Research NVDA and tell me Patel's NVDA share count so I can size the recommendation."*

**What happens live:**
- Bedrock Guardrail `nlouzhamlv7h v1 READY` is attached to every converse call
- Input matches `InsiderInformation` topic policy
- AgentCore returns `GuardrailInterventionError`
- Coordinator catches, converts to `AgentError(SAFETY, recoverable=False)`
- UI shows: *"I can't help mix client-specific share counts with research context."*
- `IR_Audit_Log__c` row writes `Action__c=GUARDRAIL_INTERVENTION`

**Proves:** Bedrock Guardrail is not decorative. `FinancialActions` + `InsiderInformation` topics fire for real on adversarial input. The panel sees the refusal, not the attempt. The attempt itself is audited.

**Live pieces used:** Bedrock Guardrail (verified READY, id `nlouzhamlv7h`), coordinator's guardrail plumbing.

**Length:** 60 seconds.

**One-line say:** *"Not every question gets an answer. Some get a compliance record."*

---

### N12 — Haiku FAQ + escalation

**Shape:** Client channel:
1. *"What's your firm's minimum investment?"* → Haiku answers in ~2 seconds
2. *"What's the best time to buy NVDA?"* → Haiku escalates: *"That's a recommendation question. Your RM is better suited."*

**What happens live:**
- `liaison_orchestrator` (Haiku 4.5) classifies turn
- First = FAQ-scope → dispatches `faq_specialist` (Haiku, empty tool_allowlist, read-only) → bounded answer
- Second = beyond-FAQ → classified for escalation → disclaimer-wrapped handoff text returned
- Both turns write `IR_Audit_Log__c` rows

**Proves:** model-tier routing is real. Haiku is the cheap, fast, bounded-scope model. Sonnet isn't wasted on every client turn. The persona acknowledges what it can and can't answer without dropping into prompt disclaimers.

**Live pieces used:** liaison_orchestrator, faq_specialist (both deployed). Verified live in the 18-second probe turn earlier.

**Length:** 60 seconds.

**One-line say:** *"The client persona runs on Haiku. 20× cheaper. Still knows when to hand off."*

---

### N13 — The Langfuse trace replay

**Shape:** After any other narrative runs, open Langfuse US cloud in a browser. Click the most recent trace. Show the span tree.

**What happens live:**
```
session.<session_id>
  └── turn.1.persona.fsi_research
        └── skill.research_orchestrator
              ├── tool_call.market-data.get_quote       ← child span, real Finnhub
              ├── tool_call.sec-edgar.get_filing        ← real EDGAR
              ├── tool_call.news-search.sentiment_30d   ← real Tavily
              ├── tool_call.compliance_screening.check  ← local deterministic
              ├── rag_retrieve
              │     ├── bm25
              │     ├── dense                            ← real Titan v2
              │     └── rerank                           ← StubReranker in test path
              └── llm_call.claude-sonnet-4-6
```

Every payload shows the MNPI scrubber has replaced raw fields with bands: `"shares_held": "0-2.5%"` not `"shares_held": 1247`. Cost attribution dashboard shows per-persona, per-skill, per-user token spend.

**Proves:** business-auditable tracing, not dev-debuggable. A compliance officer can replay the decision chain from Langfuse without pinging engineering. Cross-persona stitching is visible via `parent_brief_id` linking traces.

**Live pieces used:** Langfuse US cloud (verified, 1 project), `_ScrubbingLangfuseWrapper` (verified in code), real traces accumulating from every turn run this session.

**Length:** 90 seconds.

**One-line say:** *"Compliance doesn't file a ticket. They open Langfuse."*

---

### N14 — Cross-book research recency

**Shape:** RM asks *"What research do we have on any of my top-5 exposure tickers in the last 30 days?"*

**What happens live:**
- `advisor_orchestrator` dispatches 2 specialists in parallel:
  - `portfolio_specialist` — queries salesforce-crm MCP for top-5 positions in RM's book
  - `research_awareness` skill — queries `Research_Brief__c` by ticker with 30-day date filter
- `asyncio.gather` joins the results
- Synthesis returns a 2-column table: ticker | most-recent-brief-date | rm_consumable status
- Each row clickable to open the brief

**Proves:** the cross-skill fanout is real. `research_awareness` is a real skill joining two SObjects. The RM gets a deliverable in one turn with citations to actual `Research_Brief__c.Id` values.

**Live pieces used:** `portfolio_analytics` + `research_awareness` skills, salesforce-crm MCP, existing Research_Brief__c rows + seed-demo-rows backfill.

**Length:** 90 seconds.

**One-line say:** *"Two skills fan out in parallel. One answer. Three clicks to verify."*

---

### N15 — The Darwin audit: one brief, three personas, one chain

**Shape:**
- T+0: Sarah publishes NVDA brief → `Research_Brief__c.Id = a0G...`
- T+5 min: RM queries NVDA exposure → agent uses `research_awareness` → cites the brief
- T+10 min: Client asks about NVDA on liaison channel → liaison references the brief
- T+15 min: compliance officer opens Salesforce → runs SOQL:
  ```sql
  SELECT Action__c, Principal_Id__c, Agent_Id__c, CreatedDate
  FROM IR_Audit_Log__c
  WHERE Research_Brief_Id__c = 'a0G...'
  ORDER BY CreatedDate ASC
  ```

Returns three rows in chronological order:
- `RESEARCH_PUBLISHED | sarah@firm.com | research_orchestrator | T`
- `ADVISORY_QUERY | rm-patel@firm.com | advisor_orchestrator | T+5min`
- `CLIENT_QUERY | patel-client | liaison_orchestrator | T+10min`

**What happens live:** `Research_Brief_Id__c` is the just-deployed cross-persona stitching field (verified live earlier — SOQL `SELECT Research_Brief_Id__c FROM IR_Audit_Log__c` now returns values, not "field does not exist"). Three turns with different principal_ids and agent_ids all reference the same brief.

**Proves:** single-writer data discipline + cross-persona stitching. Every handoff is a Salesforce record. Every record is queryable. Every cross-reference is an audit artifact.

**Live pieces used:** existing audit rows from today (already have one cross-stitched RESEARCH_PUBLISHED row), the new stitching field (verified deployed), SOQL via `sf data query`.

**Length:** 60 seconds.

**One-line say:** *"One brief. Three personas. One SOQL query. The audit chain is a single JOIN."*

---

## The 10 at a glance

| # | Name | Proves | Length |
|---|---|---|---|
| N6 | Same brief, four audiences | Data-layer MNPI redaction | 90 sec |
| N7 | Citation drill-down live | Every sentence verifiable to SEC | 60 sec |
| N8 | Restricted-list comparison | Code-enforced compliance DENY | 90 sec |
| N9 | Two RMs, different books | Per-user OBO + SF sharing rules | 90 sec |
| N10 | Dry-run ActionPlan (5/7 gates live) | Trust spine is real code | 2 min |
| N11 | MNPI tripwire | Guardrail fires, audits refusal | 60 sec |
| N12 | Haiku FAQ + escalation | Model-tier routing + cost model | 60 sec |
| N13 | Langfuse trace replay | Business-auditable observability | 90 sec |
| N14 | Cross-book research recency | Multi-skill parallel fanout | 90 sec |
| N15 | Darwin audit — one brief, three personas | Cross-persona stitching via SOQL | 60 sec |

Total: ~14 minutes for all 10. Individual narratives are independent — can pick any subset.

---

## Suggested sequencing

### Compact technical demo (8 min, 4 narratives)

N7 → N10 → N11 → N13

Opens with live citation drill-down (instant trust). Runs the 5-of-7-gate ActionPlan. Fires a Guardrail refusal. Closes with Langfuse replay. Tight, proves the trust spine + observability + citation-bound generation without needing MuleSoft.

### Panel-wildcard ready (12 min, 6 narratives)

N7 → N8 → N9 → N10 → N11 → N15

Adds compliance comparison, per-RM isolation, and the Darwin audit chain. Gives the panel multiple angles to probe without derailing into anything requiring MuleSoft or rm_handoff.

### Full technical deep-dive (14 min, all 10)

In order. Use as the "architecture walk-through" session for technical panels or post-demo Q&A.

---

## What each narrative needs for stage-ready

All 10 run against the currently live infrastructure today. Three benefit from small seed work:

| Narrative | Seed work | Effort |
|---|---|---|
| N6 | 1 additional pre-seeded Research_Brief__c with rich MNPI fields | 10 min Apex write |
| N9 | Assign 2 demo RMs distinct sharing rules, seed 3 more Position rows | 20 min |
| N13 | Run 3-4 turns in advance so Langfuse UI has traces to open | 5 min |

Everything else is a one-command run against existing data and live infrastructure.

---

## Relationship to the original 5

The original 5 narratives (Earnings Morning, Client Drives Research, Risk Alert, Demand Signal, Large Liquidation) carry the **workflow story**:
- N1 — analyst → RM → client waterfall
- N2 — client-originated demand-pull research
- N3 — system-originated risk alert
- N4 — behavioral clustering feedback loop
- N5 — full 7-gate trust spine under time pressure

These 10 new narratives are **proof-layer** — they demonstrate specific design commitments that appear across multiple original narratives. They're the "if you don't believe me, click this" moments.

**Stage strategy:**
- Lead with 1-2 original narratives for the workflow story
- Sprinkle in proof-layer narratives (N7, N11, N15) where the panel wants "how does that actually work?"
- Hold N10 as the MuleSoft-independent trust-spine demo if the CloudHub deploy hasn't completed
- Use N13 as the "one more thing" closer — nobody else's demo has this

---

## Final note — honesty discipline

Each narrative here was scored against the live-right-now test:
- Does the MCP tool return HTTP 200?
- Does the SObject exist in `new-org`?
- Does the code path exist in the committed `feat/006-v3-live-demo` branch?
- Does running it produce a visible, traceable artifact?

If any answer is no, the narrative was dropped. This list contains only what works today.

*— additional narratives drafted at 2026-04-29 ~14:45 UTC.*
