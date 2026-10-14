# Incident Response Plan — Project 007 FSI Interoperability Platform

> Version: 1.0
> Date: July 2026
> SOC 2 Gap: G1 (CC7.4 — Incident Response)
> Classification: CONFIDENTIAL — Internal Use Only
> Owner: [CISO_NAME], Chief Information Security Officer
> Approved by: [CEO_NAME], Chief Executive Officer
> Review Cycle: Annual (next review: July 2027)

---

## 1. PURPOSE AND SCOPE

This Incident Response Plan (IRP) establishes formal procedures for detecting, responding to, containing, eradicating, and recovering from security incidents affecting the 007 FSI Interoperability Platform. The platform processes regulated financial data including client PII, portfolio holdings, trade data, and Material Non-Public Information (MNPI) across 13 modules serving broker-dealers, RIAs, asset managers, and hedge funds.

This plan covers all 007 platform components, infrastructure, and data — including all deployment topologies (cloud, hybrid, on-premise).

---

## 2. INCIDENT CLASSIFICATION

### 2.1 Severity Levels

| Severity | Name | Definition | FSI Examples | Response SLA |
|----------|------|------------|--------------|--------------|
| P1 | Critical | Active data breach, MNPI exposure, or complete platform outage affecting regulated operations | MNPI leaked to unauthorized party or LLM prompt; unauthorized access to client holdings across firm boundaries; compliance rule bypass allowing prohibited trade execution | 15 min acknowledge, 1 hr containment |
| P2 | High | Partial system compromise, single-module failure affecting trust layer, or potential regulatory violation | M1 identity service degraded (AID verification failing); OPA policy engine unreachable (all requests denied per fail-closed); single audit tier write failure (M10 degraded); unauthorized access attempt detected but blocked | 30 min acknowledge, 4 hr containment |
| P3 | Medium | Non-critical module degradation, policy misconfiguration detected, or vulnerability requiring patching | Trivy CVE alert (CRITICAL/HIGH) on container image; OPA rule misconfiguration detected in testing; single M11 adapter failure (vendor API unavailable); elevated OPA DENY rate indicating possible misconfiguration | 4 hr acknowledge, 24 hr remediation |
| P4 | Low | Minor operational issue, informational security event, or process deviation | Failed login attempts below threshold; non-critical dependency update available; documentation gap identified; performance degradation within SLA | 24 hr acknowledge, 5 business days remediation |

### 2.2 Incident Categories

| Category | Description | Typical Severity |
|----------|-------------|------------------|
| MNPI Exposure | Material Non-Public Information leaked outside authorized boundary | P1 |
| Unauthorized Access | Access to client data, systems, or functions beyond authorized scope | P1–P2 |
| Compliance Bypass | OPA policy circumvented or compliance check skipped | P1 |
| Data Integrity | Audit records tampered, provenance chain broken, or SHA-256 mismatch | P1–P2 |
| System Outage | Platform or critical module unavailable | P1–P2 |
| Credential Exposure | API key, token, certificate, or password exposed | P1–P2 |
| Vulnerability | CVE or security weakness identified in platform components | P2–P3 |
| Vendor Compromise | Third-party vendor system or API compromised | P2–P3 |
| Policy Misconfiguration | OPA/Rego rule error causing incorrect ALLOW/DENY decisions | P2–P3 |
| Operational Anomaly | Unusual patterns in access, volume, or behavior | P3–P4 |

---

## 3. INCIDENT RESPONSE TEAM

### 3.1 Core Team

| Role | Primary | Backup | Contact Method |
|------|---------|--------|----------------|
| Incident Commander (IC) | [CISO_NAME] | [SECURITY_LEAD_NAME] | PagerDuty, phone |
| Technical Lead | [PLATFORM_LEAD_NAME] | [SENIOR_ENGINEER_NAME] | PagerDuty, phone |
| Compliance Officer | [CCO_NAME] | [COMPLIANCE_ANALYST_NAME] | PagerDuty, phone |
| Communications Lead | [COMMS_LEAD_NAME] | [CEO_NAME] | Phone, email |
| Legal Counsel | [GENERAL_COUNSEL_NAME] | [OUTSIDE_COUNSEL_FIRM] | Phone |

### 3.2 Extended Team (Engaged as Needed)

| Role | When Engaged | Contact |
|------|-------------|---------|
| Database Administrator | Database failure, data integrity incident | PagerDuty |
| OPA Policy SME | Policy misconfiguration, compliance bypass | PagerDuty |
| Vendor Relations | Vendor compromise, adapter failure | Email, phone |
| External Forensics | P1 incidents requiring independent investigation | Retainer contract |
| Regulatory Affairs | Incidents requiring regulator notification | Phone |

---

## 4. DETECTION SOURCES

### 4.1 Automated Detection

| Source | Module | What It Detects | Alert Channel |
|--------|--------|-----------------|---------------|
| M10 Audit Alerts | M10 | SHA-256 integrity mismatch, WORM write failure, 3-tier write failure, audit volume anomaly | PagerDuty (P1/P2), Slack #security-alerts (P3/P4) |
| MNPI Leakage Scan | M6 (Gap 6) | MNPI data in LLM output — 3-layer guardrail: regex, NER, Haiku classifier | PagerDuty (P1), immediate request block |
| OPA Decision Logs | M2/M4 | DENY spike (>2x baseline in 5 min), ESCALATE volume anomaly, policy evaluation errors | PagerDuty (P2), Grafana dashboard |
| Health Check Failures | All modules | `/health` endpoint failure on any module, pod restart loops, readiness probe failure | PagerDuty (P2), ArgoCD notification |
| Trivy CVE Alerts | CI/CD | CRITICAL or HIGH CVE in container image, dependency vulnerability | GitHub Actions notification, Slack #security-alerts |
| Keycloak Auth Logs | M1 | Failed authentication spike, token revocation anomaly, suspicious AID issuance pattern | PagerDuty (P2/P3) |
| Circuit Breaker Trips | M6 | M6 circuit breaker open for any MCP server, sustained vendor API failures | Grafana alert, Slack #ops-alerts |
| Certificate Expiry | cert-manager | mTLS certificate approaching expiry (24hr rotation failure) | PagerDuty (P2) |
| ArgoCD Sync Failures | Infrastructure | GitOps sync failure, self-heal failure, drift detection | ArgoCD notification, Slack #ops-alerts |

### 4.2 Manual Detection

| Source | Description | Reporting Channel |
|--------|-------------|-------------------|
| Employee Report | Staff identifies suspicious activity or policy violation | security@[COMPANY_DOMAIN] or Slack #security-incidents |
| Client Report | Client or advisor reports unauthorized activity | Support channel, escalation to IC |
| Vendor Notification | Vendor reports breach or compromise of their systems | Vendor relations, escalation to IC |
| Regulatory Inquiry | Regulator identifies concern during examination | Legal counsel, escalation to IC |
| Penetration Test | Annual pentest identifies exploitable vulnerability | Pentest report, escalation to IC |

---

## 5. RESPONSE PROCEDURES

### 5.1 P1 — Critical Incident Response

**Timeline: 15 min acknowledge, 1 hr containment, 24 hr eradication**

#### Phase 1: Detection and Triage (0–15 minutes)
1. On-call engineer receives PagerDuty alert
2. Acknowledge alert within 15 minutes
3. Perform initial triage:
   - Confirm incident is real (not false positive)
   - Classify severity and category
   - Identify affected modules, tenants, and data
4. Page Incident Commander and Technical Lead
5. Open incident channel: Slack #incident-[YYYY-MM-DD]-[ID]

#### Phase 2: Containment (15 min – 1 hour)
1. IC assumes command, assigns roles
2. Execute immediate containment actions (see Section 6)
3. For MNPI exposure: immediately revoke affected AID tokens via M1
4. For unauthorized access: disable affected adapter via M6 circuit breaker
5. For compliance bypass: push emergency OPA policy (deny-all for affected scope)
6. Preserve evidence:
   - Export M10 audit logs for affected time window
   - Capture WORM records (immutable — already preserved)
   - Snapshot affected pod logs and state
   - Record all containment actions with timestamps

#### Phase 3: Eradication (1–24 hours)
1. Identify root cause
2. Develop and test fix
3. Deploy fix via standard GitOps pipeline (emergency PR with expedited review)
4. Verify fix resolves the issue without introducing new problems
5. Run adversarial tests against the fix

#### Phase 4: Recovery (24–72 hours)
1. Restore normal operations incrementally
2. Re-enable contained components one at a time
3. Monitor closely for recurrence (enhanced alerting for 72 hours)
4. Verify all 3 audit tiers are writing correctly
5. Confirm provenance chain integrity

#### Phase 5: Post-Incident (within 5 business days)
1. Conduct post-incident review (see Section 8)
2. File regulatory notifications if required (see Section 9)
3. Update IRP if gaps identified
4. Communicate lessons learned to team

#### Escalation Timeline — P1

| Time | Action | Who |
|------|--------|-----|
| T+0 | Alert fires | Automated |
| T+15m | Acknowledge, initial triage | On-call engineer |
| T+15m | Page IC, Technical Lead, Compliance Officer | On-call engineer |
| T+30m | IC assumes command, containment begins | IC |
| T+1h | Containment complete, status update to leadership | IC |
| T+2h | First external communication (if required) | Communications Lead |
| T+4h | Root cause identified (target) | Technical Lead |
| T+24h | Eradication complete, recovery begins | Technical Lead |
| T+72h | Recovery complete, enhanced monitoring active | Technical Lead |
| T+5d | Post-incident review complete | IC |

### 5.2 P2 — High Severity Response

**Timeline: 30 min acknowledge, 4 hr containment, 48 hr eradication**

1. On-call engineer acknowledges within 30 minutes
2. Page IC if trust layer (M1/M2/M4/M6/M10) is affected
3. Execute containment within 4 hours
4. Note: fail-closed architecture means OPA unreachable = all requests denied automatically — containment may already be in effect
5. Root cause and fix within 48 hours
6. Post-incident review within 10 business days

### 5.3 P3 — Medium Severity Response

**Timeline: 4 hr acknowledge, 24 hr remediation plan, 5 business days fix**

1. On-call engineer acknowledges within 4 hours
2. Create JIRA ticket with severity and category
3. Develop remediation plan within 24 hours
4. Implement fix within 5 business days
5. For Trivy CVE: rebuild affected container images with patched dependencies
6. Brief summary in weekly security review

### 5.4 P4 — Low Severity Response

**Timeline: 24 hr acknowledge, 5 business days remediation**

1. Acknowledge within 24 hours
2. Create JIRA ticket, prioritize in next sprint
3. Remediate within 5 business days
4. Track in monthly security metrics

---

## 6. CONTAINMENT ACTIONS

### 6.1 Immediate Containment Toolkit

| Action | How | When to Use | Impact |
|--------|-----|-------------|--------|
| Revoke AID Tokens | M1 `/revoke` endpoint — invalidates specific agent or user tokens | Unauthorized access, credential compromise, MNPI exposure | Affected agents/users cannot authenticate until re-issued |
| Disable Adapter | M6 circuit breaker force-open for specific M11 adapter | Vendor compromise, adapter vulnerability, data integrity issue | Affected vendor integration unavailable; other vendors unaffected |
| Emergency OPA Policy Push | Push deny-all policy bundle for affected scope via OPA bundle API | Compliance bypass, policy misconfiguration, rule error | All requests in affected scope denied until corrected policy deployed |
| Namespace Isolation | Apply restrictive NetworkPolicy to affected tenant namespace | Tenant-specific breach, cross-tenant access attempt | Affected tenant isolated; other tenants unaffected |
| Certificate Revocation | Revoke mTLS certificate for affected module via cert-manager | Module compromise, certificate exposure | Affected module cannot communicate until new cert issued |
| Kill Pod | `kubectl delete pod` for compromised pod (ArgoCD recreates) | Pod compromise, malicious process detected | Brief service interruption; ArgoCD self-heals |
| Disable Channel | Remove channel from OpenClaw (M12) configuration | Channel-specific attack vector | Users on affected channel cannot access platform |

### 6.2 Containment Decision Matrix

| Incident Type | Primary Action | Secondary Action |
|---------------|---------------|------------------|
| MNPI Leak | Revoke AID tokens for affected scope | Emergency OPA policy (deny data access for affected client/security) |
| Unauthorized Access | Revoke AID tokens | Namespace isolation if cross-tenant |
| Compliance Bypass | Emergency OPA policy push | Disable affected adapter if vendor-related |
| Audit Integrity | Halt affected operations (fail-closed already in effect) | Preserve WORM records, investigate discrepancy |
| Credential Exposure | Rotate affected credentials via Vault/Secrets Manager | Revoke associated AID tokens |
| Vendor Compromise | Disable adapter via M6 circuit breaker | Revoke vendor API credentials |

---

## 7. COMMUNICATION TEMPLATES

### 7.1 Internal Notification — P1/P2

```
SUBJECT: [P1/P2] Security Incident — [CATEGORY] — [DATE]

INCIDENT ID: INC-[YYYY]-[NNN]
SEVERITY: [P1/P2]
STATUS: [DETECTED / CONTAINED / ERADICATED / RECOVERED]
INCIDENT COMMANDER: [NAME]

SUMMARY:
[Brief description of what happened]

AFFECTED SYSTEMS:
[Modules, tenants, data types affected]

CURRENT ACTIONS:
[What is being done right now]

NEXT UPDATE: [TIME]

This information is CONFIDENTIAL. Do not share outside the incident
response team without IC approval.
```

### 7.2 Client Notification (if required)

```
SUBJECT: Security Notice — [COMPANY_NAME] Platform

Dear [CLIENT_NAME],

We are writing to inform you of a security event that may have affected
your data on the [COMPANY_NAME] platform.

WHAT HAPPENED:
[Clear, non-technical description]

WHAT DATA WAS INVOLVED:
[Specific data types — be precise]

WHAT WE ARE DOING:
[Actions taken and planned]

WHAT YOU CAN DO:
[Recommended actions for the client]

For questions, contact [SECURITY_EMAIL] or call [SECURITY_PHONE].

[CISO_NAME]
Chief Information Security Officer
[COMPANY_NAME]
```

### 7.3 Regulatory Notification

```
SUBJECT: Security Incident Notification — [COMPANY_NAME] / CRD# [NUMBER]

[REGULATORY_BODY]:

Pursuant to [APPLICABLE_RULE], [COMPANY_NAME] is providing notification
of a security incident affecting [DESCRIPTION].

Date of Discovery: [DATE]
Nature of Incident: [CATEGORY]
Data Affected: [TYPES]
Number of Affected Individuals: [COUNT]
Containment Status: [STATUS]
Remediation Actions: [SUMMARY]

Contact: [GENERAL_COUNSEL_NAME], [PHONE], [EMAIL]

[Signature block]
```

---

## 8. POST-INCIDENT REVIEW

### 8.1 Review Requirements

| Severity | Review Required | Timeline | Participants |
|----------|----------------|----------|-------------|
| P1 | Mandatory | Within 5 business days | Full IRT + leadership |
| P2 | Mandatory | Within 10 business days | IC + Technical Lead + Compliance |
| P3 | Recommended | Within 15 business days | Technical Lead + relevant engineers |
| P4 | Optional | Next sprint retrospective | Relevant team |

### 8.2 Post-Incident Review Template

```
POST-INCIDENT REVIEW
====================

Incident ID:        INC-[YYYY]-[NNN]
Date of Incident:   [DATE]
Date of Review:     [DATE]
Severity:           [P1/P2/P3/P4]
Category:           [CATEGORY]
Incident Commander: [NAME]
Review Facilitator: [NAME]

1. TIMELINE
-----------
[Chronological sequence of events with timestamps]
- T+0:     [Detection event]
- T+Xm:    [Acknowledgment]
- T+Xm:    [Triage complete]
- T+Xh:    [Containment achieved]
- T+Xh:    [Root cause identified]
- T+Xh:    [Eradication complete]
- T+Xh:    [Recovery complete]

2. ROOT CAUSE ANALYSIS
----------------------
[What was the underlying cause?]
[Technical failure, process failure, human error, or external attack?]
[What conditions allowed this to happen?]

3. IMPACT ASSESSMENT
--------------------
Affected Modules:    [List]
Affected Tenants:    [Count and names]
Data Exposed:        [Types and volume — or "None"]
Regulatory Impact:   [Notification required? Filed?]
Financial Impact:    [Estimated cost]
Reputation Impact:   [Assessment]
Duration:            [Time from detection to recovery]

4. WHAT WENT WELL
------------------
[Actions that worked as designed]
[Effective detection, containment, or communication]

5. WHAT NEEDS IMPROVEMENT
--------------------------
[Gaps in detection, response, or recovery]
[Process failures or delays]
[Missing runbooks or documentation]

6. REMEDIATION ACTIONS
-----------------------
| Action | Owner | Deadline | Status |
|--------|-------|----------|--------|
| [Action 1] | [Name] | [Date] | [Open/Complete] |
| [Action 2] | [Name] | [Date] | [Open/Complete] |

7. LESSONS LEARNED
-------------------
[Key takeaways for the team]
[Changes to IRP, monitoring, or architecture]

8. AUDIT TRAIL VERIFICATION
-----------------------------
WORM Records Intact:      [Yes/No]
SHA-256 Hashes Verified:   [Yes/No]
Provenance Chain Complete: [Yes/No]
Langfuse Traces Available: [Yes/No]
CRM Records Consistent:   [Yes/No]

Reviewed by: [IC_NAME], [DATE]
Approved by: [CISO_NAME], [DATE]
```

---

## 9. REGULATORY NOTIFICATION REQUIREMENTS

### 9.1 SEC Notification

| Trigger | Rule | Timeline | Method |
|---------|------|----------|--------|
| Unauthorized access to customer records | Regulation S-P (Rule 30) | As soon as reasonably practicable | Written notice to affected individuals; SEC notification via EDGAR if material |
| Material cybersecurity incident | Form 8-K Item 1.05 | 4 business days of materiality determination | SEC EDGAR filing (client responsibility; platform provides incident data) |
| Books and records integrity compromise | SEC 17a-4 | Immediate notification to designated examining authority | Written notification to SEC/FINRA |

### 9.2 FINRA Notification

| Trigger | Rule | Timeline | Method |
|---------|------|----------|--------|
| Cybersecurity incident affecting BD operations | FINRA Rule 4370 (BCP) | Prompt notification | FINRA Contact System, written follow-up |
| Customer data breach | FINRA Regulatory Notice 19-18 | Prompt notification | FINRA Contact System |
| Supervisory system failure | FINRA Rule 3110 | Prompt notification | Written notification to FINRA district office |

### 9.3 State Regulators

| Trigger | Timeline | Notes |
|---------|----------|-------|
| PII breach affecting state residents | Varies by state (30–90 days typical) | Must comply with each affected state's breach notification law |
| California (CCPA) | 72 hours for >500 residents | Attorney General notification required |
| New York (23 NYCRR 500) | 72 hours | NY DFS notification required for financial services |

### 9.4 Cross-Border (if applicable)

| Jurisdiction | Trigger | Timeline | Authority |
|-------------|---------|----------|-----------|
| EU (GDPR) | Personal data breach | 72 hours to supervisory authority | Lead DPA |
| UK (UK GDPR) | Personal data breach | 72 hours | ICO |
| Singapore (PDPA) | Significant data breach | 3 calendar days | PDPC |
| Hong Kong (PDPO) | Data breach (voluntary) | As soon as practicable | PCPD |

### 9.5 Notification Decision Tree

```
Incident Detected
       |
       v
  Is customer data affected?
       |
  YES -+---> Is it MNPI?
       |         |
       |    YES -+---> SEC + FINRA notification (immediate)
       |         |     + State AG if PII involved
       |         |     + Cross-border DPA if non-US residents
       |         |
       |    NO --+---> Is PII involved?
       |              |
       |         YES -+---> State breach notification laws apply
       |              |     FINRA notification if BD
       |              |     Cross-border DPA if non-US residents
       |              |
       |         NO --+---> Internal tracking only
       |
  NO --+---> Is platform integrity compromised?
       |         |
       |    YES -+---> SEC 17a-4 notification (books/records)
       |         |     FINRA Rule 3110 (supervisory systems)
       |         |
       |    NO --+---> Internal tracking only
```

---

## 10. ANNUAL DRILL SCHEDULE

### 10.1 Drill Calendar

| Quarter | Drill Type | Scenario | Participants | Success Criteria |
|---------|-----------|----------|-------------|-----------------|
| Q1 | Tabletop Exercise | MNPI leakage via LLM output bypass — M6 Gap 6 guardrail failure | Full IRT | IC assigned in <15m, containment plan in <1h, regulatory notification decision made |
| Q2 | Technical Simulation | M1 identity service compromise — unauthorized AID issuance | Engineering + IC | Detect within 5m (automated), contain within 30m, all affected tokens revoked |
| Q3 | Tabletop Exercise | Vendor compromise (M11 adapter exfiltrating data) | Full IRT + Legal | Adapter disabled in <30m, vendor notified, forensic evidence preserved |
| Q4 | Full Simulation | Multi-module failure: OPA unreachable + audit tier failure | Full IRT + Engineering | Fail-closed verified, DLQ operational, recovery within RTO |

### 10.2 Drill Evaluation Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to acknowledge | Per severity SLA | Timestamp from alert to acknowledgment |
| Time to contain | Per severity SLA | Timestamp from acknowledgment to containment |
| Communication accuracy | No misinformation in updates | Review of all communications sent |
| Evidence preservation | All WORM records intact, logs captured | Post-drill audit verification |
| Regulatory notification decision | Correct determination within 2 hours | Legal review of decision |
| Post-drill review | Completed within 10 business days | Review document filed |

### 10.3 Drill Records

All drill records are retained for 3 years and available for auditor review. Records include scenario description, participant list, timeline of actions taken, evaluation against success criteria, improvement actions identified, and sign-off by IC and [CISO_NAME].

---

## 11. PLAN MAINTENANCE

| Activity | Frequency | Owner |
|----------|-----------|-------|
| Full IRP review and update | Annual | [CISO_NAME] |
| Contact list verification | Quarterly | [SECURITY_LEAD_NAME] |
| Drill execution | Quarterly (see Section 10) | [CISO_NAME] |
| Post-incident IRP updates | After every P1/P2 incident | IC |
| Regulatory requirement review | Semi-annual | [CCO_NAME] |
| New module onboarding | Per new module deployment | [PLATFORM_LEAD_NAME] |

---

## 12. DOCUMENT CONTROL

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | July 2026 | [CISO_NAME] | Initial version — SOC 2 Gap G1 remediation |

---

*Incident Response Plan — Project 007 FSI Interoperability Platform*
*SOC 2 CC7.4 — Gap G1 Remediation*
