# Project 007: FSI Interoperability Platform

> Trust layer between every system a wealth management firm uses — so AI agents can act on financial data without compliance risk.

## Architecture

13 modules. 18 canonical types. 5 archetypes. 5 jurisdictions. 17+ vendor integrations.

```
USER → M12 (Channels) → M9 (Intent) → Specialists → M6 (Gateway) → M11 (Adapters) → Vendors
                                                        ↕
                                              M1 + M2/M4 + M10 (Trust Layer)
```

## Modules

| # | Module | Language | Framework |
|---|--------|----------|-----------|
| M1 | Agent Identity | Python | FastAPI + Keycloak |
| M2/M4 | Policy Engine (Authority + MNPI) | Rego + Python | OPA + FastAPI |
| M3 | Canonical Schema Registry | Python | JSON Schema + Pydantic v2 |
| M5 | Enterprise Config Loader | Python | Pydantic v2 |
| M6 | MCP Gateway (Trust-Aware) | Python | FastAPI |
| M7 | Schema Translators | Python | Pydantic v2 |
| M8 | Pipeline Engine | Python | LangGraph |
| M9 | Intent Router | Python | LLM function calling |
| M10 | Audit Logger | Python | FastAPI + Langfuse |
| M11 | MCP Adapters (polyglot) | TS + Python | MCP SDK |
| M12 | Agent Runtime | Python | Managed Agents / Strands |
| M13 | FIX Bridge | Python | QuickFIX + MCP |

## Build Order

- Phase 0: M3 + M5 (schema + config)
- Phase 1: M1 + M10 + M2/M4 + M6 (trust layer → wedge product)
- Phase 2: M7 + M11-REST + M9 + M8 + M12 (intelligence → RIA lighthouse)
- Phase 3: Smarsh + Execution + Onboarding + SOC 2 (BD onboarding)
- Phase 4: M11-BLPAPI + M11-gRPC + M13 + hybrid (Tier 2/5)

## Quick Start

```bash
bash run_all_tests.sh
docker compose up
```

## Design Docs

See `docs/` for the full architecture (carried over from design phase).
