# 005/006: Commercial Value, Market Landscape, and Real Business Problems

> Date: April 8, 2026
> Sources: AlphaSense, Hebbia, Brightwave, Cerulli Associates, McKinsey, FINRA 2026 Oversight Report, Deloitte, WealthManagement.com, Finantrix, BankingDive, Goldman Sachs
> Content was rephrased for compliance with licensing restrictions.

---

## What's Actually Available in the Market Right Now

The FSI AI research space is not empty. There are well-funded, production-grade commercial platforms:

- [AlphaSense](https://www.alpha-sense.com/) ($4B+ valuation) — 500M+ premium documents, AI-powered search across filings, transcripts, expert interviews. Recently launched autonomous AI Agent Interviewer that conducts channel checks. Custom AI agents for workflow automation. Enterprise-grade, fully cited outputs.

- [Hebbia](https://openai.com/index/hebbia/) ($700M valuation, backed by Thiel, a16z) — Claims to automate 90% of finance and legal work. Deep research across offline data. Used by major PE firms and banks.

- [Brightwave](https://www.brightwave.io/) ($21M raised) — AI research platform for buy-side. Knowledge graph from SEC filings, transcripts, news. Research agents that autonomously surface risks and contradictions. Every claim traced to source document, page, paragraph.

- Kensho (S&P Global) — NLP across filings and transcripts. Integrated into Capital IQ.

- [FilingsIQ.ai](https://www.financialcontent.com/article/abnewswire-2026-3-13-filingsiqai-launches-ai-powered-sec-filings-analysis-platform-for-rias-and-investment-analysts) — SEC filings analysis for RIAs. Reads 10-K/10-Q, populates models, generates client memos.

These tools are real, in production, and used by institutional investors today.

---

## What 005 and 006 Do That These Don't

The individual capabilities (search filings, analyze sentiment, run DCF, generate briefs) are not unique. AlphaSense and Brightwave do most of this. What's different is the integration pattern:

### 1. CRM-Connected Agent Loop

None of the commercial tools above are deeply integrated with Salesforce CRM. They're standalone research platforms. An analyst uses AlphaSense to research, then manually copies findings into Salesforce. 005/006 close that loop — the agent reads client holdings from CRM, factors them into the research, writes the brief back to CRM, and logs the audit trail. The research is personalized to the client book, not generic.

### 2. Compliance-Native from Day One

AlphaSense and Brightwave don't know about your restricted list, your MNPI flags, your trading windows, or your client concentration limits. 005/006 check compliance before every action because they're connected to the compliance data in Salesforce. FINRA 2026 explicitly requires AI agents to be supervised like human employees — these systems build that supervision into the workflow.

### 3. Action Execution (006 Only)

Research platforms tell you what to do. 006 can actually do it — submit trades via MuleSoft, initiate wires, run KYC screening, open accounts — all with HITL approval gates. The gap between "here's a research brief recommending you trim NVDA" and "I've submitted the order to trim NVDA, pending your approval" is where real operational value lives.

### 4. Multi-Channel Reach (006 Only)

No commercial research platform lets an advisor ask "prep me for my meeting with Henderson tomorrow" via WhatsApp at 6am and get a personalized brief with portfolio performance, holdings requiring discussion, and compliance notes. That's a channel + CRM + research integration that doesn't exist as a product.

---

## The Real Business Problems

These aren't architectural problems. They're people problems with dollar signs.

### The Advisor Capacity Crisis

$124 trillion is transferring from boomers to heirs through 2048 ([Cerulli Associates](https://www.kaplanfinancial.com/resources/for-businesses/great-wealth-transfer)). The industry faces a shortage of 100,000+ advisors ([McKinsey via Fortune](https://fortune.com/article/wealth-management-shortage/)). Only 44% of advisors feel prepared for the wealth transfer ([American Banker](https://www.americanbanker.com/news/with-trillions-in-motion-just-44-of-advisors-feel-prepared)).

The average advisor spends 5.3 hours/week preparing for meetings, 6.6 hours on financial planning work, and 6 hours on follow-through servicing ([WealthManagement.com](https://www.wealthmanagement.com/business-planning/how-manage-your-firm-s-data-instead-drowning-it)). That's ~18 hours/week on work an agent could compress to minutes.

Automated meeting prep alone drops from 45-90 minutes to 5-10 minutes per client ([Finantrix](https://www.finantrix.com/articles/how-to-automate-client-meeting-preparation-reports-notes-tasks)).

With 100,000 fewer advisors than needed, the only way to serve the wealth transfer is to make each advisor 3-5x more productive.

### The Research Analyst Squeeze

Wall Street is cutting headcount — Goldman forecasts 11% reduction within three years ([Business Insider](https://www.businessinsider.com/ai-impact-job-losses-layoffs-productivity-cost-cutting-goldman-sachs-2025-10)). Analysts routinely spend hours manually reading 10-K filings, copy-pasting into notes, writing memos ([FilingsIQ](https://www.financialcontent.com/article/abnewswire-2026-3-13-filingsiqai-launches-ai-powered-sec-filings-analysis-platform-for-rias-and-investment-analysts)).

Fewer analysts covering the same universe means each analyst needs to produce more research, faster, without sacrificing quality. A 23-stage pipeline that turns "deep dive on NVIDIA" into a verified, compliance-screened brief in minutes instead of days is the difference between covering 15 stocks and covering 40.

### KYC/AML Cost

Average KYC review costs $1,500-$3,500 per client. Large banks spend up to $35 million annually onboarding 10,000 new clients ([BankingDive](https://www.bankingdive.com/spons/transforming-customer-onboarding-leveraging-agentic-process-automation-for/759575/)). Firms spend $72.9 million annually on AML/KYC operations ([Zigment](https://zigment.ai/blog/automated-kyc-verification-ai-powered-assistance)).

Automated KYC can cut verification costs by 70% and time from days to under 30 seconds for low-risk clients ([Lorikeet](https://www.lorikeetcx.ai/articles/kyc-automation-fintech)).

### FINRA 2026 Compliance Cost

FINRA now explicitly addresses agentic AI — systems that initiate and complete multi-step operational tasks. They require documented governance programs, testing and monitoring controls, cybersecurity safeguards, and appropriate oversight mechanisms ([Debevoise](https://www.debevoise.com/insights/publications/2025/12/finras-2026-regulatory-oversight-report-continued)).

Every firm deploying AI agents needs audit trails, HITL checkpoints, and explainability. Building this into the agent from day one (as 005/006 do) is cheaper than retrofitting it onto a commercial tool that wasn't designed for it.

---

## The Commercial Value Proposition

The commercial value isn't "we built a better AlphaSense." It's "we built the integration layer that connects research intelligence to CRM data, compliance controls, and action execution — so the advisor never leaves the workflow."

Specifically:

- An advisor with 005/006 can serve 3-5x more clients with the same quality of personalized service — directly addressing the 100,000-advisor shortage
- A research team can cover 2-3x more stocks with the same headcount — directly addressing the analyst squeeze
- KYC onboarding drops from days/$3,500 to minutes/$500 for low-risk clients
- FINRA compliance is built-in, not bolted-on — every action audited, every decision explainable, every HITL gate logged

---

## Why Build vs Buy

An enterprise would build this (rather than buy AlphaSense + Brightwave + a compliance tool + a CRM integration) because:

1. No commercial product integrates research + CRM + compliance + action execution in a single agent loop. You'd need to stitch together 4-5 vendors, each with their own data model, auth, and audit trail.

2. The compliance requirements are firm-specific. Your restricted list, your MNPI policies, your trading windows, your concentration limits — these are unique to your firm. A commercial tool can't enforce them without deep CRM integration.

3. The $124T wealth transfer is a competitive moat question. The firms that can serve 3x more clients per advisor with personalized, compliant service will capture the assets. The firms that can't will lose them to firms that can.

4. Vendor lock-in risk. Building on open-source (006) or on platforms you already own (005 on Salesforce + AWS) means you control the roadmap. If AlphaSense raises prices or gets acquired, you're not dependent.

---

## The Honest Caveat

If a firm only needs research intelligence without CRM integration or action execution, AlphaSense or Brightwave is the better choice. They're production-grade, battle-tested, and don't require a 10-week build.

005/006 only make sense when the integration — research connected to client data connected to compliance connected to execution — is the value. The moment you need the agent to know that Client Henderson holds 5,000 shares of NVDA, that NVDA is on the restricted list, that Henderson's portfolio is over-concentrated in tech, and that the compliance officer needs to approve any trade recommendation before it goes out — that's when a standalone research tool stops being enough and an integrated agent system becomes necessary.

---

## Summary: What Each Project Uniquely Delivers

| Capability | AlphaSense / Brightwave | 005 (Agentforce + Strands) | 006 (OpenClaw + SF + AWS) |
|-----------|------------------------|---------------------------|--------------------------|
| SEC filing analysis | Yes | Yes | Yes |
| Earnings transcript NLP | Yes | Yes | Yes |
| Financial modeling (DCF, comps) | Partial | Yes | Yes |
| CRM-connected research | No | Yes (native) | Yes (via REST API) |
| Client-personalized briefs | No | Yes | Yes |
| Compliance screening (restricted list, MNPI, trading windows) | No | Yes (Apex-enforced) | Yes (prompt-based) |
| Audit trail (FINRA) | No | Yes (native) | Yes (dual: Langfuse + SF) |
| Action execution (trades, wires, KYC) | No | No | Yes (MuleSoft + HITL) |
| Multi-channel (WhatsApp, Telegram, Discord) | No | No | Yes (12+ channels) |
| Structured research pipeline (23-stage) | No | No | Yes (AutoResearchClaw) |
| Cross-run learning | No | No | Yes (MetaClaw) |
| Persistent per-user memory | No | No | Yes |
| Anti-fabrication with source tracing | Partial (Brightwave) | No | Yes (pipeline-native) |
| Production-ready today | Yes | Prototype | Prototype |
