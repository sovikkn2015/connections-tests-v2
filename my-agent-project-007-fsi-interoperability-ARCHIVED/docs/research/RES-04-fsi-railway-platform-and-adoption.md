# Project 007: The FSI Railway — Platforms, Personas, Journeys, and Adoption

> Date: April 12, 2026
> Analogy: An interoperable multi-agent system for financial services is a railway system connecting passengers (personas) to destinations (enterprise systems) via platforms (channels), trains (agents), tracks (MCP protocol), signals (trust engine), and tickets (agent identity).
> Purpose: Make the architecture as real as possible to existing financial systems and explain why institutions will adopt it.

---

## The Railway Metaphor

```
  Passengers = FSI Personas (analysts, advisors, PMs, compliance)
  Platforms  = Channels (Slack, WhatsApp, Web, Bloomberg, Symphony)
  Trains     = Agents (specialized, route-specific)
  Tracks     = MCP Protocol (standardized gauge)
  Signals    = Trust/Authority Engine (safety enforcement)
  Switches   = Intent Router (directs to correct line)
  Stations   = Enterprise Systems (CRM, OMS, PMS, compliance)
  Tickets    = Agent Identity Documents (who you are, where you can go)
  Timetable  = Pipeline Config (what runs when, in what order)
```

---

## Platforms — Where Passengers Board

```
  [SLACK]     [WHATSAPP]   [WEB]      [BLOOMBERG]  [SYMPHONY]
  Platform    Platform     Platform   Terminal     Platform
                                     Platform
  Analysts    Advisors     Everyone   Traders      Inst.
  Advisors    in field                Analysts     Sales
       |           |           |           |           |
       +───────────+───────────+─────+─────+───────────+
                                     |
                               TICKET GATE
                          (Agent Identity Check)
                                     |
                               SWITCH YARD
                            (Intent Router)
                                     |
              +──────────+───────+───+───+───────+──────────+
              v          v       v       v       v          v
           LINE 1     LINE 2  LINE 3  LINE 4  LINE 5
```

---

## 5 Railway Lines

All lines run on the same track gauge (MCP protocol). All lines pass through the same signal system (trust engine).

### Line 1: Research Express

Queries: "Deep dive on NVIDIA ahead of earnings" / "Analyze NVIDIA's latest 10-K" / "Compare NVDA vs AMD vs INTC"

Passengers: Analysts, PMs, Advisors

Route: Start -> SEC EDGAR Stn -> Market Data Stn -> News Stn -> LLM Synth. Stn -> Brief Assembly Stn -> Publish to CRM Stn

Signals: authority check, restricted list, MNPI strip before LLM, audit every stop

Stations: [SEC EDGAR] [Bloomberg/FactSet] [Tavily/DJ] [Bedrock LLM] [Salesforce CRM] [Langfuse]

### Line 2: Client Service Local

Queries: "Prep me for my meeting with Henderson tomorrow" / "Henderson's portfolio performance?" / "Henderson's plan gaps?"

Passengers: Wealth Advisors, RIAs, Relationship Managers

Route: Start -> CRM Stn -> Portfolio Stn -> Planning Stn -> LLM Synth. Stn -> Deliver to Channel

Signals: data isolation (own client?), PII strip, Reg BI / fiduciary documentation, archive if client-facing

Stations: [Salesforce FSC] [Orion/Envestnet/Addepar] [eMoney/RightCapital] [Bedrock LLM] [Smarsh]

### Line 3: Compliance Inspector

Queries: "Is NVDA on our restricted list?" / "Pre-trade compliance on this order" / "MNPI violations last 30 days?"

Passengers: Compliance Officers, Risk Managers, CCOs

Route: Start -> Restricted List Stn -> MNPI Tracking Stn -> Audit Log Stn -> Report Stn

Signals: ELEVATED AUTHORITY — cross-boundary audit access, can see all agents, cannot execute trades

Stations: [IR_Restricted_List__c] [IR_MNPI_Tracking__c] [IR_Audit_Log__c] [NICE Actimize] [Smarsh] [Langfuse]

### Line 4: Execution Express

Queries: "Trim Henderson's NVDA by 30%" / "Rebalance Client D to target" / "Wire $250K from Henderson to Chase"

Passengers: Advisors, PMs, Traders (with HITL approval)

Route: Start -> Compliance Pre-check Stn -> HITL Gate (STOP!) -> Execute Stn -> Confirm Stn -> Update CRM Stn

MANDATORY STOP: HITL GATE. Train STOPS. Human must pull the lever. No autonomous execution. Ever. Dual authorization for wire >$100K, trade >$500K.

Signals: MAXIMUM SECURITY — pre-trade compliance, concentration check, authority check, HITL approval, dual auth, post-trade audit

Stations: [Compliance Engine] [HITL Gate] [OMS/FIX or Custodian API or MuleSoft or Rebalancing Tool] [Salesforce CRM]

### Line 5: Onboarding and KYC Local

Queries: "Run KYC on prospect Jane Smith" / "Open managed account for Jane Smith" / "Henderson transfer status?"

Passengers: Operations, Client Service, Compliance

Route: Start -> KYC Screen Stn -> Sanction Check Stn -> Risk Score Stn -> HITL Gate (STOP!) -> Account Open Stn

Signals: AML/BSA compliance, risk tier determines auto-approve vs human review, low risk auto-approve with audit

Stations: [KYC Provider] [Sanctions DB] [Adverse Media Search] [Core Banking / Custodian] [Salesforce CRM]

---

## The Station Map — Enterprise Systems as Destinations

Each station is an MCP server wrapping an enterprise system. Trains stop at stations to pick up or drop off data. The signal system controls access at every station.

### Research Stations

| Station | Provides | Trains |
|---------|----------|--------|
| SEC EDGAR | Filings: 10-K, 10-Q, 8-K, insider | Any |
| Bloomberg B-PIPE | Quotes, history, consensus, options | T1, T2, T5 (license) |
| FactSet | Analytics, factors, ESG, risk | T2 (license) |
| News (Tavily/DJ/Reuters) | Headlines, articles, sentiment | Any |
| Morningstar Direct | Fund research, ratings | T3, T4 |

### Client Data Stations

| Station | Provides | Trains |
|---------|----------|--------|
| Salesforce FSC | Client, account, household, audit | T1-T4 (dominant) |
| Wealthbox / Redtail | Client, contact, household | T3, T4 (RIA) |
| Backstop | Company, contact, fund, LP data | T5 (hedge fund) |
| Orion / Envestnet Tamarac | Holdings, performance, drift | T3, T4 (wealth) |
| Aladdin / Charles River | Holdings, risk, compliance, orders | T1, T2, T5 (institutional) |
| SS&C Eze / Enfusion | Holdings, P&L, risk, orders | T5 (hedge fund) |
| eMoney / RightCapital | Goals, plan, Monte Carlo, tax | T3, T4 (planning) |

### Compliance Stations

| Station | Provides | Trains |
|---------|----------|--------|
| NICE Actimize | Trade surveillance, market abuse | T1, T3 (large BD) |
| Smarsh / Global Relay | Comms archiving, supervisory review | T1, T3 (BD) |
| RIA in a Box / SmartRIA | Policy calendar, ADV, compliance | T4 (RIA) |
| ComplySci / StarCompliance | Personal trading, pre-clearance | T5 (hedge fund) |
| Internal (Salesforce) | Restricted list, MNPI, suitability | All tiers |

### Execution Stations

| Station | Provides | Trains |
|---------|----------|--------|
| FIX Bridge | OMS/EMS routing, algo, DMA | T1, T2, T5 |
| Custodian APIs (Schwab/Fidelity/Pershing) | Trade submission, account data | T3, T4 |
| MuleSoft | Enterprise actions (OMS, wire, KYC) | Enterprise |
| Rebalancing (iRebal/tRx/Tamarac) | Model rebalancing, tax-loss harvest | T3, T4 |
| SWIFT/ISO 20022 | Wire transfers, payment settlement | T1 (banks) |

ALL EXECUTION STATIONS HAVE HITL GATES. No train passes without human approval.

---

## The Signal System — Trust Engine

```
  GREEN:   PROCEED — authorized, clean, compliant
  YELLOW:  CAUTION — authorized but flagged (concentration, blackout)
  RED:     STOP — not authorized, restricted list, Chinese wall, pod breach
  HITL:    STOP — human must pull lever (trades, wires, account opens)
```

Same junction, different signal by archetype:

```
  Junction: "Access client holdings"

  T1 bank:    RED unless same side of Chinese wall
  T2 AM:      YELLOW — check restricted list first
  T3 wealth:  GREEN if own client, RED if not
  T4 RIA:     GREEN if own client (fiduciary)
  T5 HF:      RED unless same pod (multi-strategy)
```

---

## The Ticket System — Agent Identity

### Ticket: Sarah Chen, Wealth Advisor, Tier 3

```
  Firm:      Acme Wealth Management (LEI: 5493001KJT...)
  Role:      Advisor
  Licenses:  Series 7, Series 66

  CAN RIDE:  Line 1 (Research), Line 2 (Client Service),
             Line 3 (own clients), Line 4 (with HITL), Line 5
  CAN VISIT: SF FSC, Orion, eMoney (own clients), SEC EDGAR,
             News, Market Data (unrestricted), Schwab (HITL for trades)
  CANNOT:    Other advisors' clients, trades without HITL,
             wires without dual auth, surveillance data
```

### Ticket: Mike Torres, Compliance Officer, Tier 3

```
  Role:      Compliance Officer

  CAN RIDE:  Line 3 (ALL clients, ALL agents), Line 1 (read-only)
  CAN VISIT: IR_Audit_Log__c (all), IR_Restricted_List__c (read+write),
             IR_MNPI_Tracking__c (read+write), Smarsh (all), NICE Actimize
  CANNOT:    Execute trades, access financial plans, modify client data
```

### Ticket: James Park, Hedge Fund PM, Tier 5

```
  Role:      Portfolio Manager
  Pod:       Long/Short Equity — Pod Alpha

  CAN RIDE:  Line 1 (Research), Line 4 (with HITL)
  CAN VISIT: Bloomberg, FactSet (unrestricted), SS&C Eze (Pod Alpha ONLY),
             FIX Bridge (Pod Alpha, with HITL)
  CANNOT:    Pod Beta/Gamma positions, firm-wide aggregates,
             LP/investor data, restricted securities
```


---

## 6 Journeys — Real Queries Through the Railway

### Journey 1: Wealth Advisor, WhatsApp, 6am

Sarah Chen (Advisor, Tier 3, Acme WM) on WhatsApp: "Prep me for my meeting with Henderson tomorrow"

```
  Platform:  WhatsApp
  Line:      Line 2 (Client Service Local)
  Ticket:    advisor, own-clients-only, tier3

  o-- WhatsApp Platform
  o-- Ticket Gate: Sarah Chen, Advisor, Acme WM -- GREEN
  o-- Switch Yard: intent = client.prep_meeting
  o-- Signal: Is Henderson Sarah's client? -- GREEN
  |
  o-- Station: Salesforce FSC
  |   Pick up: client profile, household, risk profile
  |   Signal: strip SSN, DOB -- filtered
  |
  o-- Station: Orion Portfolio
  |   Pick up: holdings, performance since last meeting
  |   Signal: tier3 = full holdings (retail, not MNPI)
  |
  o-- Station: eMoney Planning
  |   Pick up: plan summary, goal progress, gaps
  |   Signal: plan data stays server-side, only summary to LLM
  |
  o-- Station: Bedrock LLM
  |   Synthesize meeting prep brief
  |   Signal: Bedrock Guardrails active (PII, toxicity)
  |
  o-- Station: Smarsh Archive
  |   Drop off: archive the brief (FINRA 2210 communication)
  |
  o-- Station: Salesforce Audit
  |   Drop off: IR_Audit_Log__c entry
  |
  o-- Deliver: meeting prep brief -> WhatsApp at 6:02am
  o-- END

  Systems: Salesforce FSC, Orion, eMoney, Bedrock, Smarsh
  Time: ~15 seconds
  Compliance: Reg BI documented, communication archived, audit logged
```

### Journey 2: Equity Analyst, Slack — Full 23-Stage Pipeline

David Kim (Analyst, Tier 3, Acme WM) on Slack: "Deep dive on NVIDIA ahead of earnings"

```
  Platform:  Slack
  Line:      Line 1 (Research Express) -- full 23-stage pipeline
  Ticket:    analyst, research-authority, tier3

  o-- Slack Platform
  o-- Ticket Gate: David Kim, Analyst -- GREEN
  o-- Switch Yard: intent = research.generate_brief (triggers pipeline)
  |
  o-- Station: Salesforce FSC (Stage 2)
  |   Pick up: company, coverage, watchlist, prior research
  |   Signal: restricted list for NVDA -- GREEN
  |
  o-- Station: Market Data MCP (Stage 3)
  |   Pick up: quote, price history, consensus, earnings calendar
  |
  o-- Station: News Search MCP (Stage 4)
  |   Pick up: 20 articles, 15 headlines
  |
  o-- Station: SEC EDGAR MCP (Stage 5)
  |   Pick up: 10-K, 10-Q, 8-K filings
  |
  o-- Station: Bedrock LLM (Stage 6) -- transcript summarization
  |
  o-- SIGNAL: HITL GATE (Stage 7) -- STOP
  |   Data quality: 89% complete. David approves -- GREEN
  |
  o-- Station: Financial Models (Stages 9-11)
  |   DCF -> $184, Comps -> $167, Monte Carlo -> median $192
  |
  o-- Station: Bedrock LLM (Stage 12) -- sentiment synthesis
  |
  o-- SIGNAL: HITL GATE (Stage 13) -- STOP
  |   David reviews model outputs -- GREEN
  |
  o-- Station: Bedrock LLM + Einstein Trust Layer (Stages 14-18)
  |   Thesis, catalysts, risks, rating, target price
  |
  o-- Station: Compliance Engine (Stage 20)
  |   Restricted list: CLEAR. MNPI: CLEAR. Anti-fabrication: PASS
  |
  o-- SIGNAL: HITL GATE (Stage 21) -- STOP
  |   David reviews final brief -- GREEN
  |
  o-- Station: Salesforce CRM (Stage 22) -- IR_Research_Note__c
  o-- Station: Salesforce Audit + Langfuse (Stage 23)
  o-- Deliver: summary + link -> Slack
  o-- END

  Systems: SF FSC, Market Data, News, SEC EDGAR, Bedrock,
           Financial Models, Compliance Engine, Langfuse
  Time: ~8-12 minutes (23 stages, 3 HITL pauses)
  Compliance: 3 HITL gates, restricted list, MNPI filtered,
              anti-fabrication verified, full audit trail
```

### Journey 3: Compliance Officer, Web Portal

Mike Torres (CCO, Tier 3) on Web: "Show me all agent actions flagged for MNPI in the last 7 days"

```
  Platform:  Web Portal
  Line:      Line 3 (Compliance Inspector)
  Ticket:    compliance_officer, cross-boundary-audit, tier3

  o-- Web Platform
  o-- Ticket Gate: Mike Torres, CCO -- GREEN (elevated authority)
  o-- Switch Yard: intent = compliance.audit_review
  |
  o-- Station: Salesforce IR_Audit_Log__c
  |   Query: MNPI_Flag__c = true, last 7 days -- 12 entries
  |
  o-- Station: Langfuse -- cross-reference trace_ids
  o-- Station: Bedrock LLM -- summarize findings, flag patterns
  o-- Deliver: compliance report -> Web Portal
  o-- END

  Systems: Salesforce, Langfuse, Bedrock
  Time: ~10 seconds
  Compliance: CCO audit access logged, no MNPI data exposed
```

### Journey 4: Hedge Fund PM, Bloomberg Terminal

James Park (PM, Tier 5, Pod Alpha) on Bloomberg: "What's our exposure to semiconductors across the book?"

```
  Platform:  Bloomberg Terminal
  Line:      Line 1 (Research Express) -- abbreviated
  Ticket:    pm, pod_alpha_only, tier5

  o-- Bloomberg Platform
  o-- Ticket Gate: James Park, PM, Pod Alpha -- GREEN
  o-- Switch Yard: intent = client.get_holdings + research.summarize
  |
  o-- Signal: Pod isolation check
  |   James is Pod Alpha. Pod Beta, Gamma: INVISIBLE -- RED
  |
  o-- Station: SS&C Eze (Pod Alpha only)
  |   Signal: tier5 MNPI policy
  |   Return: SECTOR EXPOSURE PERCENTAGES ONLY
  |   Do NOT return: individual positions, sizes, P&L
  |
  o-- Station: Bloomberg B-PIPE -- sector performance, news
  o-- Station: Bedrock LLM -- synthesize exposure + context
  o-- Deliver: sector exposure summary -> Bloomberg
  o-- END

  Systems: SS&C Eze, Bloomberg, Bedrock
  Time: ~8 seconds
  Compliance: pod isolation enforced, positions NOT exposed
```

### Journey 5: Advisor Executing a Trade, Slack

Sarah Chen (Advisor, Tier 3) on Slack: "Trim Henderson's NVDA position by 30%"

```
  Platform:  Slack
  Line:      Line 4 (Execution Express)
  Ticket:    advisor, trade_recommendation (NOT trade_execution)

  o-- Slack Platform
  o-- Ticket Gate: Sarah Chen, Advisor -- GREEN
  o-- Switch Yard: intent = execution.prepare_order
  |
  o-- Station: Salesforce FSC -- Henderson is Sarah's client -- GREEN
  o-- Station: Orion -- NVDA position: 1,200 shares, 30% = sell 360
  |
  o-- Station: Compliance Engine
  |   Restricted list: CLEAR
  |   Suitability: trim reduces concentration -- SUITABLE
  |   Concentration: post-trade 7% (under 10%) -- OK
  |   Trading window: no blackout -- CLEAR
  |
  o-- ==========================================
  o-- == HITL GATE -- MANDATORY STOP           ==
  o-- ==                                       ==
  o-- == SELL 360 shares NVDA @ MARKET         ==
  o-- == Account: Henderson-BROKERAGE-001      ==
  o-- == Est. proceeds: ~$47,520               ==
  o-- == Compliance: ALL CLEAR                 ==
  o-- ==                                       ==
  o-- == [APPROVE]  [REJECT]  [EDIT]           ==
  o-- == Sarah clicks [APPROVE]                ==
  o-- ==========================================
  |
  o-- Station: Schwab API -- submit SELL 360 NVDA MARKET
  |   Confirmation: Order ID SCH-2026-04-12-8847
  |
  o-- Station: Salesforce CRM -- update record, audit log
  o-- Deliver: "Order submitted. SELL 360 NVDA. ID: SCH-8847" -> Slack
  o-- END

  Systems: SF FSC, Orion, Compliance, HITL Gate, Schwab API, SF Audit
  Time: ~30 seconds (plus HITL wait)
  Compliance: all checks passed, HITL logged, trade audited
```

### Journey 6: Cross-Boundary Agent-to-Agent (Future)

Sarah's agent at Acme WM verifies settlement with Schwab's agent via A2A protocol.

```
  o-- Sarah's Agent (Acme WM, OpenClaw)
  o-- A2A: Discover Schwab Settlement Agent (Agent Card)
  o-- A2A: Send task with Agent Identity Document
  |   AID: Sarah Chen, Advisor, Acme WM, LEI, CRD
  |   Task: "Verify settlement for order SCH-8847"
  |
  o-- Schwab's Agent receives task
  |   Verify AID: Acme WM registered BD? -- YES
  |   Verify Sarah: registered rep? -- YES
  |   Verify authority: can query settlements? -- YES
  |   Apply Schwab's OWN compliance rules
  |
  o-- Schwab returns: "SCH-8847 settled T+1, 360 NVDA"
  o-- Both firms log cross-boundary interaction
  o-- Sarah's Agent updates Salesforce CRM
  o-- END

  Requires: A2A + Agent Identity Documents + cross-boundary trust.
  This is Phase 4+ territory.
```

---

## Why Financial Institutions Will Adopt This

### Reason 1: They Already Have the Stations

Every FSI firm already has Salesforce, or Orion, or Aladdin, or Bloomberg. They already have a compliance system and a custodian. The stations EXIST. What they don't have is the RAILWAY connecting them. Today the "railway" is a human manually logging into 5-8 systems. 007 replaces the human-as-railway with an agent-as-railway. The stations don't change. The tracks connect them.

### Reason 2: The Ticket System Matches How FSI Already Works

FSI already has roles, licenses, authorities, and boundaries. Series 7 license. Fiduciary duty. Chinese walls. Pod isolation. Restricted lists. The Agent Identity Document encodes what already exists in human form into machine-readable form. A compliance officer looks at an AID and immediately understands: "This agent can do what Sarah Chen can do, minus trade execution." FINRA 2026 says "supervise AI agents like employees." The ticket system IS that supervision.

### Reason 3: Incremental Adoption — One Line at a Time

Month 1: Line 2 (Client Service). CRM + Portfolio + Planning. Meeting prep. 45 min to 5 min.

Month 3: Add Line 1 (Research). SEC EDGAR + Market Data + News. Research briefs. 2x stock coverage.

Month 6: Add Line 3 (Compliance). Smarsh + Restricted List + Audit. Automated monitoring. 3x volume.

Month 9: Add Line 4 (Execution). Custodian API + HITL Gate. Full loop. Research to execution.

Each line is independently valuable. If Line 1 fails, Line 2 still works.

### Reason 4: No Ripping and Replacing

007 does not ask firms to replace Salesforce, Orion, Bloomberg, or their compliance system. It connects them. Your existing systems become stations on the railway. You build a platform (MCP server) in front of each one. Wealthbox instead of Salesforce? Different station, same railway. Addepar instead of Orion? Different station, same railway.

### Reason 5: The Trust System Is the Selling Point, Not the Tax

Most technology is sold despite compliance requirements. 007 flips this. The trust system IS the product. A CCO sees it as: "Finally, a system that enforces our compliance rules automatically, logs everything, and gives me an audit trail I can show to a FINRA examiner." The signal system is not a cost center. It is the reason the railway gets approved for deployment.

### Reason 6: The $124 Trillion Forcing Function

$124 trillion is transferring from boomers to heirs through 2048. The industry is short 100,000+ advisors. The firms that can serve 3x more clients per advisor with personalized, compliant service will capture the assets. The railway is not a nice-to-have. It is the infrastructure that determines which firms survive the wealth transfer.

---

## The Adoption Curve

| Year | Tier | Why | Lines | Key Stations |
|------|------|-----|-------|-------------|
| 1 | Tier 4 RIAs | Most agile, most pain, REST APIs everywhere | 2 + 1 | Wealthbox/Redtail + Orion + eMoney + SEC EDGAR |
| 2 | Tier 3 Wealth/BD | SF FSC dominant, FINRA creates demand for signals | 1-4 (full) | SF FSC + Envestnet + Schwab + Smarsh |
| 3 | Tier 2 Asset Mgrs | Aladdin/CRD partnerships, FIX bridge needed | 1 + 4 | Aladdin + FactSet + Bloomberg + FIX |
| 3-4 | Tier 5 Hedge Funds | Bespoke per fund, pod isolation is differentiator | 1 + 4 | SS&C Eze + Bloomberg + FIX + PB APIs |
| 4+ | Tier 1 Banks | Proprietary everything, Chinese walls hardest | All 5 | Proprietary + NICE Actimize + SWIFT + FIX |
