# REV-06: LLMJ Committee v4 — Infrastructure Reality Assessment

> Date: April 14, 2026
> Category: REVIEW (quality gate)
> Trigger: RES-08 Financial Infrastructure Deep Research (17 systems, 10 critical findings)
> Reviewers: 5 LLMJ specialists
> Documents Reviewed: RES-08, ARCH-03, ARCH-05, ARCH-06, ARCH-07, ARCH-08, IMPL-01, REV-05
> Verdict: CONDITIONAL GO — 5 critical blockers must be resolved before Phase 2 lighthouse

---

## COMMITTEE SCORES

| Reviewer | Role | Score | Verdict |
|----------|------|-------|---------|
| Reviewer 1 | Infrastructure Realist | 5.3/10 | Architecture directionally sound, 3 critical design flaws |
| Reviewer 2 | Compliance Hardliner | 4.7/10 | Phasing will get you sanctioned. Move Smarsh to Phase 2. |
| Reviewer 3 | Network Security Architect | 5.0/10 | Cloud REST topology is 7/10. Hybrid + non-REST is 3/10. |
| Reviewer 4 | Build Feasibility Engineer | 4.1/10 | Timelines are 60-70% of reality. Budget $1M+ short. |
| Reviewer 5 | Strategic Moat Analyst | 6.4/10 | Investable with conditions. Architecture A+, go-to-market C-. |
| COMMITTEE AVERAGE | | 5.1/10 | CONDITIONAL GO |

---

## TOP 5 CRITICAL BLOCKERS

### BLOCKER 1: Smarsh Must Move to Phase 2

Source: Reviewer 2 (Compliance Hardliner), Score 3/10

IMPL-01 puts Smarsh in Phase 3 (Weeks 24-30) but deploys lighthouse BDs in Phase 2 (Weeks 22-28). That creates a window where agent-client communications at broker-dealers are NOT archived to a compliant system. $11B+ in SEC/FINRA fines (2024-2025) for exactly this failure. Deploying to BDs without communication archiving is not a risk — it is a violation.

Resolution: Either move Smarsh integration to Phase 2 (start Week 14-16, operational by Week 22) OR restrict Phase 2 lighthouse to RIA-only firms (Tier 4) where FINRA 2210 requirements are less stringent.

### BLOCKER 2: M11 Must Be Declared Polyglot

Source: Reviewers 1, 3, 4 (unanimous)

ARCH-07 says M11 is TypeScript-only. RES-08 proves Bloomberg needs Python BLPAPI (no TypeScript SDK exists), Eze needs gRPC, FIX needs stateful TCP with QuickFIX (Java/Python). Line estimates of "~200 lines each" are off by 4-20x for non-REST adapters. Bloomberg adapter: 1,500-2,500 lines Python. FIX Bridge: 2,000-4,000 lines.

Resolution: Update ARCH-07 immediately. Declare M11 polyglot. Sub-classify adapters: M11-REST (TypeScript), M11-BLPAPI (Python), M11-gRPC (Python/TypeScript), M11-FIX (Python/Java). Consider FIX Bridge as separate module M13.

### BLOCKER 3: M3 Schema Must Expand to 18+ Types

Source: Reviewer 1 (Infrastructure Realist), Score 4/10

6 canonical types (Client, Holding, Order, ResearchBrief, ComplianceCheck, AuditEntry) and 200 lines YAML cannot map 17 vendor data models. Missing types: Household, TaxLot, Transaction, Balance, Performance, SecurityProfile, Quote, PlanSummary, Goal, InteractionSummary, ComplianceAlert, PaymentInstruction. Realistic estimate: 1,000-1,500 lines YAML + 500 lines Python validation.

Resolution: Expand M3 in Phase 1 with compliance SME co-design (2-3 weeks dedicated). The Household type is the hardest — 3 different concepts across SF FSC, Orion, and Schwab. Budget for 3-5 revisions.

### BLOCKER 4: Principal Review Queue Must Be Designed

Source: Reviewer 2 (Compliance Hardliner), Score 5/10

FINRA 2210 requires a registered principal (not the advisor) to review agent communications before delivery to clients. Mentioned in 4 architecture documents, designed in 0. The HITL gates in Research and Execution Specialists are advisor-level approval, not principal-level supervisory review. These are different people with different regulatory obligations.

Resolution: Design a dedicated principal review queue with: OPA rule blocking delivery until principal approval (for pre-use mode), tamper-proof approval tokens, Smarsh integration for archival, and escalation path for rejections.

### BLOCKER 5: FIX Session Persistence for Hybrid Topology

Source: Reviewer 3 (Network Security Architect), Score 3/10

Hybrid topology (ARCH-08 Section 2.5) places M11 on-prem but shows no data store on the on-prem side. FIX protocol requires persistent session state (sequence numbers, message store) that survives pod restarts. If state is in cloud PostgreSQL, tunnel failure = FIX recovery failure (circular dependency). If state is local, it's not designed.

Resolution: Add local PostgreSQL or PersistentVolume to hybrid topology on-prem side. FIX Bridge must use StatefulSet (not Deployment) with PersistentVolumeClaim. Document in ARCH-08.

---

## DETAILED REVIEWER FINDINGS

### Reviewer 1: Infrastructure Realist (5.3/10)

| Dimension | Score | Key Finding |
|-----------|-------|-------------|
| M11 Adapter Realism | 3/10 | TypeScript-only is broken. Line estimates off 3-10x for non-REST. |
| M7 Translator Complexity | 4/10 | ~100 lines each is off 3-7x. Household/cost basis are landmines. |
| M6 Gateway Load | 6/10 | Viable for REST Phase 2. Needs protocol-aware evolution by Phase 4. |
| Vendor Approval Timeline | 5/10 | Fidelity/SOC2 chicken-and-egg not resolved. eMoney may be blocked. |
| M3 Schema Scope | 4/10 | 6 types for 17 vendor models. Needs 18+ types, 1,000+ lines. |
| Overall Architecture Fit | 6/10 | Missing: batch reconciliation, identifier cross-ref, data freshness, events. |

Top recommendation: Apply RES-08 corrections to ARCH-03 and ARCH-07 before writing any M11 or M7 code. Add batch reconciliation module for custodian SFTP files.

### Reviewer 2: Compliance Hardliner (4.7/10)

| Dimension | Score | Key Finding |
|-----------|-------|-------------|
| Smarsh Integration Urgency | 3/10 | Phase 3 is too late. BD deployment without archiving = violation. |
| Cost Basis Regulatory Risk | 4/10 | Not designed, not enforced, not tested. Silent errors waiting. |
| Supervisory Review (2210) | 5/10 | Mentioned 4 places, designed 0. No principal review queue. |
| Household MNPI Leakage | 6/10 | Enforcement exists (M2/M4) but household reconciliation undesigned. |
| T+1 Settlement Compliance | 5/10 | State machine lacks settlement states, failure handling, reconciliation. |
| BSA/AML Gaps | 7/10 | Strongest compliance design. Missing CTR filing format, 314(a). |
| Overall Compliance Readiness | 4/10 | Not ready for FINRA exam as phased. Resequence or restrict. |

Top recommendation: Do not deploy to any BD until Smarsh and principal review queue are operational. Restrict Phase 2 to RIA-only if Smarsh cannot be accelerated.

### Reviewer 3: Network Security Architect (5.0/10)

| Dimension | Score | Key Finding |
|-----------|-------|-------------|
| Bloomberg B-PIPE PrivateLink | 5/10 | Missing from VPC endpoint table. RES-08 flagged it, ARCH-08 not updated. |
| Multi-Protocol Security | 4/10 | Only REST/mTLS designed. BLPAPI, gRPC, FIX security absent. |
| Hybrid Topology Tier 2/5 | 6/10 | Works for REST. Breaks for B-PIPE (tunnel dependency) and FIX (no data zone). |
| NAT Gateway Single Egress | 5/10 | Functional but under-designed. No per-AZ docs, no IP lifecycle runbook. |
| Multi-Tenant Isolation | 6/10 | Namespace solid. PrivateLink cross-tenant and Redis key prefix are gaps. |
| FIX Session Persistence | 3/10 | Not designed. Hybrid has no on-prem data store. Pod restart = outage. |
| SOC 2 Readiness | 6/10 | Passes for cloud REST. Fails for hybrid + non-REST. 7 audit findings. |

Top recommendation: Design non-REST protocol security models before Phase 4. Add on-prem data zone to hybrid topology. Enable VPC Flow Logs for east-west traffic monitoring.

### Reviewer 4: Build Feasibility Engineer (4.1/10)

| Dimension | Score | Key Finding |
|-----------|-------|-------------|
| Phase 2 Timeline | 4/10 | 16 weeks is 60-70% of reality. Realistic: 24-28 weeks. |
| Adapter Complexity | 3/10 | "~200 lines" off by 4-20x. Bloomberg: 1,500-2,500. FIX: 2,000-4,000. |
| Team Skill Gaps | 4/10 | Phase 1-2 buildable. Phase 4-5 needs 3-4 rare specialists. |
| Vendor Dependencies | 3/10 | 2 of 4 Phase 2 vendors will be mock-only at lighthouse launch. |
| Schema Iteration Cost | 5/10 | 3-5 revisions = 5-10 weeks unplanned rework. Not budgeted. |
| Cost Accuracy | 5/10 | $2.55M low end is fantasy. Realistic: $3.5-4.5M + contingency. |
| Overall Feasibility | 5/10 | Buildable but not as planned. Extend timelines, add engineers, cut scope. |

Top recommendation: Extend Phase 2 to 24 weeks. Add 2 engineers. Cut eMoney from Phase 2 MVP. Cut Phase 5 (Tier 1) from initial fundraise. Budget $4M-5M for first 24 months.

### Reviewer 5: Strategic Moat Analyst (6.4/10)

| Dimension | Score | Key Finding |
|-----------|-------|-------------|
| FactSet MCP Validation | 7/10 | Validates thesis. Reframe M6 as the product, not M11. |
| Envestnet/Orion Threat | 5/10 | Biggest competitive risk. Cross-archetype moat theoretical until proven. |
| Trust Layer as Moat | 7/10 | Moat is encoded knowledge (Rego, schema, profiles), not OSS tools. |
| Multi-Protocol Complexity | 6/10 | Barrier but acquirable. Vendor relationships matter more than code. |
| SaaS vs On-Prem Tension | 5/10 | Three topologies = unfocused. Pick cloud. Ship it. Expand later. |
| Time-to-Market Risk | 4/10 | Existential. 15-21 month plan vs competitors shipping quarterly. |
| Overall Strategic | 6.4/10 | Investable with conditions. Ship trust layer as wedge in 12 weeks. |

Top recommendation: Stop designing. Start shipping. Get M6+M2/M4+M10 into a design partner's hands within 12 weeks. Ship the trust layer as a standalone "compliance proxy for MCP" — a wedge product that generates revenue and validates the thesis.

---

## WHAT ALL 5 REVIEWERS AGREE ON

1. The trust layer (M1+M2+M4+M6+M10) is the right architecture and the real moat
2. FactSet's MCP server validates the pattern — M6 becomes MORE valuable as vendors ship native MCP
3. The Rego rule corpus (2,100+ lines, 5 archetypes, 7 compliance regimes) is genuinely hard to replicate
4. The canonical schema (especially Household) is the hardest unsolved problem
5. Compliance must come before deployment — regulators don't give partial credit for good architecture
6. Cost and timeline estimates are 30-40% optimistic
7. Zero customers is the existential risk — ship something within 12 weeks

---

## 10 ACTIONS (Priority Order)

| # | Action | Owner | Deadline | Blocker? |
|---|--------|-------|----------|----------|
| 1 | Move Smarsh to Phase 2 OR restrict lighthouse to RIA-only | Architect | Before Phase 2 | YES |
| 2 | Update ARCH-07: M11 is polyglot (TS + Python + gRPC) | Architect | This week | YES |
| 3 | Expand M3 to 18+ canonical types with compliance SME | Architect + SME | Phase 1 Wk 4-8 | YES |
| 4 | Design principal review queue (FINRA 2210) | Architect + SME | Phase 1 Wk 8-12 | YES |
| 5 | Design FIX session persistence for hybrid topology | Architect | Phase 1 Wk 12-16 | YES |
| 6 | Add cost basis normalization to M7 translator spec | Architect + SME | Phase 1 Wk 6-10 | NO |
| 7 | Add settlement states to Execution Specialist | Architect | Phase 2 | NO |
| 8 | Add Bloomberg B-PIPE PrivateLink to ARCH-08 | Architect | This week | NO |
| 9 | Extend Phase 2 to 24 weeks, add 2 engineers | PM | Before Phase 2 | NO |
| 10 | Cut Phase 5 (Tier 1) from initial fundraise | BD Lead | Phase 0 | NO |

---

## COMMITTEE DECISION: CONDITIONAL GO

Score: 5.1/10 (up from v1: 5.1, v2: 7.5, v3: 8.2 — this is a DIFFERENT assessment against infrastructure reality, not a regression)

Proceed to Phase 0 with conditions:
- Resolve all 5 blockers before Phase 2 code begins
- Apply 10 actions in priority order
- Resubmit updated ARCH-03, ARCH-07, ARCH-08, IMPL-01 for re-review
- Next LLMJ review: after Phase 1 completion

The architecture is the best-designed FSI interoperability platform any reviewer has seen. The gap is between design and operational reality. Close that gap and this is a 7+.

---

*REV-06 — Project 007 FSI Interoperability Platform*
*LLMJ Committee v4 — Infrastructure Reality Assessment*
*5 reviewers, 35 dimensions scored, 5 blockers, 10 actions*
