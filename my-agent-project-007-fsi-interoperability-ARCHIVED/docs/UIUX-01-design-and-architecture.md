# UIUX-01: UI/UX Design and Architecture — Project 007 FSI Interoperability Platform

> Date: April 16, 2026
> Version: 1.0
> Category: DESIGN (UI/UX)
> Predecessor: ARCH-09 (module map), ARCH-07 (tech stack), 007-consolidated-design-and-plan
> Purpose: Single source of truth for everything frontend — the UI/UX equivalent of ARCH-09
> Status: DESIGN PHASE — no code. Ready for a design team to execute from.

---

## Context

Project 007 has 13 backend modules, 454+ tests, and zero UI. The architecture specifies M12 OpenClaw as the channel gateway handling 12+ channels (Slack, Teams, WhatsApp, Web). This document designs the Web channel — a full browser-based application that surfaces the entire platform to five distinct user personas across five enterprise archetypes.

The backend is built. The trust layer works. The compliance engine evaluates 2,100+ Rego rules. The adapters connect 17+ vendor systems. What's missing is the glass — the surface through which humans interact with all of it.

This document covers: competitive analysis, user personas, information architecture, screen inventory, interaction patterns, design system, tech stack, security model, and implementation plan.

---

---

# PART 1: COMPETITIVE LANDSCAPE AND RESEARCH

> What the 5 main competitors do in UI/UX, and what 007 must do differently.

---

## 1.1 Envestnet / Tamarac

**Market position:** 110,000+ advisors, $6.5T in assets, $1B R&D investment over 5 years.

**Recent UI work (2025-2026):**
- Redesigned mobile client portal with responsive design principles
- Holdings and net worth pages feature locked first-column tables for horizontal scrolling — a pattern 007 should adopt for any wide financial data table
- Report Studio added drag-and-drop grouping for custom report layouts
- Billing UI refresh with clearer fee schedule visualization
- Persona-aware navigation: advisors, operations staff, and clients see different views

**Strengths:**
- Mature advisor workflows refined over 15+ years of RIA/BD usage
- Trading oversight UI with model portfolio rebalancing visualization
- Integrated billing, reporting, and portfolio management in one screen
- Data aggregation via Yodlee gives a "whole picture" view of client assets

**Weaknesses:**
- No AI agent chat interface — the conversational AI announced in 2026 is platform-specific, not cross-system
- No cross-system intelligence — Envestnet shows Envestnet data, not Salesforce + Orion + eMoney unified
- No compliance layer UI — advisors cannot see what was filtered or why
- No HITL approval workflows native to the UI — principal review is a separate process
- Tier 3/4 only — no hedge fund pod isolation, no investment bank Chinese walls

**What 007 learns:** Locked-column tables for holdings. Persona-aware navigation. Mature rebalancing UX. Report grouping patterns.

---

## 1.2 Orion / Denali AI

**Market position:** #1 portfolio accounting platform, AI copilot for advisors (Denali AI launched 2025).

**UI characteristics:**
- Portfolio-centric views: holdings, performance attribution, tax lot management
- Performance dashboards with benchmark comparison and time-weighted return charts
- Denali AI provides a conversational overlay for portfolio queries
- Clean data tables with sortable columns and export functionality

**Strengths:**
- Best-in-class portfolio data visualization — performance attribution charts, sector allocation donuts, risk/return scatter plots
- Deep drill-down from household to account to holding to tax lot
- Advisor dashboard with AUM summary, alerts, and task list
- Webhooks for real-time data updates

**Weaknesses:**
- No compliance layer UI — no visibility into what data was filtered or why
- No multi-vendor view — shows Orion data only, not Salesforce CRM or eMoney planning data alongside
- Denali AI is Orion-scoped — cannot answer questions that require data from other systems
- No principal review queue — BD compliance workflows are external
- No research pipeline visualization — no 23-stage progress tracking

**What 007 learns:** Performance attribution chart patterns. Tax lot drill-down UX. Household-to-holding navigation hierarchy. AUM summary dashboard layout.

---

## 1.3 Salesforce Financial Services Cloud

**Market position:** CRM market leader, Agentforce integration (2025-2026), Einstein Trust Layer.

**UI characteristics:**
- Relationship model visualization: client → household → accounts → holdings
- Activity timeline showing all interactions (calls, emails, meetings, tasks)
- Einstein AI provides inline recommendations and next-best-action prompts
- Lightning Design System (LDS) — mature, accessible component library
- Agentforce chat panel embedded in the CRM sidebar

**Strengths:**
- Relationship model UI is the gold standard — household visualization with role-based relationships (primary, spouse, dependent, trustee)
- Activity timeline pattern — chronological view of all client interactions across channels
- Einstein AI integration is seamless — recommendations appear inline, not in a separate window
- Permission-aware rendering — field-level security (FLS) hides fields the user cannot see
- Mobile-first responsive design via Lightning Web Components

**Weaknesses:**
- No custodian data — cannot show Schwab positions, Fidelity balances, or Orion performance alongside CRM data
- No MNPI filtering UI — Einstein Trust Layer masks PII but doesn't show the advisor what was filtered or provide audit trail visibility
- Locked to Salesforce ecosystem — cannot display data from Orion, eMoney, Bloomberg, or any non-Salesforce system
- No research pipeline — no SEC filing analysis, no 23-stage research workflow
- No execution capability — cannot submit trades or track order lifecycle

**What 007 learns:** Relationship model visualization. Activity timeline pattern. Inline AI recommendations (not a separate window). Permission-aware field rendering. Lightning Design System accessibility patterns.

---

## 1.4 AdvisorEngine

**Market position:** Recently unveiled reimagined Client Portal with human-centered design principles.

**UI characteristics:**
- Clean, modern interface with generous whitespace
- Client-first navigation — everything organized around the client relationship
- Simplified portfolio views with clear performance summaries
- Document vault with drag-and-drop upload
- Goal tracking with visual progress indicators

**Strengths:**
- Human-centered design philosophy — reduced cognitive load, clear visual hierarchy
- Intuitive client engagement — clients can self-serve for basic portfolio views and document access
- Onboarding workflow with step-by-step progress indicators
- Mobile-responsive with touch-friendly interaction targets

**Weaknesses:**
- Limited to AdvisorEngine ecosystem — no cross-system data
- No AI agent interface — no conversational interaction
- No compliance visibility — no audit trail, no MNPI indicators
- No BD-specific workflows — no principal review, no FINRA 2210 queue
- No research or execution capabilities

**What 007 learns:** Human-centered design principles. Generous whitespace. Goal tracking progress indicators. Onboarding step-by-step UX. Document vault pattern.

---

## 1.5 Wealthbox / Redtail

**Market position:** Small RIA CRMs, known for simplicity and fast adoption.

**UI characteristics:**
- Wealthbox: social-media-inspired activity feed, clean card-based layout, minimal learning curve
- Redtail: traditional CRM with contact management, calendar, workflow automation
- Both prioritize speed of data entry over depth of visualization
- Mobile apps with core CRM functionality

**Strengths:**
- Simplicity — advisors can be productive within hours, not weeks
- Fast adoption — minimal training required
- Activity feed pattern (Wealthbox) — social-media-style updates on client activity
- Workflow automation with visual builders (Redtail)
- Affordable — accessible to solo practitioners and small RIAs

**Weaknesses:**
- No compliance layer — no MNPI filtering, no audit trail, no principal review
- No multi-system integration — CRM data only, no portfolio, no planning, no custodian
- No AI agent — no conversational interface, no research pipeline
- Limited visualization — basic charts, no performance attribution, no risk analytics
- Not suitable for BD or institutional use

**What 007 learns:** Activity feed pattern for client updates. Card-based layouts for quick scanning. Minimal learning curve as a design goal. Fast data entry patterns.

---

## 1.6 What 007's UI Must Do Differently

The competitive analysis reveals four capabilities that NO competitor provides:

### Differentiator 1: Unified Cross-System View
Show data from 20+ vendor systems in one screen. A client detail page shows Salesforce CRM data, Orion portfolio data, eMoney planning data, and Schwab custodian data — color-coded by source, reconciliation status visible. No competitor does this.

### Differentiator 2: Trust and Compliance Visibility
Show the advisor WHAT was filtered and WHY. Every data element displays its source system, its MNPI filter status, and a link to its audit trail entry. The advisor sees "[FILTERED]" placeholders with tooltips explaining the compliance rule that triggered filtering. No competitor shows this.

### Differentiator 3: HITL Approval Workflows Native to the UI
Order approval, principal review, and compliance escalation are first-class UI patterns — not external processes. Approve/Reject/Escalate with SHA-256 tokens, SLA timers, and full audit trail. Built into the same interface the advisor uses for everything else.

### Differentiator 4: Principal Review Queue for BDs
A dedicated queue for FINRA 2210 principal review — every BD communication that requires review before delivery. Filterable by advisor, client, communication type, risk level. With one-click approve/reject and automatic Smarsh archiving. No competitor has this as a native UI component.



---

---

# PART 3: INFORMATION ARCHITECTURE

> Complete sitemap, navigation structure, role-based access, backend module mapping.

---

## 3.1 Top-Level Navigation

The application uses a persistent left sidebar for primary navigation. The sidebar collapses to icons on smaller screens. Navigation items are role-filtered — users only see sections they have access to.

```
┌─────────────────────────────────────────────────────────────────┐
│  ┌──────────┐  ┌─────────────────────────────────────────────┐  │
│  │ SIDEBAR  │  │              MAIN CONTENT                   │  │
│  │          │  │                                             │  │
│  │ 🏠 Dash  │  │  [Header Bar: Search | Notifications | User]│  │
│  │ 💬 Chat  │  │  ─────────────────────────────────────────  │  │
│  │ 👥 Clients│  │                                             │  │
│  │ 📊 Port  │  │           Page Content Area                 │  │
│  │ 🔬 Research│ │                                             │  │
│  │ ⚖️ Comply│  │                                             │  │
│  │ 📋 Execute│  │                                             │  │
│  │ 📝 Onboard│ │                                             │  │
│  │ ⚙️ Admin │  │                                             │  │
│  │          │  │                                             │  │
│  │ ──────── │  │                                             │  │
│  │ 🟢 Health│  │                                             │  │
│  │ 👤 Profile│ │                                             │  │
│  └──────────┘  └─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3.2 Navigation Sections — Detail

### Dashboard (Home)
- **URL:** `/dashboard`
- **Who sees it:** All authenticated users
- **What it shows:** Personalized by role — advisor sees client alerts + AUM + meetings; compliance officer sees review queue count + alert count; ops manager sees system health + onboarding pipeline; admin sees module status + policy changes; HF PM sees pod P&L + risk exposure
- **Backend modules:** M6 (gateway) → M11 (adapters for portfolio/CRM data), M10 (recent audit entries), M2 (compliance alert counts)
- **MNPI filtering:** Dashboard data passes through M4. Tier 5 HF sees sector exposure percentages, not position details. Tier 3 BD advisor sees own clients only.

### Chat (AI Agent)
- **URL:** `/chat` (also available as slide-over panel from any screen via keyboard shortcut)
- **Who sees it:** All authenticated users
- **What it shows:** Conversational interface with the 007 AI agent. Structured response cards for meeting prep, portfolio summary, research brief. Provenance indicators showing which systems contributed data. MNPI filter indicators on every response.
- **Backend modules:** M12 (OpenClaw WebSocket), M9 (intent router), all specialists via M6
- **MNPI filtering:** Every AI response is MNPI-filtered by M4 before reaching the browser. Filtered fields show "[FILTERED]" with tooltip.

### Clients
- **URL:** `/clients` (list), `/clients/:id` (detail), `/clients/:id/household` (household view)
- **Who sees it:** Advisors, compliance officers, operations managers
- **What it shows:** Client list with search/filter. Client detail with unified cross-system profile. Household view with container model showing vendor-specific groupings.
- **Backend modules:** M6 → M11-REST (Salesforce FSC for CRM, Orion for portfolio, Schwab for custodian), M7 (schema translation to canonical Client/Household types)
- **MNPI filtering:** SSN, DOB stripped for all roles. Full holdings visible for Tier 4 RIA advisors. Sector exposure only for Tier 5 HF. Compliance officers see compliance history but not portfolio values.

### Portfolio
- **URL:** `/portfolio` (overview), `/portfolio/holdings` (holdings), `/portfolio/performance` (performance), `/portfolio/tax-lots` (tax lots), `/portfolio/rebalancing` (rebalancing)
- **Who sees it:** Advisors, HF PMs (pod-isolated)
- **What it shows:** Holdings with source attribution and cost basis method. Performance with benchmark comparison. Tax lot detail with cost basis normalization. Rebalancing proposals.
- **Backend modules:** M6 → M11-REST (Orion, Schwab, Fidelity), M7 (canonical Holding, TaxLot, Performance types), M3 (schema validation)
- **MNPI filtering:** Tier 5 HF sees sector percentages only (no individual positions). Tier 4 RIA sees full holdings. Cost basis method always displayed (never null per M3 schema). Tier 3 BD: Reg BI documentation auto-generated for any recommendation.

### Research
- **URL:** `/research` (pipeline list), `/research/:id` (pipeline detail), `/research/briefs` (completed briefs), `/research/filings` (SEC filings)
- **Who sees it:** Advisors, HF PMs, research analysts
- **What it shows:** Research pipeline status (23 stages), HITL gate indicators, completed research briefs with source attribution, SEC filing search.
- **Backend modules:** M8 (pipeline engine), M6 → M11-REST (SEC EDGAR, news APIs, market data), M9 (intent classification for research queries)
- **MNPI filtering:** Research briefs are MNPI-scanned by Gap 6 (3-layer: regex + NER + Haiku) before delivery. Source attribution preserved. Tier 5 HF: pod-isolated research — PM sees only own pod's research.

### Compliance
- **URL:** `/compliance` (dashboard), `/compliance/review-queue` (principal review), `/compliance/audit-trail` (audit viewer), `/compliance/alerts` (alert list), `/compliance/restricted-list` (restricted securities)
- **Who sees it:** Compliance officers (full access), advisors (own compliance history only), admins (policy view)
- **What it shows:** Principal review queue (FINRA 2210), compliance alerts with severity and rule reference, audit trail viewer (3-tier), restricted list management, Reg BI documentation viewer.
- **Backend modules:** M2/M4 (OPA policy evaluation), M10 (audit trail — Langfuse + S3 WORM + CRM), Gap 1 (Reg BI), Gap 3 (WSP-to-YAML), Gap 4 (BSA/AML), Gap 6 (MNPI leakage scan results)
- **MNPI filtering:** Compliance officers see compliance metadata (rule triggered, action taken, timestamp) but NOT the underlying client financial data unless their role grants it. Audit trail entries show what was filtered but not the filtered values.

### Execution
- **URL:** `/execution` (order book), `/execution/approval` (approval queue), `/execution/settlement` (settlement tracker)
- **Who sees it:** Advisors (own orders), HF PMs (pod orders), compliance officers (all orders for review)
- **What it shows:** Order book with state machine visualization (DRAFT → COMPLIANCE_CHECK → PENDING_APPROVAL → APPROVED → SUBMITTED → CONFIRMED → PENDING_SETTLEMENT → SETTLED). HITL approval screen. Settlement tracker with T+1 status.
- **Backend modules:** Execution specialist (state machine), M6 → M13 (FIX Bridge for broker execution), M2 (pre-trade compliance check), M10 (audit every state transition)
- **MNPI filtering:** Order details visible only to the submitter, their compliance officer, and the approver. Tier 5 HF: pod-isolated — PM sees only own pod's orders. No autonomous trades — HITL mandatory.

### Onboarding
- **URL:** `/onboarding` (pipeline), `/onboarding/:id` (workflow detail)
- **Who sees it:** Operations managers, advisors (own clients), compliance officers (compliance review gate)
- **What it shows:** Multi-step onboarding workflow: collect info → KYC → sanctions screening → risk profile → account opening → DocuSign → compliance review (HITL). Progress indicators per step. DocuSign status integration.
- **Backend modules:** Onboarding specialist (workflow engine), M6 → M11-REST (Salesforce for CRM, custodians for account opening), Gap 4 (BSA/AML for KYC/sanctions), M10 (audit)
- **MNPI filtering:** KYC data (SSN, DOB, address) visible only to operations staff with KYC role. Advisors see onboarding status but not KYC details. Compliance officers see sanctions screening results.

### Admin
- **URL:** `/admin` (console), `/admin/users` (user management), `/admin/policies` (OPA policies), `/admin/adapters` (adapter config), `/admin/health` (system health), `/admin/config` (enterprise config)
- **Who sees it:** Firm administrators only
- **What it shows:** User provisioning and role management. OPA policy dashboard with WSP mapping. Adapter configuration and health. System health for all 13 modules. Enterprise config editor with validation.
- **Backend modules:** M1 (identity/Keycloak), M2 (OPA policy management), M5 (enterprise config), M6 (gateway health), M10 (platform-wide audit), M11 (adapter health)
- **MNPI filtering:** Admin sees system configuration and health but NOT client data. Admin role does not grant access to client portfolios or compliance review queues.

---

## 3.3 Role-Based Navigation Matrix

| Section | RIA Advisor | BD Advisor | BD Compliance | HF PM | Ops Manager | Admin |
|---------|:-----------:|:----------:|:-------------:|:-----:|:-----------:|:-----:|
| Dashboard | ✅ (advisor) | ✅ (advisor) | ✅ (compliance) | ✅ (HF) | ✅ (ops) | ✅ (admin) |
| Chat | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Clients | ✅ (own) | ✅ (own) | ✅ (all) | ❌ | ✅ (all) | ❌ |
| Portfolio | ✅ (full) | ✅ (full) | ❌ | ✅ (pod, filtered) | ❌ | ❌ |
| Research | ✅ | ✅ | ❌ | ✅ (pod) | ❌ | ❌ |
| Compliance | ✅ (own history) | ✅ (own history) | ✅ (full) | ✅ (pod history) | ❌ | ✅ (policy only) |
| Execution | ✅ (own) | ✅ (own) | ✅ (all, review) | ✅ (pod) | ❌ | ❌ |
| Onboarding | ✅ (own clients) | ✅ (own clients) | ✅ (review gate) | ❌ | ✅ (full) | ❌ |
| Admin | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## 3.4 URL Structure

```
/                           → Redirect to /dashboard
/login                      → Keycloak login (redirect)
/dashboard                  → Personalized dashboard
/chat                       → AI chat (full page)
/clients                    → Client list
/clients/:clientId          → Client detail
/clients/:clientId/household → Household view
/portfolio                  → Portfolio overview
/portfolio/holdings         → Holdings table
/portfolio/performance      → Performance charts
/portfolio/tax-lots         → Tax lot detail
/portfolio/rebalancing      → Rebalancing proposals
/research                   → Research pipeline list
/research/:pipelineId       → Pipeline detail (23 stages)
/research/briefs            → Completed research briefs
/research/filings           → SEC filing search
/compliance                 → Compliance dashboard
/compliance/review-queue    → Principal review queue (FINRA 2210)
/compliance/audit-trail     → Audit trail viewer
/compliance/alerts          → Compliance alert list
/compliance/restricted-list → Restricted securities
/execution                  → Order book
/execution/approval         → Order approval queue (HITL)
/execution/settlement       → Settlement tracker
/onboarding                 → Onboarding pipeline
/onboarding/:workflowId    → Workflow detail
/admin                      → Admin console
/admin/users                → User management
/admin/policies             → OPA policy dashboard
/admin/adapters             → Adapter configuration
/admin/health               → System health
/admin/config               → Enterprise config editor
```

