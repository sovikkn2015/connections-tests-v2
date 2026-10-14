# Project 007: FSI Interoperability Platform

An interoperable multi-agent system for financial services — connecting research, client data, compliance, and execution across 5 enterprise archetypes via MCP adapters, a trust-aware gateway, and archetype-specific compliance policies.

Score: v1 (5.1) → v2 (7.5) → v3 (8.2) → v4 (5.1 → projected 7.0-7.5 post-fix) → REV-07 (8.5/10). Status: STRONG GO.

## Project Structure

```
docs/                          Documentation (22 docs, 4 categories)
  architecture/                ARCH-01 to ARCH-08: product design
  research/                    RES-01 to RES-07: analysis and research
  reviews/                     REV-01 to REV-04: LLMJ committee reviews
  implementation/              IMPL-01 to IMPL-05: build strategy

src/                           Source code (13 modules + specialists)
  m1-identity/                 Agent Identity Service (Keycloak + AID)
  m2-m4-policy-engine/         Unified OPA/Rego Policy Engine
  m3-schema-registry/          Canonical Schema Registry (18 types, Pydantic v2)
  m5-config-loader/            Enterprise Config Loader (Pydantic)
  m6-mcp-gateway/              Trust-Aware MCP Gateway (FastAPI)
  m7-schema-translators/       Per-vendor schema translators (5 vendors)
  m8-pipeline-engine/          LangGraph 23-stage research pipeline
  m9-intent-router/            FSI Intent Router (LLM function calling)
  m10-audit-logger/            Three-tier audit (Langfuse + WORM + CRM)
  m11-mcp-adapters/            MCP adapters (20 adapters, 5 protocols)
  m12-agent-runtime/           Managed Agents (cloud) / Strands (hybrid)
  m13-fix-bridge/              FIX 4.2 Bridge (Phase 4, specialist)
  compliance/                  7 compliance gap implementations
  execution-specialist/        Order state machine + mandatory HITL
  onboarding-specialist/       KYC workflow + DocuSign + multi-session
  smarsh-archiver/             FINRA 17a-4 communication archiving

opa-bundles/                   OPA/Rego policy bundles
  authority/                   Authorization rules
  mnpi/                        MNPI filtering rules
  account-type/                ERISA/IRA/trust rules
  bsa-aml/                     BSA/AML monitoring rules
  jurisdiction/                Per-jurisdiction overlays (US/EU/UK/SG/HK)

schemas/                       Data schemas
  canonical/                   Canonical FSI data model (JSON Schema)
  translators/                 Per-vendor translation mappings

tests/                         Test suites
  unit/                        Per-module unit tests
  integration/                 Cross-module integration tests
  adversarial/                 200+ compliance attack tests
  performance/                 Load and latency tests
  schema-reconciliation/       Canonical vs source comparison

evaluation/                    1,230+ query eval suite
infra/                         Infrastructure as code (Terraform, Helm, Docker)
.github/workflows/             CI/CD pipelines
.kiro/                         Kiro steering files and hooks
scripts/                       Utility scripts
```

## Key Architecture Decisions

- Agent runtime: Claude Managed Agents (cloud, Tier 3/4) / Strands SDK (hybrid/on-prem, Tier 1/2/5)
- Policy engine: OPA/Rego (unified authority + MNPI, deterministic, not LLM)
- Pipeline: LangGraph (23-stage with checkpointing and HITL gates)
- Tool protocol: MCP (universal adapter layer)
- Audit: Three-tier (Langfuse + S3 Object Lock WORM + CRM)
- LLM: Abstracted (Bedrock / Azure OpenAI / GCP Vertex / self-hosted)
- Deployment: 3 topologies (cloud, hybrid, on-premise)
