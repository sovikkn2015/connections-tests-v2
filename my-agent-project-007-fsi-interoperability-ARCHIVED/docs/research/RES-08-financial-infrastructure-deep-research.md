# RES-08: Financial Infrastructure Deep Research

> Date: April 14, 2026
> Category: RESEARCH (informing the design)
> Purpose: Detailed architecture study of every financial system 007 must integrate with
> Scope: 17 systems across 11 infrastructure categories
> Sources: Vendor documentation, developer portals, AWS partner pages, industry analysis
> Impact: Validates and corrects ARCH-03 (modules), ARCH-07 (tech stack), IMPL-01 (plan)

---

## WHY THIS RESEARCH EXISTS

007 designs an interoperability platform for financial services. The architecture documents (ARCH-01 through ARCH-08) describe what 007 builds. This document describes what 007 connects to — the actual infrastructure of the financial industry.

Every system has its own protocol, authentication model, data model, rate limits, vendor approval process, and integration constraints. Getting any of these wrong means failed integrations, compliance violations, or months of wasted engineering.

This research was conducted by studying vendor developer portals, API documentation, AWS partner solutions, industry publications, and regulatory guidance.

---

## PART 1: MARKET DATA INFRASTRUCTURE

### 1.1 Bloomberg B-PIPE

Bloomberg is the dominant market data provider for institutional finance. B-PIPE is the enterprise server-side data feed.

```
BLOOMBERG ARCHITECTURE:

  3 DELIVERY CHANNELS:
  ┌─────────────────────────────────────────────────────────────────┐
  │                                                                 │
  │  1. Bloomberg Terminal (desktop)                                │
  │     - $24,000/year per seat                                     │
  │     - Interactive: chat, news, analytics, trading               │
  │     - BLPAPI available for local Excel/Python integration       │
  │                                                                 │
  │  2. B-PIPE (server-side data feed)                              │
  │     - Enterprise license (negotiated, $50K-500K+/yr)            │
  │     - Real-time streaming + snapshots                           │
  │     - Reference data (fundamentals, corporate actions)          │
  │     - Delivered via BLPAPI (proprietary binary protocol)        │
  │     - NOT REST. NOT JSON. Binary request/response.              │
  │                                                                 │
  │  3. Data License (bulk file delivery)                           │
  │     - Batch delivery (daily/weekly files)                       │
  │     - Historical data, reference data, pricing                  │
  │     - SFTP or cloud delivery                                    │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘

  BLPAPI PROTOCOL:
  ┌─────────────────────────────────────────────────────────────────┐
  │  - Proprietary binary protocol (not HTTP/REST)                  │
  │  - Request: security identifier + field list                    │
  │    Example: "NVDA US Equity" + ["PX_LAST","VOLUME","PE_RATIO"]  │
  │  - Response: binary-encoded field values                        │
  │  - Subscription model for real-time streaming                   │
  │  - SDK: Python (blpapi), Java, C++, C#                         │
  │  - Reference data requested separately from pricing             │
  │  - Huge field catalog (10,000+ fields)                          │
  └─────────────────────────────────────────────────────────────────┘

  AWS INTEGRATION (B-PIPE via PrivateLink):
  ┌─────────────────────────────────────────────────────────────────┐
  │  - Bloomberg B-PIPE available on AWS via PrivateLink             │
  │  - Network Load Balancer exposes B-PIPE as local IPs            │
  │    within customer's VPC subnet                                 │
  │  - No public internet. No DNS issues.                           │
  │  - Aligns with ARCH-08 zero-public-internet design              │
  └─────────────────────────────────────────────────────────────────┘
```

007 impact:
- M11 Bloomberg adapter must use BLPAPI Python SDK, not REST
- M7 translator maps Bloomberg fields to canonical types (Holding, Quote, SecurityProfile)
- B-PIPE PrivateLink delivery aligns with ARCH-08 network design
- License cost ($24K+/yr minimum) — defer to Phase 4
- Tier 3/4 firms rarely have Bloomberg — use Alpha Vantage/Polygon as fallback

### 1.2 FactSet

FactSet is the second major financial data platform, increasingly popular with buy-side firms.

```
FACTSET ARCHITECTURE:

  DELIVERY:
  ┌─────────────────────────────────────────────────────────────────┐
  │  1. REST APIs (JSON) — open.factset.com developer portal        │
  │     - Fundamentals, estimates, ownership, prices, analytics     │
  │     - OAuth 2.0 authentication (API key + secret)               │
  │     - Standard REST patterns, well-documented                   │
  │                                                                 │
  │  2. Data as a Service (DaaS)                                    │
  │     - Bulk data delivery to cloud (AWS Data Exchange, Snowflake)│
  │     - For firms needing full datasets, not query-by-query       │
  │                                                                 │
  │  3. MCP SERVER (launched December 2025)                         │
  │     ┌─────────────────────────────────────────────────────────┐ │
  │     │  INDUSTRY FIRST: Production-grade MCP server             │ │
  │     │  Direct LLM-to-FactSet data access                      │ │
  │     │  No intermediary, no custom integration                  │ │
  │     │  Secure, authorized access within third-party AI tools   │ │
  │     │                                                          │ │
  │     │  THIS VALIDATES 007's MCP ADAPTER PATTERN.               │ │
  │     │  FactSet built exactly what 007 proposes for all vendors.│ │
  │     └─────────────────────────────────────────────────────────┘ │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘
```

007 impact:
- Option A: Use FactSet's native MCP server directly (plug-and-play through M6 gateway)
- Option B: Wrap FactSet REST API in 007's own MCP adapter
- Option A is faster and cheaper. M6 gateway still enforces trust/MNPI regardless.
- FactSet's MCP launch is the strongest external validation of 007's architecture thesis



---

## PART 2: CUSTODIAN INFRASTRUCTURE

Custodians hold client assets. They are the source of truth for positions, balances, transactions, and cost basis. 007's Tier 3/4 MVP depends on custodian integrations.

### 2.1 Charles Schwab Advisor Services

Schwab is the largest RIA custodian in the US (post TD Ameritrade merger, 2024).

```
SCHWAB ARCHITECTURE:

  INTEGRATION PATTERNS:
  ┌─────────────────────────────────────────────────────────────────┐
  │                                                                 │
  │  1. Real-time REST APIs                                         │
  │     - Positions, balances, account information                  │
  │     - Trade submission + order status                           │
  │     - Account opening (programmatic, new as of 2025)            │
  │     - OAuth 2.0 authentication                                  │
  │                                                                 │
  │  2. Daily Data Files (batch)                                    │
  │     - Positions, transactions, cost basis, tax lots              │
  │     - Delivered via SFTP (CSV or fixed-width format)            │
  │     - Reconciliation source of truth for many firms             │
  │                                                                 │
  │  3. Schwab OpenView Gateway                                     │
  │     - SSO integration for advisor platforms                     │
  │     - Balance data, contacts, holder info from custodian        │
  │     - Trade confirmations within third-party platforms          │
  │     - Document access (tax docs, statements)                    │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘

  VENDOR APPROVAL PROCESS:
  ┌─────────────────────────────────────────────────────────────────┐
  │  - Must apply to Schwab Advisor Services developer program      │
  │  - Security assessment required                                 │
  │  - Timeline: 6-8 weeks for approval                             │
  │  - SOC 2 Type II may be required for production access          │
  │  - Domain-driven API design (accounts, positions, orders)       │
  └─────────────────────────────────────────────────────────────────┘

  DATA MODEL:
  ┌─────────────────────────────────────────────────────────────────┐
  │  Account → Positions → Tax Lots                                 │
  │  Account → Transactions (trade history)                         │
  │  Account → Balances (cash, margin, total value)                 │
  │                                                                 │
  │  Cost basis: Specific lot identification (default)              │
  │  Identifiers: Schwab account number, CUSIP, ticker              │
  │  Household: Schwab groups accounts by "master account"          │
  └─────────────────────────────────────────────────────────────────┘
```

007 impact:
- M11 adapter: REST API wrapper + SFTP file ingestion for daily reconciliation
- M7 translator: Schwab Position → canonical Holding, Schwab Account → canonical Client
- Cost basis method (specific lot) must be normalized in M7
- Apply to developer program in Phase 0 Week 1. Build mock adapter immediately.
- SOC 2 Type II (Phase 3) may be prerequisite for production API access

### 2.2 Fidelity — Wealthscape Integration Xchange

Fidelity is the second-largest RIA custodian. Integration Xchange is their open architecture digital store.

```
FIDELITY ARCHITECTURE:

  INTEGRATION XCHANGE:
  ┌─────────────────────────────────────────────────────────────────┐
  │  - Open architecture digital store (launched 2018)              │
  │  - 200+ third-party technology integrations via APIs            │
  │  - REST APIs + SSO integrations                                 │
  │  - Wealthscape platform: accounts, positions, trading           │
  │  - FMAX (Managed Account Xchange) for TAMP integration          │
  │                                                                 │
  │  API capabilities:                                              │
  │    - Account data (balances, details, beneficiaries)            │
  │    - Position data (holdings, cost basis, unrealized G/L)       │
  │    - Transaction data (trade history, dividends, fees)          │
  │    - Document access (statements, tax forms)                    │
  │    - Account opening (programmatic)                             │
  │    - Trade submission                                           │
  └─────────────────────────────────────────────────────────────────┘

  VENDOR APPROVAL PROCESS — CRITICAL:
  ┌─────────────────────────────────────────────────────────────────┐
  │                                                                 │
  │  ██████████████████████████████████████████████████████████████ │
  │  ██  6-12 MONTHS FOR NEW FINTECH VENDORS                    ██ │
  │  ██  LONGEST APPROVAL CYCLE OF ANY CUSTODIAN                 ██ │
  │  ██████████████████████████████████████████████████████████████ │
  │                                                                 │
  │  Requirements:                                                  │
  │    - Formal security assessment                                 │
  │    - Data handling protocol review                              │
  │    - API integration standards compliance                       │
  │    - Ongoing compliance requirements                            │
  │    - SOC 2 Type II likely required                              │
  │                                                                 │
  │  MUST APPLY IN PHASE 0 WEEK 1. NON-NEGOTIABLE.                 │
  │  Build mock adapter with synthetic data immediately.            │
  │  Real integration earliest Phase 2-3.                           │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘

  DATA MODEL:
  ┌─────────────────────────────────────────────────────────────────┐
  │  Cost basis: Average cost (mutual funds), specific lot (equities)│
  │  Identifiers: Fidelity account number, CUSIP, SEDOL             │
  │  Household: Fidelity relationship grouping                      │
  └─────────────────────────────────────────────────────────────────┘
```

007 impact:
- 6-12 month approval is the longest lead-time item in the entire project
- Application must be submitted Phase 0 Week 1 — hard dependency
- Mock adapter with synthetic data from day one
- Cost basis method differs from Schwab (average cost for mutual funds) — M7 must normalize

### 2.3 Pershing (BNY Mellon) — NetX360+

Pershing is the dominant custodian for broker-dealers (Tier 3).

```
PERSHING ARCHITECTURE:

  PLATFORMS:
  ┌─────────────────────────────────────────────────────────────────┐
  │  NetX360+: Next-gen professional platform                       │
  │    - Custody solutions for BDs, RIAs, bank-trust firms          │
  │    - AI-powered personalized experience                         │
  │    - Curated insights and recommendations                       │
  │                                                                 │
  │  Integration Hub:                                               │
  │    - Bi-directional, real-time data synchronization              │
  │    - "Build once, deploy many" framework                        │
  │    - Growing network of integrated third-party providers        │
  │                                                                 │
  │  Wove Connect (next-gen):                                       │
  │    - Modern integration platform                                │
  │    - Digital experience creation tools                          │
  │    - Data utilization and operational streamlining              │
  │                                                                 │
  │  NetxServices API Store:                                        │
  │    - Documentation, code samples, sandbox testing               │
  │    - Self-service API exploration                               │
  └─────────────────────────────────────────────────────────────────┘
```

007 impact:
- M11 adapter: REST API wrapper via Integration Hub
- Key for Tier 3 broker-dealers (Pershing is their primary custodian)
- Phase 3 integration (after Schwab + Fidelity)
- Orion already has deep Pershing integration — can leverage Orion as intermediary

---

## PART 3: PORTFOLIO MANAGEMENT AND TRADING INFRASTRUCTURE

### 3.1 Orion Advisor Solutions

Orion is the number one portfolio accounting platform for RIAs.

```
ORION ARCHITECTURE:

  DEVELOPER PORTAL: developers.orionadvisor.com
  ┌─────────────────────────────────────────────────────────────────┐
  │  Protocol: REST API (JSON)                                      │
  │  Auth: OAuth 2.0, Basic Auth, Impersonation, SAML 2.0          │
  │                                                                 │
  │  DATA MODEL (hierarchical):                                     │
  │                                                                 │
  │    Representative (Advisor)                                     │
  │      └── Client / Household                                     │
  │            └── Portfolio (account group)                         │
  │                  └── Account (linked to custodian)               │
  │                        └── Position                             │
  │                              └── Tax Lot                        │
  │                                                                 │
  │  API DOMAINS:                                                   │
  │    - Clients/Households (hierarchical relationships)            │
  │    - Accounts (linked to custodians, with status)               │
  │    - Positions (cost basis, unrealized G/L, market value)       │
  │    - Transactions (trade history, dividends, fees)              │
  │    - Performance (TWR, IRR, benchmarks, attribution)            │
  │    - Billing (fee schedules, invoices, AUM calculations)        │
  │    - Custom Fields (user-defined, per entity)                   │
  │    - Documents (stored per household, retrievable)              │
  │    - Trading (rebalancing, model portfolios, order generation)  │
  │    - Risk (risk profiles, stress tests, survey results)         │
  │    - Financial Planning (aggregated accounts, net worth)        │
  │                                                                 │
  │  BULK DATA:                                                     │
  │    - Flat File Delivery (portfolio extracts)                    │
  │    - Data Queries via API (paginated, rate-limited)             │
  │    - Best practice: batch pulls with pagination                 │
  │                                                                 │
  │  WEBHOOKS:                                                      │
  │    - Notification webhooks for data change events               │
  │    - Reduces polling overhead                                   │
  └─────────────────────────────────────────────────────────────────┘

  KEY FINDING — ORION DENALI AI:
  ┌─────────────────────────────────────────────────────────────────┐
  │  Orion launched Denali AI — their own AI framework              │
  │  "Gravitational center of your wealthtech ecosystem"            │
  │                                                                 │
  │  007 is NOT competing with Denali.                              │
  │  007 WRAPS Orion data and makes it available cross-system.      │
  │  Denali optimizes within Orion. 007 connects across systems.    │
  └─────────────────────────────────────────────────────────────────┘
```

007 impact:
- M11 adapter: REST API wrapper with OAuth
- M7 translator: Orion Client → canonical Client, Orion Position → canonical Holding
- Critical: MarketValue field — does it include accrued interest? Must document per custodian feed.
- Household hierarchy must map to M3 canonical model
- Webhooks available for real-time position updates instead of polling

### 3.2 Envestnet / Tamarac

Envestnet is the largest TAMP serving 110,000+ advisors. Tamarac is their RIA platform.

```
ENVESTNET ARCHITECTURE:

  PLATFORM COMPONENTS:
  ┌─────────────────────────────────────────────────────────────────┐
  │                                                                 │
  │  Tamarac Trading:                                               │
  │    - Tax-intelligent rebalancing                                │
  │    - Multi-custodian trade execution                            │
  │    - Direct integration to Schwab, Fidelity, Pershing           │
  │                                                                 │
  │  Tamarac Reporting:                                             │
  │    - Portfolio accounting and performance reporting              │
  │    - Client portal with branded experience                      │
  │    - Household-level aggregation                                │
  │                                                                 │
  │  Tamarac CRM:                                                   │
  │    - Built on Microsoft Dynamics 365                            │
  │    - Client relationship management                             │
  │                                                                 │
  │  Unified Managed Accounts (UMA):                                │
  │    - Sleeve-based portfolio management                          │
  │    - Syncs into Tamarac as sleeve groups                        │
  │    - Daily data syncs for up-to-date positions                  │
  │                                                                 │
  │  Integration: REST APIs + SSO + data sync                       │
  └─────────────────────────────────────────────────────────────────┘

  COMPETITIVE POSITIONING:
  ┌─────────────────────────────────────────────────────────────────┐
  │  Envestnet is BOTH a data aggregator AND a potential competitor  │
  │    - They aggregate custodian data across Schwab/Fidelity/etc.  │
  │    - They have their own AI (Copilot)                           │
  │    - They serve 110K+ advisors                                  │
  │                                                                 │
  │  007 STRATEGY: Embrace and extend                               │
  │    - Build Envestnet adapter (wrap their API)                   │
  │    - Position 007 as cross-platform layer, not competitor       │
  │    - 007's value: cross-archetype intelligence Envestnet cannot  │
  │      match (they are Tier 3/4 only)                             │
  └─────────────────────────────────────────────────────────────────┘
```

### 3.3 SS&C Eze (OMS/EMS for Hedge Funds)

SS&C Eze is the leading order/execution management system for buy-side institutional firms.

```
SS&C EZE ARCHITECTURE:

  PLATFORMS:
  ┌─────────────────────────────────────────────────────────────────┐
  │                                                                 │
  │  Eze OMS (Order Management System):                             │
  │    - Portfolio modeling and analytics                           │
  │    - Pre-trade compliance (built-in rule engine)                │
  │    - Order lifecycle: capture → validate → route → fill → settle│
  │    - Multi-asset class: equities, FI, FX, options, crypto      │
  │    - 600+ buy-side firms                                        │
  │                                                                 │
  │  Eze EMS (Execution Management System):                         │
  │    - High-speed, multi-broker trading                           │
  │    - Algo selection and smart order routing                     │
  │    - Direct market access (DMA)                                 │
  │    - FIX connectivity to brokers and exchanges                  │
  │                                                                 │
  │  Eclipse (converged OEMS):                                      │
  │    - Single platform for multi-strategy hedge funds             │
  │    - Cloud-native, scalable                                     │
  │                                                                 │
  │  PROTOCOL: gRPC (xAPI) — NOT REST                               │
  │  ┌─────────────────────────────────────────────────────────────┐│
  │  │  Eze EMS xAPI uses Google's gRPC framework                  ││
  │  │  High-performance, binary protocol                          ││
  │  │  Proto file definitions for all message types               ││
  │  │  NOT a REST API. Cannot use standard HTTP clients.          ││
  │  └─────────────────────────────────────────────────────────────┘│
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘
```

007 impact:
- M11 adapter must use gRPC (xAPI), not REST
- Tier 5 hedge fund integration (Phase 4)
- Pod isolation in OPA must align with Eze's fund/strategy structure
- Eclipse's built-in compliance overlaps with M2/M4 — must coordinate, not conflict

---

## PART 4: TRADING PROTOCOLS

### 4.1 FIX Protocol (Financial Information eXchange)

FIX is the backbone of electronic trading since 1992.

```
FIX PROTOCOL ARCHITECTURE:

  FUNDAMENTALS:
  ┌─────────────────────────────────────────────────────────────────┐
  │  - Text-based tag=value pairs over TCP                          │
  │  - Versions: 4.0, 4.2 (most common), 4.4, 5.0 (FIXT)          │
  │  - STATEFUL: sessions maintain sequence numbers                 │
  │  - Persistent: messages stored for gap-fill recovery            │
  │                                                                 │
  │  TWO LAYERS:                                                    │
  │    Session layer: logon, heartbeat, sequence numbers, resend    │
  │    Application layer: orders, executions, market data           │
  └─────────────────────────────────────────────────────────────────┘

  KEY MESSAGE TYPES (for 007):
  ┌──────────┬───────────────────────┬──────────────────────────────┐
  │  Tag     │ Type                  │ Purpose                      │
  ├──────────┼───────────────────────┼──────────────────────────────┤
  │  D       │ NewOrderSingle        │ Submit order                 │
  │  8       │ ExecutionReport       │ Fill / reject / acknowledge  │
  │  F       │ OrderCancelRequest    │ Cancel order                 │
  │  G       │ OrderCancelReplace    │ Modify order                 │
  │  H       │ OrderStatusRequest    │ Query status                 │
  │  J       │ Allocation            │ Post-trade allocation        │
  └──────────┴───────────────────────┴──────────────────────────────┘

  SESSION MANAGEMENT (critical complexity):
  ┌─────────────────────────────────────────────────────────────────┐
  │  - Persistent TCP connection (not request/response like HTTP)   │
  │  - Sequence numbers: both sides track independently             │
  │  - Heartbeat: periodic messages to detect connection loss       │
  │  - Gap-fill: on reconnect, request missed messages by seq num   │
  │  - Session reset: daily or on-demand (sequence back to 1)       │
  │  - Message store: all sent/received messages persisted           │
  │                                                                 │
  │  This is NOT a stateless REST wrapper.                          │
  │  FIX Bridge must maintain persistent session state.             │
  └─────────────────────────────────────────────────────────────────┘

  LATENCY:
  ┌─────────────────────────────────────────────────────────────────┐
  │  HFT: sub-millisecond (not relevant for 007)                    │
  │  Institutional: single-digit milliseconds                       │
  │  007 target: <100ms for order submission (advisor-driven)       │
  └─────────────────────────────────────────────────────────────────┘

  LIBRARIES:
  ┌─────────────────────────────────────────────────────────────────┐
  │  QuickFIX/J (Java) — most mature, widely used                  │
  │  QuickFIX/n (.NET) — C# implementation                         │
  │  simplefix (Python) — exists but less mature                    │
  │  Recommendation: Hire FIX specialist to decide.                 │
  └─────────────────────────────────────────────────────────────────┘
```

007 impact:
- FIX Bridge = MCP server wrapping a FIX engine
- Must maintain FIX session state (sequence numbers, heartbeat, gap-fill)
- Hire FIX specialist contractor (Phase 4). Budget 14 weeks minimum.
- 007's Execution Specialist state machine maps to FIX order lifecycle

---

## PART 5: PAYMENT AND SETTLEMENT INFRASTRUCTURE

### 5.1 SWIFT Network and ISO 20022

SWIFT is the global financial messaging network connecting 11,000+ institutions.

```
SWIFT ARCHITECTURE:

  3 COMPONENTS:
  ┌─────────────────────────────────────────────────────────────────┐
  │  1. SWIFT Network (secure messaging backbone)                   │
  │  2. Message Standards (MT legacy → MX/ISO 20022)                │
  │  3. Connection Infrastructure (Alliance Gateway, Alliance Lite2)│
  └─────────────────────────────────────────────────────────────────┘

  ISO 20022 MIGRATION — COMPLETED NOVEMBER 2025:
  ┌─────────────────────────────────────────────────────────────────┐
  │  - CBPR+ coexistence period ended November 22, 2025             │
  │  - ISO 20022 is NOW the required format for SWIFT               │
  │  - XML-based, richer structured data than legacy MT             │
  │  - No need to support legacy MT format in 007                   │
  └─────────────────────────────────────────────────────────────────┘

  KEY MESSAGE TYPES (ISO 20022):
  ┌──────────┬──────────────────────────────┬───────────────────────┐
  │  Message  │ Name                         │ Use Case              │
  ├──────────┼──────────────────────────────┼───────────────────────┤
  │ pain.001 │ Customer Credit Transfer Init │ Payment initiation    │
  │ pain.002 │ Payment Status Report         │ Status tracking       │
  │ camt.053 │ Bank-to-Customer Statement    │ Account statements    │
  │ camt.054 │ Debit/Credit Notification     │ Transaction alerts    │
  │ pacs.008 │ FI-to-FI Credit Transfer      │ Interbank transfer    │
  └──────────┴──────────────────────────────┴───────────────────────┘

  007 RELATIONSHIP:
  ┌─────────────────────────────────────────────────────────────────┐
  │  007 does NOT connect directly to SWIFT.                        │
  │  007 wraps the bank's existing SWIFT gateway via API.           │
  │  SWIFT Bridge = MCP server parsing/generating ISO 20022 XML.    │
  │  Phase 5 only (Tier 1 banks). Hire SWIFT specialist.            │
  └─────────────────────────────────────────────────────────────────┘
```

### 5.2 DTCC (Depository Trust and Clearing Corporation)

DTCC is the central clearing and settlement infrastructure for US securities.

```
DTCC ARCHITECTURE:

  ┌─────────────────────────────────────────────────────────────────┐
  │  - Central counterparty for US equity and bond trades           │
  │  - T+1 settlement (live since May 2024)                        │
  │  - Modernizing: legacy mainframe → distributed architecture     │
  │  - CTM (Central Trade Matching) for institutional trades        │
  │                                                                 │
  │  007 does NOT integrate directly with DTCC.                     │
  │  Custodians handle DTCC clearing.                               │
  │  007 submits orders to custodian → custodian clears via DTCC.   │
  │  Settlement status comes from custodian API, not DTCC.          │
  │                                                                 │
  │  T+1 impact: Execution Specialist must track settlement         │
  │  within T+1 (next business day).                                │
  └─────────────────────────────────────────────────────────────────┘
```

### 5.3 Fedwire and CHIPS

Large-value US payment systems.

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  Fedwire: Real-time gross settlement (Federal Reserve)          │
  │    - 9,000+ participants, immediate and irrevocable             │
  │    - For large-value, time-critical transfers                   │
  │                                                                 │
  │  CHIPS: Private netting system (The Clearing House)             │
  │    - 43 member banks, nets interbank settlements                │
  │    - Cheaper than Fedwire (netting reduces volume)              │
  │                                                                 │
  │  007 relationship: Indirect only.                               │
  │  Wire transfers initiated via custodian/bank API.               │
  │  BSA/AML monitoring (ARCH-06) must flag CTR threshold ($10K+).  │
  └─────────────────────────────────────────────────────────────────┘
```



---

## PART 6: CRM INFRASTRUCTURE

### 6.1 Salesforce Financial Services Cloud (FSC)

Salesforce FSC is the dominant CRM for financial services — banking, wealth management, and insurance.

```
SALESFORCE FSC ARCHITECTURE:

  PROTOCOL:
  ┌─────────────────────────────────────────────────────────────────┐
  │  REST API (SOQL queries) — primary data access                  │
  │  Bulk API — large data loads (batch)                            │
  │  Streaming API — real-time change notifications                 │
  │  Metadata API — schema introspection                            │
  │  Auth: OAuth 2.0 (connected app)                                │
  └─────────────────────────────────────────────────────────────────┘

  FSC-SPECIFIC DATA MODEL:
  ┌─────────────────────────────────────────────────────────────────┐
  │                                                                 │
  │  Standard Salesforce objects PLUS FSC-specific objects:         │
  │                                                                 │
  │  Person Account / Contact (client)                              │
  │    └── Financial Account (investment, bank, credit)             │
  │          └── Financial Account Role (junction: client↔account)  │
  │          └── Financial Holding (positions within accounts)      │
  │                └── Securities (instrument reference data)       │
  │    └── Financial Goal (client goals, targets)                   │
  │    └── Interaction Summary (meeting notes, call logs)           │
  │                                                                 │
  │  Household (relationship grouping)                              │
  │    └── Household Members (junction to Person Account)           │
  │                                                                 │
  │  Rollup (aggregated financial data across accounts)             │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘

  HOUSEHOLD MODEL MISMATCH — CRITICAL:
  ┌─────────────────────────────────────────────────────────────────┐
  │                                                                 │
  │  Salesforce FSC Household ≠ Orion Household ≠ Schwab Household  │
  │                                                                 │
  │  SF FSC: Household is a custom object with member junction      │
  │  Orion:  Household is a hierarchical client grouping            │
  │  Schwab: Household is "master account" grouping                 │
  │                                                                 │
  │  M3 canonical schema must define ONE household model that       │
  │  maps to all three. This is a schema translation landmine.      │
  │  Expect 3-5 revisions of the canonical Household type.          │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘

  AGENTFORCE RELATIONSHIP:
  ┌─────────────────────────────────────────────────────────────────┐
  │  FSC data model is the "hidden foundation" for Agentforce       │
  │  Agentforce AI agents read FSC objects for client context       │
  │  007 does NOT compete with Agentforce                           │
  │  007 connects FSC data with non-Salesforce systems              │
  │  (Orion, Schwab, Bloomberg, etc.) that Agentforce cannot reach  │
  └─────────────────────────────────────────────────────────────────┘
```

007 impact:
- M11 adapter: REST API (SOQL) wrapper with OAuth
- M7 translator: SF FinancialAccount → canonical Client, SF FinancialHolding → canonical Holding
- Household model mismatch is the biggest schema translation challenge
- FSC Interaction Summary maps to 007's meeting prep output (write-back capability)

---

## PART 7: COMPLIANCE AND SURVEILLANCE INFRASTRUCTURE

### 7.1 NICE Actimize SURVEIL-X

NICE Actimize is the leading trade surveillance platform for institutional compliance.

```
SURVEIL-X ARCHITECTURE:

  ┌─────────────────────────────────────────────────────────────────┐
  │  Cloud-native, AI-powered holistic surveillance                 │
  │                                                                 │
  │  Capabilities:                                                  │
  │    - Trade surveillance (market manipulation, insider trading)   │
  │    - Communications surveillance (voice, text, email)           │
  │    - Cross-channel correlation (trade + comms together)         │
  │    - Self-service analytics (Studio for custom risk models)     │
  │    - GenAI-powered alert triage (reduces false positives)       │
  │    - Behavioral pattern analysis (NLP on communications)        │
  │                                                                 │
  │  Integration pattern:                                           │
  │    - Data feed ingestion (trades, orders, communications)       │
  │    - Alert output via API or dashboard                          │
  │    - 007 feeds data TO SURVEIL-X (not the reverse)              │
  │                                                                 │
  │  Enterprise partnership: 6-12 month sales cycle                 │
  │  Start conversations in Phase 3. Integration in Phase 5.        │
  └─────────────────────────────────────────────────────────────────┘
```

007 impact:
- Phase 5 (Tier 1 banks only)
- M10 audit trail → SURVEIL-X data feed (007 is a data source, not consumer)
- Alert routing: SURVEIL-X alerts → 007 compliance dashboard
- Enterprise partnership required — long sales cycle

### 7.2 Smarsh (Communication Archiving)

Smarsh is the dominant compliance archiving platform for regulated financial communications.

```
SMARSH ARCHITECTURE:

  ┌─────────────────────────────────────────────────────────────────┐
  │  Compliance archiving for regulated communications              │
  │                                                                 │
  │  Channels covered: 80+                                          │
  │    Email, SMS, WhatsApp, Slack, Teams, Bloomberg IB,            │
  │    Symphony, social media, voice recordings                     │
  │                                                                 │
  │  Architecture:                                                  │
  │    Capture → Archive → Supervise → Discover                     │
  │                                                                 │
  │    Capture: connectors for 80+ communication channels           │
  │    Archive: immutable, tamper-proof, searchable                 │
  │    Supervise: policy-based review queues for principals         │
  │    Discover: e-discovery for legal/regulatory requests          │
  │                                                                 │
  │  Regulatory context:                                            │
  │    SEC Rule 17a-4: recordkeeping requirements                   │
  │    FINRA Rule 3110: supervisory procedures                      │
  │    $8.2B in SEC fines (FY2024) for off-channel communications   │
  │    $3B+ in FINRA fines (2025) for archiving failures            │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘

  WHY THIS IS NON-NEGOTIABLE FOR 007:
  ┌─────────────────────────────────────────────────────────────────┐
  │                                                                 │
  │  Every agent-client communication through OpenClaw MUST be      │
  │  archived to a compliant system (Smarsh or equivalent).         │
  │                                                                 │
  │  If an advisor uses 007's agent on WhatsApp to discuss a        │
  │  client's portfolio, that conversation is a "business           │
  │  communication" under SEC/FINRA rules.                          │
  │                                                                 │
  │  Failure to archive = regulatory violation.                     │
  │  $11B+ in fines in 2024-2025 proves regulators are serious.    │
  │                                                                 │
  │  M12 (OpenClaw) → Smarsh connector for every channel            │
  │  Supervisory review queue: principal must review agent outputs  │
  │  FINRA 2210: communications with the public must be supervised  │
  │                                                                 │
  │  Phase 3 integration. Start conversations Phase 1.              │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘
```

---

## PART 8: REGULATORY FILING INFRASTRUCTURE

### 8.1 SEC EDGAR

EDGAR is the SEC's electronic filing system — the source of all public company financial data.

```
EDGAR ARCHITECTURE:

  ┌─────────────────────────────────────────────────────────────────┐
  │  Protocol: REST APIs (JSON) — FREE, no authentication required  │
  │  Endpoint: data.sec.gov                                         │
  │  Rate limit: 10 requests/second (User-Agent header required)    │
  │                                                                 │
  │  Key APIs:                                                      │
  │    CompanyFacts: every XBRL fact ever filed (single JSON)       │
  │    Submissions: filing history per CIK                          │
  │    Full-text search: EFTS (EDGAR Full-Text Search)              │
  │    Filing documents: HTML, XML, XBRL                            │
  │                                                                 │
  │  Data formats:                                                  │
  │    XBRL (eXtensible Business Reporting Language)                │
  │    iXBRL (inline XBRL — human + machine readable)               │
  │    HTML (legacy filings)                                        │
  │                                                                 │
  │  EDGAR Next: modernization underway                             │
  │    New filer management APIs                                    │
  │    Improved account management                                  │
  │                                                                 │
  │  Filing types relevant to 007:                                  │
  │    10-K (annual report), 10-Q (quarterly), 8-K (current events) │
  │    DEF 14A (proxy statement), 13-F (institutional holdings)     │
  │    SC 13D/G (beneficial ownership)                              │
  └─────────────────────────────────────────────────────────────────┘
```

007 impact:
- M11 adapter: REST API wrapper (already exists in 006, adapt for 007)
- Research Specialist uses EDGAR for 10-K, 10-Q, 8-K, proxy filings
- M7 translator: XBRL facts → canonical financial metrics
- Hierarchical RAG: chunk filings by section for retrieval (ARCH-05)
- Free API = no vendor approval needed. Phase 1 ready.
- Rate limit (10 req/s) requires queuing in M6 gateway

---

## PART 9: THE MULTI-CUSTODIAL INTEGRATION PROBLEM

This is the core problem 007 solves. Understanding the current landscape is essential.

```
THE PROBLEM:
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  Average wealth management firm: 20-35 separate tech platforms      │
│  Advisors spend 40% of time on manual data entry and reconciliation │
│                                                                     │
│  Typical firm tech stack:                                           │
│    2-3 custodians (Schwab + Fidelity + Pershing)                   │
│    1 CRM (Salesforce FSC or Wealthbox or Redtail)                  │
│    1 portfolio management (Orion or Tamarac or Black Diamond)      │
│    1 financial planning (eMoney or MoneyGuidePro)                  │
│    1 compliance (Smarsh + ComplySci)                                │
│    1 trading (custodian native or Orion Trading)                   │
│    1 reporting (Orion or Tamarac or custom)                        │
│    + market data, research, document management, billing...        │
│                                                                     │
│  None of these talk to each other natively.                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

CURRENT INTEGRATION APPROACHES:
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  1. MuleSoft (Salesforce-owned)                                     │
│     - API-led connectivity (System → Process → Experience layers)   │
│     - $150K-$500K+ for enterprise implementation                   │
│     - 3-6 months initial, 6-12 months full coverage                │
│     - 426-445% ROI over 3 years                                    │
│     - BUT: integration only. No AI agent. No compliance layer.     │
│                                                                     │
│  2. Point-to-point (most firms today)                               │
│     - Custom code per custodian x per system                       │
│     - N x M integration problem (5 custodians x 7 systems = 35)   │
│     - Brittle, expensive to maintain, no shared trust layer        │
│                                                                     │
│  3. Aggregators (Envestnet, Orion, Black Diamond)                   │
│     - Pre-built custodian connections                              │
│     - BUT: locked to their ecosystem                               │
│     - No cross-platform agent intelligence                         │
│                                                                     │
│  007's DIFFERENTIATION:                                             │
│     - MCP adapters (universal protocol, not point-to-point)        │
│     - Trust layer (identity + authority + MNPI) BETWEEN systems    │
│     - AI agent that REASONS across all connected systems           │
│     - Compliance built in, not bolted on                           │
│     - Works WITH existing aggregators (wraps them)                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## PART 10: OMS/EMS TRADE LIFECYCLE

Understanding the full trade lifecycle is essential for 007's Execution Specialist design.

```
TRADE LIFECYCLE — BUY-SIDE PERSPECTIVE:

  PORTFOLIO MANAGER
       │ investment decision
       ▼
  ┌─────────┐
  │   PMS   │  Portfolio Management System
  │         │  (model portfolios, target allocations)
  └────┬────┘
       │ rebalance orders
       ▼
  ┌─────────┐
  │   OMS   │  Order Management System
  │         │  (order capture, compliance check, allocation)
  │         │  Pre-trade: restricted list, concentration limits
  │         │  State: NEW → VALIDATED → ROUTED → FILLED
  └────┬────┘
       │ routed orders
       ▼
  ┌─────────┐
  │   EMS   │  Execution Management System
  │         │  (algo selection, venue routing, DMA)
  │         │  FIX connectivity to brokers/exchanges
  └────┬────┘
       │ FIX messages
       ▼
  ┌─────────┐
  │ BROKER/ │  Executing broker or exchange
  │EXCHANGE │  Fills order, sends ExecutionReport (FIX tag 8)
  └────┬────┘
       │ execution reports
       ▼
  ┌─────────┐
  │CLEARING │  DTCC / Prime Broker
  │         │  Netting, novation, settlement (T+1)
  └────┬────┘
       │ settlement confirmation
       ▼
  ┌─────────┐
  │CUSTODIAN│  Schwab / Fidelity / Pershing / Prime Broker
  │         │  Asset custody, position updates, statements
  └─────────┘

  WHERE 007 SITS:
  ┌─────────────────────────────────────────────────────────────────┐
  │  007's Execution Specialist operates at the OMS layer:          │
  │                                                                 │
  │  - Receives intent from advisor ("buy 500 NVDA for Henderson")  │
  │  - Calls Compliance Specialist (pre-trade check via OPA)        │
  │  - Prepares order (HITL gate: advisor approves)                 │
  │  - Submits to custodian API (Tier 3/4) or OMS/FIX (Tier 2/5)  │
  │  - Tracks execution reports                                     │
  │  - Logs everything to M10 WORM                                  │
  │                                                                 │
  │  007 does NOT replace the OMS/EMS. It WRAPS it.                 │
  │  For Tier 3/4: direct custodian API (no OMS needed)             │
  │  For Tier 2/5: integrates with existing Eze/Bloomberg OMS       │
  └─────────────────────────────────────────────────────────────────┘
```

---

## PART 11: PRIME BROKERAGE (Tier 5 Hedge Funds)

```
PRIME BROKERAGE ARCHITECTURE:

  SERVICES (bundled by prime broker):
  ┌─────────────────────────────────────────────────────────────────┐
  │  - Trade execution (multi-venue access)                         │
  │  - Clearing and settlement                                      │
  │  - Asset custody (segregated client assets)                     │
  │  - Securities lending (for short selling)                       │
  │  - Margin financing (leverage)                                  │
  │  - Consolidated reporting (cross-venue, cross-asset)            │
  │  - Capital introduction (investor introductions)                │
  └─────────────────────────────────────────────────────────────────┘

  MAJOR PRIME BROKERS:
  ┌─────────────────────────────────────────────────────────────────┐
  │  Goldman Sachs, Morgan Stanley, JPMorgan                        │
  │  Most large hedge funds use 2-3 prime brokers (multi-prime)     │
  │  Each prime broker has proprietary reporting APIs                │
  └─────────────────────────────────────────────────────────────────┘

  007 RELATIONSHIP:
  ┌─────────────────────────────────────────────────────────────────┐
  │  007 does NOT replace the prime broker.                         │
  │  007 wraps prime broker reporting APIs for:                     │
  │    - Position data (per pod/fund)                               │
  │    - Margin and financing data                                  │
  │    - Securities lending availability                            │
  │  Pod isolation in OPA must align with prime broker's             │
  │  fund/account structure.                                        │
  │  Multi-prime: M11 needs adapter per prime broker.               │
  └─────────────────────────────────────────────────────────────────┘
```

---

## PART 12: COMPLETE PROTOCOL MAP

Every system 007 connects to, with protocol, auth, and phase.

```
┌──────────────────┬────────────┬──────────────┬──────────┬─────────────────┐
│ System           │ Protocol   │ Auth         │ Phase    │ Notes           │
├──────────────────┼────────────┼──────────────┼──────────┼─────────────────┤
│ SEC EDGAR        │ REST/JSON  │ None (free)  │ 1        │ From 006        │
│ Salesforce FSC   │ REST/SOQL  │ OAuth 2.0    │ 2        │ Household issue │
│ Orion            │ REST/JSON  │ OAuth/Basic  │ 2        │ Webhooks avail  │
│ eMoney           │ REST/JSON  │ OAuth 2.0    │ 2        │                 │
│ Schwab           │ REST+SFTP  │ OAuth 2.0    │ 2        │ Apply Phase 0   │
│ Fidelity         │ REST/JSON  │ OAuth 2.0    │ 3        │ Apply Phase 0!  │
│ Pershing         │ REST/JSON  │ OAuth 2.0    │ 3        │ Via Integ Hub   │
│ Wealthbox        │ REST/JSON  │ API key      │ 3        │                 │
│ Redtail          │ REST/JSON  │ API key      │ 3        │                 │
│ Smarsh           │ REST/JSON  │ API key      │ 3        │ Non-negotiable  │
│ Bloomberg B-PIPE │ BLPAPI     │ License+cert │ 4        │ NOT REST ($24K+)│
│ FactSet          │ MCP native │ OAuth 2.0    │ 4        │ MCP direct!     │
│ SS&C Eze         │ gRPC       │ OAuth 2.0    │ 4        │ NOT REST        │
│ FIX (brokers)    │ FIX 4.2    │ Session auth │ 4        │ Stateful TCP    │
│ Envestnet        │ REST/JSON  │ OAuth 2.0    │ 4        │ Competitor risk │
│ ComplySci        │ REST/JSON  │ API key      │ 4        │                 │
│ NICE SURVEIL-X   │ Data feed  │ Enterprise   │ 5        │ Partnership req │
│ SWIFT ISO 20022  │ XML/MX     │ PKI/BIC      │ 5        │ Specialist req  │
│ Bedrock LLM      │ REST/JSON  │ IAM/SigV4    │ 1        │ PrivateLink     │
│ OPA              │ REST/JSON  │ localhost    │ 1        │ Sidecar         │
└──────────────────┴────────────┴──────────────┴──────────┴─────────────────┘

  NOT all REST. 3 non-REST protocols: BLPAPI, gRPC, FIX.
  M11 adapter layer must support all three.
```

---

## PART 13: CRITICAL FINDINGS THAT CHANGE OR VALIDATE 007 ARCHITECTURE

### Finding 1: FactSet Has a Native MCP Server

FactSet launched the industry's first production-grade MCP server in December 2025. This provides direct LLM-to-FactSet data access without intermediaries. This is exactly what 007 proposes for all vendors via M11 adapters. FactSet built it first for their own data. More vendors will follow. 007 is on the right side of history.

Architecture impact: For FactSet specifically, 007 can use their native MCP server routed through M6 gateway (trust/MNPI filtering still applies). For vendors without native MCP, 007 builds the adapter.

### Finding 2: Bloomberg B-PIPE Uses BLPAPI (Not REST)

M11 adapter for Bloomberg cannot be a simple REST wrapper. Must use Bloomberg's proprietary Python SDK (blpapi). Binary protocol, subscription model, separate reference data requests.

Architecture impact: M11 adapters are NOT all TypeScript REST wrappers. Bloomberg adapter must be Python. ARCH-07 listed M11 as TypeScript only — this needs correction. M11 should be polyglot (TypeScript for REST, Python for BLPAPI).

### Finding 3: SS&C Eze Uses gRPC (Not REST)

Eze EMS xAPI is built on Google's gRPC framework. High-performance binary protocol with proto file definitions.

Architecture impact: Another non-REST adapter. gRPC stubs can be generated for Python or TypeScript from proto files. Combined with Finding 2, M11 must support REST + BLPAPI + gRPC.

### Finding 4: Fidelity Vendor Approval Takes 6-12 Months

Longest approval cycle of any custodian. Formal security assessment, data handling review, ongoing compliance requirements. SOC 2 Type II likely required.

Architecture impact: This is the longest lead-time item in the entire project. Must apply Phase 0 Week 1. Build mock adapter with synthetic data immediately. Real integration earliest Phase 2-3. Already in IMPL-01 but worth emphasizing — this is a hard dependency.

### Finding 5: Household Model Mismatch

Salesforce FSC Household is a custom object with member junction. Orion Household is a hierarchical client grouping. Schwab Household is "master account" grouping. Three different data models for the same concept.

Architecture impact: M3 canonical schema must define ONE household model that maps to all three. This is the single biggest schema translation challenge. Expect 3-5 revisions of the canonical Household type. Compliance SME must validate that household-level aggregation is correct for regulatory reporting.

### Finding 6: Cost Basis Normalization

Schwab defaults to specific lot identification. Fidelity uses average cost for mutual funds, specific lot for equities. Orion reflects whatever the custodian feed provides.

Architecture impact: M7 translators must normalize cost basis method per holding. Get this wrong = incorrect tax reporting = regulatory risk. Must be validated by compliance SME and tested with reconciliation suite.

### Finding 7: Smarsh Archiving Is Non-Negotiable

$8.2B in SEC fines (FY2024) plus $3B+ in FINRA fines (2025) for off-channel communication failures. Every agent-client message through OpenClaw must be archived to a compliant system.

Architecture impact: M12 (OpenClaw) must have a Smarsh connector for every channel. Supervisory review queue required (principal must review agent outputs per FINRA 2210). Phase 3 integration. Start vendor conversations Phase 1.

### Finding 8: 007 Never Connects Directly to DTCC/Fedwire/CHIPS

These are infrastructure-of-infrastructure. Custodians and banks handle clearing, settlement, and wire transfers. 007 submits orders to custodian APIs. Settlement status comes back via custodian.

Architecture impact: No M11 adapters needed for DTCC, Fedwire, or CHIPS. Execution Specialist tracks settlement via custodian API responses. BSA/AML monitoring (ARCH-06) flags wire thresholds ($10K+ CTR) based on custodian transaction data.

### Finding 9: FIX Is Stateful

FIX protocol maintains persistent TCP sessions with sequence number tracking. Gap-fill recovery on reconnect. Message persistence required. This is not a stateless REST wrapper.

Architecture impact: FIX Bridge is specialized engineering. Hire FIX specialist contractor for Phase 4. Budget 14 weeks minimum. Use QuickFIX library (Java or Python). FIX Bridge must persist session state to survive pod restarts (DynamoDB/PostgreSQL).

### Finding 10: ISO 20022 Migration Is Complete

SWIFT's CBPR+ coexistence period ended November 2025. ISO 20022 (MX format) is now the required standard. No need to support legacy MT format.

Architecture impact: 007's SWIFT Bridge only needs MX (XML) parsing. Simplifies Phase 5 scope. One format instead of two.

---

## PART 14: CORRECTIONS TO EXISTING ARCHITECTURE DOCUMENTS

Based on this research, the following corrections are needed:

| Document | Section | Correction |
|----------|---------|-----------|
| ARCH-07 | M11 language | M11 is NOT TypeScript-only. Must be polyglot: TypeScript (REST), Python (BLPAPI), gRPC (Eze). |
| ARCH-03 | M11 lines estimate | "~200 lines each" is too low for Bloomberg (BLPAPI) and FIX Bridge. Bloomberg: ~500 lines. FIX: ~1,000+ lines. |
| IMPL-01 | Phase 0 | Add: "Submit Fidelity Integration Xchange application Week 1" — already listed but must be emphasized as longest lead-time. |
| ARCH-05 | Execution Specialist | Add: "For Tier 2/5, integrates with existing OMS (Eze) via gRPC, not direct custodian API." |
| ARCH-06 | BSA/AML | Add: "CTR threshold ($10K+) applies to wire transfers visible via custodian transaction API, not direct Fedwire access." |
| ARCH-08 | VPC endpoints | Add: "Bloomberg B-PIPE via PrivateLink (NLB in customer VPC)" for Tier 2/5 hybrid topology. |

---

## SUMMARY

This research studied 17 financial systems across 11 infrastructure categories. The key takeaways:

1. The MCP adapter pattern is validated by FactSet's production MCP server (Dec 2025). More vendors will follow.

2. Three non-REST protocols (BLPAPI, gRPC, FIX) mean M11 must be polyglot, not TypeScript-only.

3. The household model mismatch (SF FSC vs Orion vs custodians) and cost basis normalization are the two biggest schema translation landmines.

4. Smarsh archiving is non-negotiable — $11B+ in fines in 2024-2025 for communication failures.

5. Fidelity's 6-12 month vendor approval is the longest lead-time item. Must apply Phase 0 Week 1.

6. 007 never connects directly to clearing/settlement infrastructure (DTCC, Fedwire, CHIPS). Custodians handle that layer.

7. FIX and SWIFT require specialist contractors. Budget 14 weeks each.

8. Bloomberg B-PIPE on AWS PrivateLink aligns perfectly with ARCH-08 network design.

9. 007 does not replace any existing system. It wraps them all through MCP adapters with a trust layer in between.

10. The multi-custodial integration problem (20-35 disconnected platforms, 40% advisor time on data entry) is the core pain point 007 solves.

---

*RES-08 — Project 007 FSI Interoperability Platform*
*Financial Infrastructure Deep Research*


---

## PART 6: CRM INFRASTRUCTURE

### 6.1 Salesforce Financial Services Cloud (FSC)

Salesforce FSC is the dominant CRM for financial services — banking, wealth management, and insurance.

```
SALESFORCE FSC ARCHITECTURE:

  PROTOCOL:
  ┌─────────────────────────────────────────────────────────────────┐
  │  REST API: SOQL queries, CRUD operations                        │
  │  Bulk API: large data loads (10K+ records)                      │
  │  Streaming API: real-time change notifications (PushTopic, CDC) │
  │  Metadata API: schema introspection and customization           │
  │  Auth: OAuth 2.0 (connected app)                                │
  └─────────────────────────────────────────────────────────────────┘

  FSC DATA MODEL (industry-specific objects):
  ┌─────────────────────────────────────────────────────────────────┐
  │                                                                 │
  │  Person Account / Contact (client)                              │
  │    └── Household (relationship grouping)                        │
  │          └── Financial Account (investment, bank, credit)       │
  │                └── Financial Account Role (junction object)     │
  │                └── Financial Holding (positions)                │
  │                      └── Securities (instrument reference)      │
  │                                                                 │
  │  Additional FSC objects:                                        │
  │    - Financial Goal (client goals, target amounts)              │
  │    - Interaction Summary (meeting notes, action items)          │
  │    - Rollup (aggregated financial data across accounts)         │
  │                                                                 │
  │  KEY: FSC data model is the "hidden foundation" for Agentforce  │
  │  Agentforce AI agents read FSC objects for client context       │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘

  HOUSEHOLD MODEL — THE LANDMINE:
  ┌─────────────────────────────────────────────────────────────────┐
  │                                                                 │
  │  Salesforce FSC Household:                                      │
  │    - Custom object (Account with RecordType = Household)        │
  │    - Members linked via AccountContactRelation                  │
  │    - Rollup summaries aggregate across members                  │
  │    - Household = relationship grouping (family unit)            │
  │                                                                 │
  │  Orion Household:                                               │
  │    - Native entity in Orion data model                          │
  │    - Clients grouped under Household                            │
  │    - Portfolios and accounts roll up to Household               │
  │    - Household = portfolio management grouping                  │
  │                                                                 │
  │  Schwab Household:                                              │
  │    - "Master account" grouping                                  │
  │    - Accounts linked by master account number                   │
  │    - Household = custodial grouping                             │
  │                                                                 │
  │  THE PROBLEM:                                                   │
  │    These three "Household" concepts are NOT the same.           │
  │    SF FSC: family relationship grouping                         │
  │    Orion: portfolio management grouping                         │
  │    Schwab: custodial account grouping                           │
  │                                                                 │
  │    A family may have:                                           │
  │      1 SF Household, 2 Orion Households (his/hers),             │
  │      3 Schwab master accounts (IRA, joint, trust)               │
  │                                                                 │
  │    M3 canonical schema must define ONE Household model           │
  │    that maps to all three. Expect 3-5 revisions.               │
  │                                                                 │
  └─────────────────────────────────────────────────────────────────┘
```

007 impact:
- M11 adapter: REST API (SOQL) wrapper with OAuth connected app
- M7 translator: SF FinancialAccount → canonical Client, SF FinancialHolding → canonical Holding
- Household model mismatch is the single biggest schema translation risk
- M3 canonical schema must handle all three household definitions
- Already have Salesforce FSC experience from Project 006

---

## PART 7: COMPLIANCE AND SURVEILLANCE INFRASTRUCTURE

### 7.1 NICE Actimize SURVEIL-X

NICE Actimize is the leading trade surveillance platform for financial institutions.

```
SURVEIL-X ARCHITECTURE:

  ┌─────────────────────────────────────────────────────────────────┐
  │                                                                 │
  │  Trade Surveillance:                                            │
  │    - Market manipulation detection (spoofing, layering)         │
  │    - Insider trading detection                                  │
  │    - AI + ML + traditional expert rule-based analytics          │
  │                                                                 │
  │  Communications Surveillance:                                   │
  │    - Voice, email, instant messaging, chat                      │
  │    - NLP for intent and sentiment analysis                      │
  │    - Cross-channel correlation                                  │
  │                                                                 │
  │  Holistic Surveillance:                                         │
  │    - Correlates trade data WITH communications                  │
  │    - Single alert for multi-faceted misconduct                  │
  │    - Reduces false positives via contextual analysis            │
  │                                                                 │
  │  GenAI Enhancement (2025):                                      │
  │    - Supervised ML for alert classification                     │
  │    - Dramatically reduces false positive workload               │
  │                                                                 │
  │  Platform: Cloud-native                                         │
  │  Integration: Data feed ingestion (trades, orders, comms)       │
  │  Alert output: API or compliance dashboard                      │
  └─────────────────────────────────────────────────────────────────┘
```

007 impact:
- Phase 5 (Tier 1 banks only)
- 007 feeds trade data TO SURVEIL-X (not the reverse)
- M10 audit trail → SURVEIL-X data feed adapter
- Enterprise partnership required (6-12 month sales cycle). Start Phase 3.

### 7.2 Smarsh (Communication Archiving)

Smarsh is the leading compliance archiving platform for regulated financial communications.

```
SMARSH ARCHITECTURE:

  REGULATORY CONTEXT:
  ┌─────────────────────────────────────────────────────────────────┐
  │  SEC Rule 17a-4: Recordkeeping requirements                    │
  │  FINRA Rule 3110: Supervisory procedures                       │
  │  FINRA Rule 2210: Communications with the public               │
  │                                                                 │
  │  ENFORCEMENT (recent):                                          │
  │    $8.2 BILLION in SEC fines (FY2024)                           │
  │    $3+ BILLION in FINRA fines (2025)                            │
  │    Primary cause: off-channel communication failures            │
  │                                                                 │
  │  THIS IS NOT OPTIONAL FOR ANY BD OR RIA.                        │
  └─────────────────────────────────────────────────────────────────┘

  PLATFORM:
  ┌─────────────────────────────────────────────────────────────────┐
  │  Capture: 80+ channel connectors (email, SMS, WhatsApp, Slack) │
  │  Archive: immutable, tamper-proof, searchable                  │
  │  Supervise: policy-based review queues for principals          │
  │  Discover: e-Discovery for legal/regulatory requests           │
  └─────────────────────────────────────────────────────────────────┘
```

007 impact:
- ALL agent-client communications must be archived to Smarsh
- Every message through OpenClaw (M12) → Smarsh connector
- Supervisory review queue: principal must review agent outputs (FINRA 2210)
- Phase 3 integration. Start partnership conversations Phase 1.
- $11B+ in fines (2024-2025) makes this the highest regulatory risk if missed

### 7.3 SEC EDGAR

EDGAR is the SEC's electronic filing system — free, public, no authentication required.

```
SEC EDGAR ARCHITECTURE:

  APIs (data.sec.gov):
  ┌─────────────────────────────────────────────────────────────────┐
  │  CompanyFacts: every XBRL fact ever filed (single JSON per CIK) │
  │  Submissions: filing history per CIK                            │
  │  Full-Text Search (EFTS): search across all filings             │
  │  Filing Documents: HTML, XML, XBRL, iXBRL formats              │
  │                                                                 │
  │  Auth: NONE (free, public)                                      │
  │  Rate limit: 10 requests/second (User-Agent header required)    │
  │  Format: JSON (APIs), HTML/XML/XBRL (filings)                  │
  └─────────────────────────────────────────────────────────────────┘
```

007 impact:
- M11 adapter: REST API wrapper (already exists in 006, adapt)
- Research Specialist uses EDGAR for 10-K, 10-Q, 8-K, proxy filings
- Free API = no vendor approval. Phase 1 ready.
- Rate limit (10 req/s) requires throttling in M6 gateway



---

## PART 8: THE MULTI-CUSTODIAL INTEGRATION PROBLEM

This is the core problem 007 solves.

```
THE PROBLEM:
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  Average wealth management firm: 20-35 separate tech platforms      │
│  Advisors spend 40% of time on manual data entry and reconciliation │
│                                                                     │
│  CURRENT INTEGRATION APPROACHES:                                    │
│                                                                     │
│  1. MuleSoft (Salesforce-owned)                                     │
│     - API-led connectivity (System → Process → Experience layers)   │
│     - Cost: $150K-$500K+ for enterprise implementation              │
│     - Timeline: 3-6 months initial, 6-12 months full               │
│     - ROI: 426-445% over 3 years                                   │
│     - BUT: Integration only. No AI agent. No compliance layer.     │
│                                                                     │
│  2. Point-to-point (most firms today)                               │
│     - Custom code per custodian x per system                        │
│     - N x M problem: 5 custodians x 7 systems = 35 integrations   │
│     - Brittle, expensive, no shared trust layer                    │
│                                                                     │
│  3. Aggregators (Envestnet, Orion, Black Diamond)                   │
│     - Pre-built custodian connections                               │
│     - BUT: locked to their ecosystem                               │
│     - No cross-platform agent intelligence                         │
│                                                                     │
│  007's DIFFERENTIATION:                                             │
│     - MCP adapters (universal protocol, not point-to-point)        │
│     - Trust layer (identity + authority + MNPI) BETWEEN systems    │
│     - AI agent that REASONS across all connected systems           │
│     - Compliance built in, not bolted on                           │
│     - Works WITH existing aggregators (wraps them)                 │
│     - 5 archetype profiles (not one-size-fits-all)                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## PART 9: OMS/EMS TRADE LIFECYCLE

Understanding the full trade lifecycle is essential for 007's Execution Specialist.

```
TRADE LIFECYCLE — BUY-SIDE:

  PORTFOLIO MANAGER
       │ investment decision
       ▼
  ┌─────────┐
  │   PMS   │  Portfolio Management System
  │         │  (model portfolios, target allocations)
  └────┬────┘
       │ rebalance orders
       ▼
  ┌─────────┐
  │   OMS   │  Order Management System
  │         │  (capture, compliance check, allocation)
  │         │  Pre-trade: restricted list, concentration limit
  │         │  State: NEW → VALIDATED → ROUTED → FILLED
  └────┬────┘
       │ routed orders
       ▼
  ┌─────────┐
  │   EMS   │  Execution Management System
  │         │  (algo selection, venue routing, DMA)
  │         │  FIX connectivity to brokers/exchanges
  └────┬────┘
       │ FIX messages
       ▼
  ┌─────────┐
  │ BROKER/ │  Executing broker or exchange
  │EXCHANGE │  Fills order, sends ExecutionReport (FIX 8)
  └────┬────┘
       │ execution reports
       ▼
  ┌─────────┐
  │CLEARING │  DTCC / Prime Broker
  │         │  Netting, novation, settlement (T+1)
  └────┬────┘
       │ settlement confirmation
       ▼
  ┌─────────┐
  │CUSTODIAN│  Schwab / Fidelity / Pershing / Prime Broker
  │         │  Asset custody, position updates, statements
  └─────────┘
```

007's Execution Specialist sits at the OMS layer:
- Receives intent from advisor
- Calls Compliance Specialist (pre-trade check via OPA)
- Prepares order (HITL gate: advisor approves)
- Submits to custodian API (Tier 3/4) or OMS/FIX (Tier 2/5)
- Tracks execution reports, logs to M10 WORM

007 does NOT replace the OMS/EMS. It WRAPS it.

### 9.1 Prime Brokerage (Tier 5 Hedge Funds)

```
PRIME BROKER SERVICES (bundled):
┌─────────────────────────────────────────────────────────────────┐
│  - Trade execution (multi-venue)                                │
│  - Clearing and settlement                                      │
│  - Asset custody (segregated)                                   │
│  - Securities lending (for short selling)                       │
│  - Margin financing (leverage)                                  │
│  - Consolidated reporting                                       │
│                                                                 │
│  Major: Goldman Sachs, Morgan Stanley, JPMorgan                 │
│  Multi-prime: most large HFs use 2-3 prime brokers              │
│                                                                 │
│  007 wraps prime broker reporting APIs.                         │
│  Pod isolation in OPA aligns with fund/account structure.       │
│  Multi-prime: M11 needs adapter per prime broker.               │
└─────────────────────────────────────────────────────────────────┘
```

---

## PART 10: COMPLETE PROTOCOL MAP

```
┌──────────────────┬────────────┬──────────────┬─────────┬─────────┐
│ System           │ Protocol   │ Auth         │ Phase   │ Tier    │
├──────────────────┼────────────┼──────────────┼─────────┼─────────┤
│ SEC EDGAR        │ REST/JSON  │ None (free)  │ 1       │ All     │
│ Salesforce FSC   │ REST/SOQL  │ OAuth 2.0    │ 2       │ 3/4     │
│ Orion            │ REST/JSON  │ OAuth/Basic  │ 2       │ 3/4     │
│ eMoney           │ REST/JSON  │ OAuth 2.0    │ 2       │ 3/4     │
│ Schwab           │ REST+SFTP  │ OAuth 2.0    │ 2       │ 3/4     │
│ Fidelity         │ REST/JSON  │ OAuth 2.0    │ 3       │ 3/4     │
│ Pershing         │ REST/JSON  │ OAuth 2.0    │ 3       │ 3       │
│ Wealthbox/Redtail│ REST/JSON  │ API key      │ 3       │ 4       │
│ Smarsh           │ REST/JSON  │ API key      │ 3       │ All     │
│ Bloomberg B-PIPE │ BLPAPI     │ License+cert │ 4       │ 1/2/5   │
│ FactSet          │ MCP native │ OAuth 2.0    │ 4       │ 2/5     │
│ SS&C Eze         │ gRPC       │ OAuth 2.0    │ 4       │ 5       │
│ FIX (brokers)    │ FIX 4.2    │ Session auth │ 4       │ 2/5     │
│ Envestnet        │ REST/JSON  │ OAuth 2.0    │ 4       │ 3/4     │
│ ComplySci        │ REST/JSON  │ API key      │ 4       │ 2/5     │
│ NICE SURVEIL-X   │ Data feed  │ Enterprise   │ 5       │ 1       │
│ SWIFT ISO 20022  │ XML/MX     │ PKI/BIC      │ 5       │ 1       │
├──────────────────┼────────────┼──────────────┼─────────┼─────────┤
│ Bedrock LLM      │ REST/JSON  │ IAM SigV4    │ 1       │ Cloud   │
│ OPA              │ REST/JSON  │ localhost    │ 1       │ All     │
└──────────────────┴────────────┴──────────────┴─────────┴─────────┘

  NOT all REST. 3 non-REST protocols: BLPAPI, gRPC, FIX.
  M11 adapter layer must be polyglot.
```

---

## PART 11: CRITICAL FINDINGS THAT CHANGE OR VALIDATE 007

### Finding 1: FactSet Has a Native MCP Server (December 2025)

FactSet launched the industry's first production-grade MCP server. Direct LLM-to-data access without intermediaries. This is exactly what 007 proposes for all vendors via M11 adapters. 007's MCP adapter pattern is validated by the market. More vendors will follow.

### Finding 2: Bloomberg B-PIPE Uses BLPAPI (Not REST)

Bloomberg's data feed uses a proprietary binary protocol. M11 Bloomberg adapter must use the Python SDK (blpapi), not REST. M11 adapters are NOT all TypeScript REST wrappers. The adapter layer must be polyglot. ARCH-07 listed M11 as TypeScript-only — needs correction.

### Finding 3: SS&C Eze Uses gRPC (Not REST)

Eze EMS xAPI uses Google's gRPC framework. Binary protocol with proto file definitions. M11 must support gRPC adapters alongside REST and BLPAPI.

### Finding 4: Fidelity Vendor Approval Takes 6-12 Months

Longest approval cycle of any custodian. Security assessment, data handling review, API standards compliance, likely SOC 2 Type II required. Application must be submitted Phase 0 Week 1. Single longest lead-time item in the entire project.

### Finding 5: Household Model Mismatch Across Systems

SF FSC Household (family relationship), Orion Household (portfolio management), Schwab Household (custodial grouping) — three different concepts, same word. A family may have 1 SF Household, 2 Orion Households, 3 Schwab master accounts. M3 canonical schema must define ONE Household model mapping to all three. Biggest schema translation risk. Expect 3-5 revisions.

### Finding 6: Cost Basis Normalization Is a Regulatory Risk

Schwab defaults to specific lot identification. Fidelity uses average cost for mutual funds, specific lot for equities. Orion depends on custodian feed. M7 translators must normalize. Getting this wrong = incorrect tax reporting = regulatory violation.

### Finding 7: Smarsh Archiving Is Non-Negotiable

$8.2B SEC fines (FY2024) + $3B+ FINRA fines (2025) for off-channel communication failures. Every agent-client message through OpenClaw must be archived. Highest regulatory risk if missed. Phase 3 integration, start conversations Phase 1.

### Finding 8: 007 Never Connects Directly to DTCC/Fedwire/CHIPS

Infrastructure-of-infrastructure. Custodians handle clearing and settlement. 007 submits orders to custodian APIs. No DTCC/Fedwire/CHIPS adapters needed.

### Finding 9: FIX Is Stateful (Session + Sequence Numbers)

Persistent TCP sessions, sequence number tracking, heartbeat, gap-fill recovery. Not a stateless REST wrapper. Hire FIX specialist contractor for Phase 4. Budget 14 weeks. FIX Bridge must persist session state across pod restarts.

### Finding 10: ISO 20022 Migration Is Complete (November 2025)

SWIFT CBPR+ coexistence ended Nov 2025. Only MX (XML) format needed. No legacy MT support required. Simplifies Phase 5 scope.

---

## PART 12: ARCHITECTURE CORRECTIONS REQUIRED

| Document | Correction | Severity |
|----------|-----------|----------|
| ARCH-07 (Tech Stack) | M11 listed as TypeScript-only. Must add Python (BLPAPI) and gRPC. | HIGH |
| ARCH-03 (Modules) | M11 adapter count underestimated. Need 17+ adapters across 3 protocols. | MEDIUM |
| ARCH-03 (Modules) | M3 canonical Household type needs multi-source mapping design. | HIGH |
| IMPL-01 (Plan) | Phase 0: add Fidelity application as hard dependency Week 1. | HIGH |
| IMPL-01 (Plan) | Phase 0: add Smarsh partnership conversation. | MEDIUM |
| ARCH-06 (Compliance) | Cost basis normalization not addressed. Add to M7 translator spec. | HIGH |
| ARCH-05 (Multi-Agent) | Execution Specialist must handle T+1 settlement tracking. | LOW |
| ARCH-08 (Networking) | Bloomberg B-PIPE via PrivateLink validates network design. Add reference. | LOW |

---

## SUMMARY

17 systems studied across 11 infrastructure categories. 10 critical findings. 8 architecture corrections.

The financial infrastructure is real, complex, and well-documented. 007's architecture aligns with how these systems actually work. The MCP adapter pattern is validated by FactSet's production MCP server. The corrections identified are manageable and do not change the fundamental design.

The three biggest risks uncovered:
1. Household model mismatch (schema landmine)
2. Fidelity 6-12 month vendor approval (timeline risk)
3. Smarsh archiving ($11B+ in fines if missed)

---

*RES-08 — Project 007 FSI Interoperability Platform*
*Financial Infrastructure Deep Research*
*17 systems, 11 categories, 10 critical findings, 8 architecture corrections*
