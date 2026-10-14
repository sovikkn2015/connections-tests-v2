# Project 007: What We Built — Plain English

> Date: April 16, 2026
> Audience: Non-technical stakeholders, investors, design partners, new team members
> Purpose: Explain what 007 is, what's been built, who uses it, and why it matters

---

## The Problem

A financial advisor at a wealth management firm uses 20-35 different software systems every day. Salesforce for client info. Orion for portfolio data. Schwab for account balances. eMoney for financial plans. SEC EDGAR for filings. None of these talk to each other.

When an advisor needs to prep for a client meeting, they open 5 tabs, copy data from each system, paste it into a document, and spend 40 minutes doing what should take 60 seconds. Multiply that across 300,000+ advisors in the US. That's the problem.

---

## What 007 Does

An advisor types on Slack: "Prep me for my meeting with Henderson tomorrow."

007 pulls Henderson's profile from Salesforce, portfolio from Orion, financial plan from eMoney, account balances from Schwab, and relevant SEC filings — all in one shot. It filters out sensitive data the advisor shouldn't see, checks that the advisor is authorized to access Henderson's records, logs everything for regulators, and delivers a complete meeting brief in under 60 seconds.

The hard part isn't the AI. It's the trust. Who's allowed to see what? Which data is too sensitive for the AI to touch? Is every access logged immutably for 6 years? That's what we built.

---

## Who Uses It

| User | What They Get |
|------|--------------|
| Financial advisors (RIAs, broker-dealers) | Meeting prep, portfolio reviews, research briefs — in seconds instead of hours |
| Compliance officers | Every data access logged, every AI decision auditable, MNPI never leaks |
| Firm principals (broker-dealers) | Review queue for agent communications before they reach clients (FINRA requirement) |
| Firm IT/operations | One platform connecting all their disconnected systems |

---

## What We Actually Built (So Far)

Think of it as 8 layers, bottom to top.

### Layer 1 — The Data Dictionary (18 Canonical Types)

We defined a universal language for financial data. A "Client" looks the same whether it comes from Salesforce, Orion, or Schwab. 18 data types covering clients, holdings, transactions, balances, tax lots, goals, plans, orders, compliance checks, and more. Every field documented. Every vendor difference mapped.

### Layer 2 — The Config System (Enterprise Config)

Each firm gets a configuration file that says: "We're a broker-dealer, we use Schwab and Orion, we need Reg BI compliance, principal review is required." The system reads this and configures itself. A small RIA gets different rules than a large broker-dealer. Five firm archetypes are supported:

- Tier 1: Investment banks (Chinese walls, on-premise)
- Tier 2: Asset managers (portfolio-level isolation)
- Tier 3: Broker-dealers (Reg BI, FINRA 2210 principal review)
- Tier 4: Independent RIAs (fiduciary duty, advisor-level access)
- Tier 5: Hedge funds (pod isolation, position MNPI)

### Layer 3 — The ID Card System (Agent Identity)

Every person and every AI agent gets a digital ID card (JWT token) with their name, firm, role, what they're allowed to do, and what they're not. The advisor's ID says "can read client data, can't submit trades." The research AI's ID says "can read SEC filings and market data, can't access client PII."

### Layer 4 — The Rules Engine (OPA Policy)

A deterministic rules engine (not AI — actual logic rules) that answers two questions on every request:

- "Is this person/agent allowed to do this?" (authority check)
- "Which fields should be hidden from them?" (MNPI filtering)

A Tier 4 RIA advisor sees their own clients' data with SSN/DOB stripped. A Tier 5 hedge fund PM sees only their own pod's positions. A compliance officer sees everything. These rules are written in a language called Rego — auditable, testable, never probabilistic.

### Layer 5 — The Gateway (Trust-Aware MCP Gateway)

The central checkpoint. Every single data request passes through here. It:

1. Checks your ID card
2. Checks if you're allowed
3. Strips sensitive fields from the request
4. Forwards the request to the right vendor system
5. Strips sensitive fields from the response
6. Scans for data leakage (SSN patterns, account numbers, MNPI keywords)
7. Logs everything to the audit trail

If any step fails, the request is denied. No exceptions. No "let it through and log it." Denied.

The gateway also includes resilience patterns: circuit breakers (if a vendor system is down, stop hammering it), rate limiting (don't exceed vendor API limits), retry with backoff (try again on transient failures), and bulkhead isolation (a slow vendor can't starve other vendors of resources).

### Layer 6 — The Audit Trail (3-Tier Audit Logger)

Every data access is written to three places simultaneously:

1. **Langfuse** — for operational monitoring (what's slow? what's failing?)
2. **S3 Object Lock** — immutable storage that can't be deleted for 6 years (SEC Rule 17a-4)
3. **Salesforce CRM** — so compliance officers can see the audit trail in their normal tools

If any of the three writes fails, the entire request fails. A regulator can ask "show me every time anyone accessed Henderson's data in the last 3 years" and get a complete, tamper-proof answer.

Every audit entry includes a SHA-256 integrity hash and a provenance chain showing exactly which modules processed the data, in what order, with cryptographic proof at each stage.

### Layer 7 — The Translators (5 Vendor Translators)

Each vendor system speaks its own language. Schwab calls it "Position," Orion calls it "Holding," Salesforce calls it "FinancialHolding." The translators convert vendor data into our universal format and back. We built translators for:

- **Salesforce FSC** — Client, Holding, Household (relationship grouping), Goal
- **Orion** — Client, Holding (with accrued interest flag), Household (portfolio management grouping), Transaction, Performance
- **Schwab** — Client, Holding, TaxLot (cost basis = specific lot), Transaction, Balance (API vs daily file), Household (custodial grouping)
- **Fidelity** — Client, Holding, TaxLot (cost basis = average cost for mutual funds, specific lot for equities), Balance, Transaction
- **eMoney** — PlanSummary (probability of success, Monte Carlo), Goal

The Fidelity translator is particularly important — Fidelity defaults to "average cost" for mutual fund tax lots but "specific lot" for equities. Getting this wrong means wrong tax reporting. Regulatory violation.

### Layer 8 — The Vendor Connectors (5 MCP Adapters)

The actual connections to external systems:

- **SEC EDGAR** — public filings search and retrieval (free, live, 10 requests/second)
- **Alpha Vantage** — stock quotes, daily prices, company fundamentals (live, API key)
- **News API** — news article search and headlines for research (live, API key)
- **Salesforce FSC** — CRM queries, record read/write (stub, pending vendor API approval)
- **Orion** — portfolio data, positions, transactions, performance (stub, pending vendor API approval)

Each connector implements the same interface: "what tools do you have?" and "run this tool." The gateway doesn't care what's behind the connector — it could be a REST API, a Bloomberg terminal feed, or a file on an SFTP server.

---

## The Wedge Product

The trust layer (Layers 3-6) is packaged as a standalone product: **"Compliance Proxy for MCP."**

Any firm deploying AI agents that access financial data can put this between their AI and their data. It checks identity, authority, MNPI, and logs everything. Works with any MCP-compatible system — including FactSet's production MCP server (launched December 2025, validating our architecture thesis).

**Price:** $500-2K/month for an RIA, $5-15K/month for a broker-dealer.

**Ships:** End of Phase 1 (Week 14-18). First revenue before the full platform is ready.

---

## What's Not Built Yet

| Module | What It Does | When |
|--------|-------------|------|
| Intent Router (M9) | Understands "prep me for Henderson" and figures out which data to fetch | Phase 2 (next) |
| Research Pipeline (M8) | 23-stage AI research pipeline with human approval gates | Phase 2 |
| Agent Runtime (M12) | Supervisor AI that routes requests to specialist AI agents | Phase 2 |
| Compliance Gaps 1-7 | Reg BI documentation, BSA/AML monitoring, ERISA account rules, cross-border | Phase 2-3 |
| Smarsh Archiving | Communication archiving for broker-dealers ($11B+ in fines for failures) | Phase 3 |
| Execution Specialist | Trade order lifecycle with mandatory human approval | Phase 3 |
| Bloomberg, FactSet, FIX | Institutional market data and trading protocols | Phase 4 |
| Tier 1 banks, global | Chinese walls, MiFID II, GDPR, on-premise deployment | Phase 5 (deferred) |

---

## The Numbers

| Metric | Value |
|--------|-------|
| Production code | ~15,000 lines Python + 934 lines Rego |
| Canonical data types | 18 (with 78 Pydantic models) |
| Vendor translators | 5 (SF FSC, Orion, Schwab, Fidelity, eMoney) |
| MCP adapters | 5 (3 live + 2 pending vendor approval) |
| Tests passing | ~250 |
| Schema decisions documented | 37 |
| Architecture documents | 28 |
| Committee review cycles | 4 (scores: 5.1 → 7.5 → 8.2 → 8.3) |
| Specialist build agents | 6 (trust, schema, gateway, pipeline, adapter, compliance) |
| Hardcoded credentials | 0 |
| Cross-module imports | 0 (every module talks via REST only) |

---

## Why It Matters

### The Moat

The moat isn't the code — anyone can set up OPA and FastAPI. The moat is the knowledge encoded in the configuration:

- Which fields are MNPI for which firm archetype
- How Schwab's cost basis method differs from Fidelity's (and why it matters for taxes)
- What FINRA 2210 requires for broker-dealer communications
- How to map 3 different "household" concepts across 3 vendors into one container model that preserves all three semantics
- 2,100+ lines of compliance rules across 5 archetypes, 7 regulatory regimes, and 5 jurisdictions

That knowledge took 28 architecture documents, 5 committee reviews, and deep research into 17 vendor systems to produce. A competitor starting today is 6-12 months behind just on vendor API approvals alone (Fidelity takes 6-12 months).

### The Market

- 300,000+ financial advisors in the US
- Average firm runs 20-35 disconnected platforms
- 40% of advisor time wasted on manual data entry and reconciliation
- $11B+ in SEC/FINRA fines (2024-2025) for communication archiving failures
- No existing platform solves trust + intelligence + interoperability across enterprise boundaries

### The Timeline

- **Month 4:** Wedge product ships (Compliance Proxy for MCP). First revenue.
- **Month 8:** RIA lighthouse deploys (3-5 firms in draft mode). First real users.
- **Month 11:** Paying customers. $500K-4.5M ARR target.
- **Month 14-18:** Break-even.

### The Budget

- Phase 0-1: $260-410K (trust layer + wedge product)
- Phase 2: $520-780K (intelligence layer + RIA lighthouse)
- Phase 3: $520-760K (production hardening + BD onboarding)
- Phase 4: $700-1,050K (Tier 2/5 expansion)
- Phase 5: Deferred until revenue funds it
- **Total: $2.0-3.0M** (15% contingency: $2.3-3.45M)

---

## The Bottom Line

007 solves the hardest unsolved problem in financial services: making 20-35 disconnected systems work together with trust. Every data access is identity-verified, authority-checked, MNPI-filtered, and immutably logged. The compliance layer is deterministic (not AI guessing) — auditable, testable, and fail-closed.

The wedge product ships in weeks. The moat is real. The window is closing as vendors like FactSet ship their own MCP servers. 007 positions as the compliance layer between ALL of them.

---

*007-what-we-built-plain-english.md*
*Project 007 FSI Interoperability Platform*
