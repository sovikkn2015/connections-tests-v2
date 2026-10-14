# ARCH-08: Packaging, Networking, and AWS Well-Architected Alignment

> Date: April 14, 2026
> Category: ARCHITECTURE (product design)
> Predecessor: REV-05 (Critical Assessment), ARCH-07 (Definitive Tech Stack)
> Addresses: REV-05 scores — Ease of Deploy 5/10, Reproducibility 6/10
> Purpose: Close the gap between "product designed" and "platform designed"

---

## WHY THIS DOCUMENT EXISTS

REV-05 scored operational architecture 6.6/10. The three weakest areas:

1. No packaging strategy (20 services, no single deploy command)
2. No network architecture (private vs public not designed)
3. No AWS Well-Architected alignment (FSI Lens not applied)

This document fixes all three. After this, the platform is designed — not just the product.

---

## PART 1: AWS WELL-ARCHITECTED — FSI LENS ALIGNMENT

AWS Well-Architected has 6 pillars. The FSI Lens adds financial-services-specific controls. Here is how 007's 12 modules map to each pillar.

```
┌─────────────────────────────────────────────────────────────────────┐
│              AWS WELL-ARCHITECTED — 6 PILLARS × 007                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 1. OPERATIONAL EXCELLENCE                                    │   │
│  │    IaC: Terraform + Helm (every module)                      │   │
│  │    Observability: OpenTelemetry + Prometheus + Grafana        │   │
│  │    LLM Observability: Langfuse (traces, costs, latency)      │   │
│  │    Runbooks: per-module, auto-generated from Helm values      │   │
│  │    Change management: GitOps (ArgoCD)                        │   │
│  │    FSI: Audit trail for ALL config changes (M10 WORM)        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 2. SECURITY                                                  │   │
│  │    Identity: Keycloak OIDC + AID tokens (M1)                 │   │
│  │    Authorization: OPA/Rego (M2/M4) — deterministic, not LLM  │   │
│  │    Encryption at rest: AES-256 (RDS, DynamoDB, S3, EBS)      │   │
│  │    Encryption in transit: mTLS between ALL modules            │   │
│  │    Secrets: HashiCorp Vault / AWS Secrets Manager             │   │
│  │    Network: Private subnets only. No public IPs on data plane │   │
│  │    WORM: S3 Object Lock Compliance mode (6-year, immutable)   │   │
│  │    FSI: Chinese wall enforcement (OPA), MNPI filtering (M4)   │   │
│  │    FSI: Per-tenant encryption keys (KMS CMK per tenant)       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 3. RELIABILITY                                               │   │
│  │    Multi-AZ: EKS across 3 AZs                                │   │
│  │    Circuit breakers: M6 gateway per-adapter                   │   │
│  │    Retry: exponential backoff on all MCP calls                │   │
│  │    Checkpointing: LangGraph pipeline survives pod restarts    │   │
│  │    Dead letter: failed audit writes → DLQ → alarm → retry     │   │
│  │    DR: RPO <1hr, RTO <4hr (cross-region S3 replication)       │   │
│  │    FSI: Fail-closed on ANY compliance check failure            │   │
│  │    FSI: HITL gate state survives restarts (DynamoDB)           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 4. PERFORMANCE EFFICIENCY                                    │   │
│  │    Supervisor routing: <500ms (Haiku)                         │   │
│  │    Client service: <3s end-to-end                             │   │
│  │    Research pipeline: <20min (23 stages, parallel map)        │   │
│  │    OPA policy eval: <10ms (sidecar, no network hop)           │   │
│  │    MNPI scan: 3-layer (<10ms regex, <100ms NER, <2s Haiku)    │   │
│  │    Redis L1 memory: <5ms read                                 │   │
│  │    Right-sizing: Karpenter autoscaler for EKS nodes            │   │
│  │    FSI: Token budgets per pipeline stage (no runaway costs)    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 5. COST OPTIMIZATION                                         │   │
│  │    LLM: Haiku for routing/conversation, Sonnet only research  │   │
│  │    Compute: Spot instances for non-critical (eval, batch)     │   │
│  │    Storage: S3 Intelligent-Tiering for WORM after 90 days     │   │
│  │    Right-sizing: HPA per module (CPU/memory targets)           │   │
│  │    Multi-tenant: shared control plane, isolated data plane     │   │
│  │    Langfuse: self-hosted (not SaaS) — saves $500+/mo          │   │
│  │    FSI: Per-tenant cost attribution (CloudWatch + tags)        │   │
│  │    3 topologies: right-sized per tier                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 6. SUSTAINABILITY                                            │   │
│  │    Serverless where possible: Lambda for async audit writes   │   │
│  │    Scale-to-zero: non-critical modules during off-hours       │   │
│  │    Region selection: us-east-1 (lowest carbon, most services) │   │
│  │    Batch processing: research pipeline stages batched          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### FSI Lens — Additional Controls

| FSI Lens Control | 007 Implementation | Module |
|-----------------|-------------------|--------|
| Data residency | Enterprise config specifies region. Data never leaves configured region. | M5, M6 |
| Regulatory reporting | Audit trail exportable in SEC/FINRA format | M10 |
| Third-party risk | All vendor connections via MCP gateway (single choke point) | M6 |
| Business continuity | Pipeline checkpointing, HITL gate persistence, cross-AZ | M8, M6 |
| Information barriers | Chinese wall OPA rules, memory isolation | M2, M4 |
| Record retention | S3 Object Lock Compliance mode, 6-year minimum | M10 |
| Incident response | PagerDuty + runbooks + audit trail for forensics | Infra |
| Change management | GitOps, all changes audited, two-person approval for OPA | CI/CD |



---

## PART 2: NETWORK ARCHITECTURE

### 2.1 The Core Principle: No Public Internet for Data Plane

Every module that touches client data, MNPI, or compliance decisions runs in private subnets. The only public-facing component is the channel gateway (OpenClaw) behind an ALB. Everything else is private.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        NETWORK ARCHITECTURE — CLOUD TOPOLOGY               │
│                                                                             │
│  ┌─── PUBLIC INTERNET ──────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │   Users (Slack, Teams, WhatsApp, Web, Bloomberg IB, Symphony)        │  │
│  │                                                                       │  │
│  └───────────────────────────────┬───────────────────────────────────────┘  │
│                                  │ HTTPS (TLS 1.3)                         │
│                                  ▼                                          │
│  ┌─── PUBLIC SUBNET (ALB only) ─────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │   ┌──────────────────────────────────────────────┐                   │  │
│  │   │  ALB (Application Load Balancer)              │                   │  │
│  │   │  WAF: AWS WAF (OWASP Top 10, rate limiting)   │                   │  │
│  │   │  Shield: AWS Shield Advanced (DDoS)            │                   │  │
│  │   │  Cert: ACM (auto-renewed TLS)                  │                   │  │
│  │   └──────────────────────┬───────────────────────┘                   │  │
│  │                          │                                            │  │
│  └──────────────────────────┼────────────────────────────────────────────┘  │
│                             │ internal (port 8080)                          │
│                             ▼                                               │
│  ┌─── PRIVATE SUBNET A (Application Tier) ──────────────────────────────┐  │
│  │                                                                       │  │
│  │   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐   │  │
│  │   │ M12 Agent  │  │ M9 Intent  │  │ M8 Pipeline│  │ M6 MCP     │   │  │
│  │   │ Runtime    │  │ Router     │  │ Engine     │  │ Gateway    │   │  │
│  │   │ (OpenClaw) │  │            │  │ (LangGraph)│  │            │   │  │
│  │   └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘   │  │
│  │         │               │               │               │           │  │
│  │         └───────────────┴───────┬───────┴───────────────┘           │  │
│  │                                 │ mTLS (cert-manager)               │  │
│  │                                 ▼                                    │  │
│  │   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐   │  │
│  │   │ M1 Identity│  │ M2/M4 OPA │  │ M10 Audit  │  │ M5 Config  │   │  │
│  │   │ (Keycloak) │  │ (sidecar)  │  │ Logger     │  │ Loader     │   │  │
│  │   └────────────┘  └────────────┘  └────────────┘  └────────────┘   │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─── PRIVATE SUBNET B (Data Tier) ─────────────────────────────────────┐  │
│  │                                                                       │  │
│  │   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐   │  │
│  │   │ RDS        │  │ ElastiCache│  │ DynamoDB   │  │ S3 Object  │   │  │
│  │   │ PostgreSQL │  │ Redis      │  │            │  │ Lock (WORM)│   │  │
│  │   │ (M1 users) │  │ (L1 memory)│  │ (L2/L3,   │  │ (M10 audit)│   │  │
│  │   │            │  │ (M6 rate)  │  │  pipeline) │  │            │   │  │
│  │   └────────────┘  └────────────┘  └────────────┘  └────────────┘   │  │
│  │                                                                       │  │
│  │   ┌────────────┐  ┌────────────┐                                     │  │
│  │   │ Langfuse   │  │ Vault      │                                     │  │
│  │   │ (PG-backed)│  │ (secrets)  │                                     │  │
│  │   └────────────┘  └────────────┘                                     │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─── AWS SERVICES (via VPC Endpoints / PrivateLink) ───────────────────┐  │
│  │                                                                       │  │
│  │   Bedrock (LLM)  ──── PrivateLink ──── no public internet             │  │
│  │   AgentCore       ──── PrivateLink ──── no public internet             │  │
│  │   S3              ──── Gateway Endpoint ── no public internet          │  │
│  │   DynamoDB        ──── Gateway Endpoint ── no public internet          │  │
│  │   ECR             ──── PrivateLink ──── no public internet             │  │
│  │   CloudWatch      ──── PrivateLink ──── no public internet             │  │
│  │   Secrets Manager ──── PrivateLink ──── no public internet             │  │
│  │   KMS             ──── PrivateLink ──── no public internet             │  │
│  │   STS             ──── PrivateLink ──── no public internet             │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─── EXTERNAL VENDOR ACCESS (via NAT Gateway, controlled) ─────────────┐  │
│  │                                                                       │  │
│  │   M11 Adapters → NAT Gateway → Vendor APIs                           │  │
│  │   (Salesforce, Orion, eMoney, Schwab, Bloomberg, SEC EDGAR)          │  │
│  │                                                                       │  │
│  │   Controls:                                                           │  │
│  │   - Security groups: outbound only to known vendor IP ranges          │  │
│  │   - NACLs: deny all inbound from internet                            │  │
│  │   - M6 gateway: rate limiting + circuit breaker per vendor            │  │
│  │   - All calls logged to M10 WORM                                     │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 VPC Design

```
VPC CIDR: 10.0.0.0/16 (65,536 IPs — room for multi-tenant growth)

  Public Subnets (ALB only):
    10.0.1.0/24  (us-east-1a)  — ALB
    10.0.2.0/24  (us-east-1b)  — ALB
    10.0.3.0/24  (us-east-1c)  — ALB

  Private Subnets — Application Tier (EKS worker nodes):
    10.0.10.0/23 (us-east-1a)  — 512 IPs
    10.0.12.0/23 (us-east-1b)  — 512 IPs
    10.0.14.0/23 (us-east-1c)  — 512 IPs

  Private Subnets — Data Tier (RDS, ElastiCache, Langfuse):
    10.0.20.0/24 (us-east-1a)  — 256 IPs
    10.0.21.0/24 (us-east-1b)  — 256 IPs
    10.0.22.0/24 (us-east-1c)  — 256 IPs

  Private Subnets — Management (Vault, monitoring, CI/CD runners):
    10.0.30.0/24 (us-east-1a)  — 256 IPs

  Total: 3 public + 9 private subnets across 3 AZs
```

### 2.3 VPC Endpoints — Zero Public Internet for AWS Services

Every AWS service 007 uses gets a VPC endpoint. No traffic to AWS services traverses the public internet.

| AWS Service | Endpoint Type | Why |
|-------------|--------------|-----|
| Bedrock | Interface (PrivateLink) | LLM calls stay private. MNPI in prompts never hits public internet. |
| Bedrock AgentCore | Interface (PrivateLink) | Agent runtime stays private. AgentCore supports VPC mode. |
| S3 | Gateway | WORM audit writes, OPA bundle storage, pipeline artifacts |
| DynamoDB | Gateway | Pipeline state, memory L2/L3, HITL gate state |
| ECR | Interface (PrivateLink) | Container image pulls during deployment |
| CloudWatch Logs | Interface (PrivateLink) | Structured logging |
| Secrets Manager | Interface (PrivateLink) | Secret retrieval at pod startup |
| KMS | Interface (PrivateLink) | Encryption key operations |
| STS | Interface (PrivateLink) | IAM role assumption for cross-account |
| Bloomberg B-PIPE | Interface (PrivateLink via NLB) | Market data stays private. BLPAPI binary traffic off public internet. Phase 4 Tier 2/5. |

Cost: ~$7-10/month per interface endpoint x 7 = ~$50-70/month. Worth it for zero public internet.

### 2.4 Network Policies (Kubernetes)

Every module has a NetworkPolicy that restricts which other modules can talk to it. Default deny all, explicit allow per dependency.

```yaml
# Example: M6 MCP Gateway NetworkPolicy
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: m6-mcp-gateway
  namespace: fsi-007
spec:
  podSelector:
    matchLabels:
      app: m6-mcp-gateway
  policyTypes: [Ingress, Egress]
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: m12-agent-runtime
        - podSelector:
            matchLabels:
              app: m8-pipeline-engine
      ports:
        - port: 8080
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: m1-identity
        - podSelector:
            matchLabels:
              app: m2-m4-policy-engine
        - podSelector:
            matchLabels:
              app: m10-audit-logger
        - podSelector:
            matchLabels:
              app: m11-mcp-adapters
      ports:
        - port: 8080
```

Network policy matrix (mirrors ARCH-03 dependency matrix):

```
WHO CAN TALK TO WHOM (ingress allowed from):

  M1  ← M2, M4, M6, M9, M10       (identity verification)
  M2  ← M6, M8                      (authority checks)
  M3  ← M7                          (schema lookups)
  M4  ← M6                          (MNPI filtering)
  M5  ← M2, M4, M6, M8, M9         (config reads)
  M6  ← M8, M12                     (MCP gateway — central hub)
  M7  ← M11                         (schema translation)
  M8  ← M12                         (pipeline invocation)
  M9  ← M12                         (intent classification)
  M10 ← M6, M8                      (audit logging)
  M11 ← M6                          (adapter calls)
  M12 ← ALB                         (user traffic only)
```

### 2.5 Hybrid Topology — Network Design

For Tier 2/5 firms that require the trust layer on-premise:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    HYBRID TOPOLOGY — NETWORK DESIGN                     │
│                                                                         │
│  ┌─── FIRM'S DATA CENTER / VPC ──────────────────────────────────────┐ │
│  │                                                                    │ │
│  │  TRUST LAYER (on-prem, firm controls)                             │ │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                   │ │
│  │  │ M1   │ │M2/M4 │ │ M6   │ │ M10  │ │ M11  │                   │ │
│  │  │Ident.│ │Policy│ │Gatew.│ │Audit │ │Adapt.│                   │ │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘                   │ │
│  │       ▲                                                           │ │
│  │       │  mTLS tunnel (Site-to-Site VPN or Direct Connect)         │ │
│  │       ▼                                                           │ │
│  └───────┼───────────────────────────────────────────────────────────┘ │
│          │                                                              │
│  ┌───────┼─── AWS VPC (007 cloud) ───────────────────────────────────┐ │
│  │       ▼                                                            │ │
│  │  COMPUTE LAYER (cloud, 007 manages)                               │ │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                   │ │
│  │  │ M3   │ │ M5   │ │ M7   │ │ M8   │ │ M9   │                   │ │
│  │  │Schema│ │Config│ │Trans.│ │Pipeln│ │Intent│                   │ │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘                   │ │
│  │                                                                    │ │
│  │  ┌──────┐                                                         │ │
│  │  │ M12  │ → Bedrock AgentCore (PrivateLink)                      │ │
│  │  │Runtme│ → Bedrock LLM (PrivateLink)                            │ │
│  │  └──────┘                                                         │ │
│  │                                                                    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  CONNECTION OPTIONS (ordered by preference):                            │
│                                                                         │
│  1. AWS Direct Connect (1-10 Gbps, dedicated, <5ms latency)            │
│     Best for: Tier 1/2 banks with existing DC connections               │
│     Cost: $0.02-0.09/GB + port fee ($200-500/mo)                       │
│                                                                         │
│  2. AWS Site-to-Site VPN (encrypted IPsec, <50ms latency)              │
│     Best for: Tier 2/5 firms without Direct Connect                     │
│     Cost: $0.05/hr per tunnel (~$36/mo) + data transfer                │
│                                                                         │
│  3. Transit Gateway (hub-and-spoke for multi-VPC)                       │
│     Best for: Firms with multiple VPCs/accounts                         │
│     Cost: $0.05/hr + $0.02/GB                                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

Hybrid on-prem minimal data zone (added per IMPL-06 Blocker 5):
- Local PostgreSQL (small): FIX session state (M13), HITL gate state
- Local Redis (small): working memory L1, rate limits
- These are NOT the full data tier. They are local caches for latency-sensitive and tunnel-independent operations.
- If tunnel down: trust layer continues operating locally. Audit writes queue locally, sync when tunnel recovers.

Key hybrid networking rules:
- ALL traffic between firm and cloud is encrypted (IPsec or mTLS over Direct Connect)
- Client data (MNPI) flows from firm to cloud ONLY through M6 gateway (single choke point)
- LLM prompts containing client context travel over PrivateLink (never public internet)
- Audit writes from cloud to firm's M10 over the same tunnel
- If tunnel goes down: fail-closed. No degraded mode that bypasses trust layer.

### 2.6 On-Premise Topology — Network Design

For Tier 1 banks. Everything in the firm's data center. No cloud dependency.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                  ON-PREMISE TOPOLOGY — NETWORK DESIGN                   │
│                                                                         │
│  ┌─── FIRM'S DATA CENTER ────────────────────────────────────────────┐ │
│  │                                                                    │ │
│  │  ┌─── DMZ (channel gateway only) ──────────────────────────────┐ │ │
│  │  │  ┌──────────┐                                                │ │ │
│  │  │  │ M12      │ ← reverse proxy (nginx/HAProxy)               │ │ │
│  │  │  │ OpenClaw │ ← WAF (ModSecurity or F5)                     │ │ │
│  │  │  └────┬─────┘                                                │ │ │
│  │  └───────┼──────────────────────────────────────────────────────┘ │ │
│  │          │ internal firewall                                      │ │
│  │          ▼                                                        │ │
│  │  ┌─── APPLICATION ZONE ────────────────────────────────────────┐ │ │
│  │  │  All 12 modules on bare-metal Kubernetes                     │ │ │
│  │  │  Self-hosted LLM: vLLM on 4-8x A100/H100 GPUs              │ │ │
│  │  │  OPA sidecar per pod (localhost, no network hop)             │ │ │
│  │  │  cert-manager for mTLS (internal CA)                         │ │ │
│  │  └──────────────────────────────────┬───────────────────────────┘ │ │
│  │                                     │ internal firewall           │ │
│  │                                     ▼                             │ │
│  │  ┌─── DATA ZONE ──────────────────────────────────────────────┐ │ │
│  │  │  PostgreSQL (replaces RDS + DynamoDB)                       │ │ │
│  │  │  Redis (replaces ElastiCache)                               │ │ │
│  │  │  MinIO (replaces S3)                                        │ │ │
│  │  │  NetApp SnapLock (replaces S3 Object Lock for WORM)         │ │ │
│  │  │  pgvector (replaces Pinecone)                               │ │ │
│  │  │  Langfuse (self-hosted, PostgreSQL-backed)                  │ │ │
│  │  │  HashiCorp Vault (self-hosted)                              │ │ │
│  │  └────────────────────────────────────────────────────────────┘ │ │
│  │                                                                    │ │
│  │  Network: 3 zones (DMZ → App → Data), firewalls between each     │ │
│  │  No internet access from App or Data zones                        │ │
│  │  Vendor API access: dedicated proxy in DMZ with allowlist         │ │
│  │                                                                    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

On-prem substitutions:

| Cloud Service | On-Prem Replacement | Notes |
|--------------|-------------------|-------|
| EKS | kubeadm / Rancher RKE2 | Firm's K8s platform team manages |
| RDS PostgreSQL | PostgreSQL 16 | HA with Patroni |
| ElastiCache Redis | Redis 7 Sentinel | HA with Sentinel |
| DynamoDB | PostgreSQL (JSONB) | Single DB, multiple schemas |
| S3 | MinIO | S3-compatible API |
| S3 Object Lock | NetApp SnapLock | WORM-compliant, SEC 17a-4 |
| Bedrock Claude | vLLM + Llama 3.1 405B | 4-8x A100/H100 GPUs |
| Pinecone | pgvector | Extension on existing PostgreSQL |
| KMS | Vault Transit | Encryption as a service |
| CloudWatch | ELK or Loki + Grafana | Structured logging |
| ACM | cert-manager + internal CA | Auto-rotation |



---

## PART 3: PACKAGING STRATEGY

### 3.1 The Problem

REV-05 identified: "20 services, no single deploy command." A Tier 4 RIA with no IT staff cannot deploy Kubernetes. A Tier 1 bank needs highly configurable Helm charts. We need packaging for every audience.

### 3.2 Packaging Layers

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      PACKAGING LAYERS                                   │
│                                                                         │
│  Layer 1: CONTAINER (per module)                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Every module = 1 Docker image                                   │   │
│  │  Multi-stage build: builder → runtime (distroless)               │   │
│  │  Base: python:3.12-slim (Python) / node:20-slim (TypeScript)     │   │
│  │  No root. Read-only filesystem. Health check endpoint.           │   │
│  │  Scanned: Trivy in CI/CD (zero critical, zero high)              │   │
│  │  Registry: ECR (cloud) / Harbor (on-prem)                        │   │
│  │  Tag: semver + git SHA (e.g., m6-gateway:1.2.3-abc1234)         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Layer 2: HELM CHART (per module)                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Every module = 1 Helm chart                                     │   │
│  │  Configurable: replicas, resources, env, secrets, topology       │   │
│  │  Includes: Deployment, Service, NetworkPolicy, HPA, PDB          │   │
│  │  OPA sidecar injected via chart dependency                       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Layer 3: UMBRELLA CHART (full platform)                                │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  fsi-007-platform (umbrella Helm chart)                          │   │
│  │  Dependencies: all 12 module charts + infra charts               │   │
│  │  3 values files: values-cloud / values-hybrid / values-onprem    │   │
│  │  Topology selector: --set topology=cloud|hybrid|onprem           │   │
│  │  Tenant config: --set tenant.name=acme --set tenant.archetype=t3 │   │
│  │  One command: helm install fsi-007 ./charts/fsi-007-platform     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Layer 4: TERRAFORM (infrastructure)                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  infra/terraform/                                                │   │
│  │    modules/vpc/          — VPC, subnets, endpoints, NAT          │   │
│  │    modules/eks/          — EKS cluster, node groups, Karpenter   │   │
│  │    modules/rds/          — PostgreSQL, multi-AZ, encryption      │   │
│  │    modules/redis/        — ElastiCache, multi-AZ                 │   │
│  │    modules/s3-worm/      — S3 Object Lock buckets                │   │
│  │    modules/vault/        — Vault on EKS or managed               │   │
│  │    modules/monitoring/   — Prometheus, Grafana, Alertmanager     │   │
│  │    environments/dev/     — dev account tfvars                    │   │
│  │    environments/staging/ — staging account tfvars                │   │
│  │    environments/prod/    — prod account tfvars                   │   │
│  │                                                                  │   │
│  │  One command: terraform apply -var-file=environments/prod/       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Layer 5: DEPLOY-FROM-ZERO SCRIPT                                       │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  scripts/deploy-from-zero.sh                                     │   │
│  │                                                                  │   │
│  │  Step 1: Validate prerequisites (aws cli, kubectl, helm, tf)     │   │
│  │  Step 2: terraform apply (VPC, EKS, RDS, Redis, S3)             │   │
│  │  Step 3: Configure kubectl context                               │   │
│  │  Step 4: Install cert-manager + OPA                              │   │
│  │  Step 5: Install Vault + seed secrets                            │   │
│  │  Step 6: helm install fsi-007-platform                           │   │
│  │  Step 7: Run smoke tests                                         │   │
│  │  Step 8: Print dashboard URLs                                    │   │
│  │                                                                  │   │
│  │  Target: <30 minutes from empty AWS account to running platform  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Helm Umbrella Chart Structure

```
charts/
  fsi-007-platform/              ← umbrella chart
    Chart.yaml
    values.yaml                  ← defaults
    values-cloud.yaml            ← AWS cloud overrides
    values-hybrid.yaml           ← hybrid overrides
    values-onprem.yaml           ← on-prem overrides
    templates/
      namespace.yaml
      network-policies.yaml      ← generated from dependency matrix
      tenant-config.yaml         ← ConfigMap from enterprise-config.yaml
    charts/                      ← subcharts (dependencies)
      m1-identity/
      m2-m4-policy-engine/
      m3-schema-registry/
      m5-config-loader/
      m6-mcp-gateway/
      m7-schema-translators/
      m8-pipeline-engine/
      m9-intent-router/
      m10-audit-logger/
      m11-mcp-adapters/
      m12-agent-runtime/
      compliance/
      opa/
      langfuse/
      monitoring/
```

### 3.4 Deploy Commands — Per Topology

```bash
# CLOUD (Tier 3/4) — Full AWS
terraform -chdir=infra/terraform apply \
  -var-file=environments/prod/cloud.tfvars
helm install fsi-007 ./charts/fsi-007-platform \
  -f charts/fsi-007-platform/values-cloud.yaml \
  --set tenant.name=acme-wealth \
  --set tenant.archetype=tier3 \
  --set tenant.region=us-east-1

# HYBRID (Tier 2/5) — Trust on-prem, compute in cloud
# On-prem side:
helm install fsi-007-trust ./charts/fsi-007-platform \
  -f charts/fsi-007-platform/values-hybrid.yaml \
  --set topology.role=trust-layer \
  --set tunnel.endpoint=vpn-xyz.amazonaws.com
# Cloud side:
helm install fsi-007-compute ./charts/fsi-007-platform \
  -f charts/fsi-007-platform/values-hybrid.yaml \
  --set topology.role=compute-layer \
  --set tunnel.endpoint=10.1.0.1

# ON-PREM (Tier 1) — Everything local
helm install fsi-007 ./charts/fsi-007-platform \
  -f charts/fsi-007-platform/values-onprem.yaml \
  --set llm.provider=vllm \
  --set llm.endpoint=http://gpu-cluster:8000 \
  --set storage.worm.type=snaplock
```

### 3.5 docker-compose.yml — Local Development

Phase 0 Day 1 deliverable. Every engineer starts here.

```yaml
# docker-compose.yml — local development stack
version: "3.9"

services:
  # --- Infrastructure ---
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: fsi007
      POSTGRES_USER: fsi007
      POSTGRES_PASSWORD: localdev
    ports: ["5432:5432"]
    volumes: ["pg-data:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U fsi007"]
      interval: 5s

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports: ["9000:9000", "9001:9001"]
    volumes: ["minio-data:/data"]

  opa:
    image: openpolicyagent/opa:latest
    command: run --server --bundle /bundles
    ports: ["8181:8181"]
    volumes: ["./opa-bundles:/bundles"]

  langfuse:
    image: langfuse/langfuse:latest
    environment:
      DATABASE_URL: postgresql://fsi007:localdev@postgres:5432/fsi007
      NEXTAUTH_SECRET: localdev-secret
      NEXTAUTH_URL: http://localhost:3000
    ports: ["3000:3000"]
    depends_on:
      postgres: { condition: service_healthy }

  keycloak:
    image: quay.io/keycloak/keycloak:24.0
    command: start-dev --import-realm
    environment:
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: admin
    ports: ["8080:8080"]
    volumes:
      - ./infra/keycloak/realm-export.json:/opt/keycloak/data/import/realm.json

  # --- Application Modules (hot-reload) ---
  m1-identity:
    build: { context: ., dockerfile: src/m1-identity/Dockerfile }
    environment:
      KEYCLOAK_URL: http://keycloak:8080
      DATABASE_URL: postgresql://fsi007:localdev@postgres:5432/fsi007
    ports: ["8001:8080"]
    depends_on: [keycloak, postgres]
    volumes: ["./src/m1-identity:/app"]

  m6-mcp-gateway:
    build: { context: ., dockerfile: src/m6-mcp-gateway/Dockerfile }
    environment:
      M1_URL: http://m1-identity:8080
      OPA_URL: http://opa:8181
      M10_URL: http://m10-audit-logger:8080
      REDIS_URL: redis://redis:6379
    ports: ["8006:8080"]
    depends_on: [m1-identity, opa, redis]
    volumes: ["./src/m6-mcp-gateway:/app"]

  m10-audit-logger:
    build: { context: ., dockerfile: src/m10-audit-logger/Dockerfile }
    environment:
      DATABASE_URL: postgresql://fsi007:localdev@postgres:5432/fsi007
      MINIO_ENDPOINT: http://minio:9000
      LANGFUSE_URL: http://langfuse:3000
    ports: ["8010:8080"]
    depends_on: [postgres, minio, langfuse]
    volumes: ["./src/m10-audit-logger:/app"]

volumes:
  pg-data:
  minio-data:
```

Note: Minimal local stack. M2/M4 runs as OPA sidecar (included). M3, M5, M7 are libraries. M8, M9, M11, M12 added as built in Phase 1-2.

### 3.6 Multi-Tenant Isolation

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MULTI-TENANT ISOLATION MODEL                         │
│                                                                         │
│  ┌─── SHARED CONTROL PLANE ──────────────────────────────────────────┐ │
│  │                                                                    │ │
│  │  EKS Cluster (shared)                                             │ │
│  │  Prometheus + Grafana (shared, tenant labels)                     │ │
│  │  ArgoCD (shared, per-tenant apps)                                 │ │
│  │  cert-manager (shared, per-tenant certs)                          │ │
│  │                                                                    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌─── ISOLATED DATA PLANE (per tenant) ──────────────────────────────┐ │
│  │                                                                    │ │
│  │  Namespace: tenant-acme-wealth                                    │ │
│  │  ┌──────────────────────────────────────────────────────────────┐ │ │
│  │  │  All 12 module pods (dedicated per tenant)                    │ │ │
│  │  │  OPA sidecar with tenant-specific policy bundle               │ │ │
│  │  │  Enterprise config (tenant-specific ConfigMap)                 │ │ │
│  │  │  NetworkPolicy: deny cross-namespace traffic                  │ │ │
│  │  └──────────────────────────────────────────────────────────────┘ │ │
│  │                                                                    │ │
│  │  Database: schema-per-tenant (shared RDS, separate schemas)       │ │
│  │    OR separate RDS instance (Tier 1/2 — full isolation)           │ │
│  │                                                                    │ │
│  │  Encryption: KMS CMK per tenant (separate key per tenant)         │ │
│  │                                                                    │ │
│  │  S3 WORM: separate prefix per tenant                              │ │
│  │    OR separate bucket (Tier 1/2)                                  │ │
│  │                                                                    │ │
│  │  Redis: key prefix per tenant                                     │ │
│  │    OR separate Redis instance (Tier 1/2)                          │ │
│  │                                                                    │ │
│  │  OPA bundle: per-tenant bundle                                    │ │
│  │    Includes firm-specific rules + archetype rules                 │ │
│  │                                                                    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ISOLATION LEVELS:                                                      │
│                                                                         │
│  Tier 3/4 (cost-sensitive):                                             │
│    Shared cluster, namespace isolation, schema-per-tenant,              │
│    shared Redis (key prefix), shared S3 (prefix), per-tenant KMS key   │
│                                                                         │
│  Tier 2/5 (security-sensitive):                                         │
│    Shared cluster, namespace isolation, separate RDS instance,          │
│    separate Redis instance, separate S3 bucket, per-tenant KMS key     │
│                                                                         │
│  Tier 1 (full isolation):                                               │
│    Dedicated cluster (on-prem or dedicated EKS), everything separate   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.7 SaaS Model for Tier 3/4

Tier 3/4 firms (wealth managers, RIAs) cannot deploy Kubernetes. They need managed SaaS.

```
SaaS Provisioning Flow:

  Customer signs up → selects archetype (Tier 3 BD or Tier 4 RIA)
                    → provides vendor credentials (Salesforce, Orion, etc.)
                    → 007 provisions:
                        1. Kubernetes namespace
                        2. Database schema
                        3. KMS key
                        4. S3 WORM prefix
                        5. OPA bundle (archetype + firm-specific)
                        6. Enterprise config (from onboarding wizard)
                        7. MCP adapters (per selected vendors)

  Time to provision: <5 minutes (automated)
  Time to first query: <15 minutes (after vendor OAuth)

  Customer manages via:
    - Web dashboard (config, user management, audit viewer)
    - No kubectl, no Helm, no Terraform
    - Self-service adapter configuration (add/remove vendors)
    - Compliance dashboard (audit trail, policy violations, HITL approvals)
```

### 3.8 Zero-Downtime Upgrade Strategy for M6

M6 (MCP Gateway) is the god module — every call flows through it. Upgrading M6 without downtime is critical.

```
M6 UPGRADE — BLUE-GREEN WITH CONNECTION DRAINING:

  1. Deploy M6-v2 (green) alongside M6-v1 (blue)
     Both registered in Kubernetes Service

  2. Shift traffic gradually:
     - 10% to green (canary, 5 minutes)
     - Monitor: error rate, latency, OPA decisions
     - If healthy: 50% (10 minutes)
     - If healthy: 100%

  3. Drain M6-v1 (blue):
     - Stop accepting new connections
     - Wait for in-flight requests to complete (30s timeout)
     - Terminate

  4. Rollback trigger (automatic):
     - Error rate > 1% → instant rollback to blue
     - P99 latency > 2x baseline → instant rollback
     - OPA DENY rate anomaly → instant rollback

  Implementation: Argo Rollouts canary strategy
                  + Prometheus metrics for analysis
```



---

## PART 4: SECURITY HARDENING — NETWORK LEVEL

### 4.1 mTLS Between All Modules

Every module-to-module call uses mutual TLS. No plaintext HTTP inside the cluster.

```
mTLS IMPLEMENTATION:

  Tool: cert-manager + internal CA (self-signed root)
  Rotation: Certificates auto-rotated every 24 hours
  Enforcement: Application-level mTLS (FastAPI + httpx with client certs)
               OR service mesh sidecar (Istio/Linkerd, optional)

  Certificate hierarchy:
    Root CA (offline, HSM-backed in production)
      └── Intermediate CA (cert-manager, auto-managed)
           ├── m1-identity.fsi-007.svc.cluster.local
           ├── m2-m4-policy-engine.fsi-007.svc.cluster.local
           ├── m6-mcp-gateway.fsi-007.svc.cluster.local
           ├── m10-audit-logger.fsi-007.svc.cluster.local
           ├── m11-mcp-adapters.fsi-007.svc.cluster.local
           └── ... (one cert per module)

  On-prem: Same pattern, internal CA managed by firm's PKI team
```

### 4.2 Secrets Management

```
SECRET LIFECYCLE:

  Development (docker-compose):
    Environment variables in .env file (gitignored)
    No Vault dependency for local dev

  Staging / Production (cloud):
    HashiCorp Vault (primary)
      └── Kubernetes auth method (pod identity → Vault token)
      └── Dynamic secrets for PostgreSQL (short-lived credentials)
      └── Transit engine for encryption operations
    AWS Secrets Manager (fallback / AWS-native option)
      └── Automatic rotation (Lambda-based)

  On-prem:
    HashiCorp Vault (self-hosted, HA with Raft)
      └── Same patterns as cloud

  NEVER in:
    - Environment variables in Helm values (use Vault references)
    - ConfigMaps
    - Container images
    - Git repository
```

### 4.3 WAF Rules

```
AWS WAF RULES (on ALB):

  Managed rule groups:
    - AWSManagedRulesCommonRuleSet (OWASP Top 10)
    - AWSManagedRulesKnownBadInputsRuleSet (Log4j, etc.)
    - AWSManagedRulesSQLiRuleSet (SQL injection)
    - AWSManagedRulesBotControlRuleSet (bot detection)

  Custom rules:
    - Rate limiting: 1000 requests/5min per IP (configurable)
    - Geo-blocking: restrict to firm's operating jurisdictions
    - Request size: max 16KB body (agent messages)
    - Header validation: require valid Authorization header

  On-prem equivalent:
    - ModSecurity with OWASP CRS
    - Or F5 Advanced WAF (if firm already has F5)
```

### 4.4 DDoS Protection

```
LAYER 3/4: AWS Shield Standard (included, automatic)
LAYER 7:   AWS Shield Advanced ($3,000/mo — recommended for production)
           + WAF rate limiting
           + CloudFront (optional, for web channel)

On-prem: Firm's existing DDoS mitigation (Akamai, Cloudflare, F5)
```

---

## PART 5: GITOPS AND CI/CD

### 5.1 GitOps with ArgoCD

```
GIT REPOSITORY (source of truth)
  │
  ├── charts/fsi-007-platform/     ← Helm charts
  ├── infra/terraform/              ← Infrastructure
  ├── opa-bundles/                  ← OPA policies
  └── environments/
       ├── dev/                     ← dev overrides
       ├── staging/                 ← staging overrides
       └── prod/                    ← prod overrides

ARGOCD (watches git, syncs to cluster)
  │
  ├── App: fsi-007-dev      → watches main → auto-syncs to dev
  ├── App: fsi-007-staging  → watches release/* → auto-syncs to staging
  └── App: fsi-007-prod     → watches tags (v*) → manual approve → canary

FLOW:
  Developer pushes to main
    → CI: lint, test, build, scan, push to ECR
    → ArgoCD auto-syncs dev
    → Release branch created
    → ArgoCD auto-syncs staging
    → QA validates
    → Tag release (v1.2.3)
    → ArgoCD waits for manual approval
    → Approved → canary rollout (Argo Rollouts)
```

### 5.2 CI/CD Pipeline

```
GITHUB ACTIONS PIPELINE:

  on: push to main
    lint:       ruff (Python), eslint (TypeScript), opa check (Rego)
    test:       pytest (unit), opa test (Rego), schema reconciliation
    build:      docker build per changed module, trivy scan, push ECR
    integrate:  docker-compose up, integration tests, 200 eval queries

  on: tag (v*)
    staging:    terraform plan+apply, helm upgrade, full eval (1,230), adversarial (200)
    prod:       manual gate → terraform apply, helm upgrade (canary), monitor 15min, promote/rollback
```

---

## PART 6: REVISED SCORES

After ARCH-08, the operational architecture scores change:

| Dimension | REV-05 Score | After ARCH-08 | What Changed |
|-----------|-------------|---------------|-------------|
| Modularity | 7/10 | 7/10 | No change (M6 god module still exists, but upgrade strategy mitigates) |
| Reproducibility | 6/10 | 8/10 | docker-compose, deploy-from-zero, Helm umbrella, Terraform modules |
| Flexibility | 8/10 | 8/10 | No change (already strong) |
| Ease of Deploy | 5/10 | 7.5/10 | 3 topology deploy commands, SaaS for Tier 3/4, umbrella chart, GitOps |
| Future-Proofing | 7/10 | 8/10 | Well-Architected alignment, multi-tenant from day 1, network isolation |
| OVERALL | 6.6/10 | 7.7/10 | +1.1 points. Platform is now designed, not just the product. |

### What Still Needs Implementation (not design)

| Item | When | Effort |
|------|------|--------|
| docker-compose.yml | Phase 0, Week 1 | 1 day |
| Terraform VPC module | Phase 0, Week 2 | 2 days |
| Terraform EKS module | Phase 0, Week 2-3 | 3 days |
| Helm charts (per module) | Phase 1, as modules built | Ongoing |
| Umbrella chart | Phase 1, Week 12 | 2 days |
| deploy-from-zero.sh | Phase 1, Week 14 | 2 days |
| ArgoCD setup | Phase 1, Week 8 | 1 day |
| VPC endpoints | Phase 1, Week 6 | 1 day |
| Network policies | Phase 1, as modules built | Ongoing |
| Multi-tenant namespace automation | Phase 2, Week 16 | 3 days |
| SaaS provisioning API | Phase 2, Week 20 | 5 days |
| Argo Rollouts (M6 canary) | Phase 2, Week 22 | 2 days |

Total additional effort: ~25 engineering days across Phase 0-2. Integrated into existing build plan.

---

## PART 7: COMPLETE TRAFFIC FLOW — ONE REQUEST, EVERY NETWORK HOP

To prove the network design works end-to-end:

```
"Prep me for my meeting with Henderson tomorrow"

  1. Sarah types on Slack
     Slack → HTTPS → Internet → ALB (public subnet, WAF inspects)

  2. ALB → M12 OpenClaw (private subnet A, port 8080)
     Internal, no public IP

  3. M12 → M1 Identity (private subnet A, mTLS)
     M1 → Keycloak (private subnet A, localhost or mTLS)
     M1 → RDS PostgreSQL (private subnet B, TLS)

  4. M12 → M9 Intent Router (private subnet A, mTLS)
     M9 → Bedrock Haiku (PrivateLink — never public internet)
     Intent: client.prep_meeting

  5. M12 → M8 Pipeline (private subnet A, mTLS)
     M8 → M6 MCP Gateway (private subnet A, mTLS)

  6. M6 → M2 Authority (OPA sidecar, localhost:8181, no network hop)
     Decision: ALLOW

  7. M6 → M11 Salesforce Adapter (private subnet A, mTLS)
     M11 → NAT Gateway → Salesforce API (HTTPS, internet)
     Response → M7 Translator → canonical Client
     M6 → M4 MNPI Filter (OPA sidecar, localhost:8181)
     M6 → M10 Audit (private subnet A, mTLS)
     M10 → S3 Object Lock (Gateway endpoint, no internet)
     M10 → Langfuse (private subnet B, TLS)

  8. M6 → M11 Orion Adapter → NAT → Orion API
     Same filter + audit flow

  9. M8 → Bedrock Sonnet (PrivateLink — never public internet)
     Synthesize meeting prep brief
     Input: canonical Client + Holdings (MNPI-filtered)

  10. M8 → M10 Audit (log LLM call + output)
      M10 → S3 Object Lock (WORM write)

  11. M12 → Slack (response via Slack API, HTTPS, internet)

  NETWORK HOPS:
    Private-only:  steps 2-10 (all module-to-module communication)
    PrivateLink:   steps 4, 9 (Bedrock LLM calls)
    Internet:      steps 1, 7, 8, 11 (user channel + vendor APIs only)
    MNPI on internet: NEVER (filtered before leaving M6)
```

---

## SUMMARY

This document closes the three gaps identified in REV-05:

1. Packaging: 5-layer strategy (container → Helm → umbrella → Terraform → deploy-from-zero). One command per topology. docker-compose for local dev. SaaS for Tier 3/4.

2. Networking: Private subnets for all modules. PrivateLink for Bedrock/AgentCore. VPC endpoints for all AWS services. NAT Gateway only for vendor APIs. mTLS between all modules. NetworkPolicy per dependency. 3-zone on-prem design.

3. Well-Architected: All 6 pillars mapped to 007 modules. FSI Lens controls addressed. Multi-tenant isolation designed from day 1. GitOps with ArgoCD. CI/CD with canary deployments.

Operational architecture score: 6.6/10 → 7.7/10. The remaining 2.3 points come from implementation, not design.

---

*ARCH-08 — Project 007 FSI Interoperability Platform*
*Packaging, Networking, and AWS Well-Architected Alignment*
