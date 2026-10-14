# SOC 2 Type II Audit Preparation — Project 007 FSI Interoperability Platform

> Version: 1.0
> Date: July 2026
> Status: Preparation Phase (aligned with Phase 3 build order)
> Audience: Engineering, Compliance, External Auditors
> Scope: SOC 2 Type II readiness for the 007 FSI Platform trust layer and intelligence layer

---

## 1. EXECUTIVE SUMMARY

Project 007 is an FSI interoperability platform handling regulated financial data across 13 modules. SOC 2 Type II certification is required before BD (broker-dealer) onboarding in Phase 3. This document maps existing 007 controls to SOC 2 Trust Service Criteria, identifies gaps, and provides a realistic timeline.

The platform's architecture — deterministic OPA/Rego compliance, 3-tier WORM audit, mTLS everywhere, fail-closed trust layer — provides strong foundational coverage. The primary gaps are in formal documentation, monitoring dashboards, and incident response procedures.

---

## 2. TRUST SERVICE CRITERIA MAPPING

### 2.1 Security (Common Criteria — CC)

| TSC | Criterion | 007 Control | Evidence | Status |
|-----|-----------|-------------|----------|--------|
| CC1.1 | Integrity and ethical values | Code review policy, PR approval gates | GitHub branch protection rules, PR history | PARTIAL — needs formal policy doc |
| CC1.2 | Board oversight | Architecture review board (ARCH docs) | ARCH-04, ARCH-06, ARCH-09 documents | EXISTS |
| CC2.1 | Information and communication | Module map (ARCH-09), design docs | docs/architecture/ directory | EXISTS |
| CC3.1 | Risk assessment | Compliance gap analysis (ARCH-06) | 7 gap designs with regulatory context | EXISTS |
| CC5.1 | Logical access controls | M1 Agent Identity (JWT RS256, Keycloak) | M1 source code, AID schema, Keycloak config | EXISTS |
| CC5.2 | Authentication | M1 AID with FSI claims (LEI, CRD, archetype, role) | JWT token structure, RS256 verification | EXISTS |
| CC5.3 | Authorization | M2 Authority Policy (OPA/Rego, 2100+ rules) | OPA bundles, policy test results | EXISTS |
| CC6.1 | Logical and physical access | mTLS between all modules (cert-manager, 24hr rotation) | Helm values (tls config), cert-manager setup | EXISTS |
| CC6.2 | System boundaries | NetworkPolicy per module, namespace isolation | Helm templates, values-cloud/hybrid.yaml | EXISTS |
| CC6.3 | External access | PrivateLink for Bedrock, no public internet for MNPI | VPC config, PrivateLink endpoints | EXISTS |
| CC6.6 | Threat management | Trivy CVE scanning in CI/CD, dependency scanning | GitHub Actions workflow (security-scan job) | EXISTS |
| CC6.7 | Identity management | M1 AID lifecycle (issue, verify, revoke) | M1 API endpoints, Keycloak integration | EXISTS |
| CC6.8 | Authentication mechanisms | JWT RS256 with FSI-specific claims | PyJWT implementation, key rotation | EXISTS |
| CC7.1 | System monitoring | Langfuse observability (M10 Tier 1), health checks | Langfuse traces, /health endpoints | EXISTS |
| CC7.2 | Anomaly detection | OPA adversarial tests, MNPI leakage scan (3-layer) | tests/adversarial/, Gap 6 implementation | EXISTS |
| CC7.3 | Security event evaluation | 3-tier audit (Langfuse + WORM + CRM) | M10 audit logger, S3 Object Lock config | EXISTS |
| CC7.4 | Incident response | — | — | GAP |
| CC8.1 | Change management | GitOps (ArgoCD), CI/CD pipeline, PR reviews | ArgoCD config, GitHub Actions, branch protection | EXISTS |
| CC9.1 | Vendor management | M11 adapter isolation (each = own container) | Docker configs, M6 gateway trust enforcement | PARTIAL |
| CC9.2 | Vendor monitoring | Circuit breakers in M6, health checks per adapter | M6 gateway code, docker-compose health checks | EXISTS |

### 2.2 Availability (A)

| TSC | Criterion | 007 Control | Evidence | Status |
|-----|-----------|-------------|----------|--------|
| A1.1 | Capacity planning | Helm resource limits per module | values.yaml, values-cloud.yaml, values-hybrid.yaml | EXISTS |
| A1.2 | Environmental protections | AWS infrastructure (cloud), customer-managed (hybrid) | Terraform configs, deployment docs | PARTIAL |
| A1.3 | Recovery procedures | ArgoCD self-heal, retry policies, DLQ for failed audits | ArgoCD sync policy, M10 DLQ | PARTIAL |

### 2.3 Processing Integrity (PI)

| TSC | Criterion | 007 Control | Evidence | Status |
|-----|-----------|-------------|----------|--------|
| PI1.1 | Completeness | Fail-closed on all trust decisions (Rule 8) | M6 gateway code, M10 3-tier write enforcement | EXISTS |
| PI1.2 | Accuracy | OPA/Rego deterministic evaluation (99.9%), schema validation | OPA test results, M3 schema validation | EXISTS |
| PI1.3 | Timeliness | Health checks, circuit breakers, timeout configs | Docker health checks, M6 circuit breaker | EXISTS |
| PI1.4 | Output completeness | SHA-256 integrity hash on every audit write (Rule 3) | M10 audit logger, provenance chain (Gap 2) | EXISTS |
| PI1.5 | Output accuracy | Schema reconciliation tests, adversarial tests | tests/schema-reconciliation/, tests/adversarial/ | EXISTS |

### 2.4 Confidentiality (C)

| TSC | Criterion | 007 Control | Evidence | Status |
|-----|-----------|-------------|----------|--------|
| C1.1 | Identification | M4 MNPI Policy (OPA/Rego field-level filtering) | MNPI Rego rules, archetype-based filtering | EXISTS |
| C1.2 | Disposal | S3 Object Lock WORM (6-year retention, then lifecycle) | S3 bucket config, retention policy | EXISTS |
| C1.3 | Protection | mTLS, per-tenant KMS, MNPI filtering before LLM | TLS config, M4 filter rules, KMS setup | EXISTS |

### 2.5 Privacy (P)

| TSC | Criterion | 007 Control | Evidence | Status |
|-----|-----------|-------------|----------|--------|
| P1.1 | Privacy notice | — | — | GAP |
| P2.1 | Choice and consent | HITL gates for all recommendations and orders | Execution specialist state machine, HITL tokens | EXISTS |
| P3.1 | Collection limitation | M4 MNPI filtering strips PII before LLM | M4 Rego rules, MNPI filter log | EXISTS |
| P4.1 | Use limitation | Authority scope in AID (authority_scope, authority_excludes) | M1 AID schema, M2 authority rules | EXISTS |
| P6.1 | Data quality | M3 canonical schema validation (18 types, Pydantic v2) | Schema definitions, translator tests | EXISTS |
| P7.1 | Monitoring | M10 3-tier audit, MNPI filter log per data access | Audit entries, MNPI logs | EXISTS |

---

## 3. EVIDENCE INVENTORY

### 3.1 Technical Controls (Code-Level)

| Evidence | Location | Description |
|----------|----------|-------------|
| OPA/Rego policy bundles | `opa-bundles/` | 2100+ rules with wsp_section annotations |
| OPA policy tests | `opa-bundles/*/test_*.rego` | Automated tests for every policy bundle |
| M1 Agent Identity | `src/m1-identity/` | JWT RS256 with FSI claims (LEI, CRD, archetype, role) |
| M10 Audit Logger | `src/m10-audit-logger/` | 3-tier write: Langfuse + S3 Object Lock WORM + CRM |
| M4 MNPI Filter | `src/m2-m4-policy-engine/` | Per-field filtering by archetype/role/jurisdiction |
| Adversarial tests | `tests/adversarial/` | Policy bypass, MNPI leakage, privilege escalation tests |
| Schema reconciliation | `tests/schema-reconciliation/` | Vendor-to-canonical translation accuracy tests |
| Integration tests | `tests/integration/` | Cross-module integration tests |
| Canonical schemas | `schemas/canonical/` | JSON Schema definitions for 18 FSI data types |
| Enterprise configs | `config/` | Per-firm YAML configs (tier3-bd, tier4-ria) |

### 3.2 Infrastructure Controls

| Evidence | Location | Description |
|----------|----------|-------------|
| CI/CD pipeline | `.github/workflows/007-ci.yml` | 11-job pipeline: lint, test, build, scan, deploy |
| ArgoCD GitOps | `infra/argocd/` | Application + AppProject with RBAC and sync windows |
| Helm charts | `infra/helm/007-platform/` | Umbrella chart with cloud/hybrid values and resource limits |
| Docker configs | `src/*/Dockerfile` | Per-module Dockerfiles with no embedded credentials |
| Trivy scanning | CI/CD security-scan job | CVE scanning on every image build |
| Network isolation | Helm NetworkPolicy | Per-module network policies |

### 3.3 Design Documentation

| Evidence | Location |
|----------|----------|
| Tech stack decisions | `docs/architecture/ARCH-04-v2-tech-stack-decisions.md` |
| Compliance gap designs | `docs/architecture/ARCH-06-v3-compliance-gap-designs.md` |
| Complete module map | `docs/architecture/ARCH-09-complete-module-map.md` |
| Consolidated design | `docs/007-consolidated-design-and-plan.md` |
| Blocker resolution | `docs/implementation/IMPL-06-blocker-resolution-plan.md` |

---

## 4. GAP ANALYSIS

### 4.1 Critical Gaps (Must Fix Before Audit)

| ID | TSC | Description | Effort | Owner |
|----|-----|-------------|--------|-------|
| G1 | CC7.4 | Incident Response Plan — formal IR with escalation, communication templates, post-incident review | 2 weeks | Security + Compliance |
| G2 | A1.2/A1.3 | Disaster Recovery Runbook — RTO/RPO targets, failover procedures, backup verification | 2 weeks | Platform Engineering |
| G3 | CC9.1 | Vendor Risk Register — all 17+ vendor integrations with risk ratings and annual review | 1 week | Compliance |
| G4 | P1.1 | Privacy Policy — data collection, use, retention, deletion for platform | 1 week | Legal + Compliance |
| G5 | CC1.1 | Information Security Policy — code of conduct, acceptable use, data classification | 1 week | Security |
| G6 | CC5.1 | Access Review Procedures — quarterly review for Keycloak, ArgoCD RBAC, AWS IAM | 1 week | Security |

### 4.2 Moderate Gaps

| ID | TSC | Description | Effort | Owner |
|----|-----|-------------|--------|-------|
| G7 | CC7.1 | Monitoring Dashboard — centralized Grafana for all 13 modules | 2 weeks | Platform Engineering |
| G8 | CC6.6 | Penetration Test — third-party pentest, required annually for Type II | 4 weeks (vendor) | Security |
| G9 | A1.2 | Business Continuity Plan — personnel, communication, alternate processing | 1 week | Operations |
| G10 | CC8.1 | Change Management Policy — formal doc of GitOps workflow and rollback | 1 week | Platform Engineering |

### 4.3 Low Gaps

| ID | TSC | Description | Effort | Owner |
|----|-----|-------------|--------|-------|
| G11 | CC1.4 | Security Awareness Training — annual training with completion tracking | Ongoing | Security |
| G12 | C1.2 | Data Retention Schedule — formal schedule beyond WORM 6-year | 3 days | Compliance |

---

## 5. TIMELINE — ALIGNED WITH PHASE 3

Phase 3 is BD onboarding. SOC 2 Type II requires a minimum 6-month observation period.

```
Month 1-2:  Gap Remediation (G1-G6, G10)
Month 2-3:  Evidence Collection Setup (G7, automated exports, quarterly reviews)
Month 3:    Auditor Selection + Readiness Assessment
Month 4-9:  Observation Period (6 months)
              - Controls operating as designed
              - Quarterly access reviews (minimum 2)
              - Penetration test (G8)
              - Incident response drill (minimum 1)
Month 10-11: Type II Audit Fieldwork (4-6 weeks)
Month 12:    Report Issuance
```

### 5.1 Key Milestones

| Milestone | Target | Dependency |
|-----------|--------|------------|
| Gap remediation complete | Phase 3 Month 2 | G1-G6, G10 |
| Auditor selected | Phase 3 Month 3 | Procurement |
| Readiness assessment | Phase 3 Month 3 | Auditor engagement |
| Observation period start | Phase 3 Month 4 | Readiness passed |
| Penetration test complete | Phase 3 Month 6 | Vendor scheduling |
| Observation period end | Phase 3 Month 9 | 6 months elapsed |
| Type II report issued | Phase 3 Month 12 | Fieldwork complete |

---

## 6. AUDITOR SELECTION CRITERIA

### 6.1 Required Qualifications

| Criterion | Requirement |
|-----------|-------------|
| AICPA membership | Active CPA firm with peer review |
| FSI experience | Minimum 5 FSI SOC 2 engagements in past 3 years |
| AI/ML familiarity | Experience auditing AI/ML systems (LLM guardrails, HITL) |
| Cloud-native | AWS, Kubernetes, GitOps audit experience |
| Policy-as-code | Familiarity with OPA/Rego or equivalent |

### 6.2 Evaluation Weights

| Factor | Weight |
|--------|--------|
| FSI regulatory depth (SEC 17a-4, FINRA 3110, Reg BI) | 30% |
| Technical competence (K8s, mTLS, WORM, CI/CD) | 25% |
| AI system audit experience | 20% |
| Timeline fit | 15% |
| Cost | 10% |

### 6.3 Firm Categories

- **Big 4** (Deloitte, EY, PwC, KPMG) — highest credibility, highest cost
- **Mid-tier with FSI practice** (BDO, Grant Thornton, RSM) — good balance
- **Boutique SOC 2 specialists** (Schellman, A-LIGN, Coalfire) — fastest, most technical

---

## 7. PLATFORM-SPECIFIC AUDIT CONSIDERATIONS

### 7.1 Deterministic vs Probabilistic Controls

The auditor must understand 007's compliance warranty boundary (ARCH-06 Gap 2):
- **Deterministic (warranted):** M1 identity, M2/M4 OPA policy, M3 schema, M10 audit, HITL gates
- **Probabilistic (best-effort):** M8 LLM synthesis, M9 intent classification, specialist responses

HITL gates mitigate LLM risk. The platform does NOT warrant LLM output accuracy.

### 7.2 WORM Storage (SEC 17a-4)

S3 Object Lock in Compliance mode, 6-year retention. Auditor should verify immutability, retention period, SHA-256 integrity, and no delete/modify mechanism during retention.

### 7.3 OPA Policy Traceability

Every OPA rule has a `wsp_section` annotation. Any compliance decision traces back to the specific Written Supervisory Procedure section. Policy bundle hashes are recorded in audit entries.

### 7.4 Fail-Closed Architecture

007 is fail-closed on ALL trust decisions. OPA unreachable = DENY. Audit tier failure = request failure. HITL gates cannot be bypassed. Availability may be impacted by security controls — this is an intentional design trade-off.

---

*SOC 2 Type II Preparation — Project 007 FSI Interoperability Platform*
