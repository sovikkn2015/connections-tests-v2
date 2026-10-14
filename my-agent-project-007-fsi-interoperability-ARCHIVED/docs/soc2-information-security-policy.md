# Information Security Policy — Project 007 FSI Interoperability Platform

> Version: 1.0
> Date: July 2026
> SOC 2 Gap: G5 (CC1.1 — Information Security Policy)
> Classification: CONFIDENTIAL — Internal Use Only
> Owner: [CISO_NAME], Chief Information Security Officer
> Approved by: [CEO_NAME], Chief Executive Officer
> Review Cycle: Annual (next review: July 2027)

---

## 1. PURPOSE

This Information Security Policy establishes the security principles, standards, and responsibilities for the 007 FSI Interoperability Platform. The Platform processes regulated financial data — including client PII, portfolio holdings, trade data, and Material Non-Public Information (MNPI) — on behalf of broker-dealers, RIAs, asset managers, and hedge funds. Security is not optional; it is a regulatory requirement and a core architectural principle.

This policy applies to all [COMPANY_NAME] employees, contractors, and systems that interact with the 007 Platform.

---

## 2. ACCEPTABLE USE

### 2.1 Platform Access

| Requirement | Details |
|-------------|---------|
| Authentication | All platform access requires a valid Agent Identity Document (AID) issued by M1 via Keycloak. No anonymous access. |
| Authorization | Every action is evaluated by M2/M4 OPA/Rego policy before execution. Access is deny-by-default. |
| Scope limitation | Users and agents may only access data within their `authority_scope`. The `authority_excludes` claim explicitly prohibits specific actions. |
| Multi-tenant isolation | Each client firm operates in an isolated namespace with its own KMS key, OPA policy bundle, and NetworkPolicy. |
| Session management | Working memory (L1) expires after 8 hours. AID tokens have configurable expiry. Revoked tokens are rejected immediately. |

### 2.2 Prohibited Activities

The following are strictly prohibited:

- Accessing client data outside your authorized scope
- Sharing AID tokens, credentials, or access keys with unauthorized parties
- Attempting to bypass M6 gateway to access vendor APIs directly
- Modifying OPA/Rego policy bundles without PR review and approval
- Storing credentials, API keys, or secrets in source code, config files, or environment variable defaults
- Disabling or circumventing audit logging (M10)
- Accessing MNPI without a legitimate business need and proper authorization
- Attempting to extract data from WORM storage outside authorized retrieval procedures
- Using platform resources for personal or non-business purposes
- Installing unauthorized software on platform infrastructure

### 2.3 Enforcement

Violations of this policy may result in:
- Immediate AID token revocation
- Access suspension pending investigation
- Disciplinary action up to and including termination
- Regulatory reporting if required by SEC/FINRA rules
- Legal action if warranted

---

## 3. DATA CLASSIFICATION

### 3.1 Classification Levels

| Level | Definition | Examples | Handling Rules |
|-------|-----------|----------|---------------|
| MNPI | Material Non-Public Information — regulatory restrictions on access and disclosure | Pending trades, undisclosed holdings, insider information, merger details | M4 OPA/Rego filtering required; never sent to LLM unfiltered; Chinese wall enforcement; access logged to WORM; breach = P1 incident |
| Confidential | Sensitive personal or financial data requiring protection | Client PII (SSN, DOB, account numbers), financial plans, portfolio details, trade history | Encrypted at rest (per-tenant KMS) and in transit (mTLS); access restricted by AID authority_scope; PII stripped before LLM; access logged to WORM |
| Internal | Business information not intended for public disclosure | Architecture documents, OPA policy rules, enterprise configs, internal communications | Access restricted to authorized personnel; stored in private repositories; not shared externally without approval |
| Public | Information approved for public disclosure | Marketing materials, public API documentation, published privacy policy | No special handling required; review before publication |

### 3.2 Classification by Platform Data Type

| Data Type | Classification | Module(s) | Handling |
|-----------|---------------|-----------|----------|
| Agent Identity Documents (AIDs) | Confidential | M1 | JWT RS256 signed; verified on every request; revocable |
| OPA/Rego Policy Bundles | Internal | M2/M4 | Versioned in Git; hashes recorded in audit; PR review required |
| Canonical Schema Definitions | Internal | M3 | Versioned (semver); breaking changes detected in CI/CD |
| Enterprise Configs | Confidential | M5 | Per-firm; secrets referenced via Vault/Secrets Manager, never inline |
| Client Records | Confidential | Via M11/M7 | MNPI-filtered by M4 before LLM; access logged |
| MNPI Fields | MNPI | Via M4 | Stripped before LLM; Chinese wall enforced; pod isolation for HF |
| Audit Entries | Confidential | M10 | SHA-256 integrity hash; WORM storage; 6-year retention |
| LLM Prompts/Responses | Confidential | M8/M9 | MNPI-filtered input; Langfuse traces for observability |
| Vendor API Credentials | Confidential | Vault/SM | Zero credentials in code; rotated per vendor schedule |
| mTLS Certificates | Confidential | cert-manager | 24-hour rotation; never stored in Git |

### 3.3 Labeling and Handling

| Classification | Storage | Transit | Access | Disposal |
|---------------|---------|---------|--------|----------|
| MNPI | Encrypted (KMS), WORM for audit | mTLS + PrivateLink (no public internet) | M4 OPA/Rego filter + AID scope | WORM: after retention period; other: secure deletion |
| Confidential | Encrypted (KMS) | mTLS | AID authority_scope | Secure deletion with audit log |
| Internal | Standard encryption | mTLS (internal), TLS (external) | Role-based (Keycloak) | Standard deletion |
| Public | No special requirement | TLS | Unrestricted | No special requirement |

---

## 4. ACCESS CONTROL

### 4.1 Principles

| Principle | Implementation |
|-----------|---------------|
| Least privilege | AID `authority_scope` grants minimum necessary access; `authority_excludes` explicitly denies |
| Deny-by-default | M2 OPA/Rego denies all requests unless an explicit ALLOW rule matches |
| Fail-closed | OPA unreachable = DENY; audit failure = request failure; no degraded mode |
| Separation of duties | OPA policy changes require PR review by different person than author |
| Need-to-know | MNPI access restricted to users with legitimate business need per M4 rules |

### 4.2 Identity and Authentication

| Component | Implementation |
|-----------|---------------|
| Identity provider | Keycloak (self-hosted, Apache 2.0) |
| Token format | JWT RS256 with FSI-specific claims: LEI, CRD, archetype, role, authority_scope, authority_excludes |
| Token lifecycle | Issue (M1 `/issue`), Verify (M1 `/verify`), Revoke (M1 `/revoke`) |
| Key management | RS256 signing keys in AWS KMS (cloud) or HashiCorp Vault (hybrid/on-prem) |
| Multi-factor | Keycloak MFA configuration per firm policy |

### 4.3 Authorization

| Component | Implementation |
|-----------|---------------|
| Policy engine | OPA/Rego (CNCF-graduated, deterministic evaluation) |
| Rule corpus | 2,100+ Rego rules across 5 archetypes, 7 compliance regimes, 5 jurisdictions |
| Policy bundles | `authority/` (M2 — action authorization) and `mnpi/` (M4 — field-level filtering) |
| Decision model | (identity, action, target, context) evaluates to ALLOW / DENY / ESCALATE |
| Traceability | Every OPA rule includes `wsp_section` annotation mapping to Written Supervisory Procedures |

### 4.4 Quarterly Access Reviews

| Review Scope | What Is Reviewed | Reviewer | Frequency |
|-------------|-----------------|----------|-----------|
| Keycloak roles | User-to-role assignments, inactive accounts, privilege levels | [SECURITY_LEAD_NAME] | Quarterly |
| ArgoCD RBAC | Who can deploy, sync, and modify platform infrastructure | [PLATFORM_LEAD_NAME] | Quarterly |
| AWS IAM | IAM roles, policies, cross-account access, service accounts | [CLOUD_ENGINEER_NAME] | Quarterly |
| OPA policy bundles | Rule accuracy, stale rules, overly permissive rules | [COMPLIANCE_SME_NAME] | Quarterly |
| Vendor API credentials | Active credentials, rotation status, unused credentials | [SECURITY_LEAD_NAME] | Quarterly |

Access review results are documented and retained for 3 years (SOC 2 evidence).

---

## 5. CREDENTIAL MANAGEMENT

### 5.1 Zero Credentials in Code

This is a non-negotiable rule. No API keys, tokens, passwords, connection strings, or secrets may appear in:
- Source code (any file in the Git repository)
- Configuration files (enterprise-config YAML, Helm values)
- Environment variable defaults (Dockerfiles, docker-compose)
- CI/CD pipeline definitions
- Documentation or comments

### 5.2 Secrets Storage

| Secret Type | Storage | Rotation | Access |
|-------------|---------|----------|--------|
| Vendor API keys | HashiCorp Vault or AWS Secrets Manager | Per vendor schedule (minimum quarterly) | ExternalSecret CRD in Kubernetes |
| Database passwords | HashiCorp Vault or AWS Secrets Manager | Quarterly | ExternalSecret CRD |
| JWT signing keys (RS256) | AWS KMS or HashiCorp Vault | Annual (or on compromise) | M1 via KMS API |
| mTLS certificates | cert-manager (auto-generated) | 24-hour rotation (automated) | Kubernetes Secret (auto-mounted) |
| OPA bundle signing keys | HashiCorp Vault | Annual | OPA bundle build pipeline |
| Terraform state encryption | AWS KMS | Annual | Terraform backend config |

### 5.3 Credential Leak Response

If a credential is found in source code, logs, or any unauthorized location:
1. Immediately rotate the affected credential
2. Revoke any tokens or sessions using the compromised credential
3. Classify as P2 incident (minimum) per Incident Response Plan
4. Audit access logs for unauthorized use during exposure window
5. Update CI/CD scanning rules to prevent recurrence

---

## 6. CHANGE MANAGEMENT

### 6.1 GitOps Workflow

All changes to the 007 Platform follow the GitOps model:

| Stage | Requirement | Enforcement |
|-------|-------------|-------------|
| Code change | Developer creates branch and implements change | Git branching model |
| PR submission | Pull request with description, linked issue, and test results | GitHub PR template |
| Automated checks | CI/CD pipeline runs: lint (Ruff), unit tests, integration tests, security scan (Trivy), schema change detection, adversarial tests | GitHub Actions (11-job pipeline) |
| Code review | Minimum 1 approval from a different team member | GitHub branch protection rules |
| OPA policy changes | Minimum 2 approvals (including compliance SME) | GitHub CODEOWNERS for `opa-bundles/` |
| Merge | Squash merge to main branch | GitHub branch protection |
| Deployment | ArgoCD detects change, syncs to cluster | ArgoCD auto-sync with self-heal |
| Verification | ArgoCD health checks, smoke tests | ArgoCD sync status, health probes |

### 6.2 Emergency Changes

For P1/P2 incidents requiring immediate code changes:
1. Emergency PR created with `[EMERGENCY]` prefix
2. Single reviewer approval (IC or Technical Lead)
3. CI/CD pipeline still runs (no bypass)
4. Post-emergency: full review within 24 hours
5. Documented in post-incident review

### 6.3 Rollback

| Method | When | How |
|--------|------|-----|
| ArgoCD rollback | Deployment causes issues | `argocd app rollback 007-platform` — reverts to previous sync |
| Git revert | Code change causes issues | Revert commit, PR, merge — ArgoCD syncs automatically |
| OPA bundle rollback | Policy change causes incorrect decisions | Revert bundle in Git, rebuild, push to OPA |
| Helm values rollback | Configuration change causes issues | Revert values file in Git, ArgoCD syncs |

---

## 7. NETWORK SECURITY

### 7.1 Architecture Principles

| Principle | Implementation |
|-----------|---------------|
| No public internet for data plane | Only ALB is public-facing; all modules in private subnets |
| mTLS everywhere | cert-manager issues and rotates certificates every 24 hours between all modules |
| PrivateLink for LLM | Bedrock accessed via PrivateLink — MNPI in prompts never hits public internet |
| Module isolation | NetworkPolicy per module mirrors dependency matrix; only authorized module-to-module traffic |
| Namespace isolation | Per-tenant namespace with dedicated NetworkPolicy, KMS key, and OPA bundle |
| Controlled egress | Vendor API calls via NAT Gateway with security group allowlists |

### 7.2 Network Segmentation

| Zone | Contents | Access |
|------|----------|--------|
| Public subnet | ALB (load balancer) only | Internet-facing; routes to private subnet |
| Private subnet (trust) | M1, M2/M4, M6, M10 | Internal only; mTLS required |
| Private subnet (compute) | M8, M9, M12 | Internal only; mTLS required |
| Private subnet (data) | M11 adapters, M13 FIX Bridge | Internal only; mTLS required; vendor egress via NAT |
| Data stores | RDS, ElastiCache, DynamoDB, S3 | Private subnet only; VPC endpoints where available |

---

## 8. VULNERABILITY MANAGEMENT

### 8.1 Continuous Scanning

| Scan Type | Tool | Frequency | Threshold | Action |
|-----------|------|-----------|-----------|--------|
| Container image CVE | Trivy | Every build (CI/CD `security-scan` job) | CRITICAL or HIGH = build failure | Fix before merge |
| Dependency audit | Ruff + pip-audit | Every PR (CI/CD `lint` job) | Known vulnerabilities = warning | Fix within 5 business days |
| Code quality | Ruff linter | Every PR | Lint errors = build failure | Fix before merge |
| Adversarial testing | Custom test suite | Every PR | Policy bypass, MNPI leakage, privilege escalation | Fix before merge |
| Penetration testing | Third-party vendor | Annual | Per pentest report | Remediate per severity |

### 8.2 Patch Management

| Severity | Patch Timeline | Process |
|----------|---------------|---------|
| Critical CVE (actively exploited) | 24 hours | Emergency change process |
| High CVE | 7 days | Standard change process, prioritized |
| Medium CVE | 30 days | Standard change process |
| Low CVE | 90 days | Next scheduled maintenance |

---

## 9. PHYSICAL SECURITY

### 9.1 Cloud Deployments (Tier 3/4)

Physical security is managed by AWS per their SOC 2 Type II report. [COMPANY_NAME] relies on AWS's physical security controls for data center access, environmental protections, and media disposal.

### 9.2 Hybrid Deployments (Tier 2/5)

Physical security for on-premise components is the responsibility of the client firm. [COMPANY_NAME] provides guidance on:
- Server room access controls
- Environmental monitoring (temperature, humidity, fire suppression)
- Media disposal procedures for decommissioned hardware
- Visitor access logging

---

## 10. SECURITY AWARENESS

### 10.1 Training Requirements

| Audience | Training | Frequency | Tracking |
|----------|---------|-----------|----------|
| All employees | Security awareness fundamentals (phishing, social engineering, data handling) | Annual + onboarding | LMS completion records |
| Engineering team | Secure coding practices, OWASP Top 10, FSI-specific threats (MNPI leakage, compliance bypass) | Annual | LMS completion records |
| Platform operators | Incident response procedures, DR runbook, containment actions | Annual + post-drill | Drill participation records |
| Compliance team | Regulatory updates (SEC, FINRA, GDPR), OPA policy review procedures | Semi-annual | Training records |

### 10.2 Security Awareness Topics

- Recognizing phishing and social engineering attacks
- Proper handling of Confidential and MNPI data
- Credential management (zero credentials in code)
- Incident reporting procedures
- Acceptable use of platform resources
- Regulatory obligations (SEC 17a-4, FINRA 3110, privacy laws)

---

## 11. INCIDENT RESPONSE

Security incidents are handled per the Incident Response Plan (soc2-incident-response-plan.md). Key points:

- P1–P4 severity classification with FSI-specific examples
- 15-minute acknowledge SLA for P1 (Critical)
- Containment actions: AID revocation, adapter disable, emergency OPA policy push
- Fail-closed architecture provides automatic containment for many scenarios
- Post-incident review mandatory for P1/P2
- Quarterly drills
- Regulatory notification procedures for SEC, FINRA, and state regulators

---

## 12. POLICY EXCEPTIONS

### 12.1 Exception Process

No exceptions to this policy are granted without:
1. Written request describing the exception, business justification, and risk assessment
2. Compensating controls proposed
3. Approval by [CISO_NAME]
4. Time-limited scope (maximum 90 days, renewable)
5. Documented in exception register
6. Reviewed quarterly

### 12.2 Non-Negotiable Controls (No Exceptions)

The following controls cannot be excepted under any circumstances:
- Fail-closed on trust decisions (OPA unreachable = DENY)
- SHA-256 integrity hash on every audit write
- WORM storage for regulatory records (SEC 17a-4)
- MNPI filtering before LLM (M4 OPA/Rego)
- Zero credentials in code
- 3-tier audit write requirement (all 3 tiers must succeed)

---

## 13. POLICY REVIEW

| Activity | Frequency | Owner |
|----------|-----------|-------|
| Full policy review and update | Annual | [CISO_NAME] |
| Regulatory requirement review | Semi-annual | [CCO_NAME] |
| Access review procedures | Quarterly | [SECURITY_LEAD_NAME] |
| Training completion audit | Annual | [HR_LEAD_NAME] |
| Exception register review | Quarterly | [CISO_NAME] |

---

## 14. DOCUMENT CONTROL

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | July 2026 | [CISO_NAME] | Initial version — SOC 2 Gap G5 remediation |

---

*Information Security Policy — Project 007 FSI Interoperability Platform*
*SOC 2 CC1.1 — Gap G5 Remediation*
