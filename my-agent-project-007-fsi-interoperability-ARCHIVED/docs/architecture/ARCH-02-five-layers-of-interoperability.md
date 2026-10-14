# Project 007: The 5 Layers of FSI Interoperability

> Date: April 12, 2026
> Core insight: Retrofitting the trust and authority layer after the fact is nearly impossible. You must build bottom-up.
> This document reframes the entire 007 architecture around the 5 fundamental interoperability layers that any multi-agent, multi-enterprise FSI system must solve.

---

## The 5 Layers — And Why Order Matters

The layers stack. Each depends on the one below. You MUST build from the bottom up. Retrofitting a lower layer after building the upper ones is nearly impossible.

```
  Layer 5: SEMANTIC / INTENT     "What do you mean?"
       ^ depends on
  Layer 4: TRUST / AUTHORITY     "Are you allowed?"
       ^ depends on
  Layer 3: SCHEMA / DATA         "What is this data?"
       ^ depends on
  Layer 2: PROTOCOL / TRANSPORT  "How do we talk?"
       ^ depends on
  Layer 1: IDENTITY              "Who are you?"
```

---

## Layer 1: Identity — "Who Are You?"

Who is the agent? Who is the user behind the agent? Who is the firm behind the user?

In human FSI, identity is solved: FINRA CRD numbers for registered reps, SEC IARD for investment advisers, LEI for firms, SWIFT BIC for banks.

For AI agents, identity is UNSOLVED. No FINRA registration for AI agents. No standard for "this agent acts on behalf of this person at this firm with these authorities." No way to verify an agent's identity across firm boundaries. No revocation mechanism.

What exists today: A2A Agent Cards include identity metadata. OAuth 2.0 + OpenID Connect handle user identity. Verifiable Credentials (W3C) could encode agent authority. But no FSI-specific agent identity standard exists.

The problem: If Agent A at Firm X sends a trade order to Agent B at Custodian Y, how does Y verify that A is authorized? That the human behind A approved? That A's firm is a registered broker-dealer? That A's authority has not been revoked? Today this is done with phone calls, signed forms, and FINRA BrokerCheck. None of that works for autonomous agents at machine speed.

What 007 needs — an Agent Identity Document that travels with every request:

```
{
  agent_id: "oc-agent-007-prod-001",
  runtime: "openclaw",
  firm: {
    name: "Acme Wealth Management",
    lei: "5493001KJTIIGC8Y1R12",
    finra_crd: "123456",
    archetype: "tier3_wealth_management"
  },
  acting_on_behalf_of: {
    user_id: "sarah.chen@acmewm.com",
    role: "advisor",
    finra_crd: "7654321",
    licenses: ["Series 7", "Series 66"],
    authority_scope: ["client_query", "research", "trade_recommendation"],
    authority_excludes: ["trade_execution", "wire_transfer"]
  },
  issued_at: "2026-04-12T14:00:00Z",
  expires_at: "2026-04-12T22:00:00Z",
  revocation_endpoint: "https://acmewm.com/agent/revoke"
}
```

Every MCP call, every A2A message, every audit log entry includes this identity. If the identity is revoked, all in-flight requests fail.

---

## Layer 2: Protocol / Transport — "How Do We Talk?"

Status: Best solved layer. Multiple standards exist.

| Protocol | Purpose | Maturity |
|----------|---------|----------|
| MCP | Agent to Tool | 2,300+ servers, Claude/Cursor/VS Code/OpenClaw |
| A2A | Agent to Agent | 150+ orgs (AWS, Microsoft, Salesforce, SAP) |
| FIX | OMS to Broker | 35 years, universal for trading |
| SWIFT/ISO 20022 | Bank to Bank | Universal for payments/settlement |
| REST/gRPC | System to System | Universal for modern APIs |

What 007 does: No new protocols. Wrap existing ones in MCP.

The problem: Protocol is the EASIEST layer. The hard part is not "can these systems talk?" — it is "should they?" and "what do the messages mean?" Those are Layer 4 and Layer 5.

---

## Layer 3: Schema / Data — "What Is This Data?"

The same concept has different names in different systems.

"Client" = Salesforce Account+Contact, Orion Client+Household, Aladdin Portfolio+Account, Wealthbox Contact+Household, Backstop Company+Contact+Fund.

"Holdings" = Salesforce FinServ__FinancialHolding__c, Orion Position (with lots/tax lots/sleeves), Aladdin Position (with risk decomposition), Schwab Position (with cost basis methods), Eze Position (with P&L attribution).

"Trade" = FIX NewOrderSingle (150+ fields), Schwab API POST /orders (20 fields), Orion tRx rebalance trade (with model drift context), Aladdin Order (with compliance pre-check embedded).

Status: Partially solved. FIX standardized trading messages. ISO 20022 standardized payment messages. FDC3 standardized desktop context. But no standard for "client", "holdings", "research brief", "compliance check", or "risk assessment" across systems.

What 007 needs — a canonical FSI data model:

```
Client:
  id, name, type (individual/entity/household),
  risk_profile, investment_objectives, time_horizon,
  advisor_id, firm_id

Holding:
  client_id, account_id, security_id (CUSIP/ISIN/ticker),
  quantity, market_value, cost_basis, asset_class, sector,
  weight_in_portfolio, unrealized_pnl

Order:
  client_id, security_id, side (buy/sell), quantity,
  order_type, limit_price, time_in_force, account_id,
  compliance_status, approval_status, approved_by

ResearchBrief:
  security_id, analyst_id, rating, target_price, thesis,
  catalysts, risks, valuation, data_sources, generated_date

ComplianceCheck:
  security_id, check_type, result (pass/fail/warn),
  details, checked_by (agent_id), timestamp

AuditEntry:
  agent_id, user_id, action, target, timestamp,
  data_accessed, compliance_status, trace_id
```

Each MCP server translates between canonical types and system-specific schemas. The agent only sees canonical.

---

## Layer 4: Trust / Authority — "Are You Allowed?"

This is the layer you CANNOT retrofit.

Questions this layer answers:
- Can this agent access this data?
- Can this agent perform this action?
- Who authorized this agent to act on behalf of this user?
- What are the boundaries of this agent's authority?
- If Agent A delegates to Agent B, does B inherit A's authority?
- Who is liable when an agent makes a mistake?
- Can a compliance agent at Firm X audit an execution agent at Firm Y?

In human terms: this is the power of attorney, the trading authorization, the compliance mandate, the information barrier, the fiduciary duty — all encoded in machine-readable form.

Status: DOES NOT EXIST for agentic AI. OAuth 2.0 scopes are too coarse. Salesforce permission sets are CRM-specific. FINRA registration is human-specific. A2A Agent Cards advertise capability, not authority.

What 007 needs — an Authority Policy Engine:

```
Input:  (agent_identity, action, target, context)
Output: ALLOW / DENY / REQUIRE_APPROVAL / ESCALATE

Agent(advisor, tier3) + read_holdings(own_client)
  -> ALLOW

Agent(advisor, tier3) + read_holdings(other_advisor_client)
  -> DENY (data isolation)

Agent(advisor, tier3) + recommend_trade(client)
  -> ALLOW + REQUIRE(reg_bi_documentation)

Agent(advisor, tier3) + execute_trade(client)
  -> REQUIRE_APPROVAL(human, supervisor)

Agent(analyst, tier1) + read_deal_flow()
  -> DENY (Chinese wall)

Agent(pm, tier5) + read_holdings(other_pod)
  -> DENY (pod isolation)

Agent(pm, tier2) + submit_order(restricted_security)
  -> DENY (restricted list)

Agent(compliance, tier1) + audit_agent_actions(any_agent)
  -> ALLOW (compliance has cross-boundary audit authority)
```

Delegation: If Agent A delegates to Agent B, B's authority = intersection(A's authority, B's capability). B CANNOT exceed A's authority. B's actions are logged under both identities. A remains liable.

Cross-boundary: If Agent A at Firm X calls Agent B at Firm Y, B verifies A's identity document, checks A's authority scope, applies its OWN compliance rules (Y's rules, not X's), logs the cross-boundary access. Both firms have audit trail.

### Why you cannot retrofit this

If you build the data layer and protocol layer first, then try to add trust later, every existing integration becomes a security hole. Every MCP server built without authority checks needs rewriting. Every agent built assuming "if I can call it, I'm allowed to" has an implicit trust model that contradicts the explicit one.

This is exactly what happened with:

1. The Internet (1969-present): TCP/IP built without identity. 55 years of bolting on SSL, OAuth, SAML, zero-trust. Still have phishing and credential theft.

2. Email (1971-present): SMTP built without sender verification. 50+ years of spam, phishing, spoofing. SPF, DKIM, DMARC are all retrofits. Email is STILL the number one attack vector.

3. FSI Middleware (2000-present): MuleSoft, Kafka, ESBs built for data movement. Systems can exchange data but cannot verify authority. Every compliance check is a bolt-on.

The pattern: Build without trust -> bolt on trust later -> spend decades patching -> never fully close the gaps.

007 MUST NOT repeat this pattern.

---

## Layer 5: Semantic / Intent — "What Do You Mean?"

"Research NVIDIA" means different things to different people:

- Sell-side analyst: "Write a publishable research note"
- Buy-side PM: "Should I add to my position?"
- Wealth advisor: "Prep me for my client meeting about NVDA"
- Compliance officer: "Are we clean on NVDA?"
- Hedge fund PM: "What's the alpha signal?"

Same words. 5 different intents. 5 different data needs. 5 different compliance requirements. 5 different outputs.

Status: Nobody has solved this for multi-agent FSI. FDC3 tried for desktop apps. A2A has Agent Cards for capability discovery. But no FSI-specific intent taxonomy exists.

What 007 needs — an FSI Intent Taxonomy:

```
Research intents:
  research.summarize(security, scope, depth)
  research.compare(securities[], criteria[])
  research.analyze_filing(security, filing_type)
  research.generate_brief(security, template, audience)

Client intents:
  client.get_profile(client_id, fields[])
  client.get_holdings(client_id, as_of_date, include[])
  client.get_performance(client_id, period, benchmark)
  client.prep_meeting(client_id, meeting_date)

Compliance intents:
  compliance.check_restricted(security_id)
  compliance.check_suitability(client_id, recommendation)
  compliance.check_concentration(client_id, security_id)
  compliance.document_rationale(recommendation, evidence[])

Execution intents:
  execution.prepare_order(order_details)
  execution.request_approval(order_id, approver_role)
  execution.submit_order(order_id, approval_token)
  execution.check_status(order_id)
```

Each intent has: required authority level (Layer 4), required data fields (Layer 3 canonical schema), archetype-specific behavior (enterprise config), and audit requirements.

---

## How This Changes the 007 Architecture

The original 007 architecture:
```
Channel -> Orchestration -> Compliance Proxy -> MCP Servers -> Config
```

The problem: The "compliance proxy" was Layers 1 + 3 + 4 crammed into one component. Identity was a bearer token. Schema was hardcoded. Trust was bolted on. Semantics were implicit.

The revised architecture — trust-first:

The 5 interoperability layers are CROSS-CUTTING. They are not components — they are concerns that apply to every component.

```
Every MCP call passes through all 5 layers:

Agent wants to: get_holdings(client_id="C-12345")

L1 IDENTITY:  Verify agent identity document. Check expiry. Check revocation.
L2 PROTOCOL:  MCP tools/call -> MCP server (Orion)
L3 SCHEMA:    Canonical Holding -> Orion Position mapping. What to include?
L4 TRUST:     Check authority. Apply MNPI filtering. Enforce compliance. Log.
L5 SEMANTIC:  Intent is meeting_prep, not trade_analysis. Include performance,
              exclude cost basis.

Result: Agent receives exactly the data it needs, filtered for its
authority level, in canonical format, with full audit trail.
```

006 approach: Build MCP servers -> bolt on compliance.
007 approach: Design identity + trust -> then build MCP servers that NATIVELY enforce trust at every call.

The MCP server does not just wrap an API. It verifies identity, checks authority, translates schema, filters by trust policy, and logs the audit trail. Trust is not a layer on top. It is woven into every adapter.

---

## Where 006 Sits in This Framework

006 today:
- Layer 1 (Identity): Bearer token. No agent identity document. No revocation.
- Layer 2 (Protocol): MCP. Working. 3 servers.
- Layer 3 (Schema): Hardcoded Salesforce field names. No canonical model.
- Layer 4 (Trust): MNPI filter (partial). Compliance screening (basic). No authority engine.
- Layer 5 (Semantic): Implicit in pipeline stages. No intent taxonomy.

006 built Layer 2 first, then bolted on partial Layer 4. This is the same pattern that failed for the internet, email, and FSI middleware.

007 must build Layer 1 and Layer 4 FIRST, then build everything else on top.

---

## The Build Order for 007

```
PHASE 0: Design (before any code)
  Define Agent Identity Document schema
  Define Authority Policy Engine rules format
  Define Canonical FSI Data Model
  Define FSI Intent Taxonomy
  Design how these 4 artifacts flow through every MCP call

PHASE 1: Foundation (Layer 1 + Layer 4)
  Build Agent Identity issuance and verification
  Build Authority Policy Engine (YAML-driven)
  Build the trust-aware MCP wrapper (every MCP server
    inherits identity verification + authority checking)
  Prove: an unauthorized call is DENIED before it reaches
    the underlying system

PHASE 2: Schema + Adapters (Layer 3 + Layer 2)
  Define canonical types (Client, Holding, Order, etc.)
  Build schema translators for first 3 systems
    (Salesforce FSC, Orion, SEC EDGAR)
  Build trust-aware MCP servers for those 3 systems
  Prove: same canonical query, different systems,
    correct translation, trust enforced

PHASE 3: Semantics + Pipeline (Layer 5)
  Define FSI Intent Taxonomy
  Build intent router (natural language -> structured intents)
  Connect intents to authority requirements
  Build configurable pipeline engine
  Prove: "prep me for my Henderson meeting" resolves to
    right intents, checks right authorities, pulls right data

PHASE 4: Scale (more adapters, more archetypes)
  Add MCP servers for Tier 3/4 systems
  Add archetype profiles for Tier 2, 5, 1
  Each new adapter inherits trust natively
  No bolt-on compliance needed
```

---

## The Honest Assessment

This is harder than the original 007 architecture. Significantly harder. Designing the identity document, authority engine, canonical schema, and intent taxonomy BEFORE writing code requires deep FSI domain expertise and regulatory knowledge.

But it is the only way to build something that does not become a security liability. Every FSI integration project that skipped the trust layer has spent years retrofitting it. 007 has the opportunity to get it right from the start because it is greenfield.

The compliance proxy from the original architecture was the right instinct. But it was one component trying to do the work of 3 layers (identity, trust, schema). Decomposing it into proper interoperability layers makes the architecture more rigorous, more extensible, and more defensible to a regulator.

Layer 4 (Trust / Authority) is the moat. It is the thing that does not exist anywhere in the world for agentic AI in FSI. Build it right and everything else is plumbing. Build it wrong — or skip it — and nothing else matters.
