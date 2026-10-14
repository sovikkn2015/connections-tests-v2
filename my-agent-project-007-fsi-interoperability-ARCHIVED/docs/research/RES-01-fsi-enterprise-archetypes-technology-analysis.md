# FSI Enterprise Archetypes: Technology Stack & Integration Analysis

## Purpose

This document maps the 5 distinct FSI enterprise archetypes, their technology stacks, integration surfaces, compliance regimes, and data sensitivity boundaries. It is designed to inform the architecture of a modular AI agent platform that must plug into any of these environments.

---

## Table of Contents

1. [Tier 1: Investment Bank / Sell-Side](#tier-1-investment-bank--sell-side)
2. [Tier 2: Buy-Side / Asset Manager](#tier-2-buy-side--asset-manager)
3. [Tier 3: Wealth Management / Broker-Dealer](#tier-3-wealth-management--broker-dealer)
4. [Tier 4: Independent RIA](#tier-4-independent-ria)
5. [Tier 5: Hedge Fund / Alternative Investment](#tier-5-hedge-fund--alternative-investment)
6. [Cross-Archetype Integration Matrix](#cross-archetype-integration-matrix)
7. [Agent Platform Design Implications](#agent-platform-design-implications)

---

## Tier 1: Investment Bank / Sell-Side

**Representative firms:** Goldman Sachs, Morgan Stanley, JP Morgan, Citigroup, Bank of America Securities, Barclays, Deutsche Bank, UBS Investment Bank

### Technology Stack

| Function | Systems | Notes |
|----------|---------|-------|
| **Front Office / Research** | Bloomberg Terminal, Refinitiv Eikon (now LSEG Workspace), proprietary research platforms, internal knowledge management (Confluence/SharePoint) | Analysts live in Bloomberg. Proprietary research platforms are the crown jewels — they generate alpha and drive client relationships. |
| **Trading — Equities** | Proprietary OMS/EMS (e.g., Goldman's SecDB/Marquee, Morgan Stanley's Matrix), FIX 4.2/4.4/5.0 protocol, direct market access (DMA), smart order routers, algorithmic trading engines (VWAP, TWAP, implementation shortfall) | Most Tier 1 banks build proprietary. Third-party EMS (FlexTrade, Fidessa/ION) used selectively. FIX is the universal language. |
| **Trading — Fixed Income** | Bloomberg TSOX, Tradeweb, MarketAxess, proprietary e-trading platforms, voice brokerage (still ~40% of FI volume) | Fixed income is less electronic than equities. RFQ (request for quote) protocols dominate. |
| **Trading — FX** | EBS, Reuters Matching, proprietary single-dealer platforms (e.g., JP Morgan Execute, Barclays BARX), FXall, Currenex | FX is highly fragmented. Banks run their own liquidity pools. |
| **CRM** | Salesforce Financial Services Cloud, proprietary CRM, some Microsoft Dynamics | Salesforce FSC is gaining share but many banks still run proprietary systems for institutional sales coverage. |
| **Compliance / Surveillance** | NICE Actimize SURVEIL-X (trade + comms surveillance), Behavox (behavioral analytics, NLP on comms), proprietary surveillance engines, Global Relay / Smarsh (communications archiving), Bloomberg Vault | NICE Actimize is the market leader. Behavox uses AI/NLP to detect misconduct patterns across voice, email, chat. 60% of firms still don't monitor newer channels like Teams/WhatsApp. |
| **Market Data** | Bloomberg B-PIPE (real-time), Refinitiv Elektron/Real-Time, ICE Data Services, proprietary data lakes (Snowflake, Databricks, on-prem Hadoop), alternative data vendors (Quandl, Orbital Insight, satellite imagery) | B-PIPE is the institutional-grade Bloomberg feed. Banks build massive internal data lakes combining market data, transaction data, and alternative data. |
| **Risk Management** | Proprietary VaR engines, stress testing frameworks (CCAR/DFAST mandated), Murex (derivatives pricing/risk), Calypso, proprietary Monte Carlo simulations, FRTB-compliant market risk engines | Risk is almost entirely proprietary at Tier 1. Regulators require banks to build and validate their own models. |
| **Settlement / Operations** | DTCC (equities), Euroclear/Clearstream (fixed income), CLS (FX), SWIFT/ISO 20022 (payments), proprietary middle-office reconciliation | SWIFT completed migration to ISO 20022 for cross-border payments in November 2025. MT→MX transition is complete for CBPR+. |
| **Integration / Middleware** | MuleSoft, Apache Kafka (event streaming), IBM MQ, proprietary ESBs, Solace (low-latency messaging), REST/gRPC APIs, SFTP (legacy file transfers) | Kafka is the backbone for real-time event streaming. Legacy systems still rely on SFTP batch files and IBM MQ. |

### Critical Integration Points for an AI Agent

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TIER 1: AGENT INTEGRATION SURFACE                        │
│                                                                             │
│  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │ RESEARCH     │────▶│ CLIENT DATA  │────▶│ COMPLIANCE   │                │
│  │ Bloomberg    │     │ CRM (SFSC)   │     │ NICE Actimize│                │
│  │ Refinitiv    │     │ Proprietary  │     │ Behavox      │                │
│  │ Internal KB  │     │ Client DB    │     │ Global Relay │                │
│  └──────┬──────┘     └──────┬───────┘     └──────┬───────┘                │
│         │                   │                     │                        │
│         ▼                   ▼                     ▼                        │
│  ┌──────────────────────────────────────────────────────────┐              │
│  │              AI AGENT ORCHESTRATION LAYER                 │              │
│  │  Must enforce: information barriers, MNPI boundaries,    │              │
│  │  pre-trade compliance, communication logging             │              │
│  └──────────────────────────────────────────────────────────┘              │
│         │                   │                     │                        │
│         ▼                   ▼                     ▼                        │
│  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │ EXECUTION    │     │ RISK         │     │ SETTLEMENT   │                │
│  │ OMS/EMS      │     │ VaR Engine   │     │ DTCC/SWIFT   │                │
│  │ FIX Protocol │     │ Stress Test  │     │ ISO 20022    │                │
│  │ Algo Engines │     │ FRTB         │     │ Reconciliation│               │
│  └─────────────┘     └──────────────┘     └──────────────┘                │
│                                                                             │
│  PROTOCOLS: FIX 4.2/4.4/5.0, SWIFT/ISO 20022, REST, gRPC, Kafka,         │
│             SFTP (legacy), IBM MQ, proprietary binary protocols            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Protocols Used

| Protocol | Where | Direction |
|----------|-------|-----------|
| **FIX 4.2/4.4/5.0** | Order routing, execution, allocation | Bidirectional with exchanges, ECNs, dark pools, buy-side clients |
| **SWIFT / ISO 20022** | Payments, settlement instructions, confirmations | Bidirectional with correspondent banks, custodians, clearinghouses |
| **REST APIs** | CRM integration, internal microservices, client portals | Internal + client-facing |
| **gRPC** | Low-latency internal service mesh, pricing engines | Internal only |
| **Kafka** | Event streaming — trade events, market data, risk updates | Internal backbone |
| **SFTP** | Legacy file transfers — end-of-day positions, reconciliation files, regulatory reports | Bidirectional with counterparties, regulators |
| **IBM MQ / Solace** | Message queuing for middle/back office workflows | Internal |
| **Proprietary binary** | Ultra-low-latency market data feeds, co-located exchange connectivity | Exchange-facing |

### Compliance & Regulatory Requirements

- **Dodd-Frank / Volcker Rule**: Restrictions on proprietary trading; banks must prove market-making vs. prop trading
- **Basel III/IV / FRTB**: Capital adequacy, market risk, credit risk — drives risk engine requirements
- **CCAR/DFAST**: Annual stress testing mandated by the Fed — proprietary models required
- **MAR (Market Abuse Regulation)**: Trade surveillance for insider trading, market manipulation
- **MiFID II** (EU operations): Best execution reporting, transaction reporting, research unbundling
- **Reg SHO**: Short selling rules and locate requirements
- **SEC Rule 17a-4 / FINRA 4511**: Communications archiving — all electronic communications must be retained and searchable
- **Information barriers (Chinese walls)**: Strict separation between research, trading, investment banking, and private-side information

### Data Sensitivity & MNPI Boundaries

**MNPI (Material Non-Public Information)** is the single most critical data boundary at Tier 1:

- **Private-side information**: M&A deal flow, capital raises, restructuring — NEVER crosses to public-side (sales, trading, research)
- **Research**: Analyst opinions before publication are MNPI. Once published, they become public.
- **Client order flow**: Knowledge of large pending orders is MNPI. An agent must NEVER surface order flow data to research or other clients.
- **Information barriers are enforced architecturally**: Separate databases, separate access controls, separate physical floors in many cases
- **Agent implication**: An AI agent operating in this environment must be aware of which "side of the wall" it is operating on. It cannot aggregate data across the barrier.

### "Research → Client → Compliance → Execution" Chain

At a Tier 1 bank, this chain means:

1. **Research**: Analyst publishes a sector report via the proprietary research platform. Report is distributed to institutional clients via Bloomberg, email, client portal.
2. **Client Data**: Institutional sales coverage team uses CRM (Salesforce FSC or proprietary) to track which clients received the research, their current positions, and their investment mandates.
3. **Compliance**: Before the salesperson can recommend a trade based on the research, compliance must verify: (a) the research is published (not MNPI), (b) the client's mandate allows the security, (c) no restricted list conflicts, (d) the communication is logged and archived.
4. **Execution**: Client places an order via FIX. The OMS routes it through the algo engine or to the trading desk. Post-trade, the allocation is confirmed, settled via DTCC/SWIFT, and reconciled.

**Agent opportunity**: Automate the pre-trade compliance check, surface relevant research to the right clients based on their mandates, and generate post-trade summaries — all while respecting information barriers.

---

## Tier 2: Buy-Side / Asset Manager

**Representative firms:** Fidelity Investments, T. Rowe Price, Wellington Management, Capital Group, PIMCO, Vanguard, Invesco, abrdn, Franklin Templeton

### Technology Stack

| Function | Systems | Notes |
|----------|---------|-------|
| **Portfolio Management** | BlackRock Aladdin, Charles River IMS (State Street), SimCorp Dimension, SS&C Eze, Limina | Aladdin is the dominant platform — manages ~$21.6 trillion in assets across 200+ institutions. Charles River IMS is the primary competitor, now owned by State Street. SimCorp (acquired by Deutsche Börse) is strong in Europe. |
| **Order Management (OMS)** | Charles River OMS, Aladdin OMS, Bloomberg AIM, Eze OMS (SS&C), Flyer (ION) | OMS is the system of record for the investment process. Handles portfolio rebalancing, compliance checks, and post-trade allocations. |
| **Execution Management (EMS)** | Bloomberg EMSX, Virtu Triton, FlexTrade, Eze EMS, Fidessa (ION) | EMS is the trader's cockpit — real-time market access, algo selection, TCA (transaction cost analysis). Trend is toward OMS/EMS convergence. |
| **Trading Protocol** | FIX 4.2/4.4 (dominant), FIX 5.0 SP2 (emerging), RFQ protocols for fixed income | FIX is universal for buy-side→sell-side order routing. 78% of global equity volume is now electronic. |
| **CRM** | Salesforce Financial Services Cloud, proprietary, Microsoft Dynamics (some) | Salesforce FSC is gaining share for institutional distribution/wholesaling. Many asset managers still use proprietary systems for client coverage. |
| **Compliance** | Charles River compliance engine (pre-trade, post-trade, restricted lists), Aladdin compliance module, FIS InvestOne compliance, proprietary rule engines | Pre-trade compliance is critical — every order must pass compliance checks before execution. Restricted lists, concentration limits, investment guideline monitoring. |
| **Market Data / Research** | Bloomberg Terminal + B-PIPE, FactSet, MSCI, S&P Capital IQ, Refinitiv, ICE, Morningstar Direct, proprietary research | FactSet is the dominant analytics platform for buy-side fundamental research. MSCI provides ESG data, factor models, and benchmarks. |
| **Risk Management** | Aladdin Risk (integrated), Axioma (now SimCorp), MSCI RiskMetrics/Barra, Bloomberg PORT, FactSet Risk | Aladdin Risk is deeply integrated with portfolio management. Axioma provides factor-based risk models. MSCI Barra is the industry standard for equity factor risk. |
| **Performance / Attribution** | FactSet, Bloomberg PORT, StatPro (Confluence), Eagle PACE, proprietary | GIPS (Global Investment Performance Standards) compliance is required for marketing performance to institutional clients. |
| **Fund Accounting / Operations** | SS&C Advent Geneva, Eagle Investment Systems, SimCorp, BNY Mellon Eagle | Back-office NAV calculation, reconciliation, corporate actions processing. |
| **Integration / Middleware** | MuleSoft, Kafka, IBM MQ, proprietary ETL pipelines, SFTP (still dominant for custodian feeds), REST APIs | Custodian data feeds are still largely SFTP-based batch files. Real-time integration is emerging but not universal. |

### Critical Integration Points for an AI Agent

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TIER 2: AGENT INTEGRATION SURFACE                        │
│                                                                             │
│  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │ RESEARCH     │────▶│ PORTFOLIO    │────▶│ COMPLIANCE   │                │
│  │ FactSet      │     │ Aladdin/CRD  │     │ Pre-trade    │                │
│  │ Bloomberg    │     │ Portfolio    │     │ Restricted   │                │
│  │ MSCI/S&P    │     │ Holdings    │     │ lists        │                │
│  │ Internal    │     │ Benchmarks  │     │ Guidelines   │                │
│  └──────┬──────┘     └──────┬───────┘     └──────┬───────┘                │
│         │                   │                     │                        │
│         ▼                   ▼                     ▼                        │
│  ┌──────────────────────────────────────────────────────────┐              │
│  │              AI AGENT ORCHESTRATION LAYER                 │              │
│  │  Must enforce: investment guidelines, restricted lists,  │              │
│  │  pre-trade compliance, GIPS attribution, client mandates │              │
│  └──────────────────────────────────────────────────────────┘              │
│         │                   │                     │                        │
│         ▼                   ▼                     ▼                        │
│  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │ EXECUTION    │     │ RISK         │     │ REPORTING    │                │
│  │ OMS → EMS    │     │ Aladdin Risk │     │ Client       │                │
│  │ FIX to       │     │ Axioma       │     │ reporting    │                │
│  │ brokers      │     │ MSCI Barra   │     │ GIPS         │                │
│  └─────────────┘     └──────────────┘     └──────────────┘                │
│                                                                             │
│  PROTOCOLS: FIX 4.2/4.4, REST APIs, SFTP (custodian feeds),              │
│             Kafka, proprietary Aladdin/CRD APIs                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Protocols Used

| Protocol | Where | Direction |
|----------|-------|-----------|
| **FIX 4.2/4.4** | Order routing to sell-side brokers, execution reports, allocations | Outbound to brokers, inbound execution reports |
| **REST APIs** | Aladdin API, FactSet API, Bloomberg BLPAPI, CRM integration | Bidirectional with vendors and internal systems |
| **SFTP** | Custodian position files, NAV files, reconciliation, corporate actions | Inbound from custodians (daily batch), outbound trade files |
| **Kafka / MQ** | Internal event streaming — trade events, position updates, risk recalculations | Internal |
| **SWIFT / ISO 20022** | Settlement instructions to custodians, fund transfer instructions | Outbound to custodians and transfer agents |
| **Proprietary APIs** | Aladdin SDK, Charles River API, SimCorp API | Deep integration with PMS/OMS platforms |
| **FpML** | Derivatives trade confirmations and lifecycle events | Bidirectional with counterparties |

### Compliance & Regulatory Requirements

- **Investment Company Act of 1940**: Governs mutual funds — diversification requirements, leverage limits, liquidity rules
- **Investment Advisers Act of 1940**: Fiduciary duty to clients, Form ADV disclosure, code of ethics
- **SEC Rule 206(4)-7**: Compliance program requirements — written policies, annual review, CCO designation
- **SEC Rule 38a-1**: Fund compliance programs — board oversight, annual reporting
- **ERISA**: For pension fund mandates — prudent investor rule, prohibited transactions
- **MiFID II** (EU): Best execution, research unbundling (research payments must be separated from execution commissions)
- **GIPS**: Global Investment Performance Standards — required for marketing performance to institutional clients
- **Form PF**: Reporting for private fund advisers — systemic risk monitoring
- **Restricted lists**: Securities that cannot be traded due to MNPI possession (e.g., the firm's research team has non-public information from a company meeting)
- **Personal trading / Code of Ethics**: Employee trading must be pre-cleared and reported

### Data Sensitivity & MNPI Boundaries

- **Portfolio holdings**: Current holdings are MNPI until publicly disclosed (typically quarterly via 13F filings). An agent must NEVER leak current holdings to external parties.
- **Trading intentions**: Knowledge that a large fund is about to buy/sell a security is extremely sensitive MNPI. Front-running is a federal crime.
- **Research / analyst notes**: Internal research notes, company meeting notes, and investment theses are MNPI until the investment decision is made and disclosed.
- **Client mandate details**: Investment guidelines, fee structures, and AUM figures for specific clients are confidential.
- **Restricted lists**: The existence of a security on the restricted list itself implies MNPI possession — the list itself is sensitive.
- **Agent implication**: An AI agent must be scoped to specific portfolios/mandates. It cannot aggregate holdings across strategies in a way that reveals firm-wide positioning. Pre-trade compliance must be enforced before any order suggestion.

### "Research → Client → Compliance → Execution" Chain

At a Tier 2 asset manager, this chain means:

1. **Research**: Portfolio manager or analyst identifies an investment opportunity using FactSet, Bloomberg, MSCI data, and proprietary research. They build a thesis in the research management system.
2. **Client Data**: The PM determines which portfolios/mandates should participate in the trade based on investment guidelines, benchmark tracking, and client-specific restrictions (e.g., no tobacco stocks for ESG mandates).
3. **Compliance**: The proposed trade is submitted to the OMS (Aladdin/Charles River). Pre-trade compliance engine checks: restricted list, concentration limits, investment guideline compliance, diversification rules, leverage limits. Trade is blocked or approved.
4. **Execution**: Approved orders flow from OMS → EMS → FIX to sell-side brokers. Algo selection (VWAP, TWAP, etc.) is made. Post-trade: allocations across accounts, TCA analysis, settlement instructions to custodian.

**Agent opportunity**: Automate research synthesis (summarize FactSet/Bloomberg data for a sector), flag portfolio drift against benchmarks, pre-screen trades against compliance rules, and generate client reporting narratives — all scoped to authorized portfolios only.

---

## Tier 3: Wealth Management / Broker-Dealer

**Representative firms:** Merrill Lynch (Bank of America), UBS Wealth Management, Morgan Stanley Wealth Management, Raymond James, Edward Jones, LPL Financial, Stifel, Wells Fargo Advisors

### Technology Stack

| Function | Systems | Notes |
|----------|---------|-------|
| **CRM** | Salesforce Financial Services Cloud (dominant and growing), Microsoft Dynamics 365, proprietary (legacy wirehouses), Redtail (smaller BDs) | Salesforce FSC is the strategic direction for most wirehouses. Merrill uses a proprietary platform augmented with Salesforce. Morgan Stanley uses proprietary + Salesforce integration. |
| **Portfolio Management / Reporting** | Envestnet Tamarac (dominant for IBDs), Black Diamond (SS&C Advent), Orion Portfolio Solutions, Addepar (UHNW/family office), Morningstar Office, Albridge (Pershing) | Envestnet is the operating system for modern wealth management — portfolio accounting, rebalancing, reporting, billing in one platform. Tamarac serves 10,000+ advisory firms. |
| **Financial Planning** | eMoney Advisor (Fidelity-owned, dominant), MoneyGuidePro (Envestnet), RightCapital, Advizr, NaviPlan (InvestCloud) | eMoney is the market leader for comprehensive financial planning. MoneyGuidePro is strong in goal-based planning. RightCapital is gaining share with younger advisors. |
| **Custodian / Clearing** | Self-clearing (wirehouses: Merrill, Morgan Stanley, Wells Fargo), Pershing (BNY Mellon) for IBDs, National Financial Services (Fidelity), Schwab Advisor Services | Wirehouses self-clear. Independent broker-dealers use Pershing or NFS. The custodian relationship defines the technology integration surface. |
| **Trading** | Custodian trading platforms (Schwab Advisor Center, Fidelity Wealthscape, Pershing NetX360), model marketplaces (Envestnet, Orion), iRebal (TD Ameritrade/Schwab), tRx (Orion) | Most wealth advisors trade through their custodian's platform. Model marketplaces allow advisors to subscribe to third-party model portfolios and auto-rebalance. |
| **Compliance / Supervision** | Smarsh (communications archiving — email, social, text), Global Relay (archiving + surveillance), NICE Actimize (trade surveillance for larger BDs), RegEd (licensing, CE tracking), Compliance11, SilverBullet | FINRA requires all broker-dealer communications to be archived and supervisable. Smarsh and Global Relay dominate archiving. Larger BDs add trade surveillance. |
| **Account Opening / Onboarding** | DocuSign, Laser App (SS&C), Quik! Forms, custodian-specific NIGO (not in good order) workflows | Account opening is still paper-heavy in many BDs. Digital onboarding is a major pain point and opportunity. |
| **Client Portal** | Envestnet client portal, Orion client portal, Black Diamond client portal, proprietary (wirehouses) | Client-facing portals for performance reporting, document vault, secure messaging. |
| **Integration / Middleware** | Envestnet Data Aggregation, Plaid, Yodlee, MX, custodian APIs (Schwab API, Fidelity Integration Xchange), Quovo (Plaid), DTCC/NSCC for clearing | Data aggregation (Plaid, Yodlee, MX) pulls held-away account data. Custodian APIs are the primary integration surface. |

### Critical Integration Points for an AI Agent

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TIER 3: AGENT INTEGRATION SURFACE                        │
│                                                                             │
│  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │ RESEARCH /   │────▶│ CLIENT DATA  │────▶│ COMPLIANCE   │                │
│  │ PLANNING     │     │ CRM (SFSC)   │     │ Smarsh       │                │
│  │ eMoney       │     │ Household    │     │ Global Relay  │                │
│  │ MoneyGuide   │     │ Goals        │     │ FINRA rules   │                │
│  │ Morningstar  │     │ Accounts     │     │ Reg BI        │                │
│  └──────┬──────┘     └──────┬───────┘     └──────┬───────┘                │
│         │                   │                     │                        │
│         ▼                   ▼                     ▼                        │
│  ┌──────────────────────────────────────────────────────────┐              │
│  │              AI AGENT ORCHESTRATION LAYER                 │              │
│  │  Must enforce: Reg BI suitability, communication         │              │
│  │  archiving, supervisory review, client-level access      │              │
│  └──────────────────────────────────────────────────────────┘              │
│         │                   │                     │                        │
│         ▼                   ▼                     ▼                        │
│  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │ EXECUTION    │     │ PORTFOLIO    │     │ REPORTING    │                │
│  │ Custodian    │     │ Envestnet    │     │ Client       │                │
│  │ platform     │     │ Orion        │     │ portal       │                │
│  │ Model mktpl  │     │ Black Diamond│     │ Statements   │                │
│  └─────────────┘     └──────────────┘     └──────────────┘                │
│                                                                             │
│  PROTOCOLS: REST APIs (custodian), SFTP (data feeds), OAuth 2.0,          │
│             Plaid/MX APIs (aggregation), proprietary custodian APIs        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Protocols Used

| Protocol | Where | Direction |
|----------|-------|-----------|
| **REST APIs** | Custodian APIs (Schwab, Fidelity, Pershing), CRM APIs (Salesforce), portfolio platform APIs (Envestnet, Orion), planning tool APIs (eMoney) | Bidirectional — this is the primary integration pattern |
| **OAuth 2.0 / OpenID Connect** | Authentication for custodian APIs, client portal SSO, third-party integrations | Authentication layer |
| **SFTP** | Custodian position/transaction feeds (daily batch), performance data, billing files | Inbound from custodians, outbound trade files |
| **Plaid / MX / Yodlee APIs** | Held-away account aggregation — pulling data from 401(k)s, bank accounts, outside brokerages | Outbound to aggregation providers |
| **FIX** | Limited — only larger BDs with direct market access. Most trades go through custodian platforms. | Outbound to exchanges (wirehouses only) |
| **DTCC/NSCC** | Trade clearing and settlement (for self-clearing BDs) | Bidirectional with clearinghouse |
| **Proprietary custodian protocols** | Schwab Advisor Center API, Fidelity Integration Xchange (FIX), Pershing NetX360 API | Custodian-specific |

### Compliance & Regulatory Requirements

- **FINRA Rules**: Broker-dealers are FINRA members. Rules 2111 (suitability, now largely superseded by Reg BI), 3110 (supervision), 3120 (supervisory control system), 4511 (books and records)
- **Regulation Best Interest (Reg BI)**: SEC rule effective June 2020. Broker-dealers must act in the "best interest" of retail customers when making recommendations. Four obligations: disclosure, care, conflict of interest, compliance. This is NOT a fiduciary standard but is higher than the old suitability standard.
- **SEC Rule 17a-4**: Electronic communications must be retained in non-rewritable, non-erasable format (WORM). Applies to email, text, social media, chat.
- **FINRA Rule 2210**: Communications with the public — advertising, correspondence, and institutional communications must be fair, balanced, and not misleading. Supervisory review required.
- **FINRA Rule 3110**: Supervision — every BD must have a supervisory system, written supervisory procedures (WSPs), and designated supervisors for each registered rep.
- **Anti-Money Laundering (AML)**: BSA/AML compliance — CIP (Customer Identification Program), SAR filing, CTR reporting
- **Reg BI Form CRS**: Customer Relationship Summary — must be delivered to retail investors at account opening

### Data Sensitivity & MNPI Boundaries

- **Client PII**: Name, SSN, date of birth, address, financial account numbers — protected under Reg S-P (privacy), GLBA, state privacy laws
- **Account balances and holdings**: Client-specific financial data. Not MNPI in the securities law sense (these are retail accounts, not institutional), but highly sensitive under privacy regulations.
- **Financial plans**: Detailed financial plans (eMoney, MoneyGuidePro) contain comprehensive personal financial data — income, expenses, insurance, estate plans, tax returns. Extremely sensitive.
- **Communication records**: All advisor-client communications are archived and subject to supervisory review. An AI agent's interactions with clients MUST be archived and supervisable.
- **Suitability / Reg BI documentation**: Records of why a recommendation was made, the alternatives considered, and why the recommendation was in the client's best interest. These records are subject to FINRA examination.
- **Agent implication**: Every AI agent interaction that could be construed as a "recommendation" must be logged, archived, and supervisable. The agent must document the Reg BI analysis (care obligation) for any investment suggestion. Agent outputs to clients are "communications with the public" under FINRA 2210.

### "Research → Client → Compliance → Execution" Chain

At a Tier 3 wealth management firm, this chain means:

1. **Research**: Advisor reviews market research (Morningstar, firm research, third-party models), financial planning output (eMoney goals, Monte Carlo simulations), and portfolio analytics (Envestnet/Orion performance, drift analysis).
2. **Client Data**: Advisor pulls up the client's 360-degree view in CRM (Salesforce FSC) — household, accounts, goals, life events, risk profile, investment policy statement (IPS). Cross-references with financial plan.
3. **Compliance**: Before making a recommendation, the advisor must ensure Reg BI compliance: (a) Is this in the client's best interest? (b) Have conflicts been disclosed? (c) Is the recommendation suitable given the client's risk profile and goals? (d) Has the communication been logged? For BDs, the recommendation may require supervisory pre-approval (principal review).
4. **Execution**: Advisor places trades through the custodian platform (Schwab Advisor Center, Fidelity Wealthscape) or through a model marketplace (Envestnet). Rebalancing tools (iRebal, tRx) automate multi-account trading. Trades settle T+1 through the custodian.

**Agent opportunity**: Meeting prep (pull client 360 + portfolio performance + planning gaps), Reg BI documentation automation (generate the "why this recommendation" narrative), rebalancing alerts (flag accounts drifting from target allocation), and client communication drafting (compliant email/letter generation with supervisory review workflow).

---

## Tier 4: Independent RIA

**Representative firms:** Small to mid-size Registered Investment Advisors (1-50 advisors, $50M–$5B AUM), Carson Group, Buckingham Strategic Wealth, Savant Wealth Management, Mariner Wealth Advisors, Creative Planning, Hightower Advisors

### Technology Stack

| Function | Systems | Notes |
|----------|---------|-------|
| **CRM** | Wealthbox (modern, advisor-native), Redtail (most widely adopted by RIAs), Salesforce Financial Services Cloud (larger RIAs), Junxure (CRM Software), AdvisorEngine CRM | Redtail has the largest RIA install base. Wealthbox is the modern challenger with better UX and API-first design. Salesforce FSC is adopted by RIAs above ~$1B AUM. |
| **Portfolio Management / Reporting** | Orion Portfolio Solutions (dominant), Black Diamond (SS&C Advent), Addepar (complex/UHNW), Envestnet Tamarac, Morningstar Office, Kwanti, Riskalyze (now Nitrogen) | Orion is the fastest-growing platform in the RIA space. Addepar dominates for complex multi-asset, multi-custodian reporting (family offices, UHNW). |
| **Financial Planning** | eMoney Advisor (comprehensive, dominant), MoneyGuidePro (goal-based, Envestnet), RightCapital (modern, growing fast), Holistiplan (tax planning), Income Lab (retirement income), fpPathfinder (flowcharts) | The planning stack is increasingly specialized — firms use eMoney for comprehensive plans, Holistiplan for tax, Income Lab for decumulation. RightCapital is gaining share rapidly with younger advisors. |
| **Custodian** | Charles Schwab Advisor Services (~50%+ market share), Fidelity Institutional (~25%), Pershing (BNY Mellon) (~10%), LPL, Altruist (emerging digital custodian) | The "Big 3" (Schwab, Fidelity, Pershing) hold approximately 84% of all custodied RIA assets. 27% of RIAs now use multiple custodians. Schwab's acquisition of TD Ameritrade consolidated its dominance. |
| **Compliance** | RIA in a Box (dominant for small/mid RIAs — compliance calendar, ADV filing, policy templates), SmartRIA (compliance workflow automation), MyRIACompliance, NRS (National Regulatory Services), ACA Compliance Group (larger RIAs) | RIA compliance is SEC/state-regulated (not FINRA). The compliance burden is lighter than broker-dealers but still significant — annual ADV updates, code of ethics, compliance manual, annual review. |
| **Trading / Rebalancing** | Custodian trading platforms (Schwab Advisor Center, Fidelity Wealthscape), iRebal (Schwab, formerly TD Ameritrade), tRx (Orion), Tamarac Rebalancing (Envestnet), Tolerant (55ip, now Franklin Templeton) | Rebalancing is the primary "trading" activity for RIAs. Most don't do individual stock picking — they implement model portfolios. Tax-loss harvesting automation is a key differentiator. |
| **Data Aggregation** | Plaid, Yodlee (Envestnet), MX, ByAllAccounts (Morningstar), Quovo (Plaid) | Aggregation pulls held-away account data (401(k)s, bank accounts, outside brokerages) into the portfolio management platform for a complete picture. |
| **Client Portal / Communication** | Orion client portal, Black Diamond client portal, Addepar client portal, Holistiplan client-facing reports, Calendly/Acuity (scheduling), Loom (video), Hubly (workflow) | Client experience is a competitive differentiator for RIAs. Modern portals include performance reporting, document vault, secure messaging, and financial plan access. |
| **Billing** | Orion billing, Black Diamond billing, Tamarac billing, BillFin, Advyzon | Fee billing is typically AUM-based, calculated quarterly, and debited directly from custodian accounts. |

### Critical Integration Points for an AI Agent

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TIER 4: AGENT INTEGRATION SURFACE                        │
│                                                                             │
│  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │ PLANNING     │────▶│ CLIENT DATA  │────▶│ COMPLIANCE   │                │
│  │ eMoney       │     │ CRM          │     │ RIA in a Box │                │
│  │ RightCapital │     │ (Wealthbox/  │     │ SmartRIA     │                │
│  │ Holistiplan  │     │  Redtail/    │     │ SEC/State    │                │
│  │ Income Lab   │     │  Salesforce) │     │ ADV filing   │                │
│  └──────┬──────┘     └──────┬───────┘     └──────┬───────┘                │
│         │                   │                     │                        │
│         ▼                   ▼                     ▼                        │
│  ┌──────────────────────────────────────────────────────────┐              │
│  │              AI AGENT ORCHESTRATION LAYER                 │              │
│  │  Must enforce: fiduciary duty, client-level access,      │              │
│  │  communication logging, suitability documentation        │              │
│  └──────────────────────────────────────────────────────────┘              │
│         │                   │                     │                        │
│         ▼                   ▼                     ▼                        │
│  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │ EXECUTION    │     │ PORTFOLIO    │     │ AGGREGATION  │                │
│  │ Custodian    │     │ Orion        │     │ Plaid/MX     │                │
│  │ iRebal/tRx   │     │ Black Diamond│     │ Held-away    │                │
│  │ Rebalancing  │     │ Addepar      │     │ accounts     │                │
│  └─────────────┘     └──────────────┘     └──────────────┘                │
│                                                                             │
│  PROTOCOLS: REST APIs (dominant), OAuth 2.0, SFTP (custodian feeds),      │
│             Plaid Link, webhooks, CSV/Excel imports (legacy)               │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Protocols Used

| Protocol | Where | Direction |
|----------|-------|-----------|
| **REST APIs** | CRM (Wealthbox, Redtail, Salesforce), portfolio (Orion, Addepar), planning (eMoney, RightCapital), custodian APIs | Bidirectional — REST is the universal integration language for RIA tech |
| **OAuth 2.0** | Authentication for all SaaS integrations, custodian API access, client portal SSO | Authentication layer |
| **SFTP** | Custodian position/transaction feeds, performance data imports | Inbound from custodians (daily/nightly batch) |
| **Plaid Link / MX Connect** | Client-authorized account linking for held-away data aggregation | Client-initiated, outbound to aggregation providers |
| **Webhooks** | Real-time event notifications from CRM, portfolio platforms, custodians | Inbound event-driven |
| **CSV/Excel** | Legacy data imports, bulk account updates, billing file uploads | Manual/batch — still common in smaller RIAs |
| **Zapier / Make** | No-code integration between tools (CRM → email, portfolio → CRM, etc.) | Bidirectional — used by smaller RIAs without engineering resources |

### Compliance & Regulatory Requirements

- **Investment Advisers Act of 1940**: RIAs are fiduciaries — they must act in the client's best interest at all times. This is a HIGHER standard than Reg BI for broker-dealers.
- **SEC Registration** (>$100M AUM) or **State Registration** (<$100M AUM): Determines the regulatory body
- **Form ADV Part 1 & Part 2**: Annual filing with SEC/state. Part 2 (the "brochure") must be delivered to clients and describes services, fees, conflicts, disciplinary history.
- **SEC Rule 206(4)-7**: Written compliance policies, annual compliance review, designated CCO
- **Code of Ethics (Rule 204A-1)**: Personal trading policies, reporting requirements, insider trading policies
- **Custody Rule (Rule 206(4)-2)**: If the RIA has custody of client assets (e.g., fee deduction authority), annual surprise examination by an independent auditor is required
- **Books and Records (Rule 204-2)**: Must maintain client records, communications, trading records for 5 years
- **Reg S-P**: Privacy of consumer financial information — privacy notice, opt-out rights, safeguarding requirements
- **SEC Marketing Rule (Rule 206(4)-1)**: Governs advertising and testimonials — new rule (effective Nov 2022) allows testimonials and endorsements with disclosures

### Data Sensitivity & MNPI Boundaries

- **Client PII**: Same as Tier 3 — SSN, DOB, financial account numbers, etc. Protected under Reg S-P, GLBA, state privacy laws.
- **Financial plan data**: The most sensitive data in the RIA stack. Comprehensive financial plans contain: income, expenses, tax returns, insurance policies, estate documents, Social Security projections, pension details, health information (for insurance planning). This data is FAR more comprehensive than what a broker-dealer typically holds.
- **Account balances and holdings**: Sensitive but not MNPI in the securities law sense. RIA clients are retail — their individual holdings don't move markets.
- **Fee structures**: Client-specific fee schedules are confidential business information.
- **MNPI is less of a concern at Tier 4**: RIAs primarily invest in public securities using model portfolios. They rarely have access to material non-public information. However, if an RIA manages a concentrated position in a small-cap stock, knowledge of their trading intentions could be material.
- **Agent implication**: The primary data sensitivity concern is PII and comprehensive financial data, not MNPI. An AI agent must enforce strict client-level data isolation (Advisor A cannot see Advisor B's clients). Financial plan data should NEVER be sent to external LLMs without explicit consent and data processing agreements.

### "Research → Client → Compliance → Execution" Chain

At a Tier 4 independent RIA, this chain means:

1. **Research**: Advisor reviews model portfolio performance (Orion, Envestnet), market commentary (Morningstar, DFA, Vanguard research), and financial planning scenarios (eMoney Monte Carlo, RightCapital projections). For tax planning: Holistiplan scans tax returns and identifies opportunities.
2. **Client Data**: Advisor opens the client record in CRM (Wealthbox/Redtail/Salesforce) — household, accounts across custodians, financial plan, notes from last meeting, upcoming life events. Aggregated view includes held-away accounts (Plaid/MX).
3. **Compliance**: RIA fiduciary duty requires documentation of why any recommendation is in the client's best interest. Compliance is lighter than BD — no FINRA supervision requirement — but the fiduciary standard is higher. Annual compliance review (RIA in a Box/SmartRIA) ensures policies are followed. Communications should be logged.
4. **Execution**: Advisor rebalances accounts using iRebal/tRx/Tamarac through the custodian. Model portfolio changes are applied across all accounts subscribing to that model. Tax-loss harvesting is automated where possible. Trades settle T+1 at the custodian.

**Agent opportunity**: This is the highest-impact tier for an AI agent. RIAs are resource-constrained (small teams, no IT staff) and the tech stack is fragmented (5-10 separate SaaS tools). An agent that unifies CRM + portfolio + planning + compliance into a single conversational interface would be transformative. Key use cases: meeting prep, plan review summaries, rebalancing alerts, tax-loss harvesting identification, client communication drafting, compliance documentation.

---

## Tier 5: Hedge Fund / Alternative Investment

**Representative firms:** Bridgewater Associates, Citadel, Two Sigma, DE Shaw, Millennium Management, Point72, AQR Capital, Man Group, Baupost Group, Elliott Management, Renaissance Technologies

### Technology Stack

| Function | Systems | Notes |
|----------|---------|-------|
| **Portfolio Management / Risk** | BlackRock Aladdin (larger multi-strategy), SimCorp Axioma (factor risk), SS&C Eze (Eze OMS/EMS/PMS — dominant for mid-size HFs), Enfusion (cloud-native OEMS+PMS), FundCount (accounting-grade ABOR), Arcesium (D.E. Shaw spinoff — middle/back office), proprietary (quant funds) | SS&C Eze is the most widely adopted platform for hedge funds. Enfusion is the fastest-growing cloud-native alternative. Quant funds (Two Sigma, Renaissance, DE Shaw) build entirely proprietary systems. |
| **Order / Execution Management** | Eze EMS (SS&C), Bloomberg EMSX, Virtu Triton, FlexTrade, direct market access (DMA) via prime brokers, proprietary execution engines (quant funds) | Hedge funds need multi-asset execution — equities, options, futures, FX, credit, swaps — often from a single platform. DMA through prime brokers is critical for speed. |
| **Prime Brokerage** | Goldman Sachs Prime Services, Morgan Stanley Prime Brokerage, JP Morgan Prime Services, Barclays, BNP Paribas, UBS | Prime brokers provide: financing (margin/leverage), securities lending (for short selling), trade execution, custody, capital introduction, operational support. Most funds use 2-3 prime brokers for counterparty diversification. |
| **Trading Protocols** | FIX 4.2/4.4 (dominant), direct market access (DMA), swap execution facilities (SEFs) for OTC derivatives, voice brokerage (for illiquid instruments), proprietary APIs to prime brokers | Multi-asset trading requires multiple protocols. Equities = FIX. OTC derivatives = voice + SEF. FX = ECN APIs. Credit = RFQ platforms (MarketAxess, Tradeweb). |
| **Market Data** | Bloomberg Terminal + B-PIPE, Refinitiv Elektron, ICE Data Services, alternative data providers (Quandl/Nasdaq Data Link, Orbital Insight, Preqin, PitchBook, web scraping, satellite imagery, credit card data, geolocation data) | Alternative data is a key differentiator for hedge funds. Spending on alternative data reached ~$7B+ in 2024. Quant funds consume massive volumes of non-traditional data. |
| **Compliance** | Proprietary compliance engines, ACA Compliance Group (outsourced CCO services), ComplySci (employee trading surveillance), StarCompliance (personal trading monitoring), IHS Markit (now S&P) for regulatory reporting, NICE Actimize (larger funds) | Many hedge funds outsource the CCO function to ACA Compliance Group. Employee personal trading surveillance is critical — ComplySci and StarCompliance dominate. |
| **Fund Administration** | SS&C Technologies (dominant — GlobeOp, Advent Geneva), Citco Fund Services, NAV Consulting, Apex Group, Alter Domus, JTC Group, Maples Group | Fund admin handles: NAV calculation, investor reporting, capital activity processing, regulatory filings. SS&C is the largest fund administrator globally. Most hedge funds outsource fund admin. |
| **Investor Relations / CRM** | Salesforce, Backstop Solutions (purpose-built for alternatives), Dynamo Software, Altvia, proprietary | Backstop is the dominant CRM for hedge funds and alternative asset managers. Salesforce is used by larger, more institutional funds. |
| **Risk Analytics** | Axioma (SimCorp) for factor risk, Bloomberg PORT, MSCI RiskMetrics, proprietary VaR/CVaR engines, stress testing frameworks, Greeks engines (for options-heavy strategies) | Risk management is existential for hedge funds. Most build proprietary risk systems on top of vendor factor models. Real-time P&L and risk monitoring is standard. |
| **Integration / Infrastructure** | Kafka, proprietary message buses, REST/gRPC APIs, FIX engines, co-located servers (for low-latency strategies), cloud (AWS/GCP for non-latency-sensitive workloads), Snowflake/Databricks (data lakes) | Quant funds run massive compute infrastructure. Discretionary funds are increasingly cloud-native. Arcesium provides cloud-based middle/back office. |

### Critical Integration Points for an AI Agent

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TIER 5: AGENT INTEGRATION SURFACE                        │
│                                                                             │
│  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │ RESEARCH /   │────▶│ PORTFOLIO    │────▶│ COMPLIANCE   │                │
│  │ DATA         │     │ Eze/Enfusion │     │ ACA Group    │                │
│  │ Bloomberg    │     │ Aladdin      │     │ ComplySci    │                │
│  │ Alt data     │     │ Proprietary  │     │ Personal     │                │
│  │ Refinitiv    │     │ Holdings     │     │ trading      │                │
│  └──────┬──────┘     └──────┬───────┘     └──────┬───────┘                │
│         │                   │                     │                        │
│         ▼                   ▼                     ▼                        │
│  ┌──────────────────────────────────────────────────────────┐              │
│  │              AI AGENT ORCHESTRATION LAYER                 │              │
│  │  Must enforce: MNPI barriers, personal trading rules,    │              │
│  │  position limits, counterparty exposure, leverage limits │              │
│  └──────────────────────────────────────────────────────────┘              │
│         │                   │                     │                        │
│         ▼                   ▼                     ▼                        │
│  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │ EXECUTION    │     │ RISK         │     │ FUND ADMIN   │                │
│  │ EMS → FIX    │     │ Axioma       │     │ SS&C         │                │
│  │ DMA via PB   │     │ Proprietary  │     │ Citco        │                │
│  │ Multi-asset  │     │ VaR/Greeks   │     │ NAV calc     │                │
│  └─────────────┘     └──────────────┘     └──────────────┘                │
│                                                                             │
│  PROTOCOLS: FIX 4.2/4.4, REST/gRPC, Kafka, proprietary PB APIs,          │
│             SEF protocols (OTC derivatives), SFTP (fund admin feeds)       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Protocols Used

| Protocol | Where | Direction |
|----------|-------|-----------|
| **FIX 4.2/4.4** | Equity/futures order routing, execution reports, allocations to prime brokers | Bidirectional with brokers, exchanges, ECNs |
| **REST / gRPC APIs** | Prime broker APIs, fund admin APIs, market data APIs, internal microservices | Bidirectional |
| **Kafka** | Internal event streaming — trade events, position updates, risk recalculations, P&L streaming | Internal backbone |
| **SFTP** | Fund admin data feeds (NAV, investor statements), prime broker reports, regulatory filings | Bidirectional with fund admin and PBs |
| **SWIFT / ISO 20022** | Wire transfers, subscription/redemption processing, margin calls | Bidirectional with banks and custodians |
| **SEF protocols** | OTC derivative execution on swap execution facilities (Tradeweb, Bloomberg SEF) | Bidirectional with SEFs |
| **Proprietary PB APIs** | Goldman Sachs Marquee API, Morgan Stanley Matrix API, JP Morgan Execute API | Bidirectional with prime brokers |
| **FpML** | OTC derivative trade confirmations, lifecycle events, collateral management | Bidirectional with counterparties |

### Compliance & Regulatory Requirements

- **Investment Advisers Act of 1940**: Hedge fund managers are registered investment advisers (most >$150M AUM). Fiduciary duty applies.
- **Form PF**: Quarterly/annual reporting to SEC for systemic risk monitoring — AUM, leverage, counterparty exposure, liquidity profile. Large hedge fund advisers (>$1.5B) file quarterly.
- **Form ADV**: Annual filing — disclosure of business practices, fees, conflicts, disciplinary history
- **Dodd-Frank**: OTC derivatives must be cleared through central counterparties (CCPs) and reported to swap data repositories (SDRs). SEF trading mandates for certain swaps.
- **SEC Rule 13H**: Large trader reporting — firms that trade >2M shares or $20M in a day must register as large traders
- **SEC Rule 13F**: Quarterly holdings disclosure for managers with >$100M in 13F securities. Holdings become public 45 days after quarter-end.
- **Regulation SHO**: Short selling rules — locate requirements, close-out obligations
- **AIFMD** (EU): Alternative Investment Fund Managers Directive — reporting, leverage limits, depositary requirements for EU-marketed funds
- **Employee personal trading**: Code of ethics requires pre-clearance of personal trades, quarterly transaction reports, annual holdings reports. ComplySci/StarCompliance automate this.
- **Side letters**: Preferential terms for certain investors — must be disclosed and managed carefully

### Data Sensitivity & MNPI Boundaries

- **Portfolio holdings**: Current holdings are EXTREMELY sensitive MNPI. Hedge fund positions are disclosed quarterly via 13F (45-day delay), but real-time holdings reveal the fund's strategy, conviction levels, and trading intentions. Leaking holdings can cause front-running and strategy replication.
- **Trading intentions / order flow**: Knowledge of a hedge fund's pending trades is the most sensitive MNPI in this tier. A $500M equity order will move the market. This data must NEVER be accessible to anyone outside the authorized trading team.
- **Short positions**: Short positions are not disclosed via 13F (only long equity positions). Short book data is among the most closely guarded information in finance.
- **Alternative data sources**: The specific alternative data a fund uses and how they process it is proprietary intellectual property. Revealing data sources can erode alpha.
- **Investor data**: LP (limited partner) identities, commitment amounts, redemption schedules, and side letter terms are highly confidential.
- **Performance data**: Fund returns before official reporting are MNPI. Selective disclosure of performance to some investors but not others is prohibited.
- **Agent implication**: An AI agent in a hedge fund environment operates in the highest MNPI sensitivity zone. The agent must NEVER aggregate or surface: current holdings, pending orders, short positions, or unreported performance. Access must be strictly role-based (PM vs. trader vs. risk vs. compliance vs. IR). Fund-level data isolation is mandatory for multi-strategy platforms (Citadel, Millennium) where each pod operates independently.

### "Research → Client → Compliance → Execution" Chain

At a Tier 5 hedge fund, this chain means:

1. **Research**: Portfolio manager / analyst identifies an investment thesis using Bloomberg, alternative data, proprietary models, and fundamental research. For quant funds: signals are generated algorithmically from data pipelines.
2. **Client Data**: "Client" in this context means the fund's investors (LPs). Investor relations (Backstop/Salesforce) tracks LP commitments, redemption schedules, and communication preferences. The PM doesn't interact with LPs directly — IR handles that. The PM's "client" is the portfolio itself.
3. **Compliance**: Before trading, compliance checks: (a) Is the security on the restricted list? (b) Does the trade comply with fund mandate/offering documents? (c) Position limits and concentration checks. (d) Leverage limits. (e) Personal trading pre-clearance for the PM. (f) For OTC derivatives: counterparty credit checks and ISDA documentation.
4. **Execution**: Orders flow from PMS → OMS → EMS → FIX to brokers/exchanges, or DMA through prime brokers. Multi-asset execution: equities via FIX, derivatives via voice/SEF, FX via ECN. Post-trade: allocations, prime broker reconciliation, fund admin notification for NAV calculation.

**Agent opportunity**: Research synthesis (summarize alternative data signals, earnings transcripts, SEC filings), risk monitoring (real-time P&L alerts, Greeks exposure, counterparty concentration), compliance automation (restricted list checking, personal trading pre-clearance), and investor reporting (generate LP letters, performance attribution narratives). Critical constraint: the agent must operate within strict information barriers, especially at multi-strategy platforms.

---

## Cross-Archetype Integration Matrix

### Protocol Coverage by Tier

| Protocol | Tier 1 (IB) | Tier 2 (AM) | Tier 3 (WM/BD) | Tier 4 (RIA) | Tier 5 (HF) |
|----------|:-----------:|:-----------:|:---------------:|:------------:|:-----------:|
| **FIX 4.2/4.4/5.0** | ★★★ Primary | ★★★ Primary | ★ Wirehouses only | ✗ None | ★★★ Primary |
| **REST APIs** | ★★ Internal | ★★ Growing | ★★★ Primary | ★★★ Primary | ★★ Internal |
| **SWIFT / ISO 20022** | ★★★ Primary | ★★ Settlement | ★ Self-clearing BDs | ✗ None | ★ Wires only |
| **SFTP** | ★★ Legacy | ★★★ Custodian feeds | ★★ Custodian feeds | ★★ Custodian feeds | ★★ Fund admin |
| **Kafka / MQ** | ★★★ Backbone | ★★ Growing | ✗ None | ✗ None | ★★★ Backbone |
| **gRPC** | ★★ Internal | ★ Emerging | ✗ None | ✗ None | ★★ Internal |
| **OAuth 2.0** | ★ Internal | ★ Internal | ★★★ Primary auth | ★★★ Primary auth | ★ Internal |
| **Plaid / MX** | ✗ None | ✗ None | ★★ Aggregation | ★★★ Aggregation | ✗ None |
| **FpML** | ★★ Derivatives | ★ Some | ✗ None | ✗ None | ★★ Derivatives |
| **Proprietary binary** | ★★★ Exchange feeds | ✗ None | ✗ None | ✗ None | ★★ Co-location |
| **CSV/Excel** | ✗ None | ★ Legacy | ★ Legacy | ★★ Still common | ★ Legacy |
| **Zapier / No-code** | ✗ None | ✗ None | ✗ None | ★★ Common | ✗ None |

### CRM Landscape by Tier

| CRM | Tier 1 (IB) | Tier 2 (AM) | Tier 3 (WM/BD) | Tier 4 (RIA) | Tier 5 (HF) |
|-----|:-----------:|:-----------:|:---------------:|:------------:|:-----------:|
| **Salesforce FSC** | ★★ Growing | ★★ Growing | ★★★ Dominant | ★★ Large RIAs | ★ Some |
| **Proprietary** | ★★★ Dominant | ★★ Legacy | ★★ Wirehouses | ✗ None | ★ Some |
| **Wealthbox** | ✗ | ✗ | ✗ | ★★★ Popular | ✗ |
| **Redtail** | ✗ | ✗ | ★ Small BDs | ★★★ Most adopted | ✗ |
| **Backstop** | ✗ | ✗ | ✗ | ✗ | ★★★ Dominant |
| **Microsoft Dynamics** | ★ Some | ★ Some | ★ Some | ✗ Rare | ✗ |

### Compliance Regime Comparison

| Dimension | Tier 1 (IB) | Tier 2 (AM) | Tier 3 (WM/BD) | Tier 4 (RIA) | Tier 5 (HF) |
|-----------|-------------|-------------|-----------------|--------------|-------------|
| **Primary regulator** | SEC, Fed, OCC, FINRA | SEC | SEC, FINRA | SEC or State | SEC |
| **Standard of conduct** | Various (market-making, agency) | Fiduciary | Reg BI (best interest) | Fiduciary | Fiduciary |
| **Communication archiving** | Mandatory (17a-4) | Required (204-2) | Mandatory (17a-4, FINRA 4511) | Required (204-2) | Required (204-2) |
| **Trade surveillance** | Mandatory (MAR, Dodd-Frank) | Pre-trade compliance | FINRA supervision | Minimal | Personal trading surveillance |
| **Information barriers** | Mandatory (Chinese walls) | Restricted lists | Limited | N/A | Pod-level isolation (multi-strat) |
| **Stress testing** | Mandatory (CCAR/DFAST) | Portfolio-level | N/A | N/A | Internal risk management |
| **MNPI sensitivity** | ★★★★★ Extreme | ★★★★ Very High | ★★ Moderate | ★ Low | ★★★★★ Extreme |
| **AI agent logging requirement** | Every interaction | Every interaction | Every interaction (FINRA) | Recommended | Every interaction |

### Data Sensitivity Heat Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DATA SENSITIVITY BY ARCHETYPE                            │
│                                                                             │
│  Data Type              T1(IB)  T2(AM)  T3(WM)  T4(RIA)  T5(HF)          │
│  ─────────────────────  ──────  ──────  ──────  ───────  ──────           │
│  Portfolio holdings     🔴🔴🔴  🔴🔴🔴  🟡      🟡       🔴🔴🔴          │
│  Trading intentions     🔴🔴🔴  🔴🔴🔴  🟢      🟢       🔴🔴🔴          │
│  Short positions        🔴🔴🔴  🔴🔴    N/A     N/A      🔴🔴🔴          │
│  Client PII             🔴🔴    🔴🔴    🔴🔴🔴  🔴🔴🔴   🔴              │
│  Financial plans        N/A     N/A     🔴🔴🔴  🔴🔴🔴   N/A             │
│  M&A / deal flow        🔴🔴🔴  N/A     N/A     N/A      🔴🔴 (activist) │
│  Research (pre-pub)     🔴🔴🔴  🔴🔴    🟡      🟢       🔴🔴            │
│  Investor/LP data       N/A     🔴🔴    🔴      🔴       🔴🔴🔴          │
│  Fee structures         🔴      🔴🔴    🔴      🔴       🔴🔴            │
│  Alt data sources       N/A     🟡      N/A     N/A      🔴🔴🔴          │
│                                                                             │
│  🔴🔴🔴 = Critical MNPI / Extreme sensitivity                              │
│  🔴🔴   = High sensitivity                                                 │
│  🔴     = Sensitive                                                         │
│  🟡     = Moderate                                                          │
│  🟢     = Low / Not applicable                                              │
│  N/A    = Not present in this tier                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Agent Platform Design Implications

### Modular Architecture Requirements

Based on the 5 archetypes, a modular AI agent platform must support the following architectural patterns:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MODULAR AGENT PLATFORM ARCHITECTURE                      │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     AGENT ORCHESTRATION CORE                          │  │
│  │  • Topic routing (intent classification)                              │  │
│  │  • Memory management (conversation + session)                         │  │
│  │  • Guardrails engine (MNPI, PII, compliance)                         │  │
│  │  • Audit logging (every interaction, every data access)              │  │
│  └───────────────────────┬───────────────────────────────────────────────┘  │
│                          │                                                  │
│  ┌───────────────────────┼───────────────────────────────────────────────┐  │
│  │              CONNECTOR / ADAPTER LAYER                                │  │
│  │                                                                       │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │  │
│  │  │ CRM      │ │ PORTFOLIO│ │ MARKET   │ │ COMPLIANCE│ │ EXECUTION│  │  │
│  │  │ Adapter  │ │ Adapter  │ │ DATA     │ │ Adapter   │ │ Adapter  │  │  │
│  │  │          │ │          │ │ Adapter  │ │           │ │          │  │  │
│  │  │ •SF FSC  │ │ •Aladdin │ │ •Bloombg │ │ •NICE     │ │ •FIX     │  │  │
│  │  │ •Wlthbox │ │ •CRD     │ │ •FactSet │ │ •Smarsh   │ │ •Custdn  │  │  │
│  │  │ •Redtail │ │ •Orion   │ │ •MSCI    │ │ •RIA Box  │ │ •DMA     │  │  │
│  │  │ •Backstop│ │ •Eze     │ │ •Refinitv│ │ •ComplySci│ │ •Rebal   │  │  │
│  │  │ •Dynamics│ │ •Enfusion│ │ •Alt data│ │ •ACA      │ │ •Model   │  │  │
│  │  │          │ │ •Addepar │ │          │ │           │ │  mktpl   │  │  │
│  │  │          │ │ •BlkDmnd │ │          │ │           │ │          │  │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     DATA SENSITIVITY LAYER                            │  │
│  │  • MNPI classification engine (per-field, per-archetype)             │  │
│  │  • PII masking / tokenization                                        │  │
│  │  • Information barrier enforcement                                    │  │
│  │  • Role-based data access (advisor, PM, trader, compliance, IR)      │  │
│  │  • Audit trail (who accessed what, when, why)                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

#### 1. Connector Strategy: Build vs. Buy

| Connector | Build | Buy/Partner | Notes |
|-----------|:-----:|:-----------:|-------|
| Salesforce FSC | Partner | MuleSoft / Salesforce APIs | Covers Tier 1-4. Salesforce is the CRM convergence point. |
| Bloomberg | Build | BLPAPI (licensed) | Covers Tier 1, 2, 5. Requires Bloomberg Terminal license per seat. |
| Aladdin | Partner | BlackRock Aladdin API | Covers Tier 2, 5. Aladdin is a walled garden — partnership required. |
| Orion / Envestnet | Build | REST APIs (well-documented) | Covers Tier 3, 4. API-first platforms — straightforward integration. |
| Custodian APIs | Build | Schwab/Fidelity/Pershing APIs | Covers Tier 3, 4. Each custodian has its own API — must support all 3. |
| FIX Protocol | Build | FIX engine (QuickFIX, proprietary) | Covers Tier 1, 2, 5. Standard protocol but complex implementation. |
| FactSet | Build | FactSet API (well-documented) | Covers Tier 2. Strong REST API with comprehensive data coverage. |
| Wealthbox / Redtail | Build | REST APIs | Covers Tier 4. Simple, well-documented APIs. |
| Backstop | Build | REST API | Covers Tier 5. Purpose-built for alternatives. |
| Plaid / MX | Build | Plaid Link / MX Connect | Covers Tier 3, 4. Standard aggregation APIs. |

#### 2. MNPI Enforcement Architecture

The agent must implement a per-archetype MNPI policy engine:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MNPI POLICY ENGINE                                        │
│                                                                             │
│  Input: (archetype, user_role, data_field, action)                         │
│  Output: ALLOW / BLOCK / REDACT / LOG_ONLY                                │
│                                                                             │
│  Rules by archetype:                                                        │
│                                                                             │
│  TIER 1 (IB):                                                               │
│    • IF user_role = "research" AND data = "deal_flow" → BLOCK              │
│    • IF user_role = "sales" AND data = "unpublished_research" → BLOCK      │
│    • IF data = "client_order_flow" AND action = "surface_to_other" → BLOCK │
│    • ALL interactions → LOG to surveillance system                          │
│                                                                             │
│  TIER 2 (AM):                                                               │
│    • IF data = "current_holdings" AND action = "external_share" → BLOCK    │
│    • IF data = "trading_intentions" AND action = "any" → REDACT amounts    │
│    • IF security IN restricted_list → BLOCK trade suggestions              │
│    • Pre-trade compliance check → MANDATORY before any order suggestion    │
│                                                                             │
│  TIER 3 (WM/BD):                                                            │
│    • IF data = "client_PII" → REDACT in LLM prompts                       │
│    • IF action = "recommendation" → LOG Reg BI documentation               │
│    • IF communication = "client_facing" → ARCHIVE + supervisory queue      │
│    • Financial plan data → NEVER send to external LLM                      │
│                                                                             │
│  TIER 4 (RIA):                                                               │
│    • IF data = "client_PII" → REDACT in LLM prompts                       │
│    • IF data = "financial_plan" → NEVER send to external LLM              │
│    • IF action = "recommendation" → LOG fiduciary documentation            │
│    • Client isolation → Advisor A cannot see Advisor B's clients           │
│                                                                             │
│  TIER 5 (HF):                                                               │
│    • IF data = "holdings" → BLOCK external, REDACT in LLM prompts         │
│    • IF data = "short_positions" → BLOCK ALL non-authorized access         │
│    • IF data = "trading_intentions" → BLOCK ALL non-trading-desk access    │
│    • IF data = "LP_data" → BLOCK non-IR access                            │
│    • Pod isolation → Pod A cannot see Pod B's positions (multi-strat)      │
│    • ALL interactions → LOG to compliance system                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 3. Audit Trail Requirements

Every archetype requires audit logging, but the depth and regulatory mandate varies:

| Requirement | Tier 1 | Tier 2 | Tier 3 | Tier 4 | Tier 5 |
|-------------|--------|--------|--------|--------|--------|
| Log every agent interaction | Mandatory (17a-4) | Required | Mandatory (FINRA) | Recommended | Required |
| Log every data access | Mandatory | Required | Required | Recommended | Required |
| WORM storage (immutable) | Mandatory | Recommended | Mandatory (17a-4) | Not required | Recommended |
| Supervisory review queue | Mandatory | Not required | Mandatory (FINRA 3110) | Not required | Recommended |
| Retention period | 6 years (17a-4) | 5 years (204-2) | 6 years (17a-4) | 5 years (204-2) | 5 years (204-2) |
| Regulatory examination access | SEC, FINRA, Fed | SEC | SEC, FINRA | SEC or State | SEC |

#### 4. Priority Connector Roadmap

Based on market size, integration complexity, and agent value-add:

```
PHASE 1 — Wealth Management (Tier 3 + 4): Highest volume, clearest use cases
  → Salesforce FSC connector (covers both tiers)
  → Orion / Envestnet Tamarac connector (portfolio data)
  → Custodian connectors (Schwab, Fidelity, Pershing)
  → eMoney / RightCapital connector (planning data)
  → Wealthbox / Redtail connector (RIA CRM)

PHASE 2 — Asset Management (Tier 2): High value, complex integration
  → Aladdin connector (requires BlackRock partnership)
  → Charles River IMS connector
  → FactSet connector (research data)
  → Bloomberg BLPAPI connector (market data)

PHASE 3 — Hedge Fund (Tier 5): High value, bespoke integration
  → SS&C Eze connector (PMS/OMS/EMS)
  → Enfusion connector (cloud-native alternative)
  → Backstop connector (IR/CRM)
  → Prime broker API connectors (Goldman, MS, JPM)

PHASE 4 — Investment Bank (Tier 1): Highest complexity, longest sales cycle
  → FIX protocol engine (order routing)
  → NICE Actimize integration (surveillance)
  → Proprietary system adapters (custom per bank)
  → SWIFT/ISO 20022 connector (settlement)
```

#### 5. What "Research → Client → Compliance → Execution" Means for the Agent Platform

Across all 5 archetypes, the agent must support a four-stage pipeline. The specific systems change, but the pattern is universal:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│           UNIVERSAL AGENT PIPELINE: RESEARCH → CLIENT → COMPLIANCE →       │
│                                     EXECUTION                               │
│                                                                             │
│  STAGE 1: RESEARCH (Read-Only)                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Agent ingests and synthesizes information from research sources.    │    │
│  │                                                                     │    │
│  │ T1: Bloomberg, Refinitiv, internal research platform               │    │
│  │ T2: FactSet, Bloomberg, MSCI, proprietary research                 │    │
│  │ T3: Morningstar, firm research, financial planning output          │    │
│  │ T4: Morningstar, model portfolio analytics, planning scenarios     │    │
│  │ T5: Bloomberg, alternative data, proprietary models                │    │
│  │                                                                     │    │
│  │ Agent action: SUMMARIZE, ANALYZE, COMPARE — never RECOMMEND yet    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                              │
│                              ▼                                              │
│  STAGE 2: CLIENT CONTEXT (Read-Only, Access-Controlled)                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Agent retrieves client/portfolio context to personalize insights.   │    │
│  │                                                                     │    │
│  │ T1: CRM → institutional client mandates, coverage relationships    │    │
│  │ T2: PMS → portfolio holdings, benchmarks, investment guidelines    │    │
│  │ T3: CRM → household, goals, risk profile, IPS, financial plan     │    │
│  │ T4: CRM → household, goals, risk profile, financial plan, held-away│   │
│  │ T5: PMS → fund holdings, LP commitments, fund mandate             │    │
│  │                                                                     │    │
│  │ Agent action: RETRIEVE, CONTEXTUALIZE — enforce data isolation     │    │
│  │ MNPI CHECK: Is this data authorized for this user + this context?  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                              │
│                              ▼                                              │
│  STAGE 3: COMPLIANCE GATE (Mandatory, Blocking)                            │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Agent validates any potential action against compliance rules.      │    │
│  │ This stage MUST complete before any execution suggestion.           │    │
│  │                                                                     │    │
│  │ T1: Information barrier check, restricted list, pre-trade rules    │    │
│  │ T2: Pre-trade compliance (OMS), restricted list, guideline check   │    │
│  │ T3: Reg BI documentation, supervisory review, communication log    │    │
│  │ T4: Fiduciary documentation, suitability check, communication log  │    │
│  │ T5: Restricted list, position limits, leverage check, personal     │    │
│  │     trading pre-clearance                                          │    │
│  │                                                                     │    │
│  │ Agent action: VALIDATE, DOCUMENT, BLOCK if non-compliant           │    │
│  │ OUTPUT: Compliance-approved recommendation with audit trail         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                              │
│                              ▼                                              │
│  STAGE 4: EXECUTION (Write, Human-Approved)                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ Agent facilitates execution — NEVER autonomous for trades.          │    │
│  │ Human approval is ALWAYS required before any order is placed.       │    │
│  │                                                                     │    │
│  │ T1: Generate FIX order for human approval → route to OMS/EMS       │    │
│  │ T2: Submit to OMS for human approval → route via FIX to brokers    │    │
│  │ T3: Prepare trade in custodian platform → advisor clicks "execute" │    │
│  │ T4: Queue rebalancing trades → advisor reviews and approves        │    │
│  │ T5: Submit to OMS for PM approval → route via FIX/DMA             │    │
│  │                                                                     │    │
│  │ Agent action: PREPARE, PRESENT, WAIT FOR HUMAN APPROVAL            │    │
│  │ Post-execution: LOG, RECONCILE, REPORT                             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Sources

Content was rephrased for compliance with licensing restrictions.

- [BlackRock Aladdin — Wikipedia](https://en.wikipedia.org/wiki/Aladdin_(BlackRock))
- [Limina: BlackRock Aladdin vs Charles River](https://www.limina.com/blackrock-aladdin-vs-charles-river)
- [Limina: EMS vs OMS vs PMS](https://www.limina.com/blog/ems-vs-oms-vs-pms)
- [MarketClutch: Enterprise Algorithmic Trading Platforms](https://marketclutch.com/industrial-alpha-the-comprehensive-guide-to-enterprise-algorithmic-trading-software-platforms/)
- [ION Group: OMS and FIX Protocol for Buy-Side](https://iongroup.com/blog/markets/the-benefits-of-oms-and-fix-protocol-for-buy-side-traders/)
- [Somco Software: FIX Engine Integration](https://somcosoftware.com/en/blog/fix-engine-integration-into-financial-systems-a-comprehensive-guide)
- [SS&C Advent: OMS vs EMS](https://www.advent.com/news-and-insights/blog/order-management-system-vs-execution-management-system/)
- [Finantrix: Investment OMS Buyer's Guide](https://www.finantrix.com/buyer-guides/investment-oms-asset-managers)
- [FIX Trading Community: Implementation Guide](https://www.fixtrading.org/implementation-guide/)
- [Investipal: Best Wealth Management Software for RIAs 2025](https://investipal.co/blog/best-wealth-management-software-rias-2025/)
- [Envestnet: 2025-2026 Strategic Platform Roadmap](https://newsroom.envestnet.com/2025-05-13-Envestnet-Unveils-2025-2026-Strategic-Platform-Roadmap-Powering-the-Future-of-Financial-Advice-Personalized-At-Scale)
- [The Wealth Advisor: Envestnet Operating System](https://thewealthadvisor.com/article/how-envestnet-building-operating-system-modern-wealth-management)
- [Surmount: Unbundling of Wealth Management](https://surmountwealth.com/blog/unbundling-wealth-management-modular-ria-tech-stack)
- [Atomic Insights: Optimal Tech Stack for RIAs](https://www.atomicinsights.io/blog/building-the-optimal-tech-stack-for-independent-rias-and-family-offices)
- [InvestmentNews: RIA Custodian Comparison](https://www.investmentnews.com/goria/custodian/ria-custodian-comparison-which-one-is-right-for-you/250320)
- [Kitces: Comparing Small RIA Custodians](https://www.kitces.com/blog/ria-custodian-list-best-platforms-small-startup-ria-altruist-axos-tradepmr-eas-pershing-schwab/)
- [NICE Actimize: SURVEIL-X Holistic Surveillance](https://www.niceactimize.com/financial-markets-compliance/holistic-surveillance)
- [NICE Actimize: Actimize Intelligence](https://www.niceactimize.com/financial-markets-compliance/actimize-intelligence/)
- [MCO: MNPI Compliance Risk](https://mco.mycomplianceoffice.com/blog/mnpi-compliance-risk-remains-high)
- [Alpha Maven: Hedge Fund Services](https://www.alpha-maven.com/learn/hedge-fund-services-what-they-are-and-how-they-work)
- [FundCount: Hedge Fund Portfolio Management Software](https://fundcount.com/best-hedge-fund-portfolio-management-software/)
- [Banq.ai: ISO 20022 Standard](https://banq.ai/standards/iso-20022)
- [Mambu: CBPR+ ISO 20022](https://mambu.com/en/insights/articles/cbpr-is-live-what-iso-20022-means-in-practice)
- [InnReg: Regulation Best Interest Explained](https://www.innreg.com/blog/regulation-best-interest-explained)
- [Global Relay: Regulation Best Interest](https://www.globalrelay.com/resources/the-compliance-hub/rules-and-regulations/regulation-best-interest/)
- [FINRA: Reg BI Rules](https://www.finra.org/rules-guidance/rulebooks/reg-bi-rules)
- [FastTrackr: Advisor Technology Ecosystem](https://fasttrackr.ai/blog/advisor-transition-technology-ecosystem-integrations)
- [Wealthmanagement.com: RIAs Using Multiple Custodians](https://www.wealthmanagement.com/ria-news/more-rias-are-using-multiple-custodians)
