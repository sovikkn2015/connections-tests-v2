# M11-REST Adapters — COMPLETE

**Module**: M11 MCP Adapters (REST sub-type)
**Phase**: 2 (Intelligence Layer — RIA lighthouse)
**Date**: 2026-04-25
**Playbook**: 7 steps complete

## Scorecard

| Step | Status | Result |
|------|--------|--------|
| 1. Spec | done | v0.1.0, 1,628 lines |
| 2. LLMJ Review v1 | done | 7.27/10 CONDITIONAL GO — 17 required fixes |
| 3. Fix | done | v0.2.0, 1,560 lines, full rewrite |
| 4. LLMJ Review v2 | done | 8.52/10 GO (+1.25 delta) |
| 5. Build | done | 4,276 TS src + 2,406 test LOC |
| 6. Verify | done | 156 TS + 8 Python = 164 tests; 10/10 stress stable |
| 7. Complete | done | This marker |

## Scope Delivered

4 adapters x 14 tools:
- SFDC (5 tools) - OAuth JWT bearer + SSRF validation + ETag writeback idempotency
- Orion (4 tools) - OAuth client-credentials + PENDING-VERIFICATION URL probe + Phase 3 Basic-auth toggle
- eMoney (1 tool) - OAuth + scope enforcement + strict output Zod aligned to M7
- Schwab (3 tools) - OAuth refresh-token rotation + narrow RBAC + CRITICAL alerting

Plus @project-007/mcp-sdk shared package: LRU 1024 cache, SSRF validator, 3-state circuit breaker, token-bucket rate limiter, pino redaction.

## Non-Negotiables Verified

- Zero credentials in any file (AST scan)
- Zero M7 imports (AC12.6)
- 22-code closed errorCode vocabulary
- SSRF rejects http/file/ftp, RFC1918, link-local, loopback, ULA
- eMoney allow-list set-equal to M7 EMoneyPlanSummary fields (verified)
- VENDOR_API_VERSION matches M7 for all 4 vendors
- mTLS 1.3 only with 24h cert-manager rotation
- Multi-stage distroless Dockerfile, ~130 MiB under 150 MiB cap
- Per-firm LRU 1024 for token cache, rate limit, circuit breaker

## Test Results

- TypeScript vitest: 156 tests across shared SDK + 4 adapters
- Python pytest cross-module: 7 passed + 1 xfail (SFDC PascalCase gate)
- Full project suite: 839 passed + 1 xfailed + 1 xpassed
- 10/10 stress runs stable

## Deployment Gating

Pre-prod requires 4 operational items:
- Schwab developer-program approval (6-8 wk)
- eMoney partnership approval (6-12 mo)
- Orion URL path verification
- M7 SFDC PascalCase fix

## Phase 2 Next Module

M9 Intent Router (pipeline-agent specialist).
