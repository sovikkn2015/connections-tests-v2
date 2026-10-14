# SPEC-TRACEABILITY — schwab

Spec: `.kiro/specs/m11-rest-adapters.md` v0.2.0.

| R# | Files | Tests |
|----|-------|-------|
| R2 — 3 read-only tools (AC2.4) | `src/tools.ts` | `tests/test_zod.test.ts` |
| R4 — RT rotation + CRITICAL alert (AC4.7, AC4.13) | `src/auth.ts::refresh` | `tests/test_auth.test.ts` |
| R8 — Zod input only | `src/schemas.ts` | `tests/test_zod.test.ts` |
| R10 — `GET /trader/v1/userPreference` | `src/client.ts::checkVersionAvailable` | `test_m11_m7_version_match.py` |
| R17 — SIGTERM waits ≤ 10s (AC17.3) | `src/startup.ts` + `auth.ts::waitForRotation` | `tests/test_auth.test.ts` |

## Descope (AC2.4 / Appendix E row 24)

No `schwab.submit_trade`, `cancel_order`, `replace_order`. Phase 3 per IMPL-06 Blocker 1.

## RBAC

Schwab ServiceAccount has narrow `["get","update"]` on single `m11-schwab-refresh-token` Secret. §RBAC Template — default (others) vs Schwab variant.
