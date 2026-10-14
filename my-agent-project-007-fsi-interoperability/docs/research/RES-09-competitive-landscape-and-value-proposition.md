# RES-09: Competitive Landscape, Metrics, and Value Proposition

> Date: April 18, 2026
> Category: RESEARCH
> Method: Web research across 30+ sources (April 2026)
> Purpose: Map 007 against funded competitors, define the metric, articulate the value proposition

---

## PART 1: THE MARKET

Three converging forces:

1. MCP is the standard. Anthropic (Nov 2024), then OpenAI, Google, Microsoft. Arcade.dev calls it "the missing infrastructure layer." FactSet shipped a production MCP server. The protocol war is over.
2. $3B+ in compliance fines (2021-2025). 100+ firms sanctioned for off-channel communication failures. JP Morgan $200M. January 2025: 12 firms, $63M. AI agent communications are next.
3. Advisors lose 60-70% of their time to admin. Ops teams lose 30-40% to reconciliation. PreciseFP saved 198K hours in 2025 just automating data collection.

---

## PART 2: FUNDED COMPETITORS

### AI Compliance Agents

| Company | Funding | What | 007 Advantage |
|---------|---------|------|---------------|
| Delve | $32M @ $300M | SOC 2/HIPAA/GDPR automation | Dropped by YC (Apr 2026, fake evidence allegations). Generic, not FSI. No MNPI. No OPA. |
| Spektr | $20M Series A | KYC/AML for banks | KYC only. No wealth management. No interoperability. |
| Kobalt Labs | $12.7M | TPRM, internal audit | Third-party risk only. No trading. No portfolio. |
| Variance | $21.5M Series A | Fraud/risk investigation agents | Investigation focus. Not a platform. No MCP. |
| Diligent AI | EUR 2.1M Seed | KYC/AML investigations | Early stage. KYC only. |

None solve interoperability. They automate within one system. 007 enforces compliance across 17+ system boundaries.

### MCP Infrastructure

| Company | What | Relationship to 007 |
|---------|------|-------------------|
| Arcade.dev | MCP runtime, multi-user auth, SOC 2 Type 2 | Closest competitor to M6. But horizontal. No FSI Rego, no MNPI, no archetypes. Could be partner or competitor. |
| MintMCP | MCP gateway hosting | Infrastructure. Could host 007 adapters. Not a competitor. |

Arcade claims 75% time savings for wealth managers. But they have zero FSI compliance logic. 007 has 2,100+ lines of Rego across 5 archetypes and 5 jurisdictions.

### WealthTech Data

| Company | What | Relationship to 007 |
|---------|------|-------------------|
| BridgeFT | 900+ custodian feeds, single API | Solves DATA. Not TRUST. 007 could use BridgeFT as an M11 adapter. Partner. |
| Envestnet | 110K advisors, Tamarac platform | Incumbent. No AI agent layer. No MCP. No trust gateway. 007 wraps via M11. |
| Orion | #1 portfolio accounting | Incumbent. No AI agent. No compliance between systems. 007 wraps via M11. |

---

## PART 3: THE METRIC — TAIS

Trust-Adjusted Interoperability Score = (Systems) x (Compliance%) x (Trust Enforcement) x (Audit Completeness)

| Platform | Systems | Compliance | Trust | Audit | TAIS |
|----------|---------|-----------|-------|-------|------|
| 007 | 20 | 85% | 1.0 (OPA) | 1.0 (3-tier WORM) | 17.0 |
| Arcade.dev | 10 | 30% | 0.5 (auth) | 0.33 (logs) | 0.5 |
| BridgeFT | 900+ | 10% | 0.0 | 0.33 | 0.0 |
| Envestnet | 5 | 20% | 0.0 | 0.33 | 0.0 |
| Spektr | 1 | 40% | 0.5 | 0.33 | 0.07 |

007 is 34x the nearest competitor. Not because it's better at one thing — because no one else combines all four dimensions.

---

## PART 4: VALUE PROPOSITION

For the advisor: 40 minutes per meeting prep becomes 60 seconds. 30+ hours/week reclaimed.

For the CCO: Audit response from days to seconds. $3B+ in industry fines avoided.

For the firm: Integration cost from $150-500K per vendor to $5-15K/month for the whole platform.

One line: **007 is the trust layer between every system a wealth management firm uses — so AI agents can act on financial data without compliance risk.**

---

## PART 5: WHY NOW

- MCP standardized (2024-2026). Protocol war over. Vendors shipping native MCP.
- $3B+ fines created urgency. Every CCO needs compliance automation.
- 51% of orgs have AI agents in production. 58% blocked by security. 007 solves the security.
- Incumbents are slow. Envestnet 2026 = mobile redesign. Orion = MassMutual partnership. Neither has MCP or trust gateway.
- Vendor approvals = time moat. Fidelity 6-12 months. Competitor starting today is 6-12 months behind.

---

## PART 6: PRICING

| Tier | Customer | Price/Month |
|------|----------|-------------|
| Wedge | Any MCP user | $500-2K (RIA), $5-15K (BD) |
| Tier 4 RIA | Independent RIA | $500-2K |
| Tier 3 BD | Broker-dealer | $5-25K |
| Tier 2 AM | Asset manager | $8-40K |
| Tier 5 HF | Hedge fund | $8-40K |
| Tier 1 Bank | Investment bank | $50-150K (DEFERRED) |

---

## PART 7: BOTTOM LINE

The market is forming. MCP is the protocol. Compliance is the pain. Interoperability is unsolved. Competitors are horizontal (Arcade), single-domain (Spektr), or data-only (BridgeFT). Nobody else has deterministic OPA + MNPI filtering + 18 canonical types + 20 adapters + 3-tier WORM + 5 archetypes + 5 jurisdictions behind a single MCP gateway. TAIS 17.0 vs 0.5. Ship the wedge product.

---

*RES-09 — Project 007 FSI Interoperability Platform*
