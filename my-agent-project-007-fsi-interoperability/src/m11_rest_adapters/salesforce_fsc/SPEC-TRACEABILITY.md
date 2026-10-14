# SPEC-TRACEABILITY — salesforce_fsc

Spec: `.kiro/specs/m11-rest-adapters.md` v0.2.0.

## Requirements

| R# | Files | Tests |
|----|-------|-------|
| R1 MCP contract | shared-sdk `server.ts` | shared `test_mcp_server.test.ts` |
| R2 5 tools | `src/tools.ts` | `tests/test_zod.test.ts` |
| R3 per-adapter independence | `package.json`, `Dockerfile`, `tsconfig.json` | build passes |
| R4 SecretsClient + LRU + SSRF | `src/auth.ts` | `tests/test_auth.test.ts` |
| R5 rate limit 100K/24h | shared `rate_limit.ts` + SFDC daily bucket | shared `test_rate_limit.test.ts` |
| R6 circuit breaker | shared `circuit.ts` | shared `test_circuit.test.ts` |
| R7 structured logging | shared `logger.ts` | shared `test_logger_redact.test.ts` |
| R8 Zod input + ETag writeback | `src/schemas.ts` + `client.ts` | `tests/test_zod.test.ts` |
| R9 mTLS + NetworkPolicy | Helm templates (chart) | `helm template` smoke |
| R10 version check v59.0 | `client.ts::checkVersionAvailable` | `test_m11_m7_version_match.py` |
| R11 Dockerfile | `Dockerfile` | hadolint + image-size |
| R12 module boundary | tsconfig + dockerignore | shared `test_module_boundary.test.ts` |
| R13 public API | `src/index.ts` | — |
| R14 SSRF + redaction | shared `ssrf.ts` + `logger.ts` | shared `test_ssrf.test.ts`, `test_no_token_in_logs.test.ts` |
| R15 DECISION-LOG | `../DECISION-LOG.md` | — |
| R16 22 error codes | shared `errors.ts` | shared `test_error_codes.test.ts` |
| R17 startup | `src/startup.ts` | — |
| R18 test gates | `vitest.config.ts` | full suite |

## Tools

| Tool | Schema | Handler | Tests |
|------|--------|---------|-------|
| `sfdc.fetch_client` | FetchClientInput | `client.ts::fetchClient` | zod + property |
| `sfdc.fetch_household` | FetchHouseholdInput | `client.ts::fetchHousehold` | zod + property |
| `sfdc.fetch_goal` | FetchGoalInput | `client.ts::fetchGoal` | zod + property |
| `sfdc.update_client` | UpdateClientInput + ETag | `client.ts::updateClient` | zod + property |
| `sfdc.create_interaction_summary` | CreateInteractionSummaryInput + ETag | `client.ts::createInteractionSummary` | zod |

## Known Gaps

- §Known Blockers row 4 — **SFDC PascalCase vs M7 snake_case** gap documented; `test_m7_sfdc_shape.py` is `xfail` pending M7 resolution. Blocks SFDC pre-prod deployment.
