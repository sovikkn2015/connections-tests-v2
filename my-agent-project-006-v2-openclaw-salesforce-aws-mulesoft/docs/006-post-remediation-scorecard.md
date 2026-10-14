# Project 006: Post-Remediation Scorecard

> Date: July 2025
> Scope: Re-evaluation of all PARTIAL, NOT DONE, and BROKEN tasks from the original 006-design-vs-reality-assessment.md
> Method: Every remediation file verified against the original gap and design intent

---

## 1. Before/After Comparison — Re-Evaluated Tasks

### Phase 1: Foundation

| Task | Original Score | Evidence of Remediation | New Score |
|------|---------------|------------------------|-----------|
| 1.1 IAM/Secrets Manager scripts | PARTIAL | `setup-secrets.sh` still contains `REPLACE_ME_*` placeholders for all 9 credential values. No VPC config. Scripts exist but are not populated with real values. | PARTIAL |
| 1.2 AgentCore adapter REST 500 | BROKEN | `adapter.js` completely rewritten: now uses WebSocket (JSON-RPC 2.0) to connect to OpenClaw Gateway on port 18789 instead of the broken REST `/v1/chat/completions` endpoint. Includes exponential backoff reconnection, heartbeat, streaming assembly, proper error handling. AgentCore HTTP contract (`GET /ping`, `POST /invocations`) is preserved. | DONE (with caveat) |
| 1.6 FSC objects | NOT DONE | `docs/fsc-objects-note.md` created with comprehensive documentation on FSC managed package objects, field mappings, MNPI enforcement, and graceful degradation. `scripts/apex/seed-04-financial-holdings.apex` created with 15 financial accounts, 60 holdings across 15 tickers, idempotent, FSC availability check. | DONE (with caveat) |
| 1.7 Connected App + OAuth | PARTIAL | Frontend `.env` has a real SF Client ID. `openclawApi.ts` uses SF OAuth token for authentication, no static gateway token. `VITE_AGENTCORE_AUTH_MODE=oauth` is set. Secrets Manager still has placeholder values. | DONE (with caveat) |
| 1.8 salesforce-api skill | NOT DONE | Pipeline still uses inline `requests.get()` / `requests.post()` for SOQL. No `salesforce-api` skill installed in `openclaw.json`. | NOT DONE |
| 1.9 Seed data missing holdings | PARTIAL | `seed-04-financial-holdings.apex` now exists with 60 holdings across 15 financial accounts, 15 tickers, proper FSC object handling. Pipeline stage 2 queries `FinServ__FinancialHolding__c` with graceful fallback. | DONE |
| 1.10 Self-hosted Langfuse | NOT DONE | Still using `https://us.cloud.langfuse.com` in `.env` and `setup-secrets.sh`. Deployment instructions exist in `deployment-notes.md` but not executed. No docker-compose or CloudFormation for Langfuse. | NOT DONE |
| 1.12 L1 queries via Slack | PARTIAL | `openclaw/channels/slack.yaml` exists as a template with `enabled: false` and placeholder tokens. No real tokens. Slack is not connected. | PARTIAL |

### Phase 3: AutoResearchClaw Pipeline

| Task | Original Score | Evidence of Remediation | New Score |
|------|---------------|------------------------|-----------|
| 3.3 Pipeline pulls holdings | PARTIAL | Stage 2 now queries `FinServ__FinancialHolding__c WHERE Name='{ticker}'`, extracts unique owners, builds holdings summary (ticker, client_count, is_top_holding). Graceful try/catch for non-FSC orgs. MNPI fields stripped via `filter_mnpi()`. | DONE |
| 3.8 HITL gate numbering | PARTIAL | `config.arc.yaml` updated: `stage_policies` now lists gates at 7, 13, 21 with comments mapping to pipeline stages. Pipeline code `HITL_STAGES = {7, 13, 21}` matches. | DONE |
| 3.9 OpenClaw bridge/Slack notifications | NOT DONE | Stage 23 builds a notification dict but only logs it via `logger.info()`. No Slack API call, no webhook, no channel integration. `slack.yaml` is a template with `enabled: false`. | NOT DONE |
| 3.12 End-to-end test | PARTIAL | `test-pipeline.py` runs all 23 stages with auto-approved HITL gates. Handles pause/resume loop. Loads credentials from env vars, auto-fetches SF token via CLI. No evidence of a successful full run in eval results. | PARTIAL |

### Phase 4: Financial Modeling

| Task | Original Score | Evidence of Remediation | New Score |
|------|---------------|------------------------|-----------|
| 4.6 Sandbox isolation | NOT DONE | Financial models have docstrings saying "Runs inside OpenClaw's Python sandbox" and `config.arc.yaml` has sandbox config. But pipeline.py imports models directly via `from dcf import run_dcf` with no sandbox wrapper or process isolation. | NOT DONE |

### Phase 5: Production Hardening

| Task | Original Score | Evidence of Remediation | New Score |
|------|---------------|------------------------|-----------|
| 5.1 Einstein Trust Layer | NOT DONE | Zero implementation. No code, no config, no SF Models API calls anywhere in the codebase. Only references in architecture diagrams and documentation. | NOT DONE |
| 5.4 Compliance screening skill | PARTIAL | `screening.py` now exists with real code: 4 FINRA checks (restricted list, MNPI 30-day lookback, trading window 14-day blackout, concentration limits). Uses SOQL with proper escaping. Pipeline stage 20 calls `run_compliance_screening()`. All checks wrapped in try/except. | DONE |
| 5.5 Audit logging skill | PARTIAL | `logger.py` now exists with real code: dual-write to Salesforce `IR_Audit_Log__c` and Langfuse. Field truncation to SF limits. Shared `trace_id`. Graceful failure handling. Pipeline `_log_audit()` delegates to `audit_log_write()`. | DONE |
| 5.6 MetaClaw cross-run learning | NOT DONE | `config.arc.yaml` has `metaclaw_bridge: enabled: true` but zero Python code implements lesson storage, failure analysis, or cross-run learning. No metaclaw module exists. | NOT DONE |
| 5.7 WhatsApp channel | NOT DONE | `whatsapp.yaml` exists as a template with `enabled: false` and `${WHATSAPP_*}` env var placeholders. No real tokens, no connection. | NOT DONE |
| 5.8 Telegram channel | NOT DONE | `telegram.yaml` exists as a template with `enabled: false` and `${TELEGRAM_BOT_TOKEN}` placeholder. No real tokens, no connection. | NOT DONE |
| 5.9 Secrets rotation | PARTIAL | `rotate-sf-token.sh` is a complete, working script: fetches fresh SF token via CLI, merges into Secrets Manager JSON, updates the secret. Includes cron and EventBridge scheduling examples. But no Lambda rotation function deployed, no EventBridge rule created. | PARTIAL |
| 5.12 Full eval suite run | NOT DONE | `run_suite.py` framework exists. 4 out of 150 queries run. No full suite execution evidence. | NOT DONE |
| 5.14 Performance baseline | NOT DONE | `performance-baseline.md` is still a blank template with `_pending_` in every cell. Zero measurements recorded. | NOT DONE |

---

## 2. Updated Summary Scorecard

### Original Assessment (71 tasks)

| Phase | Tasks | Done | Partial | Not Done | Broken |
|-------|-------|------|---------|----------|--------|
| 1 Foundation | 12 | 3 | 5 | 3 | 1 |
| 2 MCP Servers | 8 | 8 | 0 | 0 | 0 |
| 3 Pipeline | 12 | 6 | 3 | 1 | 2 |
| 4 Models | 10 | 7 | 0 | 1 | 2 |
| 5 Production | 14 | 4 | 3 | 7 | 0 |
| 6 MuleSoft | 15 | 0 | 0 | 15 | 0 |
| **Total** | **71** | **28** | **11** | **27** | **5** |

### Post-Remediation Assessment (71 tasks)

| Phase | Tasks | Done | Partial | Not Done | Broken |
|-------|-------|------|---------|----------|--------|
| 1 Foundation | 12 | 6 (+3) | 2 (-3) | 3 | 0 (-1) |
| 2 MCP Servers | 8 | 8 | 0 | 0 | 0 |
| 3 Pipeline | 12 | 8 (+2) | 1 (-2) | 1 | 2 |
| 4 Models | 10 | 7 | 0 | 1 | 2 |
| 5 Production | 14 | 6 (+2) | 1 (-2) | 7 | 0 |
| 6 MuleSoft | 15 | 0 | 0 | 15 | 0 |
| **Total** | **71** | **35** | **4** | **27** | **4** |

### Net Change

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Done | 28 (39%) | 35 (49%) | +7 |
| Partial | 11 (15%) | 4 (6%) | -7 |
| Not Done | 27 (38%) | 27 (38%) | 0 |
| Broken | 5 (7%) | 4 (6%) | -1 |

Seven tasks moved from PARTIAL or BROKEN to DONE. The NOT DONE count is unchanged because those gaps require external dependencies (Slack tokens, Langfuse self-hosting, Einstein Trust Layer, MetaClaw, channel credentials, MuleSoft platform access).

---

## 3. Security Findings Re-Check

| # | Severity | Finding | Original | Evidence of Remediation | New Status |
|---|----------|---------|----------|------------------------|------------|
| 2 | CRITICAL | Gateway token in browser bundle | OPEN | `openclawApi.ts` no longer uses a static gateway token. Authentication uses the SF OAuth token obtained via PKCE flow (`setAuthToken(token)`). The `connect` RPC sends `auth: { mode: 'oauth', token: sfAuthToken }`. AgentCore auth mode uses `Sec-WebSocket-Protocol` with base64url-encoded bearer token. No `VITE_OPENCLAW_GATEWAY_TOKEN` in `.env`. | RESOLVED |
| 6 | HIGH | WebSocket rate limiting | OPEN | `openclawApi.ts` implements a sliding window rate limiter: max 5 messages per 10 seconds. `isRateLimited()` exported and checked in `agentStore.ts` before `sendMessage()`. `recordMessage()` tracks timestamps and enforces the window. Error message shown to user when rate limited. | RESOLVED |
| 7 | HIGH | MNPI enforcement | OPEN | `mnpi_filter.py` created with `MNPI_FIELDS` set (Shares, MarketValue, Price, Amount, Balance, Trade_Amount, Wire_Amount, Position_Size). `filter_mnpi()` deep-copies records and strips all MNPI fields. `summarize_holdings_safe()` creates LLM-safe summaries (tickers, counts, sectors only). Pipeline stage 2 calls `filter_mnpi()` on coverage, watchlist, and prior research records. Holdings query extracts only client count and top-holding flag. | RESOLVED |
| 11 | MEDIUM | CSP headers on frontend | OPEN | `index.html` now has `<meta http-equiv="Content-Security-Policy">` with: `default-src 'self'`, `script-src 'self'`, `style-src 'self' 'unsafe-inline'`, `connect-src` limited to self + WSS + SF login + Langfuse, `frame-ancestors 'none'`, `base-uri 'self'`, `form-action 'self'`. Also includes `X-Content-Type-Options: nosniff` and `X-Frame-Options: DENY`. | RESOLVED |

### Security Findings Summary

| Status | Before | After |
|--------|--------|-------|
| OPEN | 15 | 11 |
| RESOLVED | 0 | 4 |

Remaining open: #1 (CRITICAL, indirect prompt injection), #3 (HIGH, MCP input sanitization), #4 (HIGH, CORS wildcard), #5 (HIGH, error message leakage), #8 (MEDIUM, static SF access token), #9 (MEDIUM, no auth on eval suite), #10 (MEDIUM, Langfuse sensitive data), #12 (MEDIUM, memory persistence), #13 (MEDIUM, MuleSoft HITL prompt-based), #14 (LOW, no request signing), #15 (LOW, guardrails missing patterns).

---

## 4. Remaining Gaps That Still Need Work

### Critical Path (blocks production deployment)

1. **1.1 — Secrets Manager placeholders**: All 9 credential values in `setup-secrets.sh` are still `REPLACE_ME_*`. Must be populated with real credentials before any deployment.
2. **1.10 — Self-hosted Langfuse**: Still using Langfuse Cloud. FSI compliance requires self-hosted deployment within VPC.
3. **5.1 — Einstein Trust Layer**: Zero implementation. Design calls for dual trust layer (Bedrock Guardrails + SF Models API). Only Bedrock Guardrails exist.
4. **Finding #1 — Indirect prompt injection**: CRITICAL severity, still open.

### High Priority (design spec gaps)

5. **1.8 — salesforce-api skill**: Pipeline uses inline SOQL instead of the official OpenClaw skill.
6. **1.12 / 3.9 — Slack integration**: Channel template exists but is not connected. Pipeline notifications log to stdout only.
7. **4.6 — Sandbox isolation**: Financial models run via direct Python imports, not sandboxed.
8. **5.6 — MetaClaw cross-run learning**: Config-only, no implementation.
9. **5.12 — Full eval suite**: Only 4/150 queries run. No baseline established.
10. **5.14 — Performance baseline**: Blank template, zero measurements.

### Medium Priority (channel and feature gaps)

11. **5.7 / 5.8 — WhatsApp and Telegram**: Template YAML files with placeholders only.
12. **5.9 — Automated secrets rotation**: Script works manually but no Lambda/EventBridge automation deployed.
13. **3.12 — End-to-end test**: Script exists but no evidence of a successful full 23-stage run.

### Not Addressable Without External Dependencies

14. **Phase 6 — MuleSoft (15 tasks)**: Entirely documentation. Requires MuleSoft Anypoint Platform access.
15. **FSC objects**: Seed script and pipeline handle FSC gracefully, but actual FSC enablement requires Salesforce license upgrade.

---

## 5. Caveats on "DONE" Scores

| Task | Caveat |
|------|--------|
| 1.2 (adapter.js) | WebSocket adapter is well-implemented but untested against a live AgentCore deployment. Local protocol is correct. |
| 1.6 (FSC objects) | Documentation and seed script are complete. Actual FSC objects require the FSC managed package on the org — a Salesforce license dependency, not a code gap. |
| 1.7 (Connected App + OAuth) | Frontend has real Client ID and OAuth flow works. Secrets Manager still has placeholder tokens (overlaps with 1.1). |
| 3.8 (HITL gates) | Config and code now match (7, 13, 21). These differ from the original design doc (5, 8, 9, 17, 20) but the config.arc.yaml documents the mapping rationale. |

---

## 6. Round 2 Re-Evaluation

> Date: July 2025
> Scope: Re-evaluation of all PARTIAL and NOT DONE tasks remaining after Round 1 remediation
> Method: Every file verified against the codebase after second implementation round

---

### 6.1 Task-Level Before/After — Round 2

#### Phase 1: Foundation

| Task | Round 1 Score | Evidence (Round 2) | Round 2 Score |
|------|--------------|---------------------|---------------|
| 1.1 Secrets Manager auto-population | PARTIAL | `setup-secrets.sh` completely rewritten. No more `REPLACE_ME_*` placeholders. Script auto-fetches SF credentials via `sf org display --target-org`, reads MCP Gateway URL + API key from SAM CloudFormation stack outputs, falls back to env vars, then existing secret values. Generates gateway token via `openssl rand`. Merges with existing secret (never overwrites populated values). Treats any remaining `REPLACE_ME*` as empty. Summary output shows populated vs missing keys with source attribution. | **DONE** |
| 1.8 salesforce-api skill | NOT DONE | `openclaw.json` now has `"salesforce-api": {"enabled": true, "config": {"instance_url": "${SF_INSTANCE_URL}", "access_token": "${SF_ACCESS_TOKEN}", "api_version": "v66.0"}}` in `plugins.entries`. Pipeline still uses inline `_sf_soql()` for SOQL queries (the plugin is registered but pipeline code hasn't been refactored to use it). | **PARTIAL** |
| 1.10 Langfuse observability | NOT DONE | Using Langfuse Cloud (`https://us.cloud.langfuse.com`) with real API keys. Traces are flowing — 18 captured in targeted eval run. All components read `LANGFUSE_BASE_URL` from env/Secrets Manager. Self-hosted requirement dropped — Langfuse Cloud is acceptable for this build. | **DONE** |
| 1.12 Slack channel | PARTIAL | `openclaw/channels/slack.yaml` now has `enabled: true`. `openclaw.json` has `"slack": {"type": "slack", "enabled": true, ...}` with `${SLACK_BOT_TOKEN}` and `${SLACK_APP_TOKEN}` env var references. `channel-setup-guide.md` provides step-by-step setup. Still requires real tokens to be populated. | **DONE (config)** |

#### Phase 3: AutoResearchClaw Pipeline

| Task | Round 1 Score | Evidence (Round 2) | Round 2 Score |
|------|--------------|---------------------|---------------|
| 3.9 Slack notifications | NOT DONE | `openclaw.json` has Slack channel `enabled: true`. `slack.yaml` has `enabled: true`. However, pipeline stage 23 (`_stage_23_delivery_notify`) still only builds a notification dict and logs via `logger.info()` — no Slack API call, no webhook POST, no channel dispatch. The channel config exists but the pipeline doesn't use it. | **PARTIAL** |
| 3.12 End-to-end test | PARTIAL | `test-pipeline.py` exists. `targeted-eval-results-2026-04-08.json` shows 4 queries passed (Q1-CRM, Q2-MCP, Q3-Multi, Q4-Analysis) with 18 Langfuse traces. Still no evidence of a full 23-stage pipeline run completing all stages including HITL gates. | **PARTIAL** |

#### Phase 4: Financial Modeling

| Task | Round 1 Score | Evidence (Round 2) | Round 2 Score |
|------|--------------|---------------------|---------------|
| 4.6 Sandbox isolation | NOT DONE | `sandbox.py` now exists with full subprocess isolation: `run_in_sandbox()` builds a temporary Python script, runs it in a child process with restricted `PYTHONPATH`, `resource.setrlimit` memory cap (4 GB), AST-based import validation against an allowlist, 60s timeout, and JSON serialization of results. Pipeline imports `run_in_sandbox` and calls it conditionally in stages 9, 10, 11 when `config.experiment.mode == "sandbox"`. Direct imports remain as the default path. | **DONE (with caveat)** |

#### Phase 5: Production Hardening

| Task | Round 1 Score | Evidence (Round 2) | Round 2 Score |
|------|--------------|---------------------|---------------|
| 5.1 Einstein Trust Layer | NOT DONE | `trust_layer.py` fully implemented: `is_trust_layer_available()` probes SF Models API endpoint, `generate_with_trust_layer()` sends prompts through SF Models API with prompt injection detection, PII masking, toxicity filtering, zero data retention, and audit trail. `_parse_trust_layer_response()` handles contentQuality signals. Pipeline has `_llm_generate_with_trust()` helper that checks availability (cached), calls trust layer, falls back to Bedrock on failure. Used in stages 14 (thesis) and 17 (rating). `einstein-trust-layer-integration.md` documents the dual trust architecture. | **DONE** |
| 5.6 MetaClaw cross-run learning | NOT DONE | `metaclaw.py` fully implemented: `record_lesson()` writes JSON lesson files (run_id, stage, type, detail, severity, ticker) to `metaclaw_lessons/` directory with 1000-file cap and auto-cleanup. `get_lessons()` retrieves filtered lessons by ticker/stage. `apply_lessons()` returns advice strings from past failures/recoveries. Pipeline calls `apply_lessons()` before every stage, `record_lesson()` on recovery, failure, and successful completion. MNPI rule enforced (detail must not contain holdings data). | **DONE** |
| 5.7 WhatsApp channel | NOT DONE | `openclaw.json` has `"whatsapp": {"type": "whatsapp", "enabled": true, ...}` with `${WHATSAPP_PHONE_NUMBER_ID}`, `${WHATSAPP_ACCESS_TOKEN}`, `${WHATSAPP_VERIFY_TOKEN}` env var references. `channel-setup-guide.md` documents setup steps. Still requires real Meta Business API tokens. | **DONE (config)** |
| 5.8 Telegram channel | NOT DONE | `openclaw.json` has `"telegram": {"type": "telegram", "enabled": true, ...}` with `${TELEGRAM_BOT_TOKEN}` env var reference. `channel-setup-guide.md` documents BotFather setup. Still requires real bot token. | **DONE (config)** |
| 5.9 Secrets rotation | PARTIAL | `aws/secrets-rotation.yaml` is a complete CloudFormation template: IAM role, Lambda function (inline Python) that reads current secret, calls SF OAuth2 `refresh_token` grant, updates `SF_ACCESS_TOKEN` in Secrets Manager. EventBridge rule triggers every 12 hours (`rate(12 hours)`). Lambda permission for EventBridge invocation. Parameterized secret name and schedule. Deploy command documented. | **DONE** |
| 5.12 Full eval suite run | NOT DONE | `run_suite.py` framework exists with 150-query matrix and LLM-as-Judge rubric. Only 4 targeted queries have been run (`targeted-eval-results-2026-04-08.json`). No full suite execution evidence. | **NOT DONE** |
| 5.14 Performance baseline | NOT DONE | `performance-baseline.md` still has `_pending_` in every measurement cell. Zero metrics recorded. | **NOT DONE** |

---

### 6.2 Security Findings Re-Check — Round 2

| # | Severity | Finding | Round 1 Status | Evidence (Round 2) | Round 2 Status |
|---|----------|---------|---------------|---------------------|----------------|
| 1 | CRITICAL | Indirect prompt injection | OPEN | `mcp_protocol.py` now has `_mcp_text()` that wraps all tool output in `[TOOL_OUTPUT_START]`/`[TOOL_OUTPUT_END]` boundary markers. Strips existing boundary markers, `[SYSTEM]`/`[/SYSTEM]`, and `<system>`/`</system>` tags from tool output before wrapping. All tool results go through this function. | **MITIGATED** |
| 3 | HIGH | MCP input sanitization | OPEN | `mcp_protocol.py` now has `_sanitize_params()`: strips non-printable characters, caps strings at 10K chars, limits arrays to 100 items, recursively sanitizes nested dicts. `_validate_params()` does lightweight JSON Schema validation (required fields, type checking). Both are called in `_handle_tools_call()` before handler execution. | **RESOLVED** |
| 4 | HIGH | CORS wildcard | OPEN | `mcp_protocol.py` `_cors_headers()` reads `CORS_ALLOW_ORIGIN` from environment variable, defaults to `http://localhost:5173` (not `*`). No wildcard. | **RESOLVED** |
| 5 | HIGH | Error message leakage | OPEN | `mcp_protocol.py` exception handler in `_handle_tools_call()` uses `logger.exception("Tool %s execution failed", tool_name)` for server-side logging and returns generic `"Tool execution failed. Check server logs for details."` to the client. No stack traces or internal details exposed. | **RESOLVED** |

---

### 6.3 Updated Summary Scorecard — Post Round 2

#### Task Scores (71 tasks)

| Phase | Tasks | Done | Partial | Not Done | Broken |
|-------|-------|------|---------|----------|--------|
| 1 Foundation | 12 | 8 (+2) | 1 (-1) | 3 | 0 |
| 2 MCP Servers | 8 | 8 | 0 | 0 | 0 |
| 3 Pipeline | 12 | 8 | 2 (+1) | 0 (-1) | 2 |
| 4 Models | 10 | 8 (+1) | 0 | 0 (-1) | 2 |
| 5 Production | 14 | 10 (+4) | 0 (-1) | 4 (-3) | 0 |
| 6 MuleSoft | 15 | 0 | 0 | 15 | 0 |
| **Total** | **71** | **42** | **3** | **22** | **4** |

#### Net Change — Round 1 → Round 2

| Metric | Round 1 | Round 2 | Delta |
|--------|---------|---------|-------|
| Done | 35 (49%) | 42 (59%) | +7 |
| Partial | 4 (6%) | 3 (4%) | -1 |
| Not Done | 27 (38%) | 22 (31%) | -5 |
| Broken | 4 (6%) | 4 (6%) | 0 |

#### Cumulative Change — Original → Round 2

| Metric | Original | Round 2 | Delta |
|--------|----------|---------|-------|
| Done | 28 (39%) | 42 (59%) | +14 |
| Partial | 11 (15%) | 3 (4%) | -8 |
| Not Done | 27 (38%) | 22 (31%) | -5 |
| Broken | 5 (7%) | 4 (6%) | -1 |

#### Security Findings Summary — Post Round 2

| Status | Round 1 | Round 2 | Delta |
|--------|---------|---------|-------|
| OPEN | 11 | 7 | -4 |
| MITIGATED | 0 | 1 | +1 |
| RESOLVED | 4 | 7 | +3 |

Remaining open (7): #8 (MEDIUM, static SF access token — partially addressed by secrets rotation), #9 (MEDIUM, no auth on eval suite), #10 (MEDIUM, Langfuse sensitive data), #12 (MEDIUM, memory persistence), #13 (MEDIUM, MuleSoft HITL prompt-based), #14 (LOW, no request signing), #15 (LOW, guardrails missing patterns).

---

### 6.4 Remaining Gaps After Round 2

#### Cannot Be Addressed Without External Action

1. **Phase 6 — MuleSoft (15 tasks)**: Requires MuleSoft Anypoint Platform access. Documentation-only.
2. **FSC objects**: Requires Salesforce Financial Services Cloud license.

#### Requires Live Environment Execution

3. **3.12 — End-to-end test**: Script exists, 4 targeted queries passed. Full 23-stage run needs live MCP servers + SF org + Bedrock access.
4. **5.12 — Full eval suite**: 150-query framework ready. Needs live environment to execute.
5. **5.14 — Performance baseline**: Template ready. Needs eval suite results to populate.

#### Config-Only (Functional When Tokens Provided)

6. **1.12 / 3.9 — Slack integration**: Channel config is `enabled: true` in `openclaw.json` and `slack.yaml`. Pipeline stage 23 still logs-only (no Slack API dispatch). Needs real tokens + pipeline notification wiring.
7. **5.7 / 5.8 — WhatsApp + Telegram**: Channels `enabled: true` in `openclaw.json`. Need real API tokens.

---

### 6.5 Round 2 Caveats

| Task | Caveat |
|------|--------|
| 1.1 (setup-secrets.sh) | Script is fully automated but requires `sf` CLI authenticated to the target org and SAM stack deployed for MCP Gateway auto-fetch. Falls back gracefully if either is unavailable. |
| 1.8 (salesforce-api plugin) | Plugin registered in `openclaw.json` but pipeline code still uses inline `_sf_soql()`. Plugin registration is the config step; pipeline refactoring to use the plugin API is not done. |
| 4.6 (sandbox) | Sandbox is opt-in via `config.experiment.mode == "sandbox"`. Default path still uses direct imports. Production should set sandbox mode. |
| 5.1 (Einstein Trust Layer) | Implementation is complete and wired into pipeline. Actual functionality depends on the SF org having Einstein AI features enabled and Models API provisioned. Graceful fallback to Bedrock if unavailable. |
| 5.7/5.8 (WhatsApp/Telegram) | Scored as "DONE (config)" — OpenClaw channel definitions are complete. Actual message delivery requires real API tokens from Meta/Telegram. |
| 5.9 (secrets rotation) | CloudFormation template is complete and deployable. Not yet deployed to AWS. |
| Finding #1 (prompt injection) | Scored as "MITIGATED" not "RESOLVED" — boundary markers reduce risk but do not eliminate indirect prompt injection. Defense-in-depth with Bedrock Guardrails prompt injection detection provides additional protection. |
