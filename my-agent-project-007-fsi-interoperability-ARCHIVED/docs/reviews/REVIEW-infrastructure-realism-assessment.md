# LLMJ Review: Infrastructure Realism Assessment

> Reviewer: LLMJ Reviewer 1 — "Infrastructure Realist"
> Background: Senior integration architect, custodian and market data integrations at 3 wealth management firms
> Date: July 2026
> Documents Reviewed: RES-08, ARCH-03, ARCH-07, IMPL-01-v2
> Verdict: Architecture is directionally sound but has 3 critical design flaws that will cause integration failures if not corrected before Phase 2.

---

## OVERALL SCORE: 5.3 / 10

The team has done exceptional research (RES-08 is one of the best FSI infrastructure surveys I have seen from a startup). The problem is that the architecture documents (ARCH-03, ARCH-07) were written BEFORE that research was completed, and the corrections identified in RES-08 Part 14 have not yet been applied. The result is an architecture that knows what is wrong with itself but has not yet fixed it.

I am scoring against what is written in ARCH-03 and ARCH-07 today, not what they could become after corrections.

---

## DIMENSION 1: M11 ADAPTER REALISM

### Score: 3 / 10 — CRITICALLY BROKEN AS DESIGNED

**What ARCH-07 says:**
- M11 language: TypeScript/Node
- Framework: MCP SDK (@modelcontextprotocol)
- ARCH-03 estimates: ~200 lines each

**What RES-08 reveals:**
- Bloomberg B-PIPE uses BLPAPI — a proprietary binary protocol with SDKs in Python, Java, C++, and C#. There is NO TypeScript BLPAPI SDK. Period. You cannot wrap Bloomberg in TypeScript.
- SS&C Eze xAPI uses gRPC with proto file definitions. While gRPC stubs CAN be generated for TypeScript (via grpc-js), the Eze ecosystem is Python/Java-centric. Proto compilation and client generation adds significant complexity.
- FIX protocol requires stateful TCP session management with sequence numbers, heartbeat, gap-fill recovery, and message persistence. This is fundamentally incompatible with a stateless MCP request/response wrapper at ~200 lines. QuickFIX libraries exist in Java and Python (mature) — not TypeScript.
- Schwab requires REST + SFTP file ingestion for daily reconciliation. SFTP batch processing is not a "wrap a REST API" problem.

**RES-08 itself says this (Finding 2, Part 14):**
> "M11 is NOT TypeScript-only. Must be polyglot: TypeScript (REST), Python (BLPAPI), gRPC (Eze)."

**The line estimates are also broken:**
- REST API wrappers (Salesforce, Orion, eMoney): ~200 lines is plausible for a thin MCP wrapper IF you exclude auth token management, pagination, rate limit handling, retry logic, error mapping, and SFTP ingestion. With those: 400-600 lines each.
- Bloomberg BLPAPI adapter: RES-08 itself corrects this to ~500 lines. I would estimate 600-800 lines including subscription management, field catalog mapping, and reference data vs. pricing separation.
- FIX Bridge: RES-08 corrects to ~1,000+ lines. Realistic estimate with session state persistence, gap-fill, heartbeat, and message store: 1,500-2,500 lines. This is not an "adapter" — it is a stateful protocol bridge.
- Schwab (REST + SFTP): ~400-500 lines (REST wrapper + SFTP file parser + reconciliation logic).

**What needs to change:**
1. M11 must be declared polyglot in ARCH-07. TypeScript for REST-based vendors. Python for Bloomberg (BLPAPI) and potentially FIX (QuickFIX). The MCP SDK wrapper can still be TypeScript, but the underlying protocol client must be in the language the vendor SDK supports.
2. Introduce an M11 sub-classification:
   - M11-REST: TypeScript MCP wrapper over REST APIs (~400-600 lines each)
   - M11-BLPAPI: Python MCP wrapper over Bloomberg binary protocol (~600-800 lines)
   - M11-gRPC: TypeScript or Python MCP wrapper over Eze proto stubs (~400-600 lines)
   - M11-FIX: Python/Java FIX Bridge with persistent session state (~1,500-2,500 lines)
   - M11-SFTP: Batch file ingestion module for custodian daily files (~300-400 lines)
3. The FIX Bridge should arguably be its own module (M13) given its complexity, statefulness, and the need for a specialist contractor. It is architecturally different from every other adapter.
4. ARCH-03's dependency matrix shows M11 only depends on M7. The FIX Bridge also needs DynamoDB/PostgreSQL for session state persistence (sequence numbers survive pod restarts). This dependency is missing.


---

## DIMENSION 2: M7 TRANSLATOR COMPLEXITY

### Score: 4 / 10 — SIGNIFICANTLY UNDERESTIMATED

**What ARCH-03 says:**
- M7 Schema Translators: ~100 lines each
- "One per vendor system (~15-20 translators)"

**What RES-08 reveals about the actual translation problems:**

**Problem 1 — Household Model Mismatch (RES-08 Finding 5):**
- Salesforce FSC: Household is a custom object with a member junction table (Household → HouseholdMember → PersonAccount)
- Orion: Household is a hierarchical client grouping (Representative → Client/Household → Portfolio → Account)
- Schwab: Household is a "master account" grouping
- These are three fundamentally different data models for the same concept. The M7 translator for each vendor must map its household concept to M3's canonical Household type. RES-08 predicts "3-5 revisions of the canonical Household type." I have seen this take 6-8 revisions at firms I have worked at. The household mapping alone is 50-100 lines per vendor, with extensive edge cases (what happens when a client belongs to multiple households in one system but not another?).

**Problem 2 — Cost Basis Normalization (RES-08 Finding 6):**
- Schwab: specific lot identification (default)
- Fidelity: average cost for mutual funds, specific lot for equities
- Orion: reflects whatever the custodian feed provides
- Getting cost basis wrong means incorrect tax reporting, which is a regulatory violation. The M7 translator must normalize cost basis method per holding, per asset class, per custodian. This is not a field mapping — it is a business logic transformation with regulatory implications. Each cost basis translator needs 80-150 lines of logic plus extensive test coverage.

**Problem 3 — MarketValue Ambiguity (RES-08, Orion section):**
- "MarketValue field — does it include accrued interest? Must document per custodian feed."
- This is a classic integration landmine. Orion MarketValue for a bond position may or may not include accrued interest depending on the custodian feed configuration. Schwab and Fidelity handle this differently. If M7 does not normalize this, portfolio valuations will be wrong by the accrued interest amount — potentially thousands of dollars per position for fixed income.

**Problem 4 — Identifier Mapping:**
- Schwab uses: Schwab account number, CUSIP, ticker
- Fidelity uses: Fidelity account number, CUSIP, SEDOL
- Orion uses: Orion internal IDs, linked to custodian account numbers
- Salesforce FSC uses: Salesforce record IDs
- Bloomberg uses: Bloomberg ticker ("NVDA US Equity"), FIGI
- M7 translators need a shared cross-reference service to map between identifier systems. This is not in any module.

**Realistic line estimates per translator:**
- Simple REST vendor (Wealthbox, Redtail, SEC EDGAR): 150-250 lines
- Medium complexity (Salesforce FSC, Orion, eMoney): 400-700 lines (household mapping, cost basis, MarketValue normalization, identifier cross-reference)
- High complexity (Schwab, Fidelity — custodians with batch + real-time + cost basis): 600-1,000 lines
- Bloomberg: 500-800 lines (10,000+ field catalog, reference data vs. pricing separation, security identifier mapping)

**The "~100 lines each" estimate is off by 3-7x for any vendor that touches positions, cost basis, or household data.** Only the simplest CRM-to-canonical-Client mappings might approach 100 lines, and even those need error handling and null-field logic.

**What needs to change:**
1. Revise M7 estimates in ARCH-03 to 300-800 lines per translator (average ~500).
2. Create a shared M7 utility library for common operations: identifier cross-reference, cost basis normalization, household mapping, MarketValue normalization. This library will be ~500-800 lines itself.
3. Budget for a "reconciliation test harness" (already mentioned in IMPL-01 deliverable 1.7) that runs daily automated comparisons between vendor data and canonical output. This is not optional — it is how you catch the translation bugs that WILL exist.
4. The compliance SME must sign off on every cost basis and household mapping. These are not engineering decisions — they are regulatory decisions.


---

## DIMENSION 3: M6 GATEWAY LOAD

### Score: 6 / 10 — VIABLE BUT NEEDS PROTOCOL-AWARE ROUTING

**What ARCH-03 says:**
- M6: Trust-Aware MCP Gateway, ~600 lines
- "Central hub — every MCP call passes through, enforces trust"
- Depends on: M1 (identity), M2 (authority), M4 (MNPI), M10 (audit)
- Used by: agent runtime — all MCP calls route here

**What RES-08 reveals about the load profile:**

The protocol map (RES-08 Part 12) shows 17+ vendor systems with:
- 13 REST/JSON APIs (standard HTTP request/response)
- 1 BLPAPI (proprietary binary, subscription-based streaming)
- 1 gRPC (binary, potentially streaming)
- 1 FIX (stateful TCP, persistent session, NOT request/response)
- 1 MCP native (FactSet — passes through directly)
- Various auth models: OAuth 2.0, API key, session auth, PKI/BIC, IAM/SigV4, license+cert
- Various rate limits: SEC EDGAR at 10 req/s, vendor-specific throttling

**The single-gateway design works for REST APIs.** M6 as a FastAPI middleware that checks identity → authority → MNPI → routes to M11 → filters response → audits is a clean pattern for synchronous HTTP request/response. For 13 REST vendors, this is fine.

**The single-gateway design breaks for non-REST protocols:**
- Bloomberg B-PIPE subscriptions are long-lived streaming connections. You do not "route a call" through M6 — you subscribe to a data feed and receive continuous updates. M6 would need to manage subscription lifecycle, not just request/response.
- FIX sessions are persistent TCP connections with state. M6 cannot "route" a FIX message the same way it routes an HTTP request. The FIX Bridge needs its own session management that is independent of M6's request lifecycle.
- gRPC can be unary (like REST) or streaming. If Eze uses streaming RPCs, M6 needs to handle that.

**However, the trust enforcement (M1/M2/M4/M10) still applies to all protocols.** The question is whether M6 enforces trust as a synchronous middleware (current design) or as a policy enforcement point that different protocol handlers call into.

**Realistic assessment:**
- M6 at 600 lines is plausible for REST-only Phase 2 (Salesforce, Orion, eMoney, Schwab REST API, SEC EDGAR). This covers the Tier 3/4 MVP.
- By Phase 4 (Bloomberg, FIX, Eze), M6 needs to evolve into a trust enforcement library that protocol-specific handlers call, not a single HTTP gateway that everything passes through.
- The circuit breaker, retry, and rate limiting logic in M6 must be per-vendor configurable (SEC EDGAR's 10 req/s is very different from Orion's rate limits).

**What needs to change:**
1. Rename M6 from "Trust-Aware MCP Gateway" to "Trust Enforcement Layer" and design it as both a gateway (for REST) and a library (for non-REST protocols).
2. Add per-vendor rate limit configuration to M5 enterprise config.
3. For Phase 4, the FIX Bridge and Bloomberg adapter should call M6's trust functions (identity verify, authority check, MNPI filter, audit log) as library calls, not route through M6 as HTTP middleware.
4. 600 lines is realistic for Phase 2. Budget 1,000-1,200 lines by Phase 4 with protocol-aware routing.

---

## DIMENSION 4: VENDOR APPROVAL TIMELINE

### Score: 5 / 10 — PARTIALLY ACCOUNTED FOR, CRITICAL GAPS REMAIN

**What IMPL-01 says:**
- Phase 0 Week 1: Submit Schwab, Orion, eMoney applications
- Phase 0 Week 2: Submit Fidelity, Smarsh applications
- Phase 2 Week 16: Start Bloomberg conversations
- Phase 3 Week 28-30: Start SS&C Eze, NICE Actimize, Backstop, ComplySci conversations

**What RES-08 reveals about actual timelines:**
- Schwab: 6-8 weeks for approval + SOC 2 Type II may be required for production access
- Fidelity: 6-12 MONTHS for new fintech vendors (longest in the industry)
- Bloomberg: Enterprise license negotiation, 3-6 months, $24K+/yr minimum
- NICE Actimize: 6-12 month enterprise sales cycle
- SS&C Eze: 4-8 weeks but requires enterprise relationship

**Gap 1 — Fidelity timeline vs. IMPL-01 Phase 3:**
IMPL-01 schedules the Fidelity adapter (deliverable 3.1) for weeks 24-28. Fidelity application is submitted Phase 0 Week 2. If Fidelity takes the full 12 months, approval arrives at Week 52 — that is Phase 4, not Phase 3. Even at 6 months, approval arrives at Week 26, leaving only 2 weeks to build the adapter before Phase 3 ends. The plan says "build mock adapter with synthetic data" as mitigation, but the Phase 3 exit criteria include "Fidelity adapter functional" without specifying "real or mock." This ambiguity will cause confusion.

**Gap 2 — SOC 2 Type II as a prerequisite:**
RES-08 notes that both Schwab and Fidelity may require SOC 2 Type II for production API access. IMPL-01 schedules SOC 2 completion in Phase 3 (weeks 24-36). But Schwab production API access is needed in Phase 2 (weeks 12-28). If Schwab requires SOC 2 before granting production access, the entire Phase 2 MVP runs on mock data. This is a potential showstopper that is not called out.

**Gap 3 — Bloomberg negotiation start time:**
IMPL-01 starts Bloomberg conversations at Phase 2 Week 16. RES-08 says 3-6 months for enterprise negotiation. That means Bloomberg access arrives weeks 28-40. IMPL-01 schedules the Bloomberg adapter for Phase 4 weeks 36-44. If negotiation takes 6 months, access arrives at week 40 — leaving only 4 weeks to build the adapter. The dependency tracker shows this but does not flag the tight margin.

**Gap 4 — eMoney is Fidelity-owned:**
The dependency tracker notes: "eMoney API not publicly documented (Fidelity-owned). May require Fidelity enterprise partnership." If eMoney access is gated behind the Fidelity relationship, the 6-12 month Fidelity timeline may also block eMoney. This would remove one of the four Phase 2 vendor integrations.

**What needs to change:**
1. Add explicit "real vs. mock" acceptance criteria for every adapter deliverable. "Functional" must be defined.
2. Investigate whether Schwab grants sandbox/limited production access before SOC 2 completion. If not, Phase 2 MVP is mock-only for custodian data — which significantly reduces the value of lighthouse deployments.
3. Move Bloomberg enterprise conversations to Phase 1 (not Phase 2 Week 16). Every week of delay compresses Phase 4.
4. Investigate eMoney API access independently of Fidelity. If they are coupled, the Phase 2 plan needs a fallback (MoneyGuidePro? RightCapital?).
5. Add a "vendor access Gantt chart" to IMPL-01 that overlays application timelines with adapter build timelines. The current table format makes it hard to see the conflicts.


---

## DIMENSION 5: SCHEMA TRANSLATION RISK (M3 Canonical Schema)

### Score: 4 / 10 — DANGEROUSLY UNDERSCOPED

**What ARCH-03 says:**
- M3: Canonical Schema Registry, BUILD ~200 lines YAML
- Defines: Client, Holding, Order, ResearchBrief, ComplianceCheck, AuditEntry
- "System-agnostic FSI data types + field semantics"

**What RES-08 reveals about the data models M3 must unify:**

Salesforce FSC data model:
- PersonAccount/Contact → FinancialAccount → FinancialAccountRole (junction) → FinancialHolding → Securities
- Household → HouseholdMember (junction to PersonAccount)
- FinancialGoal, InteractionSummary, Rollup

Orion data model:
- Representative → Client/Household → Portfolio → Account → Position → TaxLot
- Custom Fields per entity
- Performance (TWR, IRR, benchmarks, attribution)
- Billing (fee schedules, AUM calculations)

Schwab data model:
- Account → Positions → TaxLots
- Account → Transactions
- Account → Balances (cash, margin, total value)
- "Master account" household grouping

Fidelity data model:
- Account data (balances, beneficiaries)
- Position data (holdings, cost basis, unrealized G/L)
- "Relationship grouping" for households

Bloomberg data model:
- Security identifier + field list (10,000+ fields)
- Reference data separate from pricing
- No "client" or "household" concept — pure market data

**The 6 canonical types listed in ARCH-03 are insufficient.**

Missing types that RES-08 implies are needed:
- Household (the most contentious type — 3 different models)
- TaxLot (critical for cost basis normalization)
- Transaction (trade history, dividends, fees — different from Order)
- Balance (cash, margin, total value — custodian-specific)
- Performance (TWR, IRR — Orion-specific but needed for reporting)
- SecurityProfile (Bloomberg reference data — fundamentals, corporate actions)
- Quote (real-time pricing — Bloomberg/FactSet)
- PlanSummary (eMoney financial plans — already referenced in ARCH-03 call flow but not in M3 type list)
- Goal (FSC FinancialGoal)
- InteractionSummary (meeting notes — FSC)
- ComplianceAlert (NICE Actimize alerts)
- PaymentInstruction (SWIFT ISO 20022)

That is 12 additional types beyond the 6 listed. Each type needs field definitions with semantic annotations, versioning (semver), validation rules, nullable field handling, and unit specifications (currency, percentage, basis points).

~200 lines of YAML for 6 types is ~33 lines per type. A realistic canonical type definition with field names, types, descriptions, validation rules, nullable flags, and unit specs is 40-80 lines per type. For 18 types: 720-1,440 lines of YAML.

But the YAML is the easy part. The hard part is the semantic decisions:
- What is the canonical definition of "MarketValue"? Does it include accrued interest?
- What is the canonical cost basis method? Do we store the method alongside the value?
- How does the canonical Household handle a client who appears in multiple vendor households?
- What is the canonical security identifier? CUSIP? FIGI? ISIN? All three?

These decisions require the compliance SME, and each one will be debated and revised.

**What needs to change:**
1. Expand M3 type list from 6 to 18+ types. The call flow in ARCH-03 already references PlanSummary — it should be in M3.
2. Revise estimate from ~200 lines YAML to ~1,000-1,500 lines YAML (schema definitions) + ~500 lines Python (validation logic, version management, breaking change detection).
3. Budget 2-3 weeks of dedicated compliance SME time for schema design in Phase 1. This is not an engineering task — it is a domain modeling task.
4. Add a "schema decision log" that records why each semantic choice was made (e.g., "MarketValue excludes accrued interest because Schwab's feed excludes it and they are the largest custodian for our target market").
5. Plan for the 3-5 revisions RES-08 predicts. Version from day one. Breaking change detection in CI (already in IMPL-01 deliverable 1.3 — good).

---

## DIMENSION 6: OVERALL ARCHITECTURE FIT

### Score: 6 / 10 — DIRECTIONALLY CORRECT, STRUCTURALLY INCOMPLETE

**What works well:**

1. The trust layer (M1/M2/M4/M6/M10) is the right architecture. Identity → Authority → MNPI → Audit as a mandatory pipeline for every data access is exactly what regulated financial services needs. This is the moat, and it is well-designed.

2. The MCP adapter pattern is validated. FactSet launching a native MCP server (RES-08 Finding 1) proves the thesis. The pattern of wrapping vendor APIs in MCP servers and routing through a trust gateway is sound.

3. The phased approach by archetype tier is smart. Starting with Tier 3/4 (REST-only, simpler compliance) and expanding to Tier 2/5 (non-REST protocols, pod isolation) and Tier 1 (Chinese walls, SWIFT) is the right sequencing.

4. The build order (Phase 0-6 in ARCH-03) is correct. Schema + Config first, then Identity + Audit, then Trust layer, then Adapters, then Intelligence. You cannot build adapters before you have a schema to translate to.

5. RES-08 is exceptional research. The team clearly understands the infrastructure they are connecting to. The corrections in Part 14 are honest and accurate.

**What is missing or over-engineered:**

1. **Missing: Batch/reconciliation module.** RES-08 reveals that custodians (Schwab, Fidelity) deliver daily batch files via SFTP. These are the source of truth for positions, cost basis, and tax lots. The architecture has no module for batch file ingestion and reconciliation. M11 is designed as a real-time MCP adapter, not a batch processor. Recommendation: Add M14 (Batch Reconciliation Engine) or extend M11 with a batch ingestion sub-pattern. This is critical for Tier 3/4 where daily SFTP files are how most firms actually get their data.

2. **Missing: Identifier cross-reference service.** Every vendor uses different identifiers (Schwab account number vs. Orion internal ID vs. Salesforce record ID vs. CUSIP vs. FIGI vs. Bloomberg ticker). M7 translators need a shared cross-reference service to map between identifier systems. This is not in any module. Recommendation: Add this as a sub-service of M3 or a new M15.

3. **Missing: Data freshness/staleness tracking.** When M6 returns a canonical Holding, how old is the data? Real-time from Orion API? Yesterday's SFTP file from Schwab? Last week's eMoney plan? The agent needs to know data freshness to make appropriate decisions (e.g., do not execute a trade based on stale position data). No module tracks this.

4. **Over-engineered: 12 modules for Phase 2.** The call flow in ARCH-03 shows "all 12 modules touched for a single request." For a Tier 3/4 MVP, this is a lot of moving parts. The trust layer (M1/M2/M4/M6/M10) is 5 modules that must all work correctly for any request to succeed. Consider whether M2 and M4 can be a single module in Phase 1-2 (they both use OPA, both depend on M1 and M5, and are always called together by M6).

5. **Missing: Webhook/event handling.** RES-08 notes that Orion has webhooks for data change events. The architecture is entirely pull-based (agent requests data through M6). There is no event ingestion pattern for push-based data updates. For Phase 2 this is fine (polling works), but by Phase 3-4 with 20-50 customers, polling 4+ vendor APIs per customer will not scale.

6. **The FactSet native MCP server creates an architectural question.** If FactSet already has an MCP server, does it go through M11 (007's adapter) or directly through M6 (gateway)? ARCH-03 shows M6 → M11 → M7 → M3 as the call chain. But FactSet's MCP server already returns data in FactSet's format — M7 still needs to translate it to canonical. The architecture needs to handle "native MCP vendors" as a distinct pattern from "007-wrapped vendors."

**What is the real module count?**

The 12-module architecture is conceptually clean but practically needs 14-16 modules by Phase 4:
- M1-M12 as designed (with corrections above)
- M13: FIX Bridge (too complex and stateful to be an M11 adapter)
- M14: Batch Reconciliation Engine (SFTP file ingestion + daily reconciliation)
- M15: Identifier Cross-Reference Service (or fold into M3)
- M16: Event/Webhook Ingestion (or fold into M6 as Phase 3 extension)

---

## SUMMARY TABLE

| Dimension | Score | Verdict |
|-----------|-------|---------|
| 1. M11 Adapter Realism | 3/10 | CRITICALLY BROKEN — TypeScript-only is wrong, line estimates off by 3-10x for non-REST |
| 2. M7 Translator Complexity | 4/10 | SIGNIFICANTLY UNDERESTIMATED — ~100 lines is off by 3-7x, household/cost basis are landmines |
| 3. M6 Gateway Load | 6/10 | VIABLE FOR PHASE 2 — needs protocol-aware evolution by Phase 4 |
| 4. Vendor Approval Timeline | 5/10 | PARTIALLY ACCOUNTED — Fidelity/SOC2 chicken-and-egg problem not resolved |
| 5. Schema Translation Risk (M3) | 4/10 | DANGEROUSLY UNDERSCOPED — 6 types and 200 lines for 17 vendor data models |
| 6. Overall Architecture Fit | 6/10 | DIRECTIONALLY CORRECT — missing batch, identifiers, freshness, events |
| **WEIGHTED AVERAGE** | **5.3/10** | **Needs significant revision before Phase 2 code begins** |

---

## TOP 5 RECOMMENDATIONS (Priority Order)

1. **IMMEDIATE: Apply RES-08 corrections to ARCH-03 and ARCH-07.** The research identified the problems. The architecture documents have not been updated. Do this before writing any M11 or M7 code.

2. **IMMEDIATE: Declare M11 polyglot.** TypeScript for REST, Python for BLPAPI, language-appropriate for FIX. Update ARCH-07 table. Add M11 sub-classifications.

3. **PHASE 1: Expand M3 to 18+ canonical types with compliance SME co-design.** The schema is the foundation everything else builds on. Getting it wrong cascades through M7, M6, M8, and every agent specialist. Budget 2-3 weeks of dedicated schema design.

4. **PHASE 0: Investigate SOC 2 prerequisites for Schwab/Fidelity production API access.** If SOC 2 Type II is required before production access, the Phase 2 MVP runs entirely on mock data. The team needs to know this NOW, not at week 20.

5. **PHASE 1: Add batch reconciliation capability.** Daily SFTP files from custodians are how Tier 3/4 firms actually operate. An architecture that only supports real-time API calls misses the primary data delivery mechanism for the target market.

---

## CLOSING NOTE

I want to be clear: the team's research quality (RES-08) is outstanding. They identified every problem I would have flagged. The gap is between knowing the problems and updating the architecture to solve them. The 12-module design is elegant in theory — it just needs to absorb the reality that RES-08 uncovered. Fix the 5 items above and this architecture goes from a 5.3 to a 7+.

The trust layer is genuinely differentiated. Do not let adapter plumbing problems undermine it.

— Infrastructure Realist, LLMJ Reviewer 1