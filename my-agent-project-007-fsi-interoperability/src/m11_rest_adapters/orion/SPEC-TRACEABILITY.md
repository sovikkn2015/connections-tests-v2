# SPEC-TRACEABILITY — orion

Spec: `.kiro/specs/m11-rest-adapters.md` v0.2.0.

| R# | Files | Tests |
|----|-------|-------|
| R2 — 4 tools | `src/tools.ts` | `tests/test_zod.test.ts` |
| R4 — OAuth + Phase 3 Basic toggle (AC4.12) | `src/auth.ts` both branches | `tests/test_auth.test.ts` |
| R5 — 60 RPM PENDING-VERIFICATION | `src/startup.ts` | shared `test_rate_limit.test.ts` |
| R8 — Zod + 90-day range refine | `src/schemas.ts` | `tests/test_zod.test.ts` + `test_property.test.ts` |
| R10 — `vendor_version_check_skipped` | `src/startup.ts` | — |
| AC2.11 — Orion path probe | `src/client.ts::probeBasePath` | startup only |

## Tools

| Tool | Path (PENDING-VERIFICATION) |
|------|-----------------------------|
| `orion.fetch_holdings` | `/api/v2.0/portfolio/accounts/{id}/positions` |
| `orion.fetch_transactions` | `/api/v2.0/portfolio/accounts/{id}/transactions` |
| `orion.fetch_household` | `/api/v2.0/portfolio/households/{id}` |
| `orion.fetch_taxlots` | `/api/v2.0/portfolio/accounts/{id}/taxlots` |
