# 006 Gap Remediation — Code Review

**Reviewer:** Kiro (automated code review)
**Date:** 2025-07-15
**Scope:** All files created/modified by 5 implementation subagents
**Verdict:** APPROVED WITH NOTES

---

## Summary Table

| # | File | Arch Rules | No Creds | MNPI | Imports | Error Handling | Consistency | Verdict |
|---|------|-----------|----------|------|---------|---------------|-------------|---------|
| **Subagent 1 — AgentCore** | | | | | | | | |
| 1 | `agentcore/adapter.js` | PASS | PASS | N/A | PASS | PASS | PASS | ✅ |
| 2 | `agentcore/Dockerfile` | PASS | PASS | N/A | PASS | PASS | PASS | ✅ |
| 3 | `agentcore/start.sh` | PASS | PASS | N/A | PASS | PASS | PASS | ✅ |
| 4 | `agentcore/agentcore-config.yaml` | PASS | PASS | N/A | PASS | N/A | PASS | ✅ |
| 5 | `agentcore/docker-compose.yml` | PASS | PASS | N/A | N/A | N/A | PASS | ✅ |
| **Subagent 2 — Salesforce FSC** | | | | | | | | |
| 6 | `scripts/apex/seed-04-financial-holdings.apex` | PASS | PASS | PASS | PASS | PASS | PASS | ✅ |
| 7 | `docs/fsc-objects-note.md` | PASS | N/A | PASS | N/A | N/A | PASS | ✅ |
| 8 | `pipeline.py` (Stage 2 FSC changes) | PASS | PASS | PASS | PASS | PASS | PASS | ✅ |
| **Subagent 3 — Security** | | | | | | | | |
| 9 | `screening.py` | PASS | PASS | PASS | PASS | PASS | PASS | ✅ |
| 10 | `mnpi_filter.py` | PASS | PASS | PASS | PASS | PASS | PASS | ✅ |
| 11 | `logger.py` | PASS | PASS | N/A | PASS | PASS | PASS | ✅ |
| 12 | `pipeline.py` (security integration) | PASS | PASS | PASS | PASS | PASS | PASS | ✅ |
| **Subagent 4 — Pipeline Alignment** | | | | | | | | |
| 13 | `config.arc.yaml` | PASS | PASS | N/A | N/A | N/A | PASS | ✅ |
| 14 | `pipeline.py` (HITL_STAGES) | PASS | PASS | N/A | PASS | PASS | PASS | ✅ |
| 15 | `agentStore.ts` (defaultPipelineStages) | PASS | PASS | N/A | PASS | PASS | PASS | ✅ |
| **Subagent 5 — Frontend Security** | | | | | | | | |
| 16 | `openclawApi.ts` | PASS | PASS | N/A | PASS | PASS | PASS | ✅ |
| 17 | `App.tsx` | PASS | PASS | N/A | PASS | PASS | PASS | ✅ |
| 18 | `index.html` | PASS | PASS | N/A | N/A | N/A | PASS | ✅ |
| 19 | `_headers` | PASS | PASS | N/A | N/A | N/A | PASS | ✅ |
| 20 | `vite.config.ts` | PASS | PASS | N/A | PASS | N/A | PASS | ✅ |
| 21 | `.env` | NOTE | NOTE | N/A | N/A | N/A | PASS | ⚠️ |
| 22 | `.env.example` | PASS | PASS | N/A | N/A | N/A | PASS | ✅ |

**Result: 21 PASS, 1 NOTE (non-blocking)**

---

## Detailed Findings

### Subagent 1 — AgentCore

**adapter.js** — WebSocket adapter bridging AgentCore HTTP to OpenClaw Gateway JSON-RPC 2.0.
- Architecture: OpenClaw-only runtime. No Agentforce/Strands references. Connects to OpenClaw Gateway on port 18789 via WebSocket. Exposes GET /ping + POST /invocations for AgentCore contract.
- Credentials: All from env vars (OPENCLAW_GATEWAY_TOKEN, GATEWAY_HOST, GATEWAY_PORT). Zero hardcoded secrets.
- Error handling: Exponential backoff reconnection (1s to 30s), heartbeat keepalive, request timeout (600s), pending request cleanup on disconnect.
- Imports: express and ws — standard, no unexpected dependencies.

**Dockerfile** — Multi-stage build on node:22-slim. Installs OpenClaw globally, copies adapter. Healthcheck on /ping. No credentials baked in.

**start.sh** — Launches OpenClaw Gateway (background), waits up to 30s for readiness, then starts adapter (foreground via exec). Clean process management.

**agentcore-config.yaml** — All secrets reference AWS Secrets Manager (secretId: openclaw/*). Model config: us.anthropic.claude-sonnet-4-6 primary, us.anthropic.claude-haiku-4-5 fallback. Bedrock-only.

**docker-compose.yml** — Local testing only. OPENCLAW_GATEWAY_TOKEN sourced from env var with empty default. No hardcoded values.

### Subagent 2 — Salesforce FSC

**seed-04-financial-holdings.apex** — Creates 15 FinServ__FinancialAccount__c and 60 FinServ__FinancialHolding__c records. Idempotent (deletes before insert). Graceful FSC detection via Schema.getGlobalDescribe() — exits cleanly on non-FSC orgs. MNPI fields (FinServ__Shares__c, FinServ__Price__c, FinServ__MarketValue__c) are present in seed data (correct — this is Salesforce-side data, not LLM-facing).

**fsc-objects-note.md** — Correctly documents MNPI enforcement: FinServ__Shares__c, FinServ__Price__c, FinServ__MarketValue__c, FinServ__Balance__c explicitly listed as "NEVER sent to LLM." Consistent with mnpi_filter.py field list.

**pipeline.py Stage 2** — FSC holdings query wrapped in try/except. On success, only ticker, client_count, and is_top_holding (boolean) are extracted — no dollar amounts or share counts reach the pipeline state. filter_mnpi() called on coverage, watchlist, and prior research records. summarize_holdings_safe() called to build LLM-safe summary.

### Subagent 3 — Security

**screening.py** — Implements 4 FINRA compliance checks (restricted list, MNPI lookback, trading window, concentration). All Salesforce access via function parameters (sf_instance_url, sf_access_token) — zero env var reads, zero hardcoded credentials. SOQL values escaped via _escape_soql(). Every check wrapped in try/except. No LLM imports. No Comprehend/FinBERT.

**mnpi_filter.py** — Defines MNPI_FIELDS set: FinServ__Shares__c, FinServ__MarketValue__c, FinServ__Price__c, Amount, Balance__c, Trade_Amount__c, Wire_Amount__c, Position_Size__c. filter_mnpi() deep-copies records and strips all MNPI fields. summarize_holdings_safe() returns only tickers, client count, top holdings (by frequency, not value), and sector exposure (by count, not value). On error, returns empty safe dict rather than leaking data.

**logger.py** — Dual-write to Salesforce IR_Audit_Log__c AND Langfuse. Shared trace_id links both systems. Field truncation to SF limits. Graceful failure: if SF write fails but Langfuse succeeded, returns partial success. No credentials in code — all via function parameters.

**pipeline.py security integration** — _log_audit() delegates to logger.py. Called at every stage (1-23). Compliance screening delegated to screening.py at stage 20. filter_mnpi() and summarize_holdings_safe() imported and used in stage 2.

### Subagent 4 — Pipeline Alignment

**config.arc.yaml** — HITL gates at stages 7, 13, 21. LLM: anthropic.claude-sonnet-4-6 primary, anthropic.claude-haiku-4-5 fallback. Provider: acp (OpenClaw). No GPT/OpenAI/Comprehend/FinBERT.

**pipeline.py HITL_STAGES** — HITL_STAGES = {7, 13, 21}. Comment states "must match config.arc.yaml hitl.stage_policies." All three gates return {"gate": True} which pauses the pipeline for analyst approval. resume() handles approval/rejection with audit logging.

**agentStore.ts defaultPipelineStages()** — 23 stages. isHitlGate: true at stages 7, 13, 21. Comment: "HITL gates at stages 7, 13, 21 — Must match config.arc.yaml and pipeline.py HITL_STAGES." Three-way alignment confirmed.

### Subagent 5 — Frontend Security

**openclawApi.ts** — No static gateway token. sfAuthToken set via setAuthToken() after SF OAuth PKCE. AgentCore auth encodes OAuth token in Sec-WebSocket-Protocol header (base64url). Rate limiting: sliding window, max 5 messages per 10 seconds. Exponential backoff reconnection. Heartbeat ping every 30s. Connects to OpenClaw WebSocket only — no direct SF API calls for agent queries.

**App.tsx** — SF OAuth2 PKCE via react-oauth2-code-pkce. Token used for user identity only. After OAuth, calls setAuthToken(token) then connectToOpenClaw(). Clean separation: SF = identity, OpenClaw = agent communication.

**index.html** — CSP meta tag: default-src 'self', connect-src allows wss://*.amazonaws.com, ws://localhost:18789, SF login, Langfuse. frame-ancestors 'none', X-Content-Type-Options: nosniff, X-Frame-Options: DENY. No unsafe-eval in script-src.

**_headers** — Static hosting headers mirror index.html CSP. Adds Referrer-Policy: strict-origin-when-cross-origin.

**vite.config.ts** — Dev server CSP headers match production. connect-src includes ws://localhost:18789 (local dev) and wss://*.amazonaws.com (AgentCore).

**.env** — Contains VITE_SF_CLIENT_ID (public OAuth2 client identifier, not a secret) and a specific AgentCore WebSocket URL with ARN. No passwords or secret keys. See Note 1.

**.env.example** — Placeholder values (YOUR_SF_CLIENT_ID, YOUR_RUNTIME_ARN). Clean template.

---

## Notes (Non-Blocking)

### NOTE 1: .env contains environment-specific values

frontend/.env contains a real SF Connected App client ID and AgentCore ARN. Per OAuth2 spec, the client ID is a public identifier (not a secret). The AgentCore WebSocket URL requires authentication. Neither is a credential. However, .env should be in .gitignore to avoid committing environment-specific values.

Severity: Low. Not a security issue, but a hygiene concern.

### NOTE 2: screening.py SOQL uses string interpolation with sanitization

_check_restricted_list and other checks use f-string SOQL with _escape_soql() sanitization. The escape function strips non-alphanumeric characters and escapes single quotes. Adequate for ticker symbols (uppercase alphanumeric). For free-text inputs, consider parameterized queries.

Severity: Low. Current inputs are ticker symbols only.

---

## Architecture Rule Verification

| Rule | Status | Evidence |
|------|--------|----------|
| 1. OpenClaw ONLY runtime | PASS | No Agentforce/Strands imports or references in any file |
| 2. Bedrock only (Sonnet 4.6 / Haiku 4.5) | PASS | config.arc.yaml + pipeline.py boto3 bedrock-runtime. No OpenAI/Comprehend/FinBERT |
| 3. MCP: GET / + POST /tools/list + POST /tools/call | PASS | pipeline.py._mcp_call() uses POST {gateway}/{server}/tools/call |
| 4. Frontend: OpenClaw WebSocket only | PASS | openclawApi.ts connects to VITE_OPENCLAW_GATEWAY_URL. No SF Agent API |
| 5. ZERO credentials in code | PASS | All via env vars, function params, or AWS Secrets Manager |
| 6. Every action writes IR_Audit_Log__c | PASS | _log_audit() called at every stage, delegates to logger.py |
| 7. MNPI NEVER sent to LLM/memory | PASS | mnpi_filter.py strips 8 fields. Stage 2 uses filter + summarize |

---

## Final Verdict

**APPROVED WITH NOTES**

All 7 architecture rules pass. All files pass the 6-point review checklist. The two notes (environment-specific .env values and SOQL string interpolation) are non-blocking. MNPI enforcement, audit logging, credential management, and HITL gate alignment are correctly implemented across all 5 subagent deliverables.
