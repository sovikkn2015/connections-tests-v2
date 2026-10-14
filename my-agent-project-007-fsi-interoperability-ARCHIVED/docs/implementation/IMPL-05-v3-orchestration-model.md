# Project 007 v3: Orchestration Model — How to Run 28 Agents

> Date: April 12, 2026
> Category: IMPLEMENTATION UTILS (how to build, not what to build)
> Answer: You don't run 28 agents. You run 6 build agents (one at a time). The other 22 are automated infrastructure you set up once.

---

## The 4 Categories

| Category | Count | How They Run | Your Involvement |
|----------|-------|-------------|-----------------|
| Active (build specialists) | 6 | You invoke, one at a time | HIGH |
| Reactive (hooks + CI/CD) | 15 | Fire automatically on events | ZERO |
| Scheduled (periodic jobs) | 5 | Run on timers | LOW — review results |
| On-demand (when needed) | 2 | You call when needed | LOW — occasional |

At any moment you manage ONE active build agent. The other 22 are automated.

---

## Reactive Agents (15) — set up once, run forever

| Agent | Implementation | Trigger |
|-------|---------------|---------|
| Code Review | Kiro hook (postToolUse: write) | Every file write |
| Architecture Review | Kiro hook (preToolUse: write) | Cross-module writes |
| Compliance Review | Kiro hook (postToolUse: write) | OPA file changes |
| Security Audit | GitHub Actions + bandit/semgrep/trivy | Every PR + weekly |
| Unit Test | Kiro hook (postTaskExecution) | After every build |
| Integration Test | GitHub Actions (on merge) | Every merge |
| Schema Reconciliation | GitHub Actions (daily cron) | Daily |
| API Docs | GitHub Actions (on code change) | Every code change |
| WSP Docs | Kiro hook (on OPA file change) | OPA changes |
| Runbook | GitHub Actions (on infra change) | Infra changes |
| CI/CD | GitHub Actions (on commit) | Every commit |
| Infrastructure | GitHub Actions (on IaC change) | IaC changes |
| Health Check | Prometheus + Grafana + PagerDuty | Continuous |
| Cost Monitor | CloudWatch + custom Lambda | Continuous |
| Regression | GitHub Actions (on release tag) | Every release |

## Scheduled Agents (5) — periodic jobs

| Agent | Schedule |
|-------|----------|
| Eval Suite (1,230+ queries) | Weekly + phase gates |
| Adversarial Test (200+ attacks) | Monthly + phase gates |
| Performance Test (load + latency) | Pre-deploy |
| Pen Test (OWASP ZAP) | Monthly |
| Benchmark (competitive) | Quarterly |

## On-Demand Agents (2)

| Agent | When |
|-------|------|
| LLMJ Committee (5 reviewers) | Per version review |
| Incident Response | On alert |

---

## Which Are Actually LLM Agents?

LLM agents: ~15 (build specialists + review hooks + LLMJ + docs generation)

Automation/tooling: ~13 (scripts, CI/CD, monitoring, testing frameworks)

Most of the "28 agents" are well-configured automation, not LLM agents.

---

## The Assembly Line

```
STATION 1: BUILD — you invoke ONE specialist
      | (hooks fire automatically)
STATION 2: REVIEW — Code + Architecture + Compliance + Security
      | (CI/CD fires automatically)
STATION 3: TEST — Unit + Integration
      | (doc generation fires automatically)
STATION 4: DOCUMENT — API docs + WSP docs + Runbooks
      | (verification runs at phase gates)
STATION 5: VERIFY — Eval suite + Adversarial + Performance
      | (monitoring starts automatically)
STATION 6: MONITOR — Health + Cost + Incident Response
```

You manage Station 1. Stations 2-6 are automated.

---

## Your Daily Workflow

Morning: Check overnight results (CI/CD, health, cost, schema reconciliation). Pick today's build task. Invoke the right specialist.

During day: Build agent writes code (hooks fire on each write). You review output. Merge and test (CI/CD runs automatically).

End of day: Check test results. Update progress.

Phase gates (every 4-8 weeks): Run full verification. Review results. LLMJ Committee review if version change.

---

## Setup Order

Week 0-1: Set up the factory (steering files, hooks, CI/CD, monitoring). After this, reactive agents are LIVE.

Week 1-2: Set up scheduled frameworks (eval suite, adversarial, schema reconciliation, performance). Empty frameworks ready for content.

Week 2+: Start building. Invoke build agents one at a time. The factory handles everything else.

---

## The Honest Summary

You don't orchestrate 28 agents. You orchestrate 6 build agents (one at a time). You set up 15 reactive automations (once). You schedule 5 periodic jobs (once). You call 2 on-demand agents when needed.

It is not a war room with 28 agents. It is an assembly line with 6 workers and 22 machines.

---

## Document Taxonomy

For clarity, the 007 docs are organized as:

DESIGN and ARCHITECTURE (the product):
- 007-intersystem-interoperability-architecture.md
- 007-five-layers-of-interoperability.md
- 007-module-architecture-and-interconnectivity.md
- 007-v2-tech-stack-decisions.md
- 007-v2-multi-agent-and-memory-architecture.md
- 007-v3-compliance-gap-designs.md

RESEARCH and ANALYSIS (informing the design):
- 007-fsi-enterprise-archetypes-technology-analysis.md
- 007-competitive-landscape-and-gap-analysis.md
- 007-implementability-and-accuracy-assessment.md
- 007-fsi-railway-platform-and-adoption.md
- 007-simple-railway-diagram.md
- 007-railway-track-diagram.md

REVIEWS (quality gates):
- REVIEW-01-architecture-and-tech-stack.md
- REVIEW-02-to-05-committee-assessments.md
- REVIEW-v2-committee-reassessment.md
- REVIEW-v3-final-committee-assessment.md

IMPLEMENTATION UTILS (how to build):
- 007-v2-implementation-plan.md
- 007-v2-findings-summary.md
- 007-v3-build-strategy-specialist-skills.md
- 007-v3-full-agentic-sdlc.md
- 007-v3-orchestration-model.md (this document)
