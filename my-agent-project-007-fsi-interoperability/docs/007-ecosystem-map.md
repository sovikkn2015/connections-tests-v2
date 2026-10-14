# Project 007 — Where It Lives in the FSI Ecosystem

> Audience: C-Level / Executive Steering Committee
> Purpose: One-page visual positioning of Project 007 in the wealth management / financial services stack
> Format: ASCII — render-anywhere, no dependencies, copy-paste into any deck or email

---

## The Map

```
                         PROJECT 007 — WHERE IT LIVES IN THE FSI ECOSYSTEM
                         ════════════════════════════════════════════════

┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              END USERS  (humans + channels)                          │
│                                                                                      │
│   Advisors   │   Compliance Officers   │   Portfolio Mgrs   │   RIA / BD Operations  │
│      │                │                         │                      │             │
│      ▼                ▼                         ▼                      ▼             │
│   Salesforce FSC   │   Slack / Teams   │   Web / Mobile   │   Email   │   Voice      │
└──────────────────────────────────┬───────────────────────────────────────────────────┘
                                   │  (12+ channels — OpenClaw is channel gateway only)
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                         AGENT LAYER  (reasoning + orchestration)                     │
│                                                                                      │
│    Supervisor  ──►  Research │ Client │ Compliance │ Execution │ Onboarding          │
│                    (Claude Sonnet = research · Claude Haiku = routing/exec)          │
└──────────────────────────────────┬───────────────────────────────────────────────────┘
                                   │  every call — no exceptions
                                   ▼
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                      ║
║      ██████   ██████  ███████     ██████  ██████   ██████  ██   ██    ██             ║
║     ██    ██ ██    ██ ██          ██   ██ ██   ██ ██    ██ ██   ██    ██             ║
║     ██    ██ ██    ██ ███████     ██████  ██████  ██    ██ ███████    ██             ║
║     ██    ██ ██    ██      ██     ██      ██   ██ ██    ██      ██    ██             ║
║      ██████   ██████  ███████     ██      ██   ██  ██████       ██    ██             ║
║                                                                                      ║
║                    PROJECT 007 — FSI INTEROPERABILITY PLATFORM                       ║
║                     "The Trust Layer for AI in Financial Services"                   ║
║                                                                                      ║
║   ┌────────────────────────────────────────────────────────────────────────────┐     ║
║   │                    M6  TRUST-AWARE MCP GATEWAY                             │     ║
║   │           (every agent call passes through — fail-closed)                  │     ║
║   └────────────────────────────────────────────────────────────────────────────┘     ║
║          │            │              │              │             │                 ║
║          ▼            ▼              ▼              ▼             ▼                 ║
║       ┌─────┐      ┌─────┐       ┌───────┐      ┌───────┐     ┌──────┐               ║
║       │ M1  │      │M2/M4│       │  M3   │      │  M7   │     │ M10  │               ║
║       │ ID  │      │ OPA │       │Schema │      │Xlate  │     │Audit │               ║
║       │Auth │      │Policy│      │18 FSI │      │Canon. │     │3-tier│               ║
║       │     │      │MNPI │       │types  │      │norms  │     │ WORM │               ║
║       └─────┘      └─────┘       └───────┘      └───────┘     └──────┘               ║
║      Identity    Authority+      Canonical      Vendor-to-   Langfuse+               ║
║                  MNPI filter     contracts      canonical    S3 Lock+                ║
║                  (Rego only)                                 CRM                     ║
║                                                                                      ║
║                   M8 Pipeline · M9 Intent · M12 Runtime · M13 FIX                    ║
║                   M5 Config  · M11 Adapters (polyglot, 17+ vendors)                  ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
                                   │  MCP over mTLS · canonical schema only
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                       DATA & EXECUTION LAYER  (the vendor zoo)                       │
│                                                                                      │
│  MARKET DATA       CUSTODY / BOOKS      RESEARCH          COMPLIANCE     EXECUTION   │
│  ──────────        ──────────────       ────────          ──────────     ─────────   │
│  Bloomberg BLPAPI  Pershing / NetX      Morningstar       Smarsh         FIX venues  │
│  Refinitiv         Schwab / Fidelity    FactSet           Global Relay   Broker APIs │
│  ICE / S&P         Addepar / Orion      YCharts           MyComplianceO  DTCC        │
│  (17+ adapters across 5 protocols: REST · BLPAPI · gRPC · SFTP · FIX)                │
└──────────────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                      REGULATORY PERIMETER  (the reason 007 exists)                   │
│                                                                                      │
│   SEC Reg BI  ·  FINRA 2210  ·  BSA/AML  ·  ERISA  ·  MNPI / Reg FD  ·  Cross-border │
│   Every action above is logged, policy-checked, and defensible under examination.    │
└──────────────────────────────────────────────────────────────────────────────────────┘


   WHO SITS WHERE (archetype view)
   ──────────────────────────────
     Tier 1 IB     ─┐
     Tier 2 WM     ─┤     all five archetypes plug into the SAME 007 trust layer;
     Tier 3 BD     ─┼──►  only the Helm values file changes (cloud / hybrid / on-prem).
     Tier 4 RIA    ─┤
     Tier 5 FinTech─┘

   THE ONE-LINE PITCH
   ──────────────────
     Agents and LLMs live above 007.  Vendors and regulators live below.
     007 is the compliance-graded wire that lets them talk — without the firm
     ending up on a FINRA enforcement docket.
```

---

## How to Read This Map (90 seconds)

**Top band — End Users and Channels.** Humans (advisors, compliance officers, PMs, ops) reach the system through the channels they already use: Salesforce FSC, Slack, Teams, web, mobile, email, voice. No new UI to learn.

**Second band — Agent Layer.** A supervisor agent routes to five specialists (Research, Client, Compliance, Execution, Onboarding). Claude Sonnet does research-heavy reasoning; Claude Haiku does routing and execution. This is where "AI" happens.

**Middle — Project 007.** Every single agent call passes through M6, the Trust-Aware MCP Gateway. Around M6 sit the trust primitives:
- **M1** verifies agent identity
- **M2/M4** evaluates authority and filters MNPI using OPA/Rego (deterministic, never LLM)
- **M3** defines 18 canonical FSI data types
- **M7** translates vendor data into those canonical types
- **M10** writes a 3-tier WORM audit trail (Langfuse + S3 Object Lock + CRM)

Supporting modules M5, M8, M9, M11, M12, M13 round out pipeline, intent, config, adapters, runtime, and FIX.

**Below 007 — Data and Execution Vendors.** Bloomberg, Refinitiv, Pershing, Schwab, Fidelity, Addepar, Orion, Morningstar, FactSet, Smarsh, Global Relay, FIX venues. 17+ integrations across 5 protocols (REST, BLPAPI, gRPC, SFTP, FIX). Agents never call vendors directly — everything goes through M6.

**Bottom band — Regulatory Perimeter.** SEC Reg BI, FINRA 2210, BSA/AML, ERISA, MNPI / Reg FD, cross-border. This is the reason 007 exists. Every action above is logged and policy-checked so the firm can defend itself under examination.

---

## What the Banner Art Is

The large block-text header inside the 007 box is ASCII banner art spelling the project name. It is generated by the same family of tools as `figlet` / `toilet` — each character is drawn as a 5-row block of solid squares (`█`). Common in CLI tools and terminal READMEs to give the page a visual anchor that survives being pasted into plain-text email, chat, or GitHub issues.

The banner has zero functional meaning; it is purely a visual marker that says "this is the 007 layer."

---

## Why This Diagram Works for Executives

1. **One page, no animation, no colors required.** Renders in email, Slack, GitHub, PDF, a terminal, or a whiteboard photo.
2. **Three actors, clear direction.** Users flow down, vendors flow up, 007 is the toll booth in the middle.
3. **Answers the "so what" in one line:** 007 is the compliance-graded wire between AI and financial data.
4. **Shows the moat.** The trust layer (M1+M2/M4+M6+M10) is visually the largest block — because that is where the defensibility and the regulatory value live.
5. **Archetype-agnostic.** The same picture works for a Tier 1 bank and a Tier 4 RIA; only the Helm values file changes.

---

*Project 007 FSI Interoperability Platform — Executive Ecosystem Map*
