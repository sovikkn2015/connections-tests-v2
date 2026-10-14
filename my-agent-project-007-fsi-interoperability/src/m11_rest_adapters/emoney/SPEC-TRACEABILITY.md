# SPEC-TRACEABILITY — emoney

Spec: `.kiro/specs/m11-rest-adapters.md` v0.2.0.

| R# | Files | Tests |
|----|-------|-------|
| R2 — 1 tool | `src/tools.ts` | `tests/test_zod.test.ts` |
| R4 — OAuth client-credentials + scope enforcement | `src/auth.ts` | `tests/test_zod.test.ts` |
| R8.5 — **strict output** aligned to M7 EMoneyPlanSummary | `src/schemas.ts` | `tests/test_zod.test.ts` + `test_m7_emoney_allowlist.py` |
| R8.6 — reject raw plan body | `src/client.ts::fetchPlanSummary` | `tests/test_zod.test.ts` |

## Allow-list

- 7 required + 14 optional = 21 (NEW-2 patch).
- Cross-module set-equality: `tests/integration/test_m7_emoney_allowlist.py`.
