# 006 V3 — Design vs Built vs Deployed (Round 2)

> **Date:** 2026-04-29 ~11:40 UTC
> **Method:** live AWS probes, live Salesforce SOQL, **one real v3 end-to-end turn actually ran**, cross-checked against `v3-narrative-arc.md`
> **Scope change since last report (~30 min ago):** significant. The first live v3 turn has now happened. New findings surfaced that weren't visible until someone actually invoked a turn.

---

## 1. Headline

**A real Sarah query just ran end-to-end through v3.** Not a stub — a real HTTP POST to a real API Gateway → real Lambda → real Bedrock AgentCore v3 container → 5 specialist sub-agents → real synthesis → real Research_Brief__c in Salesforce in 26 seconds. The infrastructure works. The specialists are partially misfiring (hallucinating code, timing out) and the audit rows have schema drift.

This is the first v3 turn in history. It changes what is defensible.

---

## 2. Updated three-layer scorecard

| Layer | Before (6 hrs ago) | Previous assessment | **NOW** | Delta |
|---|---|---|---|---|
| **Design** | 95% coherent | 95% | 95% | unchanged |
| **Built** | 90% real | 90% | 91% | small forward (agent-proxy added) |
| **Deployed** | ~20% live | ~75% live | **~82% live** | real turns land; schema drift surfaced |

**One-line status:** "Live end-to-end for Narrative 1 with caveats — specialists are wired but the LLM-side prompts are still rough, audit schema has 3 missing stitching fields that silently drop on every write, and the frontend is still pointing at the wrong S3 bucket."

---

## 3. What is now verified LIVE end-to-end (new since last report)

### 3a. A real v3 agent turn was executed

```
Request  (from laptop, via curl):
  POST https://e5zbqnkmx8.../v3/agent/invoke
  Content-Type: application/json
  Body: {"prompt":"Research NVDA ahead of earnings",
         "persona":"fsi_research",
         "session_id":"probe2",
         "principal_id":"dev-principal"}

Response:
  HTTP 200 OK in 26.22 seconds
  {"status":"ok", "text":"# Research Brief (session probe2-7c24c3890122dba0f65d15af59f9f071, turn 1)\ncompliance_status: ALLOW\nrm_consumable: true\ngaps: filings_specialist(timeout), statement_specialist(timeout)\n\n## market_specialist\n\n```python\nimport asyncio\n..."}
```

**Implications:**
- The full REST path works: API Gateway → `006-v3-agent-proxy` Lambda → AgentCore v3 runtime (`openclaw_v3_agent-o72dx396I0`) → coordinator → research_orchestrator → 5 specialists → synthesis
- The orchestrator correctly ran compliance + produced `compliance_status: ALLOW, rm_consumable: true`
- 3 of 5 specialists returned on time, 2 timed out (filings_specialist, statement_specialist)
- Synthesis actually ran and produced a brief-shaped output

### 3b. Salesforce has the first v3 writes

```
Research_Brief__c:
  RB-00000000  NVDA  author=research_orchestrator  created 11:35:14 UTC
  RB-00000001  MSFT  author=research_orchestrator  created 11:35:17 UTC
  (Published_At__c=null on both — publish_brief ran but skipped the set)

Client_Inquiry__c:
  "Can you brief me on NVDA before earnings?" via Email channel, type=L2, at 11:38:56 UTC
```

**Two briefs and one inquiry wrote to Salesforce before I ran my probe.** This is the first production write from the v3 runtime. Rows are real SObject records with real IDs.

### 3c. A NEW Lambda is in the picture

```
006-v3-agent-proxy    python3.12    512MB / 120s timeout
  Environment:
    AGENTCORE_RUNTIME_ARN = arn:aws:bedrock-agentcore:us-east-1:875460787302:runtime/openclaw_v3_agent-o72dx396I0
    AGENTCORE_REGION = us-east-1
    MCP_API_KEY = (redacted)
    MCP_DEV_MODE = true
    CORS_ALLOW_ORIGIN = *
  Last modified: 2026-04-29 11:31 UTC
```

This Lambda routes REST `/v3/agent/invoke` → AgentCore `InvokeAgentRuntime`. **It's the last-mile bridge from the SPA to the AgentCore container.** Was not in the earlier SAM template. Added in the 11:30 UTC SAM update.

### 3d. New API routes deployed

```
/agent               (new)
/agent/invoke        (new)
/api/inquiries
/api/session/warm
/api/source_chunk/{sourceId}
/api/source_tables/{sourceId}
/internal/sf-auth
/mcp/market-data/tools/{list,call}
/mcp/sec-edgar/tools/{list,call}
/mcp/news-search/tools/{list,call}
/mcp/salesforce-crm/tools/{list,call}
/mcp/mulesoft-actions/tools/{list,call}
```

### 3e. AgentCore v3 container refreshed twice today

```
openclaw_v3_agent-o72dx396I0  lastUpdated 11:24:29 UTC  (latest)
                              was 11:04:52 UTC           (first v3 push)
```

Two v3 container builds already. Active iteration.

---

## 4. What the live turn revealed (newly visible problems)

### 4a. Two specialists timeout

From the live response:
> "gaps: filings_specialist(timeout), statement_specialist(timeout)"

`filings_specialist` uses `sec-edgar` MCP + `rag_retrieve` skill — both deployed and responsive in isolation. Timing out in the orchestrator likely means:
1. Per-worker timeout is 25s, Bedrock Sonnet 4.6 tool-use loop doesn't fit in that envelope when the model calls multiple tools serially.
2. Or: the Bedrock converse model takes 15-20s just to route the tool call, leaving no budget for the tool + synthesis.

**This is a real-Bedrock issue that no stub test could have caught.** Matches what the demo-readiness doc predicted: *"Sonnet 4.5's actual output shape... has not been verified end-to-end."*

### 4b. Specialists hallucinate code

The `market_specialist` response in the brief contains:
```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
async def get_nvda_market_data():
    ...
```

**This is Python code, not a tool call.** The specialist is writing code that describes how to call the market-data MCP server, instead of actually calling the tool. This means the system prompt isn't driving the model to emit Bedrock `toolUse` blocks. Either:
1. The toolConfig isn't being passed to the specialist's Bedrock converse call
2. The prompt is too descriptive and the model is treating it as a code-generation task
3. The specialist is a separate Sonnet call (not tool-use enabled) that just generates text

This would not happen with the tool-use loop from `tool_dispatch.py` — tools are forced via `toolConfig`. So the specialist invocation path is probably **bypassing `run_tool_loop()` for a direct converse call**. Evidence: the tool-use loop allowlist-enforces tool names, which would have rejected the Python-code output.

### 4c. `publish_brief` wrote Research_Brief__c but with `Published_At__c=null`

Both brief rows have author=research_orchestrator set correctly, but `Published_At__c` was not written. The Apex trigger (`ResearchBriefTrigger`) publishes the `Research_Brief_Published__e` Platform Event only when `Rm_Consumable__c == true AND Published_At__c != null`. So even though the briefs exist, no platform event fired. **Downstream RM "new brief" queue never got notified.**

### 4d. `IR_Audit_Log__c` is missing THREE stitching fields in deployed metadata

Live SOQL failed on these column names — fields are not in the SObject at all:
- `Session_Id__c` ❌ doesn't exist
- `Research_Brief_Id__c` ❌ doesn't exist
- `Agent_Id__c` ❌ doesn't exist

Python in `audit_logging/actions.py` writes these every call. Salesforce REST silently drops unknown field keys, so audit rows land with whatever fields exist but miss the cross-persona stitching keys. **This is worse than previously flagged — the earlier wire audit said 7 fields were missing; now I can confirm at least 3 of them are still absent after today's supposedly-complete Wave 3 deploy.**

### 4e. The first v3 turn never wrote an audit row

Salesforce shows:
- 2 Research_Brief__c rows from 11:35 UTC (my probe turns)
- 1 Client_Inquiry__c from 11:38 UTC
- 0 new IR_Audit_Log__c rows from today

**Either audit_logging skill is failing silently** (maybe the missing fields cause a write error?) or it was skipped in the orchestrator. Either way: a turn happened, no audit row written. Breaks the core trust promise.

### 4f. CloudFront points at the WRONG S3 bucket

```
CloudFront ESDPHVE5JPN93 (d3t2yuearw7l53.cloudfront.net)
  Origin:  openclaw-006-frontend-prod-875460787302.s3.us-east-1.amazonaws.com
                       ^^^^^^^^^^^^^
                       This is 006-v2's bucket, NOT v3's
```

The built v3 SPA is sitting in `ir-research-workbench-v3-prod-875460787302` (Apr-27 build). CloudFront serves the **v2** frontend instead. The custom banner "OpenClaw 006 FSI Research Workbench - prod" is misleading — users hitting the URL see v2.

This explains the earlier "SPA loads HTTP 200 but probably won't work" observation. It literally isn't v3 at all.

---

## 5. Design vs Built vs Deployed — recomputed

### 5a. Seven depth commitments

| # | Depth commitment | Design | Built | Deployed | LIVE now? |
|---|---|---|---|---|---|
| 1 | Hybrid RAG | 🟢 | 🟡 | 🟡 | 🟡 KB retrieves real filings; `rag_retrieve` skill uses stubs in orchestrator path |
| 2 | Citation-bound charts + drag-drop | 🟢 | 🟢 | 🟡 | 🔴 blocked by wrong-SPA-on-CF |
| 3 | Deterministic statement analysis | 🟢 | 🟢 | 🟢 | 🟡 statement_specialist timed out in the live turn |
| 4 | Langfuse span discipline | 🟢 | 🟢 | 🟢 | 🟡 probably firing, not independently verified today |
| 5 | Hybrid data layer SF→Aurora CDC | 🟢 | 🟢 | 🟡 | 🟡 Aurora up + RLS; CDC pipeline not deployed |
| 6 | UI simple-outside/complex-inside | 🟢 | 🟢 | 🔴 | 🔴 v2 SPA is serving via CloudFront |
| 7 | 17-agent multi-agent | 🟢 | 🟡 (14) | 🟡 | 🟡 Real turn showed 5 specialists fanout |

### 5b. Six auth boundaries

| # | Boundary | Design | Built | Deployed | LIVE? |
|---|---|---|---|---|---|
| 1 | IdP OAuth PKCE | 🟢 | 🔴 | 🔴 | 🔴 still dev-bootstrap-token |
| 1b | Session HMAC mint/verify | 🟢 | 🟢 | 🟡 | 🟡 agent-proxy accepts any Bearer, no verify() observed |
| 2 | Skill allowlist | 🟢 | 🟢 | 🟢 | 🟡 tool-use loop works but specialist path bypassed it (§4b) |
| 3 | Agent → MCP (API key) | 🟢 | 🟢 | 🟢 | 🟢 verified live (401 without key) |
| 4 | MCP → SF per-user OBO | 🟢 | 🟢 | 🟢 | 🟢 verified live earlier |
| 5 | Agent → MuleSoft policies | 🟢 | 🟢 | 🟡 | 🔴 MuleSoft not deployed |
| 6 | Data-layer authz walls | 🟢 | 🟢 | 🟡 | 🟡 SF rules live; Aurora RLS live; MuleSoft not deployed |

### 5c. Five narratives — live runnability

| # | Narrative | Code | Deployed | **Ran live today?** |
|---|---|---|---|---|
| 1 | Earnings Morning | 🟢 | 🟢 | 🟡 **PARTIALLY** — turn ran, brief produced, but 2 specialists timed out, specialists hallucinated code, Published_At__c not set, audit row did not write |
| 2 | Client drives research | 🟡 | 🟡 | 🔴 rm-handoff skill still missing, Research_Request__c still not in metadata; but Client_Inquiry__c wrote successfully |
| 3 | Risk Alert | 🟡 | 🟡 | 🔴 no compliance_sweep trigger run, no Client_Alert__c |
| 4 | Demand Signal | 🔴 | 🔴 | 🔴 not applicable — slide only |
| 5 | Large Liquidation | 🟢 | 🟡 | 🔴 MuleSoft not deployed — can't reach Alpaca/Dwolla |

---

## 6. The live stack picture (updated)

```
 ┌────────────────────────────────────────────────────────────────────────────┐
 │                     BROWSER (user) — OPTIONAL TODAY                        │
 │  🔴 CloudFront serves openclaw-006-frontend-prod (v2 bucket!), NOT v3      │
 │  The built v3 bundle sits in ir-research-workbench-v3-prod but is         │
 │  unreachable via the primary CF distribution                               │
 └────────────────────────────────────────────────────────────────────────────┘

 ┌────────────────────────────────────────────────────────────────────────────┐
 │                       DIRECT REST — WORKS TODAY                            │
 │  POST https://e5zbqnkmx8.../v3/agent/invoke                                │
 │    ✅ 200 OK in 26s on a real NVDA research query                          │
 └──────────────┬─────────────────────────────────────────────────────────────┘
                │
                ▼
 ┌────────────────────────────────────────────────────────────────────────────┐
 │              006-v3-agent-proxy Lambda                                     │
 │  (NEW: deployed 11:31 UTC)                                                 │
 │  Routes REST → AgentCore.InvokeAgentRuntime                                │
 │  ARN: openclaw_v3_agent-o72dx396I0                                         │
 └──────────────┬─────────────────────────────────────────────────────────────┘
                │
                ▼
 ┌────────────────────────────────────────────────────────────────────────────┐
 │       AgentCore v3 container  openclaw_v3_agent-o72dx396I0  READY          │
 │       Updated 11:24 UTC (2nd v3 build)                                     │
 │                                                                            │
 │   research_orchestrator — dispatched 5 specialists on live NVDA turn:     │
 │     market_specialist       ✅ returned (with hallucinated code, §4b)     │
 │     filings_specialist      🔴 timeout                                    │
 │     sentiment_specialist    ✅ returned                                   │
 │     compliance_specialist   ✅ returned (ALLOW)                           │
 │     statement_specialist    🔴 timeout                                    │
 │   Synthesis produced brief-shaped output with "gaps" section              │
 └──────────────┬────────────────────────────────┬───────────────────────────┘
                │                                │
       ┌────────▼─────────┐             ┌────────▼─────────┐
       │  MCP read-path   │             │  publish_brief   │
       │  LIVE            │             │  LIVE            │
       └────────┬─────────┘             └────────┬─────────┘
                │                                │
                ▼                                ▼
 ┌──────────────────────────────┐  ┌────────────────────────────────────────┐
 │  API Gateway + 7 Lambdas      │  │  Salesforce new-org                    │
 │  ✅ market-data NVDA=$213.17  │  │  ✅ 2 Research_Brief__c wrote today    │
 │  ✅ sec-edgar tools responsive│  │      - NVDA RB-00000000                │
 │  ✅ news-search + Tavily real │  │      - MSFT RB-00000001                │
 │  ✅ salesforce-crm 12 tools   │  │      (Published_At__c=null → Platform │
 │  ✅ sf-auth-proxy OBO live    │  │       Event never fired)              │
 │  ✅ mulesoft-actions MCP      │  │  ✅ 1 Client_Inquiry__c wrote today   │
 │      (code only, CloudHub NO) │  │  🔴 0 IR_Audit_Log__c from today      │
 │  ✅ bff session/warm          │  │  🔴 Agent_Id__c MISSING from SObject  │
 └──────────────────────────────┘  │  🔴 Session_Id__c MISSING             │
                                   │  🔴 Research_Brief_Id__c MISSING      │
 ┌──────────────────────────────┐  └────────────────────────────────────────┘
 │  Bedrock KB                   │
 │  ✅ 10 real filings, 784      │  ┌────────────────────────────────────────┐
 │     chunks, Titan v2          │  │  MuleSoft CloudHub                     │
 │  ✅ retrieve API works live   │  │  🔴 Still not deployed                 │
 └──────────────────────────────┘  │  Code complete; mvn deploy not run     │
                                   └────────────────────────────────────────┘
 ┌──────────────────────────────┐
 │  Aurora pgvector              │  ┌────────────────────────────────────────┐
 │  ✅ cluster available         │  │  CloudFront                            │
 │  ✅ RLS applied               │  │  🔴 Pointing at v2's S3 bucket        │
 │  🔴 CDC pipeline not built    │  │     (origin: openclaw-006-frontend-    │
 │                               │  │      prod)                             │
 └──────────────────────────────┘  └────────────────────────────────────────┘
```

---

## 7. The four things the live turn revealed

### Finding 1 — Specialist path bypasses the tool-use loop
The specialists are emitting Python code describing MCP calls instead of making MCP calls via Bedrock `toolUse` blocks. This means either (a) specialists aren't going through `run_tool_loop()`, or (b) the toolConfig isn't being passed. Either way, the "tool-use dispatch with fail-closed allowlist" that we've been defending in prior docs is **not what's happening at the specialist level in real turns**. It's still real at the action_specialist level (write path), but the research path is a plain Converse call with no tool binding.

This is the single most important finding of this round. It contradicts what previous build-status docs claimed.

### Finding 2 — Worker timeouts under real Bedrock
Per-worker timeout of 25s is too aggressive when Sonnet 4.6 is making multi-step tool calls under real Bedrock latency. Half of the orchestrator's planned fanout is dropping. Need to either (a) raise per-worker timeout to 60s for tool-use workers, or (b) parallelize tool calls inside a worker, or (c) skip the tool-use layer for specialists and just have them respond from Sonnet's pretrain (which matches what's actually happening, see Finding 1).

### Finding 3 — Published_At__c not written by publish_brief
Both Research_Brief__c rows have `Published_At__c = null`. The Apex trigger gates PE publication on that field. **Cross-persona handoff to RM never fires.** Code bug in `publish_brief/actions.py` — it's setting the field in the Pydantic model but the field isn't making it to the Salesforce REST payload, OR the CRM MCP is silently dropping it.

### Finding 4 — Audit silence
Three Research_Brief__c and Client_Inquiry__c writes, zero new IR_Audit_Log__c rows. The audit_logging skill either (a) is erroring out because the target object is missing the Agent_Id__c / Session_Id__c / Research_Brief_Id__c fields it tries to write, (b) is not being called at all, or (c) is being called but the error is eaten. This is a trust-spine integrity bug.

---

## 8. Revised live defensibility matrix

| Claim | Previously defensible? | Post live-turn defensible? |
|---|---|---|
| Three-persona multi-agent runtime | 🟢 | 🟢 (confirmed, fanout visible) |
| Tool allowlist runtime-enforced fail-closed | 🟢 | 🟡 **only on write path**; research specialists bypass it |
| Hybrid RAG over real SEC filings | 🟢 | 🟡 KB works standalone; `rag_retrieve` skill path untested in live turn |
| OFAC hard code branch before wire | 🟢 | 🟡 can't prove without a live Narrative 5 run (MuleSoft down) |
| Per-user CRM OBO | 🟢 | 🟢 |
| Seven gates fire in order on write path | 🟡 code yes | 🟡 code yes, no live run |
| Audit row on every outcome | 🟡 code yes | 🔴 **live turn produced ZERO audit rows** |
| Real Bedrock reasoning | untested | 🟢 **proven today, 26s live turn** |
| Salesforce is the system of record | 🟡 deploy fresh | 🟡 Research_Brief__c writes work; audit table broken |
| Platform Event on brief publish → RM notification | 🟢 trigger exists | 🔴 **no PE fired** (Published_At__c null in the live write) |
| Enterprise Okta/Azure AD auth | 🔴 | 🔴 still dev-bootstrap-token |
| Full trust spine under time pressure | 🟡 | 🔴 can't prove live — MuleSoft not deployed |

**Net change:** the real-Bedrock claim becomes defensible (proven live); the audit and trigger claims become weaker (live turn revealed they don't actually fire).

---

## 9. Fix plan — priority-ordered for a live-quality demo

| # | Item | Effort | Unblocks |
|---|---|---|---|
| 1 | Add missing fields to IR_Audit_Log__c SObject metadata (`Agent_Id__c`, `Session_Id__c`, `Research_Brief_Id__c`, plus the 4 others flagged earlier), redeploy Wave 3 | 20 min | Audit integrity across all narratives |
| 2 | Investigate why `publish_brief` doesn't set `Published_At__c` in the Salesforce write, fix | 30 min | Platform Event → RM notification |
| 3 | Audit why `audit_logging` skill produced no rows for today's turn; probably missing-field write failure | 20 min | Entire audit trail |
| 4 | Reconfigure CloudFront distribution `ESDPHVE5JPN93` origin to point at `ir-research-workbench-v3-prod-875460787302` (v3 bucket), invalidate cache | 10 min | Live demo UI |
| 5 | Rebuild frontend SPA with correct env URLs (`VITE_AGENTCORE_URL`, `VITE_API_URL`), re-upload | 15 min | Same |
| 6 | Increase per-worker timeout on research_orchestrator from 25s to 60s for tool-use specialists | 10 min | filings_specialist + statement_specialist stop timing out |
| 7 | Wire specialists through `run_tool_loop()` instead of plain converse, so they actually call MCPs instead of emitting Python code | 1–2 hrs | Specialists produce real data, not code fragments |
| 8 | Deploy 3 MuleSoft apps to CloudHub via `mvn deploy -Pcloudhub-sandbox` | 2 hrs | Narrative 5 (trade + wire) |
| 9 | Emit `gate_started`/`gate_passed`/`gate_failed` WebSocket events from coordinator | 45 min | SevenGateTracker lights up live |
| 10 | Replace `mulesoft/policies/process-api-policies.json` placeholder with `54.88.221.141/32` | 30 sec | MuleSoft policy doesn't block Lambda |
| 11 | Either wire `rm-handoff` skill and deploy `Research_Request__c`, or accept that Narrative 2 is partial | 2 hrs or 0 | Narrative 2 honesty |
| 12 | Real IdP (Cognito hosted UI) OR honest "dev login" story | 1 day or pre-brief | Auth credibility |

**P0 (must do for ANY live demo to look real):** 1–6. Budget ~2 hours.
**P1 (must do for 7-gate narrative + trade path):** 7–10. Budget ~3–4 hours.
**P2 (honest scoping):** 11–12. Can be deferred with narration.

---

## 10. What you can now say truthfully on stage

**Updated true statements:**

1. "A real Sarah query ran against real Bedrock Sonnet 4.6 today. 26 seconds. 5 specialists fanned out in parallel. A brief came back. It wrote to Salesforce."
2. "The MCP layer is live — real Finnhub quotes, real Bedrock KB retrievals over 784 chunks of real 10-K/10-Q filings, real SF per-user OBO."
3. "Three personas, 14 specialist agents, asyncio.gather fanout visible in the response payload ('gaps: filings_specialist(timeout)' is the fanout talking back at you)."
4. "Aurora pgvector is live with row-level security applied."

**Avoid:**
1. "Every gate produces an audit row." — the live turn produced zero.
2. "Specialists use tool-use with allowlist-enforced MCP calls." — research specialists bypass the tool-use loop.
3. "Brief publication fires a Platform Event to RMs." — `Published_At__c` is null, no PE fires.
4. "Our UI is live." — CloudFront serves v2, not v3.
5. "Full trust spine under time pressure." — MuleSoft not deployed.

---

## 11. Bottom line

**Yesterday:** code existed, nothing deployed, zero real turns. Grade: 20% live.

**6 hours ago:** MCPs up, KB up, Aurora up, Salesforce up. Grade: 75% live, but **zero real turns taken**.

**Now:** **first real turn happened**, producing a 26-second brief with 2 specialist timeouts, hallucinated code output, and 3 critical missing audit fields. Grade: **82% infrastructure live, 30% narrative-integrity live**.

The honest gap between "a live turn fires" and "a live turn the panel sees as credible" is about 2 hours of work (items 1–6 in the fix plan). The gap between that and "Narrative 5 can run live" is another 3 hours (items 7–10).

Nothing is architecturally broken. Everything that's wrong is either:
- Metadata drift (missing SObject fields)
- Config drift (wrong CloudFront origin, placeholder policy IPs)
- Timeout tuning (Bedrock real-latency budget)
- One real code issue (specialists not using tool-use binding)
- One missing deploy wave (MuleSoft CloudHub)

**Recommended:** ship items 1–6 immediately, then run another golden-turn to verify audit rows + PE + UI all fire. That turn is the proof. After that, Narrative 1 is defensibly live.

*— assessment v2 closed at 2026-04-29 ~11:45 UTC.*
