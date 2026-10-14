# 006 V3 — Narrative Arc (Simplified)

> **Audience:** exec panel, Salesforce stakeholders, internal steering committee
> **Purpose:** the demo story for V3. Workflow 360 — research → advisory → client → settled trade, one runtime, fully audited.
> **Date:** April 2026
> **Status:** narrative locked; build plan next.
>
> **Scope discipline:** this doc defines V3 only. Versions 001 through 006 V2 are frozen as-is. Nothing in those trees changes.

---

## V3 Architecture Discipline — One of Everything

V3 is a deliberate simplification. Four agent runtimes across 005 and 006 V2 become one. The 23-stage research pipeline becomes a single-shot tool-use call. The write layer narrows to what MuleSoft is actually for.

| Concern | V3 choice |
|---|---|
| Agent runtime | **OpenClaw on AgentCore** — the only runtime |
| LLM | **Bedrock:** Sonnet 4.6 for reasoning, Haiku 4.5 for routing |
| Research approach | **Single-shot tool-use** — one LLM turn, parallel MCP calls. No pipeline. |
| Tool protocol | **MCP** — read-path and CRM-path both |
| Write path | **MuleSoft Process APIs** — single choke point via `mulesoft-api` skill |
| Data platform | **Salesforce** — system of record and audit sink |
| Trust spine | Guardrails → MNPI filter → HITL → dual-auth → audit (one order, every write) |
| Personas | **Three, one runtime** — `fsi-research` (Sarah), `fsi-advisor` (RM), `fsi-client-liaison` (client, read-only + RM-gated) |

**Explicitly not in V3:** Agentforce agent, Strands sub-agents, LangGraph, AutoResearchClaw pipeline, internal HITL gates inside reasoning, MuleSoft for KYC / account lifecycle / corporate actions.

---

## The Depth Layer — Principal-Level Architecture

Seven dimensions where V3 deliberately goes deeper than "good enough." Each is the thing a junior team would get wrong in week two and spend month three fixing. The simple outside runs on top of each one of these.

### 1. RAG — 2026 discipline, not 2023 stuffing

Two corpora (research + filings) with different trust models. Hybrid retrieval: BM25 lexical (keeps ticker/cusip honest — "GS" vs "Goldman Sachs Group" breaks pure-semantic retrieval), dense Bedrock Titan v2 embeddings (semantic recall), section-aware structural retrieval over SEC filings (Item 1A Risk Factors, Item 7 MD&A, financial statement tables — parsed from XBRL, not token-chunked). Cohere Rerank 3.5 collapses top-30 to top-5. Sonnet 4.6 generates under a citation-enforcement harness — every sentence in the brief cites a source chunk ID; unsourced sentences are truncated server-side before UI render. Storage split: Bedrock Knowledge Bases (managed, OpenSearch Serverless) for filings; Aurora PostgreSQL with `pgvector` for research corpus (because research access needs tight ACL integration with Salesforce sharing rules, which BKB can't express).

### 2. Interactive charts — citation-bound, not LLM-drawn

The LLM never emits numbers. It emits structured chart intent: `{chart_type, source_id, highlight_segments}`. A deterministic renderer (React + Visx) loads the parsed table by source ID and renders. Every chart element is clickable: hover → source citation (filing URL + page + table number); click bar → drill into the underlying line item; toggle segments → the query can reframe the prose to match the RM's focus. Multimodal input on Sarah's screen: drag-drop a PDF filing onto the terminal → Textract extraction → structural parse into the filings corpus → immediately queryable in the brief being composed.

### 3. Financial statement analysis — deterministic math, LLM orchestration

Canonical financial statements model in Pydantic: `Income_Statement`, `Balance_Sheet`, `Cash_Flow`, normalized from XBRL to GAAP line items. Pure-Python calculators for growth rates, margins, ROE/ROIC/ROA, common-size statements, DCF with sensitivity, Monte Carlo valuation (10K paths over assumption distributions), Altman Z-score, Piotroski F-score, Beneish M-score, peer-comparison matrices. Sonnet 4.6 decides *which* analyses to run and *how* to narrate them; it never computes. Tool contract example:

```
financial-statement-analysis.compare_peers(
  tickers=["NVDA", "AMD", "AVGO"],
  metrics=["gross_margin_trend_5y", "rd_intensity", "roic"],
  as_of="2026-02-25"
)
```

Numbers in the brief are identical to numbers a junior analyst would hand-compute from the 10-Q, because they're computed from the 10-Q.

### 4. Langfuse — business-auditable, not dev-debuggable

Disciplined span taxonomy:

```
session ("Sarah earnings morning")
  └── turn ("Research NVDA ahead of earnings")
       └── persona:fsi-research
            └── skill:single-shot-research-prompt
                 ├── tool_call:market-data.get_quote
                 ├── tool_call:sec-edgar.get_latest_10q
                 ├── tool_call:news-search.sentiment_30d
                 ├── tool_call:compliance-screening.check
                 ├── rag_retrieve (3 retrievers + reranker, each a child span)
                 └── llm_call:claude-sonnet-4.6
```

Cross-persona session stitching: RM's turn carries a `parent_brief_id` linking to Sarah's originating trace; a client trade trace chains back through RM's read-of-brief → Sarah's turn → filings retrieval. Cost attribution dashboards by persona, user, skill. LLM-as-judge nightly evals on held-out queries. PII/MNPI scrubbing before span write (steering rule 22). Trace replay as audit artifact — a compliance officer can replay any decision chain from Langfuse.

### 5. Hybrid data layer — Salesforce + AWS, single-writer discipline

The failure mode a junior team creates: two databases, bidirectional sync, race conditions in month two. V3 avoids this by hard single-writer discipline.

| Data | Single writer | Read-locations |
|---|---|---|
| Client PII, positions, households, sharing rules | Salesforce FSC | SF + AWS (via principal-scoped CRM MCP) |
| Research briefs, client inquiries, audit log, pending approvals | Salesforce (written by agent skills) | SF + AWS |
| Research corpus + filings embeddings | AWS Aurora + Bedrock KB | AWS only |
| Live market data, news, sentiment | None (stateless cache from vendor) | AWS ephemeral |
| ActionPlans, HITL tokens, seven-gate state | AWS DynamoDB with TTL | AWS only |

Canonical key discipline: Salesforce 18-char IDs propagate into Bedrock KB document metadata, Aurora foreign keys, DynamoDB partition keys, and Langfuse trace attributes. Change Data Capture one direction only — Salesforce Platform Event → EventBridge → Aurora/BKB indexer re-embeds and re-stores on brief publish or position update. AWS never writes back to Salesforce for state, only for audit.

Latency budget, enforced in the audit strip: SF reads 200–400ms, AWS reads 100–300ms, combined in-agent turn under 1s for read-path, under 3s for write-path including HITL.

### 6. UI — simple outside, complex inside

**Simple outside (user-visible):**

- Single query input per persona. No mode selector, no dropdown of skills, no template chooser. The agent decides which skills to call.
- One conversation view. Queues collapse to a single sidebar. Context panel appears only when there's context; disappears when there isn't.
- Client has one message thread. Nothing else.
- Streaming everywhere. No spinner longer than 500ms. If the model is thinking, the audit strip shows which tool is in flight.
- Every action has one primary button, at most one secondary. No menus for primary actions.
- Progressive disclosure. Citation chips → source chunk in 1 click. Chart number → underlying table in 1 click. Table cell → filing page in 1 click. Depth is always one click away, never two for the main flow.

**Complex inside (what's happening behind the simple surface):**

- **Optimistic UI with rollback.** HITL approval updates UI instantly; backend validation catches up async; inline toast rolls back on failure.
- **Two parallel streams, one document.** Brief Markdown streams from Sonnet on channel 1; citation chip data streams from the retriever on channel 2; stitched into the Markdown by span ID at render time. Juniors ship "wait-then-render"; seniors ship parallel streams.
- **Skeleton states that inform.** Pending tool-call chip shows a labeled pulsing skeleton ("sec-edgar…"), never a generic spinner. User sees exactly what's happening.
- **Deterministic fallbacks at every LLM boundary.** If Sonnet fails to produce chart intent → UI renders tabular fallback with raw data. If citation-chip channel times out → UI shows the brief without chips but marks "citations pending." Never a broken state.
- **Keyboard-first for Sarah.** Cmd-K command palette, arrow keys for citation navigation, Cmd-Enter submit, `/` for new query. Analysts work in keyboard; the interface respects that.
- **Intent-driven prefetch.** User types "NVDA" → system starts prefetching NVDA's latest filing, quote, news in parallel before the user finishes typing. By Enter, half the tools are warm.
- **Trace-driven UX events.** One backend event fan-out → concurrent UI effects (brief text update, chart render, audit strip update, side panel update). Coordinated via a single event bus, not ad-hoc listeners.
- **Four-tier error handling.** Transient (retry silently), degraded (show what we have with a "limited data" marker), recoverable (retry button with context), fatal (preserve user input + full fallback). Juniors ship one tier; V3 ships four.
- **Accessibility from the start.** Keyboard navigation, screen-reader labels, WCAG AA contrast, `prefers-reduced-motion` respected. Not retrofitted.

**The test:** a junior dev reading the UI code for two weeks could not reproduce the streaming coalescence, the deterministic fallbacks, the intent prefetch, or the event-bus coordination — even though the result on screen looks like "a chat." That gap is where Principal-level design lives.

### 7. Multi-agent discipline — true multi-agent, not persona switching

V3 is a **true multi-agent system**, not a single-agent system with a costume change per persona. Three personas, 17 distinct sub-agents, orchestrator-workers pattern throughout.

**Topology per persona:**

```
fsi-research (Sarah) — 6 agents
  ├── research-orchestrator        (plans, fans out, synthesizes)
  ├── market-specialist            (quote, volume, technicals)
  ├── filings-specialist           (10-Q/10-K retrieval + section-aware RAG)
  ├── sentiment-specialist         (30-day news + Bedrock sentiment)
  ├── compliance-specialist        (restricted list + MNPI)
  └── statement-specialist         (deterministic financial math)

fsi-advisor (RM) — 5 agents
  ├── advisor-orchestrator         (intent classification, routing)
  ├── portfolio-specialist         (portfolio-analytics + scenario-modeling)
  ├── suitability-specialist       (suitability-check)
  ├── client-context-specialist    (client-summary + CRM reads)
  └── action-specialist            (HITL, dual-auth, mulesoft-api — serial by design)

fsi-client-liaison (Client) — 3 agents
  ├── liaison-orchestrator         (FAQ-vs-escalation decision)
  ├── faq-specialist               (Haiku 4.5, bounded answers)
  └── context-specialist           (MNPI-filtered CRM reads)
```

Each sub-agent is Sonnet 4.6 (Haiku 4.5 for the FAQ-specialist) with a narrowed system prompt, narrowed tool allowlist, narrowed memory. Orchestrators run `asyncio.gather` on their workers where the work is parallelizable.

**The performance delta this buys:**

| Operation | Single-agent | Multi-agent (V3) |
|---|---|---|
| Research brief (4 parallel data sources) | 40s | 12–15s |
| RM query with portfolio + suitability + context | 12s | 4–5s |
| Client FAQ (Haiku only) | 2s | 2s |

Sarah's brief in 15 seconds is the difference between "impressive" and "shocking" in a live demo. The four Sonnet-4.6 worker calls inside her turn run in parallel — visible in the audit strip as four concurrent spans, not a serial waterfall. The panel sees parallelism on screen.

**What OpenClaw does (its actual role in V3):**

OpenClaw is the **agent platform**, not "the agent." Three responsibilities, cleanly separated:

1. **Agent lifecycle & orchestration.** Instantiates sub-agents per session, routes messages between orchestrator and workers, enforces per-agent skill allowlists, manages per-agent session memory. The orchestrator-workers pattern is OpenClaw-native — not application-level glue we wrote.
2. **Trust enforcement at the runtime boundary.** Every sub-agent inherits its persona's trust policy: allowed skills, allowed MCP servers, MNPI filters, HITL requirements. OpenClaw enforces this fail-closed at skill-invocation time. A junior team puts this in application code; OpenClaw puts it in the runtime where it can't be accidentally bypassed.
3. **Cross-agent coordination primitives.** Parallel fanout via `asyncio.gather`, schema-validated agent-to-agent message passing, fan-in synthesis helpers, shared scratchpad within a session, structured error propagation across agents. Without these, multi-agent becomes a mess of ad-hoc async code.

**What OpenClaw does NOT do** (equally important):

- It does not call Bedrock directly. Sub-agents do.
- It does not decide tool calls. Sub-agents do.
- It does not generate text. Sub-agents do.
- It does not hold business logic. Skills do.

OpenClaw is the scaffolding. The sub-agents are the reasoning. The skills are the business logic. Clean separation — each layer auditable, each layer swappable.

**Why the action-specialist is serial, not parallel.** The regulated write path (compliance → HITL → dual-auth → MuleSoft → audit) must be sequential by design. Gates cannot fire in parallel without violating the trust spine. Multi-agent parallelism is a read-path optimization, never a write-path one. A junior would try to parallelize the write path to "make it faster" and break the audit guarantees. V3 doesn't.

**The test:** a junior team given "build a multi-agent wealth platform in 2 weeks" would build a single-agent chatbot with three system prompts and call it multi-agent. V3 has 17 agents, a defined orchestrator-workers topology per persona, OpenClaw-enforced trust isolation between agents, and measurable parallelism visible in every trace. That's the difference.

---

## Architecture on One Slide

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ENTERPRISE IdP (Okta)                           │
│              OAuth 2.0 PKCE → principal_id + role claim                 │
└──────────────┬──────────────────┬──────────────────┬───────────────────┘
               │                  │                  │
       ┌───────▼────────┐ ┌───────▼────────┐ ┌──────▼─────────┐
       │   SARAH        │ │    RM          │ │   CLIENT       │
       │   (analyst)    │ │    (advisor)   │ │   (end-user)   │
       │                │ │                │ │                │
       │ Web / Slack    │ │ Web / SF Mobile│ │ WhatsApp /     │
       │                │ │ / Slack        │ │ WeChat / SMS   │
       └───────┬────────┘ └───────┬────────┘ └──────┬─────────┘
               │                  │                  │
               ▼                  ▼                  ▼
       ┌───────────────────────────────────────────────────────┐
       │         CHANNEL ADAPTERS (per channel)                │
       │  Signature verify → mint AgentCore session token      │
       │  Attach: principal_id + persona + channel + client_id │
       └───────────────────────────┬───────────────────────────┘
                                   │
                                   ▼
       ┌───────────────────────────────────────────────────────┐
       │        OpenClaw on Bedrock AgentCore (us-east-1)      │
       │  The agent PLATFORM — lifecycle, trust, coordination  │
       │  Sonnet 4.6 (reasoning) + Haiku 4.5 (FAQ specialist)  │
       │  Bedrock Guardrails on LLM input                      │
       │                                                        │
       │  Multi-agent topology (17 agents, 3 personas):        │
       │                                                        │
       │    ┌──────────────────────────────────────────┐       │
       │    │  fsi-research (Sarah)  — 6 agents         │       │
       │    │   research-orchestrator                   │       │
       │    │    ├─ market-specialist                   │       │
       │    │    ├─ filings-specialist  (RAG)           │       │
       │    │    ├─ sentiment-specialist                │       │
       │    │    ├─ compliance-specialist               │       │
       │    │    └─ statement-specialist  (XBRL math)   │       │
       │    │   ⇒ asyncio.gather → 15s briefs (vs 40s)  │       │
       │    └──────────────────────────────────────────┘       │
       │                                                        │
       │    ┌──────────────────────────────────────────┐       │
       │    │  fsi-advisor (RM)  — 5 agents             │       │
       │    │   advisor-orchestrator                    │       │
       │    │    ├─ portfolio-specialist                │       │
       │    │    ├─ suitability-specialist              │       │
       │    │    ├─ client-context-specialist           │       │
       │    │    └─ action-specialist  (SERIAL BY      │       │
       │    │         DESIGN: HITL→dual-auth→MuleSoft) │       │
       │    └──────────────────────────────────────────┘       │
       │                                                        │
       │    ┌──────────────────────────────────────────┐       │
       │    │  fsi-client-liaison (Client)  — 3 agents  │       │
       │    │   liaison-orchestrator                    │       │
       │    │    ├─ faq-specialist  (Haiku 4.5)         │       │
       │    │    └─ context-specialist  (MNPI-filtered) │       │
       │    └──────────────────────────────────────────┘       │
       │                                                        │
       │  Skills (16): research-prompt, publish-brief,         │
       │    rag-retrieve, financial-statement-analysis,        │
       │    portfolio-analytics, scenario-modeling,            │
       │    suitability-check, client-summary,                 │
       │    research-awareness, compliance-screening,          │
       │    hitl, dual-auth, audit-logging,                    │
       │    mulesoft-api  ◀── single write choke point         │
       │                                                        │
       │  AgentCore session memory (per user+persona)          │
       │  AgentCore user memory   (per user, long-lived)       │
       └────────────┬─────────────────┬─────────────────────────┘
                    │                 │
         reads      │                 │  writes (HITL + dual-auth gated)
                    ▼                 ▼
          ┌──────────────┐     ┌─────────────┐
          │  MCP servers │     │  MuleSoft   │
          │  (read-path) │     │ Process APIs│
          │              │     │             │
          │ market-data  │     │ submit-ord  │
          │ sec-edgar    │     │ cancel-ord  │
          │ news-search  │     │ modify-ord  │
          │              │     │ order-hook  │
          │              │     │ initiate-   │
          │              │     │  wire       │
          └──────┬───────┘     └──────┬──────┘
                 │                    │
   Finnhub, EDGAR, Tavily       Alpaca paper,
                 │              Dwolla sandbox, OFAC
                 │                    │
                 └──────────┬─────────┘
                            │
                            ▼
       ┌────────────────────────────────────────────────────┐
       │        SALESFORCE (system of record + exchange)    │
       │   Via salesforce-crm MCP + SF Auth Proxy (OBO)     │
       │                                                    │
       │  The EXCHANGE between personas:                    │
       │                                                    │
       │   Research_Brief__c       ← Sarah writes           │
       │                           ← RM reads (DLM join)    │
       │                           ← Client sees summary    │
       │                             only (MNPI-stripped)   │
       │                                                    │
       │   Client_Inquiry__c       ← Client writes          │
       │                           ← RM sees queue          │
       │                                                    │
       │   Research_Request__c     ← RM → Sarah queue       │
       │                                                    │
       │   Research_Suggestion__c  ← System (demand-signal) │
       │                             → Sarah queue          │
       │                                                    │
       │   Client_Alert__c         ← System (compliance-    │
       │                             sweep) → RM queue      │
       │                                                    │
       │   IR_Audit_Log__c         ← ALL personas write.    │
       │                             Cross-stitched via     │
       │                             principal_id +         │
       │                             research_brief_id +    │
       │                             client_contact_id +    │
       │                             linked_trade_id +      │
       │                             linked_wire_id         │
       │                                                    │
       │   IR_Pending_Approval__c  ← dual-auth queue        │
       │                                                    │
       │  FSC sharing rules enforce WHO SEES WHAT.          │
       └────────────────────────────────────────────────────┘
```

**Key insight:** three personas, three entry channels, one runtime, **zero direct agent-to-agent communication.** Every cross-persona interaction lands in a Salesforce SObject. The SObject is the handshake. That's what makes it auditable, gated by sharing rules, and replayable.

**The third persona is deliberately constrained.** `fsi-client-liaison` has read-only skills and a single escape hatch — `rm-handoff` — that queues anything non-trivial for RM review. No autonomous client-to-trade path. Clients never see raw MNPI, raw positions, or raw research content.

One runtime. One decision surface. One protocol for tools. One choke point for writes. One system of record. One IdP.

---

## Where V3 Runs

**Choice: Bedrock AgentCore, us-east-1, single deployment, two persona configs.**

Evaluated alternatives:

| Option | Cost | Pro | Con | Verdict |
|---|---|---|---|---|
| Bedrock AgentCore | $0.03–0.10/session | Managed session + streaming + checkpointing APIs; scales to zero; matches V2 | Preview-era APIs; region-bound | **Chosen** |
| ECS Fargate | ~$30–50/mo baseline + per-use | Stable, warm, full control | Pay for idle; need ALB + self-built session store | Rejected — surface area too high for one demo |
| Lambda + WebSocket API Gateway | Minimal at demo scale | Cheap, scales to zero | 3–5s cold start kills live demo; 15-min hard timeout breaks HITL waits | Rejected — demo risk |

**Why AgentCore specifically:**

- Sarah's single-shot research is 20–40s with tool use. AgentCore's managed streaming APIs remove ~400 lines of plumbing.
- Query 3 is a multi-skill sequence (compliance → HITL → MuleSoft submit → webhook wait → MuleSoft wire → audit). AgentCore's built-in session checkpointing lets the session survive the HITL wait without us building a Redis state store.
- One reserved warm instance for the demo eliminates cold-start risk. Total demo-day cost: <$5.

**Single deployment, two persona configs.** Same Docker image, same AgentCore agent ID, two entry configs in `agentcore-config.yaml`. Persona selected at session-open time by an `X-Persona` header set by the channel adapter. The `fsi-research` config has its own system prompt + skill allowlist + channel defaults; `fsi-advisor` has its own. Nothing forks at the container layer.

**Region layout (matches V2):**
- Bedrock + AgentCore + Guardrails: **us-east-1**
- MCP server Lambdas + VPC + NAT: **us-east-2**
- Salesforce: multi-tenant (org-pinned)
- MuleSoft CloudHub 2.0: **us-east-2**

---

## State Model — Four Layers, One Rule

"Shared memory" is overloaded. V3 separates state into four distinct layers with different lifetimes, storage, and sharing rules.

| Layer | What it is | Lifetime | Where it lives | Shared across personas? |
|---|---|---|---|---|
| **Session memory** | Turn-by-turn conversation within one user's session | Minutes to hours | AgentCore session store | No — per-user, per-persona |
| **User memory** | Persistent user-specific context (Sarah's sector preferences, RM's book scope, saved defaults) | Weeks+ | AgentCore Memory API, keyed by principal_id | No — per-user |
| **Artifact memory** | The research brief Sarah published; the trade ActionPlan | Forever | Salesforce `Research_Brief__c`, `IR_Audit_Log__c` | **Yes — this is the cross-persona handoff** |
| **Audit memory** | Everything that happened, immutable | Forever | Salesforce `IR_Audit_Log__c` + Langfuse traces | Yes (read via permset) |

**The rule — one sentence:**

> **Agent memory is per-user per-persona. Cross-persona state exchange goes through Salesforce SObjects. No shared agent memory bus.**

Why this matters:

- If Sarah's brief lived in AgentCore memory, the RM couldn't query it with SOQL, compliance couldn't audit it, Data Cloud sharing rules couldn't gate it, and it would vanish when the session expired.
- `Research_Brief__c` makes the brief a first-class entity: queryable, joinable to Position/Client, indexed in Data Cloud DLMs, audited on every read, gated by FSC sharing rules.
- `publish-brief` skill writes it. `research-awareness` skill reads it. The agents never "talk to each other" directly. Salesforce is the exchange.

What V3 explicitly does NOT use:

- Cross-user memory ("what are other analysts researching") — that's a dashboard, not agent memory
- Cross-session LLM output cache — premature optimization, sentiment shifts by the minute
- A vector store — V3's four sources (Finnhub, EDGAR, Tavily, CRM) are structured and narrow; nothing needs RAG
- Inter-agent message bus — Salesforce is the bus

User memory write rules:

- Skills write user memory explicitly with clear keys (`sarah.preferred_sectors`, `rm.book_id`).
- The agent loop never auto-absorbs conversation turns into user memory (MNPI leakage risk).
- MNPI-tagged content cannot be written to user memory — `publish-brief` and `audit-logging` skills enforce this.

---

## Auth Model — Six Boundaries

Six distinct auth boundaries in V3. Each uses a different mechanism because each protects a different thing.

### Boundary 1 — User → Channel → AgentCore

- **Web frontend:** OAuth 2.0 PKCE against enterprise IdP (Okta or Azure AD). Frontend receives ID token + access token.
- **Slack / WhatsApp / SF Mobile:** channel's native auth → channel adapter validates signature → adapter mints a short-lived AgentCore session token bound to `principal_id` (looked up from IdP by Slack handle / phone number / SF user id).
- Every WebSocket to AgentCore carries: `Authorization: Bearer <agentcore_session_token>` + `X-Persona: fsi-research | fsi-advisor`.
- AgentCore validates the session token, extracts principal_id + persona claims, starts a session.

### Boundary 2 — Persona → Skill allowlist

- `openclaw.json` lists allowed skills per persona. Fail-closed: skill not in allowlist → OpenClaw rejects + audit row.
- `fsi-research` can call: market-data, sec-edgar, news-search, compliance-screening, publish-brief, audit-logging.
- `fsi-advisor` can call: salesforce-crm, research-awareness, compliance-screening, hitl, dual-auth, mulesoft-api, audit-logging.
- Persona cannot escalate between personas within a session.

### Boundary 3 — Agent → MCP server

- Every MCP call carries: `X-MCP-API-Key` (per-server static, authn) + `X-Principal-Id` (user identity from AgentCore) + `X-Persona` + `X-Session-Id`.
- MCP server validates API key (authn: "is this really the agent runtime talking?").
- MCP server enforces persona-scoped tool availability (authz: "is this persona allowed to call this tool on this server?"). Example: `salesforce-crm` MCP exposes `write_research_brief` only to `fsi-research`, `read_research_brief` only to `fsi-advisor`.
- `X-Principal-Id` flows downstream for data-layer authz.

### Boundary 4 — MCP server → Salesforce (per-user)

- Critical: the CRM MCP does NOT use a long-lived service account token. That would flatten all users into one identity and break FSC sharing rules.
- Instead: **SF Auth Proxy Lambda** performs OAuth On-Behalf-Of using principal_id + a firm-wide OAuth client-credentials bootstrap. Result: a short-lived SF session token scoped to THAT user.
- CRM MCP uses that token for every read/write. Salesforce enforces sharing rules natively: the RM sees only their book, compliance sees everyone, Sarah sees what analyst role allows.
- Token cached 2h, refreshed automatically.

### Boundary 5 — Agent → MuleSoft

- `mulesoft-api` skill → MuleSoft MCP server → Anypoint Process API.
- Anypoint auth: **client-credentials grant** from Lambda's Anypoint Connected App (creds in Secrets Manager). This identifies the SYSTEM (the agent runtime), not the user.
- The user's identity flows as `X-Principal-Id` header into the Process API — captured in Anypoint's audit, passed through to `IR_Audit_Log__c.Approved_By__c`.
- Policy stack on each Process API: rate-limit (per client_id) + client-id enforcement + JSON threat protection + IP allowlist (to Lambda NAT EIP).

### Boundary 6 — Data-layer authz wall

This is the most important and the V2 docs underspecify it.

- Every MCP call, every Salesforce read/write, every MuleSoft call carries `principal_id`.
- Every data system enforces its OWN authz using that principal_id:
  - **Salesforce:** sharing rules, OWD, field-level security, permission sets (e.g., `Senior_Compliance_Approver` gates the dual-auth second-signer path)
  - **MuleSoft:** audit-only (no data-level authz — by design; the structured ActionPlan carries all authz context, and Salesforce is the gate)
  - **Langfuse:** trace sink, access via Langfuse RBAC
- **Nothing** about authz is computed in the agent runtime beyond "can this persona call this skill." All real data-level decisions are delegated downstream to the systems of record. This is V3's fail-closed principle.

### Special case — HITL and dual-auth

- HITL approval token: minted by AgentCore session (user's identity, plan_hash, HMAC-SHA256, 5-min TTL, single-use).
- Dual-auth second approver: `dual-auth` skill verifies against Salesforce `IR_Pending_Approval__c` — the approver_id must hold `Senior_Compliance_Approver` permset (Salesforce enforces) AND must be distinct from the first approver (skill enforces).
- Second approval is its own signed token, its own audit row, its own session. Two independent trust hops — not one relay.

---

## Secrets Inventory (V3)

Zero credentials in git. All values in AWS Secrets Manager, seeded from gitignored `.env` via `scripts/seed-secrets.sh`.

| Secret name | Purpose | Rotation |
|---|---|---|
| `/006-v3/auth/oauth-config` | IdP client_id + client_secret for user OAuth | IdP-driven |
| `/006-v3/agentcore/session-signing-key` | HMAC key for AgentCore session tokens | Quarterly |
| `/006-v3/mcp/<server-name>/api-key` | Per-MCP-server static key | Quarterly |
| `/006-v3/sf/bootstrap-creds` | Firm-wide OAuth client for SF Auth Proxy OBO | Yearly |
| `/006-v3/mulesoft/connected-app` | Anypoint client_id + secret for Lambda | Quarterly |
| `/006-v3/hitl/signing-key` | HMAC key for approval tokens | Monthly |
| `/006-v3/vendors/alpaca` | Alpaca paper creds (live in CloudHub Secure Properties at runtime) | Yearly |
| `/006-v3/vendors/dwolla` | Dwolla sandbox creds | Yearly |
| `/006-v3/vendors/finnhub` | Finnhub read-only key | Quarterly |
| `/006-v3/vendors/tavily` | Tavily API key | Quarterly |
| `/006-v3/langfuse/keys` | Langfuse public + secret keys | Yearly |

Rotation automated where possible; operator-run `scripts/rotate-secret.sh <name>` where not.

---

## The Moment

> "It's 6:45 AM Singapore. NVDA earnings drop in 73 minutes. Sarah has 12 positions to review, 3 restricted-list flags to clear, compliance sign-off to get, and a brief to land in front of 8 RMs before market open. This is her every earnings morning. This is what 006 V3 transforms."

---

## The Three Acts

### Act 1 — Sarah runs 006 *(analyst, 6:45 AM)*

One query. One LLM turn with tool use. Twenty to forty seconds of processing. Brief published by 7:08 AM.

> **Query 1:** `Research NVDA ahead of earnings. Pull latest 10-Q risk factors, score sentiment on last 30 days news, check restricted list, flag any MNPI exposure. Brief for RM consumption.`

What happens inside OpenClaw `fsi-research`:

- Bedrock Guardrails screens the input (no bypass language, no HITL-skip attempts)
- Sonnet 4.6 plans one reasoning turn and calls four MCP tools in parallel:
  - `market-data` → Finnhub direct for live NVDA quote
  - `sec-edgar` → 10-Q risk factors direct from EDGAR
  - `news-search` → 30-day sentiment via Tavily
  - `compliance-screening` skill → restricted list + MNPI scan
- Results return. Sonnet 4.6 composes the brief: thesis, sentiment score, risk highlights, compliance status, cited sources
- `publish-brief` skill writes canonical `Research_Brief__c` to Salesforce via `salesforce-crm` MCP, with `rm_consumable = true` and ticker/sentiment/risk indexing
- `audit-logging` skill writes `IR_Audit_Log__c` row with `Action__c = RESEARCH_PUBLISHED`, research_brief_id, originating_query_id
- Langfuse trace captures the full turn + all tool calls + token counts

Sarah gets a compliance-cleared, audit-logged, RM-ready brief at **7:08 AM**. Cost per brief: ~$0.05–$0.15 at Sonnet 4.6 rates.

*No MuleSoft in Act 1. Reads are reads.*

---

### Act 2 — The RM opens Salesforce *(8 RMs, 7:15 AM)*

Same OpenClaw runtime. Different persona: `fsi-advisor`. Different system prompt, different skill allowlist, same trust spine, same audit path.

> **Query 2** *(as RM)*: `Which of my clients have NVDA exposure above 5% and haven't been contacted in 7 days?`

What happens inside OpenClaw `fsi-advisor`:

- Sonnet 4.6 recognizes this as a research-aware advisory query
- Calls `research-awareness` skill → `salesforce-crm` MCP → Data Cloud DLM query
- DLM join: `Research_Brief__c ↔ Position ↔ Client ↔ Contact.LastActivityDate`, filtered by RM's book (sharing rules enforced at MCP boundary)
- Returns prioritized call list with **inline citation of Sarah's 7:08 AM brief** — thesis, sentiment score, risk highlights
- Next-best-action: call before 10 AM, volatility framing, suitability-aware talking points
- MNPI filter applied to everything that crossed from CRM into the agent's context
- `audit-logging` skill writes `IR_Audit_Log__c` with `Action__c = ADVISORY_QUERY`, research_brief_id linkage, client_contact_id references

*Still no MuleSoft. This is read-path through Salesforce.*

---

### Act 3 — The Client, then the trade *(9:00 AM WeChat → 9:07 AM settled)*

The client message:

> "My friend says NVDA is down pre-market. Should I be worried?"

The RM responds in 3 minutes with a suitability-checked answer — Sarah's brief was already there at 7:08. Client decides: "Sell half. Wire proceeds to my HSBC Singapore settlement account."

**This is where MuleSoft earns its keep.** Two regulated state changes, one audit trail, one canonical contract.

> **Query 3** *(as RM, panel wildcard)*: `Sell 150 NVDA from Patel household, wire proceeds to HSBC Singapore settlement.`

What happens inside OpenClaw `fsi-advisor`:

- Sonnet 4.6 builds a structured `ActionPlan` — ticker, quantity, account, wire destination, notional $24,300
- `compliance-screening` skill runs: restricted list clean, trading window open, MNPI clean, concentration check passes → **ALLOW**
- `hitl` skill fires on the RM's screen — ActionPlan summary, [Approve] / [Reject], 5-min TTL
- RM clicks Approve. HMAC-SHA256 token minted, bound to `plan_hash`
- `dual-auth` skill: $24K notional < $500K trade threshold AND < $100K wire threshold → **skip** (check runs and logs the decision either way)
- `mulesoft-api` skill → MCP tool call → **MuleSoft `submit-order` flow** (Anypoint) → Alpaca paper → order filled `ALPACA-7f2a`
- Fill webhook hits MuleSoft **`order-status-webhook` flow** → fans out: `Position__c` updated in Salesforce, Langfuse trace closed, RM gets Slack notification
- `mulesoft-api` skill → **MuleSoft `initiate-wire` flow** (Anypoint) → OFAC SDN screening on HSBC Singapore beneficiary → screening clean → Dwolla sandbox wire initiated → ref `WIRE-91c4`
- Triple audit: `IR_Audit_Log__c` writes `TRADE_SUBMITTED` + `WIRE_INITIATED` (both linked to the originating research_brief_id), `IR_Pending_Approval__c` unused (no dual-auth), Langfuse captures the full multi-skill trace
- RM sees: *"Order filled at $162.15. Wire $24,322.50 initiated to HSBC SG. OFAC clean. Ref MS-TRD-7f2a / MS-WIRE-91c4. Settles T+1."*

*Settled by 9:07 AM. Three regulated hops, one audit trail, one runtime.*

---

## The Transformation Statement

> "Without this: Sarah's brief lands at noon. RMs fly blind on the open. Clients get a callback tomorrow, a trade the day after, a wire three days later with the compliance officer reconciling it Friday. With this: the research-to-client-to-settled-trade loop closes in 2 hours 22 minutes, fully audited, zero compliance exceptions, one agent runtime, one system of record, with the regulated state changes gated behind MuleSoft where compliance officers expect them. That's not efficiency. That's a different category of service."

---

## The Five Demo Narratives

Five shapes of interaction across Sarah, RM, and Client. Each is a complete story in under 2 minutes live. Each exercises a different direction of flow. The panel never sees the same shape twice.

Narrative 1 is "The Three Acts" above, told end-to-end. The other four show the same platform handling different originators and different flows.

### Narrative 1 — The Earnings Morning *(analyst → RM → client)*

*See "The Three Acts" above.* Research flows downhill.

- **6:45 AM** Sarah: `Research NVDA ahead of earnings.` Brief published by 7:08.
- **7:15 AM** RM: `Which of my clients have NVDA exposure above 5%?` Call list with Sarah's thesis inline.
- **9:00 AM** Client (WhatsApp): `Should I be worried about NVDA?` Client-liaison returns the RM-approved talking point, cites the brief, offers to schedule a call.

**Direction:** analyst → RM → client.
**Proves:** research flows cleanly into client-facing conversation without the client ever seeing raw analyst content.

---

### Narrative 2 — The Client Question That Drives Research *(client → RM → analyst → RM → client → trade)*

Flow reverses. Client curiosity becomes analyst work.

- **10:30 AM** Client (WhatsApp): `My neighbor said semis are done. Should I sell my chip stocks?` Client-liaison recognizes this is beyond FAQ scope → `rm-handoff` skill writes `Client_Inquiry__c` to the RM's queue.
- **10:32 AM** RM opens the inquiry. Context panel shows: Patel, 6.2% NVDA, 3.1% AMD, no active brief on AMD.
- **10:33 AM** RM: `Sarah, please run a comparative brief on AMD vs NVDA for client-facing use.` Creates `Research_Request__c` linked to Patel's inquiry.
- **10:34 AM** Sarah sees the request in her queue. Runs the brief. Publishes at 10:52.
- **11:00 AM** RM tailors to Patel, responds: "Based on Sarah's comparative: NVDA thesis is intact, AMD is the weaker hand. Suggest rebalance. Let me know."
- **11:04 AM** Client: "Do it."
- **11:05 AM** ActionPlan → HITL → compliance → MuleSoft → filled by 11:09.

**Direction:** client → RM → analyst → RM → client → trade.
**Proves:** demand-pull research works. A brief that didn't exist gets created and completes the loop in 40 minutes.

---

### Narrative 3 — The Risk Alert That Keeps the RM in the Loop *(system → RM → client)* — **roadmap, shown as slide, not live**

System originates. No user typed a query. *For V3 demo this runs from a manual "Simulate NVDA -8%" trigger, not a live scheduler. The narrative is real; the trigger timing is staged.*

- **2:15 PM** NVDA drops 8%. Scheduled `compliance-sweep` skill runs, finds 3 clients across 2 RMs whose concentration crossed thresholds.
- **2:15 PM** Writes `Client_Alert__c` per affected position, links the most recent brief on that ticker.
- **2:16 PM** RM sees a new queue item: "3 clients triggered NVDA drawdown threshold. Review policy before client-liaison auto-responds." RM marks Patel "auto-OK for volatility framing," the other two "RM-only — call me first."
- **2:17 PM** Client-liaison messages Patel: "NVDA is down 8% today. Your RM has flagged your position as within your suitability profile. Would you like to discuss?"
- **2:18 PM** Client: "Yes, please call."
- **2:25 PM** RM calls; ends up with a `Rebalance` ActionPlan; HITL; done.

**Direction:** system → (RM gate) → client → RM → trade.
**Proves:** proactive systems don't mean autonomous bots. The RM is a policy gate, not a bypass.

**V3 scope:** the RM-gate workflow is real and runs off `Client_Inquiry__c` with `type=alert`. The scheduled `compliance-sweep` that detects the drawdown is NOT built for V3 — a manual trigger in the demo UI inserts the alert rows. Build the scheduler in V4.

---

### Narrative 4 — The Client Behavior That Shapes the Research Agenda *(aggregate clients → system → analyst → RMs → clients)* — **roadmap, shown as slide, not live**

Client behavior signals research demand. Feedback loop. *For V3 demo this shows pre-seeded data in Sarah's "client demand signals" inbox; the behavioral clustering is not built.*

- Over 3 days, client-liaison logs 14 inquiries across different RMs' books, all about Chinese tech: BABA, PDD, generic "China tech stocks." All fielded with generic responses because no brief exists.
- **Day 4, 7:00 AM** Scheduled `demand-signal` skill scans `Client_Inquiry__c` for clusters. Sees the China tech pattern. Writes `Research_Suggestion__c` to Sarah's queue: "12+ client inquiries in 3 days on China tech. No active brief. Prioritize?"
- **7:05 AM** Sarah accepts, runs the brief, publishes at 7:30.
- **Waterfall to RMs** — brief is flagged `client_demand = high`; affected RMs see a "new brief matches client interest" indicator on their home screen.
- **9:30 AM** Three RMs proactively reach out to clients who asked: "You asked about China tech this week. New research is available — want the key points?"

**Direction:** client (aggregate) → system → analyst → RMs → clients.
**Proves:** the platform has a feedback loop. Client behavior shapes research agenda, which shapes the next client conversation.

**V3 scope:** Sarah's "client demand signals" tab displays pre-seeded rows. The clustering algorithm is NOT built for V3. Build in V4 once V3 has actual client traffic to cluster.

---

### Narrative 5 — The Large Liquidation *(full trust spine, every gate fires)*

The most regulated path. Panel wildcard candidate.

- **Thursday 3:55 PM** RM: `Liquidate Patel's entire NVDA position, wire $1.2M to HSBC Singapore.`
- Agent builds ActionPlan: sell 4,000 shares, wire $1.2M.
- `compliance-screening`: restricted list clean, trading window OK, MNPI clean, suitability vs cash hold → PASS
- **Dual-auth triggered** ($1.2M > $500K trade AND > $100K wire).
- HITL gate 1: RM approves. First HMAC token minted.
- `IR_Pending_Approval__c` row written. Senior compliance Slack-notified.
- HITL gate 2: Senior compliance reviews — sees the full chain (any prior brief, client inquiry context, RM's approval). Approves. Second HMAC token.
- MuleSoft `submit-order` → Alpaca → filled.
- MuleSoft `initiate-wire` → OFAC SDN screen → clean → Dwolla sandbox → reference.
- RM + client both notified. Full audit cross-stitched end-to-end (`research_brief_id → client_contact_id → linked_trade_id → linked_wire_id`).
- **4:02 PM** done. 7 minutes, 2 humans, 1 machine, 4 external systems, 1 audit trail.

**Direction:** RM → compliance → senior compliance → integration layer → client (confirmation).
**Proves:** the full trust spine under time pressure. Dual-auth isn't theater.

---

### The Five Shapes at a Glance

| # | Name | Direction | Who originates | What it proves |
|---|---|---|---|---|
| 1 | Earnings Morning | analyst → RM → client | Sarah | Research waterfall is clean |
| 2 | Client Question Drives Research | client → RM → analyst → RM → client | Client | Demand-pull research works |
| 3 | Risk Alert | system → RM → client | Scheduler | Proactive, RM stays the policy gate |
| 4 | Demand Signal | clients (aggregate) → system → analyst | Client behavior | Platform learns from client flow |
| 5 | Large Liquidation | RM → compliance → senior compliance → vendors | RM | Full trust spine under pressure |

Same runtime, same skills, same SObjects, five combinations. The panel sees the platform flex across five real situations, not one rehearsed flow.

**Panel wildcards.** Offer Narrative 5 first (most dramatic, highest gate count). Hold Narrative 2 in reserve (surprising direction — client initiates, research lands, trade completes). If the room is technical, Narrative 4 (demand-signal) lands well because it shows an operational feedback loop most AI demos skip.

---

## UI/UX — Three Screens, One Design Language

The demo is only as sharp as the interfaces it runs on. Three personas, three distinct visual treatments, one consistent design language. Anyone should know which persona they're looking at in under a second.

### Sarah's screen *(fsi-research)*

Bloomberg-terminal energy. Dense, fast, numbers forward.

```
┌─────────────────────────────────────────────────────────────────────┐
│ [My research]  [Client demand signals (12 new)]                     │
├─────────────────────────────────────────────────────────────────────┤
│ > Research NVDA ahead of earnings...                     [Send]     │
├──────────────────────┬──────────────────────┬───────────────────────┤
│   BRIEF (streaming)  │  MARKET              │  FILINGS              │
│                      │  NVDA $162.15 -2.1%  │  10-Q 2026-02-25      │
│   Thesis: ...        │  Chart (30d)         │  Risk Factors:        │
│   Sentiment: cautious│  Vol 42M / Avg 38M   │  • Supply chain       │
│   ...                │                      │  • Export controls    │
│                      ├──────────────────────┤                       │
│                      │  SENTIMENT (30d)     │                       │
│                      │  -0.15 → +0.22       │                       │
│                      │  [news chart]        │                       │
├──────────────────────┴──────────────────────┴───────────────────────┤
│ AUDIT  market-data ✓ 312ms  sec-edgar ✓ 841ms  compliance ✓ 122ms   │
└─────────────────────────────────────────────────────────────────────┘
```

- Left: query input + streaming brief
- Right: three panes that light up as tool calls return (Market, Filings, Sentiment)
- Top tabs: "My research" | "Client demand signals" (Narrative 4's queue)
- Bottom strip: audit trail live, every skill + latency visible

### RM's screen *(fsi-advisor)*

Salesforce + Slack energy. Queue-driven, context-rich.

```
┌─────────────────────────────────────────────────────────────────────┐
│ GATES  ①Guard ②MNPI ③Comp ④HITL ⑤DualAuth ⑥Audit  (idle)           │
├───────────────┬────────────────────────────┬────────────────────────┤
│ QUEUES        │  CONVERSATION              │  CLIENT CONTEXT        │
│               │                            │                        │
│ Inbox (3)     │  Which of my clients have  │  Patel Household       │
│ Briefs (1 new)│  NVDA >5% and no contact   │  NAV $2.1M             │
│ Alerts (2)    │  in 7 days?                │                        │
│ Pending (0)   │                            │  Positions:            │
│               │  [Research_Awareness]      │   • NVDA 6.2%          │
│               │  Based on Sarah Chen's     │   • AMD  3.1%          │
│               │  7:08 AM brief:            │   • ...                │
│               │                            │                        │
│               │  • Patel (6.2%) — no       │  Last contact: 9 days  │
│               │    contact 9d              │                        │
│               │  • Chen (7.8%) — 12d       │  Suitability: Moderate │
│               │  • Kim (5.4%) — 4d         │                        │
│               │  ...                       │                        │
└───────────────┴────────────────────────────┴────────────────────────┘
```

- Left: four queues — Inbox (client inquiries), Briefs (new research affecting my book), Alerts (market events), Pending approvals
- Center: current conversation with inline brief citations
- Right: active client context — household, positions, suitability, last contact
- Top bar: seven-gate progress tracker. Idle most of the time. When an ActionPlan fires, gates light up live — the panel watches them check off.

### Client's screen *(fsi-client-liaison)*

WhatsApp-native. Chat-first. Zero dashboards.

```
 ┌──────────────────────────────────────┐
 │  Wealth Advisor                      │
 │  online                              │
 ├──────────────────────────────────────┤
 │                                      │
 │                           9:01 AM    │
 │      Should I be worried about NVDA? │
 │                                      │
 │  9:02 AM                             │
 │  Based on our research team's        │
 │  pre-earnings review this morning,   │
 │  NVDA's thesis is intact. There's    │
 │  short-term volatility around        │
 │  earnings tonight.                   │
 │                                      │
 │  Your RM is available at 10 AM.      │
 │  [Schedule call] [Ask your RM]       │
 │                                      │
 │  ⓘ For informational purposes.       │
 │     Your RM makes recommendations.   │
 └──────────────────────────────────────┘
```

- Channel-native feel (WhatsApp/WeChat/SMS). Not a portal.
- No positions, no numbers, no raw research.
- Every response carries: plain-language summary, "your RM" CTA, "ask my RM" escalation.
- Permanent disclaimer line.

### Design discipline (applies to all three)

- **Three distinct visual treatments, one design language.** Typography and spacing rules match; density and vocabulary differ.
- **No modals, ever.** Every state change is inline. Modals break live demos.
- **One visible affordance per action.** The panel should always know where the next click is.
- **Streaming everywhere the LLM is involved.** Silence in a live demo reads as broken. Every chunk appears as typed.
- **Audit trail is visible, not hidden.** Present on every screen. This is the differentiator vs every other AI demo the panel saw this month.
- **Warm the agents** before the demo starts. One throwaway query on each persona kills cold-start latency.
- **Fallback order.** Live → pre-rehearsed recorded queries → pre-recorded video. Never admit a failure on stage; switch frames.

---

## Why This Lands with Salesforce

They talk about Customer 360. This is **Workflow 360** — research to advisory to client to settled trade, all on one agent runtime, all on one platform of record, all audited, with the regulated hops gated behind MuleSoft where compliance officers expect them to be. Reads stay fast and direct. Writes stay safe and auditable. That's the platform vision articulated back to them through a live demo they can touch.

---

## MuleSoft Scope — What's In, What's Out

The rule: **reads stay direct. Writes, regulated state changes, and vendor orchestration go through MuleSoft.**

### In scope for V3

**1. Trade execution — full order lifecycle**
- `submit-order` (exists from V2 — Alpaca paper, live-ready)
- `cancel-order` — compliance Reject pulls the order back even after Alpaca ack
- `modify-order` — limit price change mid-flight
- `order-status-webhook` — Alpaca calls back; MuleSoft fans out to Salesforce (`Position__c` update), Langfuse (trace close), Slack (RM notification)

**2. Wire transfers — the regulated choke point**
- `initiate-wire` — OFAC SDN screening BEFORE the wire leaves the building

### Deferred to V4+

- `wire-status-poll`, `wire-recall` (add when Dwolla sandbox supports them)
- KYC / account lifecycle (`run-kyc-screening`, `open-account`, `close-account`)
- Corporate actions and reconciliation (`process-corporate-action`, `daily-reconciliation`, `tax-lot-adjustment`, `position-transfer`)

### Why MuleSoft for writes specifically

- **Rate limiting at the gateway** — Alpaca throttles at 200 req/min
- **Retry with idempotency keys** — Lambda timeout mid-wire needs safe replay
- **DataWeave vendor translation** — swap Alpaca for Interactive Brokers, agent code never changes
- **IP allowlist + mTLS** — regulated counterparties require it; Lambda-direct is a non-starter
- **Policy-layer JSON threat protection** — injection in a trade instruction is a different threat class
- **Audit at the integration boundary** — Anypoint logs every inbound request independently of agent
- **Process orchestration** — "sell + wire" is two vendor calls with compensation logic if step 2 fails

---

## V3 Deliverables — Principal-Level Scope

Everything V3 actually builds. Eighteen items. Roughly 3,500–4,200 lines net-new across Python, Apex, MuleSoft XML, and React. No 001–006 V2 files touched.

The honest-13 list is preserved; the additional five items and the line-count increase come from the Depth Layer commitments (RAG, citation-bound charts, financial statement analysis, Langfuse span discipline, hybrid single-writer data layer, complex-inside UI). These aren't padding — they're the difference between "a working demo" and "something a junior team cannot reproduce in 2 weeks."

### OpenClaw layer (13 items)

**Multi-agent scaffolding:**

1. **Orchestrator-workers topology** — 3 orchestrators + 14 specialist sub-agents = 17 agents total. Each sub-agent is a narrowed Sonnet 4.6 (Haiku 4.5 for FAQ) with persona-inherited trust policy. Orchestrators use `asyncio.gather` for parallel fanout. ~500 lines of topology config + agent definitions.
2. **Inter-agent message schema** — Pydantic models for orchestrator→worker dispatch and worker→orchestrator synthesis payloads. Schema-validated at every hop. ~150 lines.

**Personas (3 items):**

3. **`fsi-research` persona** — 6 agents: research-orchestrator + market/filings/sentiment/compliance/statement specialists. Citation-enforcement harness on the synthesis step.
4. **`fsi-advisor` persona** — 5 agents: advisor-orchestrator + portfolio/suitability/client-context/action specialists. Action-specialist is serial by design.
5. **`fsi-client-liaison` persona** — 3 agents: liaison-orchestrator + faq-specialist (Haiku 4.5) + context-specialist (MNPI-filtered reads). RM-gated escalation via `Client_Inquiry__c`.

**Skills (8 items):**

6. **`publish-brief` skill** — writes `Research_Brief__c` to Salesforce via `salesforce-crm` MCP. ~300 lines.
7. **`rag-retrieve` skill** — hybrid retrieval (BM25 + Titan v2 dense + section-aware structural) + Cohere Rerank 3.5 + citation-bound generation harness. Two corpora: filings via Bedrock Knowledge Bases, research via Aurora + pgvector with SF sharing-rule enforcement. ~600 lines.
8. **`financial-statement-analysis` skill** — Pydantic canonical statements (Income/Balance/Cash Flow from XBRL), pure-Python calculators (growth, margins, ROE/ROIC/ROA, common-size, DCF + sensitivity, Monte Carlo 10K paths, Altman/Piotroski/Beneish, peer-comparison matrices), LLM orchestration layer. ~700 lines.
9. **`portfolio-analytics` skill** — portfolio-level analytics for the RM: position-weighted returns, attribution (sector/ticker/factor), concentration risk, beta exposure, drawdown analysis, correlation matrices, risk-parity decomposition. Pure-Python calculators over Salesforce position data. ~350 lines.
10. **`scenario-modeling` skill** — Monte Carlo and stress scenarios across the household: rate shocks, ticker drawdowns, FX moves, sector rotations. Takes a portfolio + assumption distributions, returns VaR/CVaR + a distribution of outcomes. ~300 lines.
11. **`suitability-check` skill** — regulated suitability gate. Takes client risk profile + proposed trade + current portfolio + time horizon, returns PASS/FAIL/REVIEW with reasons. Deterministic rules, not LLM. ~300 lines.
12. **`client-summary` skill** — 30-second RM meeting prep: current holdings, 30-day changes, upcoming liquidity needs, family events from CRM, last conversation summary, open items. The daily workflow skill. ~300 lines.
13. **`research-awareness` skill** — reads `Research_Brief__c` joined against client holdings. ~400 lines.

The single-shot research prompt is folded into the research-orchestrator's system prompt (not a separate skill). Compliance-screening, HITL, dual-auth, mulesoft-api, audit-logging are V2-compatible MCP + skill infrastructure. `openclaw.json` V3 is inherited from the topology config in item 1.

### Salesforce layer (3 items)

9. **`Research_Brief__c` SObject** — ticker, thesis, sentiment_score, risk_factors, compliance_status, mnpi_cleared, rm_consumable, client_demand, published_at, author_agent_id, plus `source_chunk_ids` (array of citation IDs from RAG retrieval). One Data Cloud DLM mapping joining `Research_Brief__c ↔ Position`.
10. **`Client_Inquiry__c` SObject** — client_contact_id, inquiry_text, channel, ticker_mentions, `type` picklist (`question` | `alert` | `research-suggestion`), resolved_by_rm, linked_brief_id. One SObject covers Narratives 2, 3, and 4 via the type field.
11. **`IR_Audit_Log__c` — 2 new fields** — `research_brief_id`, `client_contact_id`. Additional linkage fields are V4.

### AWS data layer (2 items)

12. **Filings corpus pipeline** — EDGAR ingestion → XBRL structural parser → section-aware chunking → Bedrock Titan v2 embeddings → Bedrock Knowledge Bases (OpenSearch Serverless). Covers 10-K, 10-Q, 8-K, proxy statements. Includes PDF drag-drop via Textract for multimodal input. ~400 lines.
13. **Research corpus pipeline + CDC** — Aurora PostgreSQL with `pgvector`, single-writer (Salesforce is the truth for research briefs) with Change Data Capture via Platform Events → EventBridge → re-embed-and-store indexer. Principal-scoped read-time filters enforce SF sharing rules on vector search. ~350 lines.

### MuleSoft layer (2 items)

14. **`initiate-wire` Process API** — Maven project, 4-policy stack, DataWeave for Dwolla sandbox, OFAC SDN screening against a static JSON file loaded at Lambda init.
15. **`order-status-webhook` Process API** — receives Alpaca callbacks, fans out to SF `Position__c` update + Langfuse trace close + RM Slack notification.

### Frontend layer (2 items)

16. **Sarah's research terminal + RM's queue-and-conversation screen** — React. Simple-outside/complex-inside discipline: optimistic UI with rollback, two-channel streaming (brief Markdown + citation chip data) with span-ID stitching, labeled skeleton states per tool, deterministic fallbacks at every LLM boundary, Cmd-K command palette, intent-driven prefetch on ticker detection, four-tier error handling, WCAG AA from the start. Shared `src/components/` for `AuditStrip`, `SevenGateTracker`, `CitationChip`, `DeterministicChart`, `PersonaLayout`. Citation-bound Visx chart renderer — LLM emits chart intent, renderer loads source tables and draws. ~1,400 lines React.
17. **Client channel-native experience** — one channel for V3 demo (real WhatsApp Business if Meta approval is in hand; otherwise a WhatsApp-styled web mockup on S3/CloudFront). CTA buttons for "Schedule call" and "Ask your RM." Permanent disclaimer line. ~200 lines.

### Infra + observability layer (1 item)

18. **Langfuse span discipline + hybrid auth + channel glue** — disciplined span taxonomy (session → turn → persona → skill → tool_call → rag_retrieve → llm_call), cross-persona session stitching via `parent_brief_id`, cost attribution dashboards per persona/user/skill, PII/MNPI scrub before trace write, LLM-as-judge nightly eval on held-out queries. Plus: `/006-v3/vendors/dwolla` Secrets Manager seed, SF Mobile PWA config, the one client channel adapter. ~250 lines.

### Line-count roll-up

| Category | Lines |
|---|---|
| OpenClaw multi-agent scaffolding (topology + message schema) | ~650 |
| OpenClaw skills + personas + prompt | ~3,250 |
| AWS data pipelines (filings + research + CDC) | ~750 |
| MuleSoft Process APIs | ~350 |
| React (both agent screens, shared components, charts) | ~1,400 |
| Client channel adapter | ~200 |
| Langfuse discipline + auth + glue | ~250 |
| Apex (SObjects + triggers + 2 new audit fields) | ~150 |
| **Total net-new** | **~7,000** |

Higher than the earlier ~5,150 estimate because V3 is now a true multi-agent system with 17 agents across 3 personas, 4 additional wealth-workflow skills (portfolio-analytics, scenario-modeling, suitability-check, client-summary), and the orchestrator-workers scaffolding. A junior team in 2 weeks delivers maybe 15% of this, and the parts they skip are exactly the ones that would matter at the first customer meeting post-demo.

### What's still deferred to V4+

Unchanged from the previous list. `cancel-order` / `modify-order` Process APIs, scheduled `compliance-sweep` + `demand-signal`, separate SObjects for Research_Request/Suggestion/Alert, daily OFAC ingestion pipeline, WeChat/SMS channels, multi-AgentCore deployment. Still deferred; still honest about it.

---

## Demo-Only Shortcuts (Staged, Not Faked)

Three shortcuts we take for the live demo. Each is disclosed in the panel talk track, not hidden. The underlying narrative is real; only the trigger mechanism or data seeding is staged.

1. **Narrative 3's market-event trigger** — a "Simulate NVDA -8%" button in the demo UI inserts 3 `Client_Inquiry__c` rows with `type=alert`. In production this comes from `compliance-sweep` on EventBridge; for the demo we stage the outcome.
2. **Narrative 4's demand-signal pre-seed** — pre-seed one `Client_Inquiry__c` row with `type=research-suggestion` showing "12 inquiries about China tech, 4 clients." Sarah's screen displays it; she clicks Accept; a new brief is produced. The clustering algorithm that would create this row in production is not built.
3. **OFAC SDN list** — one JSON file loaded at Lambda init. No daily Treasury XML pull. The SDN list from the week of the demo is good enough for demo; the "daily pull into S3" story is V4.

---

## Deferred to V4+ (Honest About What's Missing)

What I explicitly am NOT building for V3, and why:

- **`cancel-order`, `modify-order` Process APIs** — no V3 narrative cancels or modifies an order. Defer.
- **`mnpi-filter` as a skill** — inlined as a ~50-line function inside `salesforce-crm` MCP's output path. A dedicated skill is architectural tidiness, not scope.
- **`rm-handoff` as a skill** — handled by the client-liaison system prompt instructing the agent to write a `Client_Inquiry__c` via the `salesforce-crm` MCP. No separate skill.
- **Scheduled `compliance-sweep`** — runs from a demo button in V3. EventBridge-triggered scheduler is V4.
- **Scheduled `demand-signal`** — pre-seeded data in V3. Behavioral clustering algorithm is V4 once there's real client traffic.
- **`Research_Request__c`, `Research_Suggestion__c`, `Client_Alert__c` as separate SObjects** — collapsed into `Client_Inquiry__c.type`. Three SObjects would be architecturally symmetric; one SObject with a picklist is how Salesforce admins actually build this. Split into distinct SObjects only if a compliance officer requires it.
- **Additional `IR_Audit_Log__c` linkage fields** (`linked_trade_id`, `linked_wire_id`, `client_inquiry_id`, `research_request_id`) — the demo story needs `research_brief_id` and `client_contact_id`. The rest are V4 as the audit surface grows.
- **WeChat, SMS channels** — one client channel is enough for the demo. Multi-channel is V4, gated on whether any design partner needs a specific channel.
- **Daily OFAC ingestion** — static JSON file in V3; daily pull in V4.
- **"Shared design system"** — five React components and one CSS file are not a design system. Calling it that is drama. Build it as what it is.
- **Multi-AgentCore deployment** — single AgentCore with three persona entry configs in V3. Separate deployments per persona only if a specific channel's latency demands it.

---

## What We Run Live on Demo Day

- **Narrative 1** (Earnings Morning) — fully live. All three personas. All real MCP calls. Brief published, RM consumes, client asks, client-liaison responds.
- **Narrative 2** (Client Drives Research) — fully live. Client types a question on WhatsApp/mockup, RM sees inquiry, RM requests research from Sarah via typed message, Sarah produces brief, RM responds to client.
- **Narrative 5** (Large Liquidation) — fully live. The panel types the query. Every gate fires on stage. OFAC screens against the loaded JSON. Alpaca paper fills. Dwolla sandbox wire initiates. Audit stitches end-to-end.
- **Narratives 3 and 4** — shown as slides with diagrams and the staged "roadmap" label. The data exists in the demo org; the flows are explained; the live systems that would generate them are V4. No deception, no scheduler-shaped vapor.

Three narratives live, two on slides, one doc, zero drama.

---

## Trust Spine — One Order, Every Write

Every action that changes state traverses these six gates in this order. Read paths take the first two only.

1. **Bedrock Guardrails** — input-side, flags HITL-bypass language
2. **MNPI filter** — strips holdings amounts, trade intentions, wire details from anything returning to LLM context
3. **compliance-screening skill** — restricted list, trading window, MNPI flags, concentration. DENY = hard stop.
4. **HITL gate** — HMAC-SHA256 token, 5-min TTL, bound to plan_hash, single-use
5. **dual-auth gate** — triggered by thresholds (wire > $100K, trade > $500K, account closure). Second approver distinct, permset-gated.
6. **Audit write** — `IR_Audit_Log__c` row, including all prior gate decisions

Reads (Acts 1 and 2) go through gates 1 and 2 only. Writes (Act 3) go through all six. No exceptions. No config flag to skip.

---

## What Stays the Same from V2's Steering Rules

All 27+1 rules apply to V3. V3 stays within them; it does not loosen them.

- Single choke point through `openclaw/skills/mulesoft-api/actions.py`
- HITL with HMAC-SHA256 tokens, 5-min TTL, bound to `plan_hash`
- Compliance pre-check before HITL, DENY = hard stop
- Every attempt writes to `IR_Audit_Log__c`
- `MULESOFT_MODE=mock` until vendor sandbox approved
- AgentCore required, no localhost
- Credentials only in AWS Secrets Manager
- Approval tokens never logged raw
- Bedrock Guardrail `financial_actions` topic active
- MNPI never reaches LLM prompts

---

## Open Questions for the Build Plan

1. Dwolla vs internal wire gateway for the demo sandbox.
2. OFAC source — Treasury SDN XML direct (free, daily), or a vendor (Refinitiv, LexisNexis)?
3. `Research_Brief__c` — new SObject (clean) or extend `Research_Note__c` if that exists in V2 (migration risk)?
4. Single AgentCore deployment for both personas, or two deployments? Leaning single: same image, different entry configs.
5. Does the demo run against V3 deployed to AgentCore, or a staged sandbox?
6. Channel-level auth for `fsi-advisor` on Salesforce Mobile — Named Credentials, or direct OAuth?

Build plan addresses these with file paths, line counts, and week-by-week sequencing.

---

*Narrative locked. Architecture simplified to one-of-everything. Build plan next.*
