# What 007 Actually Does — Plain English

> For investors, partners, and anyone who doesn't want to read 28 architecture documents.

---

## The Problem

A wealth management advisor uses 20-35 disconnected systems every day. Salesforce for client data. Orion for portfolio holdings. eMoney for financial plans. Schwab for custodian positions. Bloomberg for market data. None of them talk to each other.

To prep for one client meeting, the advisor opens 5 browser tabs, copies data from each system, pastes it into a document, and spends 40 minutes assembling a brief. 60-70% of their week is admin, not advising.

Now add AI agents. The advisor wants to say "Prep me for my Henderson meeting tomorrow" and get a complete brief in 60 seconds. The AI needs to pull data from 5 systems simultaneously. But who decides what the AI is allowed to see? What if Henderson's SSN leaks into the AI's response? What if the AI recommends a trade that violates compliance rules? What if there's no audit trail of what the AI did?

That's the problem 007 solves.

---

## What 007 Is

007 is the trust layer between every system a wealth management firm uses — so AI agents can act on financial data without compliance risk.

It's not a CRM (Salesforce does that). It's not a portfolio system (Orion does that). It's not a trading platform (Schwab does that). It's the layer that sits between all of them and enforces: who can see what, what's compliant, and what gets logged.

---

## The Components

### Deterministic OPA

Every compliance decision — can this person see this data? can this agent submit this order? — is made by a rule engine called OPA, written in a language called Rego. Not by the AI. Not by a language model that might hallucinate.

A rule that says "deny if the advisor isn't assigned to this client" will deny 100% of the time. Deterministic means same input, same output, every time. An auditor can read the rule and verify it's correct. You can't do that with an LLM.

This matters because Delve, a $300M compliance startup, was dropped by Y Combinator in April 2026 for allegedly generating fake compliance evidence using LLMs. The market learned that LLM-based compliance doesn't work. Deterministic rules do.

### MNPI Filtering

MNPI stands for Material Non-Public Information. Things like a client's Social Security Number, date of birth, pending trades, undisclosed holdings.

Before any data reaches the AI model or the advisor's screen, OPA strips the fields they're not allowed to see. A Tier 4 RIA advisor sees holdings but not SSN. A Tier 5 hedge fund portfolio manager in Pod A can't see Pod B's positions.

This happens at the field level, not the record level. It's not "you can't see this client" — it's "you can see the client but not their SSN."

### 18 Canonical Types

Every vendor has their own data format. Schwab calls it "costBasis." Orion calls it "costBasisMethod." Fidelity calls it something else entirely.

007 defines 18 standard data types (Client, Holding, Household, TaxLot, Order, Transaction, Balance, etc.) that all vendor data gets translated into. The rest of the platform speaks one language regardless of which vendor the data came from.

The Household type is the hardest. Salesforce thinks a household is a relationship grouping. Orion thinks it's a portfolio grouping. Schwab thinks it's a custodial grouping. 007's Household is a container that holds all three definitions and flags when they disagree.

### 20 Adapters

Each vendor system has its own adapter that speaks the vendor's language and translates it into MCP (Model Context Protocol):

- REST adapters for Salesforce, Orion, eMoney, Schwab, Fidelity, Pershing, Wealthbox, Redtail, Envestnet, ComplySci, SEC EDGAR
- Bloomberg adapter using their proprietary binary protocol (BLPAPI)
- SS&C Eze adapter using gRPC (hedge fund order management)
- SFTP adapters for Schwab and Fidelity daily batch files
- FactSet passthrough (FactSet already has their own MCP server — validates the whole thesis)

20 adapters. 17+ systems. 5 protocols. Each runs in its own container. If Bloomberg goes down, Salesforce keeps working.

### 3-Tier WORM Audit

Every action is logged to three places simultaneously:

1. Langfuse — operational debugging, 90-day retention
2. S3 Object Lock (Compliance mode) — regulatory records, 6-year retention, physically cannot be deleted or modified. WORM = Write Once Read Many.
3. Salesforce CRM — so advisors and compliance officers see the audit trail in their existing tools

If any tier fails to write, the entire request is blocked. No unaudited actions. Ever. Every entry includes a SHA-256 integrity hash proving the record hasn't been tampered with. SEC Rule 17a-4 requires 6 years of immutable retention. This is how 007 meets it.

### 5 Archetypes

Not every firm is the same:

- Tier 1 Investment Bank: Chinese walls between divisions. On-premise. Self-hosted LLM.
- Tier 2 Asset Manager: Hybrid deployment. Trust layer on-premise, compute in cloud.
- Tier 3 Broker-Dealer: FINRA 2210 principal review. Smarsh archiving mandatory.
- Tier 4 Independent RIA: Cloud SaaS. Fiduciary duty. Simplest compliance profile.
- Tier 5 Hedge Fund: Pod isolation between trading strategies. Position-level MNPI.

Same platform, 5 different compliance regimes. Configured, not coded.

### 5 Jurisdictions

- United States: SEC, FINRA, state regulations
- European Union: GDPR, MiFID II, DORA, AI Act
- United Kingdom: FCA Consumer Duty, UK GDPR
- Singapore: MAS TRM, FEAT, AIRG
- Hong Kong: SFC suitability, PDPO privacy, AMLO anti-money laundering

Each jurisdiction has its own OPA rules that overlay on top of the base rules. Cross-border data transfers get checked against the destination jurisdiction's requirements.

### Principal Review

FINRA Rule 2210 says a registered principal (not the advisor) must review all retail communications at a broker-dealer before they're sent to clients.

When the AI generates a recommendation at a BD, it goes to a review queue. The principal sees the output, the compliance context (which OPA rule allowed it, what MNPI was stripped), and clicks Approve or Reject. Rejection requires a reason (archived to WORM). Approval generates a cryptographic proof of who approved what and when. This is a legal requirement, not a feature.

### HITL Gates

Human-In-The-Loop. Certain actions cannot happen without a human clicking a button: order submission, wire transfers, account closures. The AI prepares them. A human must approve. The approval generates a cryptographic proof. If no human approves within 24 hours, the action auto-cancels. Zero autonomous trades.

### Behind a Single MCP Gateway

All of the above happens inside one choke point: the M6 gateway. Every request from every channel (Slack, Teams, WhatsApp, Web) passes through M6:

1. M1: Who are you? (identity verification)
2. M2: Are you allowed? (OPA authority check)
3. M4: What can you see? (MNPI field filtering)
4. Route to vendor adapter
5. M7: Translate vendor response to canonical type
6. M4 again: Strip MNPI from the response
7. Gap 6: Scan for MNPI leakage (regex + NER + classifier)
8. M10: Log to all 3 audit tiers

One gateway. One trust pipeline. One place to enforce everything.

---

## The Metric: TAIS

Trust-Adjusted Interoperability Score = Systems x Compliance% x Trust x Audit

```
PLATFORM       SYSTEMS  COMPLIANCE  TRUST   AUDIT   TAIS
──────────────────────────────────────────────────────────
007            20       85%         1.0     1.0     17.0
Arcade.dev     10       30%         0.5     0.33     0.5
BridgeFT       900+     10%         0.0     0.33     0.0
Envestnet      5        20%         0.0     0.33     0.0
Spektr         1        40%         0.5     0.33     0.07
```

007 is 34x the nearest competitor. Not because it's incrementally better at one thing — because nobody else combines all four dimensions. BridgeFT connects 900+ feeds but has zero trust enforcement. Arcade has auth but no FSI compliance. Spektr has compliance but only for KYC. The gap isn't 2x or 5x. It's 34x. That's the moat.

---

*Project 007 FSI Interoperability Platform*
