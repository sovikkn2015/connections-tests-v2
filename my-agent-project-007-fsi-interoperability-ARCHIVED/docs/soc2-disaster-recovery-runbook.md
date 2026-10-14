# Disaster Recovery Runbook — Project 007 FSI Interoperability Platform

> Version: 1.0
> Date: July 2026
> SOC 2 Gap: G2 (A1.2/A1.3 — Recovery Procedures)
> Classification: CONFIDENTIAL — Internal Use Only
> Owner: [PLATFORM_LEAD_NAME], Platform Engineering Lead
> Approved by: [CTO_NAME], Chief Technology Officer
> Review Cycle: Annual (next review: July 2027)

---

## 1. PURPOSE AND SCOPE

This Disaster Recovery Runbook defines recovery procedures for the 007 FSI Interoperability Platform across all failure modes — from single-module failures to full cloud region outages. The platform processes regulated financial data subject to SEC 17a-4, FINRA 3110, and state regulatory requirements. Continuity of audit writes (WORM) and fail-closed trust enforcement are non-negotiable during any recovery scenario.

This runbook covers all 13 modules across cloud (Tier 3/4) and hybrid (Tier 2/5) deployment topologies.

---

## 2. RTO/RPO TARGETS

### 2.1 By Deployment Topology

| Topology | Tiers Served | RTO | RPO | Justification |
|----------|-------------|-----|-----|---------------|
| Cloud (AWS EKS) | Tier 3 BD, Tier 4 RIA | 4 hours | 1 hour | SaaS deployment with AWS managed services; automated recovery via ArgoCD |
| Hybrid | Tier 2 AM, Tier 5 HF | 8 hours | 4 hours | Trust layer on-prem adds recovery complexity; requires coordination with firm infrastructure |

### 2.2 By Module Criticality

| Tier | Modules | RTO | RPO | Rationale |
|------|---------|-----|-----|-----------|
| Critical | M1 (Identity), M2/M4 (Policy), M6 (Gateway), M10 (Audit) | 1 hour | 15 min | Trust layer — platform is fail-closed without these; all requests denied |
| High | M9 (Intent Router), M8 (Pipeline), M12 (Runtime) | 2 hours | 1 hour | Intelligence layer — platform non-functional for users without these |
| Standard | M11 (Adapters), M7 (Translators), M3 (Schema), M5 (Config) | 4 hours | 1 hour | Data layer — individual adapter failures degrade but do not halt platform |
| Specialized | M13 (FIX Bridge) | 8 hours | 4 hours | Stateful TCP sessions require sequence number recovery; specialist knowledge |

---

## 3. BACKUP STRATEGY

### 3.1 Data Store Backup Matrix

| Data Store | Module(s) | Backup Method | Frequency | Retention | Recovery Location |
|-----------|-----------|---------------|-----------|-----------|-------------------|
| PostgreSQL (RDS) | M1 (Keycloak/AID), M3 (Schema) | Automated RDS snapshots + cross-region replication | Continuous (5-min point-in-time) | 35 days snapshots, 7 days PITR | Same region (primary), cross-region (DR) |
| Redis (ElastiCache) | M6 (rate limits, circuit breaker state) | AOF persistence + Redis replication | Continuous (AOF fsync every second) | Ephemeral — rebuilt on recovery | Same AZ (replica), rebuilt from scratch if lost |
| S3 Object Lock (WORM) | M10 (regulatory audit) | Cross-region replication (CRR) | Continuous (async, typically <15 min) | 6+ years (SEC 17a-4, immutable) | DR region (CRR target bucket) |
| S3 (OPA bundles) | M2/M4 | Git is source of truth; S3 is delivery mechanism | On every bundle publish | Git history (permanent) | Rebuilt from Git on recovery |
| DynamoDB | M8 (pipeline checkpoints) | Point-in-time recovery (PITR) + on-demand backups | Continuous PITR | 35 days PITR | Same region, cross-region via global tables |
| Langfuse (PostgreSQL) | M10 (observability) | RDS snapshots (Langfuse backing store) | Daily automated snapshot | 35 days | Same region; operational data — not regulatory record |
| CRM (Salesforce) | M10 (business audit) | Salesforce native backup + weekly export | Daily (Salesforce), weekly export | Per Salesforce retention | Salesforce DR (managed by Salesforce) |

### 3.2 Configuration and Code Backup

| Asset | Backup Method | Recovery |
|-------|---------------|----------|
| Application code | Git (GitHub) | Clone and redeploy via ArgoCD |
| OPA/Rego policy bundles | Git (`opa-bundles/`) | Rebuild bundles from Git, push to OPA |
| Helm charts and values | Git (`infra/helm/`) | ArgoCD sync from Git |
| Enterprise configs | Git (`config/`) | M5 loads from Git/ConfigMap |
| Canonical schemas | Git (`schemas/`) | M3 serves from Git |
| CI/CD pipelines | Git (`.github/workflows/`) | GitHub Actions auto-recovers |
| ArgoCD application definitions | Git (`infra/argocd/`) | Bootstrap ArgoCD, sync from Git |
| Terraform state | S3 backend with DynamoDB locking | Restore from S3 versioned bucket |

### 3.3 Backup Verification

| Verification | Frequency | Method | Owner |
|-------------|-----------|--------|-------|
| RDS snapshot restore test | Monthly | Restore snapshot to test instance, verify data integrity | DBA |
| WORM cross-region verification | Weekly | Compare object counts and SHA-256 checksums between regions | Platform Engineering |
| OPA bundle rebuild from Git | Monthly | Delete S3 bundles, rebuild from Git, verify OPA loads correctly | Platform Engineering |
| Full DR failover test | Annual | Execute full DR drill (see Section 9) | [PLATFORM_LEAD_NAME] |

---

## 4. RECOVERY PROCEDURES

### 4.1 Failure Mode: Single Module Failure

**Scenario:** One module pod crashes or becomes unresponsive.

**First Line of Defense: ArgoCD Self-Heal**

ArgoCD self-heal is enabled for all modules. When a pod fails:
1. Kubernetes restarts the pod (restartPolicy: Always)
2. If pod fails readiness probe 3 times, Kubernetes replaces it
3. ArgoCD detects drift from desired state and reconciles
4. If replica count drops below minimum, ArgoCD scales back up

**Expected Recovery Time:** 30 seconds – 5 minutes (automated, no human intervention)

**If ArgoCD Cannot Self-Heal:**

| Step | Action | Command/Procedure |
|------|--------|-------------------|
| 1 | Check pod status and events | `kubectl describe pod <pod> -n 007` |
| 2 | Check pod logs for root cause | `kubectl logs <pod> -n 007 --previous` |
| 3 | Check node health | `kubectl get nodes` — verify node is Ready |
| 4 | Force delete stuck pod | `kubectl delete pod <pod> -n 007 --force --grace-period=0` |
| 5 | If image pull failure | Verify ECR access, check image tag in Helm values |
| 6 | If persistent volume issue | Check PV/PVC status: `kubectl get pv,pvc -n 007` |
| 7 | If config/secret missing | Verify Vault/Secrets Manager connectivity, check ExternalSecret |
| 8 | Redeploy module | `argocd app sync 007-platform --resource <module>` |

**Trust Layer Module Failure (M1/M2/M4/M6/M10):**
- Platform is fail-closed — all requests are automatically denied when trust layer modules are down
- No manual intervention needed to protect data; the architecture enforces safety
- Priority is restoring the module, not implementing workarounds
- There is NO degraded mode. Do not attempt to bypass the trust layer.

### 4.2 Failure Mode: Database Failure

#### PostgreSQL (RDS) Failure

| Step | Action | Details |
|------|--------|---------|
| 1 | Verify failure type | Check RDS console: instance status, Multi-AZ failover status |
| 2 | If Multi-AZ: automatic failover | RDS promotes standby (60–120 seconds). DNS endpoint unchanged. No action needed. |
| 3 | If single-AZ or failover fails | Restore from latest automated snapshot |
| 4 | Restore procedure | Create new RDS instance from snapshot; update Helm values with new endpoint; ArgoCD sync |
| 5 | Verify data integrity | Run schema validation queries; verify M1 AID registry, M3 schema versions |
| 6 | Verify Keycloak | Test AID issuance and verification via M1 `/health` and `/verify` |

**RPO Impact:** Up to 5 minutes of data loss (RDS PITR granularity). AID tokens in flight may need re-issuance.

#### Redis (ElastiCache) Failure

| Step | Action | Details |
|------|--------|---------|
| 1 | Verify failure type | Check ElastiCache console: node status, replication status |
| 2 | If replica available | Automatic failover to replica (typically <30 seconds) |
| 3 | If full cluster failure | Create new ElastiCache cluster from Helm values |
| 4 | Rebuild state | Rate limit counters reset (acceptable). Circuit breaker state resets to closed (acceptable — will re-trip if vendor still down). |

**RPO Impact:** Redis data is ephemeral. Loss is acceptable — M6 rebuilds state from live traffic.

#### DynamoDB Failure

| Step | Action | Details |
|------|--------|---------|
| 1 | Check DynamoDB service health | AWS Health Dashboard |
| 2 | If table-level issue | Restore from PITR to new table; update M8 config |
| 3 | If region-level issue | Failover to global table replica in DR region |

**RPO Impact:** DynamoDB PITR provides second-level granularity. Pipeline checkpoints may need replay from last checkpoint.

### 4.3 Failure Mode: Full Cluster Failure

**Scenario:** EKS cluster is unrecoverable (control plane failure, etcd corruption).

| Step | Action | Owner | Time Est. |
|------|--------|-------|-----------|
| 1 | Confirm cluster is unrecoverable | Platform Engineering | 15 min |
| 2 | Provision new EKS cluster via Terraform | Platform Engineering | 30–60 min |
| 3 | Bootstrap ArgoCD on new cluster | Platform Engineering | 15 min |
| 4 | ArgoCD syncs all applications from Git | Automated | 15–30 min |
| 5 | Verify ExternalSecrets connect to Vault/Secrets Manager | Platform Engineering | 10 min |
| 6 | Verify database connectivity (RDS, ElastiCache, DynamoDB) | DBA | 10 min |
| 7 | Verify OPA bundles loaded from S3 | Platform Engineering | 5 min |
| 8 | Verify M10 3-tier audit writes | Platform Engineering | 10 min |
| 9 | Run smoke tests (health checks, AID verify, OPA evaluate) | QA | 15 min |
| 10 | Flush DLQ audit entries accumulated during outage | Platform Engineering | 15 min |
| 11 | Restore traffic (update ALB target group or DNS) | Platform Engineering | 5 min |

**Total Estimated Recovery Time:** 2–3 hours

**Critical Verification Before Restoring Traffic:**
- M1 can issue and verify AIDs
- M2/M4 OPA evaluates correctly (run adversarial test subset)
- M10 writes to all 3 tiers (Langfuse + WORM + CRM)
- M6 gateway routes requests through full trust pipeline
- SHA-256 integrity hashes compute correctly

### 4.4 Failure Mode: Cloud Region Failure

**Scenario:** Primary AWS region (e.g., us-east-1) is unavailable.

| Step | Action | Owner | Time Est. |
|------|--------|-------|-----------|
| 1 | Confirm region-level outage (not just AZ) | Platform Engineering | 15 min |
| 2 | Activate DR region infrastructure via Terraform | Platform Engineering | 45–60 min |
| 3 | Bootstrap EKS + ArgoCD in DR region | Platform Engineering | 30 min |
| 4 | Verify RDS cross-region read replica; promote to primary | DBA | 15 min |
| 5 | Verify S3 WORM cross-region replication is current | Platform Engineering | 10 min |
| 6 | Verify DynamoDB global table replica | Platform Engineering | 10 min |
| 7 | Deploy all applications via ArgoCD | Automated | 15–30 min |
| 8 | Update DNS (Route 53 failover record) | Platform Engineering | 5 min |
| 9 | Verify full trust pipeline operational | QA | 20 min |
| 10 | Flush DLQ entries from outage period | Platform Engineering | 15 min |
| 11 | Notify clients of region failover | Communications | — |

**Total Estimated Recovery Time:** 3–4 hours (within cloud RTO target)

**Post-Failover:**
- Monitor DR region closely for 72 hours
- Plan failback to primary region when available
- Verify WORM record continuity — no gaps in audit trail

---

## 5. WORM AUDIT CONTINUITY

### 5.1 Audit Write Behavior During Outage

The 007 platform is fail-closed: if M10 cannot write to all 3 audit tiers, the originating request fails. During an outage, this means:

| Scenario | Behavior |
|----------|----------|
| Langfuse unavailable | Audit write fails; request fails; entry goes to DLQ |
| S3 WORM unavailable | Audit write fails; request fails; entry goes to DLQ |
| CRM unavailable | Audit write fails; request fails; entry goes to DLQ |
| M10 pod down | All audit writes fail; all requests fail; ArgoCD self-heals M10 |

### 5.2 Dead Letter Queue (DLQ) Behavior

Failed audit writes are queued in the DLQ (SQS in cloud, RabbitMQ on-prem):

1. The originating request still fails immediately (fail-closed — the DLQ does not bypass the audit requirement)
2. DLQ entries contain the complete audit payload including SHA-256 hash
3. DLQ retention: 14 days (sufficient for any reasonable outage)
4. DLQ entries are encrypted at rest (KMS)

### 5.3 DLQ Flush on Recovery

| Step | Action | Details |
|------|--------|---------|
| 1 | Verify all 3 audit tiers are operational | M10 health check returns healthy for all tiers |
| 2 | Begin DLQ drain | M10 DLQ consumer processes entries in chronological order |
| 3 | For each entry: write to all 3 tiers | Same 3-tier write logic as normal operation |
| 4 | Verify SHA-256 integrity | Hash in DLQ entry must match recomputed hash |
| 5 | If any DLQ entry fails to write | Re-queue for retry; alert on-call engineer |
| 6 | Verify no gaps in WORM timeline | Query S3 WORM for time range; confirm continuous coverage |

### 5.4 WORM Continuity Verification

After any outage affecting M10:

```
WORM CONTINUITY CHECK:
1. Query S3 WORM for entries in outage time window
2. Compare against DLQ entries processed
3. Verify: (DLQ entries flushed) + (entries written during outage) = expected total
4. Verify SHA-256 integrity on all recovered entries
5. Document any gaps with explanation (outage duration, DLQ flush status)
6. File WORM continuity report for compliance records
```

---

## 6. FIX BRIDGE RECOVERY (M13)

### 6.1 M13 Architecture Considerations

M13 FIX Bridge is fundamentally different from other modules:
- Stateful TCP sessions (not stateless HTTP)
- Sequence number tracking (FIX protocol requirement)
- StatefulSet deployment (not Deployment)
- PersistentVolume for session state and message store

### 6.2 Recovery Procedure

| Step | Action | Details |
|------|--------|---------|
| 1 | Verify M13 pod status | `kubectl get statefulset m13-fix-bridge -n 007` |
| 2 | Check PersistentVolume | `kubectl get pv,pvc -n 007 -l app=m13-fix-bridge` — PV must be intact |
| 3 | If pod restarted (PV intact) | QuickFIX reads last sequence number from persistent store; sends ResendRequest to counterparty for gap-fill |
| 4 | If PV lost | Restore from latest DynamoDB checkpoint (cloud) or PostgreSQL backup (hybrid) |
| 5 | Sequence number recovery | Read last confirmed sequence from persistent store; counterparty gap-fill handles missing messages |
| 6 | Session re-establishment | QuickFIX sends Logon (A) message; counterparty responds; heartbeat resumes |
| 7 | Verify message integrity | Compare message store against counterparty confirms; reconcile any discrepancies |
| 8 | Resume order flow | Only after sequence numbers are reconciled and session is stable |

### 6.3 FIX Session Recovery Timeline

| Phase | Duration | What Happens |
|-------|----------|-------------|
| Pod restart | 30–60 seconds | StatefulSet recreates pod, mounts PV |
| Sequence recovery | 1–5 minutes | Read last sequence from store |
| Logon + gap-fill | 1–10 minutes | Depends on counterparty response time and gap size |
| Reconciliation | 5–30 minutes | Verify all messages accounted for |
| Resume trading | After reconciliation | Manual approval required before resuming order flow |

**Total M13 Recovery:** 10–45 minutes (pod restart with PV) to 2–8 hours (PV loss requiring backup restore)

---

## 7. HYBRID TOPOLOGY RECOVERY

### 7.1 Hybrid Architecture Reminder

In hybrid deployments (Tier 2/5):
- Trust layer (M1, M2/M4, M6, M10) runs on-premise in the firm's network
- Compute layer (M8, M9, M12) runs in cloud
- Data adapters (M11) run where the data lives (on-prem)
- mTLS encrypted tunnel connects on-prem to cloud

### 7.2 On-Premise Component Failure

| Component | Recovery | Notes |
|-----------|----------|-------|
| On-prem K8s node failure | ArgoCD self-heal on remaining nodes | Requires minimum 3 nodes for HA |
| On-prem trust layer failure | Restore from local backups; cloud compute is non-functional until trust layer recovers | Fail-closed: cloud cannot bypass on-prem trust |
| On-prem PostgreSQL failure | Restore from local backup or replica | Keycloak and AID registry must be recovered first |
| On-prem WORM storage failure | NetApp SnapLock/Dell EMC Centera recovery per vendor procedures | Regulatory records — highest priority |
| mTLS tunnel failure | Re-establish WireGuard/PrivateLink/ExpressRoute | Cloud compute isolated until tunnel restored |

### 7.3 Cloud Component Failure (Hybrid)

| Component | Recovery | Notes |
|-----------|----------|-------|
| Cloud EKS failure | Standard cloud recovery (Section 4.3) | On-prem trust layer continues to deny requests (fail-closed) |
| Cloud LLM (Bedrock) failure | Switch to alternative provider via M5 config | LLM provider is abstracted; config toggle |
| Cloud Langfuse failure | On-prem audit continues to WORM + CRM; Langfuse tier degraded | DLQ for Langfuse entries; flush on recovery |

---

## 8. RECOVERY VALIDATION CHECKLIST

Before declaring recovery complete, verify all items:

```
RECOVERY VALIDATION CHECKLIST
==============================

TRUST LAYER
[ ] M1: AID issuance returns valid JWT with FSI claims
[ ] M1: AID verification succeeds for known-good token
[ ] M1: AID revocation works (revoked token is rejected)
[ ] M2: OPA authority policy evaluates correctly (test ALLOW and DENY)
[ ] M4: OPA MNPI policy filters fields correctly per archetype
[ ] M6: Gateway routes request through full trust pipeline
[ ] M6: Circuit breakers in correct state (closed for healthy vendors)

AUDIT LAYER
[ ] M10: Langfuse trace created successfully
[ ] M10: S3 WORM write succeeds with Object Lock
[ ] M10: CRM record created successfully
[ ] M10: SHA-256 integrity hash computed and stored
[ ] M10: Provenance chain records all stages
[ ] M10: DLQ drained — no pending entries

DATA LAYER
[ ] PostgreSQL: All tables accessible, data integrity verified
[ ] Redis: Operational (state rebuilt from traffic)
[ ] DynamoDB: Tables accessible, PITR enabled
[ ] S3 WORM: Cross-region replication current, no gaps

INFRASTRUCTURE
[ ] ArgoCD: All applications synced and healthy
[ ] cert-manager: mTLS certificates valid and rotating
[ ] ExternalSecrets: All secrets resolved from Vault/Secrets Manager
[ ] NetworkPolicy: Per-module isolation enforced
[ ] Health checks: All module /health endpoints returning 200

SMOKE TESTS
[ ] End-to-end request: user query through full pipeline
[ ] Adversarial test subset: policy bypass attempts denied
[ ] MNPI filter test: sensitive fields stripped correctly
[ ] Audit completeness: all 3 tiers written for smoke test

Verified by: [NAME], [DATE], [TIME]
```

---

## 9. ANNUAL DR DRILL SCHEDULE

### 9.1 Drill Calendar

| Quarter | Drill Type | Scope | Participants |
|---------|-----------|-------|-------------|
| Q1 | Single Module Recovery | Kill critical module pod (M6 or M10), verify ArgoCD self-heal and fail-closed behavior | Platform Engineering |
| Q2 | Database Failover | Trigger RDS Multi-AZ failover, verify application reconnection and data integrity | Platform Engineering + DBA |
| Q3 | DLQ Flush Exercise | Simulate M10 tier failure, accumulate DLQ entries, recover and flush, verify WORM continuity | Platform Engineering |
| Q4 | Full DR Simulation | Simulate region failure, execute full recovery in DR region, verify all validation checklist items | Full team |

### 9.2 Success Criteria

| Metric | Cloud Target | Hybrid Target |
|--------|-------------|---------------|
| Recovery Time (full DR) | < 4 hours | < 8 hours |
| Data Loss (RPO verification) | < 1 hour | < 4 hours |
| WORM Continuity | Zero gaps in audit trail | Zero gaps in audit trail |
| Trust Layer Recovery | < 1 hour | < 2 hours |
| All validation checklist items | 100% pass | 100% pass |
| DLQ entries flushed | 100% processed | 100% processed |

### 9.3 Drill Documentation

Each drill produces a report containing: drill scenario and objectives, actual recovery timeline vs. targets, issues encountered and resolution, validation checklist results, improvement actions with owners and deadlines, and sign-off by [PLATFORM_LEAD_NAME] and [CTO_NAME].

Drill reports are retained for 3 years and available for auditor review.

---

## 10. DOCUMENT CONTROL

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | July 2026 | [PLATFORM_LEAD_NAME] | Initial version — SOC 2 Gap G2 remediation |

---

*Disaster Recovery Runbook — Project 007 FSI Interoperability Platform*
*SOC 2 A1.2/A1.3 — Gap G2 Remediation*
