# REV-10: Bedrock AgentCore, Auth, and AWS Well-Architected — Honest Gaps

> Date: April 18, 2026
> Purpose: Document gaps between architecture docs and actual code
> Scope: Bedrock AgentCore, authentication/authorization, AWS Well-Architected 6 pillars

---

## 1. BEDROCK AGENTCORE

Architecture says Managed Agents is default runtime. Helm values set it. But no code calls the Bedrock AgentCore API. M9 classifies intents locally. M8 uses LangGraph locally. Supervisor routing is Python, not Managed Agents.

| Component | Architecture Says | Code Reality |
|-----------|------------------|-------------|
| Agent orchestration | Managed Agents (cloud) | Self-orchestrated via LangGraph + FastAPI |
| Specialist routing | Managed Agents supervisor | Python routing in M9 + web_api.py |
| Long-running sessions | Managed Agents sessions | LangGraph checkpointing (DynamoDB) |
| Runtime toggle | Helm values config | Config exists, zero API calls behind it |

Not a blocker for wedge product. Phase 2 integration task.

---

## 2. AUTHENTICATION AND AUTHORIZATION

### Implemented (Real)
- M1 JWT RS256 with FSI claims (real RSA-2048 crypto)
- M2/M4 OPA/Rego (2,100+ rules, deny-by-default, 29 + 30 adversarial tests)
- M6 Web API role-based access on all 13 endpoints
- AID token in memory only (never localStorage)

### NOT Implemented
| Component | Status | When to Fix |
|-----------|--------|-------------|
| Keycloak integration | Zero code calls Keycloak | Phase 2 (RIA lighthouse) |
| Token refresh | Not implemented | Phase 2 |
| MFA | Not implemented | Phase 3 (BD onboarding) |
| OAuth 2.0 PKCE flow | Scaffolded, not functional | Phase 2 |

Auth works for dev/demo. Production needs Keycloak wired as real IdP.

---

## 3. AWS WELL-ARCHITECTED — 6 PILLARS

### Security — STRONGEST (8/10)
- mTLS (cert-manager, 24hr rotation), PrivateLink for Bedrock, private subnets, per-tenant KMS, OPA/Rego, MNPI filtering, zero creds in code, Trivy scanning, 30 adversarial tests
- Missing: WAF, GuardDuty, Security Hub

### Reliability — PARTIAL (6/10)
- Circuit breakers, rate limiting, retry, fail-closed, ArgoCD self-heal
- Missing: HPA, SQS DLQ (in-memory only), multi-AZ EKS nodes, chaos testing

### Operational Excellence — PARTIAL (5/10)
- CI/CD (11-job), GitOps (ArgoCD), health checks, structured logging
- Missing: CloudWatch dashboards, alerting rules, automated runbooks

### Performance Efficiency — PARTIAL (5/10)
- Benchmarks (11 tests, all pass), resource limits in Helm, Redis for hot path
- Missing: HPA, load testing, Graviton/ARM

### Cost Optimization — DESIGNED (2/10)
- 3 topology pricing documented, Phase 5 deferred
- Missing: Spot instances, Savings Plans, cost tags, right-sizing

### Sustainability — NOT ADDRESSED (0/10)

---

## 4. SCORECARD

| Area | Design | Code | Gap |
|------|--------|------|-----|
| Bedrock AgentCore | 9/10 | 2/10 | Config toggle, zero API calls |
| Auth (M1 JWT) | 8/10 | 7/10 | Real crypto, no Keycloak |
| Auth (M2/M4 OPA) | 9/10 | 9/10 | Real and tested |
| WA: Security | 9/10 | 8/10 | No WAF/GuardDuty |
| WA: Reliability | 8/10 | 6/10 | No HPA, no SQS DLQ |
| WA: Ops | 7/10 | 5/10 | No dashboards |
| WA: Performance | 7/10 | 5/10 | No HPA, no load test |
| WA: Cost | 6/10 | 2/10 | Designed not implemented |
| WA: Sustainability | 2/10 | 0/10 | Not addressed |

---

## 5. FIX TIMELINE

Phase 1 (Wedge): None are blockers.
Phase 2 (Lighthouse): Keycloak, OAuth PKCE, token refresh, Bedrock AgentCore, HPA, SQS DLQ.
Phase 3 (BD): MFA, WAF, GuardDuty, Security Hub, dashboards, load testing.
Phase 4 (Expansion): Cross-region DR, Spot, cost tags, Graviton.

---

*REV-10 — Project 007 FSI Interoperability Platform*
