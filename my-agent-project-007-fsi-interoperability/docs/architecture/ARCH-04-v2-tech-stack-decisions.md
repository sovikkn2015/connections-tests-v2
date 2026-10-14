# PROJECT 007 v2 — TECH STACK DECISION DOCUMENT

> Version: 2.0
> Date: July 2026
> Status: Detailed Technical Specification (addressing LLMJ Committee Actions #3)
> Audience: Engineering team, architecture review board, compliance stakeholders
> Predecessor: 007 v1 architecture (9 documents), LLMJ Committee Review (5 reviewers)

---

## 1. EXECUTIVE SUMMARY

This document specifies the exact technology stack for each of the 12 modules (M1–M12) in Project 007. Every choice is justified against alternatives considered, with cloud-agnostic deployment paths for AWS, Azure, GCP, and on-premise environments. This directly addresses the committee's finding that "across 9 documents and ~25,000 words, the exact technology stack for each module is never explicitly defined."

---

## 2. MODULE-BY-MODULE TECH STACK

### M1: Agent Identity Service

| Dimension | Decision | Justification |
|-----------|----------|---------------|
| **Language** | Python 3.12+ | Consistent with M2/M4/M6/M8/M9 core modules; strong JWT/crypto libraries |
| **Framework** | FastAPI (identity API) + Keycloak (user auth) | Keycloak is Apache 2.0, CNCF-adjacent, used in FSI for Basel III compliance. Handles OAuth 2.0/OIDC/SAML natively. We BUILD the custom AID schema on top; we ADAPT Keycloak for user authentication and token issuance. FastAPI exposes the AID issuance/verification/revocation endpoints. |
| **Alternatives Considered** | **Auth0** — SaaS, no self-hosted option for air-gapped Tier 1 banks. **AWS Cognito** — AWS-locked, insufficient customization for AID schema. **Custom JWT service** — unnecessary when Keycloak handles 80% of the work. |
| **Key Libraries** | `PyJWT` (AID token signing/verification), `cryptography` (key management interface), `pydantic` (AID schema validation) |
| **Token Format** | JWT (RS256 signing) with custom FSI claims (LEI, CRD, archetype, authority_scope, authority_excludes) |
| **Key Management** | Abstracted via provider interface — AWS KMS (cloud), HashiCorp Vault (hybrid/on-prem), Azure Key Vault (Azure deployments) |
| **Deployment** | Container (FastAPI) + Keycloak container (sidecar or shared service) |
| **Database** | PostgreSQL (Keycloak user store + AID registry) |
| **Cloud Dependencies** | KMS for key management (abstracted) |
| **Cloud-Agnostic Path** | HashiCorp Vault replaces KMS; Keycloak is fully self-hosted |

### M2/M4: Unified Authority + MNPI Policy Engine (OPA/Rego)

| Dimension | Decision | Justification |
|-----------|----------|---------------|
| **Language** | Rego (policy language) + Python 3.12+ (integration layer) | OPA is CNCF-graduated, used by Goldman Sachs, Capital One, and other FSI institutions via Styra. Evaluates exactly the (identity, action, target, context) → decision pattern M2 needs. M4 MNPI rules are additional Rego policy bundles in the same engine — eliminates the consistency risk of two separate engines (committee finding: "what if M2 allows but M4 denies?"). |
| **Framework** | Open Policy Agent (OPA) v1.x as evaluation engine + Python FastAPI as integration API |
| **Alternatives Considered** | **AWS Cedar** — newer, less FSI adoption, AWS-locked. **Casbin** — simpler RBAC/ABAC but lacks Rego's expressiveness for field-level MNPI filtering. **Custom YAML interpreter** (v1 proposal) — reinventing the wheel; OPA handles evaluation, caching, partial evaluation, and bundle management out of the box. Building a custom policy engine is unnecessary risk for a system handling MNPI. |
| **Policy Structure** | Two policy bundles in one OPA instance: `authority/` (M2 rules: action authorization, delegation, escalation) and `mnpi/` (M4 rules: per-archetype field filtering, restricted list, Chinese wall). Bundles are versioned independently. |
| **Key Libraries** | `opa-python-client` (OPA REST API client), `pydantic` (policy input/output schemas), `httpx` (async OPA queries) |
| **Deployment** | OPA sidecar container (per-service) or shared OPA server (per-namespace). Python integration layer as container. |
| **Database** | OPA bundle storage: S3 (cloud) / MinIO (on-prem) / Azure Blob (Azure). Policy version history: PostgreSQL. |
| **Performance** | OPA evaluates policies in <1ms for typical rule sets. Partial evaluation caches common decisions. Bundle updates propagate in <30 seconds (configurable). |
| **Fail Mode** | **FAIL-CLOSED** — if OPA is unreachable, all requests are DENIED. Maximum propagation delay SLA: <60 seconds for restricted list updates. |
| **Cloud-Agnostic Path** | OPA is fully open-source. No cloud dependency. Bundle storage is the only external dependency (S3/MinIO/Blob). |

### M3: Canonical Schema Registry

| Dimension | Decision | Justification |
|-----------|----------|---------------|
| **Language** | JSON Schema (type definitions) + Python 3.12+ (registry API) |
| **Framework** | JSON Schema Draft 2020-12 for type definitions + FastAPI for registry API |
| **Alternatives Considered** | **Protobuf** — excellent for wire format but poor for human-readable schema documentation; FSI compliance SMEs need to read and validate schemas. **Apache Avro** — good for Kafka but overkill for REST/MCP. **OpenMetadata/DataHub** — considered for registry infrastructure but adds operational complexity; a lightweight FastAPI registry with JSON Schema validation is sufficient for Phase 1. Revisit for Phase 3+. |
| **Versioning Strategy** | Semantic versioning (MAJOR.MINOR.PATCH). MAJOR = breaking change (field removed/renamed). MINOR = additive (new optional field). PATCH = documentation/description fix. Breaking change detection: automated JSON Schema diff in CI/CD. All translators (M7) pin to a schema version. |
| **Key Libraries** | `jsonschema` (validation), `json-schema-diff` (breaking change detection), `pydantic` (runtime type enforcement) |
| **Canonical Types** | `Client`, `Holding`, `Order`, `ResearchBrief`, `ComplianceCheck`, `AuditEntry`, `PlanSummary`, `RiskProfile` — each with explicit field-level documentation of inclusions, exclusions, and semantic meaning |
| **Deployment** | Container (FastAPI). Schema files stored in Git (version control) + served via API. |
| **Database** | Git (source of truth for schema definitions) + Redis (schema cache, TTL 5 min) |
| **Cloud-Agnostic Path** | Fully cloud-agnostic. Git + container. |

### M5: Enterprise Config Loader

| Dimension | Decision | Justification |
|-----------|----------|---------------|
| **Language** | Python 3.12+ |
| **Framework** | Pydantic v2 (config validation) + watchdog (hot reload) |
| **Alternatives Considered** | **Kubernetes ConfigMaps** — good for cloud but not for on-prem YAML-first deployments. Used as a delivery mechanism in K8s deployments, but the loader itself is runtime-agnostic. **Spring Cloud Config** — Java ecosystem, not applicable. |
| **Config Validation** | Pydantic models enforce schema. Invalid config = startup failure (fail-fast). |
| **Secrets Management** | Secrets (API keys, DB passwords) are NEVER in enterprise-config.yaml. Referenced via `${VAULT:secret/path}` or `${ENV:VAR_NAME}` syntax. Resolved at runtime from: HashiCorp Vault (primary), AWS Secrets Manager (AWS), Azure Key Vault (Azure), environment variables (dev/test). |
| **Hot Reload** | File watcher triggers config reload without restart. Compliance rules (M2/M4 OPA bundles) reload independently via OPA bundle sync. |
| **Deployment** | Library (imported by other modules), not a standalone service |
| **Cloud-Agnostic Path** | Fully cloud-agnostic. YAML + Pydantic. |

### M6: Trust-Aware MCP Gateway

| Dimension | Decision | Justification |
|-----------|----------|---------------|
| **Language** | Python 3.12+ (application-level middleware) |
| **Framework** | FastAPI + custom MCP proxy middleware |
| **Architecture Decision** | **Application-level middleware**, not Envoy proxy with custom filters. Rationale: Envoy custom filters require C++/Lua/WASM — adding complexity for a team that is Python/TypeScript. The trust logic (M1 verify → M2 authorize → M4 filter → M10 audit) is complex business logic that benefits from Python's expressiveness and testability. Envoy is excellent for L4/L7 routing but the trust-aware filtering requires deep integration with OPA, schema registry, and audit logger that is more naturally expressed in application code. **Revisit for Phase 4+** when throughput exceeds 10K req/sec — at that point, move static routing to Envoy and keep trust logic in application layer. |
| **Alternatives Considered** | **Envoy + custom WASM filters** — higher performance but C++/Rust filter development is a different skill set; trust logic is too complex for WASM filters. **Kong/APISIX** — good API gateways but plugin systems are less flexible than custom Python middleware for FSI-specific trust logic. **NGINX + Lua** — similar concerns to Envoy. |
| **Key Libraries** | `httpx` (async MCP server calls), `opentelemetry-api` (distributed tracing), `circuitbreaker` (per-MCP-server circuit breakers), `tenacity` (retry with exponential backoff) |
| **Resilience Patterns** | Circuit breaker per MCP server (5 failures → open for 30s). Retry with exponential backoff (3 retries, 1s/2s/4s). Timeout per MCP call (30s default, configurable per server). Bulkhead isolation (separate thread pools per MCP server category). Rate limiting per user per tool (configurable). |
| **Deployment** | Container. Horizontally scalable. |
| **Database** | Redis (rate limit counters, circuit breaker state, response cache with short TTL) |
| **Cloud-Agnostic Path** | Fully cloud-agnostic. Python + Redis. |

### M7: Schema Translators

| Dimension | Decision | Justification |
|-----------|----------|---------------|
| **Language** | Python 3.12+ |
| **Framework** | Pydantic v2 (type-safe translation) + pytest (automated reconciliation tests) |
| **Approach** | Hand-written translators with code-generation assist. Each translator is a Python module with `to_canonical()` and `from_canonical()` functions. Mapping definitions stored as declarative YAML; code generated from YAML where possible, hand-tuned for semantic edge cases. |
| **Alternatives Considered** | **Fully generated from mapping DSL** — attractive but semantic mismatches (e.g., Orion MarketValue includes accrued interest) require human judgment. Generated code is the starting point; human review is mandatory. **JSONata/JQ** — good for simple field mapping but cannot handle semantic transformations. |
| **Testing** | Automated reconciliation: for every translator, compare canonical output against source system values for 100+ sample records. Flag any field where canonical value ≠ source value beyond rounding tolerance. Run daily in CI/CD. |
| **Deployment** | Library (imported by M11 adapters) |
| **Cloud-Agnostic Path** | Fully cloud-agnostic. Pure Python. |

### M8: Pipeline Engine (LangGraph)

| Dimension | Decision | Justification |
|-----------|----------|---------------|
| **Language** | Python 3.12+ |
| **Framework** | LangGraph (MIT license) |
| **Justification vs Custom pipeline.py (006)** | The 23-stage research pipeline with HITL gates, checkpointing, and branching IS a stateful directed graph. LangGraph was literally designed for this: stateful graphs with durable checkpointing (pause at HITL gate, persist state, resume after human approval), time-travel debugging (replay any pipeline run from any stage), human-in-the-loop as a first-class primitive, and deployment on Bedrock AgentCore. The custom pipeline.py from 006 (~1,400 lines) would need to reimplement all of these features. LangGraph reduces custom code from ~1,400 lines to ~600 lines of graph definition + stage implementations. |
| **Alternatives Considered** | **Custom pipeline.py (006)** — works for single-path pipelines but lacks checkpointing, HITL, and time-travel. Maintaining a custom state machine is unnecessary risk. **Prefect/Airflow** — designed for data pipelines, not LLM agent pipelines. No native HITL or LLM integration. **CrewAI** — good for prototyping but weaker production observability. |
| **Key Libraries** | `langgraph` (pipeline orchestration), `langchain-aws` (Bedrock integration), `langchain-community` (tool integrations) |
| **Checkpointing** | LangGraph native checkpointing to DynamoDB (cloud) or PostgreSQL (on-prem). Pipeline state survives process restarts. |
| **Deployment** | Container. Long-running pipeline executions managed by LangGraph's async runtime. |
| **Database** | DynamoDB (checkpoint state — cloud) / PostgreSQL (on-prem) |
| **Cloud-Agnostic Path** | LangGraph is open-source. Checkpoint backend is pluggable (DynamoDB/PostgreSQL/SQLite). |

### M9: FSI Intent Router

| Dimension | Decision | Justification |
|-----------|----------|---------------|
| **Language** | Python 3.12+ |
| **Framework** | LLM function calling with structured output (Anthropic tool_use / OpenAI function_calling) |
| **Approach** | The FSI intent taxonomy is defined as a JSON Schema (tool/function schema). The LLM classifies user input into structured intents using native function calling with constrained output. For unambiguous intents (80%+), deterministic regex/keyword routing bypasses the LLM entirely. For ambiguous intents, LLM classification with confidence score — below 80% confidence, ask user for clarification. |
| **Alternatives Considered** | **Fine-tuned classifier** — requires training data we don't have yet; function calling achieves 85-95% accuracy without fine-tuning. Revisit when eval data exceeds 5,000 labeled examples. **Rule-based NLU (Rasa)** — too rigid for natural language variation. **Embedding similarity** — less precise than structured function calling for a defined taxonomy. |
| **Key Libraries** | `anthropic` (Claude function calling), `pydantic` (intent schema validation) |
| **Deployment** | Container (lightweight, fast cold start) |
| **Cloud-Agnostic Path** | LLM provider abstracted (see Section 4). Intent taxonomy is provider-agnostic JSON Schema. |

### M10: Audit Logger

| Dimension | Decision | Justification |
|-----------|----------|---------------|
| **Language** | Python 3.12+ |
| **Framework** | FastAPI (audit API) + three-tier write architecture |
| **Three-Tier Architecture** | **Tier 1 — Operational (Langfuse):** Real-time LLM observability, prompt debugging, cost tracking. Retention: 90 days. NOT the regulatory record. **Tier 2 — Compliance (S3 Object Lock / WORM):** Immutable, 6-year retention, SHA-256 hash per entry for integrity verification, third-party access via cross-account IAM for 17a-4(f)(3)(vii) DEA requirement. THIS is the regulatory record of truth. **Tier 3 — Business (CRM):** Salesforce IR_Audit_Log__c or equivalent. Business-accessible audit trail for advisors and compliance officers. Not the regulatory record. |
| **Alternatives Considered** | **Langfuse only** — NOT WORM-compliant; records can be modified/deleted. Rejected as sole audit store. **CRM only** — Salesforce records can be edited by admins. Not immutable. **Splunk/Datadog** — good for log aggregation but not WORM-compliant. Used as optional Tier 1 alternative to Langfuse for firms on those platforms. |
| **WORM Implementation** | S3 Object Lock (Compliance mode) — retention is IRREVERSIBLE once set. 6-year retention for trade-related records, 3-year for order tickets, 5-year for general books and records. Azure alternative: Immutable Blob Storage. On-prem alternative: NetApp SnapLock or Dell EMC Centera. |
| **Key Libraries** | `langfuse` (LLM observability), `boto3` (S3 Object Lock), `hashlib` (SHA-256 integrity hashing) |
| **Dead Letter Queue** | Failed audit writes go to SQS DLQ (cloud) / RabbitMQ DLQ (on-prem). If audit write fails, the entire request fails (fail-closed for compliance). |
| **Deployment** | Container |
| **Database** | S3 Object Lock (WORM), Langfuse (PostgreSQL-backed), CRM (Salesforce/equivalent) |
| **Cloud-Agnostic Path** | S3 Object Lock → Azure Immutable Blob → NetApp SnapLock (on-prem). Langfuse is self-hosted. |

### M11: MCP Server Adapters

| Dimension | Decision | Justification |
|-----------|----------|---------------|
| **Language** | TypeScript/Node.js (primary) + Python (for vendors with Python SDKs) |
| **Framework** | `@modelcontextprotocol/sdk` (official MCP SDK for TypeScript) |
| **Justification** | 006's mcp-rest-bridge.mjs is TypeScript/Node.js and works. Most vendor REST APIs are well-served by TypeScript. Python adapters for vendors with Python-only SDKs (e.g., Bloomberg BLPAPI). Each adapter implements: `GET /` (health), `POST /tools/list` (capability discovery), `POST /tools/call` (tool execution). |
| **Alternatives Considered** | **Python only** — would work but TypeScript has better async HTTP handling for REST API wrapping and the MCP SDK is TypeScript-first. **Go** — fast but smaller ecosystem for vendor SDK integration. |
| **Per-Adapter Concerns** | Each adapter handles: authentication (OAuth/API key per vendor), rate limiting (vendor-specific limits), error handling (vendor-specific error codes → canonical errors), retry logic (per vendor SLA). |
| **Deployment** | Container per adapter (independently deployable, independently scalable). Sidecar deployment option for on-prem (adapter runs next to the data source). Serverless option for low-traffic adapters (Lambda/Cloud Functions). |
| **Cloud-Agnostic Path** | Fully cloud-agnostic. Node.js containers. |

### M12: Agent Runtime + Multi-Agent Orchestration

| Dimension | Decision | Justification |
|-----------|----------|---------------|
| **Language** | Python 3.12+ |
| **Framework** | Strands Agents SDK (Apache 2.0) for multi-agent orchestration on Bedrock AgentCore |
| **Justification** | Strands is open-source (1M+ downloads), deploys natively on Bedrock AgentCore (GA Oct 2025), supports supervisor + specialist patterns, and is model-driven (LLM decides tool use). The committee unanimously recommended moving from single-agent to supervisor + specialist. Strands provides this natively. OpenClaw remains as the channel gateway (12+ channels) but the orchestration core moves to Strands for multi-agent support. |
| **Alternatives Considered** | **OpenClaw alone** — single-agent-with-tools pattern; insufficient for 5 fundamentally different reasoning patterns (committee finding). **CrewAI** — good for prototyping but weaker production observability and no native AgentCore deployment. **AutoGen/Microsoft Agent Framework** — Azure-centric, in maintenance mode transition. **Custom orchestrator** — unnecessary when Strands provides the pattern natively. |
| **Channel Gateway** | OpenClaw Gateway for 12+ channels (Slack, Teams, WhatsApp, Telegram, Discord, Web, SMS, Email, Bloomberg IB Chat, Symphony, custom portals). OpenClaw handles channel routing; Strands handles agent orchestration. |
| **Key Libraries** | `strands-agents` (agent SDK), `strands-agents-tools` (tool integration), `langgraph` (research specialist pipeline) |
| **Deployment** | Bedrock AgentCore (cloud) / Kubernetes (hybrid/on-prem) |
| **Cloud-Agnostic Path** | Strands is open-source and runs on any Python runtime. AgentCore is the managed deployment target for AWS; Kubernetes is the deployment target for hybrid/on-prem. |

---

## 3. DEPLOYMENT TOPOLOGIES

### Topology 1: Full Cloud (AWS) — Tier 3/4 Target

```
┌─────────────────────────────────────────────────────────────────┐
│  AWS ACCOUNT (per-tenant or shared with namespace isolation)    │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  BEDROCK AGENTCORE                                       │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │  │
│  │  │ Strands      │  │ LangGraph    │  │ OpenClaw      │  │  │
│  │  │ Supervisor   │  │ Research     │  │ Channel GW    │  │  │
│  │  │ + Specialists│  │ Pipeline     │  │ (12+ channels)│  │  │
│  │  └──────┬───────┘  └──────┬───────┘  └───────────────┘  │  │
│  └─────────┼─────────────────┼──────────────────────────────┘  │
│            │                 │                                   │
│  ┌─────────▼─────────────────▼──────────────────────────────┐  │
│  │  EKS CLUSTER (or ECS Fargate)                            │  │
│  │                                                          │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │  │
│  │  │ M1     │ │ M2/M4  │ │ M3     │ │ M5     │           │  │
│  │  │Identity│ │OPA+API │ │Schema  │ │Config  │           │  │
│  │  │+Keyclk │ │        │ │Registry│ │        │           │  │
│  │  └────────┘ └────────┘ └────────┘ └────────┘           │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │  │
│  │  │ M6     │ │ M9     │ │ M10    │ │ M11    │           │  │
│  │  │MCP GW  │ │Intent  │ │Audit   │ │Adapters│           │  │
│  │  │        │ │Router  │ │Logger  │ │(per svc)│          │  │
│  │  └────────┘ └────────┘ └────────┘ └────────┘           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  DATA LAYER                                              │  │
│  │  RDS PostgreSQL (M1, M3)  │  DynamoDB (M8 checkpoints)  │  │
│  │  ElastiCache Redis (M6)   │  S3 Object Lock (M10 WORM)  │  │
│  │  S3 (OPA bundles)         │  Langfuse (self-hosted ECS)  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  BEDROCK LLM                                             │  │
│  │  Claude Sonnet (research, deep reasoning)                │  │
│  │  Claude Haiku (client service, fast responses)           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  OBSERVABILITY                                           │  │
│  │  OpenTelemetry Collector → CloudWatch / Grafana Cloud    │  │
│  │  Prometheus (metrics) → Grafana (dashboards)             │  │
│  │  PagerDuty (alerting)                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Cost Estimate (per tenant, Tier 4 RIA):** $800–$2,500/month infrastructure
**Cost Estimate (per tenant, Tier 3 BD):** $3,000–$8,000/month infrastructure


### Topology 2: Hybrid Cloud — Tier 2/5 Target

```
┌─────────────────────────────────────────────────────────────────┐
│  FIRM'S PRIVATE NETWORK / VPC                                   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  ON-PREMISE / FIRM VPC (trust layer stays with the data) │  │
│  │                                                          │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │  │
│  │  │ M1     │ │ M2/M4  │ │ M6     │ │ M10    │           │  │
│  │  │Identity│ │OPA     │ │MCP GW  │ │Audit   │           │  │
│  │  │+Keyclk │ │(trust) │ │(trust) │ │(WORM)  │           │  │
│  │  └────────┘ └────────┘ └────────┘ └────────┘           │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐                      │  │
│  │  │ M5     │ │ M7     │ │ M11    │  ← Adapters run      │  │
│  │  │Config  │ │Translat│ │Adapters│    WHERE THE DATA IS  │  │
│  │  │        │ │        │ │(local) │                       │  │
│  │  └────────┘ └────────┘ └────────┘                      │  │
│  │                                                          │  │
│  │  PostgreSQL (M1)  │  Redis (M6)  │  WORM Storage (M10) │  │
│  │  MinIO (OPA bundles)                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│            │                                                    │
│            │  mTLS encrypted tunnel (WireGuard / AWS PrivateLink│
│            │  / Azure ExpressRoute / GCP Interconnect)          │
│            │                                                    │
│  ┌─────────▼────────────────────────────────────────────────┐  │
│  │  CLOUD (AWS / Azure / GCP) — compute layer only          │  │
│  │                                                          │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │  │
│  │  │ Strands      │  │ LangGraph    │  │ OpenClaw      │  │  │
│  │  │ Supervisor   │  │ Research     │  │ Channel GW    │  │  │
│  │  │ + Specialists│  │ Pipeline     │  │               │  │  │
│  │  └──────────────┘  └──────────────┘  └───────────────┘  │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐                      │  │
│  │  │ M3     │ │ M8     │ │ M9     │                      │  │
│  │  │Schema  │ │Pipeline│ │Intent  │                      │  │
│  │  └────────┘ └────────┘ └────────┘                      │  │
│  │                                                          │  │
│  │  LLM: Bedrock / Azure OpenAI / GCP Vertex AI            │  │
│  │  Langfuse (observability — cloud instance)               │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Principle:** Trust layer (M1, M2/M4, M6, M10) and data adapters (M11) run WHERE THE DATA LIVES — in the firm's network. Compute layer (M8, M9, M12) runs in cloud. No MNPI or PII crosses the network boundary in cleartext — all data is filtered by M4 before leaving the firm's network.

**Cost Estimate (Tier 2 AM):** $8,000–$25,000/month (cloud compute + firm provides on-prem infrastructure)
**Cost Estimate (Tier 5 HF):** $10,000–$40,000/month (higher compute for research pipeline)

### Topology 3: Full On-Premise — Tier 1 Target

```
┌─────────────────────────────────────────────────────────────────┐
│  FIRM'S DATA CENTER (air-gapped or restricted internet)         │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  KUBERNETES CLUSTER (bare-metal or VMware Tanzu)         │  │
│  │                                                          │  │
│  │  ALL 12 MODULES run on-premise                           │  │
│  │                                                          │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │  │
│  │  │ M1     │ │ M2/M4  │ │ M3     │ │ M5     │           │  │
│  │  │Identity│ │OPA     │ │Schema  │ │Config  │           │  │
│  │  │+Keyclk │ │        │ │        │ │        │           │  │
│  │  └────────┘ └────────┘ └────────┘ └────────┘           │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │  │
│  │  │ M6     │ │ M7     │ │ M8     │ │ M9     │           │  │
│  │  │MCP GW  │ │Translat│ │Pipeline│ │Intent  │           │  │
│  │  └────────┘ └────────┘ └────────┘ └────────┘           │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐                      │  │
│  │  │ M10    │ │ M11    │ │ M12    │                      │  │
│  │  │Audit   │ │Adapters│ │Runtime │                      │  │
│  │  │(WORM)  │ │        │ │Strands │                      │  │
│  │  └────────┘ └────────┘ └────────┘                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  SELF-HOSTED LLM                                         │  │
│  │  vLLM or TGI serving:                                    │  │
│  │    - Llama 3.1 405B (research, deep reasoning)           │  │
│  │    - Llama 3.1 70B (client service, fast responses)      │  │
│  │    - Mistral Large (alternative)                         │  │
│  │  GPU: 4-8x NVIDIA A100/H100 (research)                  │  │
│  │       2x NVIDIA A100 (client service)                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  DATA LAYER (all on-premise)                             │  │
│  │  PostgreSQL (M1, M3, M8 checkpoints)                     │  │
│  │  Redis (M6 cache, rate limits)                           │  │
│  │  MinIO (OPA bundles, schema storage)                     │  │
│  │  NetApp SnapLock / Dell EMC Centera (WORM — M10)         │  │
│  │  pgvector (semantic memory — vector search)              │  │
│  │  Langfuse (self-hosted, PostgreSQL-backed)               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  OBSERVABILITY (all on-premise)                          │  │
│  │  OpenTelemetry Collector → Prometheus → Grafana          │  │
│  │  ELK Stack (log aggregation)                             │  │
│  │  Alertmanager → PagerDuty (via approved egress)          │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Cost Estimate (Tier 1 Bank):** $50,000–$150,000/month (GPU infrastructure + engineering support)
**Note:** Tier 1 banks typically provide their own infrastructure; cost is primarily engineering/support.

---

## 4. LLM PROVIDER ABSTRACTION

The architecture abstracts the LLM provider behind a unified interface. No module directly imports a provider-specific SDK.

```python
# llm_provider.py — unified interface
class LLMProvider(Protocol):
    async def complete(self, messages: list[Message], tools: list[Tool] | None = None,
                       model: str = "default", temperature: float = 0.0,
                       max_tokens: int = 4096) -> CompletionResponse: ...
    async def embed(self, texts: list[str], model: str = "default") -> list[list[float]]: ...
```

| Provider | Completion Models | Embedding Models | Deployment |
|----------|------------------|-----------------|------------|
| **AWS Bedrock** (default) | Claude Sonnet (research), Claude Haiku (client svc) | Titan Embeddings v2 | Cloud (AWS) |
| **Azure OpenAI** | GPT-4o (research), GPT-4o-mini (client svc) | text-embedding-3-large | Cloud (Azure) |
| **GCP Vertex AI** | Gemini 1.5 Pro (research), Gemini 1.5 Flash (client svc) | text-embedding-004 | Cloud (GCP) |
| **Self-Hosted (vLLM/TGI)** | Llama 3.1 405B (research), Llama 3.1 70B (client svc) | BGE-large-en-v1.5 | On-premise |
| **LiteLLM** (proxy) | Any supported model via unified API | Any supported model | Any (proxy layer) |

**Selection Logic:** The enterprise config specifies the LLM provider. The `LLMProvider` interface is injected at startup. All modules use the interface, never the provider SDK directly.

```yaml
# enterprise-config.yaml
llm:
  provider: "bedrock"          # bedrock | azure_openai | vertex_ai | self_hosted | litellm
  research_model: "claude-sonnet-4-20250514"
  conversational_model: "claude-haiku-4-20250514"
  embedding_model: "amazon.titan-embed-text-v2"
  endpoint: null               # null = default; set for self-hosted or LiteLLM proxy
  region: "us-east-1"
```

---

## 5. DATABASE SELECTIONS

| Module | Database | Purpose | Cloud (AWS) | Hybrid/On-Prem |
|--------|----------|---------|-------------|----------------|
| M1 | PostgreSQL | Keycloak user store + AID registry | RDS PostgreSQL | Self-hosted PostgreSQL |
| M2/M4 | S3 / MinIO | OPA policy bundle storage | S3 | MinIO |
| M2/M4 | PostgreSQL | Policy version history, audit of rule changes | RDS PostgreSQL | Self-hosted PostgreSQL |
| M3 | Git + Redis | Schema definitions (Git) + cache (Redis) | CodeCommit + ElastiCache | Git + self-hosted Redis |
| M6 | Redis | Rate limit counters, circuit breaker state, response cache | ElastiCache Redis | Self-hosted Redis |
| M8 | DynamoDB / PostgreSQL | Pipeline checkpoint state, HITL gate state | DynamoDB | PostgreSQL |
| M10 | S3 Object Lock | WORM-compliant audit archive (6-year retention) | S3 Object Lock (Compliance mode) | NetApp SnapLock / Dell EMC Centera |
| M10 | PostgreSQL | Langfuse operational observability store | RDS PostgreSQL (Langfuse) | Self-hosted PostgreSQL |
| Memory L1 | Redis | Working memory (current conversation) | ElastiCache Redis | Self-hosted Redis |
| Memory L2 | DynamoDB / PostgreSQL | Short-term memory (recent interactions) | DynamoDB | PostgreSQL |
| Memory L3 | DynamoDB + Vector | Episodic memory (past interactions + outcomes) | DynamoDB + OpenSearch | PostgreSQL + pgvector |
| Memory L4 | pgvector / Pinecone | Semantic memory (learned client facts) | Pinecone / OpenSearch | pgvector |
| Memory L5 | File-based JSON | Procedural memory (MetaClaw learned workflows) | S3 | Local filesystem / NFS |
| Memory L6 | S3 Object Lock | Compliance memory (audit trail — same as M10 WORM) | S3 Object Lock | NetApp SnapLock |

---

## 6. SECRET MANAGEMENT STRATEGY

| Deployment | Primary | Fallback | Rotation |
|------------|---------|----------|----------|
| **Cloud (AWS)** | AWS Secrets Manager | HashiCorp Vault (if multi-cloud) | Automatic rotation via Secrets Manager (30-day cycle for API keys, 90-day for DB passwords) |
| **Hybrid** | HashiCorp Vault (on-prem master) | AWS Secrets Manager (cloud secrets) | Vault auto-rotation policies |
| **On-Premise** | HashiCorp Vault | CyberArk (if firm mandates) | Vault auto-rotation policies |
| **Azure** | Azure Key Vault | HashiCorp Vault | Key Vault auto-rotation |

**Secret Categories:**

| Category | Examples | Rotation Frequency | Storage |
|----------|---------|-------------------|---------|
| Vendor API Keys | Schwab, Orion, eMoney, Bloomberg | 90 days | Vault / Secrets Manager |
| Database Credentials | PostgreSQL, Redis, DynamoDB | 90 days (auto-rotated) | Vault / Secrets Manager |
| JWT Signing Keys | AID token signing (RS256) | 365 days (with key overlap period) | KMS / Vault |
| OPA Bundle Signing | Policy bundle integrity | 365 days | KMS / Vault |
| mTLS Certificates | Inter-module communication | 90 days (auto-renewed via cert-manager) | Vault / cert-manager |
| LLM API Keys | Bedrock (IAM role), Azure OpenAI, etc. | IAM role (no static key for AWS); 90 days for others | IAM / Vault |

**Access Pattern:** Modules reference secrets via `${VAULT:secret/007/m11/schwab/api_key}` in enterprise-config.yaml. The config loader (M5) resolves references at startup and on hot-reload. Secrets are NEVER logged, NEVER in environment variables in production (injected via Vault Agent sidecar or Secrets Manager SDK).

---

## 7. OBSERVABILITY STACK

| Component | Tool | Purpose | Cloud (AWS) | On-Prem |
|-----------|------|---------|-------------|---------|
| **Metrics** | Prometheus + Grafana | System metrics (latency, error rate, throughput per module) | Amazon Managed Prometheus + Managed Grafana | Self-hosted |
| **Tracing** | OpenTelemetry + Jaeger | Distributed tracing across all 12 modules (trace_id propagation) | AWS X-Ray or Jaeger on EKS | Self-hosted Jaeger |
| **Logging** | Structured JSON logs + aggregator | Application logs (NOT audit logs) | CloudWatch Logs or OpenSearch | ELK Stack (Elasticsearch + Logstash + Kibana) |
| **LLM Observability** | Langfuse (self-hosted) | LLM cost tracking, prompt debugging, latency monitoring, eval results | Langfuse on ECS/EKS | Langfuse self-hosted |
| **Alerting** | Alertmanager + PagerDuty | On-call alerting for module failures, SLA breaches | PagerDuty / OpsGenie | PagerDuty (via approved egress) |
| **Compliance Dashboard** | Custom Grafana dashboards | CCO-facing: compliance engine health, exception rates, HITL approval patterns, audit completeness | Managed Grafana | Self-hosted Grafana |

**SLA Targets:**

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| M6 (MCP Gateway) p99 latency | <500ms | >1s for 5 min |
| M2/M4 (OPA) policy evaluation | <10ms | >50ms for 5 min |
| M9 (Intent Router) classification | <2s | >5s for 5 min |
| M8 (Pipeline) full research run | <15 min | >20 min |
| M10 (Audit) write latency | <100ms | >500ms for 1 min |
| WORM write success rate | 100% | Any failure → P1 alert |
| Overall system availability | 99.9% | <99.5% over 1 hour |

---

## 8. INFRASTRUCTURE AS CODE

| Deployment | IaC Tool | Justification |
|------------|----------|---------------|
| **AWS** | AWS CDK (TypeScript) | Already in use (cdk.out folder exists). CDK provides type-safe infrastructure definition. |
| **Multi-Cloud / Hybrid** | Terraform | Industry standard for multi-cloud. HashiCorp BSL license is acceptable for internal use. |
| **Kubernetes** | Helm charts | Every module has a Helm chart. Values files per environment (dev/staging/prod) and per topology (cloud/hybrid/on-prem). |
| **CI/CD** | GitHub Actions | Pipeline: lint → test → build container → push to registry → deploy to staging → run eval suite → promote to prod. |
| **Container Registry** | ECR (AWS) / ACR (Azure) / Artifact Registry (GCP) / Harbor (on-prem) | Per-cloud registry. Harbor for on-prem private registry. |

**Deployment Strategy:** Blue-green deployment for all modules. Canary deployment for M6 (MCP Gateway) and M9 (Intent Router) — these are the highest-traffic, highest-risk modules. Rollback within 5 minutes if error rate exceeds 1%.

---

## 9. NETWORK SECURITY

| Control | Implementation |
|---------|---------------|
| **mTLS between modules** | cert-manager (Kubernetes) with auto-rotation. All inter-module communication encrypted and authenticated. |
| **Network policies** | Kubernetes NetworkPolicy. M11 adapters can only be reached by M6. M2/M4 can only be reached by M6 and M8. M1 is reachable by all modules. |
| **Ingress** | OpenClaw channel gateway is the only public-facing endpoint. All other modules are internal-only. |
| **Egress** | M11 adapters have egress to specific vendor API endpoints (allowlisted). No other module has internet egress. |
| **Data residency** | PII-processing modules (M1, M4, M6, M10, M11) run in the firm's jurisdiction. Non-PII modules (M3, M8, M9) can run in any region. |
| **Encryption at rest** | AES-256 for all databases. KMS-managed keys (cloud) or Vault-managed keys (on-prem). |

---

## 10. TECHNOLOGY DECISION SUMMARY TABLE

| Module | Language | Framework | Database | Deployment | Cloud Dep. | Agnostic Alt. |
|--------|----------|-----------|----------|------------|------------|---------------|
| M1 | Python | FastAPI + Keycloak | PostgreSQL | Container + sidecar | KMS | Vault |
| M2/M4 | Rego + Python | OPA + FastAPI | S3/MinIO + PostgreSQL | Container + sidecar | S3 | MinIO |
| M3 | Python | FastAPI + JSON Schema | Git + Redis | Container | None | Fully agnostic |
| M5 | Python | Pydantic + watchdog | N/A (library) | Library | None | Fully agnostic |
| M6 | Python | FastAPI + custom middleware | Redis | Container | None | Fully agnostic |
| M7 | Python | Pydantic | N/A (library) | Library | None | Fully agnostic |
| M8 | Python | LangGraph | DynamoDB / PostgreSQL | Container | DynamoDB | PostgreSQL |
| M9 | Python | LLM function calling | N/A | Container | Bedrock | LLM abstraction |
| M10 | Python | FastAPI | S3 Object Lock + PostgreSQL | Container | S3 Object Lock | SnapLock/Centera |
| M11 | TypeScript | MCP SDK | N/A | Container / Serverless | None | Fully agnostic |
| M12 | Python | Strands SDK + OpenClaw | N/A | AgentCore / K8s | AgentCore | Kubernetes |

**Cloud-agnostic modules (zero cloud dependency):** M3, M5, M6, M7, M11 — 5 of 12 modules
**Abstractable cloud dependency:** M1, M2/M4, M8, M9, M10, M12 — 6 of 12 modules (swap via config)
**AWS-specific managed service (optional):** AgentCore for M12 — replaceable with Kubernetes

---

*Document 1 of 3 — Project 007 v2 Architecture*
*Addressing LLMJ Committee Action #3: Detailed Tech Stack Decision Document*