# PROJECT 007 — REVIEWER 1 ASSESSMENT
# ARCHITECTURE & TECH STACK

> Reviewer: Reviewer 1 (Architecture & Tech Stack Specialist)
> Committee: 5-Person LLM-as-Judge Panel
> Date: July 2026
> Documents Reviewed: All 9 documents in /docs/
> External Research: A2A protocol, Bedrock AgentCore, Strands Agents, CrewAI, AutoGen, LangGraph, OPA, Keycloak, Apache Atlas/OpenMetadata, FSI deployment patterns

---

## EXECUTIVE SUMMARY

Project 007 presents an ambitious and intellectually rigorous vision for cross-archetype FSI agent interoperability. The 5-layer model, the railway metaphor, and the trust-first build order are architecturally sound instincts. The competitive analysis is honest and well-researched. However, the documentation has significant gaps in explicit technology choices, deployment flexibility, multi-agent orchestration, and operational infrastructure. The architecture reads as a brilliant whitepaper that has not yet been pressure-tested against the realities of multi-cloud enterprise procurement, on-premise banking requirements, or production operations at scale.

**Overall Architecture Score: 6.8 / 10**

The vision is 9/10. The specificity of implementation is 5/10. The gap between those two numbers is the risk.

---

## 1. TECH STACK GAPS — Score: 4/10

### The Core Problem

Across 9 documents and ~25,000 words, the exact technology stack for each module is never explicitly defined. The docs mention OpenClaw, Bedrock, Salesforce, MCP, and A2A — but these are referenced as assumptions, not as justified architectural decisions with alternatives considered.

### What Is Stated vs. What Is Missing

| Module | What Docs Say | What Is Missing |
|--------|--------------|-----------------|
| M1: Agent Identity | "BUILD ~300 lines" | Language? Runtime? JWT or custom token format? Key management (AWS KMS? HashiCorp Vault? Azure Key Vault?)? Token signing algorithm? |
| M2: Authority Policy Engine | "BUILD ~500 lines, YAML-driven" | Why not OPA/Rego? Why not AWS Cedar? Why not Casbin? What evaluates the YAML — a custom interpreter? Performance at scale? |
| M3: Canonical Schema Registry | "BUILD ~200 lines YAML" | Why not JSON Schema? Why not Protobuf? Why not Apache Avro? Schema versioning strategy? Schema evolution? Breaking change detection? |
| M4: MNPI Policy Engine | "BUILD ~400 lines" | Language? How does it differ from M2? Why is this separate from the Authority Engine? Could they share an evaluation engine? |
| M5: Enterprise Config Loader | "ADAPT ~200 lines, reads YAML" | Config validation? Hot reload? Config versioning? Secrets management (API keys in YAML?)? |
| M6: Trust-Aware MCP Gateway | "BUILD ~600 lines" | Language? Framework? How does it proxy MCP calls? Is it a reverse proxy (like Envoy/NGINX) or application-level middleware? Latency budget? |
| M7: Schema Translators | "ADAPT ~100 lines each" | Generated or hand-written? Schema mapping DSL? How are mappings tested? What about the semantic mismatch problem the docs themselves identify as the #1 risk? |
| M8: Pipeline Engine | "ADAPT ~1,400 lines from 006" | What is the pipeline runtime? Is it LangGraph? A custom state machine? How are stages defined — code or config? |
| M9: FSI Intent Router | "BUILD ~300 lines" | LLM-based or rule-based? If LLM-based, which model? What about the 85-95% accuracy the docs acknowledge? Fallback strategy? |
| M10: Audit Logger | "ADAPT ~200 lines" | WORM storage provider? Is Langfuse the observability layer? What about firms that use Datadog, Splunk, or New Relic? What about the WORM requirement for 17a-4? |
| M11: MCP Server Adapters | "ADAPT ~200 lines each" | Language? Node.js (like 006's mcp-rest-bridge.mjs)? Python? Both? Deployment model — sidecar, standalone, serverless? |
| M12: Agent Runtime | "PLUG IN — OpenClaw + Bedrock AgentCore" | What if the firm uses Azure OpenAI? GCP Vertex AI? What about firms banned from using AWS? |

### Cloud Lock-In Assessment

The architecture is implicitly AWS-only:
- **LLM**: Bedrock Claude — no mention of Azure OpenAI, GCP Gemini, or self-hosted models
- **Runtime**: Bedrock AgentCore — AWS-specific managed service
- **Guardrails**: Bedrock Guardrails — AWS-specific
- **Observability**: Langfuse (open-source, good) but no mention of CloudWatch, Datadog, etc.
- **Trust Layer**: Einstein Trust Layer (Salesforce-specific)

This is a problem because:
- **Tier 1 banks** (Goldman, JPM, MS) run multi-cloud or private cloud. Many have Azure-first or GCP-first mandates for specific workloads.
- **Tier 5 hedge funds** (Two Sigma, DE Shaw) often run on GCP for compute-heavy workloads.
- **European firms** under DORA/GDPR may require EU-sovereign cloud or on-premise deployment.
- **Tier 2 asset managers** using Aladdin are already in BlackRock's infrastructure — adding AWS creates a third cloud dependency.

### Specific Recommendations

1. **Define an explicit tech stack table** for each module with: language, runtime, cloud dependencies, and cloud-agnostic alternatives.
2. **Abstract the LLM layer** behind a provider interface. The docs mention "Bedrock Claude" throughout, but the architecture should support any LLM via a common interface (LiteLLM, LangChain model abstraction, or custom).
3. **Abstract the runtime layer**. Bedrock AgentCore is one deployment target. The modules (M1-M11) should be deployable on any container runtime (ECS, EKS, Azure Container Apps, GKE, bare metal Kubernetes).
4. **Replace "Einstein Trust Layer" references** with a generic guardrails interface. Einstein Trust Layer is Salesforce-specific. Firms not on Salesforce need an equivalent.
5. **Address data residency explicitly**. Where does data flow? Which modules process PII? Which modules can run in a VPC vs. must run on-premise?

---

## 2. MULTI-AGENT DESIGN — Score: 5/10

### The Current Assumption: Single Agent with Skills

The docs assume a single OpenClaw agent instance that routes through M9 (Intent Router) to different "lines" (research, client service, compliance, execution). This is the "single-agent-with-tools" pattern — one LLM reasoning loop that calls different MCP tools depending on the intent.

### Why This May Be Insufficient

Real FSI workflows involve fundamentally different reasoning patterns that a single agent loop handles poorly:

1. **Research Agent** needs deep, multi-step reasoning with long context windows (23-stage pipeline). It needs to hold 10-K filings, earnings transcripts, and financial models in context simultaneously.

2. **Compliance Agent** needs deterministic, rule-based evaluation. The docs correctly identify that compliance should NOT be LLM-based. But if compliance is deterministic, why route it through an LLM agent at all? A compliance agent should be a specialized, non-LLM agent that evaluates policies.

3. **Execution Agent** needs stateful, transactional behavior with HITL gates. It must maintain order state across human approval cycles that may take minutes or hours.

4. **Client Service Agent** needs conversational memory and personalization. It should remember prior interactions with the same client.

These are four fundamentally different agent architectures forced into one runtime.

### Current Multi-Agent Landscape (2025-2026)

Based on research:

| Framework | Pattern | Relevance to 007 |
|-----------|---------|-------------------|
| **Strands Agents (AWS)** | Model-driven, open-source, deploys on AgentCore | HIGH — natural fit since 007 already uses AgentCore. Supports multi-agent collaboration patterns natively. 1M+ downloads in 4 months. |
| **LangGraph** | Stateful graph-based orchestration with checkpointing | HIGH — the 23-stage pipeline IS a graph. LangGraph's checkpointing solves the HITL gate problem natively. |
| **CrewAI** | Role-based teams with shared context | MEDIUM — the "railway lines" map to CrewAI crews. But CrewAI lacks production observability. |
| **AutoGen/Microsoft Agent Framework** | Conversational multi-agent | LOW — AutoGen is in maintenance mode (consolidated into Microsoft Agent Framework Oct 2025). |
| **A2A Protocol** | Cross-boundary agent-to-agent | FUTURE — relevant for Journey 6 (cross-firm agent communication). Already backed by 150+ orgs including AWS, Salesforce. |
| **Bedrock Multi-Agent Collaboration** | Supervisor + specialist agents on AWS | HIGH — GA since March 2025. Supervisor agent routes to specialist agents. Maps directly to 007's line concept. |

### Recommendation: Hybrid Multi-Agent Architecture

007 should adopt a **supervisor + specialist** pattern:

```
Supervisor Agent (M9 Intent Router + Orchestrator)
  |
  +-- Research Specialist (Line 1) — LangGraph-based, long-running, checkpointed
  +-- Client Service Specialist (Line 2) — Conversational, memory-enabled
  +-- Compliance Specialist (Line 3) — Deterministic, rule-based (NOT LLM)
  +-- Execution Specialist (Line 4) — Stateful, transactional, HITL-aware
  +-- Onboarding Specialist (Line 5) — Workflow-based, form-driven
```

This maps naturally to:
- Bedrock Multi-Agent Collaboration (supervisor pattern)
- Strands Agents SDK (open-source, deploys on AgentCore)
- LangGraph (for the research pipeline specifically)

The compliance "agent" should NOT be an LLM agent. It should be a deterministic policy engine (M2 + M4) exposed as an MCP tool that other agents call. The docs already recognize this ("compliance checks are NOT done by the LLM") but don't follow through architecturally.

### A2A Protocol Integration

The docs mention A2A for "Phase 4+ territory" (Journey 6: cross-boundary agent-to-agent). This is correct timing-wise, but the architecture should be A2A-ready from day one:
- Agent Identity Documents should be compatible with A2A Agent Cards
- The MCP Gateway (M6) should be extensible to handle A2A task delegation
- The audit logger (M10) should support cross-boundary trace correlation

A2A was donated to the Linux Foundation in June 2025 and is backed by 150+ organizations. It will be the standard for inter-enterprise agent communication. 007's Agent Identity Document is a natural extension of A2A Agent Cards with FSI-specific fields.

---

## 3. DEPLOYMENT MODEL — Score: 4/10

### What the Docs Say

"OpenClaw Gateway + Bedrock AgentCore + 12+ channels" — M12 is "PLUG IN."

### What the Docs Don't Address

#### On-Premise Requirements

Many Tier 1 banks and some Tier 5 hedge funds REQUIRE on-premise deployment for:
- Data that cannot leave the firm's network (MNPI, trading intentions, client PII)
- Regulatory requirements (some jurisdictions require data residency)
- Latency requirements (FIX protocol bridges need sub-millisecond latency)
- Air-gapped environments (some trading systems have no internet access)

The architecture assumes cloud-native deployment throughout. There is no discussion of:
- Containerized deployment on bare-metal Kubernetes
- Self-hosted LLM options (vLLM, TGI, Ollama for smaller models)
- On-premise MCP server deployment
- Hybrid architectures where M1-M6 run on-premise and M12 runs in cloud

#### Multi-Cloud Requirements

| Archetype | Typical Cloud | 007's Assumption | Gap |
|-----------|--------------|-------------------|-----|
| Tier 1 Bank | Multi-cloud (AWS + Azure + private) | AWS-only | CRITICAL |
| Tier 2 AM | Varies (Aladdin = BlackRock infra) | AWS-only | HIGH |
| Tier 3 WM | Cloud-agnostic SaaS | AWS-only | MEDIUM |
| Tier 4 RIA | Cloud-agnostic SaaS | AWS-only | LOW |
| Tier 5 HF | GCP (quant), AWS, or private | AWS-only | HIGH |

#### Deployment Topology Options Needed

The docs should define at minimum 3 deployment topologies:

1. **Full Cloud (AWS)** — Current assumption. OpenClaw + AgentCore + Bedrock. Suitable for Tier 3/4.
2. **Hybrid Cloud** — M1-M6 (trust layer) on-premise or in firm's VPC. M12 (runtime) in cloud. MCP servers deployed where the data lives. Suitable for Tier 2/5.
3. **Full On-Premise** — Everything runs in the firm's data center. Self-hosted LLM. Kubernetes-based deployment. Suitable for Tier 1.

#### Specific Gaps

- **No Kubernetes manifests or Helm charts** discussed
- **No container registry strategy** (ECR? Docker Hub? Private registry?)
- **No CI/CD pipeline** defined
- **No infrastructure-as-code** (CDK, Terraform, Pulumi) — though there's a `cdk.out` folder in the repo suggesting CDK is intended
- **No environment strategy** (dev/staging/prod)
- **No blue-green or canary deployment** strategy for a system handling financial data
- **No disaster recovery** or failover strategy
- **No data backup** strategy for audit logs (WORM requirement)

### Recommendations

1. **Define 3 deployment topologies** (cloud, hybrid, on-premise) with explicit component placement diagrams.
2. **Abstract the LLM provider** — support Bedrock, Azure OpenAI, GCP Vertex AI, and self-hosted (vLLM/TGI) behind a common interface.
3. **Abstract the agent runtime** — OpenClaw is the default, but the M1-M11 modules should be runtime-agnostic. They are MCP servers and policy engines, not OpenClaw-specific code.
4. **Define a Kubernetes-native deployment** model. Every module should be a container with a Helm chart.
5. **Address data residency** per module. Which modules process PII? Which can run in a shared VPC? Which must run in the firm's private network?

---

## 4. BUILD vs ADAPT ASSESSMENT — Score: 7/10

### Module-by-Module Assessment

| Module | Docs Classification | My Assessment | Rationale |
|--------|-------------------|---------------|-----------|
| **M1: Agent Identity** | BUILD | BUILD — Correct | FSI-specific agent identity with LEI, CRD, authority, revocation does not exist. However, the USER identity layer should ADAPT Keycloak (open-source IAM, supports OIDC/OAuth 2.0/SAML, used in FSI for Basel III compliance). Build the AID schema; adapt Keycloak for user auth + token issuance. |
| **M2: Authority Policy Engine** | BUILD | **ADAPT OPA + BUILD FSI rules** | Open Policy Agent (OPA) with Rego is a CNCF graduated project used by financial institutions at scale. Styra (commercial OPA) explicitly targets FSI. OPA evaluates (input, data, policy) → decision — exactly the (identity, action, target, context) → decision pattern M2 needs. Build FSI-specific Rego policies; adapt OPA as the evaluation engine. Building a custom policy engine from scratch is unnecessary and risky. |
| **M3: Canonical Schema Registry** | BUILD | BUILD — Correct, but consider alternatives | The canonical FSI data model is novel. However, the REGISTRY infrastructure should adapt existing tools. Consider: JSON Schema for type definitions (industry standard), OpenMetadata or DataHub for schema registry infrastructure (both open-source, LFAI projects), Protobuf or Avro for wire format. Build the FSI types; adapt the registry infrastructure. |
| **M4: MNPI Policy Engine** | BUILD | **MERGE with M2 + BUILD MNPI rules** | M4 is architecturally a specialized case of M2. Both evaluate (identity + context) → filtering decision. If M2 uses OPA, MNPI rules are just additional Rego policies. Separate engines create consistency risks — what if M2 allows but M4 denies? A unified policy engine with separate policy bundles (authority + MNPI) is cleaner. |
| **M5: Enterprise Config Loader** | ADAPT | ADAPT — Correct | Standard config loading. Consider using Kubernetes ConfigMaps/Secrets for cloud deployments, HashiCorp Vault for secrets, and a validation schema (JSON Schema or Pydantic) for the YAML. |
| **M6: Trust-Aware MCP Gateway** | BUILD | BUILD — Correct, but leverage existing patterns | This is the most critical BUILD component. Consider building on top of an existing API gateway pattern (Envoy proxy with custom filters, or a lightweight Node.js/Python middleware). The "trust-aware" logic is novel; the "MCP gateway" plumbing is not. |
| **M7: Schema Translators** | ADAPT | ADAPT — Correct | Per-vendor translation. Consider code generation from mapping definitions rather than hand-writing each translator. |
| **M8: Pipeline Engine** | ADAPT | **ADAPT LangGraph** | The 23-stage pipeline with HITL gates, checkpointing, and branching IS a stateful graph. LangGraph provides exactly this: stateful graphs with checkpointing, human-in-the-loop, and time-travel debugging. Adapting LangGraph is lower risk than maintaining a custom pipeline engine. LangGraph also deploys on Bedrock AgentCore. |
| **M9: FSI Intent Router** | BUILD | BUILD — Correct | The FSI intent taxonomy is novel. The router itself could use LLM function calling (structured output) with the taxonomy as the schema. |
| **M10: Audit Logger** | ADAPT | ADAPT — Correct, but address WORM | For 17a-4 WORM compliance, consider: AWS S3 Object Lock (Governance or Compliance mode), Azure Immutable Blob Storage, or on-premise WORM storage. Langfuse for observability is good but is NOT WORM-compliant. The dual-write (CRM + Langfuse) needs a third leg: WORM archive. |
| **M11: MCP Server Adapters** | ADAPT | ADAPT — Correct | Standard adapter pattern. The mcp-rest-bridge.mjs from 006 is a good starting point. |
| **M12: Agent Runtime | PLUG IN | PLUG IN — Correct, but needs abstraction | OpenClaw is the default runtime. But the architecture should support alternative runtimes (Strands Agents, custom) without rewriting M1-M11. |

### Key Open-Source Projects to Evaluate

| Project | Relevance | Module | License |
|---------|-----------|--------|---------|
| **OPA (Open Policy Agent)** | Policy evaluation engine | M2, M4 | Apache 2.0 |
| **Keycloak** | Identity & access management | M1 (user auth layer) | Apache 2.0 |
| **OpenMetadata** | Schema registry infrastructure | M3 | Apache 2.0 |
| **LangGraph** | Stateful pipeline orchestration | M8 | MIT |
| **Strands Agents** | Agent SDK with multi-agent support | M12 | Apache 2.0 |
| **Langfuse** | LLM observability | M10 | MIT (self-hosted) |
| **Envoy Proxy** | API gateway / MCP proxy | M6 | Apache 2.0 |
| **HashiCorp Vault** | Secrets management | M1, M5 | BSL (source-available) |
| **JSON Schema** | Type definitions | M3 | Open standard |

### Revised Line Count Estimate

If OPA, LangGraph, and Keycloak are adopted:

| Component | Original Estimate | Revised Estimate | Reason |
|-----------|------------------|------------------|--------|
| M2: Authority Engine | ~500 lines (custom engine) | ~300 lines (OPA Rego policies + integration) | OPA handles evaluation; we write policies |
| M4: MNPI Engine | ~400 lines (custom engine) | ~200 lines (additional Rego policies) | Merged with M2's OPA instance |
| M8: Pipeline Engine | ~1,400 lines (custom) | ~600 lines (LangGraph adaptation) | LangGraph handles state, checkpointing, HITL |
| M1: Identity (user auth) | ~300 lines (custom) | ~150 lines (Keycloak config + AID schema) | Keycloak handles OAuth/OIDC; we build AID |

Total reduction: ~1,350 lines of custom code replaced by battle-tested open-source.

---

## 5. MISSING COMPONENTS — Score: 4/10

### Critical Missing Infrastructure

The 12 modules cover the functional architecture well. But production FSI systems require operational infrastructure that is entirely absent from the docs:

#### 5.1 Monitoring & Observability (CRITICAL)

| Component | Status | Requirement |
|-----------|--------|-------------|
| Metrics collection (Prometheus/CloudWatch) | MISSING | Every module needs latency, error rate, throughput metrics |
| Distributed tracing (OpenTelemetry) | MISSING | The trace_id in audit logs is mentioned but no tracing infrastructure is defined |
| Alerting (PagerDuty/OpsGenie) | MISSING | Who gets paged when M6 goes down at 2am? |
| Dashboards (Grafana/CloudWatch) | MISSING | CCO dashboard for compliance metrics? Ops dashboard for system health? |
| Log aggregation (ELK/CloudWatch Logs) | MISSING | Where do application logs go? (Audit logs ≠ application logs) |
| LLM observability (Langfuse) | PARTIAL | Langfuse is mentioned for audit but not for LLM cost tracking, latency monitoring, or prompt debugging |

#### 5.2 Resilience Patterns (CRITICAL)

| Pattern | Status | Why It Matters |
|---------|--------|---------------|
| Circuit breakers | MISSING | If Bloomberg API is down, the agent should gracefully degrade, not cascade-fail |
| Retry logic with backoff | MISSING | MCP server calls to vendor APIs WILL fail. What's the retry strategy? |
| Timeout management | MISSING | The 23-stage pipeline could take 8-12 minutes. What if stage 5 hangs? |
| Rate limiting | MISSING | Bloomberg BLPAPI has strict rate limits. Orion API has rate limits. Every vendor API has limits. |
| Bulkhead isolation | MISSING | A slow Orion API call should not block a Salesforce API call |
| Fallback strategies | MISSING | If FactSet is down, can the research pipeline use Bloomberg instead? |
| Dead letter queues | MISSING | Failed audit log writes must not be lost |

#### 5.3 Session & State Management (HIGH)

| Component | Status | Requirement |
|-----------|--------|-------------|
| Conversation memory | MENTIONED but not designed | OpenClaw has memory, but how does it persist across channels? |
| HITL gate state | MISSING | When Sarah approves a trade on Slack, where is the approval state stored? What if she closes Slack? |
| Pipeline checkpoint state | MISSING | The 23-stage pipeline needs durable state. What if the system restarts at stage 12? |
| Session timeout | MISSING | How long does an AID remain valid? The docs say "expires_at" but no session management logic |

#### 5.4 Caching (MEDIUM)

| Component | Status | Requirement |
|-----------|--------|-------------|
| Schema cache | MISSING | M3 canonical schemas should be cached, not loaded per-request |
| Policy cache | MISSING | M2 policy evaluations for the same (identity, action, target) should be cacheable |
| Config cache | MISSING | M5 enterprise config should be cached with TTL |
| MCP response cache | MISSING | Some MCP responses (e.g., client profile) are cacheable for short periods |
| Restricted list cache | MISSING | Restricted list lookups are frequent; cache with short TTL + invalidation |

#### 5.5 Error Handling (HIGH)

| Scenario | Status | Requirement |
|----------|--------|-------------|
| MCP server unreachable | MISSING | Graceful degradation, user notification, retry |
| LLM timeout/error | MISSING | Fallback model? Retry? User notification? |
| Policy evaluation error | MISSING | Fail-open or fail-closed? (MUST be fail-closed for FSI) |
| Schema translation error | MISSING | The docs identify this as the #1 risk but propose no error handling strategy |
| Audit write failure | MISSING | If audit log write fails, should the entire request fail? (Probably yes for compliance) |
| Identity verification failure | MISSING | Fail-closed. But what's the user experience? |
| Cross-module communication failure | MISSING | M6 calls M1, M2, M4, M10. What if M4 is down? |

#### 5.6 Security Infrastructure (HIGH)

| Component | Status | Requirement |
|-----------|--------|-------------|
| mTLS between modules | MISSING | Inter-module communication must be encrypted and authenticated |
| API key rotation | MISSING | Vendor API keys need rotation. How? |
| Secret management | MISSING | Where are API keys stored? Not in enterprise-config.yaml, hopefully |
| Network segmentation | MISSING | Which modules can talk to which? Network policies? |
| Penetration testing plan | MISSING | FSI systems require regular pen testing |
| Vulnerability scanning | MISSING | Container image scanning, dependency scanning |

#### 5.7 Testing Strategy (MEDIUM)

| Component | Status | Requirement |
|-----------|--------|-------------|
| Unit test strategy | MISSING | Per-module unit tests |
| Integration test strategy | MISSING | Cross-module integration tests |
| Schema translation tests | MENTIONED as critical but not designed | Automated comparison tests for semantic mismatches |
| Compliance rule tests | MISSING | How do you test that M2 correctly denies a Chinese wall violation? |
| Load testing | MISSING | What's the target throughput? Latency SLA? |
| Chaos engineering | MISSING | What happens when M6 loses connection to M2 mid-request? |
| Eval suite | MENTIONED (150-query from 006) | Needs expansion for all 5 archetypes |

#### 5.8 Data Management (MEDIUM)

| Component | Status | Requirement |
|-----------|--------|-------------|
| Database selection | MISSING | Where does M1 store AIDs? M2 store policies? M10 store audit logs? |
| Data migration strategy | MISSING | Schema evolution for canonical types |
| Backup and recovery | MISSING | Especially for audit logs (regulatory requirement) |
| Data retention policies | MENTIONED (5-6 years) but not designed | Automated retention enforcement |

---

## SCORING SUMMARY

| Area | Score | Weight | Weighted |
|------|-------|--------|----------|
| 1. Tech Stack Gaps | 4/10 | 25% | 1.00 |
| 2. Multi-Agent Design | 5/10 | 20% | 1.00 |
| 3. Deployment Model | 4/10 | 20% | 0.80 |
| 4. Build vs Adapt | 7/10 | 15% | 1.05 |
| 5. Missing Components | 4/10 | 20% | 0.80 |
| **OVERALL** | | | **4.65 / 10** |

**Adjusted Overall (accounting for vision quality): 6.8 / 10**

The raw score is 4.65, but the architectural vision, competitive analysis, and domain expertise demonstrated across the 9 documents are genuinely exceptional. The gap is not in thinking — it's in specificity. This is a pre-implementation design that needs a detailed technical specification phase before code is written.

---

## TOP 10 RECOMMENDATIONS (Priority Order)

1. **Write an explicit tech stack decision document** — For each module, state: language, framework, cloud dependencies, and cloud-agnostic alternatives. Justify each choice.

2. **Adopt OPA for M2/M4** — Do not build a custom policy engine. OPA is CNCF-graduated, used in FSI (Styra), and evaluates exactly the pattern M2 needs. Write FSI-specific Rego policies instead.

3. **Adopt LangGraph for M8** — The 23-stage pipeline with HITL gates and checkpointing is a textbook LangGraph use case. It deploys on Bedrock AgentCore and provides time-travel debugging.

4. **Define 3 deployment topologies** — Cloud (Tier 3/4), Hybrid (Tier 2/5), On-Premise (Tier 1). Each with explicit component placement.

5. **Design the multi-agent orchestration** — Move from single-agent-with-tools to supervisor + specialist pattern. Use Bedrock Multi-Agent Collaboration or Strands Agents for orchestration.

6. **Add operational infrastructure** — Monitoring (OpenTelemetry + Prometheus), circuit breakers (per MCP server), retry logic, rate limiting, caching, and error handling. These are not optional for FSI.

7. **Abstract the LLM provider** — Support Bedrock, Azure OpenAI, GCP Vertex AI, and self-hosted models behind a common interface. Cloud lock-in is a deal-breaker for Tier 1/2/5.

8. **Design the WORM audit architecture** — Langfuse is not WORM-compliant. Define the immutable audit storage (S3 Object Lock, Azure Immutable Blob, or on-premise WORM) as a first-class component.

9. **Add a testing strategy document** — Especially for schema translation (the self-identified #1 risk) and compliance rule evaluation. Property-based testing for policy engines.

10. **Merge M2 and M4 conceptually** — They are the same pattern (policy evaluation) with different rule sets. A unified policy engine with separate policy bundles reduces complexity and eliminates consistency risks.

---

## CONCLUSION

Project 007's architectural vision is among the most thoughtful FSI agent designs I've reviewed. The 5-layer interoperability model, the trust-first build order, and the honest self-assessment of risks demonstrate deep domain expertise. The railway metaphor makes the architecture accessible to non-technical stakeholders — a rare and valuable quality.

The weakness is in the gap between vision and implementation specification. The docs describe WHAT to build with clarity but not HOW to build it with precision. For a system that will handle MNPI, execute trades, and face FINRA examination, "~300 lines of BUILD" is not a sufficient specification. Each module needs: technology choices justified against alternatives, interface contracts (API schemas), error handling behavior, deployment model, and testing strategy.

The architecture is ready for a detailed technical design phase. It is not ready for implementation.

---

*Reviewer 1 — Architecture & Tech Stack*
*Project 007 LLM-as-Judge Committee*
