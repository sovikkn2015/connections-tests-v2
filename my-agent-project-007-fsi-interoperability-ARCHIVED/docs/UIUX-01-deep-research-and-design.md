# UIUX-01: UI/UX Deep Research, Design, and Architecture

> Date: April 18, 2026
> Category: DESIGN (UI/UX)
> Status: Design Phase — No code until approved
> Predecessor: ARCH-09 (module map), 007-consolidated-design-and-plan.md
> Purpose: Complete UI/UX strategy for the 007 FSI Platform web channel
> Research Sources: Envestnet Tamarac 2026 releases, AdvisorEngine Client Portal, Trew Knowledge UX of Trust (2026), Peakflo HITL Governance Framework, FINRA Rule 2210, OWASP accessibility guidelines

---

## PART 1: THE PROBLEM — WHY 007 NEEDS A UI

007 has 13 modules, 707 tests, and zero user interface. An advisor cannot use this platform without opening Slack or Teams. The web channel (M12) is defined in the architecture but has no design, no wireframes, no component library, no screens.

The competitors all have UIs:
- Envestnet Tamarac: full advisor portal + client portal + mobile app (2026 redesign with responsive holdings, performance attribution, billing UI)
- Orion: advisor dashboard + client portal + Eclipse trading UI
- AdvisorEngine: client portal with "human-centered design principles"
- Salesforce FSC: advisor console with household views, financial accounts, goals

007 wraps all of these systems. But the advisor still needs a place to ask questions, review answers, approve orders, and monitor compliance. That place is the web UI.

### What the UI is NOT

- NOT a replacement for Slack/Teams/WhatsApp channels (those remain via M12 OpenClaw)
- NOT a portfolio management system (Orion/Tamarac do that)
- NOT a CRM (Salesforce/Wealthbox/Redtail do that)
- NOT a trading platform (Schwab/Fidelity/Eze do that)

### What the UI IS

The UI is the trust interface — the place where humans interact with the AI agent system, review its work, approve its actions, and verify its compliance. It is the HITL surface.

---

## PART 2: COMPETITIVE LANDSCAPE ANALYSIS

### 2.1 Envestnet Tamarac (110K+ advisors)

Key UX patterns (from 2026 Q1 release):
- Responsive design across all screen sizes (mobile redesign)
- Holdings table with locked first column on horizontal scroll
- Performance attribution with benchmark contribution columns
- Pie chart visuals for asset allocation
- Report Studio with custom grouping options
- Selective sync for data management
- Refreshed billing UI with modernized navigation

What they lack: No AI agent interface. No HITL approval workflow. No compliance decision transparency. No cross-system intelligence.

### 2.2 AdvisorEngine Client Portal

Key UX patterns:
- Human-centered design principles
- Intuitive client engagement focus
- Advisor-client relationship emphasis

What they lack: Advisor-facing AI tools. Compliance workflow. Multi-system data aggregation.

### 2.3 Industry UX Trends (2025-2026)

Content rephrased for compliance with licensing restrictions:

- Trust is a product feature, not a marketing claim. It shows up in consent flows, data visibility, and the ability to undo actions. ([Source](https://trewknowledge.com/2026/03/16/the-ux-of-trust-designing-financial-platforms-for-consent-comfort-and-compliance/))
- Granular consent beats single "Agree" buttons. Finance data has different emotional weights.
- Well-designed HITL systems enable 80-90% automation while maintaining control. Tiered approval: auto-approve low-risk, route mid-risk for review, escalate high-risk. ([Source](https://peakflo.co/blog/human-in-the-loop-ai-finance-governance-framework))
- Forcing a high-net-worth client to log into four siloed apps to view net worth is the primary driver of HNW client churn in 2026. ([Source](https://www.goldendoorasset.com/playbooks/client-portal-ux))
- Optimized CRM interfaces save advisors 45 minutes daily. 34% higher adoption rates. ([Source](https://vantagepoint.io/blog/sf/ui/ux-design-the-hidden-driver-of-crm-adoption-in-financial-services))


---

## PART 3: USER PERSONAS

### 3.1 Primary: Financial Advisor (Sarah Chen)

- Role: Wealth advisor at a Tier 4 independent RIA
- Daily tools: Salesforce FSC, Orion, eMoney, Schwab, email, phone
- Pain: Opens 5 tabs to prep for one client meeting. Copies data manually. 40% of time on admin.
- Goal: "Prep me for Henderson tomorrow" — one question, complete brief, 60 seconds
- UI needs: Chat interface, meeting prep view, portfolio summary, client timeline
- HITL role: Reviews AI-generated briefs before sending to clients. Approves order recommendations.
- Tech comfort: Medium. Uses Salesforce daily but not a power user. Mobile-first for quick checks.

### 3.2 Secondary: Registered Principal (Mike Torres)

- Role: Chief Compliance Officer at a Tier 3 broker-dealer
- Regulatory: FINRA 2210 — must review all retail communications before delivery
- Pain: Reviews 50-100 agent outputs per day. Current process is email-based, slow, no audit trail.
- Goal: Queue of pending reviews. Approve/reject with one click. Full audit trail.
- UI needs: Principal review queue, communication preview, approve/reject/edit workflow, compliance dashboard
- HITL role: MANDATORY approver for all BD retail communications. Cannot be bypassed.
- Tech comfort: High. Power user of compliance tools. Needs keyboard shortcuts.

### 3.3 Tertiary: Compliance Officer (Diana Park)

- Role: Compliance analyst at a Tier 3 BD or Tier 4 RIA
- Pain: Audit trail spread across 5 systems. No single view of what the AI agent did and why.
- Goal: "Show me every action the agent took for client Henderson in the last 30 days"
- UI needs: Audit trail viewer, OPA decision log, MNPI filter log, provenance chain viewer
- HITL role: Post-hoc reviewer. Does not approve in real-time but investigates after the fact.
- Tech comfort: High. Comfortable with data tables, filters, exports.

### 3.4 Quaternary: Firm Administrator (James Liu)

- Role: Technology lead at a Tier 4 RIA
- Pain: No visibility into adapter health, OPA policy status, or system performance.
- Goal: "Is everything working? Which adapters are down? Are OPA policies current?"
- UI needs: System health dashboard, adapter status, OPA bundle versions, circuit breaker state
- HITL role: None (operational, not compliance)
- Tech comfort: Very high. Wants APIs and dashboards, not wizards.

---

## PART 4: INFORMATION ARCHITECTURE

### 4.1 Application Structure

```
007 Web Console
|
+-- Advisor Workspace (Sarah)
|   +-- Chat (primary interaction — conversational AI)
|   +-- Meeting Prep (structured output from client.prep_meeting)
|   +-- Portfolio View (holdings, performance, allocation — via M6)
|   +-- Client Timeline (interaction history — memory L2/L3)
|   +-- Order Review (HITL gate — approve/reject before submission)
|
+-- Principal Review Queue (Mike) [BD only]
|   +-- Pending Reviews (agent outputs awaiting FINRA 2210 approval)
|   +-- Review Detail (full output + compliance context + approve/reject/edit)
|   +-- Review History (completed reviews with audit trail)
|
+-- Compliance Console (Diana)
|   +-- Audit Trail Viewer (M10 3-tier — search by client, advisor, date, action)
|   +-- OPA Decision Log (authority + MNPI decisions with rule references)
|   +-- Provenance Chain Viewer (per-request SHA-256 hash chain)
|   +-- MNPI Filter Log (what was stripped, why, for whom)
|   +-- Compliance Alerts (BSA/AML triggers, concentration warnings)
|
+-- Admin Dashboard (James)
|   +-- System Health (all 13 modules — health check status)
|   +-- Adapter Status (M11 — 20 adapters, circuit breaker state, last response)
|   +-- OPA Policy Status (bundle versions, last sync, test results)
|   +-- Performance Metrics (latency p50/p95/p99, throughput, error rates)
|
+-- Settings
    +-- Profile (AID claims display — read-only)
    +-- Firm Config (M5 enterprise config — admin only)
    +-- Channel Preferences (notification settings)
    +-- Data Consent (granular consent per data category)
```

### 4.2 Navigation Model

- Left sidebar: persistent, collapsible, role-based
- Top bar: firm logo, user identity (name + role + archetype from AID), notifications, settings
- Content area: single-pane with contextual panels
- Mobile: bottom tab bar, responsive breakpoints at 768px and 1024px

### 4.3 Role-Based Visibility (Driven by AID Claims)

| AID Role | Workspace | Review Queue | Compliance Console | Admin Dashboard |
|----------|-----------|-------------|-------------------|----------------|
| advisor | Yes | No | No | No |
| principal | Yes | Yes | Read-only | No |
| compliance_officer | Read-only | Read-only | Yes | No |
| admin | Yes | Yes | Yes | Yes |

UI hides sections per role. M6 gateway enforces access via OPA — UI is not the security boundary.


---

## PART 5: SCREEN INVENTORY AND WIREFRAME DESCRIPTIONS

### 5.1 Screen S01: Advisor Chat (Primary Screen)

Layout: Split-pane. Left 40% = chat thread. Right 60% = contextual detail panel.

Chat thread (left):
- Message input at bottom with send button and attachment icon
- Messages flow upward (newest at bottom)
- User messages right-aligned (blue bubble), agent messages left-aligned (gray bubble) with specialist badge
- Streaming response indicator during agent processing
- Each agent message has: timestamp, specialist name, source attribution links, "View provenance" link
- HITL prompts inline: "Agent recommends buying 100 AAPL. [Approve] [Reject] [Edit]"

Detail panel (right):
- Dynamically populated based on last agent response type
- Meeting prep: structured card (Client Summary, Holdings, Interactions, Talking Points, Compliance Notes)
- Portfolio view: holdings table (locked first column), allocation pie chart, performance chart
- Research brief: sourced sections with citations, confidence score
- Order review: order details with HITL approve/reject, compliance checks, cost impact
- Empty state: "Ask a question to get started" with sample queries

### 5.2 Screen S02: Meeting Prep View

Full-width structured document: Header (client, meeting date) -> Client Summary (MNPI-filtered) -> Holdings Overview (top 10, allocation %, cost basis method) -> Recent Activity (last 5 from memory L2/L3) -> Financial Plan Summary (from eMoney) -> AI-Generated Talking Points (editable) -> Compliance Notes -> Actions [Send to Client] [Export PDF] [Edit] -> Provenance chain link

### 5.3 Screen S03: Principal Review Queue (BD Only)

Master-detail. Left = queue list (Status | Advisor | Client | Type | Submitted | SLA countdown). Right = review detail (full output, compliance context, OPA decision + wsp_section, MNPI fields stripped, leakage scan result). Actions: [Approve] [Reject with Reason] [Edit and Approve]. Keyboard shortcuts: A=approve, R=reject, arrow keys to navigate. SHA-256 approval token generated on approve.

### 5.4 Screen S04: Order Approval (HITL Gate)

Single-focus card: Order type badge, security, quantity, price type, account, client risk profile. Compliance checks list (passed/failed with OPA rule refs). Cost impact estimate. Concentration check. [Approve Order] [Reject Order] [Request Changes]. 24hr timeout warning. Approve button disabled if any compliance check failed.

### 5.5 Screen S05: Audit Trail Viewer

Full-width data table with filters (date range, client, advisor, action, decision, module). Columns: Timestamp | Trace ID | Actor | Action | Target | Decision | Module | SHA-256. Row click opens detail drawer: full audit JSON, provenance chain visualization (vertical timeline with per-stage SHA-256), MNPI filter details, OPA decision details, links to Langfuse and WORM record.

### 5.6 Screen S06: Admin System Health

Grid of status cards (Trust Layer, Intelligence Layer, Data Layer, Compliance) + module detail table (Module | Status | Latency | Error Rate | Circuit Breaker) + adapter detail table (Adapter | Vendor | Protocol | Status | Last Success | Rate Limit Usage). Color-coded: green/yellow/red/gray.

---

## PART 6: INTERACTION PATTERNS

### 6.1 HITL Approval Tiers

| Risk Level | Action Examples | UI Behavior |
|-----------|----------------|-------------|
| Low (read-only) | client.read, portfolio.read | Auto-delivered. No approval. |
| Medium (recommendations) | meeting prep, research brief | Advisor reviews before forwarding. Edit available. |
| High (financial actions) | order.submit, wire.send | Prominent approval card. Cannot proceed without click. 24hr timeout. |
| Regulatory (BD comms) | Any retail communication at BD | Principal review queue. Two-person approval. Smarsh archived. |

### 6.2 Streaming Responses

SSE from M6 gateway. Text streams into chat bubble progressively. Structured outputs render incrementally. Leakage scan block mid-stream: stream stops, blocked message replaces content. M2 deny: immediate generic message, no details.

### 6.3 Error Handling

- M2 DENY: "I don't have access to that information." No details. No retry.
- M1 token expired: Redirect to login.
- M11 adapter down: "The [vendor] system is temporarily unavailable."
- Leakage scan BLOCK: "This response was blocked by compliance review."
- Network error: "Connection lost. Reconnecting..." with auto-retry.

### 6.4 Consent and Transparency

First login: granular consent per data category (PII, holdings, trades, plans) with per-category toggle. Each shows what, why, and what happens if declined. Revisitable from Settings. Every agent response shows "Data sources" badge. Provenance chain one click away.

---

## PART 7: DESIGN SYSTEM

Tech: React 18 + TypeScript + Tailwind CSS 4 + Radix UI (headless) + TanStack Query/Table + Recharts + Keycloak JS + SSE + Vite + Vitest + Playwright.

Colors: primary (blue), success (green, ALLOW), danger (red, DENY/BLOCK), warning (yellow, ESCALATE), mnpi-badge (violet). Light + dark mode. Never color-only — always icon + color.

Typography: Inter for UI, JetBrains Mono for hashes/trace IDs/JSON. 14px body, 24px h1.

Accessibility: WCAG 2.1 AA minimum. Keyboard navigable. Screen reader support. Focus management. Reduced motion respect. 200% zoom functional.

---

## PART 8: DATA FLOW

Browser is OUTSIDE the trust boundary. All data reaching the browser has been: (1) authorized by M2, (2) filtered by M4, (3) scanned by Gap 6, (4) logged by M10. UI does NOT make compliance decisions. Auth via Keycloak JS adapter, AID token in memory (not localStorage), all API calls through M6 gateway.

---

## PART 9: IMPLEMENTATION PLAN

| Phase | What | Duration |
|-------|------|----------|
| UI Phase 1 | Chat + Meeting Prep | 3-4 weeks |
| UI Phase 2 | Principal Review Queue + Order Approval | 2-3 weeks |
| UI Phase 3 | Compliance Console | 3-4 weeks |
| UI Phase 4 | Admin Dashboard | 2-3 weeks |
| UI Phase 5 | Mobile responsive + dark mode + accessibility audit | 2-3 weeks |

UI is part of M12 (Agent Runtime). Communicates exclusively through M6 gateway. No direct vendor calls. No cross-module imports. Build, not buy — no off-the-shelf product provides HITL approval workflows for FSI compliance.

---

## PART 10: OPEN QUESTIONS

1. Should chat support file uploads (PDFs for onboarding specialist)?
2. Should principal review queue support batch approve?
3. Should compliance console have export-to-PDF?
4. Dark mode in Phase 1 or Phase 5?
5. Multi-language support for cross-border deployments?
6. Client-facing read-only portfolio summary shared via link?

---

*UIUX-01 — Project 007 FSI Interoperability Platform*
*UI/UX Deep Research, Design, and Architecture*
