# Privacy Policy — Project 007 FSI Interoperability Platform

> Version: 1.0
> Date: July 2026
> SOC 2 Gap: G4 (P1.1 — Privacy Notice)
> Classification: PUBLIC (client-facing document)
> Owner: [DPO_NAME], Data Protection Officer
> Approved by: [GENERAL_COUNSEL_NAME], General Counsel
> Review Cycle: Annual (next review: July 2027)

---

## 1. INTRODUCTION

[COMPANY_NAME] ("we," "us," "our") operates the 007 FSI Interoperability Platform ("Platform"), a financial services interoperability system that connects wealth management firms with their technology vendors through a trust-aware gateway. This Privacy Policy describes how we collect, use, store, share, and protect personal data processed through the Platform.

This policy applies to all data processed by the Platform on behalf of our clients (broker-dealers, registered investment advisors, asset managers, and hedge funds) and their end users (financial advisors, compliance officers, and operations staff).

[COMPANY_NAME] acts as a data processor on behalf of our clients (data controllers) under applicable privacy regulations.

---

## 2. DATA WE PROCESS

### 2.1 Categories of Personal Data

| Category | Examples | Source | Purpose |
|----------|---------|--------|---------|
| Client PII | Name, address, phone, email, date of birth, Social Security Number | CRM systems (Salesforce FSC, Wealthbox, Redtail) via M11 adapters | Client identification, meeting preparation, account servicing |
| Financial Holdings | Portfolio positions, account balances, cost basis, asset allocation | Portfolio systems (Orion, Schwab, Fidelity, Pershing) via M11 adapters | Portfolio review, research, rebalancing recommendations |
| Trade Data | Order history, execution details, settlement status | Custodians and OMS (Schwab, Fidelity, SS&C Eze) via M11/M13 | Order execution, trade lifecycle management |
| Financial Plans | Goals, projections, risk tolerance, income, net worth | Planning systems (eMoney) via M11 adapters | Financial planning, suitability assessment |
| Advisor Interactions | Conversation history, meeting notes, recommendations made | Platform channels (Slack, Teams, Web) via M12 | Continuity of service, compliance documentation |
| Material Non-Public Information (MNPI) | Pending trades, undisclosed holdings, insider information | Multiple vendor systems | Regulatory compliance — filtered and restricted per regulations |
| Authentication Data | User identity, role, firm affiliation, access scope | Keycloak (M1) | Access control, audit trail |

### 2.2 Data We Do NOT Collect

- We do not collect data for marketing or advertising purposes
- We do not build consumer profiles for sale to third parties
- We do not process data beyond what is necessary for the services contracted by our clients
- We do not retain raw vendor API responses beyond the processing window

---

## 3. HOW DATA FLOWS THROUGH THE PLATFORM

### 3.1 Standard Data Flow

Every data access follows this trust pipeline:

```
User Request (via M12 channel gateway)
    |
    v
M1: Identity Verification
    Agent Identity Document (AID) verified — JWT RS256 with FSI claims
    WHO is making this request?
    |
    v
M9: Intent Classification
    What does the user want? (structured FSI intent)
    |
    v
M2: Authority Check (OPA/Rego — deterministic, not LLM)
    Is this user ALLOWED to perform this action on this data?
    Decision: ALLOW / DENY / ESCALATE
    |
    v
M6: Trust-Aware Gateway
    Routes request to appropriate vendor adapter
    |
    v
M11: Vendor Adapter
    Retrieves data from vendor system (Salesforce, Orion, Schwab, etc.)
    |
    v
M7: Schema Translation
    Converts vendor-specific format to canonical type
    |
    v
M4: MNPI Filter (OPA/Rego — deterministic, not LLM)
    Strips sensitive fields based on user archetype, role, and jurisdiction
    PII (SSN, DOB) stripped before any LLM processing
    |
    v
M10: Audit Logger
    Logs access to all 3 tiers: Langfuse + S3 WORM + CRM
    SHA-256 integrity hash on every entry
    |
    v
Response delivered to user (filtered, audited, compliant)
```

### 3.2 MNPI Filtering at Every Stage

Material Non-Public Information is filtered by M4 (OPA/Rego policy) at multiple points:

| Stage | What Is Filtered | Why |
|-------|-----------------|-----|
| Before LLM processing | PII fields (SSN, DOB, account numbers), MNPI fields per archetype rules | LLM providers must never receive unfiltered PII or MNPI |
| Before agent memory storage | Sensitive fields stripped before writing to any memory tier | Memory tiers have different retention and access controls |
| Before cross-firm data access | Chinese wall enforcement, pod isolation (hedge funds) | Regulatory information barriers |
| Before response delivery | Final MNPI scan — 3-layer guardrail (regex + NER + classifier) | Defense-in-depth against MNPI leakage |

### 3.3 Data Minimization

| Principle | Implementation |
|-----------|---------------|
| Purpose limitation | AID `authority_scope` restricts what data each agent/user can access |
| Field-level filtering | M4 OPA/Rego strips fields not needed for the specific operation |
| PII stripping before LLM | SSN, DOB, and other PII removed before any LLM prompt |
| Canonical types only | Business logic operates on M3 canonical types — vendor-specific fields not propagated |
| No raw data retention | Raw vendor API responses are not stored; only canonical representations |

---

## 4. DATA RETENTION

### 4.1 Retention Schedule by Tier

| Memory/Storage Tier | Retention Period | Data Types | Deletion Method |
|--------------------|-----------------|------------|-----------------|
| L1: Working Memory (Redis) | 8 hours TTL | Current conversation context | Automatic TTL expiry |
| L2: Short-Term Memory (DynamoDB) | 7 days | Recent interaction summaries | Automatic TTL expiry |
| L3: Episodic Memory (DynamoDB + vector) | 2 years | Past interactions and outcomes | Scheduled deletion job |
| L4: Semantic Memory (pgvector/Pinecone) | Permanent (until deletion request) | Learned facts about clients | Manual deletion on request |
| L5: Procedural Memory (S3) | Permanent (until deletion request) | Advisor workflow preferences | Manual deletion on request |
| L6: Compliance Memory / WORM (S3 Object Lock) | 6+ years minimum | Immutable audit trail, regulatory records | Cannot be deleted during retention period (SEC 17a-4) |

### 4.2 Regulatory Retention Requirements

| Regulation | Requirement | Platform Implementation |
|-----------|-------------|------------------------|
| SEC Rule 17a-4 | Books and records: 6 years (first 2 years immediately accessible) | S3 Object Lock Compliance mode, 6-year retention |
| SEC Rule 17a-3 | Order tickets: 3 years | S3 Object Lock, 3-year minimum |
| FINRA Rule 3110 | Supervisory records: 3 years | S3 Object Lock, 3-year minimum |
| FINRA Rule 4511 | General books and records: 6 years | S3 Object Lock, 6-year retention |
| State regulations | Varies (up to 7 years in some states) | Configurable per jurisdiction in M5 enterprise config |

### 4.3 Post-Retention Disposal

After the retention period expires:
1. WORM records: S3 lifecycle policy deletes objects after retention period
2. Non-WORM data: Scheduled deletion jobs with verification
3. All deletions are logged in the audit trail
4. Deletion confirmation provided to data controller (client firm) on request

---

## 5. DATA SUBJECT RIGHTS

### 5.1 Rights and Platform Response

| Right | Description | Platform Capability | WORM Exception |
|-------|-------------|--------------------|--------------------|
| Right of Access | Data subjects may request a copy of their personal data | Export from CRM (M10 Tier 3) + memory tiers (L2–L5) | WORM records accessible but cannot be modified |
| Right of Correction | Data subjects may request correction of inaccurate data | Correction applied in CRM and memory tiers; new audit entry created | WORM records are immutable — correction recorded as new entry with reference to original |
| Right of Deletion | Data subjects may request deletion of their personal data | Deletion from L1–L5 memory tiers and CRM | WORM records CANNOT be deleted during regulatory retention period — this is a legal requirement (SEC 17a-4) |
| Right to Restrict Processing | Data subjects may request restriction of processing | M2 OPA policy updated to restrict access to subject's data | Existing WORM records unaffected |
| Right to Data Portability | Data subjects may request data in machine-readable format | Export in JSON (canonical schema format) | Available for all tiers including WORM (read-only) |

### 5.2 WORM Exception for Regulatory Records

Certain data subject rights (particularly deletion) conflict with regulatory record retention requirements:

- SEC Rule 17a-4 requires immutable retention of books and records for 6 years
- S3 Object Lock in Compliance mode makes records physically undeletable during the retention period
- This is not a platform limitation — it is a legal requirement
- Data subjects are informed of this exception at the time of any deletion request
- After the regulatory retention period expires, deletion proceeds normally

### 5.3 Request Processing

| Step | Action | Timeline |
|------|--------|----------|
| 1 | Request received from data controller (client firm) | — |
| 2 | Identity verification of requesting party | 1 business day |
| 3 | Scope assessment (which data, which tiers) | 2 business days |
| 4 | Execution (access/correction/deletion/restriction) | 5 business days |
| 5 | Confirmation to data controller | Within 30 days total |
| 6 | Audit entry created for the request itself | Immediate |

---

## 6. CROSS-BORDER DATA HANDLING

### 6.1 Jurisdiction Overlays

The Platform supports multiple regulatory jurisdictions via M2 OPA/Rego policy overlays (ARCH-06 Gap 7):

| Jurisdiction | Regulation | Key Privacy Requirements | Platform Implementation |
|-------------|-----------|------------------------|------------------------|
| United States | SEC/FINRA, state laws, CCPA | Regulation S-P (safeguards), state breach notification | Default jurisdiction; M4 MNPI filtering per archetype |
| European Union | GDPR | Lawful basis, data minimization, 72-hour breach notification, DPO requirement | GDPR overlay in M2; enhanced data minimization; EU data residency option |
| United Kingdom | UK GDPR | Similar to EU GDPR with UK-specific DPA 2018 provisions | UK overlay in M2; UK data residency option |
| Singapore | PDPA, MAS Guidelines | Consent, purpose limitation, data protection officer | SG overlay in M2; SG data residency |
| Hong Kong | PDPO, SFC Guidelines | Data protection principles, cross-border transfer restrictions | HK overlay in M2; HK data residency |

### 6.2 Data Residency

| Topology | Data Location | Cross-Border Transfers |
|----------|--------------|----------------------|
| Cloud (Tier 3/4) | AWS region selected per client jurisdiction | No cross-border transfer of PII/MNPI without explicit configuration |
| Hybrid (Tier 2/5) | Trust layer and data adapters on-premise in client's jurisdiction | Only filtered, non-PII data crosses to cloud compute layer |
| On-premise (Tier 1) | All data remains in client's data center | No cross-border transfer |

### 6.3 Cross-Border Transfer Safeguards

When data must cross jurisdictional boundaries:
1. M4 MNPI filter applies jurisdiction-specific rules before transfer
2. Standard Contractual Clauses (SCCs) or equivalent mechanism in place
3. Transfer impact assessment documented
4. Encryption in transit (mTLS) and at rest (per-tenant KMS key)
5. Audit entry records the cross-border transfer with jurisdiction metadata

---

## 7. THIRD-PARTY DATA SHARING

### 7.1 How Data Is Shared

| Recipient | Purpose | Mechanism | Data Shared |
|-----------|---------|-----------|-------------|
| Vendor APIs (Salesforce, Orion, Schwab, etc.) | Data retrieval and action execution on behalf of client | M6 gateway to M11 adapters; vendor's own API | Only data necessary for the specific API call; credentials via Vault |
| LLM Provider (AWS Bedrock) | AI-powered analysis and response generation | M6 gateway via PrivateLink (no public internet) | MNPI-filtered data only — PII stripped by M4 before LLM |
| Langfuse | LLM observability and debugging | M10 Tier 1 write | Trace data, prompt/response metadata — NOT the regulatory record |
| CRM (Salesforce) | Business audit trail for advisors and compliance | M10 Tier 3 write | Audit entries linked to client and advisor records |

### 7.2 What We Do NOT Do

- We do NOT sell personal data to any third party
- We do NOT share data for marketing or advertising purposes
- We do NOT provide data to data brokers
- We do NOT use client data to train LLM models
- We do NOT share data with any party not explicitly authorized by the client firm's enterprise configuration

### 7.3 Vendor Security Requirements

All vendor integrations are subject to:
- M6 gateway enforcement (no direct vendor API calls)
- Per-vendor circuit breakers and rate limiting
- Per-adapter container isolation (each M11 adapter runs in its own container)
- Vendor risk assessment (SOC 2 Gap G3 — Vendor Risk Register)
- Credential management via HashiCorp Vault or AWS Secrets Manager (zero credentials in code)

---

## 8. DATA SECURITY

### 8.1 Technical Safeguards

| Safeguard | Implementation |
|-----------|---------------|
| Encryption in transit | mTLS between all modules (cert-manager, 24-hour certificate rotation) |
| Encryption at rest | Per-tenant KMS key for all data stores |
| Access control | M1 Agent Identity Document (JWT RS256) with FSI-specific claims |
| Authorization | M2/M4 OPA/Rego deterministic policy evaluation (2,100+ rules) |
| Network isolation | Private subnets only for data plane; PrivateLink for Bedrock; NetworkPolicy per module |
| Audit trail | M10 3-tier audit: Langfuse + S3 Object Lock WORM + CRM |
| Integrity verification | SHA-256 hash on every audit entry; provenance chain per request |
| Vulnerability management | Trivy CVE scanning on every container build; CRITICAL/HIGH = build failure |
| Secrets management | HashiCorp Vault / AWS Secrets Manager; zero credentials in code |

### 8.2 Organizational Safeguards

| Safeguard | Implementation |
|-----------|---------------|
| Least privilege | AID `authority_scope` and `authority_excludes` enforce minimum necessary access |
| Fail-closed | OPA unreachable = DENY; audit failure = request failure; no degraded mode |
| Change management | GitOps via ArgoCD; PR review required; CI/CD gates enforced |
| Incident response | Formal IRP with P1–P4 severity levels (see soc2-incident-response-plan.md) |
| Personnel security | Keycloak role assignment; background checks per firm policy |

---

## 9. BREACH NOTIFICATION

In the event of a personal data breach:

1. Detection via M10 audit alerts, MNPI leakage scan, or other detection sources
2. Classification per Incident Response Plan severity levels (P1–P4)
3. Containment actions executed per IRP (AID revocation, adapter disable, emergency OPA policy)
4. Notification to affected client firms (data controllers) within 24 hours of confirmation
5. Client firms responsible for notifying their data subjects per applicable law
6. Regulatory notifications per jurisdiction requirements:
   - SEC/FINRA: prompt notification
   - GDPR/UK GDPR: 72 hours to supervisory authority
   - State laws: per state-specific timelines
   - Singapore PDPA: 3 calendar days
7. Full details in the Incident Response Plan (soc2-incident-response-plan.md)

---

## 10. POLICY UPDATES

This Privacy Policy is reviewed annually and updated when:
- New data categories are processed
- New vendor integrations are added
- Regulatory requirements change
- New jurisdictions are supported
- Material changes to data processing practices occur

Updates are communicated to all client firms with 30 days notice before taking effect.

---

## 11. CONTACT

For privacy inquiries, data subject requests, or complaints:

- Data Protection Officer: [DPO_NAME]
- Email: privacy@[COMPANY_DOMAIN]
- Address: [COMPANY_ADDRESS]

For security incidents: security@[COMPANY_DOMAIN] (see Incident Response Plan)

---

## 12. DOCUMENT CONTROL

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | July 2026 | [DPO_NAME] | Initial version — SOC 2 Gap G4 remediation |

---

*Privacy Policy — Project 007 FSI Interoperability Platform*
*SOC 2 P1.1 — Gap G4 Remediation*
