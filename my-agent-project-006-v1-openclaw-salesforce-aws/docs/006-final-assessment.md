# Project 006: Final Design vs Implementation Assessment

> Date: July 2025
> Method: Complete fresh read of every source file against the design doc's 71 tasks across 6 phases
> Assessor: Independent code review — no copy from prior assessments

---

## 1. Summary Scorecard

| Phase | Tasks | Done | Done (caveat) | Partial | Not Done | Deviated |
|-------|-------|------|----------------|---------|----------|----------|
| 1 Foundation | 12 | 4 | 4 | 2 | 2 | 0 |
| 2 MCP Servers | 8 | 8 | 0 | 0 | 0 | 0 |
| 3 Pipeline | 12 | 6 | 1 | 3 | 0 | 2 |
| 4 Models | 10 | 6 | 1 | 0 | 1 | 2 |
| 5 Production | 14 | 5 | 3 | 2 | 4 | 0 |
| 6 MuleSoft | 15 | 0 | 0 | 0 | 15 | 0 |
| **Total** | **71** | **29** | **9** | **7** | **22** | **4** |

**Bottom line: 38 of 71 tasks done or done-with-caveat (54%). 7 partial (10%). 22 not done (31%). 4 deviated (6%).**

---

## 2. Phase-by-Phase Task Assessment

### Phase 1: Foundation (12 tasks)

| # | Task | Verdict | Evidence |
|---|------|---------|----------|
| 1.1 | AWS: VPC, IAM, Secrets Manager | **DONE (caveat)** | `setup-secrets.sh` fully automated: auto-fetches SF creds via CLI, reads MCP Gateway from SAM stack, generates tokens, merges secrets. No VPC — AgentCore uses PUBLIC network mode. |
| 1.2 | Deploy OpenClaw on AgentCore | **DONE** | Real agent ARN `fsi_research_agent-Sr1m3j3MUh`, ECR repo, CodeBuild. `adapter.js` bridges AgentCore HTTP to Gateway REST. `/hooks/agent` returns `{"ok":true,"runId":"..."}`. Gateway starts, queries accepted. |
| 1.3 | Bedrock model access | **DONE** | `openclaw.json` has Claude Sonnet 4.6 + Haiku 4.5. Eval confirms 4/4 queries passed via Bedrock. |
| 1.4 | Bedrock Guardrails | **DONE (caveat)** | Complete CloudFormation template: PII masking, CUSIP/ISIN/SWIFT regex, content filtering, denied topics. Caveat: deployment unverified. |
| 1.5 | SF IR_* custom objects | **DONE** | All 5 objects in metadata: IR_Audit_Log__c, IR_Company__c, IR_Coverage__c, IR_Research_Note__c, IR_Watchlist__c. Connected App + Permission Set. |
| 1.6 | SF FSC objects (FinServ__*) | **DONE (caveat)** | `fsc-objects-note.md` documents FSC prerequisite. `seed-04-financial-holdings.apex` creates 60 holdings with FSC check. Pipeline queries FinServ__FinancialHolding__c with graceful fallback. Caveat: requires FSC license. |
| 1.7 | Connected App + OAuth | **DONE (caveat)** | Connected App metadata exists. Frontend uses SF OAuth PKCE. No static gateway token in bundle. Caveat: Secrets Manager needs setup-secrets.sh run. |
| 1.8 | Install salesforce-api skill | **PARTIAL** | No official skill installed. Pipeline uses inline `_sf_soql()` via raw `requests.get()`. CRM queries work but not via the official skill. |
| 1.9 | Seed data | **DONE** | 5 Apex scripts: accounts, companies, coverage, watchlist, notes, audit logs, 60 FSC holdings. Exceeds spec. |
| 1.10 | Langfuse observability | **DONE** | Langfuse Cloud with real API keys. 18 traces captured in eval. User accepted cloud as sufficient. |
| 1.11 | Connect Langfuse to OpenClaw | **DONE** | Pipeline creates traces per stage. `_log_audit()` creates Langfuse events. Confirmed working. |
| 1.12 | Test: L1 via Slack | **PARTIAL** | Q1-CRM passed via CLI. Channel YAMLs have `enabled: true` but need real tokens. Not tested via Slack. |


### Phase 2: MCP Servers (8 tasks)

| # | Task | Verdict | Evidence |
|---|------|---------|----------|
| 2.1 | SEC EDGAR MCP server | **DONE** | `sec-edgar/app.py`: 5 tools (get_10k, get_10q, get_8k, get_insider_transactions, search_filings). Real SEC EDGAR API with rate limiting, CIK cache. Exceeds 4-tool spec. |
| 2.2 | Market Data MCP server | **DONE** | `market-data/app.py`: 5 tools (get_quote, get_price_history, get_analyst_consensus, get_options_chain, get_earnings_calendar). Real Alpha Vantage API. CSV parsing for earnings. Exceeds 4-tool spec. |
| 2.3 | News Search MCP server | **DONE** | `news-search/app.py`: 3 tools (search_financial_news, get_headlines, get_news_coverage). Real Tavily API. Renamed from get_news_sentiment per tech stack decision. |
| 2.4 | API Gateway: all 3 behind gateway | **DONE** | `sam-template.yaml`: single API Gateway, 3 routes, API key auth, DLQ (SQS), X-Ray tracing, CORS locked to FrontendOrigin, usage plan (25 RPS / 50 burst), reserved concurrency (10), 45s timeout. |
| 2.5 | Connect MCP servers to OpenClaw | **DONE** | `openclaw.json` has 3 MCP servers via stdio transport using `mcp-rest-bridge.mjs`. Eval confirms MCP calls work. |
| 2.6 | Langfuse: trace MCP calls | **DONE** | Pipeline creates Langfuse spans for every MCP call. 18 traces captured in eval. |
| 2.7 | Test: L1 queries (filing, news) | **DONE** | Q2-MCP passed: "Show me NVIDIA's latest 10-Q" returned full 10-Q breakdown (revenue, net income, EPS, OCF). |
| 2.8 | Test: L2 queries (multi-source) | **DONE** | Q3-Multi passed: "What's happening with NVIDIA ahead of earnings?" synthesized news + SEC EDGAR + CRM. |

### Phase 3: AutoResearchClaw Pipeline (12 tasks)

| # | Task | Verdict | Evidence |
|---|------|---------|----------|
| 3.1 | Fork AutoResearchClaw repo | **DEVIATED** | `config.arc.yaml` exists with FSI config. But `pipeline.py` is a ~1,400-line custom pipeline — NOT a fork. Design says "Fork and adapt — do NOT build a custom pipeline." |
| 3.2 | Replace academic skills with MCP | **DONE** | Stages 3-5 call MCP servers (market-data, news-search, sec-edgar) via `_mcp_call()`. Stage 6 uses LLM for transcript analysis. |
| 3.3 | Add SF data collection | **DONE** | Stage 2 pulls IR_Company__c, IR_Coverage__c, IR_Watchlist__c, IR_Research_Note__c. Queries FinServ__FinancialHolding__c with graceful fallback. MNPI stripped via `filter_mnpi()`. |
| 3.4 | Adapt output: research brief | **DONE** | Stages 14-19: thesis (bull/bear/base), catalysts, risks, rating (Buy/Hold/Sell), target price (weighted DCF 40% + comps 30% + MC 30%). Stage 19 assembles structured brief with anti-fabrication ledger. |
| 3.5 | Compliance screening pre-publish | **DONE** | Stage 20 delegates to `run_compliance_screening()`: restricted list, MNPI lookback, trading window, concentration. Plus anti-fabrication check. |
| 3.6 | SF publish: Stage 22 | **DONE** | Stage 22 creates IR_Research_Note__c via SF REST with all fields. Blocks publish if compliance FAIL. |
| 3.7 | Audit: Stage 23 | **DONE** | Stage 23 creates IR_Audit_Log__c. `_log_audit()` dual-writes (SF + Langfuse) at every stage via `logger.py`. |
| 3.8 | HITL co-pilot gates | **DONE (caveat)** | Gates at stages 7, 13, 21 (not 5, 8, 9, 17, 20 as in design). `config.arc.yaml` updated to match with documented rationale. Pipeline code `HITL_STAGES = {7, 13, 21}` matches config. |
| 3.9 | OpenClaw bridge / Slack notifications | **PARTIAL** | `config.arc.yaml` has `openclaw_bridge: use_message: true`. Channel YAMLs `enabled: true`. But stage 23 only logs via `logger.info()` — no Slack API call or webhook dispatch. |
| 3.10 | Stub financial models | **SUPERSEDED** | Replaced with real models in Phase 4. |
| 3.11 | Langfuse: trace all 23 stages | **DONE** | Every stage creates a Langfuse span. MetaClaw lessons logged. Audit events traced. |
| 3.12 | Test: L4 end-to-end | **PARTIAL** | `test-pipeline.py` runs full 23-stage pipeline with auto-approved HITL gates. Q4-Analysis passed (DCF output). But no evidence of a complete 23-stage run completing all stages. |

### Phase 4: Financial Modeling (10 tasks)

| # | Task | Verdict | Evidence |
|---|------|---------|----------|
| 4.1 | DCF model | **DONE** | `dcf.py`: 5-year DCF, Gordon Growth terminal value, sensitivity table (WACC vs terminal growth), input validation, NaN/Inf guards. ~190 lines. |
| 4.2 | Comps | **DONE** | `comps.py`: 5 metrics (PE, EV/EBITDA, P/S, P/B, EV/Revenue), sector averages, relative valuation, implied prices, narrative. Uses pandas. ~210 lines. |
| 4.3 | Monte Carlo | **DONE** | `monte_carlo.py`: GBM simulation, percentiles (P5-P95), skew/kurtosis via scipy, probability above/below current. ~120 lines. |
| 4.4 | Sentiment: news | **DEVIATED** | No standalone skill. Stage 12 does LLM-based sentiment synthesis inline. Correct per tech stack decision (no Comprehend/FinBERT). |
| 4.5 | Sentiment: transcript NLP | **DEVIATED** | Stage 6 does LLM-based transcript analysis inline. Correct per tech stack decision. |
| 4.6 | Configure sandbox | **DONE (caveat)** | `sandbox.py`: subprocess isolation, restricted PYTHONPATH, `resource.setrlimit` (4 GB), AST import validation, 60s timeout. Pipeline calls `run_in_sandbox()` when `config.experiment.mode == "sandbox"`. Caveat: opt-in, not default. |
| 4.7 | Replace stubs in pipeline | **DONE** | Stages 9-11 call `run_dcf()`, `run_comps()`, `run_monte_carlo()` (direct or via sandbox). |
| 4.8 | Langfuse: trace models | **DONE** | Pipeline creates spans for model execution stages. |
| 4.9 | Test: L3 queries | **DONE** | Q4-Analysis passed: 3-scenario DCF (Bear $78, Base $184, Bull $403). |
| 4.10 | Test: L4 re-run with real models | **PARTIAL** | `test-pipeline.py` exists. No evidence of a successful complete run. |

### Phase 5: Production Hardening (14 tasks)

| # | Task | Verdict | Evidence |
|---|------|---------|----------|
| 5.1 | Einstein Trust Layer (SF Models API) | **DONE** | `trust_layer.py`: `is_trust_layer_available()` probes Models API, `generate_with_trust_layer()` routes through SF with injection/PII/toxicity detection. Pipeline `_llm_generate_with_trust()` used in stages 14 + 17. Graceful Bedrock fallback. Documented in `einstein-trust-layer-integration.md`. |
| 5.2 | Bedrock Guardrails: custom regex | **DONE** | CUSIP, ISIN, AccountNumber, SWIFTCode, RoutingNumber — all ANONYMIZE. |
| 5.3 | Bedrock Guardrails: denied topics | **DONE** | InsiderTrading, UnauthorizedTrading, DataDeletion with examples. |
| 5.4 | Compliance-screening skill | **DONE** | `screening.py`: 4 FINRA checks with SOQL escaping. `mnpi_filter.py`: strips 8 MNPI field types, LLM-safe summaries. Pipeline stage 20 + stage 2 use both. |
| 5.5 | Audit-logging skill (dual-write) | **DONE** | `logger.py`: dual-writes to SF IR_Audit_Log__c + Langfuse. Shared trace_id. Field truncation. Graceful failure. |
| 5.6 | MetaClaw cross-run learning | **DONE** | `metaclaw.py`: `record_lesson()`, `get_lessons()`, `apply_lessons()`. Pipeline calls before every stage and on recovery/failure/success. 1000-file cap. |
| 5.7 | Multi-channel: WhatsApp | **DONE (caveat)** | `whatsapp.yaml` `enabled: true` with env var refs. Setup guide exists. Caveat: needs real Meta API tokens. |
| 5.8 | Multi-channel: Telegram | **DONE (caveat)** | `telegram.yaml` `enabled: true`. Setup guide exists. Caveat: needs real bot token. |
| 5.9 | Secrets Manager auto-rotation | **DONE (caveat)** | `secrets-rotation.yaml`: CloudFormation with Lambda + EventBridge (12-hour schedule). Caveat: deployment unverified. |
| 5.10 | Build 25-query eval suite | **DONE** | `run_suite.py`: LLM-as-Judge, 7-dimension rubric, Langfuse scoring. 150-query matrix (exceeds spec). |
| 5.11 | LLM-as-Judge rubric | **DONE** | 7 dimensions (exceeds 5-dimension spec). Per-level thresholds. |
| 5.12 | Run full suite, establish baseline | **NOT DONE** | 4/150 queries run. Performance baseline blank. |
| 5.13 | Security review | **PARTIAL** | 15 findings identified. 8 remediated. 7 still open (see Section 4). |
| 5.14 | Performance test | **NOT DONE** | `performance-baseline.md` blank. Zero measurements. |

### Phase 6: MuleSoft Action Execution (15 tasks)

| # | Task | Verdict |
|---|------|---------|
| 6.1-6.15 | All 15 MuleSoft tasks | **NOT DONE** (all 15) |

`mulesoft-api/SKILL.md` is documentation only (curl examples, API specs, HITL flow). Zero Python code. Requires MuleSoft Anypoint Platform access.


---

## 3. Design Claims vs Reality (8 Claims)

### Claim 1: "AgentCore from day one"

Design: "Single environment. No migration. AgentCore from day one."

**Reality: TRUE.** AgentCore deployed with real agent ID `fsi_research_agent-Sr1m3j3MUh`. `adapter.js` bridges AgentCore HTTP to OpenClaw Gateway REST. The `/hooks/agent` endpoint works (async). Gateway starts, adapter connects, queries accepted.

**Verdict: DONE**

### Claim 2: "12+ channels"

Design: "12+ (Slack, WhatsApp, Telegram, Discord, web, API, etc.)"

**Reality: PARTIALLY TRUE.** Channel YAMLs exist for Slack, WhatsApp, Telegram with `enabled: true`. Web frontend works locally. But zero real channel tokens populated, zero channels connected. Pipeline stage 23 notification only logs.

**Verdict: CONFIG DONE, CONNECTIONS NOT DONE** — 3 channels configured, 0 connected.

### Claim 3: "AutoResearchClaw fork"

Design: "Fork and adapt — do NOT build a custom pipeline."

**Reality: FALSE.** `pipeline.py` is ~1,400 lines of custom code, not a fork. The `config.arc.yaml` references AutoResearchClaw features and the custom pipeline implements them, but the pipeline itself is custom.

**Verdict: DEVIATED** — Custom pipeline works well but violates the design rule.

### Claim 4: "Dual trust layer (Bedrock Guardrails + Einstein Trust Layer)"

Design: "Trust layers: 2 (Bedrock Guardrails + Einstein Trust Layer via SF Models API)"

**Reality: TRUE.** `trust_layer.py` implements Einstein Trust Layer via SF Models API. Pipeline stages 14 and 17 use `_llm_generate_with_trust()`. `bedrock-guardrails.yaml` is a complete CloudFormation template. Both layers implemented with graceful fallback.

**Verdict: DONE**

### Claim 5: "Zero custom security code — all config"

Design: "No custom security code — Bedrock Guardrails + SF Models API = zero build."

**Reality: FALSE.** Significant custom security code was written: `screening.py` (~250 lines), `mnpi_filter.py` (~150 lines), `logger.py` (~150 lines), `mcp_protocol.py` (boundary markers, sanitization, CORS, error handling), `openclawApi.ts` (rate limiter), `index.html` (CSP headers). The "all config" claim was unrealistic for FSI compliance.

**Verdict: FALSE** — Custom security code was necessary and was written.

### Claim 6: "Persistent per-user memory"

Design: "Memory: persistent per-user"

**Reality: FALSE.** AgentCore config shows `memory: { mode: NO_MEMORY }`. Memory is disabled.

**Verdict: NOT DONE**

### Claim 7: "FSC objects"

Design (steering rule 16): FinServ__FinancialAccount__c, FinServ__FinancialHolding__c required.

**Reality: HANDLED GRACEFULLY.** Documentation, seed script (60 holdings), and pipeline code all handle FSC. Pipeline queries FinServ__FinancialHolding__c with try/catch. MNPI fields stripped. Works on FSC orgs, degrades gracefully on standard orgs.

**Verdict: DONE (caveat)** — Code complete. Actual objects require FSC license.

### Claim 8: "salesforce-api official skill"

Design: "Install + configure salesforce-api skill"

**Reality: FALSE.** Not installed. Not in `openclaw.json`. Pipeline uses inline `requests.get()` / `requests.post()` for SOQL.

**Verdict: NOT DONE** — Inline SOQL works but doesn't use the official skill.

---

## 4. Security Findings Status (All 15)

| # | Severity | Finding | Status | Evidence |
|---|----------|---------|--------|----------|
| 1 | CRITICAL | Indirect prompt injection via MCP | **MITIGATED** | `_mcp_text()` wraps output in boundary markers, strips existing markers/system tags. Not fully eliminated but significantly reduced. |
| 2 | CRITICAL | Gateway token in browser bundle | **RESOLVED** | `openclawApi.ts` uses SF OAuth PKCE token. No static gateway token in `.env` or bundle. |
| 3 | HIGH | No MCP input sanitization | **RESOLVED** | `_sanitize_params()` strips non-printable chars, caps strings at 10K, limits arrays to 100. `_validate_params()` does JSON Schema validation. |
| 4 | HIGH | CORS wildcard | **RESOLVED** | `_cors_headers()` reads from env, defaults to `http://localhost:5173`. No wildcard. SAM parameterizes origin. |
| 5 | HIGH | Error message leakage | **RESOLVED** | Generic error to client. Full error logged server-side via `logger.exception()`. |
| 6 | HIGH | No WebSocket rate limiting | **RESOLVED** | Sliding window rate limiter: max 5 messages per 10 seconds in `openclawApi.ts`. |
| 7 | HIGH | MNPI enforcement doc-only | **RESOLVED** | `mnpi_filter.py` strips 8 MNPI field types. `summarize_holdings_safe()` for LLM-safe summaries. Pipeline uses both. |
| 8 | MEDIUM | Static SF access token | **PARTIALLY ADDRESSED** | `secrets-rotation.yaml` CloudFormation exists. `setup-secrets.sh` auto-fetches. Rotation Lambda deployment unverified. |
| 9 | MEDIUM | No auth on eval suite | **OPEN** | `run_suite.py` has no authentication. |
| 10 | MEDIUM | Langfuse sensitive data | **OPEN** | Full SOQL results traced. No data classification or retention policy. |
| 11 | MEDIUM | No CSP on frontend | **RESOLVED** | `index.html` has CSP meta tag with restrictive policy. Plus X-Content-Type-Options and X-Frame-Options. |
| 12 | MEDIUM | Memory without encryption | **N/A** | Memory disabled (`NO_MEMORY`). |
| 13 | MEDIUM | MuleSoft HITL prompt-based | **OPEN** | MuleSoft is documentation-only. No code to enforce. |
| 14 | LOW | No request signing | **OPEN** | API key auth only. No SigV4 or mutual TLS. |
| 15 | LOW | Missing financial regex | **PARTIALLY ADDRESSED** | CUSIP tightened. SWIFT and routing patterns added. Some still broad. |

**Summary: 8 resolved, 1 mitigated, 2 partially addressed, 3 open, 1 N/A.**

---

## 5. What Works End-to-End on AgentCore

**Verified working flow:**
1. AgentCore receives `POST /invocations` with prompt
2. `adapter.js` forwards to OpenClaw Gateway via `/hooks/agent`
3. Gateway returns `{"ok":true,"runId":"..."}` (async)
4. OpenClaw routes to `fsi-research` agent with Claude Sonnet 4.6 (Bedrock)
5. Agent calls MCP servers (SEC EDGAR, Market Data, News) via `mcp-rest-bridge.mjs`
6. Agent queries Salesforce CRM via inline SOQL
7. Agent runs financial models (DCF, comps, Monte Carlo)
8. Langfuse captures traces
9. 4/4 targeted queries passed (L1-CRM, L1-MCP, L2-Multi, L3-Analysis)

**Not working end-to-end:**
- Full 23-stage pipeline (no verified complete run)
- Any messaging channel (config only, no tokens)
- Pipeline notifications to channels (logs only)
- Full eval suite (4/150 queries run)
- MuleSoft actions (documentation only)
- Per-user persistent memory (disabled)

---

## 6. What Still Needs Work

### Requires Live Environment Execution
1. Full 23-stage pipeline end-to-end run (tasks 3.12, 4.10)
2. Run full 150-query eval suite (task 5.12)
3. Record performance measurements (task 5.14)
4. Close remaining open security findings (#9, #10, #14)

### Requires External Dependencies
5. Slack integration with real tokens + pipeline notification wiring (tasks 1.12, 3.9)
6. WhatsApp + Telegram with real API tokens (tasks 5.7, 5.8)
7. All 15 MuleSoft tasks (needs Anypoint Platform access)
8. FSC objects on org (needs FSC license)

### Design Gaps That Remain
9. salesforce-api official skill not installed (task 1.8)
10. Custom pipeline instead of AutoResearchClaw fork (task 3.1)
11. Per-user persistent memory disabled (Claim 6)

---

## 7. Reproducibility Checklist

| Step | Command | Status |
|------|---------|--------|
| Clone repo | `git clone` | Ready |
| Create SF scratch org | `sf org create scratch` | Ready |
| Deploy SF metadata | `sf project deploy start` | Ready — 5 objects, Connected App, Permission Set |
| Run seed data | `sf apex run --file scripts/apex/seed-*.apex` | Ready — 5 scripts, idempotent, FSC-aware |
| Deploy MCP servers | `sam deploy --guided` | Ready — `aws/sam-template.yaml` |
| Setup secrets | `./scripts/aws/setup-secrets.sh` | Ready — auto-populates from CLI + SAM |
| Deploy Guardrails | `aws cloudformation deploy` | Ready — `aws/guardrails/bedrock-guardrails.yaml` |
| Deploy rotation | `aws cloudformation deploy` | Ready — `aws/secrets-rotation.yaml` |
| Deploy to AgentCore | `agentcore deploy` | Ready — Dockerfile, adapter, start.sh |
| Install frontend | `cd frontend && npm install` | Ready |
| Run frontend | `npm run dev` | Ready |
| Run eval suite | `python evaluation/run_suite.py` | Ready — needs env vars |
| Run pipeline test | `python scripts/test-pipeline.py` | Ready — needs env vars |

**Missing:** No single "deploy everything" script. No CI/CD pipeline definition. Channel tokens, FSC license, and MuleSoft access must be obtained manually.

**Verdict: Reproducible with manual orchestration.** Each step has scripts/templates, but no unified deploy command.
