# IMPL-06: Blocker Resolution Plan

> Date: April 14, 2026
> Category: IMPLEMENTATION (how to build)
> Trigger: REV-06 LLMJ Committee v4 — 5 critical blockers identified
> Purpose: Concrete fix for each blocker + revised timeline + revised budget
> Status: Action plan for immediate execution

---

## THE ROOT CAUSE

The 5 blockers share a common origin: the architecture (ARCH-01 through ARCH-07) was designed top-down before the infrastructure research (RES-08) was done bottom-up. RES-08 revealed what the real systems look like. The corrections were identified but never applied to the architecture documents. This plan applies the corrections, resolves the blockers, and adjusts the timeline and budget to match reality.

---

## BLOCKER 1: SMARSH COMMUNICATION ARCHIVING

### The Problem

IMPL-01 puts Smarsh in Phase 3 (Weeks 24-30) but deploys lighthouse BDs in Phase 2 (Weeks 22-28). Agent-client communications at broker-dealers would flow without compliant archiving. $11B+ in SEC/FINRA fines (2024-2025) for exactly this.

### The Decision: Option B+C (lowest risk, no Phase 2 delay)

1. Phase 2 lighthouse restricted to RIA-only (Tier 4) firms
2. Build minimal archiving on M10 for Phase 2 (capture all OpenClaw messages to WORM)
3. Full Smarsh integration in Phase 3 Week 24-28
4. BDs onboarded in Phase 3 Week 28+ with full Smarsh operational

### Why Not Move Smarsh to Phase 2

Moving Smarsh to Phase 2 adds an engineer, adds a vendor dependency (4-6 week approval), and creates a new critical path item. The RIA-only restriction achieves the same regulatory safety with zero additional cost. RIAs have fiduciary duty under the Investment Advisers Act, not FINRA 2210 communication review requirements.

### Implementation

```
Phase 0 Week 2:     Submit Smarsh API application (already in IMPL-01)
Phase 1 Week 8-12:  Build minimal archiving on M10 (~200 lines Python)
Phase 2 Week 12-28: Lighthouse with RIA-only firms (3-5 Tier 4)
Phase 3 Week 24-28: Full Smarsh integration + principal review queue
Phase 3 Week 28+:   BD onboarding begins with full archiving
```

### Cost Impact: $0 additional. Risk Reduction: Eliminates regulatory violation risk.


---

## BLOCKER 2: M11 POLYGLOT ADAPTER LAYER

### The Problem

ARCH-07 declares M11 as TypeScript-only. RES-08 proves Bloomberg needs Python BLPAPI (no TypeScript SDK exists), Eze needs gRPC, FIX needs stateful TCP with QuickFIX. Line estimates of ~200 lines each are off by 4-20x for non-REST adapters.

### The Fix

Document update + interface decision. No code changes needed (M11 not built yet).

Update ARCH-07 M11 row to polyglot with sub-classifications:

| Sub-Type | Language | Vendors | Lines |
|----------|----------|---------|-------|
| M11-REST | TypeScript, MCP SDK | Salesforce, Orion, eMoney, Fidelity, Pershing, Wealthbox, Redtail, Envestnet, ComplySci, SEC EDGAR | 400-800 each |
| M11-BLPAPI | Python, blpapi SDK + MCP wrapper | Bloomberg B-PIPE | 600-800 |
| M11-gRPC | Python or TypeScript, grpcio + MCP wrapper | SS&C Eze (xAPI) | 400-600 |
| M11-FIX | Python, QuickFIX + MCP wrapper (SEPARATE MODULE M13) | Broker/exchange FIX sessions | 1,500-2,500 |
| M11-SFTP | Python, paramiko + batch parser | Schwab daily files, Fidelity daily files | 300-400 per custodian |

Common MCP interface all adapters implement regardless of language: GET /, POST /tools/list, POST /tools/call. Each adapter is its own Docker container. M6 gateway talks MCP to all of them — internal protocol is invisible.

FIX Bridge becomes M13 (separate module) given its complexity, statefulness, and need for specialist contractor.

### Cost Impact: $0 (document update only). Effort: 1 day.

---

## BLOCKER 3: M3 CANONICAL SCHEMA EXPANSION

### The Problem

6 canonical types and 200 lines YAML cannot map 17 vendor data models. Missing 12+ types. Household type is the hardest — 3 different concepts across SF FSC, Orion, and Schwab.

### The Fix (Phased)

Phase 1 Week 4-6: Define 18 type names and fields (1 week, architect + SME). New types: Household, TaxLot, Transaction, Balance, Performance, SecurityProfile, Quote, PlanSummary, Goal, InteractionSummary, ComplianceAlert, PaymentInstruction.

Phase 1 Week 6-10: Validate against real vendor data models (2 weeks). Map SF FSC and Orion API responses to canonical types. Document every semantic difference in a schema decision log.

Phase 2 Week 12-28: Iterate with real data (3-5 revisions budgeted at 1-2 weeks each = 5-10 weeks rework).

### The Household Decision

The canonical Household is a CONTAINER that holds references to vendor-specific groupings:

```yaml
Household:
  canonical_id: string (uuid)
  display_name: string
  primary_source: enum (salesforce_fsc, orion, schwab, fidelity, manual)
  members:
    - client_ref: string (canonical Client ID)
      role: enum (primary, spouse, dependent, trustee, beneficiary)
      source: string (which system defined this membership)
  vendor_mappings:
    salesforce_fsc: { household_id: "001xxx", type: "relationship" }
    orion: { household_id: "H-789", type: "portfolio_management" }
    schwab: { master_account: "SCHW-456", type: "custodial" }
  reconciliation:
    sources_agree: boolean
    discrepancies: list
    last_reconciled: datetime
```

This preserves vendor-specific semantics. When sources disagree on membership, the discrepancy is flagged for compliance SME review. OPA rules check access against canonical_id.

### Cost Basis in TaxLot Type

```yaml
TaxLot:
  cost_basis_method: enum (specific_lot, average_cost, fifo, lifo, hifo)  # REQUIRED
  source_custodian: string
  source_cost_basis_method: string  # custodian's native method name
```

M7 translators MUST set cost_basis_method. OPA rule validates it is never null. Reconciliation test compares cost basis across custodian daily file vs real-time API.

### Revised M3 Estimates

| Metric | Original | Revised |
|--------|----------|---------|
| Types | 6 | 18 |
| Lines (YAML) | ~200 | ~1,200 |
| Lines (Python validation) | 0 | ~500 |
| SME time | Not specified | 3 weeks Phase 1 + ongoing |

### Cost Impact: +$30-50K (SME time). Effort: 3-4 weeks Phase 1.

---

## BLOCKER 4: PRINCIPAL REVIEW QUEUE (FINRA 2210)

### The Problem

FINRA 2210 requires a registered principal (not the advisor) to review agent communications. Mentioned in 4 documents, designed in 0. HITL gates are advisor-level, not principal-level.

### The Fix

New OPA rule: authority/communication_review.rego (~100 lines Rego). Classifies every agent output as INSTITUTIONAL (no review) or RETAIL_COMMUNICATION (principal review required). Based on recipient type, content type, channel, archetype, registration type.

New workflow: Agent output → guardrails → OPA classification → if retail + BD: route to PRINCIPAL REVIEW QUEUE → principal approves/rejects → deliver/block → archive to Smarsh → log to WORM.

Review queue schema (DynamoDB/PostgreSQL): review_id, output_content, output_hash, advisor_id, client_id, principal_id, status (PENDING/APPROVED/REJECTED/EXPIRED), SLA deadline (4 hours async), review_token (tamper-proof).

Phasing: Build queue in Phase 1 Week 10-14. Operational for RIA lighthouse in Phase 2 (recommended not enforced). Enforced for BDs in Phase 3.

### Cost Impact: +$15-20K (2-3 weeks engineering). Effort: Built into Phase 1-2.

---

## BLOCKER 5: FIX SESSION PERSISTENCE (HYBRID TOPOLOGY)

### The Problem

ARCH-08 hybrid topology has no data store on the on-prem side. FIX requires persistent session state surviving pod restarts. Cloud PostgreSQL over VPN tunnel creates circular failure mode.

### The Fix

Update ARCH-08 hybrid topology: add minimal data zone on on-prem side.

```
FIRM'S DATA CENTER (hybrid on-prem side):
  TRUST LAYER: M1, M2/M4, M6, M10, M11
  MINIMAL DATA ZONE (new):
    PostgreSQL (small) — FIX session state, HITL gate state
    Redis (small) — working memory L1, rate limits
```

FIX Bridge (M13) uses StatefulSet with PersistentVolumeClaim for QuickFIX message store. Session state (sequence numbers) in local PostgreSQL. On pod restart: reads last sequence, sends Logon with correct sequence, gap-fill recovery works.

If tunnel down: trust layer continues operating locally. Audit writes queue locally, sync when tunnel recovers.

### Cost Impact: $0 (design update now, implementation in Phase 4). Effort: 1 day document update.

---

## ADDITIONAL FIXES (Non-Blockers)

| # | Fix | Effort | Phase |
|---|-----|--------|-------|
| 6 | Cost basis normalization in M7 spec | Included in Blocker 3 | Phase 1 |
| 7 | Settlement states in Execution Specialist (PENDING_SETTLEMENT, SETTLEMENT_FAILED) | 1 day doc update | Phase 3 |
| 8 | Bloomberg B-PIPE PrivateLink in ARCH-08 VPC endpoints table | 1 day doc update | Now |
| 9 | Phase 2 timeline: 16 weeks → 24 weeks, 5 engineers → 7 | Plan update | Before Phase 2 |
| 10 | Cut Phase 5 (Tier 1) from initial fundraise | Plan update | Phase 0 |

---

## REVISED TIMELINE

```
PHASE 0        PHASE 1            PHASE 2 (extended)       PHASE 3              PHASE 4
Prerequisites  Foundation         Tier 3/4 MVP             Production           Tier 2/5
Wk 0-4        Wk 4-18            Wk 14-36                 Wk 32-44             Wk 40-60
               (+2 wks)           (+8 wks)                 (unchanged)          (+4 wks)

              M1,M10,M3(18       M7,M11,M9,M8,M12         Smarsh,Fidelity      Bloomberg,FIX
              types),M2/M4       2 specialists             Execution Spec.      Eze,FactSet
              M5,M6,Eval         Memory L1-L4              Principal review     Tier 2/5 profiles
              Principal queue    3-5 RIA lighthouse        SOC 2 Type II        Hybrid topology
              Min. archiving     Schema iterations         BD onboarding        Pod isolation

PHASE 5 (Tier 1 + Global): DEFERRED. Designed but not funded initially.
```

---

## REVISED BUDGET

| Phase | IMPL-01 | Revised | Delta |
|-------|---------|---------|-------|
| Phase 0 | $40-70K | $40-70K | — |
| Phase 1 | $180-280K | $220-340K | +$40-60K |
| Phase 2 | $350-520K | $520-780K | +$170-260K |
| Phase 3 | $480-720K | $520-760K | +$40K |
| Phase 4 | $600-900K | $700-1,050K | +$100-150K |
| Phase 5 | $900-1,400K | $0 (DEFERRED) | -$900-1,400K |
| TOTAL | $2.55-3.89M | $2.0-3.0M | -$550-890K |

By cutting Phase 5, total budget DECREASES despite more realistic Phase 1-4 estimates. Add 15% contingency: $2.3-3.45M.

---

## THE WEDGE PRODUCT

Ship the trust layer as a standalone product at Week 14-18 (end of Phase 1):

```
"COMPLIANCE PROXY FOR MCP"

  What: M6 + M2/M4 + M1 + M10 packaged as a single Helm chart
  Does: Sits between ANY MCP client and ANY MCP server.
        Checks identity, authority, MNPI. Logs to WORM.
  Who:  Any firm deploying AI agents that access financial data via MCP
  Why:  Works with FactSet's native MCP server, OpenClaw, any MCP client
  Price: $500-2K/mo (Tier 4 RIA), $5-15K/mo (Tier 3 BD)
  Ships: Week 14-18 (IS Phase 1 — just packaged as a product)
```

Every wedge customer becomes a full platform customer when Phase 2 ships. This is how you go from zero customers to revenue before the lighthouse even deploys.

---

## EXECUTION ORDER

```
WEEK 0 (NOW):
  □ Update ARCH-07: M11 polyglot + M13 (Blocker 2)
  □ Update ARCH-08: Bloomberg PrivateLink + hybrid data zone (Blockers 5, 8)
  □ Update ARCH-03: M3 18 types, M11 estimates, M13 (Blockers 2, 3)
  □ Update ARCH-05: settlement states (Fix 7)
  □ Update IMPL-01: Phase 2 = 24 wks, RIA-only, Phase 5 deferred

WEEK 1-4 (PHASE 0):
  □ Submit all vendor API applications
  □ Hire compliance SME
  □ Identify 3-5 RIA lighthouse customers (RIA-only, not BD)

WEEK 4-8 (PHASE 1 START):
  □ M3 schema expansion: 18 types with SME co-design (Blocker 3)
  □ M1, M10, M2/M4, M5 build begins

WEEK 8-14 (PHASE 1 MID):
  □ Principal review queue (Blocker 4)
  □ Minimal archiving on M10 (Blocker 1)
  □ M6 gateway build

WEEK 14-18 (PHASE 1 END):
  □ Trust layer operational
  □ WEDGE PRODUCT: package as "Compliance Proxy for MCP"
  □ Ship to first design partner
```

---

## SUMMARY

5 blockers. All fixable. Most are document updates and design decisions, not rewrites.

| Blocker | Fix | Effort | Cost |
|---------|-----|--------|------|
| 1. Smarsh phasing | RIA-only lighthouse + minimal archiving | 1 week | $0 |
| 2. M11 polyglot | Document update | 1 day | $0 |
| 3. M3 schema expansion | 18 types + Household container + cost basis | 3-4 weeks | +$30-50K |
| 4. Principal review queue | OPA rule + workflow + queue | 2-3 weeks | +$15-20K |
| 5. FIX session persistence | Hybrid data zone design | 1 day | $0 |

Total additional cost: +$45-70K. Timeline: Phase 2 extends 8 weeks. Phase 5 deferred. Net budget decreases $550-890K.

The wedge product (Compliance Proxy for MCP) ships at Week 14-18. Revenue before lighthouse. Thesis validated with real customers. Installed base for full platform upgrade.

---

*IMPL-06 — Project 007 FSI Interoperability Platform*
*Blocker Resolution Plan*
