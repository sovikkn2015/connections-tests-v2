# UIUX-02: ASCII Wireframes — All 6 Screens + Mobile

> Date: April 18, 2026
> Companion to: UIUX-01-deep-research-and-design.md
> Purpose: Visual wireframes for all screens in the 007 Web Console
> Personas: Sarah Chen (Advisor), Mike Torres (Principal), Diana Park (Compliance), James Liu (Admin)

---

## S01: Advisor Chat (Primary Screen)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  ☰  007 Platform          Sarah Chen · Advisor · Tier 4 RIA    🔔 3   ⚙️       │
├────────────┬─────────────────────────────────────────────────────────────────────┤
│            │                                                                     │
│  WORKSPACE │   CHAT                              DETAIL PANEL                    │
│  ▸ Chat    │                                                                     │
│  ▸ Clients │   ┌─────────────────────────┐       ┌─────────────────────────────┐ │
│  ▸ Orders  │   │ 🤖 Client Service       │       │  📋 MEETING PREP            │ │
│            │   │                         │       │                             │ │
│  REVIEWS   │   │ Here's your meeting     │       │  Client: James Henderson    │ │
│  (hidden)  │   │ prep for Henderson:     │       │  Meeting: Apr 19, 2:00 PM   │ │
│            │   │                         │       │  Advisor: Sarah Chen        │ │
│  COMPLIANCE│   │ ▸ View full brief →     │       │                             │ │
│  (hidden)  │   │                         │       │  ── CLIENT SUMMARY ──────── │ │
│            │   │ Sources: Salesforce,    │       │  Risk: Moderate             │ │
│  ADMIN     │   │ Orion, eMoney           │       │  Objective: Growth          │ │
│  (hidden)  │   │ 🔗 View provenance     │       │  AUM: $1.2M                 │ │
│            │   └─────────────────────────┘       │                             │ │
│            │                                     │  ── TOP HOLDINGS ────────── │ │
│            │   ┌─────────────────────────┐       │  AAPL    32%  +12.4%       │ │
│            │   │           You  10:32 AM │       │  VTI     28%   +8.1%       │ │
│            │   │                         │       │  BND     15%   -1.2%       │ │
│            │   │   Prep me for my        │       │  MSFT    12%  +15.7%       │ │
│            │   │   meeting with          │       │  Cash    13%     —         │ │
│            │   │   Henderson tomorrow    │       │                             │ │
│            │   └─────────────────────────┘       │  ── TALKING POINTS ──────── │ │
│            │                                     │  • Portfolio up 9.2% YTD    │ │
│            │                                     │  • Rebalance due (equity    │ │
│            │                                     │    overweight by 5%)        │ │
│            │                                     │  • eMoney plan on track     │ │
│            │                                     │    for retirement goal      │ │
│            │                                     │                             │ │
│            │                                     │  ── COMPLIANCE NOTES ────── │ │
│            │                                     │  ✅ No restricted securities│ │
│            │                                     │  ✅ Concentration within    │ │
│            │                                     │     limits                  │ │
│            │                                     │  ⚠️  Annual review due      │ │
│            │                                     │                             │ │
│            │                                     │  [Send to Client] [PDF] [✏️]│ │
│            │                                     └─────────────────────────────┘ │
│            │                                                                     │
│            │   ┌─────────────────────────────────────────────────────────────┐   │
│            │   │  💬  Ask 007 anything...                            [Send]  │   │
│            │   └─────────────────────────────────────────────────────────────┘   │
├────────────┴─────────────────────────────────────────────────────────────────────┤
│  Data sources: Salesforce FSC, Orion, eMoney  │  Provenance: 6 stages, SHA-256  │
└──────────────────────────────────────────────────────────────────────────────────┘
```


---

## S02: Order Approval (HITL Gate)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  ☰  007 Platform          Sarah Chen · Advisor · Tier 4 RIA    🔔 3   ⚙️       │
├────────────┬─────────────────────────────────────────────────────────────────────┤
│            │                                                                     │
│  WORKSPACE │   ⚠️  ORDER REQUIRES YOUR APPROVAL                                 │
│  ▸ Chat    │                                                                     │
│  ▸ Clients │   ┌─────────────────────────────────────────────────────────────┐   │
│  ▸ Orders ◀│   │                                                             │   │
│            │   │   🟢 BUY  ·  100 shares  ·  AAPL (Apple Inc.)              │   │
│            │   │   Order Type: Limit @ $215.00                               │   │
│            │   │   Account: Henderson IRA (FID-001) · Fidelity               │   │
│            │   │                                                             │   │
│            │   │   ── CLIENT CONTEXT ──────────────────────────────────────── │   │
│            │   │   Client: James Henderson · Moderate Risk · Growth          │   │
│            │   │   Current AAPL: 150 shares (32% of portfolio)               │   │
│            │   │   Post-trade AAPL: 250 shares (38% of portfolio)            │   │
│            │   │                                                             │   │
│            │   │   ── COMPLIANCE CHECKS ──────────────────────────────────── │   │
│            │   │   ✅ Suitability       Growth objective, moderate risk  OK  │   │
│            │   │   ✅ Restricted List   AAPL not restricted                  │   │
│            │   │   ⚠️  Concentration    38% post-trade (limit: 40%)         │   │
│            │   │   ✅ Client Scope      Henderson in advisor scope           │   │
│            │   │   ✅ Authority         order.submit in scope                │   │
│            │   │                                                             │   │
│            │   │   ── COST IMPACT ────────────────────────────────────────── │   │
│            │   │   Estimated Cost: $21,500.00                                │   │
│            │   │   Cost Basis Method: FIFO                                   │   │
│            │   │   Tax Lot: New lot (no wash sale risk)                      │   │
│            │   │                                                             │   │
│            │   │   ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │   │
│            │   │   │ ✅ APPROVE   │ │ ❌ REJECT    │ │ ✏️  REQUEST CHANGES│  │   │
│            │   │   │   ORDER      │ │   ORDER      │ │                    │  │   │
│            │   │   └──────────────┘ └──────────────┘ └────────────────────┘  │   │
│            │   │                                                             │   │
│            │   │   ⏱️  Auto-cancels in 23h 41m without approval              │   │
│            │   │                                                             │   │
│            │   └─────────────────────────────────────────────────────────────┘   │
│            │                                                                     │
└────────────┴─────────────────────────────────────────────────────────────────────┘
```

---

## S03: Principal Review Queue (BD Only — FINRA 2210)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  ☰  007 Platform          Mike Torres · Principal · Tier 3 BD   🔔 12  ⚙️      │
├────────────┬─────────────────────────────────────────────────────────────────────┤
│            │                                                                     │
│  WORKSPACE │   PENDING REVIEWS (12)                    REVIEW DETAIL             │
│  ▸ Chat    │                                                                     │
│            │   ┌─────────────────────────┐  ┌───────────────────────────────────┐│
│  REVIEWS   │   │                         │  │                                   ││
│  ▸ Pending◀│   │ 🔴 SLA 0:42            │  │  AGENT OUTPUT (what client sees)  ││
│  ▸ History │   │ Sarah Chen → Henderson  │  │                                   ││
│            │   │ Meeting Prep · 9:48 AM  │  │  "Based on your portfolio review, ││
│  COMPLIANCE│   │ ─────────────────────── │  │   I recommend increasing your     ││
│  (read)    │   │ 🟡 SLA 1:55            │  │   equity allocation by 5% to      ││
│            │   │ Tom Park → Williams     │  │   align with your growth          ││
│            │   │ Portfolio Review · 9:52 │  │   objective. Your current 60/40   ││
│            │   │ ─────────────────────── │  │   split could move to 65/35..."   ││
│            │   │ 🟢 SLA 3:12            │  │                                   ││
│            │   │ Lisa Wang → Davis       │  │  ── COMPLIANCE CONTEXT ────────── ││
│            │   │ Research Brief · 10:01  │  │  OPA Decision: ALLOW              ││
│            │   │ ─────────────────────── │  │  Rule: authority/main.rego        ││
│            │   │ 🟢 SLA 3:28            │  │  WSP Section: 2.0                 ││
│            │   │ Sarah Chen → Martinez   │  │                                   ││
│            │   │ Trade Confirm · 10:05   │  │  MNPI Stripped: SSN, DOB          ││
│            │   │ ─────────────────────── │  │  Leakage Scan: ✅ PASS            ││
│            │   │ 🟢 SLA 3:45            │  │  Smarsh Archive: Pending          ││
│            │   │ Tom Park → Anderson     │  │                                   ││
│            │   │ Meeting Prep · 10:08    │  │  ── ADVISOR ──────────────────── ││
│            │   │                         │  │  Sarah Chen · CRD# 1234567       ││
│            │   │  ↑↓ Navigate  A Approve │  │  Client: Henderson (CLT-10001)   ││
│            │   │  R Reject     E Edit    │  │                                   ││
│            │   │                         │  │  ┌──────────┐ ┌────────────────┐  ││
│            │   │  Showing 5 of 12        │  │  │✅ APPROVE│ │❌ REJECT+REASON│  ││
│            │   │                         │  │  └──────────┘ └────────────────┘  ││
│            │   └─────────────────────────┘  │  ┌────────────────────────────┐   ││
│            │                                │  │ ✏️  EDIT AND APPROVE       │   ││
│            │                                │  └────────────────────────────┘   ││
│            │                                └───────────────────────────────────┘│
└────────────┴─────────────────────────────────────────────────────────────────────┘
```

---

## S04: Audit Trail Viewer (Compliance Console)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  ☰  007 Platform          Diana Park · Compliance · Tier 3 BD   🔔 2   ⚙️      │
├────────────┬─────────────────────────────────────────────────────────────────────┤
│            │                                                                     │
│  WORKSPACE │   AUDIT TRAIL                                                       │
│  (read)    │                                                                     │
│            │   Filters: [Apr 11-18 ▾] [Henderson ▾] [All Actions ▾] [All ▾]    │
│  COMPLIANCE│                                                                     │
│  ▸ Audit  ◀│   ┌────────┬──────────┬────────┬──────────┬────────┬──────┬──────┐ │
│  ▸ OPA Log │   │ TIME   │ TRACE    │ ACTOR  │ ACTION   │ TARGET │ DEC  │ MOD  │ │
│  ▸ MNPI    │   ├────────┼──────────┼────────┼──────────┼────────┼──────┼──────┤ │
│  ▸ Alerts  │   │ 10:32  │ e2e-001  │ Sarah  │client    │Hender- │🟢   │ M6   │ │
│            │   │        │          │ Chen   │.read     │son     │ALLOW │      │ │
│            │   ├────────┼──────────┼────────┼──────────┼────────┼──────┼──────┤ │
│            │   │ 10:33  │ e2e-002  │ Agent  │order     │AAPL    │🟡   │ M6   │ │
│            │   │        │          │ Exec   │.submit   │        │ESCAL │      │ │
│            │   ├────────┼──────────┼────────┼──────────┼────────┼──────┼──────┤ │
│            │   │ 10:45  │ e2e-003  │ Sarah  │order     │AAPL    │🟢   │ M6   │ │
│            │   │        │          │ Chen   │.approve  │        │ALLOW │      │ │
│            │   ├────────┼──────────┼────────┼──────────┼────────┼──────┼──────┤ │
│            │   │ 09:15  │ e2e-004  │ Tom    │client    │Hender- │🔴   │ M6   │ │
│            │   │        │          │ Park   │.read     │son     │DENY  │      │ │
│            │   └────────┴──────────┴────────┴──────────┴────────┴──────┴──────┘ │
│            │                                                                     │
│            │   ── DETAIL (click row e2e-001) ──────────────────────────────────  │
│            │                                                                     │
│            │   PROVENANCE CHAIN                    MNPI FILTER                   │
│            │                                                                     │
│            │   ● M1  Identity Verify               Stripped: ssn, dob, tax_id   │
│            │   │ SHA: a3f8c2...                     Rule: mnpi/main.rego         │
│            │   ● M2  Authority Check                Archetype: tier4_ria         │
│            │   │ SHA: 7b1d4e...                                                  │
│            │   │ Rule: authority/main.rego          WORM Record:                  │
│            │   │ WSP: 2.0                           s3://007-worm/2026/04/        │
│            │   ● M4  MNPI Filter                    e2e-001.json                 │
│            │   │ SHA: 9e2f5a...                                                  │
│            │   ● M6  Route to Vendor               [View Langfuse] [View WORM]   │
│            │   │ SHA: 1c8b3d...                    [Export JSON]                  │
│            │   ● M11 Salesforce FSC                                               │
│            │   │ SHA: 4d7a9f...                                                  │
│            │   ● M10 Audit Write                                                 │
│            │     SHA: 8f3c1b...                                                  │
│            │                                                                     │
└────────────┴─────────────────────────────────────────────────────────────────────┘
```

---

## S05: Admin System Health

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  ☰  007 Platform          James Liu · Admin · Tier 4 RIA       🔔 0   ⚙️       │
├────────────┬─────────────────────────────────────────────────────────────────────┤
│            │                                                                     │
│  WORKSPACE │   SYSTEM HEALTH                                                     │
│            │                                                                     │
│  ADMIN     │   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────┐ │
│  ▸ Health ◀│   │ 🟢 TRUST     │ │ 🟢 INTEL     │ │ 🟡 DATA      │ │ 🟢 COMPL  │ │
│  ▸ Adapters│   │ LAYER        │ │ LAYER        │ │ LAYER        │ │           │ │
│  ▸ OPA     │   │ M1  🟢  2ms │ │ M8  🟢 45ms │ │ 18/20 up     │ │ OPA v2.4  │ │
│  ▸ Metrics │   │ M2  🟢  1ms │ │ M9  🟢  3ms │ │ 2 degraded   │ │ 278 tests │ │
│            │   │ M6  🟢  8ms │ │ M12 🟢  —   │ │              │ │ 100% pass │ │
│            │   │ M10 🟢  5ms │ └──────────────┘ └──────────────┘ └───────────┘ │
│            │   └──────────────┘                                                  │
│            │                                                                     │
│            │   ── ADAPTER STATUS ──────────────────────────────────────────────  │
│            │                                                                     │
│            │   ADAPTER          VENDOR      PROTO  STATUS  CB     LAST OK        │
│            │   salesforce-fsc   Salesforce  REST   🟢 UP   CLOSED  2m ago        │
│            │   orion            Orion       REST   🟢 UP   CLOSED  1m ago        │
│            │   schwab-rest      Schwab      REST   🟢 UP   CLOSED  3m ago        │
│            │   emoney           eMoney      REST   🟡 SLOW CLOSED  5m ago        │
│            │   fidelity-rest    Fidelity    REST   🔴 DOWN OPEN    2h ago        │
│            │   bloomberg        Bloomberg   BLPAPI 🟢 UP   CLOSED  30s ago       │
│            │   factset          FactSet     MCP    🟢 UP   CLOSED  2m ago        │
│            │   eze-grpc         SS&C Eze    gRPC   🟢 UP   CLOSED  1m ago        │
│            │                                                                     │
│            │   ── PERFORMANCE (last 1 hour) ───────────────────────────────────  │
│            │   M6 Gateway:  p50=8ms  p95=22ms  p99=45ms  142 req/s              │
│            │   M2 Policy:   p50=1ms  p95=3ms   p99=5ms   8,421 evals            │
│            │   M10 Audit:   p50=5ms  p95=12ms  p99=18ms  8,421 writes           │
│            │   Leakage:     p50=2ms  p95=6ms   p99=9ms   4,210 scans            │
│            │                                                                     │
└────────────┴─────────────────────────────────────────────────────────────────────┘
```

---

## S06: Mobile (Responsive — 375px)

```
┌─────────────────────────┐
│  007    Sarah Chen  🔔 3│
├─────────────────────────┤
│                         │
│  🤖 Client Service      │
│                         │
│  Here's your meeting    │
│  prep for Henderson:    │
│                         │
│  Client: James Henderson│
│  AUM: $1.2M             │
│  Risk: Moderate         │
│                         │
│  Top Holdings:          │
│  AAPL  32%  +12.4%     │
│  VTI   28%   +8.1%     │
│  BND   15%   -1.2%     │
│                         │
│  Talking Points:        │
│  • Portfolio up 9.2%    │
│  • Rebalance due        │
│  • Plan on track        │
│                         │
│  [Send] [PDF] [Edit]   │
│                         │
│  Sources: SF, Orion,    │
│  eMoney · 🔗 Provenance │
│                         │
│  ┌───────────────────┐  │
│  │ Ask 007...  [Send]│  │
│  └───────────────────┘  │
│                         │
├─────┬──────┬──────┬─────┤
│ 💬  │ 👤   │ 📋   │ ⚙️  │
│Chat │Client│Review│Set  │
└─────┴──────┴──────┴─────┘
```

---

## SCREEN SUMMARY

| Screen | Persona | Key Feature | HITL Role |
|--------|---------|-------------|-----------|
| S01 Advisor Chat | Sarah (Advisor) | Split-pane: chat + contextual detail | Reviews briefs before forwarding |
| S02 Order Approval | Sarah (Advisor) | Single-focus HITL gate with compliance checks | Mandatory approve/reject for orders |
| S03 Principal Queue | Mike (Principal) | Master-detail with SLA countdown + keyboard shortcuts | FINRA 2210 mandatory review |
| S04 Audit Trail | Diana (Compliance) | Filterable table + provenance chain drawer | Post-hoc investigation |
| S05 Admin Health | James (Admin) | Status cards + adapter table + perf metrics | Operational monitoring |
| S06 Mobile | Sarah (Advisor) | Responsive chat with bottom tab nav | Quick checks on the go |

---

*UIUX-02 — Project 007 FSI Interoperability Platform*
*ASCII Wireframes — All 6 Screens + Mobile*
