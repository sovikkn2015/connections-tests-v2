# SOC 2 Control Matrix — Project 007 FSI Interoperability Platform

> Version: 1.0
> Date: July 2026
> Companion to: soc2-type2-prep.md
> Purpose: Detailed control-by-control mapping for SOC 2 Type II audit evidence collection

---

## CONTROL MATRIX LEGEND

- **Control ID**: Internal 007 control identifier
- **TSC**: SOC 2 Trust Service Criteria reference
- **Control Description**: What the control does
- **Implementation**: How 007 implements it
- **Evidence Source**: Where to find proof
- **Frequency**: How often the control operates
- **Status**: EXISTS / PARTIAL / GAP

---

## 1. SECURITY CONTROLS (CC)

### 1.1 Control Environment

| Control ID | TSC | Control Description | Implementation | Evidence Source | Frequency | Status |
|------------|-----|---------------------|----------------|----------------|-----------|--------|
| SEC-001 | CC1.1 | Information security policy | Formal security policy document | `docs/` (Gap G5) | Annual review | GAP |
| SEC-002 | CC1.2 | Architecture review board oversight | ARCH docs reviewed and approved | `docs/architecture/ARCH-04`, `ARCH-06`, `ARCH-09` | Per design change | EXISTS |
| SEC-003 | CC1.3 | Personnel security and role assignment | Keycloak role assignment, AID archetype/role claims | M1 Keycloak config, AID JWT claims | Per onboarding | EXISTS |
| SEC-004 | CC2.1 | System design documented | 13-module architecture with complete module map | `docs/architecture/ARCH-09-complete-module-map.md` | Per release | EXISTS |

### 1.2 Logical Access

| Control ID | TSC | Control Description | Implementation | Evidence Source | Frequency | Status |
|------------|-----|---------------------|----------------|----------------|-----------|--------|
| SEC-010 | CC5.1 | Logical access restricted | M1 Agent Identity Document (JWT RS256) with FSI claims | `src/m1-identity/`, Keycloak realm config | Every request | EXISTS |
| SEC-011 | CC5.2 | User authentication | JWT RS256 verification with Keycloak-issued tokens | M1 `/verify` endpoint, PyJWT RS256 | Every request | EXISTS |
| SEC-012 | CC5.3 | Per-request authorization | M2 OPA/Rego authority policy (2100+ rules) | `opa-bundles/authority/`, OPA decision logs | Every request | EXISTS |
| SEC-013 | CC5.3 | Least privilege enforcement | AID `authority_scope` and `authority_excludes` claims | M1 AID schema, M2 authority rules | Every request | EXISTS |
| SEC-014 | CC5.1 | Quarterly access reviews | Review of Keycloak roles, ArgoCD RBAC, AWS IAM | Access review reports (Gap G6) | Quarterly | GAP |
| SEC-015 | CC5.3 | MNPI field-level access control | M4 OPA/Rego filters fields by archetype/role/jurisdiction | `opa-bundles/mnpi/`, MNPI filter logs | Every data access | EXISTS |

### 1.3 Network Security

| Control ID | TSC | Control Description | Implementation | Evidence Source | Frequency | Status |
|------------|-----|---------------------|----------------|----------------|-----------|--------|
| SEC-020 | CC6.1 | mTLS encryption in transit | cert-manager mTLS between all modules, 24hr rotation | Helm `tls` config, cert-manager CRDs | Continuous | EXISTS |
| SEC-021 | CC6.2 | Network segmentation | Kubernetes NetworkPolicy per module, namespace isolation | Helm templates, values files | Continuous | EXISTS |
| SEC-022 | CC6.3 | No public internet for MNPI | PrivateLink for Bedrock, private subnets for data plane | VPC config, PrivateLink endpoints | Continuous | EXISTS |
| SEC-023 | CC6.2 | Module boundary enforcement | No cross-module imports; REST/MCP communication only | Code review, import analysis | Every PR | EXISTS |

### 1.4 Threat Management

| Control ID | TSC | Control Description | Implementation | Evidence Source | Frequency | Status |
|------------|-----|---------------------|----------------|----------------|-----------|--------|
| SEC-030 | CC6.6 | Container vulnerability scanning | Trivy CVE scan (CRITICAL/HIGH = build failure) | CI/CD `security-scan` job, SARIF reports | Every build | EXISTS |
| SEC-031 | CC6.6 | Code linting and dependency audit | Ruff lint in CI/CD | CI/CD `lint` job | Every PR | EXISTS |
| SEC-032 | CC6.6 | Adversarial testing | Policy bypass, MNPI leakage, privilege escalation tests | `tests/adversarial/` | Every PR | EXISTS |
| SEC-033 | CC6.6 | MNPI leakage detection | 3-layer output guardrail: regex + NER + LLM scan | M6 gateway, Gap 6 implementation | Every LLM output | EXISTS |
| SEC-034 | CC6.6 | Annual penetration testing | Third-party pentest | Pentest report (Gap G8) | Annual | GAP |

### 1.5 Monitoring and Detection

| Control ID | TSC | Control Description | Implementation | Evidence Source | Frequency | Status |
|------------|-----|---------------------|----------------|----------------|-----------|--------|
| SEC-040 | CC7.1 | Operational observability | Langfuse traces for every interaction (M10 Tier 1) | Langfuse dashboard, trace exports | Continuous | EXISTS |
| SEC-041 | CC7.1 | Health monitoring | `/health` endpoint on every module | Health check configs, uptime metrics | Continuous | EXISTS |
| SEC-042 | CC7.2 | Anomaly detection | OPA adversarial tests, MNPI leakage scan | `tests/adversarial/`, M6 scan results | Every request | EXISTS |
| SEC-043 | CC7.3 | Security event logging | 3-tier audit: Langfuse + S3 Object Lock WORM + CRM | M10 audit logger, S3 bucket | Every event | EXISTS |
| SEC-044 | CC7.3 | Audit integrity verification | SHA-256 hash on every audit entry, WORM immutability | M10 hash computation, S3 Object Lock | Every write | EXISTS |
| SEC-045 | CC7.4 | Incident response procedures | Formal IR plan with escalation and post-incident review | IR plan doc (Gap G1) | Per incident | GAP |

### 1.6 Change Management

| Control ID | TSC | Control Description | Implementation | Evidence Source | Frequency | Status |
|------------|-----|---------------------|----------------|----------------|-----------|--------|
| SEC-050 | CC8.1 | GitOps deployment | ArgoCD automated sync, self-heal, ordered waves | `infra/argocd/application.yaml` | Every deployment | EXISTS |
| SEC-051 | CC8.1 | CI/CD pipeline enforcement | 11-job pipeline with no bypass flags | `.github/workflows/007-ci.yml` | Every PR/push | EXISTS |
| SEC-052 | CC8.1 | Code review requirement | PR approval required before merge | GitHub branch protection rules | Every PR | EXISTS |
| SEC-053 | CC8.1 | OPA policy versioning | Bundles versioned, hashes in audit entries | OPA bundle versions, M10 entries | Every policy change | EXISTS |
| SEC-054 | CC8.1 | Schema change detection | Automated detection script in CI | `scripts/detect-schema-changes.py` | Every PR | EXISTS |

### 1.7 Vendor Management

| Control ID | TSC | Control Description | Implementation | Evidence Source | Frequency | Status |
|------------|-----|---------------------|----------------|----------------|-----------|--------|
| SEC-060 | CC9.1 | Vendor container isolation | Each M11 adapter in its own container | `src/m11-mcp-adapters/*/Dockerfile` | Continuous | EXISTS |
| SEC-061 | CC9.1 | Vendor trust enforcement | All vendor calls through M6 Trust-Aware Gateway | M6 gateway middleware | Every vendor call | EXISTS |
| SEC-062 | CC9.1 | Vendor risk register | Formal register with risk ratings and review schedule | Vendor risk register (Gap G3) | Annual | GAP |
| SEC-063 | CC9.2 | Vendor health monitoring | Circuit breakers in M6, per-adapter health checks | M6 circuit breaker, health checks | Continuous | EXISTS |

---

## 2. AVAILABILITY CONTROLS (A)

| Control ID | TSC | Control Description | Implementation | Evidence Source | Frequency | Status |
|------------|-----|---------------------|----------------|----------------|-----------|--------|
| AVL-001 | A1.1 | Resource capacity planning | Helm resource requests/limits per module | `values.yaml`, `values-cloud.yaml` | Per release | EXISTS |
| AVL-002 | A1.1 | Horizontal scaling | Configurable replica counts per topology | Helm values, HPA configs | Continuous | EXISTS |
| AVL-003 | A1.2 | Infrastructure redundancy | Multi-AZ (cloud), HA replicas for critical modules | Terraform config, Helm replicas | Continuous | EXISTS |
| AVL-004 | A1.2 | Self-healing deployment | ArgoCD self-heal, retry policies | ArgoCD sync policy | Per failure | EXISTS |
| AVL-005 | A1.2 | Dead letter queue for audit | Failed audit writes queued for retry | M10 DLQ implementation | Per failure | EXISTS |
| AVL-006 | A1.3 | Disaster recovery runbook | DR plan with RTO/RPO targets | DR runbook (Gap G2) | Annual test | GAP |
| AVL-007 | A1.2 | Business continuity plan | BCP for personnel, communication, alternate processing | BCP doc (Gap G9) | Annual review | GAP |

---

## 3. PROCESSING INTEGRITY CONTROLS (PI)

| Control ID | TSC | Control Description | Implementation | Evidence Source | Frequency | Status |
|------------|-----|---------------------|----------------|----------------|-----------|--------|
| INT-001 | PI1.1 | Fail-closed processing | OPA unreachable = DENY; no degraded mode | M6 gateway, M2/M4 error handling | Every request | EXISTS |
| INT-002 | PI1.1 | 3-tier audit completeness | All 3 tiers must succeed or request fails | M10 audit logger | Every audit write | EXISTS |
| INT-003 | PI1.2 | Deterministic compliance | OPA/Rego only for compliance (no LLM) | `opa-bundles/`, M2/M4 engine | Every check | EXISTS |
| INT-004 | PI1.2 | Schema validation | M3 canonical types (18 types, Pydantic v2) | `schemas/canonical/`, validators | Every transform | EXISTS |
| INT-005 | PI1.2 | Schema reconciliation testing | Vendor-to-canonical accuracy tests | `tests/schema-reconciliation/` | Every PR | EXISTS |
| INT-006 | PI1.3 | Processing timeliness | Health checks, circuit breakers, timeouts | Health configs, M6 circuit breaker | Continuous | EXISTS |
| INT-007 | PI1.4 | SHA-256 audit integrity hash | Hash over canonical audit payload | M10 hash computation | Every write | EXISTS |
| INT-008 | PI1.4 | Provenance chain | Per-stage SHA-256 hash chain (Gap 2) | M6/M10 provenance recorder | Every request | EXISTS |
| INT-009 | PI1.5 | HITL gates | Mandatory human approval for orders, research, Reg BI | Execution state machine, HITL tokens | Every gated action | EXISTS |
| INT-010 | PI1.5 | Tamper-proof approval tokens | SHA-256(gate_id + approver_id + timestamp) | HITL token generation, WORM | Every approval | EXISTS |
| INT-011 | PI1.2 | Cost basis preservation | cost_basis_method never null | M7 translators, schema validation | Every transform | EXISTS |

---

## 4. CONFIDENTIALITY CONTROLS (C)

| Control ID | TSC | Control Description | Implementation | Evidence Source | Frequency | Status |
|------------|-----|---------------------|----------------|----------------|-----------|--------|
| CNF-001 | C1.1 | MNPI classification | M4 OPA/Rego classifies fields by sensitivity | `opa-bundles/mnpi/` | Every access | EXISTS |
| CNF-002 | C1.1 | MNPI filter log | Filter log for every data access | M10 MNPI filter log entries | Every access | EXISTS |
| CNF-003 | C1.3 | MNPI filtering before LLM | M4 strips MNPI before any LLM prompt | M4 rules, M6 enforcement | Every LLM call | EXISTS |
| CNF-004 | C1.3 | Encryption at rest | Per-tenant KMS key | KMS config, S3 encryption | Continuous | EXISTS |
| CNF-005 | C1.3 | Encryption in transit | mTLS (24hr cert rotation) | cert-manager, Helm tls | Continuous | EXISTS |
| CNF-006 | C1.2 | WORM retention (SEC 17a-4) | S3 Object Lock Compliance mode, 6-year minimum | S3 Object Lock config | Continuous | EXISTS |
| CNF-007 | C1.3 | Zero credentials in code | Secrets via Vault or AWS Secrets Manager | Code scanning, CI/CD | Every PR | EXISTS |
| CNF-008 | C1.1 | Chinese wall enforcement | OPA rules for information barriers | `opa-bundles/authority/` | Every cross-unit access | EXISTS |
| CNF-009 | C1.2 | Data retention schedule | Formal schedule for all data tiers | Schedule doc (Gap G12) | Annual review | PARTIAL |

---

## 5. PRIVACY CONTROLS (P)

| Control ID | TSC | Control Description | Implementation | Evidence Source | Frequency | Status |
|------------|-----|---------------------|----------------|----------------|-----------|--------|
| PRV-001 | P1.1 | Privacy policy | Platform privacy policy | Policy doc (Gap G4) | Annual review | GAP |
| PRV-002 | P2.1 | Consent via HITL | Human approval for recommendations and orders | HITL gates, approval tokens | Every gated action | EXISTS |
| PRV-003 | P3.1 | PII minimization | M4 strips PII (SSN, DOB) before LLM | M4 MNPI Rego rules | Every LLM call | EXISTS |
| PRV-004 | P4.1 | Purpose limitation | AID authority_scope restricts data use | M1 AID claims, M2 rules | Every request | EXISTS |
| PRV-005 | P6.1 | Data accuracy | M3 canonical schema validation | `schemas/canonical/`, Pydantic v2 | Every transform | EXISTS |
| PRV-006 | P7.1 | Privacy monitoring | MNPI filter log + 3-tier audit trail | M10 entries, MNPI logs | Continuous | EXISTS |

---

## 6. REGULATORY OVERLAY CONTROLS (FSI-Specific)

| Control ID | Regulation | Control Description | Implementation | Evidence Source | Status |
|------------|-----------|---------------------|----------------|----------------|--------|
| REG-001 | SEC 17a-4 | WORM storage for records | S3 Object Lock Compliance mode, 6-year | S3 config, M10 WORM tier | EXISTS |
| REG-002 | FINRA 3110 | WSP-to-YAML mapping | OPA rules with wsp_section annotations (Gap 3) | `opa-bundles/` annotations | EXISTS |
| REG-003 | Reg BI | Best interest documentation | Reg BI Document Generator (Gap 1) | Gap 1 implementation | EXISTS |
| REG-004 | FINRA 2210 | Principal review for BD comms | OPA retail vs institutional classification | M2 principal review rules | EXISTS |
| REG-005 | BSA/AML | Transaction monitoring | CTR, SAR, sanctions screening (Gap 4) | `opa-bundles/bsa-aml/` | EXISTS |
| REG-006 | ERISA | Account-type awareness | 16 account types with per-type rules (Gap 5) | `opa-bundles/account-type/` | EXISTS |
| REG-007 | Cross-border | Jurisdictional compliance | US/EU/UK/SG/HK overlays (Gap 7) | `opa-bundles/jurisdiction/` | EXISTS |

---

## 7. CONTROL TESTING SCHEDULE

| Category | Method | Frequency | Automated |
|----------|--------|-----------|-----------|
| Logical access (SEC-010–015) | Token tests, access review | Continuous + Quarterly | Yes + No |
| Network security (SEC-020–023) | mTLS validation, NetworkPolicy | Continuous | Yes |
| Threat management (SEC-030–034) | Trivy, adversarial tests, pentest | Per build + Annual | Yes + No |
| Monitoring (SEC-040–045) | Trace verification, audit completeness | Continuous | Yes |
| Change management (SEC-050–054) | CI/CD execution, ArgoCD logs | Per change | Yes |
| Processing integrity (INT-001–011) | Unit, integration, reconciliation tests | Per PR | Yes |
| Confidentiality (CNF-001–009) | MNPI filter tests, encryption checks | Per PR + Continuous | Yes |
| Privacy (PRV-001–006) | HITL gate tests, PII filter tests | Per PR | Yes |

---

## 8. SUMMARY

| Category | Total | EXISTS | PARTIAL | GAP |
|----------|-------|--------|---------|-----|
| Security (CC) | 27 | 21 | 1 | 5 |
| Availability (A) | 7 | 5 | 0 | 2 |
| Processing Integrity (PI) | 11 | 11 | 0 | 0 |
| Confidentiality (C) | 9 | 8 | 1 | 0 |
| Privacy (P) | 6 | 5 | 0 | 1 |
| **Total** | **60** | **50** | **2** | **8** |

Processing Integrity has 100% coverage. Gaps are concentrated in formal documentation and periodic processes, not technical controls.

---

*SOC 2 Control Matrix — Project 007 FSI Interoperability Platform*
