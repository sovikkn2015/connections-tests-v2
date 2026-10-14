# PROJECT 007 — LLMJ COMMITTEE v2 REASSESSMENT
# INTEROPERABLE MULTI-AGENT SYSTEM FOR FINANCIAL SERVICES

> Committee: 5-Person LLM-as-Judge Panel (Reconvened)
> Date: July 2026
> v1 Score: 5.1/10 — CONDITIONAL GO
> Documents Reviewed (v2): 007-v2-tech-stack-decisions.md, 007-v2-multi-agent-and-memory-architecture.md, 007-v2-implementation-plan.md
> Documents Reviewed (v1): All 9 original /docs/ files, REVIEW-01, REVIEW-02-to-05
> Purpose: Assess whether the 10 required actions from the v1 review have been adequately addressed

---

## 1. SCORECARD: STATUS OF THE 10 REQUIRED ACTIONS

---

### ACTION 1: Hire a Compliance SME (Week 0)

**Verdict: FULLY ADDRESSED**

The v2 implementation plan makes the compliance SME a Phase 0 deliverable (item 0.1, due Week 1) with explicit acceptance criteria: "SME with FINRA Rule 3110/3120 experience onboarded. Can translate regulatory requirements to machine-readable rules." The plan budgets $15K–$25K for Phase 0 alone, $72K for Phase 1 (12 weeks × 20 hrs × $300/hr), and identifies the SME as a critical path dependency for M2/M4 rules and M3 schema validation. The risk register (R3) addresses SME unavailability with a mitigation: "Identify 3 candidate SMEs. Engage backup." The compliance dependency tracker lists the SME as NOT STARTED with HIGH risk, demonstrating honest status tracking.

**Evidence:** Implementation plan Phase 0 deliverable 0.1, Phase 1 team composition, Risk R3, Compliance Dependencies table.

---

### ACTION 2: Start All Vendor API Applications (Week 0)

**Verdict: FULLY ADDRESSED**

Phase 0 deliverables 0.2–0.6 explicitly list: Schwab API application (Wk 1), Orion API application (Wk 1), eMoney API application (Wk 1), Fidelity Integration Xchange (Wk 2), Smarsh API (Wk 2). The dependency tracker provides a comprehensive table of 13 vendors with application dates, expected response times, current status (all NOT STARTED except Salesforce FSC which is AVAILABLE), and fallback plans for each. Mock adapters with synthetic data are specified as the universal fallback. Risk R2 ("Vendor API access delayed beyond 12 weeks," probability HIGH 80%) has explicit mitigation.

**Evidence:** Implementation plan Phase 0 deliverables 0.2–0.6, Vendor API Applications dependency tracker (13 vendors), Risk R2.

---

### ACTION 3: Write the Detailed Tech Stack Decision Document (Weeks 1–2)

**Verdict: FULLY ADDRESSED**

The v2 tech stack document is a ~500-line specification covering all 12 modules (M1–M12) with: language, framework, alternatives considered with justification for rejection, key libraries, deployment model, database selection, cloud dependencies, and cloud-agnostic alternatives. Every module has a structured decision table.

The document also includes: 3 deployment topologies (cloud, hybrid, on-premise) with ASCII architecture diagrams and per-tier cost estimates, LLM provider abstraction with a unified `LLMProvider` protocol interface supporting Bedrock/Azure OpenAI/Vertex AI/self-hosted/LiteLLM, database selections per module with cloud and on-prem alternatives, secret management strategy with rotation schedules, observability stack with SLA targets, infrastructure-as-code decisions (CDK for AWS, Terraform for multi-cloud, Helm for K8s), and network security controls (mTLS, network policies, egress allowlisting, encryption at rest).

Specific committee recommendations adopted: OPA/Rego for M2/M4, LangGraph for M8, Strands Agents SDK for M12, S3 Object Lock for M10 WORM, Keycloak for M1 user auth, M2/M4 merged into unified OPA engine. The technology summary table classifies 5 of 12 modules as zero cloud dependency, 6 as abstractable via config, and only AgentCore (M12) as AWS-specific — replaceable with Kubernetes.

**Evidence:** Entire 007-v2-tech-stack-decisions.md. Sections 2–10.

---

### ACTION 4: Design the Multi-Agent Architecture (Weeks 2–4)

**Verdict: FULLY ADDRESSED**

The v2 multi-agent document provides a comprehensive supervisor + specialist architecture with:

- A rationale table showing why single-agent fails (5 lines with different reasoning patterns, context windows, state models, and LLM needs).
- Supervisor Agent on Strands SDK/AgentCore using Claude Haiku for fast routing (<500ms).
- 5 specialist definitions with detailed attribute tables: Research (LangGraph, Sonnet, 23-stage pipeline with 3 HITL gates, 20-min timeout, max 3 concurrent per tenant), Client Service (Strands, Haiku, <3s target, cross-channel memory), Compliance (OPA/Rego, NO LLM, deterministic, exposed as MCP tool), Execution (Strands + finite state machine, mandatory HITL, 24hr timeout, tamper-proof approval tokens), Onboarding (workflow engine, multi-session over days).
- Inter-agent communication protocol with JSON message format, 5 handoff rules, and MNPI-filtered state transfer via supervisor.
- Supervisor routing logic with pseudocode: >95% confidence = deterministic routing, 80–95% = LLM-assisted planning with per-step authority validation, <80% = clarification request.
- ASCII diagrams for the supervisor architecture, research pipeline (23 stages with 3 HITL gates), and execution order state machine.

The compliance specialist is explicitly NOT an LLM agent — it is a deterministic OPA/Rego engine exposed as an MCP tool (`compliance.check(security_id, check_type, context)`), exactly as Reviewers 1 and 4 recommended. Example call/response patterns are provided.

**Evidence:** 007-v2-multi-agent-and-memory-architecture.md, Part 1, Sections 1.1–1.5.

---

### ACTION 5: Design the Memory Architecture (Weeks 2–4)

**Verdict: FULLY ADDRESSED**

The v2 document provides a 6-layer memory architecture with storage backends, retention policies, and retrieval mechanisms for each layer:

- L1 Working Memory: Redis, cross-channel, session TTL 8 hours, session_id = hash(user_id + firm_id + date). Detailed Redis session state JSON schema provided.
- L2 Short-Term Memory: DynamoDB/PostgreSQL, 7-day rolling, promoted to L3 if significant.
- L3 Episodic Memory: DynamoDB + vector index / PostgreSQL + pgvector, hybrid retrieval (recency + relevance), 2-year retention.
- L4 Semantic Memory: pgvector/Pinecone, permanent, vector similarity search.
- L5 Procedural Memory (MetaClaw): File-based JSON (S3/local), permanent, advisor-specific preferences.
- L6 Compliance Memory: S3 Object Lock (WORM), 6+ year retention, immutable.

MNPI-aware memory filtering is designed in detail: memory entry schema includes `archetype`, `role`, `mnpi_level`, and `data_classification` tags. Per-archetype filtering rules table specifies behavior (Tier 1: Chinese wall enforcement on memory, Tier 5: position-level stripped to sector/exposure, cross-pod blocked). Memory retrieval passes through M4 (OPA) before returning to the specialist.

Cross-channel persistence is explicitly designed with a session resolution flow. Pipeline checkpoint state uses LangGraph native checkpointing. HITL gate state persistence has a detailed JSON schema with tamper-proof approval flow.

**Evidence:** 007-v2-multi-agent-and-memory-architecture.md, Part 2, Sections 2.1–2.5.

---

### ACTION 6: Implement WORM-Compliant Audit Storage (Weeks 3–6)

**Verdict: FULLY ADDRESSED**

The v2 tech stack document (M10 section) specifies a three-tier audit architecture exactly as Reviewer 2 recommended:

- Tier 1 Operational (Langfuse): 90-day retention. Explicitly: "NOT the regulatory record."
- Tier 2 Compliance (S3 Object Lock): Immutable, 6-year retention, SHA-256 hash per entry, third-party access via cross-account IAM for 17a-4(f)(3)(vii). Explicitly: "THIS is the regulatory record of truth." Azure: Immutable Blob Storage. On-prem: NetApp SnapLock / Dell EMC Centera.
- Tier 3 Business (CRM): Salesforce IR_Audit_Log__c. Explicitly: "Not the regulatory record."

Retention periods specified: 6-year trade-related, 3-year order tickets, 5-year general books and records. Dead letter queue for failed writes. Fail-closed on audit failure.

The implementation plan includes a dedicated "WORM Storage Proof" deliverable (Phase 1, item 1.9, Weeks 6–8) with compliance SME sign-off as acceptance criteria. Risk R7 addresses misconfiguration with two-person approval requirement.

**Evidence:** Tech stack M10 section, Implementation plan deliverable 1.9, Risk R7.

---

### ACTION 7: Design the Canonical Schema with the Compliance SME (Weeks 3–8)

**Verdict: PARTIALLY ADDRESSED**

The v2 tech stack document (M3 section) specifies JSON Schema Draft 2020-12, semantic versioning, automated breaking change detection via `json-schema-diff`, and lists 8 canonical types: Client, Holding, Order, ResearchBrief, ComplianceCheck, AuditEntry, PlanSummary, RiskProfile.

The M7 section specifies hand-written translators with code-generation assist, declarative YAML mapping definitions, and automated reconciliation tests ("compare canonical output against source system values for 100+ sample records, run daily in CI/CD"). The Orion translator explicitly documents the MarketValue semantic mismatch.

**What is still missing:**
- The actual field-level schema definitions are not provided. We know the 8 type names but not their fields, inclusions, exclusions, or semantic documentation. The committee asked for "explicit field-level documentation" — this is deferred to implementation.
- No sample schema is provided to validate the approach. Even a draft Client or Holding schema would demonstrate feasibility and surface design questions early.
- The reconciliation test framework is described conceptually but not designed — no test harness architecture, no sample test cases, no tolerance thresholds.

The schema design is correctly scoped and planned, but the actual schema content — the committee's #1 technical risk — remains unwritten.

**Evidence:** Tech stack M3 and M7 sections, Implementation plan deliverables 1.3, 2.1–2.4, Risk R1.

---

### ACTION 8: Build the Evaluation Framework (Weeks 4–8)

**Verdict: FULLY ADDRESSED**

The v2 multi-agent document (Part 5) specifies a comprehensive evaluation framework totaling 1,230+ tests:

- 750 functional queries (150 per archetype × 5)
- 200 adversarial compliance tests
- 100 schema reconciliation tests per translator
- 200 multi-agent routing tests
- 30 end-to-end journey tests (6 journeys × 5 archetypes)
- 50 performance tests

8 sample adversarial test cases are provided (ADV-001 through ADV-008) covering: own-client filtering, pod isolation, prompt injection, PII blocking, Chinese wall, MNPI filtering, HITL enforcement, and rate limiting.

The implementation plan phases the eval suite: v1 in Phase 1 (200 queries + 50 adversarial), v2 in Phase 2 (750+ functional + 200 adversarial + multi-agent routing + CI/CD integration). SLA targets provide concrete performance benchmarks.

**Evidence:** Multi-agent doc Part 5, Implementation plan deliverables 1.7 and 2.11, Tech stack Section 7 (SLA targets).

---

### ACTION 9: Define Pricing and GTM Strategy (Weeks 4–6)

**Verdict: FULLY ADDRESSED**

Phase 0 deliverable 0.9 specifies pricing: "Tier 4: $500-$2K/mo per-seat. Tier 3: $5K-$25K/mo platform + adapter. Validated with 3 advisor conversations." Due Week 3.

Lighthouse customer identification (item 0.10): "3 Tier 4 RIAs + 2 Tier 3 BDs. LOIs or verbal commitments." Due Week 4.

GTM is embedded in the phased plan: Phase 2 lighthouse "draft mode" with edit rate tracking (<20% target), Phase 3 expansion to 20–50 customers with SOC 2 completion, Phase 4 Tier 2/5 pipeline, Phase 5 Tier 1 pilots.

Revenue projections provided: Phase 3 $1M–$7.5M ARR, Phase 4 $4.5M–$22M ARR. Break-even Month 10–14. Infrastructure cost estimates per topology per tier. SOC 2 preparation starts Phase 0 (item 0.8).

**Evidence:** Implementation plan Phase 0 deliverables 0.8–0.10, Revenue Projections table, Cost Summary table, Tech stack Section 3 cost estimates.

---

### ACTION 10: Add Cross-Border Regulatory Support (Weeks 6–10)

**Verdict: PARTIALLY ADDRESSED**

The implementation plan addresses cross-border regulation in two phases:

- Phase 3 (deliverable 3.7, Weeks 30–36): "Jurisdiction field in enterprise config. GDPR basics: consent tracking, right-to-erasure with legal hold exception, DPA tracking. DORA basics: third-party ICT register, incident reporting hooks."
- Phase 5 (deliverables 5.4–5.6, Weeks 52–78): Full MiFID II, Full DORA, Full GDPR modules with dedicated EU regulatory SME.

**What is still missing:**
- No architectural design for jurisdiction-aware compliance in the v2 documents. The tech stack document does not show how OPA policies would be structured per jurisdiction, how conflicting regulations (GDPR erasure vs. 17a-4 retention) would be resolved in the policy engine, or how data residency would be enforced per jurisdiction.
- FCA Consumer Duty, MAS TREx, and SFC AI Guidelines (identified by Reviewer 2) are not mentioned in the v2 docs.
- The enterprise-config.yaml sample does not include a jurisdiction field.
- The phasing is reasonable (US-first, then global), but the architectural hooks for jurisdiction-aware compliance should be designed now even if implementation is deferred.

**Evidence:** Implementation plan deliverables 3.7, 5.4–5.6. Absence of jurisdiction-aware OPA policy design in tech stack document.

---

### SCORECARD SUMMARY

| # | Required Action | Verdict | Notes |
|---|----------------|---------|-------|
| 1 | Hire Compliance SME | **FULLY ADDRESSED** | Phase 0 deliverable, budgeted, risk-mitigated |
| 2 | Start Vendor API Applications | **FULLY ADDRESSED** | 13 vendors tracked, fallback plans for each |
| 3 | Tech Stack Decision Document | **FULLY ADDRESSED** | ~500-line spec, all 12 modules, 3 topologies |
| 4 | Multi-Agent Architecture | **FULLY ADDRESSED** | Supervisor + 5 specialists, detailed design |
| 5 | Memory Architecture | **FULLY ADDRESSED** | 6-layer model, MNPI-aware, cross-channel |
| 6 | WORM Audit Storage | **FULLY ADDRESSED** | Three-tier architecture, S3 Object Lock, SME sign-off |
| 7 | Canonical Schema Design | **PARTIALLY ADDRESSED** | Types named, approach defined, but no field-level schemas |
| 8 | Evaluation Framework | **FULLY ADDRESSED** | 1,230+ tests, adversarial suite, phased rollout |
| 9 | Pricing and GTM | **FULLY ADDRESSED** | Pricing defined, lighthouse plan, revenue projections |
| 10 | Cross-Border Regulatory | **PARTIALLY ADDRESSED** | Phased plan exists, but no architectural design for jurisdiction-aware policies |

**Result: 8 of 10 FULLY ADDRESSED. 2 of 10 PARTIALLY ADDRESSED. 0 NOT ADDRESSED.**

---

## 2. REVISED SCORES

---

### Area 1: Architecture & Tech Stack (Reviewer 1)

| Dimension | v1 Score | v2 Score | Delta | Justification |
|-----------|----------|----------|-------|---------------|
| Tech Stack Gaps | 4/10 | 8.5/10 | +4.5 | Every module now has language, framework, alternatives considered, cloud-agnostic path. The tech stack document is exactly what the committee asked for. Deducting 1.5 for: no performance benchmarks for OPA at scale, no load testing results for the LLM provider abstraction layer, and the LLM provider interface is shown as pseudocode but not validated. |
| Multi-Agent Design | 5/10 | 9/10 | +4.0 | Supervisor + 5 specialists with different frameworks per specialist (LangGraph for research, Strands for conversational, OPA for compliance, state machine for execution). Inter-agent communication protocol defined. Routing logic with pseudocode. This is a textbook implementation of the committee's recommendation. Deducting 1 for: no failure mode analysis for supervisor itself (what if supervisor LLM hallucinates a routing decision?), no circuit breaker on supervisor. |
| Deployment Model | 4/10 | 8/10 | +4.0 | Three topologies defined with ASCII diagrams and cost estimates. Hybrid topology correctly places trust layer on-prem and compute in cloud. Full on-prem with self-hosted LLM (vLLM/TGI) addressed. Deducting 2 for: no actual Helm chart structure shown, no Terraform/CDK module structure, hybrid topology mTLS tunnel is described but not designed (WireGuard vs. PrivateLink is listed as options, not a decision). |
| Build vs Adapt | 7/10 | 8.5/10 | +1.5 | OPA, LangGraph, Keycloak, Strands all adopted as recommended. M2/M4 merged. Line count reduction from ~1,350 lines of custom code to battle-tested open-source acknowledged. Deducting 1.5 for: OpenClaw dependency risk is acknowledged but no concrete migration plan if OpenClaw is abandoned. |
| Missing Components | 4/10 | 8/10 | +4.0 | Monitoring (OpenTelemetry + Prometheus + Grafana + Langfuse), circuit breakers (per MCP server), retry logic (exponential backoff), rate limiting, caching (Redis), error handling (fail-closed), mTLS, secret management (Vault/Secrets Manager), network policies — all now specified. Deducting 2 for: no chaos engineering plan, no disaster recovery testing procedure (RPO/RTO targets stated in Phase 3 but no DR test plan), no runbook documentation mentioned. |

| **Area 1 Weighted** | **v1: 6.8/10 (adjusted)** | **v2: 8.4/10** | **+1.6** |
|---|---|---|---|

---

### Area 2: Compliance & Regulatory (Reviewer 2)

| Dimension | v1 Score | v2 Score | Delta | Justification |
|-----------|----------|----------|-------|---------------|
| FINRA 2026 Alignment | 6/10 | 7.5/10 | +1.5 | WORM storage now fully designed (three-tier). HITL gates detailed with tamper-proof approval tokens. AID maps to FINRA's "supervise AI like employees" expectation. Still missing: WSP-to-YAML mapping document, Rule 3120 supervisory dashboard is only a Grafana concept, Rule 2210 principal review queue is in Phase 3 but not architecturally designed. |
| Regulatory Gaps | 5/10 | 6/10 | +1.0 | Reg BI documentation is still not designed as a first-class module. ERISA account-type awareness is not mentioned. BSA/AML ongoing monitoring (SAR/CTR) absent. SOX controls remain unaddressed. The compliance specialist's deterministic design is excellent for auditability, but the regulatory gap list from v1 is only partially closed. |
| Audit Trail Adequacy | 5/10 | 8.5/10 | +3.5 | Three-tier architecture is exactly what Reviewer 2 recommended. S3 Object Lock Compliance mode with 6-year retention, SHA-256 integrity hashing, third-party access via cross-account IAM, dead letter queue, fail-closed. WORM Storage Proof deliverable with compliance SME sign-off. Deducting 1.5 for: chain of custody documentation process not described, legal hold capability not designed. |
| MNPI Enforcement | 7/10 | 8.5/10 | +1.5 | Memory is now MNPI-aware with per-entry tagging and OPA filtering on retrieval. Per-archetype memory filtering rules table is well-designed. Fail-closed with <60s propagation. Automated reconciliation tests specified. Deducting 1.5 for: MNPI Leakage Scan (output guardrail [5]) is listed but not designed — no description of detection mechanism or accuracy. |
| Cross-Border | 3/10 | 4.5/10 | +1.5 | Phased plan exists (GDPR basics Phase 3, full MiFID II/DORA/GDPR Phase 5). EU regulatory SME hire planned. But no architectural design for jurisdiction-aware policies. FCA, MAS, SFC still absent. |
| Liability Framework | 4/10 | 4.5/10 | +0.5 | E&O insurance mentioned in dependency tracker but no liability allocation matrix, no compliance warranty boundary, no indemnification framework. Largely unaddressed. |

| **Area 2 Weighted** | **v1: 5.0/10** | **v2: 6.6/10** | **+1.6** |
|---|---|---|---|

---

### Area 3: Commercial Viability & Market Fit (Reviewer 3)

| Dimension | v1 Score | v2 Score | Delta | Justification |
|-----------|----------|----------|-------|---------------|
| Market Sizing | 7/10 | 7/10 | 0 | No new market analysis in v2 docs. The v1 analysis was already strong. |
| Competitive Moat | 5/10 | 6/10 | +1.0 | The multi-agent architecture with deterministic compliance specialist strengthens the moat narrative. Cross-archetype capability is now architecturally concrete (5 archetype profiles in OPA). However, no new competitive intelligence or Envestnet counter-strategy. |
| Pricing Model | 4/10 | 7/10 | +3.0 | Pricing defined: Tier 4 $500–$2K/mo, Tier 3 $5K–$25K/mo. Infrastructure cost estimates per topology. Revenue projections with break-even. Deducting 3 for: no unit economics analysis (LLM cost per query, MCP cost per call), no margin analysis, no competitive pricing comparison. |
| Go-to-Market | 5/10 | 7/10 | +2.0 | Tier 3 + Tier 4 simultaneous pursuit adopted. Lighthouse plan (3 RIAs + 2 BDs). "Draft mode" → "assisted mode" progression. SOC 2 from Phase 0. Deducting 3 for: no channel partnership plan (RIA in a Box, ACA Compliance Group), no marketing strategy, no sales cycle timeline per tier in the GTM plan. |
| Build vs Buy | 6/10 | 7/10 | +1.0 | "Compliance-first integration layer" positioning is implicit but not explicitly stated as commercial positioning. Adapter ecosystem marketplace concept not mentioned. |
| Partnership Strategy | 5/10 | 6/10 | +1.0 | Vendor API applications tracked with dependency table. But no strategic Envestnet partnership plan, no open-source canonical data model strategy, no compliance consulting firm channel partnership. |

| **Area 3 Weighted** | **v1: 5.3/10** | **v2: 6.7/10** | **+1.4** |
|---|---|---|---|

---

### Area 4: Agentic AI Design Patterns (Reviewer 4)

| Dimension | v1 Score | v2 Score | Delta | Justification |
|-----------|----------|----------|-------|---------------|
| Single vs Multi-Agent | 4/10 | 9/10 | +5.0 | Complete transformation. Supervisor + 5 specialists with framework-per-specialist. Model selection per specialist. Inter-agent communication protocol. Routing logic with confidence thresholds. Deducting 1 for: no A2A protocol readiness (AID compatibility with A2A Agent Cards not addressed). |
| Memory Architecture | 3/10 | 8.5/10 | +5.5 | From completely undesigned to 6-layer model with storage backends, retention policies, MNPI-aware filtering, cross-channel persistence, HITL gate state. Deducting 1.5 for: no memory eviction/compaction strategy, no memory consistency model, MetaClaw learning mechanism not designed. |
| Tool Use Patterns | 6/10 | 8/10 | +2.0 | Constrained plan-and-execute adopted. Plan validation against authority engine. Deterministic routing for >95% confidence. Deducting 2 for: no plan caching, no cost budget per query design. |
| Guardrails Architecture | 5/10 | 8/10 | +3.0 | Rationalized to 11 guardrails in 3 categories with firing order and conflict resolution table. Einstein Trust Layer scoped correctly. Output guardrails added. On-premise substitution plan. Deducting 2 for: output guardrails listed but not designed (MNPI Leakage Scan mechanism undefined), no test cases for conflict scenarios. |
| Evaluation Strategy | 3/10 | 8/10 | +5.0 | From 150 queries to 1,230+ tests across 7 dimensions. Adversarial samples provided. Phased rollout. CI/CD integration. Deducting 2 for: no eval infrastructure design, no baseline metrics defined (what is "passing"?), no eval dataset creation process. |
| Context Window Management | 3/10 | 8/10 | +5.0 | Hierarchical RAG + map-reduce designed. Three-level chunking. Per-stage token budgets. Model selection per stage. Deducting 2 for: no embedding model connected to RAG design, no reranker selected, no vector database for research document indexing. |

| **Area 4 Weighted** | **v1: 4.0/10** | **v2: 8.3/10** | **+4.3** |
|---|---|---|---|

---

### Area 5: Implementation Feasibility & Risk (Reviewer 5)

| Dimension | v1 Score | v2 Score | Delta | Justification |
|-----------|----------|----------|-------|---------------|
| Team Size & Skills | 4/10 | 7.5/10 | +3.5 | Team scaling plan: 3→5→7→10→10→12. Key hires per phase with skills and priority. FIX/SWIFT specialists as contractors. Compliance SME from Phase 0. Deducting 2.5 for: no succession planning, single compliance SME is still a SPOF. |
| Timeline Reality | 3/10 | 7/10 | +4.0 | Adopts "honest assessment" timeline: 78 weeks (18 months). Phase gate checklists. Deducting 3 for: overlapping phases add coordination complexity not addressed, no buffer between phases, revenue projections at Month 9 are aggressive given SOC 2 completes same phase. |
| Dependency Risks | 4/10 | 7/10 | +3.0 | 13 vendor APIs tracked with fallback plans. Technology dependencies with risk levels. 15-risk register. Deducting 3 for: no critical path dependency graph, Bloomberg/Aladdin fallbacks (Alpha Vantage/Polygon) are not equivalent for institutional clients. |
| Technical Risks | 5/10 | 7.5/10 | +2.5 | Honest risk register (schema translation 90% probability CRITICAL). Concrete mitigations. Multi-tenant isolation addressed. Deducting 2.5 for: no technical spike/prototype plan to validate risky assumptions before full implementation. |
| Organizational Risks | 5/10 | 6.5/10 | +1.5 | "Draft mode" addresses advisor resistance. Edit rate tracking. SOC 2 from Phase 0. Deducting 3.5 for: no CCO dashboard design, no kill switch design, no vendor security questionnaire template, no BCP/DR plan, no incident response plan. |

| **Area 5 Weighted** | **v1: 4.2/10** | **v2: 7.1/10** | **+2.9** |
|---|---|---|---|

---

## 3. REVISED OVERALL SCORE

| Reviewer Area | v1 Score | v2 Score | Delta | Weight |
|---------------|----------|----------|-------|--------|
| 1. Architecture & Tech Stack | 6.8/10 | 8.4/10 | +1.6 | 25% |
| 2. Compliance & Regulatory | 5.0/10 | 6.6/10 | +1.6 | 20% |
| 3. Commercial Viability | 5.3/10 | 6.7/10 | +1.4 | 15% |
| 4. Agentic AI Design Patterns | 4.0/10 | 8.3/10 | +4.3 | 25% |
| 5. Implementation Feasibility | 4.2/10 | 7.1/10 | +2.9 | 15% |
| **COMMITTEE OVERALL** | **5.1/10** | **7.5/10** | **+2.4** | |

**Justification for 7.5/10:**

The v2 documents represent a substantial and genuine improvement. The largest gains are in Agentic AI Design Patterns (+4.3) and Implementation Feasibility (+2.9) — the two areas that were weakest in v1. The multi-agent architecture, memory design, and evaluation framework went from "completely undesigned" to "detailed technical specification." The tech stack document is comprehensive and well-justified. The implementation plan is phased, costed, risk-registered, and honestly timed.

The score is held below 8.0 by two factors:

1. **Compliance depth remains the weakest area (6.6/10).** The WORM storage and MNPI enforcement improved significantly, but Reg BI documentation, ERISA, BSA/AML ongoing monitoring, liability framework, WSP-to-YAML mapping, and cross-border architectural design are still gaps. For a platform whose entire value proposition is "compliance-first," the compliance specification should be the strongest section, not the weakest.

2. **Several designs are described but not validated.** The LLM provider abstraction is pseudocode. The MNPI leakage scan is a bullet point. The memory eviction strategy is absent. The eval framework has no infrastructure design. The canonical schema has no field-level content. These are reasonable to defer to implementation — but they represent execution risk that the committee cannot score as "addressed" until proven.

---

## 4. REMAINING GAPS

---

### 4.1 Compliance Gaps (Priority: CRITICAL)

1. **Reg BI Documentation Generator:** Reviewer 2 asked for a first-class module that generates structured Reg BI documentation (basis for recommendation, alternatives considered, best interest rationale, costs and conflicts). The v2 docs do not mention this. For any BD or dual-registered RIA, this is a regulatory requirement for every recommendation the agent makes.

2. **Liability Allocation Framework:** No liability matrix, no compliance warranty boundary (deterministic checks warranted vs. LLM output best-effort), no E&O insurance requirements beyond a one-line mention. Every general counsel will ask for this before signing.

3. **WSP-to-YAML Mapping:** FINRA examiners will ask: "Show me your written supervisory procedures for this AI agent." The YAML config is not a WSP. A human-readable WSP document that maps to the technical controls is needed.

4. **BSA/AML Ongoing Monitoring:** The onboarding specialist handles KYC/sanctions at account opening, but ongoing SAR filing triggers, CTR thresholds, and CDD monitoring are absent.

5. **ERISA Account-Type Awareness:** No concept of account-type-specific compliance rules (taxable vs. retirement vs. trust). A recommendation suitable for a taxable account may violate ERISA for a retirement account.

### 4.2 Architectural Gaps (Priority: HIGH)

6. **MNPI Leakage Scan Design:** Listed as output guardrail [5] but not designed. How does the system detect if the LLM inferred MNPI from filtered data? What is the detection mechanism? What is the false positive rate? This is the hardest guardrail to implement and the most important for compliance.

7. **A2A Protocol Readiness:** Reviewer 1 recommended A2A-ready from day one. The v2 docs do not mention A2A. AID compatibility with A2A Agent Cards, M6 extensibility for A2A task delegation, and cross-boundary trace correlation should be designed now for Journey 6.

8. **Jurisdiction-Aware OPA Policy Structure:** The enterprise config will have a "jurisdiction" field, but how do OPA policy bundles handle jurisdiction? Are there separate bundles per jurisdiction? How are conflicts resolved (GDPR erasure vs. 17a-4 retention)? This architectural decision affects the OPA bundle structure designed in Phase 1.

9. **Memory Consistency and Eviction:** What happens when L3 episodic memory grows to millions of entries? What is the compaction strategy? What if L2 short-term memory and L4 semantic memory have conflicting information about a client preference?

10. **Supervisor Failure Modes:** The supervisor is a single point of routing. What if the supervisor LLM hallucinates a routing decision? What if the supervisor process crashes mid-handoff? No circuit breaker or fallback for the supervisor itself.

### 4.3 Operational Gaps (Priority: MEDIUM)

11. **Eval Infrastructure:** 1,230+ tests are specified but no infrastructure to run them. What tool runs the evals? What constitutes "passing"? How are results tracked over time?

12. **CCO Dashboard and Kill Switch:** Mentioned conceptually but not designed. The CCO needs: real-time compliance engine health, exception rates, HITL approval patterns, and a button to disable the agent for a specific firm/user/line instantly.

13. **Disaster Recovery Testing:** RPO <1hr and RTO <4hr are stated as Phase 3 targets, but no DR test plan, no failover procedure, no runbook.

14. **Canonical Schema Field Definitions:** The 8 type names are listed but no fields are defined. Even draft schemas would surface design questions and validate the approach before Phase 1 implementation.

15. **Technical Spikes:** No plan to validate risky technical assumptions (LangGraph + DynamoDB checkpointing at scale, OPA performance with 500+ rules, cross-channel Redis session resolution) before committing to full implementation.

---

## 5. VERDICT

**Project 007 v2 is a GO for Phase 0 — with conditions.**

The v2 documents have closed the gap between vision and specification that was the primary concern in v1. The architecture is no longer a whitepaper — it is a buildable technical specification. The multi-agent design, memory architecture, tech stack decisions, and implementation plan are all at a level of detail sufficient to begin Phase 0 (prerequisites) and Phase 1 (foundation) work.

The committee upgrades the verdict from CONDITIONAL GO to **GO FOR PHASE 0** with the following conditions:

### Conditions for Phase 0 Start (immediate):
- [x] Tech stack decisions documented — **DONE**
- [x] Multi-agent architecture designed — **DONE**
- [x] Memory architecture designed — **DONE**
- [x] Implementation plan with phases, costs, risks — **DONE**
- [x] WORM audit architecture designed — **DONE**
- [x] Evaluation framework designed — **DONE**

### Conditions for Phase 1 Start (must be completed during Phase 0):
- [ ] Compliance SME onboarded and available 20+ hrs/week
- [ ] At least 3 vendor API applications submitted
- [ ] SOC 2 auditor engaged
- [ ] Draft canonical schema (Client + Holding types at minimum) reviewed by compliance SME
- [ ] Liability allocation framework drafted with legal counsel input

### Conditions for Phase 2 Gate (must be completed before lighthouse deployment):
- [ ] Reg BI documentation generator designed as a module
- [ ] MNPI leakage scan mechanism designed and prototyped
- [ ] CCO dashboard and kill switch operational
- [ ] At least 1 technical spike completed (LangGraph + DynamoDB checkpointing)
- [ ] WSP-to-YAML mapping document created with compliance SME

---

## 6. TOP 5 REMAINING ACTIONS

**1. Design the Reg BI Documentation Generator (Phase 0–1)**
This is the most critical compliance gap. Every recommendation the agent makes to a retail customer must be accompanied by structured Reg BI documentation. This is not a logging problem — it is a structured document generation problem with specific regulatory fields (basis, alternatives, best interest rationale, costs, conflicts). Design this as a first-class output of the Client Service and Research specialists. The compliance SME must define the required fields. Without this, no BD or dual-registered RIA can deploy.

**2. Design the MNPI Leakage Scan (Phase 1)**
Output guardrail [5] is listed but not designed. This is the hardest and most important guardrail. The system must detect if the LLM's output contains information that should have been filtered from its input — i.e., the LLM inferred MNPI from context clues. Options include: keyword/pattern matching against the filtered field list, a secondary LLM classifier trained on MNPI patterns, or a deterministic comparison of output entities against the MNPI filter log. Design the mechanism, estimate its accuracy, and define the false positive handling strategy. A regulator will ask how this works.

**3. Draft the Canonical Schema Field Definitions (Phase 0)**
The 8 type names are listed but no fields are defined. Before Phase 1 code is written, draft at minimum the Client and Holding schemas with field-level documentation of inclusions, exclusions, and semantic meaning. Validate against real Salesforce FSC and Orion API response schemas. This will surface the semantic mismatch problems early — the committee's #1 technical risk — and give the compliance SME something concrete to review. Do not wait until Phase 1 Week 4 to discover that "MarketValue" means different things in different systems.

**4. Engage Legal Counsel for Liability Framework (Phase 0)**
The v2 docs have no liability allocation. Before any lighthouse customer signs an LOI, the team needs: a liability allocation matrix (platform vendor vs. firm vs. LLM provider vs. MCP server vendor), a compliance warranty boundary (deterministic checks warranted, LLM output not warranted), indemnification provisions for schema translation errors, and E&O insurance requirements. This is a commercial blocker, not a technical one, but it will delay Phase 2 lighthouse deployment if not started in Phase 0.

**5. Run Technical Spikes for High-Risk Assumptions (Phase 0–1)**
Before committing to the full 23-stage LangGraph pipeline, prove that: (a) LangGraph checkpointing to DynamoDB works reliably at the scale of a 20-minute research pipeline with 3 HITL gates, (b) OPA evaluates 500+ Rego rules in <10ms as claimed, (c) Redis cross-channel session resolution works when a user switches from WhatsApp to Slack mid-conversation, and (d) the LLM provider abstraction layer produces equivalent results across Bedrock Claude and at least one alternative (Azure OpenAI or self-hosted). A 1-week spike per assumption in Phase 0 would retire significant execution risk before the team scales to 5 engineers in Phase 1.

---

## FINAL ASSESSMENT

The v2 documents represent a genuine and substantial improvement over v1. The committee's 10 required actions have been taken seriously — 8 are fully addressed, 2 are partially addressed, and none are ignored. The overall score improvement from 5.1 to 7.5 reflects real architectural progress, not cosmetic changes.

The largest transformation is in Agentic AI Design Patterns (4.0 → 8.3), where the architecture went from a single-agent assumption with no memory design to a fully specified multi-agent system with 6-layer MNPI-aware memory. This was the committee's highest-priority concern and it has been addressed with impressive depth and specificity.

The remaining weakness is compliance depth. For a platform whose entire commercial thesis is "compliance-first integration layer," the compliance specification (6.6/10) should not be the lowest-scoring area. The WORM storage and MNPI enforcement are strong, but Reg BI documentation, liability framework, and cross-border regulatory architecture need the same level of detailed design that the multi-agent architecture received.

The project is ready to begin. The 5 remaining actions above are achievable within Phase 0–1 and do not block the start of work. The team should begin Phase 0 immediately while addressing these gaps in parallel.

Build the signals first. The trains are now designed. Time to lay track.

---

*LLMJ Committee — Reconvened*
*Project 007 v2 Reassessment*
*July 2026*
