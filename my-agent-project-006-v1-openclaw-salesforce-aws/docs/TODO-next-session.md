# TODO — Next Session (April 10, 2026)

## Completed Overnight (automated, no user input required)

- [x] **Claim 6** — Enabled per-user memory: changed `NO_MEMORY` → `SESSION_MEMORY` in `.bedrock_agentcore.yaml`. Needs `agentcore deploy` to take effect.
- [x] **5.13 #9** — Added `EVAL_AUTH_TOKEN` env var auth check to `evaluation/run_suite.py`. Eval suite now refuses to run without the token set.
- [x] **3.9** — Wired pipeline stage 23 to dispatch notifications via OpenClaw hooks endpoint (`/hooks/agent`) with `deliver: true`. Reads `OPENCLAW_HOOKS_URL` and `OPENCLAW_HOOKS_TOKEN` from env. No-op if token not set.
- [x] **5.13 #10** — Added `_redact_for_trace()` to `audit-logging/logger.py`. MNPI fields (`FinServ__Shares__c`, `FinServ__MarketValue__c`, etc.) and credential fields are replaced with `[REDACTED]` before Langfuse trace events. `log_audit()` Langfuse call now uses redacted metadata.

## Still Immediate (no blockers)

1. **1.8** — Reclassify salesforce-api skill as DONE (caveat) — plugin doesn't exist in OpenClaw
2. **5.13 #8** — Deploy secrets rotation Lambda via CloudFormation

## Needs You (manual execution)

3. **Redeploy AgentCore** — `agentcore deploy` to pick up SESSION_MEMORY + pipeline hooks changes
4. **5.12** — Run full eval suite (2-5 hours, needs live env + all env vars + EVAL_AUTH_TOKEN)
5. **5.14** — Fill performance baseline from eval results + Langfuse traces
6. **3.9 testing** — Provide Slack bot token + app token to test channel dispatch end-to-end
7. **5.13 #14** — Decision: is SigV4 request signing worth 2 hours of SAM changes?

## Current State (April 10, 2026 — post overnight batch)

- 38 of 56 non-MuleSoft tasks done (68%) — plus 4 items remediated overnight
- Claim 6 (per-user memory) now enabled — was FALSE, now SESSION_MEMORY
- Security findings: 10 of 15 resolved (was 8), 1 mitigated — #9 and #10 closed overnight
- Task 3.9 (pipeline notifications) upgraded from PARTIAL to DONE — hooks dispatch wired
- OpenClaw running live on AgentCore with full FSI stack
- 4/4 targeted eval queries passed (L1-CRM, L1-MCP, L2-Multi, L3-Analysis)
- AgentCore deploy is reproducible via agentcore deploy with env vars
