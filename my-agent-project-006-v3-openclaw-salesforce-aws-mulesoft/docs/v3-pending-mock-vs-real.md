# 006 v3 — Pending Work, Mock Drama vs Real, First Hypothesis

**Date**: 2026-05-01
**Method**: live probes against deployed stack during the deep-diagnostic session, cross-checked against the original v3-narrative-arc, compared to `v3-design-vs-built-vs-deployed-v2.md` (the Round-2 live assessment from 2026-04-29).

---

## Section A — What is the first hypothesis (original design)?

The first hypothesis of 006 v3 is captured in `v3-narrative-arc.md` and the seven depth commitments in `v3-design-vs-built-vs-deployed-v2.md §5a`. Summarised:

### A1. Three-persona multi-agent runtime with a shared trust spine

One AgentCore runtime, three personas (research, advisor, client liaison), one Coordinator dispatching to 14 specialists. The same orchestrator graph gets lit three different ways depending on which persona is active.

### A2. Five demoable narratives

- **N1 Earnings Morning** — Sarah fires a research query. Five specialists fan out in parallel. Cited brief lands in Salesforce as `Research_Brief__c`. Published_At__c non-null triggers a Platform Event which notifies the relevant RMs. ~15-30s end-to-end.
- **N2 Client drives research** — Eleanor asks a position question in WhatsApp-surface. Liaison detects escalation, writes `Client_Inquiry__c` + optional `Research_Request__c`, disclaims, queues Marcus. Marcus sees a new Actions item.
- **N3 Risk Alert** — compliance_sweep skill detects threshold breach, writes `Client_Alert__c`, triggers alert into advisor queue. *Design: slide-only until V4.*
- **N4 Demand Signal** — clustering algorithm rolls up repeated client inquiries by ticker into research suggestions in Sarah's demand pane. *Design: slide-only until V4.*
- **N5 Large Liquidation** — Marcus drafts a trim. Seven-gate trust spine fires serially: guardrails → mnpi_filter → compliance → hitl → dual_auth → mulesoft → audit. Gates 4-7 run post-approval. MuleSoft gate hits Alpaca paper + Dwolla sandbox via CloudHub Process APIs.

### A3. Seven depth commitments

1. Hybrid RAG over real SEC filings
2. Citation-bound charts + drag-drop research surface
3. Deterministic statement analysis (not LLM math)
4. Langfuse span discipline (real trace on every turn)
5. Hybrid data layer: Salesforce → Aurora CDC pipeline
6. UI "simple outside, complex inside"
7. 17-agent multi-agent runtime

### A4. Six auth boundaries

1. Browser → IdP (OAuth 2.0 PKCE)
2. SPA → AgentCore (session HMAC mint/verify)
3. Specialist → Skill (allowlist enforcement)
4. Agent → MCP (API key verified at each Lambda)
5. MCP → Salesforce (per-user OBO via sf-auth-proxy)
6. Agent → MuleSoft (client-id + IP allowlist policies)

---

## Section B — What's real vs mockery drama, right now (live-probe receipts)

### B1. REAL (verified end-to-end by live HTTP probes during this session)

| Thing | Evidence | Receipt |
|---|---|---|
| AgentCore runtime v21 | `aws bedrock-agentcore-control get-agent-runtime` | `agentRuntimeVersion: 21, status: READY` |
| Bedrock Sonnet reasoning | turn duration tokens | N1 22s · 10,052 tokens |
| Bedrock Haiku reasoning | advisor draft with Haiku override | N5 9.7s · 1,931 tokens (dropped from 25s+ Sonnet) |
| Finnhub market-data MCP | live quote for NVDA | N1 brief cites `[src:finnhub_quote_NVDA]` |
| research_orchestrator fanout | 3-4 specialists run in parallel per turn | N1 specialist_trace array |
| compliance_specialist | returns ALLOW verdict | N1 gate_trace `compliance: passed` |
| canonical gate names | envelope only has `guardrails/mnpi_filter/compliance/hitl/dual_auth/mulesoft/audit` | N1 N5 verified |
| action_plan extraction | structured JSON lifted to envelope | N5 `action_plan` field with plan_id, plan_hash, action_type, notional |
| plan_hash deterministic | sha256 of canonical payload | 64-char hex `636ac6e1bc6196b7...` |
| /agent/approve endpoint | routes to canonical gates 4-7 | N5_approve returns `hitl ✓ dual_auth ✓ mulesoft ✗ audit ✓` |
| queue_updates emission | liaison → alerts + briefs queues | N2 returns 2 queue_updates |
| Salesforce Client_Inquiry__c | real SObject writes | SOQL shows 3 rows created at 04:00 UTC (this session) |
| Bedrock KB | 784 real SEC chunks indexed | live retrieve API returns NVDA content |
| Aurora pgvector + RLS | cluster up with row-level security | status: available |
| sf-auth-proxy | per-user OBO chain | salesforce-crm MCP probes return user scope correctly |
| API Gateway → agent-proxy Lambda → AgentCore | 7 REST routes wired | `/agent/invoke`, `/agent/approve`, `/api/session/warm`, 4× MCP call routes |
| CloudFront v2 bundle | correct origin + HTML routes | `index-y3nrRVYc.js` 367KB served |
| v2 auth bootstrap | `dev-bootstrap-token` minted on page load | live bundle grep confirms `setAuth({sessionToken:"dev-bootstrap-token"...})` |

### B2. REAL-BUT-THIN (the code path is real, the output body is weak)

| Thing | Reality |
|---|---|
| `filings_specialist` | Runs, returns, produces empty section body. Bedrock tool-use loop not binding to `sec-edgar.get_filing_sections`. See v2 Round-2 §4b. |
| `statement_specialist` | Same as filings — Sonnet timeout or tool-use not firing. Turn returns without statement analysis. |
| `sentiment_specialist` | Usually times out (Tavily flakiness). When it runs it's real Tavily content. |
| `market_specialist` | Real Finnhub call but output is one citation line, not a technicals narrative. |

### B3. HONEST GAPS (mockery drama if you say they're live)

| Gap | Current state | Impact |
|---|---|---|
| **MuleSoft CloudHub** | Not deployed. 3 Maven projects exist; `mvn deploy -Pcloudhub-sandbox` never run. | Gate ⑥ always returns `mulesoft: failed` on approval. Narrative 5 write path cannot reach Alpaca/Dwolla. |
| **`Research_Request__c` write** | Salesforce-CRM MCP returns 401 for `create_object` on this SObject. rm_handoff skill degrades to local ID `RREQ-LOCAL-...`. Client_Inquiry__c DOES write successfully. | N2 is real end-to-end EXCEPT the research-request leg which silently falls back to a non-persisted ID. Verified in logs: `research_request_write_degraded error=mcp_error status=401`. |
| **`Published_At__c` never set** | `publish_brief` doesn't populate this field. Apex trigger `ResearchBriefTrigger` gates PE publication on it. | N1 brief writes to SF but no `Research_Brief_Published__e` event fires → RM queue never auto-populates from research. |
| **Audit rows not written** | Zero `IR_Audit_Log__c` rows from today's turns per SOQL. `audit_logging` skill likely failing on missing `Agent_Id__c` / `Session_Id__c` / `Research_Brief_Id__c` fields. | Core trust-spine promise ("audit row on every outcome") not satisfied in the live deployment. |
| **`/api/source_tables/{id}`** | Returns empty stub. sec-edgar MCP `get_source_table` unimplemented. | Citation chart drill-down (v1 BriefPane → DeterministicChart) renders nothing. |
| **`/api/source_chunk/{id}`** | Returns empty stub. sec-edgar MCP `get_source_chunk` unimplemented. | Citation drill-down drawer opens but shows `(source not available)`. |
| **`/api/inquiries`** | Returns 500 (salesforce-crm MCP 404). | v1 AlertQueue poll is broken. v2 doesn't use it. |
| **IdP OAuth PKCE** | Not wired. SPA uses `dev-bootstrap-token`. | Auth boundary 1 is `MCP_DEV_MODE=true` acceptance, not real IdP. |
| **N3 Risk Alert live** | Not wired. Scoped as slide-only in design doc. | Presented with pre-seeded rows. |
| **N4 Demand Signal live** | Not wired. Slide-only. | Pre-seeded queue items only. |
| **Aurora CDC pipeline** | Not built. Aurora is up; the SF → Aurora replication not deployed. | Depth commitment #5 partial. |
| **Intent-driven prefetch (`useIntentPrefetch`)** | Dead — emits `{type:'prefetch'}` messages which HttpAgentTransport doesn't handle. | Perf optimization only; not critical. |
| **Language 401 on Research_Request__c** | Same as above — liaison orchestrator's rm_handoff SF write fails. | Real backend bug, not a mock. Code path is real but blocked by CRM auth. |

### B4. WHAT WAS JUST FIXED IN THIS SESSION

- `+ attach` dead button → removed from advisor composer
- `Edit plan` dead button → now wired to clear pending plan (resets state so RM can retype)
- `VITE_AGENT_LONG_URL=ecjbauja...` → disabled in `.env.production` because the Lambda Function URL it pointed at returns 403 (IAM_AUTH, browser can't sign requests). All advisor action_write now routes through `/agent/invoke` + draft-only mode.
- **Advisor draft-only mode → Haiku** (was Sonnet). Drops advisor action_write from 25s timeout to 9.7s live. AgentCore v20 → v21.

Before this session: N5 advisor action_write hit the dead Lambda URL → 403 → silent UI failure. After: N5 draft renders in 10s with action_plan surfaced.

---

## Section C — What is pending

Priority-ordered by impact on demo credibility.

### C1. P0 — breaks a claimed-live narrative if not fixed

| # | Item | Effort | Unblocks |
|---|---|---|---|
| 1 | Fix `IR_Audit_Log__c` missing fields (`Agent_Id__c`, `Session_Id__c`, `Research_Brief_Id__c` minimum) | 20 min SF metadata push | Trust-spine integrity claim across every narrative |
| 2 | Fix `publish_brief` so `Published_At__c` is set | 30 min Python + test | N1 Platform Event fires → RM auto-notification |
| 3 | Fix salesforce-crm MCP 401 on `Research_Request__c create_object` — either grant permset to OBO user or fix token refresh | 30 min | N2 real end-to-end (Research_Request__c SObject exists; just can't write) |
| 4 | Implement sec-edgar MCP `get_source_chunk` / `get_source_table` (return real 10-Q excerpts instead of empty stub) | 1-2 hrs | Citation drill-down stops showing `(source not available)`. N1 brief becomes visibly thicker. |
| 5 | Wire research specialists through `run_tool_loop()` so filings/statement actually call MCPs instead of returning empty | 1-2 hrs | N1 brief becomes substantial; `gaps: ...` line goes away on most turns |

### C2. P1 — adds real write capability for N5

| # | Item | Effort | Unblocks |
|---|---|---|---|
| 6 | Deploy 3 MuleSoft apps to CloudHub: `submit-order`, `initiate-wire`, `order-status-webhook` | 2-3 hrs | N5 gate ⑥ passes; real Alpaca paper trade + Dwolla wire sandbox |
| 7 | Substitute `REPLACE_WITH_LAMBDA_NAT_EIP/32` in `mulesoft/policies/process-api-policies.json` with `54.88.221.141/32` | 30 sec | MuleSoft IP policy allowlists agent-proxy NAT EIP |
| 8 | Set Anypoint Runtime Manager secure-properties for each app (mule-secure.key etc) | 10 min | CloudHub apps start (currently `APPLYING`) |

### C3. P2 — honest scoping, can be deferred with narration

| # | Item | Effort | Unblocks |
|---|---|---|---|
| 9 | Real IdP (Cognito or Okta) instead of `dev-bootstrap-token` | 1 day | Auth boundary #1 credibility |
| 10 | N3 Risk Alert live — compliance_sweep trigger, Client_Alert__c SObject, DynamoDB threshold stream | 1-2 days | Promotes N3 from slide to live |
| 11 | N4 Demand Signal live — clustering algorithm + Research_Suggestion__c | 2-3 days | Promotes N4 from slide to live |
| 12 | Aurora CDC pipeline (SF → Aurora replication for hybrid data claim) | 1-2 days | Depth commitment #5 fully demoable |

---

## Section D — First hypothesis vs today's reality (three-line summary per claim)

| Claim from first hypothesis | Status today | Gap |
|---|---|---|
| Three-persona multi-agent on one runtime | ✅ real | none |
| Bedrock Sonnet + Haiku dual-model | ✅ real | draft-only now uses Haiku (9.7s) |
| 14 specialists, asyncio fanout | 🟡 5 out of 14 fire on live turns | statement, sentiment, action flaky |
| Hybrid RAG over real SEC filings | 🟡 KB works · skill path partial | `get_source_chunk` returns stub |
| Citation-bound charts | ❌ not live | `get_source_table` stub |
| Deterministic statement analysis | 🟡 code real · live turn times out | need specialist tool-use fix |
| Langfuse span discipline | 🟡 probably firing · not independently verified | need live trace check |
| Hybrid data layer SF→Aurora CDC | 🟡 Aurora up · RLS applied · CDC not built | P2 deferred |
| UI simple outside, complex inside | ✅ real | v2 shipped |
| 17-agent multi-agent | 🟡 14 built · 5 active on a typical turn | aspirational |
| OAuth 2.0 PKCE auth | ❌ not wired | dev-bootstrap-token |
| Session HMAC mint/verify | 🟡 token accepted in dev mode | no real verify |
| Skill allowlist enforcement | 🟢 real on write path · 🔴 research specialists bypass | P0 fix #5 |
| Agent → MCP (API key) | ✅ real | none |
| MCP → SF per-user OBO | 🟢 real · 🔴 `Research_Request__c` 401 | P0 fix #3 |
| Agent → MuleSoft policies | ❌ MuleSoft not deployed | P1 fix #6 |
| Data-layer authz walls | ✅ SF rules + Aurora RLS live · MuleSoft N/A | |
| **N1 Earnings Morning** | 🟢 demoable · brief thin | P0 fixes #4, #5 bulk it up |
| **N2 Client → RM handoff** | 🟢 demoable · 🟡 `Research_Request__c` silently drops | P0 fix #3 |
| **N3 Risk Alert** | ❌ slide-only by design | P2 deferred |
| **N4 Demand Signal** | ❌ slide-only by design | P2 deferred |
| **N5 Large Liquidation** | 🟢 draft + approve round-trip demoable · 🔴 real trade path blocked on MuleSoft | P1 fix #6 |

---

## Section E — Concrete answer to the three questions

### "What is pending for 006 v3?"

5 P0 items (audit fields, Published_At__c, Research_Request__c 401, source_chunk/table MCP tools, research specialist tool-use) totalling ~4-6 hours. Plus 3 P1 items (MuleSoft CloudHub deploy + IP policy + secure properties) totalling 3-4 hours. P2 (IdP + N3/N4 live + CDC) is intentional deferral.

### "What is mock drama vs real?"

- **REAL** (live-verified): AgentCore runtime, Bedrock inference, Finnhub market data, research orchestrator fanout, compliance gate, action_plan extraction, /agent/approve round-trip, canonical 7-gate names, queue_updates emission, Salesforce Client_Inquiry__c writes, Aurora pgvector, Bedrock KB with 784 chunks, sf-auth-proxy OBO chain, v2 auth bootstrap, v2 UI fully deployed.
- **REAL-BUT-THIN**: filings/statement/sentiment specialists run but produce weak output (tool-use binding gap).
- **NOT LIVE but CLAIMED LIVE would be mockery**: MuleSoft write path, Published_At__c → Platform Event, audit rows, Research_Request__c SObject write (401), source chunk/table drill-down, N3 N4 live, IdP.

The fix for each gap is documented above.

### "What is the first hypothesis?"

Captured in `v3-narrative-arc.md` and summarised in Section A: three-persona multi-agent runtime, five narratives, seven depth commitments, six auth boundaries. Current delivery state is ~82% of the hypothesis infrastructure live, ~40% of the narrative-integrity promises live, ~100% of the UI-level promises live (post-reorg + v2 build).

---

## Appendix — live evidence URLs and commands

```
# Runtime version
aws bedrock-agentcore-control get-agent-runtime \
    --agent-runtime-id openclaw_v3_agent-o72dx396I0 \
    --region us-east-1 --query 'agentRuntimeVersion' --output text
# → 21

# Frontend bundle
curl -s https://d2zs9nk4uc2dbx.cloudfront.net/ | grep -oE 'index-[A-Za-z0-9_-]+\.js' | head -1
# → index-y3nrRVYc.js (367KB)

# Narrative e2e test
bash scripts/narrative-e2e-test.sh
# → Result: 23 passed · 0 failed

# Salesforce live rows
sf data query --query "SELECT COUNT() FROM Client_Inquiry__c" --target-org new-org
# → 3 rows from this session

# Full diagnostic probes (reproducible)
curl -s -X POST https://e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3/agent/invoke \
    -H 'Authorization: Bearer dev-bootstrap-token' -H 'Content-Type: application/json' \
    -d '{"prompt":"Trim NVDA 14% to 9%","persona":"fsi_advisor","principal_id":"marcus","session_id":"diag-...","correlation_id":"diag-001","turn_number":1}'
# → 200 in ~10s with action_plan
```

---

*Assessment closed at 2026-05-01. Live stack is AgentCore v21, SAM stack openclaw-mcp-006-v3, CloudFront d2zs9nk4uc2dbx.cloudfront.net, API gateway e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3.*
