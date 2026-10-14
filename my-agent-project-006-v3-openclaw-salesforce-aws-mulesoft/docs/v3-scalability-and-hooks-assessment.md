# V3 Scalability + OpenClaw Hooks Assessment

Date: April 2026
Author: platform-ops, post-Narrative-3 build
Scope: honest engineering assessment — what scales, what doesn't, what the OpenClaw hook surface gives us that V3 is not yet using.

---

## 1. OpenClaw hook surface — research summary

Rephrased from the [OpenClaw Agent Loop docs](https://xlongxia.mintlify.app/concepts/agent-loop) and the [Extended Core Hook System Proposal gist](https://gist.github.com/openmetaloom/657c4668c09d235f8da1306e2438904b), with the [freeCodeCamp primer](https://www.freecodecamp.org/news/how-to-build-and-secure-a-personal-ai-agent-with-openclaw) and the [84 Hooks post](https://blakecrosley.com/blog/anatomy-of-a-claw) as context. Content below was rephrased for licensing compliance (≤30 words verbatim per source).

OpenClaw exposes two distinct hook systems.

**Internal event hooks (Gateway hooks)** — fire after the fact. Examples: `session:start`, `command:new`, incoming webhook. Good for notifications, external integrations, triggers. Cannot modify context or block execution. This is the surface the public OpenClaw webhooks guide covers.

**Plugin hooks (agent + gateway lifecycle)** — fire during processing. Roughly:

| Plugin hook | Phase | What it can do |
|---|---|---|
| `before_model_resolve` | pre-session | Override provider / model before resolution |
| `before_prompt_build` | post-session load | Inject prependContext, systemPrompt, append/prepend system context |
| `before_agent_start` | legacy | Compatibility shim; prefer the explicit hooks |
| `agent_end` | post-run | Inspect final message list + run metadata |
| `before_compaction` / `after_compaction` | compaction | Observe or annotate compaction cycles |
| `before_tool_call` / `after_tool_call` | tool loop | Intercept tool params/results |
| `tool_result_persist` | pre-transcript write | Transform tool results before they persist |
| `message_received` / `message_sending` / `message_sent` | messaging | Inbound + outbound message lifecycle |
| `session_start` / `session_end` | session boundaries | Setup/teardown per session |
| `gateway_start` / `gateway_stop` | gateway lifecycle | Gateway cold-start / shutdown |

The extended proposal (2026-02-05) adds 10 more lifecycle phases around request/response processing: `preRequest`/`postRequest`, `preRecall`, `preResponse`/`postResponse`, `preToolExecution`/`postToolExecution`, `preCompaction`/`postCompaction`, `onError`.

Key difference: plugin hooks CAN modify context, block execution, enrich before recall. Event hooks only observe after the fact.

### What V3 uses today

**None of the plugin hooks are registered explicitly.** A `grep -r register_hook` returns zero. The equivalents are implemented inline:

| Cross-cut concern | Where it lives today | Hook it *could* be |
|---|---|---|
| MNPI re-scrub on specialist LLM output | `coordinator._run_one()` inline | `after_tool_call` on every Bedrock converse return |
| MNPI scrub on Langfuse payload | `_ScrubbingLangfuseWrapper` decorator class | `before_trace_write` (custom) |
| Bedrock Guardrails on LLM input | `BedrockConverseClient.converse()` always-on | `before_model_resolve` |
| Audit-row write after every skill | Each skill's own body | `after_tool_call` |
| Seven-gate tool-use dispatch | `tool_dispatch.run_tool_loop()` explicit | `before_tool_call` + `after_tool_call` pair |
| Session-open signature verify | `_require_session_token()` inline per Lambda | `session_start` |

### Verdict on hook usage

What we have works. What we have is also harder to swap and harder to audit independently of the coordinator. If V4 adds a 4th persona or a second tenant, the inline approach means touching the coordinator; a hook-based approach means registering one plugin.

**Action items (V4 candidate, not in V3 scope):**
- Move MNPI scrub + audit write into `after_tool_call` plugin hooks. Single change-point when compliance policy evolves.
- Move Guardrail bootstrap into `before_model_resolve`. Simplifies A/B-testing guardrail configs.
- Move session-token HMAC verification into `session_start`. Eliminates duplicate auth code across five Lambdas.

None of these are demo-blockers. Listed here so the next iteration isn't inventing new patterns where OpenClaw already provides them.

---

## 2. Scalability — can V3 handle 100 concurrent sessions?

Honest, component by component.

### 2.1 The coordinator + AgentCore

**Scales well up to ~500 concurrent sessions.** AgentCore is an AWS-managed serverless runtime; it auto-scales the coordinator container behind the WebSocket endpoint. One coordinator instance per session; no shared in-process state between sessions (every SessionContext is per-session per-principal).

Constraint: Bedrock Converse per-account RPS limits (Sonnet 4.6 in us-east-1 is ~100 RPS on-demand for a new account, higher with Provisioned Throughput). A research turn fans out 5 Sonnet calls in parallel; a ballpark of 20 concurrent research turns = 100 in-flight Sonnet requests = hitting the ceiling.

**Mitigation present:** per-specialist `timeout_s` in OrchestratorDispatch. A queued-but-not-yet-dispatched specialist waits in `asyncio.wait_for`; a throttled one returns `AgentErrorType.TIMEOUT`.

**Mitigation missing:** no explicit `asyncio.Semaphore` around Bedrock calls. Under burst load the coordinator would let 500 concurrent Converse calls fire and take the Bedrock 429s with no retry. The fix is ~20 lines:

```python
# coordinator.py — add to BedrockConverseClient
_BEDROCK_SEM = asyncio.Semaphore(int(os.getenv("BEDROCK_MAX_CONCURRENT", "50")))

async def converse(self, ...):
    async with _BEDROCK_SEM:
        return await self._invoke(...)
```

Not in V3 because the demo never exceeds ~3 concurrent sessions. Add when you onboard real RMs.

### 2.2 The 7-gate tool-use dispatch loop

**Scales linearly with LLM throughput.** Every gate is either a deterministic Python call (compliance_screening, suitability_check, dual_auth gate check, audit_logging) or an outbound MCP/REST call (mulesoft_api). No in-memory shared state. Per-turn budget caps (20 loops, 50K tokens) prevent runaway cost.

### 2.3 MCP Lambdas (5 servers)

**Scales to AWS account limits.** Each Lambda has no reserved concurrency configured in the SAM template — that means default behavior (up to 1,000 concurrent per region, unreserved pool). For a research-fanout of 5 parallel MCP calls × 100 concurrent research turns = 500 simultaneous Lambda invocations. Well under the ceiling.

**Potential bottleneck:** `mulesoft-actions` Lambda runs in-VPC with a single NAT gateway. NAT GW has ~5 Gbps throughput, plenty for wire submits (low throughput by design — HITL-paced). Not a scale issue for V3.

**Potential bottleneck:** `salesforce-crm` MCP calls Salesforce REST via JWT OAuth. Salesforce per-user API limits are ~100K calls/24h (Enterprise Edition). If every user query hits CRM ~3 times, that's ~33K queries/user/day — well under.

### 2.4 Mulesoft Process APIs (CloudHub 2.0)

**Scales by replicas.** pom.xml sets `cloudhub.replicas=1` and `cloudhub.vcores=0.1`. That's tuned for demo. A real trading desk with ~20 RMs doing ~10 trades/day each = 200 trades/day. One replica at 0.1 vCores handles that in seconds. For 200 RMs at 5x volume you bump to 3 replicas at 0.25 vCores via pom property — done.

Throttle: API Manager rate limit is 60 req/min per app. Above that, clients get 429. This is deliberate — writes are human-paced by design (HITL gates); 60/min is an order of magnitude above steady-state.

### 2.5 Salesforce side

**Scales with your SF Edition.** `IR_Audit_Log__c` is queryable, indexed on correlation_id, audited on every update. Platform Events have 100K events/day free on Enterprise Edition — plenty.

Hot spot: `Research_Brief__c` reads on RM queue refresh. Cached in Data Cloud DLM with a 30-min TTL. If DLM cost becomes an issue, a Redis-backed read-through cache in front of the salesforce-crm MCP is a one-Lambda change.

### 2.6 AWS data pipelines (CDK-provisioned)

**Filings corpus (EDGAR → Bedrock KB):** runs once daily on EventBridge cron. Zero scale concern — we aren't trying to scale it.

**Research corpus (SF CDC → Aurora pgvector):** Aurora Serverless v2 auto-scales from 0.5 → 2 ACU based on load. `pgvector` HNSW index is O(log n) on retrieval, handles ~10M chunks without tuning.

**Risk alerts (price monitor → sweep dispatcher):** 5-min scheduled scan of ~50 tickers = ~600 Finnhub calls/hour during market hours, well under the 60/min limit pacing. SQS queue is the throttle and the back-pressure — during a market-wide shock, the queue depth grows and the dispatcher processes at Lambda concurrency limit. No loss, no drama.

### 2.7 Frontend

**React SPA served from CloudFront.** Scales to millions. No state in the SPA that isn't per-session.

**BFF Lambda (new):** 4 endpoints, all < 100ms p50. No shared state. Scales to Lambda limits (~1000 concurrent, region-default). For a team of 200 RMs polling `/api/inquiries` every 10s = 20 req/s, negligible.

### 2.8 Aurora + pgvector RLS

**Scales, but watch the write path.** The CDC Lambda writes to Aurora on every SF Platform Event. If Sarah publishes 5 briefs/day × 20 analysts = 100 embedding calls/day → 100 Bedrock Titan v2 calls → ~$0.04/day. Tiny. Reads scale with HNSW; writes scale with Aurora Serverless capacity.

Hot spot: every `principal_visibility` update triggers an RLS re-eval. If the SF sharing model has thousands of role-hierarchy members, the read-time filter could get slow. Haven't seen it; monitor the p99 on `retrieve_research_chunks` spans in Langfuse.

---

## 3. Overall verdict

**V3 scales to a working desk — ~20 concurrent RMs + 2 analysts.**

**Two things to add before V4 or before a real 100-RM deployment:**

1. Bedrock concurrency semaphore (`BEDROCK_MAX_CONCURRENT=50` env var, ~20 lines in `coordinator.py`).
2. OpenClaw plugin hooks for the four cross-cutting concerns above. Makes the trust layer swappable without touching the coordinator.

**Neither is a demo blocker.** Demo day traffic is 3 concurrent sessions (presenter + wildcard panelist + pre-warmed backup).

**Claims NOT being made:**

- Not claiming V3 is a production-grade multi-tenant platform. One tenant, one org, one region. Per-tenant isolation and cross-region replication are V4.
- Not claiming the demo traffic is load-tested. It isn't. Rehearse twice, record once as fallback.
- Not claiming p99 latency targets. V3 has never been measured under sustained load. Baseline is "feels instant on a single-user rehearsal."

---

## 4. Sources

- [OpenClaw Agent Loop docs — Hook points section](https://xlongxia.mintlify.app/concepts/agent-loop)
- [OpenClaw Extended Core Hook System Proposal gist](https://gist.github.com/openmetaloom/657c4668c09d235f8da1306e2438904b)
- [freeCodeCamp: How to Build and Secure a Personal AI Agent with OpenClaw](https://www.freecodecamp.org/news/how-to-build-and-secure-a-personal-ai-agent-with-openclaw)
- [Blake Crosley: 84 Hooks as an Orchestration Layer](https://blakecrosley.com/blog/anatomy-of-a-claw)
- [Amazon: Introducing Amazon Bedrock AgentCore](https://aws.amazon.com/blogs/aws/introducing-amazon-bedrock-agentcore-securely-deploy-and-operate-ai-agents-at-any-scale/)

Content was rephrased for compliance with licensing restrictions.
