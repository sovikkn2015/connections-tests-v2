# Project 007 FSI Interoperability Platform — Deployment Architecture

> Date: April 17, 2026
> Status: Phases 0-4 complete. Phase 5 (on-prem) deferred.
> Everything in git. `docker-compose up -d` brings up the full 25-service stack.

---

## Architecture Diagram

```
                         ┌─────────────────────────────────┐
                         │         USERS (12+ channels)     │
                         │  Slack │ Teams │ WhatsApp │ Web  │
                         └────────────────┬────────────────┘
                                          │
                    ┌─────────────────────▼─────────────────────┐
                    │  M12 OpenClaw + Managed Agents / Strands  │
                    │  (PLUG IN — Helm values toggle)           │
                    └──────┬──────────────┬──────────┬─────────┘
                           │              │          │
              ┌────────────▼──┐    ┌──────▼───┐  ┌──▼──────────┐
              │ M9 Intent     │    │ M8 Pipe  │  │ Specialists │
              │ Router        │    │ Engine   │  │             │
              │ :8009         │    │ :8008    │  │ Execution   │
              │ Haiku <500ms  │    │ LangGraph│  │ :8020       │
              └───────┬───────┘    │ 23 stage │  │ Onboarding  │
                      │            │ 3 HITL   │  │ :8021       │
                      │            └────┬─────┘  └──────┬──────┘
                      │                 │               │
         ┌────────────▼─────────────────▼───────────────▼──────┐
         │                                                      │
         │          M6 MCP GATEWAY (THE CORE — :8006)           │
         │                                                      │
         │  Pre-call:  M1 verify → M2 authority → M4 MNPI      │
         │  Forward:   MCP call to downstream adapter           │
         │  Post-call: M7 translate → M4 filter → scan → M10   │
         │                                                      │
         │  Circuit breaker │ Retry │ Rate limit │ Bulkhead     │
         │  Redis-backed │ OpenTelemetry │ Provenance chain     │
         └──┬────┬────┬────┬────────────────┬────┬────┬────┬───┘
            │    │    │    │                │    │    │    │
     ┌──────▼┐ ┌▼───┐│ ┌──▼──┐         ┌──▼──┐│ ┌──▼──┐ │
     │ M1    │ │M2/ ││ │ M10 │         │ M11 ││ │ M13 │ │
     │ Ident │ │M4  ││ │Audit│         │ MCP ││ │ FIX │ │
     │ :8001 │ │OPA ││ │:8010│         │Adapt││ │Bridge│ │
     │ JWT   │ │:8002│ │3-tier│        │     ││ │:8030 │ │
     │ RS256 │ │Rego│ │ WORM │         │     ││ │State-│ │
     └───────┘ └─┬──┘ └──┬───┘        │     ││ │fulSet│ │
                 │       │             │     ││ └──────┘ │
              ┌──▼──┐  ┌─▼──────┐     │     │└──────────┘
              │ OPA │  │Langfuse│     │     │
              │:8181│  │ :3000  │     └──┬──┘
              └─────┘  └────────┘        │
                                         │
    ┌────────────────────────────────────▼────────────────────────┐
    │                    M11 MCP ADAPTERS (11 total)              │
    │                                                             │
    │  REST: SEC EDGAR :8011 │ Market Data :8012 │ News :8013    │
    │  SF FSC :8003 │ Orion :8004 │ Schwab REST :8014            │
    │  eMoney :8015 │ Schwab SFTP :8016                          │
    │                                                             │
    │  BLPAPI: Bloomberg B-PIPE :8040 (binary, PrivateLink)      │
    │  gRPC:  SS&C Eze xAPI :8041 (proto definitions)            │
    │  MCP-Native: FactSet :8042 (passthrough)                   │
    └─────────────────────────────────────────────────────────────┘
```

---

## Infrastructure

| Service | Port | Purpose |
|---------|------|---------|
| PostgreSQL | 5432 | 4 databases: fsi007, fsi007_m1, fsi007_m8, fsi007_m10 |
| Redis | 6379 | Circuit breaker state, rate limiting |
| MinIO | 9000 | S3-compatible WORM audit storage |
| OPA | 8181 | 26 Rego policy files |
| Langfuse | 3000 | LLM observability traces |
| Keycloak | 8080 | IAM token issuance |

---

## Compliance Layer (7 gaps, 278 tests)

| Gap | Parent | What |
|-----|--------|------|
| 1 Reg BI | M10 | 4-obligation documentation generator |
| 2 Liability | M6+M10 | SHA-256 provenance chain |
| 3 WSP Mapping | M2 | WSP ↔ Rego bidirectional |
| 4 BSA/AML | M2 | CTR/SAR/sanctions/anti-tipping-off |
| 5 ERISA | M2 | 16 account types + tax calculator |
| 6 MNPI Scan | M6 | 3-layer output guardrail |
| 7 Cross-Border | M2 | 5 jurisdictions (US/EU/UK/SG/HK), modular engines |

---

## OPA Rego Bundles (26 files, 51 tests)

| Bundle | Rules |
|--------|-------|
| authority/ | ALLOW/DENY/ESCALATE, pod isolation, client scope |
| mnpi/ | PII stripping, Chinese wall, pod isolation |
| account-type/ | ERISA, IRA, trust rules |
| bsa-aml/ | SAR triggers, CTR threshold, sanctions/PEP |
| jurisdiction/us/ | SEC 17a-4, FINRA 2210, Reg BI suitability |
| jurisdiction/eu/ | MiFID II, GDPR consent/erasure, DORA, AI Act |
| jurisdiction/uk/ | FCA Consumer Duty, UK GDPR |
| jurisdiction/sg/ | MAS TRM, FEAT, AIRG |

---

## Helm (3 topologies)

| Topology | Runtime | LLM | Checkpoints | WORM | M13 |
|----------|---------|-----|-------------|------|-----|
| Cloud | Managed Agents | Bedrock | DynamoDB | S3 Object Lock | Disabled |
| Hybrid | Strands SDK | Self-hosted/VPN | PostgreSQL | MinIO | Enabled (StatefulSet) |
| On-prem | Strands SDK | Self-hosted | PostgreSQL | MinIO | Enabled (Phase 5) |

---

## CI/CD

| Job | What |
|-----|------|
| test-python | 507+ tests via run_all_tests.sh |
| test-opa | opa check + opa test (51 tests) |
| validate-schemas | 18 JSON schemas |
| lint | ruff |
| docker-build | 6 module Dockerfiles (main only) |

---

## Final Numbers

| Metric | Count |
|--------|-------|
| Modules built | 13/13 |
| Compliance gaps | 7/7 |
| Specialist agents | 5/5 |
| Jurisdictions | 5 |
| Python tests | 590+ |
| OPA tests | 51 |
| Rego files | 26 |
| JSON schemas | 18 |
| Dockerfiles | 20 |
| Docker-compose services | 25 |
| Helm templates | 7 |
| M11 adapters | 11 |
| Python LOC | ~32K |
| Rego LOC | ~3.6K |
