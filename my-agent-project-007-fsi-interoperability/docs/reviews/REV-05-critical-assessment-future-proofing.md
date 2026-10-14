# Project 007: Critical Assessment — Modularity, Reproducibility, and Future-Proofing

> Date: April 13, 2026
> Category: REVIEW
> Purpose: Honest stress-test of the tech stack.
> Verdict: Product architecture 8.2/10. Operational architecture 5-6/10. The gap is not what to build but how to run it.

---

## Modularity: 7/10

What is modular: MCP adapters, OPA bundles, schema translators, LLM provider, deployment topology, compliance gaps — all add/remove via config.

What is coupled: M6 Gateway is a god module (every call flows through it). Strands SDK is a single vendor dependency for orchestration. LangGraph is a single vendor dependency for the pipeline. Keycloak is heavy for what M1 needs (3 endpoints, not a full IAM platform).

Recommendations: Circuit breaker for M6. Abstract Strands behind an orchestrator interface. Abstract LangGraph behind a pipeline interface. Consider lightweight JWT service instead of Keycloak.

---

## Reproducibility: 6/10

What is reproducible: Every module is a container. Helm charts. Terraform. Versioned OPA bundles and schemas. One YAML enterprise config.

What is not: No deploy-from-zero script (20+ services, no single command). No docker-compose for local dev. No seed data. No environment parity across 3 topologies (DynamoDB vs PostgreSQL, S3 vs MinIO, Bedrock vs vLLM).

Recommendations: docker-compose.yml as first Phase 0 deliverable. deploy-all.sh script. Seed data for every module. Topology test matrix in CI.

---

## Flexibility: 8/10

| Action | Difficulty |
|--------|-----------|
| Add new vendor (Bloomberg) | EASY — 1 adapter + 1 translator + config |
| Add new archetype (Insurance) | EASY — 1 OPA bundle + config |
| Add new jurisdiction (Japan) | EASY — 1 OPA overlay + config |
| Change LLM (Bedrock to Azure) | EASY — config change only |
| Change pipeline (23 to 15 stages) | MEDIUM — modify LangGraph graph |
| Remove module (drop BSA/AML) | EASY — remove from config |
| Replace Strands | MEDIUM — rewrite M12 (~500-800 lines) |
| Replace OPA | HARD — rewrite 2,100 lines of Rego |

---

## Ease of Deployment: 5/10 — Weakest Area

007 has ~20 services. Tier 4 RIAs (no IT staff) cannot deploy Kubernetes. They need managed SaaS. Tier 1 banks need highly configurable Helm charts.

Missing: No SaaS model. No one-click deploy. No Kubernetes operator. No upgrade strategy for M6. No multi-tenant isolation design.

Recommendations: SaaS for Tier 3/4. Kubernetes operator. Multi-tenant isolation (namespace + keys + OPA per tenant). Zero-downtime upgrade for M6.

---

## Future-Proofing: 7/10

| Risk | Level | Mitigation |
|------|-------|-----------|
| LLM landscape shifts | LOW | Abstracted, swap via config |
| MCP replaced or forked | MEDIUM | Linux Foundation standard, 150+ orgs |
| OPA/Rego loses momentum | LOW-MEDIUM | CNCF graduated, but 2,100 lines of Rego |
| Strands direction changes | MEDIUM | M12 isolated, abstract behind interface |
| Regulatory shifts | LOW | OPA bundles additive, jurisdiction overlays |
| Competitor leapfrogs | HIGH | 15-21 month window, must ship not just design |
| K8s complexity backlash | LOW-MEDIUM | Operator + SaaS mitigates |

---

## What Is Still Missing

Critical (blocks Phase 0): docker-compose, seed data, enterprise config template, canonical schema fields, first OPA rules.

High (blocks Phase 1): Kiro steering files, Kiro hooks, GitHub Actions CI/CD, Helm charts, multi-tenant design.

Medium (blocks Phase 2): SaaS model, M6 upgrade strategy, K8s operator, topology test matrix, vendor abstraction interfaces.

Strategic (long-term): Strands abstraction, LangGraph abstraction, MCP migration strategy, OPA migration path, A2A integration.

---

## Overall Scores

| Dimension | Score |
|-----------|-------|
| Modularity | 7/10 |
| Reproducibility | 6/10 |
| Flexibility | 8/10 |
| Ease of Deploy | 5/10 |
| Future-Proofing | 7/10 |
| OVERALL | 6.6/10 |

Product is designed. Platform is not.

---

## 5 Actions

1. BUILD DOCKER-COMPOSE FIRST — Day 1 of Phase 0. PostgreSQL + Redis + OPA + Langfuse + MinIO. Every engineer starts here.

2. ABSTRACT VENDOR DEPENDENCIES — Strands, LangGraph, OPA, Keycloak each behind an interface. FSI moves in 5-year cycles. Survive vendor pivots.

3. DESIGN MULTI-TENANT FROM DAY 1 — Bolt-on later means rebuilding M1, M6, M10, all OPA bundles. Namespace + keys + bundles per tenant now.

4. PLAN SAAS FOR TIER 3/4 — These firms cannot deploy Kubernetes. Managed SaaS before Phase 2 lighthouse.

5. BUILD DEPLOY-FROM-ZERO SCRIPT — One command, full stack, fresh environment. More than 30 minutes and 10 manual steps means no enterprise adoption.
