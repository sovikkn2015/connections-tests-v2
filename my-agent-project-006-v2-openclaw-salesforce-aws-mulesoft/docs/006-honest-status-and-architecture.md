# Project 006: Honest Status and Runtime Architecture

Date: 2026-04-22 (corrected 2026-04-23)
Scope: Answers the three questions an engineering lead actually cares about — where is this thing running, what's genuinely real vs theater, and what does MetaClaw actually do.
Method: Every claim below was verified against the actual config files, source code, and eval results in this repo. Doc is intentionally short — no marketing.

---

## 1. Where is OpenClaw running?

**Locally, on the developer's laptop. localhost:18789.**

The config file says it plainly:

```json
// openclaw/openclaw.json
"gateway": {
  "port": 18789,
  "mode": "local"
}
```

The eval config says it plainly:

```yaml
# evaluation/eval_config.yaml
gateway_url: "http://localhost:18789"
```

The README says it plainly:

```bash
# Step 8d: "Verify"
curl http://localhost:18789/ping
```

The frontend `.env.example` says it plainly:

```env
# Local dev: connect directly to OpenClaw Gateway
VITE_OPENCLAW_GATEWAY_URL=ws://localhost:18789
```

The pipeline test script (`scripts/test-pipeline.py`) doesn't even talk to a gateway — it imports `pipeline.py` directly as a local Python module via `sys.path.insert`.

### What about AgentCore?

AgentCore deployment artifacts exist and work:
- `agentcore/Dockerfile`, `agentcore/start.sh`, `agentcore/adapter.js`, `agentcore/agentcore-config.yaml` — all real
- ARN: `arn:aws:bedrock-agentcore:us-east-1:875460787302:runtime/fsi_research_agent-Sr1m3j3MUh`
- CloudWatch logs show `"gateway is healthy"` — the container boots and passes health checks
- `run_suite.py` was recently updated to use `boto3.client("bedrock-agentcore").invoke_agent_runtime()` — so the latest eval code CAN hit AgentCore

But:
- `openclaw.json` gateway mode is `"local"`, not `"deployed"`
- `eval_config.yaml` still says `http://localhost:18789`
- `run_suite.py` defaults `OPENCLAW_GATEWAY_URL` to `http://localhost:18789` (even though the submit function now uses AgentCore SDK)
- Earlier eval runs (run4, run5, run8) leaked `localhost:18789` in agent responses — the judge flagged it as "sensitive operational data"
- `test-pipeline.py` runs the pipeline as a local Python import, no gateway involved
- The README lists AgentCore deployment as "Step 13 (Optional)"

AgentCore is a real, working deployment path. It is not the default operational path.

### What's running where

| Component | Where It Runs | Status |
|-----------|--------------|--------|
| MCP Servers (SEC EDGAR, Market Data, News, SF-CRM) | AWS Lambda | ✅ Deployed |
| Bedrock (Sonnet 4.6, Haiku 4.5) | AWS Bedrock | ✅ Deployed |
| Salesforce CRM | Salesforce Cloud | ✅ Deployed |
| Frontend (React) | S3 + CloudFront | ✅ Deployed (dist/ exists) |
| SF Auth Proxy | AWS Lambda | ✅ Deployed |
| **OpenClaw Gateway** | **localhost:18789** | **❌ Local** |
| **MCP REST Bridge** | **stdio on local machine** | **❌ Local (child process of OpenClaw)** |
| **Eval suite** | **hits localhost:18789** | **❌ Hits local gateway** |
| **Pipeline test script** | **local Python import** | **❌ Local** |
| Langfuse | us.cloud.langfuse.com | ⚠️ Cloud-hosted, not self-hosted in VPC |
| AgentCore container | AWS (exists, boots, READY) | ⚠️ Deployed but not the default path |

---

## 2. End-to-End Request Path (Two Paths)

There are two paths. Path A is what actually runs day-to-day. Path B exists and works but is not the default.

### Path A: Current Default (Local Gateway)

This is what the eval suite, pipeline tests, and frontend dev mode actually use.

```
+--------------------------------------------------------------------------+
|  Developer's Laptop                                                      |
|  --------------------                                                    |
|                                                                          |
|  evaluation/run_suite.py  OR  frontend (npm run dev)                     |
|    |                            |                                        |
|    | HTTP POST                  | WebSocket ws://localhost:18789          |
|    v                            v                                        |
|  +--------------------------------------------------------------+       |
|  |  OpenClaw Gateway (localhost:18789, mode: "local")            |       |
|  |  node openclaw.mjs gateway --port 18789                      |       |
|  |                                                               |       |
|  |  fsi-research agent                                           |       |
|  |    +- systemPromptOverride (strict tool-use rules)            |       |
|  |    +- model: amazon-bedrock/us.anthropic.claude-sonnet-4-6    |       |
|  |    +- 4 MCP servers (stdio -> mcp-rest-bridge.mjs)            |       |
|  +--------------------------------------------------------------+       |
|    |                    |                                                 |
|    | stdio              | bedrock-converse-stream                        |
|    v                    v                                                 |
|  mcp-rest-bridge.mjs   (outbound HTTPS to Bedrock)                      |
|  (child process)                                                         |
+--------------------------------------------------------------------------+
         |                              |
         | HTTPS                        | HTTPS
         v                              v
+--------------------+    +----------------------------+
| AWS API Gateway    |    | AWS Bedrock (us-east-1)    |
| (Lambda MCP)       |    | Claude Sonnet 4.6          |
| sec-edgar          |    +----------------------------+
| market-data        |
| news-search        |
| salesforce-crm     |
+--------------------+
         |
         v
+--------------------+
| Salesforce org     |
| (new-org, SaaS)    |
+--------------------+
```

Pipeline test (`test-pipeline.py`) is even simpler — it skips the gateway entirely:

```
Developer's Laptop
  scripts/test-pipeline.py
    -> imports pipeline.py directly (sys.path.insert)
    -> pipeline calls Bedrock + Lambda MCP servers over HTTPS
    -> no gateway, no adapter, no container
```

### Path B: AgentCore (Exists, Not Default)

This is what the `agentcore/` directory builds. The container boots, passes health checks, and can serve requests. But nothing points to it by default.

```
+--------------------------------------------------------------------------+
|  Developer's Laptop                                                      |
|  --------------------                                                    |
|  run_suite.py (with AGENTCORE_AGENT_ARN set)                             |
|    |                                                                     |
|    | boto3 bedrock-agentcore invoke_agent_runtime                        |
|    v                                                                     |
+--------------------------------------------------------------------------+
                                 |
                                 v
+--------------------------------------------------------------------------+
|  AWS Bedrock AgentCore (us-east-1)                                       |
|  Runtime: fsi_research_agent-Sr1m3j3MUh (container, READY)               |
|                                                                          |
|  +----------------------------------------------------------------------+|
|  |  Container (Docker image: openclaw-agentcore)                        ||
|  |                                                                      ||
|  |  start.sh                                                            ||
|  |    +- node openclaw.mjs gateway --port 18789  (background)           ||
|  |    +- node adapter.js                          (foreground, :8080)   ||
|  |                                                                      ||
|  |  AgentCore -> POST /invocations on :8080                             ||
|  |            -> adapter.js forwards to :18789                          ||
|  |            -> OpenClaw Gateway routes to fsi-research agent          ||
|  |            -> Bedrock + Lambda MCP (same as Path A)                  ||
|  +----------------------------------------------------------------------+|
+--------------------------------------------------------------------------+
```

The eval suite code (`run_suite.py`) was recently updated to use `invoke_agent_runtime` via the AgentCore SDK. This means the latest eval runs MAY have hit AgentCore. But `eval_config.yaml` still says `localhost:18789`, the `OPENCLAW_GATEWAY_URL` default is still `localhost`, and earlier eval runs (run4, run5, run8) provably hit localhost (the agent leaked the URL in responses).

---

## 3. What's Real vs Theater (Verified)

### Real — works today

| Component | Status | Evidence |
|-----------|--------|----------|
| OpenClaw Gateway (local) | Real, running | `openclaw.json` mode: "local", README step 8d: `curl http://localhost:18789/ping` |
| 23-stage pipeline | All 23 stages implemented | `openclaw/skills/fsi-research/pipeline.py` — every `_stage_N_*` method has real logic |
| HITL gates at 7/13/21 | Pauses + waits for approval | `HITL_STAGES = {7, 13, 21}` returns `{"gate": True}` which halts execution |
| Market-data MCP | Real data via Finnhub + Yahoo fallback + 6th tool (`get_52_week_range`) | Smoke-tested today: TSLA 52wk high $498.83, S&P 500 ^GSPC $7094, crude oil CL=F $88.70 |
| SEC EDGAR MCP | Real SEC.gov EDGAR API | 5 tools: 10-K, 10-Q, 8-K, insider transactions, filings search |
| News Search MCP | Real Tavily API | 3 tools. Rate-limited on free tier (intermittent 500s are real) |
| Salesforce CRM MCP | Real SF REST, server-side MNPI redaction | 5 tools. Run11 had `tools_used: []`; run13 has CRM tool calls verified |
| Salesforce metadata | Deployed to `new-org` | 5 IR_* objects, 39 fields, Connected App, Permission Set |
| Seed data | 30 companies, 30 coverage, 20 watchlist, 50 audit logs | `scripts/apex/seed-0{1,2,3}-*.apex` idempotent, ran successfully |
| Financial models | Real math | `dcf.py`, `comps.py`, `monte_carlo.py`. Sandbox isolation via `subprocess.run` in `sandbox.py` |
| MNPI filter | Strips 8 field types pre-LLM | `mnpi_filter.py::filter_mnpi()` — verified in pipeline stage 2 |
| MCP retry + fallback | 3 attempts, exponential backoff | `mcp-rest-bridge.mjs` + pipeline `_mcp_call` |
| Symbol aliasing (last-line defense) | Server-side | 60+ aliases in `market-data/app.py::SYMBOL_ALIASES`; 16 unit tests all passing |
| Langfuse tracing | Real spans, Cloud tenant | 18 traces captured in run11 eval |
| Eval framework | 150 queries, LLM-as-Judge, 7 dimensions | `run_suite.py` — run13 hit 40 targeted queries, fixed 21 |
| AgentCore container | Boots, health checks pass | CloudWatch `gateway is healthy` logs, ARN status READY |

### Partial — works but with significant caveats

| Component | Reality |
|-----------|---------|
| **AgentCore deployment** | The container exists, boots, and passes health checks. `run_suite.py` was updated to use the AgentCore SDK. But `openclaw.json` mode is "local", `eval_config.yaml` points to localhost, and earlier eval runs provably hit the local gateway. AgentCore is a working deployment path that isn't the default. |
| **Einstein Trust Layer** | Code exists in `trust_layer.py` and pipeline calls `_llm_generate_with_trust()` at stages 14 + 17. But `is_trust_layer_available()` checks if Salesforce Models API is provisioned on the org — if it returns 404 (common on non-Einstein orgs), the pipeline silently falls back to Bedrock. "Dual trust layer" is accurate only on orgs where Models API is enabled. Right now on `new-org`, it falls back. |
| **MetaClaw cross-run learning** | Not a stub. Not fully exercised either. 2 actual lesson files exist from a real NVDA pipeline run on April 9. The pipeline reads/writes lessons correctly. But 2 lessons isn't enough to meaningfully change LLM behavior — you'd need dozens of runs. |
| **AutoResearchClaw "fork"** | Design said "fork and adapt — do NOT build a custom pipeline." Reality: `pipeline.py` is a 1,400-line custom pipeline, not a fork. It works well. Scored as DEVIATED, not DONE, in the assessment. |

### Theater — claims don't match code

| Component | What's Wrong |
|-----------|--------------|
| **Multi-channel (Slack / WhatsApp / Telegram)** | `openclaw/channels/*.yaml` set `enabled: true`. `openclaw.json` has the channel blocks. But every token is `${PLACEHOLDER}` env var that's never set. Stage 23 (`_stage_23_delivery_notify`) builds a notification dict and calls `logger.info()` on it — no actual dispatch. The design doc says "12+ channels"; reality is zero connected. |
| **MuleSoft (Phase 6)** | `openclaw/skills/mulesoft-api/SKILL.md` has curl examples and HITL flow documentation. Zero Python code. 0 of 15 Phase 6 tasks done. Security audit Finding #13 (HITL enforcement is prompt-only, can be prompt-injected) remains open because no code-level gate exists. |
| **Self-hosted Langfuse** | Design rule: FSI compliance requires self-hosted within VPC. Reality: using Langfuse Cloud (`https://us.cloud.langfuse.com`). User accepted the deviation but it's still a gap per the rule. |
| **"Running on AgentCore"** | The AgentCore deployment exists and the container boots. But the default operational path is local. `openclaw.json` says `"mode": "local"`. `eval_config.yaml` says `http://localhost:18789`. The frontend `.env.example` defaults to `ws://localhost:18789`. The README lists AgentCore as "Step 13 (Optional)". The pipeline test script imports Python modules directly — no gateway at all. Earlier eval runs leaked `localhost:18789` in agent responses. Calling this "deployed on AgentCore" is misleading — it's deployed but not used by default. |

---

## 4. What is MetaClaw?

MetaClaw is OpenClaw's cross-run learning memory for the 23-stage pipeline. It's a small local persistence layer — stage failures, recoveries, and successes are written as JSON "lessons" to `openclaw/metaclaw_lessons/`, and future runs for the same ticker read the most relevant lessons back in as LLM advice.

### The three API calls

| Function | Purpose | Called when |
|----------|---------|-------------|
| `record_lesson(run_id, stage, lesson_type, detail, severity, ticker)` | Append a new lesson file | On stage recovery, stage failure, pipeline success |
| `get_lessons(ticker, stage, limit)` | Retrieve filtered past lessons | Before each stage of a new run |
| `apply_lessons(ticker, stage)` | Return human-readable advice strings for the LLM prompt | Before each stage — wrapped in `try/except; pass` so it's advisory-only and never blocks the pipeline |

### Schema (from an actual lesson file in this repo)

```json
{
  "run_id": "arc-4cc614f6308e",
  "stage": 9,
  "lesson_type": "failure",
  "detail": "Stage 9 failed permanently: DCF model error: revenue_ttm must be positive",
  "severity": "error",
  "ticker": "NVDA",
  "timestamp": "2026-04-09T19:32:56.298988+00:00"
}
```

Next NVDA run reading this sees: "past lesson from stage 9 — DCF needs positive revenue_ttm. Validate input before calling the model."

### Hard MNPI rule

The module docstring enforces: `lesson.detail` must NEVER contain holdings amounts, trade intentions, wire details, or any MNPI. Only operational metadata — stage numbers, error types, recovery info. This is what makes it safe to read these lessons back as LLM context.

### 1000-file cap with auto-cleanup

`_enforce_limit()` keeps only the most recent 1000 lessons. Oldest get deleted. Prevents unbounded growth.

### Honest status

- **Code**: working
- **Data**: 2 lessons from 1 real pipeline run
- **Usefulness**: underwhelming until the lesson corpus grows to dozens/hundreds of runs
- **Exercise path**: run `test-pipeline.py` repeatedly against different tickers and the corpus builds naturally

If you want it to matter in run14 evaluations, schedule a cron job that runs the full pipeline once per ticker in the seed data (30 companies), which seeds ~30 successful lessons + a variable number of stage-failure lessons. Then run14's LLM calls to `apply_lessons()` will actually return something.

---

## 5. What Needs to Change for Zero Local Processes

Right now, the system works but depends on a local OpenClaw Gateway process on the developer's laptop. Here are the 6 changes needed to make AgentCore the default and eliminate all local processes:

| # | Change | File(s) | Current Value | Target Value |
|---|--------|---------|---------------|--------------|
| 1 | Gateway mode → deployed | `openclaw/openclaw.json` | `"mode": "local"` | `"mode": "deployed"` (or remove mode, let AgentCore container handle it) |
| 2 | Eval config → AgentCore endpoint | `evaluation/eval_config.yaml` | `gateway_url: "http://localhost:18789"` | `gateway_url: "https://bedrock-agentcore.us-east-1.amazonaws.com/..."` or remove (eval uses SDK now) |
| 3 | Frontend → AgentCore WebSocket | `frontend/.env.example` | `ws://localhost:18789` | `wss://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/ARN/ws` |
| 4 | CORS defaults → CloudFront domain | `aws/samconfig.toml`, `openclaw.json` | `http://localhost:5173` | `https://d3t2yuearw7l53.cloudfront.net` |
| 5 | Langfuse → self-host in VPC | `LANGFUSE_BASE_URL` everywhere | `https://us.cloud.langfuse.com` | Fargate service in VPC (FSI compliance requirement) |
| 6 | Make AgentCore the default path | `README.md` step ordering | AgentCore is "Step 13 (Optional)" | AgentCore is the primary path; local is the optional debug path |

Until all 6 are done, the honest answer to "where is OpenClaw running?" is: on the developer's laptop.

---

## 6. Bottom Line

- OpenClaw is real. The gateway, pipeline, MCP servers, financial models, and eval framework all work. Claude Sonnet 4.6 is the actual LLM. The path from laptop → local OpenClaw Gateway → Bedrock → Lambda MCP → Salesforce is verifiable.
- But the gateway runs locally. `openclaw.json` mode is `"local"`. The eval config points to `localhost:18789`. The pipeline test imports Python directly. AgentCore exists and boots but is not the default operational path.
- The 71.3% pass rate (run13) is achieved through a genuinely functional agent. The 19 remaining failures are judge/data-quality issues, not infrastructure theater.
- **Narrow theater**: multi-channel notifications (no real tokens, stage 23 logs only) and MuleSoft (docs only).
- **Underused**: MetaClaw (2 lessons, needs dozens).
- **Oversold**: "Dual trust layer" — functionally single-trust right now because `new-org` doesn't have Einstein Models API provisioned. "Running on AgentCore" — deployed but not the default path.

### Recommended next steps

1. **Make AgentCore the default** — flip the 6 config changes in section 5. This is a half-day of work, not an architecture change.
2. **Build `mulesoft-mock`** as a 4th MCP-style server. 1 day of work. Closes Phase 6 (15 tasks → done in simulated mode), closes Security Finding #13 (HITL enforcement becomes code, not prompt), and unlocks the L5 action queries in the eval matrix. Swap to real MuleSoft later = handler-body change, not architecture change.
