# REV-09: Real vs Mock — Brutally Honest Assessment

> Date: April 18, 2026
> Method: 3 specialist sub-agents audited every module line-by-line
> Scope: Trust layer, compliance gaps, OPA bundles, M11 adapters, M13 FIX Bridge, infra wiring
> Tests verified: 707 pass, 0 fail, 2 skip

---

## THE HONEST PICTURE

707 tests pass. But passing tests and production-ready are different things.

---

## TRUST LAYER

| Component | Verdict |
|-----------|---------|
| M1 JWT RS256 crypto | REAL — PyJWT + cryptography, real RSA-2048 |
| M1 Keycloak integration | NOT IMPLEMENTED — env var exists, zero code |
| M1 AID registry | MOCK — in-memory dict, no PostgreSQL |
| M6 trust pipeline HTTP calls | REAL — httpx async to all modules |
| M6 MCP forwarding | REAL — httpx async proxy |
| M6 circuit breaker | REAL — state machine + Redis option |
| M6 rate limiter | REAL — sliding window + Redis option |
| M6 leakage scan Layer A | REAL — 10+ regex patterns |
| M6 leakage scan B/C | STUB — by design (Phase 2/3) |
| M6 GatewayConfig env vars | BROKEN — BaseModel not BaseSettings, docker-compose env vars ignored |
| M2/M4 OPA HTTP calls | REAL — httpx, env var correctly read |
| M2/M4 local evaluator | REAL — faithful Rego mirror |
| M2/M4 fail-closed | REAL — DENY on OPA unreachable |
| M10 SHA-256 integrity | REAL — hashlib.sha256 |
| M10 S3 WORM writer | CODE EXISTS, NEVER ACTIVATED |
| M10 Langfuse writer | CODE EXISTS, NEVER ACTIVATED |
| M10 CRM writer | CODE EXISTS, NEVER ACTIVATED |
| M10 DLQ | MOCK — in-memory deque |
| Integration tests | ALL MOCKED — no real container-to-container test |

## COMPLIANCE LAYER

| Component | Verdict |
|-----------|---------|
| Gap 1 Reg BI | REAL BUT INCOMPLETE — no Jinja2, no WORM write, no LLM narrative |
| Gap 2 Liability Provenance | REAL — genuine SHA-256 chains |
| Gap 3 WSP-to-YAML | REAL — bidirectional, validates real Rego files |
| Gap 4 BSA/AML | REAL — correct thresholds, anti-tipping-off. No fuzzy sanctions. |
| Gap 5 ERISA | REAL BUT INCOMPLETE — 17 types, tax calc. No OPA integration from Python. |
| Gap 6 MNPI Scan | REAL (A+B), STUB (C) |
| Gap 7 Cross-Border | REAL BUT INCOMPLETE — HK empty, no MiFID II best execution |
| OPA authority/mnpi | REAL — substantive rules with tests |
| OPA bsa-aml | REAL — correct thresholds, partially tested |
| OPA account-type | REAL — no native Rego tests |
| OPA jurisdiction (US/EU/UK/SG) | REAL — no native Rego tests |
| OPA jurisdiction HK | STUB — empty .gitkeep |

## M11 ADAPTERS

| Classification | Count | Which |
|---------------|-------|-------|
| PRODUCTION-READY (public API) | 4 | sec-edgar, sec-edgar-ts, market-data, news-search |
| DEV-MODE WITH REAL CODE | 10 | fidelity-rest, pershing, redtail, wealthbox, envestnet, complysci, factset-native, bloomberg-blpapi, fidelity-sftp, eze-grpc |
| STUB (pending vendor) | 5 | salesforce-fsc, orion, emoney, schwab-rest, schwab-sftp |

Zero hardcoded credentials.

## M13 FIX BRIDGE

Session manager: REAL. QuickFIX engine: REAL CODE, dev-mode no-op. MCP handlers: REAL (use session manager). Missing: quickfix in requirements.txt, FIX42.xml.

## CANONICAL SCHEMA

18 Pydantic models: REAL. Household container: REAL. cost_basis_method never-null: REAL. JSON Schema files: EXIST (18 + baselines).

---

## BLOCKING ISSUES

1. GatewayConfig env var loading — docker-compose wiring broken
2. M10 backend activation — production code exists but never called
3. Salesforce/Orion/eMoney adapters are stubs (needed for RIA lighthouse, not wedge product)

## HONEST SCORE

Code quality and design: 7.5/10. Production readiness: 5/10.

Fix the 3 blocking items and production readiness jumps to 8.5/10.

---

*REV-09 — Project 007 FSI Interoperability Platform*
