# Project 007 v3: Full Agentic SDLC — 28 Agents Across 8 Tiers

> Date: April 12, 2026
> Problem: Build strategy designed 9 agents covering BUILD only. Writing code is 30% of shipping software. The other 70% — review, test, security, docs, deploy, monitor, evaluate — was missing.
> Solution: Complete agentic SDLC with 28 agents across 8 tiers.

---

## Gap Analysis

| Phase | Designed | Needed | Gap |
|-------|----------|--------|-----|
| Design | 2 | 2 | None |
| Build | 6 | 6 | None |
| Review | 0 | 3 | 3 missing |
| Test | 0 | 6 | 6 missing |
| Security | 0 | 2 | 2 missing |
| Documentation | 0 | 3 | 3 missing |
| Deploy/Monitor | 0 | 5 | 5 missing |
| Evaluation | 1 | 3 | 2 missing |
| TOTAL | 9 | 28 | 19 missing |

---

## Tier 1: Design Agents (done)

Architect Agent (human + Kiro) — specs, reviews, approves

LLMJ Committee (5 specialists) — scores architecture per version (v1 5.1, v2 7.5, v3 8.2)

## Tier 2: Build Agents (designed)

Trust (M1, M2/M4, M10), Schema (M3, M7), Gateway (M6), Pipeline (M8, M9), Adapter (M11), Compliance (Gaps 1-7)

## Tier 3: Review Agents (NEW)

**Code Review Agent** — reviews every PR. Checks quality, patterns, naming, complexity. Checks code matches v2/v3 design. Checks tests exist. Runs ruff, mypy, eslint. Produces approve/request-changes. Trigger: every PR.

**Architecture Review Agent** — reviews cross-module changes. Checks module boundaries, dependency direction, API contract stability, canonical schema consistency. Produces architecture compliance report. Trigger: PRs touching multiple modules.

**Compliance Review Agent** — reviews all OPA/Rego changes. Checks wsp_section annotations, fail-closed behavior, MNPI field identification, anti-tipping-off rules, jurisdiction overlay consistency. Produces compliance review for SME sign-off. Trigger: any OPA bundle change.

## Tier 4: Test Agents (NEW)

**Unit Test Agent** — generates pytest/vitest tests for every module. Targets 80%+ coverage. Test-driven: generates tests from spec, build agent writes code to pass. Trigger: after every build.

**Integration Test Agent** — tests cross-module flows end-to-end. Tests full request path (M12->M9->M2->M6->M11->M7->M4->M10). Tests HITL gate pause/resume. Tests multi-agent routing. Tests cross-channel memory. Uses docker-compose. Trigger: after every task.

**Eval Suite Agent** — runs 1,230+ query evaluation suite. Tracks scores over time. Generates reports per dimension per archetype. Trigger: phase gates + weekly.

**Adversarial Test Agent** — runs 200+ attacks. MNPI leakage, authority bypass, cross-pod access, Chinese wall violation, SAR tipping-off, HITL bypass, prompt injection, data exfiltration. Zero tolerance: ANY failure blocks release. Trigger: phase gates + monthly.

**Performance Test Agent** — load tests (100 concurrent users), latency SLA verification per specialist, LLM cost per query, stress tests (10x load), soak tests (24hr). Tools: locust/k6. Trigger: Phase 2+ before production deploys.

**Schema Reconciliation Agent** — compares canonical output vs source system values for every M7 translator. Runs against real vendor sandbox data. Flags semantic mismatches (the number one technical risk). Trigger: daily + every translator change.

## Tier 5: Security Agents (NEW)

**Security Audit Agent** — scans for hardcoded secrets, injection vulnerabilities, CVEs in dependencies, MNPI in logs/traces/errors, missing mTLS, missing encryption. Tools: bandit, semgrep, trivy, detect-secrets. Trigger: every PR + weekly full scan.

**Pen Test Agent** — automated penetration testing of M6 gateway. Tests auth bypass, authorization escalation, rate limit evasion, MNPI extraction, cross-tenant access, WORM tampering. Trigger: monthly + phase gates.

## Tier 6: Documentation Agents (NEW)

**API Documentation Agent** — auto-generates OpenAPI specs from FastAPI, MCP tool catalogs from adapters, OPA policy docs from Rego, JSON Schema docs from canonical types. Keeps docs in sync with code. Trigger: every code change.

**Runbook Agent** — generates operational runbooks per module. Startup, shutdown, health check, troubleshooting, incident response, DR/failover, scaling. Trigger: infrastructure/config changes.

**WSP Documentation Agent** — generates human-readable WSP sections from Rego rules (Gap 3). Maintains cross-reference registry. Flags rule changes without WSP update. Generates FINRA examination report on demand. Trigger: every OPA change.

## Tier 7: Deploy and Monitor Agents (NEW)

**CI/CD Agent** — manages GitHub Actions. Pipeline: lint, type check, unit test, build, push, deploy staging, integration test, eval suite, promote production. Enforces all 4 quality gates. Blue-green deployments. Canary for M6/M9. Auto-rollback if error rate exceeds 1%. Trigger: every commit.

**Infrastructure Agent** — manages Terraform/CDK and Helm charts. Handles scaling, resource allocation, cost optimization. Runs terraform plan on every change. Manages 3 topologies (cloud, hybrid, on-prem). Trigger: infrastructure changes.

**Health Check Agent** — monitors all 12 modules continuously. M6 latency, OPA eval time, WORM write success (must be 100%), MCP server availability, LLM provider health, memory store health. Alerts via PagerDuty. Grafana dashboards for ops and CCO. Trigger: continuous.

**Incident Response Agent** — triggered by health check alerts. Diagnoses failure, activates circuit breakers, triggers failover, generates incident report (DORA 4-hour SLA), preserves evidence for post-mortem. Trigger: on alert.

**Cost Monitor Agent** — tracks LLM cost per query per specialist per tenant, infrastructure cost per module, vendor API cost per adapter. Calculates unit economics. Alerts on budget breach. Monthly cost report. Trigger: continuous.

## Tier 8: Ongoing Evaluation (partially done)

**LLMJ Committee** (done) — 5 reviewers, per version, 3 cycles completed.

**Regression Agent** (NEW) — runs full eval suite on every release. Compares against baseline. Blocks release if any dimension regresses more than 0.5. Tracks trends. Trigger: every release.

**Benchmark Agent** (NEW) — compares 007 against competitors quarterly. Tracks Envestnet, Agentforce, Aladdin Copilot. Recalibrates competitive window. Trigger: quarterly.

---

## The Full Pipeline

```
DESIGN
  Architect + LLMJ Committee
      |
BUILD
  6 Specialist Agents write code
      |
REVIEW (before merge)
  Code Review + Architecture Review + Compliance Review + Security Audit
      |
TEST (after merge)
  Unit Test + Integration Test + Schema Reconciliation
      |
DOCUMENT (auto-generated)
  API Docs + WSP Docs + Runbooks
      |
DEPLOY
  CI/CD Agent + Infrastructure Agent
      |
VERIFY (post-deploy)
  Eval Suite + Adversarial Test + Performance Test + Regression
      |
MONITOR (continuous)
  Health Check + Cost Monitor + Incident Response
      |
EVALUATE (periodic)
  LLMJ Committee + Benchmark Agent
```

---

## Why the Missing 70% Is Non-Negotiable for FSI

| Agent | Why Non-Negotiable |
|-------|--------------------|
| Adversarial Test | MNPI leakage is a federal crime. Must prove it cannot happen. |
| Schema Reconciliation | Number one technical risk. Silent mismatches cause fiduciary breaches. |
| WSP Documentation | FINRA examiner will ask for supervisory procedures. |
| Compliance Review | Every OPA rule change affects regulatory compliance. |
| Security Audit | SOC 2 Type II requires continuous security scanning. |
| Pen Test | FINRA and DORA require penetration testing. |
| Incident Response | DORA requires 4-hour incident notification. |
| Cost Monitor | Pricing ($500-$25K/mo) must be validated against actual costs. |
| Regression | Cannot ship a release that degrades compliance accuracy. |
| Health Check | WORM write failure is a regulatory violation. Must catch instantly. |

---

## Summary

| Category | Count | Status |
|----------|-------|--------|
| Design | 2 | Done |
| Build | 6 | Designed |
| Review | 3 | NEW |
| Test | 6 | NEW |
| Security | 2 | NEW |
| Documentation | 3 | NEW |
| Deploy/Monitor | 5 | NEW |
| Evaluation | 3 | 1 done, 2 NEW |
| TOTAL | 28 | 9 done, 19 new |

Writing code is 30%. The other 70% makes it production-ready, compliant, secure, documented, deployable, and monitorable. For FSI, that 70% is not optional.
