# Project 007: Definitive Tech Stack

> The complete, plain-language answer to "what is the tech stack?"

---

## Languages

| Language | Where Used | Modules |
|----------|-----------|---------|
| Python 3.12+ | 11 of 13 modules + all compliance gaps | M1-M10, M13, compliance |
| TypeScript/Node | MCP adapters (REST vendor API wrappers) | M11-REST |
| Rego | OPA policy rules (all compliance) | M2/M4, all OPA bundles |
| YAML | Config, schemas, pipeline definitions | M5, enterprise config |
| JSON Schema | Canonical data type definitions | M3 |

Two programming languages + one policy language. M11 is polyglot: TypeScript for REST adapters, Python for BLPAPI (Bloomberg) and gRPC (Eze). See M11 sub-types below.

---

## Stack Per Module

| Module | Language | Framework / Key Tech |
|--------|----------|---------------------|
| M1 Identity | Python | FastAPI + Keycloak |
| M2/M4 Policy Engine | Rego + Python | OPA (Open Policy Agent) + FastAPI |
| M3 Schema Registry | Python | FastAPI + JSON Schema |
| M5 Config Loader | Python | Pydantic v2 |
| M6 MCP Gateway | Python | FastAPI (custom middleware) |
| M7 Schema Translators | Python | Pydantic v2 |
| M8 Pipeline Engine | Python | LangGraph |
| M9 Intent Router | Python | LLM function calling |
| M10 Audit Logger | Python | FastAPI + Langfuse |
| M11-REST Adapters | TypeScript | MCP SDK (@modelcontextprotocol) |
| M11-BLPAPI Adapter | Python | blpapi SDK + MCP wrapper (Bloomberg) |
| M11-gRPC Adapter | Python | grpcio + MCP wrapper (SS&C Eze) |
| M11-SFTP Ingestion | Python | paramiko + batch parser (Schwab/Fidelity daily files) |
| M12 Agent Runtime | Python | Claude Managed Agents (cloud) / Strands SDK (hybrid/on-prem) |
| M13 FIX Bridge | Python | QuickFIX + MCP wrapper (stateful TCP sessions) |

---

## LLM — Abstracted, Not Locked

| Provider | Models | When |
|----------|--------|------|
| AWS Bedrock (default) | Claude Sonnet (research), Claude Haiku (conversational) | Cloud deployments |
| Azure OpenAI (alternative) | GPT-4o / GPT-4o-mini | Azure-first firms |
| GCP Vertex AI (alternative) | Gemini 1.5 Pro / Flash | GCP-first firms |
| Self-hosted (on-premise) | Llama 3.1 405B / 70B via vLLM or TGI | Air-gapped / Tier 1 |
| LiteLLM (proxy) | Any model via unified proxy | Multi-provider |

Which model for which specialist:

| Specialist | Model | Why |
|-----------|-------|-----|
| Supervisor | Haiku | Fast routing, less than 500ms |
| Research | Sonnet | Deep reasoning, large context |
| Client Service | Haiku | Conversational, less than 3s |
| Compliance | NO LLM | Deterministic OPA |
| Execution | Haiku | Order preparation |
| Onboarding | Haiku | Form filling |

---

## Agent Runtime

| Component | Tech | Role | Topology |
|-----------|------|------|----------|
| Claude Managed Agents | Anthropic cloud (public beta) | Supervisor + 5 specialists (cloud default) | Cloud (Tier 3/4) |
| Strands Agents SDK | Apache 2.0, AWS | Supervisor + 5 specialists (self-hosted) | Hybrid/On-prem (Tier 1/2/5) |
| OpenClaw | MIT | Channel gateway only (12+ channels) | All topologies |
| LangGraph | MIT, LangChain | Research pipeline (23-stage, checkpointed, HITL) | All topologies |

Claude Managed Agents is the default runtime for cloud deployments (Tier 3/4). It provides sandboxed execution, long-running sessions, multi-agent coordination, credential management, and session tracing — eliminating weeks of orchestration infrastructure work. Strands SDK remains the runtime for hybrid and on-prem topologies where cloud dependency is not acceptable. The application code (M1-M11, M13, all compliance) is identical regardless of runtime. The runtime is a Helm values toggle, not a code change.

What Managed Agents provides (no longer need to build): sandboxed execution, long-running sessions (research pipeline can run hours), multi-agent coordination (supervisor + specialists native), checkpointing, credential management, error recovery, session tracing.

What 007 still builds regardless of runtime: M1-M10 trust layer, M11 vendor adapters, M13 FIX Bridge, 7 compliance gaps, canonical schema, enterprise config, principal review queue, WORM audit (Managed Agents tracing is operational, not SEC 17a-4 compliant).

Strands handles self-hosted orchestration. Managed Agents handles cloud orchestration. OpenClaw handles channels. LangGraph handles the research pipeline.

---

## Databases

| What | Cloud (AWS) | On-Prem |
|------|-------------|---------|
| User store (M1) | RDS PostgreSQL | PostgreSQL |
| Policy bundles (M2/M4) | S3 | MinIO |
| Schema cache (M3) | ElastiCache Redis | Redis |
| Rate limits (M6) | ElastiCache Redis | Redis |
| Pipeline state (M8) | DynamoDB | PostgreSQL |
| HITL gate state | DynamoDB | PostgreSQL |
| Working memory (L1) | ElastiCache Redis | Redis |
| Short-term memory (L2) | DynamoDB | PostgreSQL |
| Episodic memory (L3) | DynamoDB + vector | PostgreSQL + pgvector |
| Semantic memory (L4) | Pinecone | pgvector |
| WORM audit (M10) | S3 Object Lock | NetApp SnapLock |
| LLM observability | Langfuse (PostgreSQL) | Langfuse (PostgreSQL) |

---

## Infrastructure

| Layer | Tech |
|-------|------|
| Containers | Docker (every module is a container) |
| Orchestration | Kubernetes (EKS on AWS, bare-metal on-prem) |
| IaC | Terraform (multi-cloud) + AWS CDK (AWS-specific) |
| Helm | One chart per module |
| CI/CD | GitHub Actions |
| Registry | ECR (AWS) / Harbor (on-prem) |
| Secrets | HashiCorp Vault (primary) / AWS Secrets Manager |
| mTLS | cert-manager (auto-rotation between modules) |
| Monitoring | Prometheus + Grafana |
| Tracing | OpenTelemetry + Jaeger |
| Logging | Structured JSON to CloudWatch (cloud) / ELK (on-prem) |
| Alerting | Alertmanager + PagerDuty |

---

## Protocols

| Communication | Protocol |
|--------------|----------|
| Agent to Tool | MCP (Model Context Protocol) |
| Agent to Agent | A2A (future, Phase 4+) |
| Agent to OMS | FIX 4.2/4.4 via MCP bridge (Phase 4) |
| Agent to Bank | SWIFT/ISO 20022 via MCP bridge (Phase 5) |
| Agent to CRM | REST via MCP adapter |
| Module to Module | REST (FastAPI) over mTLS |
| Auth | OAuth 2.0 / OpenID Connect (Keycloak) |
| Policy eval | OPA REST API (localhost sidecar) |

---

## 3 Deployment Topologies

### Topology 1: Full Cloud (Tier 3/4)

For wealth management firms and independent RIAs.

AWS: Claude Managed Agents (runtime), EKS (M1-M11 trust + adapters), RDS, ElastiCache, DynamoDB, S3 Object Lock. LLM: Claude via Managed Agents. Cost: $800-$8,000/month per tenant + $0.08/session-hour for Managed Agents runtime.

### Topology 2: Hybrid (Tier 2/5)

For asset managers and hedge funds. Trust layer stays with the data.

Firm network: M1, M2/M4, M6, M10, M11 on on-prem Kubernetes. Cloud: Strands + LangGraph on AgentCore, M3/M5/M8/M9 on EKS. mTLS tunnel between. Cost: $8,000-$40,000/month.

### Topology 3: Full On-Premise (Tier 1)

For investment banks. Everything in the firm's data center.

All 12 modules on bare-metal Kubernetes. Self-hosted LLM: vLLM serving Llama 3.1 405B + 70B. 4-8x NVIDIA A100/H100 GPUs. Cost: $50,000-$150,000/month.

---

## What Is NOT in the Stack

| Excluded | Why |
|----------|-----|
| Salesforce Agentforce | Not the agent runtime (Managed Agents / Strands is) |
| Amazon Comprehend | LLM handles sentiment |
| FinBERT | LLM handles sentiment |
| Envoy proxy | FastAPI middleware is simpler for the team |
| Custom policy engine | OPA/Rego is battle-tested, CNCF graduated |
| Custom pipeline engine | LangGraph has checkpointing and HITL native |
| Kafka | Not needed until Tier 1/5 (Phase 4+) |
| Airflow/Prefect | LangGraph replaces for agent pipelines |

---

## One-Line Summary

Python + TypeScript + Rego. FastAPI + OPA + LangGraph + Claude Managed Agents (cloud) / Strands (hybrid) + MCP. PostgreSQL + Redis + DynamoDB + S3 Object Lock. Kubernetes + Terraform + GitHub Actions. Claude (swappable). 3 topologies. 13 modules.
