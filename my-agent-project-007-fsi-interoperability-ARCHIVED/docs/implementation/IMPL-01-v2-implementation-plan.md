# PROJECT 007 v2 — IMPLEMENTATION PLAN

> Version: 2.0
> Date: July 2026
> Status: Detailed Implementation Plan (addressing ALL LLMJ Committee findings)
> Timeline: "Honest assessment" — 6-9 months Tier 3/4, 18-24 months all 5 tiers
> Audience: Engineering team, project management, investors, compliance stakeholders

---

## TIMELINE OVERVIEW

```
PHASE 0        PHASE 1           PHASE 2              PHASE 3              PHASE 4           PHASE 5
Prerequisites  Foundation        Tier 3/4 MVP         Production Hardening Tier 2/5 Expansion Tier 1 + Global
Wk 0-4        Wk 4-18           Wk 14-36             Wk 32-44             Wk 40-60           DEFERRED
              ├─────────────────┤                     │                    │                   │
              │ M1,M10,M3,M2/M4│ M7,M11,M9,M8,M12   │ Fidelity,Pershing  │ Bloomberg,FactSet │ NICE,SWIFT
              │ M5,M6,Eval     │ 2 specialists       │ Execution Spec.    │ FIX,SS&C,Backstop│ Chinese wall
              │                │ Memory L1-L4        │ Onboarding Spec.   │ Tier 2/5 profiles│ MiFID,DORA
              │                │ 3-5 lighthouse       │ SOC 2 Type II      │ Pod isolation    │ Full global
              │                │ "Draft mode"         │ 20-50 customers    │                  │
```

---

## PHASE 0: PREREQUISITES (Weeks 0–4, Before Any Code)

### Objective
Eliminate the non-technical blockers that will delay Phases 1-2 if not started immediately.

### Team
- 1 Technical Lead / Architect
- 1 Compliance SME (contract, part-time — $200-$400/hr, budget $15K-$25K for Phase 0)
- 1 Business Development lead

### Deliverables

| # | Deliverable | Owner | Due | Acceptance Criteria |
|---|-------------|-------|-----|---------------------|
| 0.1 | Hire/contract compliance SME | Tech Lead | Wk 1 | SME with FINRA Rule 3110/3120 experience onboarded. Can translate regulatory requirements to machine-readable rules. |
| 0.2 | Submit Schwab API application | BD Lead | Wk 1 | Application submitted to Schwab Advisor Services developer program. |
| 0.3 | Submit Orion API application | BD Lead | Wk 1 | Application submitted to Orion API partner program. |
| 0.4 | Submit eMoney API application | BD Lead | Wk 1 | Application submitted to eMoney/Fidelity integration program. |
| 0.5 | Submit Fidelity Integration Xchange application | BD Lead | Wk 2 | Application submitted. |
| 0.6 | Submit Smarsh API application | BD Lead | Wk 2 | Application submitted for compliance archiving integration. |
| 0.7 | Engage FINRA Innovation Office | Compliance SME | Wk 2 | Informal guidance meeting scheduled. Present 007 architecture for feedback. |
| 0.8 | Begin SOC 2 Type II preparation | Tech Lead | Wk 3 | Auditor engaged (Schellman, A-LIGN, or equivalent). Control framework selected. Evidence collection process defined. |
| 0.9 | Define pricing model | BD Lead | Wk 3 | Tier 4: $500-$2K/mo per-seat. Tier 3: $5K-$25K/mo platform + adapter. Documented and validated with 3 advisor conversations. |
| 0.10 | Identify 5 lighthouse customers | BD Lead | Wk 4 | 3 Tier 4 RIAs + 2 Tier 3 BDs identified. LOIs or verbal commitments for pilot program. |
| 0.11 | Set up development infrastructure | Tech Lead | Wk 2 | GitHub repo, CI/CD (GitHub Actions), container registry (ECR), dev AWS account, Terraform/CDK base. |
| 0.12 | Vendor sandbox accounts | BD Lead | Wk 4 | Salesforce FSC sandbox, Orion sandbox (if available), mock adapters for Schwab/eMoney with synthetic data. |

### Risk Mitigations
- Schwab API access may take 6-8 weeks → build mock adapter with synthetic data immediately
- Compliance SME may be unavailable → identify 3 candidates, engage backup
- FINRA Innovation Office may not respond → proceed with architecture, document assumptions

### Exit Criteria
- [ ] Compliance SME onboarded and available 20+ hrs/week
- [ ] All 5 vendor API applications submitted
- [ ] SOC 2 auditor engaged
- [ ] 5 lighthouse customers identified
- [ ] Dev infrastructure operational
- [ ] Pricing model defined

### Estimated Cost: $40K–$70K
- Compliance SME: $15K-$25K
- SOC 2 auditor engagement: $10K-$20K
- Infrastructure setup: $5K-$10K
- BD travel/conferences: $5K-$10K
- Vendor sandbox fees: $2K-$5K

---

## PHASE 1: FOUNDATION (Weeks 4–16)

### Objective
Build the trust layer (identity, policy, audit, gateway) and prove that an unauthorized call is DENIED before reaching any system. This is the "build the signals before the trains" phase.

### Team: 4 engineers + 1 compliance SME (part-time)
- 1 Senior Backend (Python) — M1, M2/M4, M6
- 1 Senior Backend (Python) — M10, M8 (LangGraph setup)
- 1 Full-Stack (Python + TypeScript) — M3, M5, M11 (mock adapters)
- 1 DevOps/Platform — Infrastructure, CI/CD, observability, WORM storage
- 1 Compliance SME (part-time, 20 hrs/wk) — M2/M4 rules, M3 schema validation

### Deliverables

| # | Deliverable | Owner | Weeks | Acceptance Criteria |
|---|-------------|-------|-------|---------------------|
| 1.1 | M1: Agent Identity Service | Sr Backend 1 | 4-6 | Keycloak deployed. AID issuance, verification, revocation working. JWT RS256 with FSI claims (LEI, CRD, archetype, authority). Token expiry and revocation endpoint functional. |
| 1.2 | M10: Audit Logger (3-tier) | Sr Backend 2 | 4-7 | Three-tier write: Langfuse (operational), S3 Object Lock Compliance mode (WORM, 6-year retention), CRM stub. SHA-256 integrity hashing. Dead letter queue for failed writes. Fail-closed on audit failure. |
| 1.3 | M3: Canonical Schema Registry | Full-Stack | 4-8 | JSON Schema definitions for Client, Holding, Order, ResearchBrief, ComplianceCheck, AuditEntry. Versioned (semver). Breaking change detection in CI. Validated by compliance SME for field-level semantics. |
| 1.4 | M2/M4: Unified OPA Policy Engine | Sr Backend 1 | 6-10 | OPA deployed with two policy bundles: `authority/` and `mnpi/`. 50+ Rego rules covering: restricted list, concentration limits, trading window, data isolation (advisor-level), MNPI field filtering for Tier 3 and Tier 4. Fail-closed. <60s propagation for rule updates. |
| 1.5 | M5: Enterprise Config Loader | Full-Stack | 5-7 | Pydantic-validated YAML config. Secret reference resolution (Vault/Secrets Manager). Hot reload. Two sample configs: Tier 3 BD and Tier 4 RIA. |
| 1.6 | M6: Trust-Aware MCP Gateway | Sr Backend 1 | 8-12 | Central hub wiring M1→M2/M4→M10. Every MCP call: verify AID, check authority, apply MNPI filter, audit log. Circuit breakers, retry logic, rate limiting. Integration tests proving unauthorized calls are DENIED. |
| 1.7 | Evaluation Framework (v1) | Full-Stack + SME | 8-14 | 200 queries (Tier 3 + Tier 4). 50 adversarial compliance tests. Automated CI/CD integration. Schema reconciliation test harness (ready for real data). |
| 1.8 | Infrastructure + Observability | DevOps | 4-16 | EKS cluster, Helm charts for all modules, OpenTelemetry + Prometheus + Grafana, Langfuse deployment, S3 Object Lock configuration (tested in sandbox first!), mTLS between modules, network policies. |
| 1.9 | WORM Storage Proof | DevOps + SME | 6-8 | S3 Object Lock Compliance mode tested: write, verify immutability, verify retention, verify third-party access via cross-account IAM. Compliance SME signs off. |

### Key Milestone: "Trust Gate" Demo (Week 12)
Demonstrate: A mock MCP call from an unauthorized user is DENIED by M2, logged to M10 WORM, and never reaches the mock MCP server. A mock MCP call from an authorized user passes through M6, is MNPI-filtered by M4, and returns filtered data with full audit trail.

### Risk Mitigations
- Canonical schema will be wrong on first try → version from day one, expect 3-5 revisions
- OPA/Rego is a niche skill → allocate 1 week for team Rego training (Styra Academy, free)
- S3 Object Lock Compliance mode is IRREVERSIBLE → test in sandbox account first, never in prod until verified

### Exit Criteria
- [ ] Unauthorized MCP call is DENIED before reaching any system (proven in integration test)
- [ ] WORM audit storage operational with 6-year retention (compliance SME sign-off)
- [ ] 200+ eval queries passing in CI/CD
- [ ] All modules containerized with Helm charts
- [ ] Observability stack operational (metrics, tracing, logging, LLM observability)

### Estimated Cost: $180K–$280K
- 4 engineers × 12 weeks × $3K-$4K/wk: $144K-$192K
- Compliance SME (12 weeks × 20 hrs × $300/hr): $72K
- Infrastructure: $3K-$5K/month × 3 months: $9K-$15K

---

## PHASE 2: TIER 3/4 MVP (Weeks 12–28)

### Objective
Build the first working agent with real vendor integrations, multi-agent orchestration (2 specialists), and memory. Deploy to 3-5 lighthouse customers in "draft mode" (agent produces drafts, advisors review).

### Team: 5 engineers + 1 compliance SME + 1 QA/Eval engineer
- 2 Senior Backend (Python) — M8 (LangGraph pipeline), M9 (intent router), multi-agent (Strands)
- 1 Full-Stack (TypeScript) — M11 adapters (Salesforce, Orion, eMoney, Schwab), M7 translators
- 1 Backend (Python) — Memory architecture (L1-L4), client service specialist
- 1 DevOps/Platform — Production deployment, monitoring, scaling
- 1 QA/Eval — Eval suite expansion, schema reconciliation, adversarial testing
- 1 Compliance SME (part-time, 15 hrs/wk)

### Deliverables

| # | Deliverable | Owner | Weeks | Acceptance Criteria |
|---|-------------|-------|-------|---------------------|
| 2.1 | M7 Translators: Salesforce FSC | Full-Stack | 12-15 | SF Account/Contact → canonical Client. SF FinancialHolding → canonical Holding. Automated reconciliation tests with real SF sandbox data. |
| 2.2 | M7 Translators: Orion | Full-Stack | 14-17 | Orion Client/Household → canonical Client. Orion Position → canonical Holding (with explicit documentation: MarketValue includes/excludes accrued interest). Reconciliation tests. |
| 2.3 | M7 Translators: eMoney | Full-Stack | 16-19 | eMoney Plan → canonical PlanSummary. Goal data, Monte Carlo results mapped. |
| 2.4 | M7 Translators: Schwab | Full-Stack | 18-22 | Schwab Position → canonical Holding. Schwab Order → canonical Order. Cost basis methods documented. |
| 2.5 | M11 Adapters: Above 4 vendors | Full-Stack | 12-22 | MCP servers for Salesforce FSC, Orion, eMoney, Schwab. Each implements GET / + POST /tools/list + POST /tools/call. Auth, rate limiting, error handling per vendor. |
| 2.6 | M11 Adapters: SEC EDGAR + Market Data + News | Full-Stack | 14-18 | Adapted from 006. SEC EDGAR filing retrieval, market data (Alpha Vantage/Polygon as Bloomberg fallback), news API. |
| 2.7 | M9: FSI Intent Router | Sr Backend | 12-16 | LLM function calling with FSI intent taxonomy. 85%+ accuracy on eval suite. Deterministic routing for unambiguous intents. Confidence thresholds (>95% direct route, 80-95% LLM plan, <80% clarify). |
| 2.8 | M8: Pipeline on LangGraph | Sr Backend | 14-20 | 23-stage research pipeline as LangGraph graph. Checkpointing to DynamoDB. 3 HITL gates functional. Map-reduce for multi-source synthesis. Token budgets per stage. |
| 2.9 | Multi-Agent: Supervisor + 2 Specialists | Sr Backend | 16-24 | Strands SDK supervisor on AgentCore. Client Service specialist (Haiku, memory-enabled). Research specialist (LangGraph, Sonnet). Compliance specialist as OPA tool (not LLM agent). Supervisor routing with constrained plan-and-execute. |
| 2.10 | Memory Architecture (L1-L4) | Backend | 16-24 | L1 Working (Redis, cross-channel). L2 Short-term (DynamoDB, 7-day). L3 Episodic (DynamoDB + vector). L4 Semantic (pgvector/Pinecone). MNPI-aware filtering on retrieval. |
| 2.11 | Eval Suite v2 | QA/Eval | 14-28 | 750+ functional queries (5 archetypes). 200 adversarial. Schema reconciliation for all translators. Multi-agent routing tests. CI/CD integrated. |
| 2.12 | Lighthouse Deployment | DevOps + All | 22-28 | 3-5 RIA-ONLY lighthouse customers deployed (no BDs until Smarsh operational in Phase 3). "Draft mode" — agent produces drafts, advisors review. Edit rate tracking. Feedback collection. |

### Key Milestone: "First Real Query" (Week 18)
Sarah Chen at Acme Wealth Management asks on Slack: "Prep me for my meeting with Henderson tomorrow." The agent: classifies intent (M9), routes to Client Service specialist, retrieves Henderson's profile from Salesforce (M11→M7→M6→M2/M4→M10), retrieves holdings from Orion, retrieves plan from eMoney, synthesizes meeting prep brief, delivers to Slack. Full audit trail in WORM.

### Key Milestone: "Draft Mode Launch" (Week 24)
3-5 lighthouse customers using the agent daily. All outputs are "drafts" that advisors review and edit. Edit rate tracked as quality metric. Target: <20% edit rate within 4 weeks of launch.

### Risk Mitigations
- Vendor API access not yet approved → use mock adapters with synthetic data until approved, swap to real when ready
- Schema translation errors → daily automated reconciliation tests, compliance SME reviews mismatches weekly
- LLM output quality disappoints → "draft mode" sets expectations, edit rate tracking identifies weak spots
- Multi-agent routing errors → start with 2 specialists, add incrementally

### Exit Criteria
- [ ] 3-5 lighthouse customers using agent daily in draft mode
- [ ] Edit rate <20% after 4 weeks
- [ ] 750+ eval queries passing
- [ ] All 4 vendor adapters functional (real or mock)
- [ ] Memory persistence across channels proven
- [ ] HITL gates functional for research pipeline

### Estimated Cost: $350K–$520K
- 5 engineers × 16 weeks × $3K-$4K/wk: $240K-$320K
- QA/Eval engineer × 14 weeks × $2.5K-$3.5K/wk: $35K-$49K
- Compliance SME (16 weeks × 15 hrs × $300/hr): $72K
- Infrastructure: $5K-$10K/month × 4 months: $20K-$40K
- Lighthouse customer support: $10K-$20K


---

## PHASE 3: PRODUCTION HARDENING (Weeks 24–36)

### Objective
Expand vendor coverage, add remaining specialists (Execution + Onboarding), complete SOC 2 Type II, and scale to 20-50 Tier 3/4 customers.

### Team: 6 engineers + 1 compliance SME + 1 QA/Eval + 1 sales engineer
- 2 Senior Backend — Execution specialist (state machine + HITL), Onboarding specialist
- 1 Full-Stack (TypeScript) — New adapters (Fidelity, Pershing, Wealthbox, Redtail)
- 1 Backend — Smarsh integration, communication archiving, FINRA 2210 review queue
- 1 DevOps/Platform — Production hardening, multi-tenant isolation, DR/failover
- 1 Security Engineer — Pen testing, vulnerability scanning, SOC 2 evidence
- 1 QA/Eval — Expanded eval suite, regression testing, load testing
- 1 Compliance SME (part-time, 15 hrs/wk)
- 1 Sales Engineer — Customer onboarding, technical support

### Deliverables

| # | Deliverable | Owner | Weeks | Acceptance Criteria |
|---|-------------|-------|-------|---------------------|
| 3.1 | M11 Adapters: Fidelity | Full-Stack | 24-28 | Fidelity Integration Xchange adapter. Position, account, order data. Reconciliation tests. |
| 3.2 | M11 Adapters: Pershing (BNY Mellon) | Full-Stack | 26-30 | NetX360 API adapter. Position, transaction data. |
| 3.3 | M11 Adapters: Wealthbox + Redtail | Full-Stack | 28-32 | CRM adapters for non-Salesforce Tier 4 RIAs. Contact, activity, pipeline data. |
| 3.4 | Smarsh Integration | Backend | 24-30 | All agent-client communications archived to Smarsh. FINRA 2210 compliance. Supervisory review queue for principal review of agent outputs. |
| 3.5 | Execution Specialist (Line 4) | Sr Backend | 24-32 | Strands Agent + finite state machine. Order lifecycle: DRAFT→COMPLIANCE→APPROVAL→SUBMITTED→CONFIRMED. HITL gate mandatory. Approval token with tamper-proof hash. Timeout (24hr configurable). Integration with Schwab/Fidelity order APIs. |
| 3.6 | Onboarding Specialist (Line 5) | Sr Backend | 28-34 | Workflow engine. Steps: collect info → KYC → sanctions → risk profile → account opening → DocuSign → compliance review. Multi-session (client may complete over days). |
| 3.7 | Cross-Border Regulatory (basics) | Compliance SME + Backend | 30-36 | Jurisdiction field in enterprise config. GDPR basics: consent tracking, right-to-erasure workflow with legal hold exception, DPA tracking. DORA basics: third-party ICT register, incident reporting hooks. |
| 3.8 | SOC 2 Type II Audit | Security + DevOps | 24-36 | Complete SOC 2 Type II audit. All controls documented and evidenced. Auditor report issued. |
| 3.9 | Multi-Tenant Isolation | DevOps | 24-30 | Per-tenant: separate encryption keys, namespace isolation (K8s), database isolation (schema-per-tenant or separate DB), audit log isolation, network policies. |
| 3.10 | Production Hardening | DevOps | 28-36 | Blue-green deployment. Canary for M6/M9. DR/failover (RPO <1hr, RTO <4hr). Backup strategy for all databases. Load testing (target: 100 concurrent users per tenant). |
| 3.11 | Expand to 20-50 Customers | Sales Eng + All | 30-36 | Onboard 20-50 Tier 3/4 customers. Transition from "draft mode" to "assisted mode" (agent suggests, advisor confirms with 1-click). |

### Risk Mitigations
- SOC 2 audit may find gaps → security engineer dedicated from week 24, continuous evidence collection
- Execution specialist is safety-critical → extensive testing, mandatory code review by 2 engineers, compliance SME sign-off on state machine
- Smarsh integration may require enterprise partnership → start conversations in Phase 1

### Exit Criteria
- [ ] SOC 2 Type II report issued
- [ ] Execution specialist operational with HITL gates (zero autonomous trades)
- [ ] Smarsh archiving operational for all agent-client communications
- [ ] 20-50 paying customers
- [ ] Edit rate <10% for returning customers
- [ ] Multi-tenant isolation verified by pen test
- [ ] DR/failover tested

### Estimated Cost: $480K–$720K
- 6 engineers × 12 weeks × $3K-$4K/wk: $216K-$288K
- Security engineer × 12 weeks × $3.5K-$4.5K/wk: $42K-$54K
- QA/Eval × 12 weeks × $2.5K-$3.5K/wk: $30K-$42K
- Sales engineer × 12 weeks × $2.5K-$3.5K/wk: $30K-$42K
- Compliance SME: $54K
- SOC 2 audit: $50K-$100K
- Infrastructure (scaling): $10K-$20K/month × 3: $30K-$60K
- Pen testing: $20K-$40K

---

## PHASE 4: TIER 2/5 EXPANSION (Weeks 36–52)

### Objective
Add institutional-grade adapters (Bloomberg, FactSet, FIX, SS&C Eze) and Tier 2/5 archetype profiles. Deploy hybrid topology for firms requiring on-premise trust layer.

### Team: 7 engineers + 1 compliance SME + 1 QA/Eval + 1 FIX specialist (contract)
- 2 Senior Backend — Tier 2/5 policy rules, pod isolation, hybrid deployment
- 1 Full-Stack (TypeScript) — Bloomberg, FactSet adapters
- 1 FIX Protocol Specialist (contract, $250-$400/hr) — FIX Bridge MCP server
- 1 Backend — SS&C Eze, Backstop, ComplySci adapters
- 1 DevOps/Platform — Hybrid topology deployment, on-prem Kubernetes
- 1 Security Engineer — Hybrid security, mTLS across network boundaries
- 1 QA/Eval — Tier 2/5 eval suite, adversarial testing for institutional scenarios
- 1 Compliance SME (part-time) — Tier 2/5 compliance rules

### Deliverables

| # | Deliverable | Owner | Weeks | Acceptance Criteria |
|---|-------------|-------|-------|---------------------|
| 4.1 | Bloomberg B-PIPE Adapter | Full-Stack | 36-44 | Bloomberg BLPAPI integration. Real-time market data, reference data, historical data. Requires Bloomberg license ($24K+/yr). Rate limit compliance. |
| 4.2 | FactSet Adapter | Full-Stack | 38-44 | FactSet API integration. Fundamental data, estimates, ownership data. |
| 4.3 | FIX Protocol Bridge | FIX Specialist | 36-48 | FIX 4.2/4.4 session management wrapped in MCP. Stateful session handling. Order routing, execution reports, allocations. Sub-second latency for order submission. |
| 4.4 | SS&C Eze Adapter | Backend | 40-46 | Eze OMS/EMS integration. Position, order, execution data. Hedge fund workflow support. |
| 4.5 | Backstop Adapter | Backend | 42-48 | Backstop CRM for hedge funds. Contact, company, fund, deal data. |
| 4.6 | ComplySci Adapter | Backend | 44-48 | ComplySci compliance platform. Personal trading pre-clearance, code of ethics. |
| 4.7 | Tier 2 Archetype Profile | Sr Backend + SME | 36-44 | OPA policy bundle for Tier 2 asset managers: portfolio-level authorization, restricted list (firm-wide), pre-trade compliance integration, GIPS attribution awareness, cross-strategy isolation. |
| 4.8 | Tier 5 Archetype Profile | Sr Backend + SME | 40-48 | OPA policy bundle for Tier 5 hedge funds: pod isolation (PM can only see own pod), position-level MNPI (aggregate exposure only to non-authorized), fund-level authorization, prime broker integration rules. |
| 4.9 | Pod Isolation (Tier 5) | Sr Backend | 42-50 | Complete data isolation between pods within a hedge fund. Separate memory spaces, separate audit trails, separate MCP server instances per pod. OPA enforces pod boundaries. |
| 4.10 | Hybrid Topology Deployment | DevOps | 36-48 | Trust layer (M1, M2/M4, M6, M10, M11) deployable on-premise in firm's VPC. Compute layer (M8, M9, M12) in cloud. mTLS tunnel between. Tested with 1 Tier 2 or Tier 5 pilot customer. |

### Risk Mitigations
- Bloomberg API access takes 3-6 months to negotiate → start in Phase 2, build mock adapter
- FIX bridge is complex stateful engineering → hire specialist contractor, budget 2x estimated time
- Tier 5 hedge funds are bespoke → start with 1 pilot fund, iterate on pod isolation rules
- Hybrid deployment adds operational complexity → dedicated DevOps engineer, runbook documentation

### Exit Criteria
- [ ] Bloomberg and FactSet adapters operational (real or sandbox)
- [ ] FIX Bridge functional for equity order routing
- [ ] Tier 2 and Tier 5 archetype profiles in OPA with 100+ rules each
- [ ] Pod isolation verified by adversarial testing
- [ ] Hybrid topology deployed with at least 1 customer
- [ ] 5-10 Tier 2/5 customers in pipeline

### Estimated Cost: $600K–$900K
- 7 engineers × 16 weeks × $3K-$4K/wk: $336K-$448K
- FIX specialist (12 weeks × 40 hrs × $350/hr): $168K
- QA/Eval: $40K-$56K
- Compliance SME: $72K
- Bloomberg license: $24K+
- Infrastructure (hybrid): $15K-$25K/month × 4: $60K-$100K

---

## PHASE 5: TIER 1 AND GLOBAL (Weeks 52–78)

### Objective
Add Tier 1 investment bank support (NICE Actimize, SWIFT, Chinese walls), full global regulatory compliance (MiFID II, DORA, GDPR), and on-premise deployment capability.

### Team: 8 engineers + 2 compliance SMEs + 1 QA/Eval + 1 SWIFT specialist (contract)
- 2 Senior Backend — Chinese wall enforcement, Tier 1 policy rules
- 1 Backend — NICE Actimize integration, surveillance hooks
- 1 SWIFT/ISO 20022 Specialist (contract) — SWIFT Bridge MCP server
- 1 Backend — Full GDPR module, DORA compliance, MiFID II suitability
- 1 Full-Stack — Tier 1 adapters (proprietary OMS/EMS integration patterns)
- 1 DevOps/Platform — Full on-premise topology, self-hosted LLM (vLLM/TGI)
- 1 Security Engineer — Bank-grade security, pen testing, air-gapped deployment
- 2 Compliance SMEs (1 US regulatory, 1 EU regulatory)
- 1 QA/Eval — Tier 1 eval suite, Chinese wall adversarial testing

### Deliverables

| # | Deliverable | Owner | Weeks | Acceptance Criteria |
|---|-------------|-------|-------|---------------------|
| 5.1 | NICE Actimize Integration | Backend | 52-62 | SURVEIL-X API integration. Trade surveillance data feed. Communications monitoring hooks. Alert routing to compliance dashboard. |
| 5.2 | SWIFT/ISO 20022 Bridge | SWIFT Specialist | 52-66 | ISO 20022 message parsing and generation. Payment initiation (pain.001), status (pain.002), statement (camt.053). MCP server wrapping SWIFT Alliance Lite2 or equivalent. |
| 5.3 | Chinese Wall Enforcement | Sr Backend + SME | 52-64 | Information barrier enforcement in OPA. Private-side vs. public-side classification for all data, memory, and agent actions. Cross-wall access DENIED with audit trail. Memory isolation across wall boundaries. Tested with adversarial scenarios. |
| 5.4 | Full MiFID II Module | Backend + EU SME | 56-68 | Best execution reporting. Research unbundling cost tracking. Transaction reporting (T+1). Product governance checks. Suitability assessment (alternative to Reg BI for EU). |
| 5.5 | Full DORA Compliance | Backend + EU SME | 58-70 | ICT risk management framework. Third-party register (all vendors). Incident reporting (4-hour SLA for major incidents). Digital operational resilience testing framework. Exit strategies for all third-party providers. |
| 5.6 | Full GDPR Module | Backend + EU SME | 56-66 | Consent management. DPIA documentation for MNPI engine. DPA tracking for all processors. Right-to-erasure workflow with legal hold hierarchy (17a-4 retention > GDPR erasure). Cross-border data transfer mechanisms (SCCs). Data flow map. |
| 5.7 | Tier 1 Archetype Profile | Sr Backend + SME | 54-66 | OPA policy bundle for Tier 1 banks: Chinese wall enforcement, MAR surveillance hooks, CCAR/DFAST awareness, information barrier classification, cross-department authorization, multi-entity support (bank holding company structure). |
| 5.8 | Full On-Premise Topology | DevOps | 52-68 | All 12 modules on bare-metal Kubernetes. Self-hosted LLM (vLLM serving Llama 3.1 405B + 70B). Self-hosted Langfuse, PostgreSQL, Redis, MinIO, NetApp SnapLock. Air-gapped deployment option. |
| 5.9 | Self-Hosted LLM Integration | DevOps + Sr Backend | 56-66 | vLLM or TGI serving open-weight models. LLM provider abstraction verified with self-hosted backend. Performance benchmarks vs. Bedrock Claude (acceptable quality threshold defined with eval suite). |

### Risk Mitigations
- NICE Actimize requires enterprise partnership (6-12 month cycle) → start conversations in Phase 3
- SWIFT integration is extremely complex → hire specialist, budget 14 weeks
- Chinese wall enforcement is the hardest compliance problem → dedicate 2 senior engineers + compliance SME, extensive adversarial testing
- Self-hosted LLM quality may be lower than Claude → define minimum quality threshold on eval suite, fall back to cloud LLM via secure tunnel if quality insufficient
- Bank procurement cycles are 6-18 months → start sales conversations in Phase 3

### Exit Criteria
- [ ] Chinese wall enforcement verified by adversarial testing (0 cross-wall data leaks)
- [ ] NICE Actimize integration operational
- [ ] SWIFT Bridge functional for payment messages
- [ ] MiFID II, DORA, GDPR modules operational
- [ ] Full on-premise deployment proven with self-hosted LLM
- [ ] 1-2 Tier 1 bank pilots in progress
- [ ] All 5 archetype profiles in OPA

### Estimated Cost: $900K–$1.4M
- 8 engineers × 26 weeks × $3K-$4K/wk: $624K-$832K
- SWIFT specialist (14 weeks × 40 hrs × $400/hr): $224K
- 2 Compliance SMEs: $156K
- QA/Eval: $65K-$91K
- Infrastructure (GPU for self-hosted LLM): $30K-$50K/month × 6: $180K-$300K
- Security/pen testing: $40K-$60K

---

## RISK REGISTER

### Top 15 Risks

| # | Risk | Probability | Impact | Phase | Mitigation |
|---|------|-------------|--------|-------|------------|
| R1 | **Schema translation errors cause silent data mismatches** | HIGH (90%) | CRITICAL | 1-2 | Automated reconciliation tests daily. Compliance SME reviews mismatches weekly. Version schema from day one. Expect 3-5 major revisions in first 3 months. |
| R2 | **Vendor API access delayed beyond 12 weeks** | HIGH (80%) | HIGH | 0-2 | Submit ALL applications in Phase 0. Build mock adapters with synthetic data. Identify vendors with sandbox environments. Fallback: use alternative data sources (Alpha Vantage instead of Bloomberg). |
| R3 | **Compliance SME unavailable or provides incorrect rules** | MEDIUM (50%) | CRITICAL | 0-5 | Identify 3 candidate SMEs. Engage backup. All rules version-controlled and tested. Quarterly compliance audit of rule accuracy. |
| R4 | **LLM output quality disappoints advisors** | HIGH (70%) | HIGH | 2-3 | Launch in "draft mode" — advisors review all outputs. Track edit rates. Do not go autonomous until edit rate <10%. Continuous prompt engineering based on feedback. |
| R5 | **Multi-agent orchestration harder than expected** | HIGH (75%) | MEDIUM | 2-3 | Start with 2 specialists (Client Service + Research). Add incrementally. Build supervisor routing tests before adding specialists. Budget 2x estimated time. |
| R6 | **SOC 2 Type II audit finds critical gaps** | MEDIUM (40%) | HIGH | 3 | Dedicated security engineer from Phase 3. Continuous evidence collection. Pre-audit readiness assessment at week 28. |
| R7 | **S3 Object Lock misconfiguration (irreversible)** | LOW (15%) | CRITICAL | 1 | Test in sandbox account ONLY. Never configure Compliance mode in production until verified. Document exact configuration steps. Two-person approval for WORM config changes. |
| R8 | **FIX protocol bridge exceeds 2x time estimate** | HIGH (70%) | MEDIUM | 4 | Hire specialist contractor. Budget 14 weeks (not 6). Build mock FIX server for testing. Accept that FIX bridge may slip to Phase 5. |
| R9 | **Regulatory uncertainty — FINRA does not bless architecture** | MEDIUM (50%) | HIGH | 0-5 | Engage FINRA Innovation Office early (Phase 0). Document all compliance design decisions. Build "compliance warranty boundary" — deterministic checks are warranted, LLM output is not. |
| R10 | **Envestnet launches competing AI before 007 reaches market** | MEDIUM (60%) | HIGH | 2-4 | Position as integration layer, not competitor. Build Envestnet adapter (wrap their API). Focus on cross-archetype capability Envestnet cannot match. Move fast on Tier 3/4 launch. |
| R11 | **Key engineer departure** | MEDIUM (40%) | HIGH | 1-5 | Document all architectural decisions. Code review by 2+ engineers. No single points of failure in team knowledge. Competitive compensation. |
| R12 | **Bloomberg API license cost prohibitive for early stage** | MEDIUM (50%) | MEDIUM | 4 | Defer Bloomberg to Phase 4. Use Alpha Vantage / Polygon as research data fallback for Phase 2-3. Bloomberg is required for Tier 1/2/5 but not Tier 3/4. |
| R13 | **Chinese wall enforcement has edge cases** | HIGH (80%) | CRITICAL | 5 | Dedicate 2 senior engineers + compliance SME. Extensive adversarial testing (200+ scenarios). Engage external pen tester specializing in FSI. Accept that edge cases will emerge post-launch — build rapid rule update pipeline. |
| R14 | **Self-hosted LLM quality insufficient for research pipeline** | MEDIUM (50%) | MEDIUM | 5 | Define minimum quality threshold on eval suite before deploying. Fall back to cloud LLM via secure tunnel if quality insufficient. Llama 3.1 405B is competitive with Claude for many tasks but may lag on financial reasoning. |
| R15 | **Customer procurement cycles longer than expected** | HIGH (70%) | MEDIUM | 2-5 | Tier 4 RIA: 2-4 weeks (fast). Tier 3 BD: 2-4 months. Tier 2 AM: 4-8 months. Tier 1 Bank: 6-18 months. Revenue projections must account for these cycles. Start Tier 2/5 sales conversations in Phase 2, not Phase 4. |

---

## DEPENDENCY TRACKER

### Vendor API Applications

| Vendor | Application Date | Expected Response | Status | Fallback Plan | Phase Needed |
|--------|-----------------|-------------------|--------|---------------|-------------|
| Schwab Advisor Services | Phase 0, Week 1 | 6-8 weeks | NOT STARTED | Mock adapter with synthetic data. Schwab API docs are partially public. | Phase 2 |
| Orion Portfolio Solutions | Phase 0, Week 1 | 4-6 weeks | NOT STARTED | Orion has open API program. Sandbox available. Mock adapter as backup. | Phase 2 |
| eMoney Advisor | Phase 0, Week 1 | 6-10 weeks | NOT STARTED | eMoney API not publicly documented (Fidelity-owned). May require Fidelity enterprise partnership. Mock adapter with synthetic plan data. | Phase 2 |
| Fidelity Integration Xchange | Phase 0, Week 2 | 6-8 weeks | NOT STARTED | Fidelity has developer program. Sandbox available. | Phase 3 |
| Smarsh | Phase 0, Week 2 | 4-6 weeks | NOT STARTED | Smarsh has open API. Global Relay as alternative. | Phase 3 |
| Salesforce FSC | Already available | N/A | AVAILABLE | 006 already integrates. AppExchange partner program is open. | Phase 1 |
| Bloomberg B-PIPE/BLPAPI | Phase 2, Week 16 | 3-6 months | NOT STARTED | Alpha Vantage / Polygon for market data. SEC EDGAR for filings. Bloomberg required for Tier 1/2/5 only. License: $24K+/yr. | Phase 4 |
| BlackRock Aladdin | Phase 3, Week 30 | 6-12 months | NOT STARTED | Aladdin is a walled garden. May require BlackRock partnership. Defer to Phase 5 if access not granted. | Phase 4-5 |
| SS&C Eze | Phase 3, Week 28 | 4-8 weeks | NOT STARTED | Requires enterprise relationship. SS&C has partner program. | Phase 4 |
| NICE Actimize | Phase 3, Week 30 | 6-12 months | NOT STARTED | Enterprise sales cycle. Start conversations early. Required for Tier 1 only. | Phase 5 |
| Backstop | Phase 3, Week 30 | 4-6 weeks | NOT STARTED | Backstop has API documentation. Hedge fund CRM. | Phase 4 |
| ComplySci | Phase 3, Week 30 | 4-6 weeks | NOT STARTED | ComplySci has API. Personal trading compliance. | Phase 4 |
| FactSet | Phase 2, Week 20 | 4-8 weeks | NOT STARTED | FactSet has developer program. Alternative: S&P Capital IQ. | Phase 4 |

### Technology Dependencies

| Dependency | Status | Risk | Mitigation |
|------------|--------|------|------------|
| OPA (CNCF) | Stable, graduated | LOW | CNCF graduated project. Styra provides commercial support. |
| LangGraph | Stable, MIT license | LOW | Active development by LangChain. Large community. |
| Strands Agents SDK | Stable, Apache 2.0 | MEDIUM | AWS-backed, 1M+ downloads. Risk: breaking changes in early versions. Pin version, test upgrades. |
| Keycloak | Stable, Apache 2.0 | LOW | CNCF-adjacent. Red Hat backing. Widely used in FSI. |
| OpenClaw | Open-source | MEDIUM | Risk: breaking changes, abandonment. Mitigation: M1-M11 are runtime-agnostic, only M12 depends on OpenClaw. |
| Bedrock AgentCore | GA (AWS) | LOW | AWS managed service. Risk: pricing changes. Mitigation: Strands deploys on any Python runtime. |
| S3 Object Lock | GA (AWS) | LOW | Core AWS service. Compliance mode is well-documented. |
| Langfuse | Open-source, MIT | MEDIUM | Self-hosted. Risk: maintenance burden. Mitigation: Langfuse Cloud as fallback. |

### Compliance Dependencies

| Dependency | Status | Risk | Mitigation |
|------------|--------|------|------------|
| FINRA Innovation Office engagement | NOT STARTED | MEDIUM | Engage in Phase 0. Informal guidance, not formal approval. |
| SOC 2 Type II auditor | NOT STARTED | LOW | Multiple auditors available (Schellman, A-LIGN, Coalfire). Engage in Phase 0. |
| Compliance SME | NOT STARTED | HIGH | Identify 3 candidates. Budget $50K-$100K Year 1. Critical path for M2/M4 rules. |
| EU regulatory counsel | NOT STARTED | MEDIUM | Needed for Phase 5 (GDPR, DORA, MiFID II). Engage in Phase 3. |
| E&O insurance | NOT STARTED | MEDIUM | Required before enterprise deployment. Engage broker in Phase 2. |

---

## COST SUMMARY

| Phase | Duration | Team Size | Estimated Cost | Cumulative |
|-------|----------|-----------|---------------|------------|
| Phase 0: Prerequisites | 4 weeks | 3 | $40K–$70K | $40K–$70K |
| Phase 1: Foundation | 12 weeks | 5 | $180K–$280K | $220K–$350K |
| Phase 2: Tier 3/4 MVP | 16 weeks | 7 | $350K–$520K | $570K–$870K |
| Phase 3: Production Hardening | 12 weeks | 10 | $480K–$720K | $1.05M–$1.59M |
| Phase 4: Tier 2/5 Expansion | 16 weeks | 10 | $600K–$900K | $1.65M–$2.49M |
| Phase 5: Tier 1 + Global | DEFERRED | — | $0 (deferred) | $2.0M–$3.0M |
| **TOTAL (18 months)** | **78 weeks** | **3→12** | **$2.55M–$3.89M** | |

### Revenue Projections (Conservative)

| Phase | Customers | Avg. ACV | ARR |
|-------|-----------|----------|-----|
| Phase 2 (Month 6) | 5 lighthouse (free/discounted) | $0-$6K | $0-$30K |
| Phase 3 (Month 9) | 20-50 Tier 3/4 | $50K-$150K | $1M-$7.5M |
| Phase 4 (Month 12) | 50-100 Tier 3/4 + 5-10 Tier 2/5 | $75K-$200K | $4.5M-$22M |
| Phase 5 (Month 18) | 100-200 Tier 3/4 + 10-20 Tier 2/5 + 1-2 Tier 1 | $100K-$500K | $12M-$50M+ |

**Break-even estimate:** Month 10-14 (Phase 3), assuming 30-50 customers at $50K+ ACV.

---

## TEAM SCALING PLAN

```
Phase 0 (Wk 0-4):    ███ (3 people)
Phase 1 (Wk 4-16):   █████ (5 people)
Phase 2 (Wk 12-28):  ███████ (7 people)
Phase 3 (Wk 24-36):  ██████████ (10 people)
Phase 4 (Wk 36-52):  ██████████ (10 people)
Phase 5 (Wk 52-78):  ████████████ (12 people)
```

### Key Hires by Phase

| Phase | Hire | Skill | Priority |
|-------|------|-------|----------|
| 0 | Compliance SME (contract) | FINRA rules, Reg BI, MNPI | P0 — blocks M2/M4 |
| 1 | DevOps/Platform Engineer | K8s, AWS, IaC, observability | P0 — blocks infrastructure |
| 2 | QA/Eval Engineer | Test automation, LLM eval, adversarial testing | P0 — blocks quality |
| 2 | Backend Engineer (memory) | Python, Redis, DynamoDB, vector DBs | P1 |
| 3 | Security Engineer | Pen testing, SOC 2, FSI security | P0 — blocks SOC 2 |
| 3 | Sales Engineer | Customer onboarding, technical support | P1 |
| 4 | FIX Protocol Specialist (contract) | FIX 4.2/4.4, session management | P0 — blocks FIX bridge |
| 5 | SWIFT Specialist (contract) | ISO 20022, SWIFT Alliance | P0 — blocks SWIFT bridge |
| 5 | EU Compliance SME (contract) | GDPR, DORA, MiFID II | P0 — blocks EU expansion |

---

## PHASE GATE CHECKLIST

Each phase requires explicit sign-off before proceeding to the next.

### Phase 0 → Phase 1 Gate
- [ ] Compliance SME onboarded
- [ ] All vendor API applications submitted
- [ ] SOC 2 auditor engaged
- [ ] 5 lighthouse customers identified
- [ ] Dev infrastructure operational

### Phase 1 → Phase 2 Gate
- [ ] Unauthorized MCP call DENIED (proven in integration test)
- [ ] WORM audit storage operational (compliance SME sign-off)
- [ ] 200+ eval queries passing
- [ ] All modules containerized with Helm charts

### Phase 2 → Phase 3 Gate
- [ ] 3-5 lighthouse customers using agent daily
- [ ] Edit rate <20%
- [ ] 750+ eval queries passing
- [ ] Memory persistence across channels proven

### Phase 3 → Phase 4 Gate
- [ ] SOC 2 Type II report issued
- [ ] 20-50 paying customers
- [ ] Edit rate <10%
- [ ] Execution specialist operational with HITL

### Phase 4 → Phase 5 Gate
- [ ] Bloomberg/FactSet adapters operational
- [ ] FIX Bridge functional
- [ ] Tier 2/5 profiles in OPA
- [ ] Hybrid topology deployed with customer
- [ ] 5+ Tier 2/5 customers in pipeline

---

> **POST-LLMJ v4 CORRECTIONS (IMPL-06):** Phase 2 extended to 24 weeks (from 16). Phase 2 lighthouse restricted to RIA-only (BDs deferred to Phase 3 when Smarsh operational). Phase 5 (Tier 1 + Global) DEFERRED from initial plan — designed but not funded. Revised budget: $2.0-3.0M (down from $2.55-3.89M). See IMPL-06 for full blocker resolution details.

*Document 3 of 3 — Project 007 v2 Architecture*
*Addressing ALL LLMJ Committee Findings: Updated Implementation Plan with Honest Timeline*