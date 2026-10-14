# FSI Wealth Advisor Agent — Demo Narrative

A standalone story for audiences who have not seen 001, 002, or 003.

**Three beats, in order:** business problem → demo → architecture.

Total runtime: **7–8 minutes**. Four live queries. One architecture slide.

---

## Beat 1 — The business problem *(90 sec)*

**Wealth advisors spend 60–70% of their time on prep work, not on clients.**

Before a single client meeting, an advisor typically opens 6–8 tabs:

- CRM for household and client profile
- Portfolio system for balances and allocations
- Goal-planning tool for retirement targets
- Trading system for recent transactions
- Compliance dashboard for suitability checks
- Referral tracker to remember who introduced the client

Each system has a different login, a different query language, and a different view of "the client." The advisor stitches it together in their head, then walks into the meeting.

Three things go wrong because of this:

1. **Advisors lose billable hours to data gathering** — a $2M book of business can support maybe 40 meaningful client conversations a year; prep eats a third of that capacity.
2. **Compliance risk sits in the gap between systems** — a portfolio that drifted past the suitability threshold on Tuesday doesn't show up in the CRM on Wednesday.
3. **Newer advisors can't scale senior playbooks** — the judgment lives in the head of the top 10% of the firm, not in the tools.

Firms have been trying to fix this with dashboards for 15 years. Dashboards don't work because the advisor still has to know *which question to ask*. What they want is to type a sentence and get an answer.

**That's what this is:** a **Salesforce Agentforce** agent for wealth advisors that speaks natural language, grounds its answers in the firm's actual data, and logs every interaction for compliance. One screen, many systems — built on the platform the firm already trusts for CRM.

---

## Beat 2 — The live demo *(4 min)*

Open the React frontend. Four queries, four capabilities. Don't narrate while typing — let the agent respond, then call out what just happened.

**Query 1 — "Tell me about the Johnson household"**
> Grounded retrieval. Agentforce pulled from the firm's system of record through Data Cloud. Nothing invented, nothing from the LLM's memory.

**Query 2 — "Does Sarah Johnson need rebalancing?"**
> Deterministic business logic on top of the grounded data. A 5% drift threshold applied in Apex, not in prose. This is the part you couldn't do with a generic chatbot.

**Query 3 — "Show me recent transactions for Wei Chen"**
> A different client, a different data source, same interface. One screen, many systems.

**Query 4 — "Is the Patel account compliant?"**
> A compliance check — 15% drift and 80% concentration thresholds. This is the output that used to require a human compliance officer.

After the fourth query, pause and say:

> *"Everything you just saw was logged. Every query, every user, every client record touched. The compliance team has a full audit trail without the advisor having to do anything extra."*

That transition sets up the architecture beat.

---

## Beat 3 — How it works *(2 min, one architecture slide)*

**This runs on Salesforce Agentforce.** Three layers sit on top of the platform, top to bottom.

**Conversation layer — Agentforce topic selector.** The LLM reads the advisor's sentence and picks one of 10 topics (client lookup, portfolio, goals, meeting prep, rebalancing, transactions, compliance, referrals, escalation, off-topic). That's all the LLM does. It never touches data. Topics are defined in Agentforce's declarative builder — no prompt engineering, no fine-tuning.

**Business logic layer — Agentforce invokable Apex actions.** 8 deterministic Apex classes, one per topic. These run the actual calculations — drift, concentration, suitability. Same answer every time for the same input. When a regulation changes, you update an Apex threshold. No model retraining.

**Data layer — Salesforce Data Cloud.** Every Apex action queries Data Cloud through `ConnectApi.CdpQuery`, which unifies 8 source systems into one semantic model across 7 DLMs. The CRM is the source of truth; Data Cloud is the lens the agent looks through.

Cross-cutting, and the reason this survives compliance review — all of it comes from the platform:

- **Audit logging** — every interaction writes an immutable record to `WA_Audit_Log__c` with user, timestamp, query, client accessed, and response summary
- **Role-based access** — Salesforce sharing rules and permission sets; advisors see their book, compliance sees everyone; the agent inherits the advisor's session permissions via `with sharing`
- **Knowledge grounding** — Salesforce Knowledge articles inform responses, not just transactional data
- **External data via MCP** — market quotes, financial news, internal compliance checks are exposed as Model Context Protocol tools, not baked into the model
- **Performance-tested** — load-tested with published SLA tiers for concurrent advisors
- **Three Agentforce deployment channels** — Experience Cloud web chat, Salesforce Mobile, and Slack, all backed by the same agent definition

One line to remember:

> *"Agentforce routes. Apex runs. Data Cloud grounds."*

That sentence is the answer to the three questions every compliance officer will ask:

- *How do you prevent hallucination?* → The LLM never generates numbers. Agentforce routes; Apex answers.
- *How do you prove what happened?* → Every Agentforce invocation is logged with SOC-2-grade detail.
- *How do you handle a new regulation?* → You change the Apex action, not the model.

Close with:

> *"This isn't a proof of concept. It's 10 Agentforce topics, 8 Apex actions, 7 Data Cloud DLMs, full audit, and three deployment channels. The platform is doing the heavy lifting — we wrote the domain logic."*

---

## Demo mechanics

**Run order for live queries:** Johnson lookup → Sarah rebalancing → Wei Chen transactions → Patel compliance. Four is the right number. Ten is too many — the audience stops listening after six.

**Warm the agent** with one throwaway query before the session starts. Cold starts add 8–10 seconds and kill the rhythm.

**Fallback order if anything breaks:**

1. Switch to Agentforce Agent Builder Preview inside the org — zero setup, still looks credible
2. Play the pre-recorded video in `004-V2-videos/` — zero risk

---

## Questions to expect, and the one-line answer for each

| Question | Answer |
|---|---|
| Can it hallucinate a client? | No. Agentforce only routes to a topic; the data comes from deterministic Apex queries against Data Cloud. |
| What happens when a regulation changes? | Update the Apex action's threshold. No model retraining. |
| How do you handle a client that doesn't exist? | Fuzzy matching with a graceful "I don't have that client" fallback, logged. |
| Why not just use ChatGPT? | ChatGPT doesn't have your data, your audit log, or your CRM permissions. Agentforce inherits all three from Salesforce. |
| Why Agentforce over a custom LLM app? | Audit, RBAC, and Data Cloud wiring come with the platform. We'd spend 6 months rebuilding what Salesforce ships. |
| What data did you train the model on? | None. The model is off-the-shelf. All firm-specific knowledge lives in Data Cloud and the Apex actions. |
| How do you handle PII? | Field-level security and sharing rules in Salesforce; the Agentforce session inherits the advisor's permissions. |
| What if the data is wrong? | The agent is a lens on the CRM via Data Cloud. If the CRM is wrong, the agent is wrong — and so is every other tool the firm uses. |
