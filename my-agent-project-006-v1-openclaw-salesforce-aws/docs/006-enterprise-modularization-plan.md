# Project 006: Enterprise Modularization & Production Readiness Plan

> Date: April 12, 2026
> Goal: Transform 006 from a working prototype into a modular, parameterized, enterprise-pluggable platform
> Approach: Autonomous execution via parallel subagents, minimal human intervention
> Available infrastructure: Salesforce CLI (authenticated), AWS CLI (authenticated), SAM CLI, Finch, Python 3.10, Node 25, Bedrock (Claude Sonnet 4.6 + Haiku 4.5)

---

## The Core Problem

006 today is a monolith pretending to be modular. The pipeline is 1,400 lines of hardcoded stages. The skills are tightly coupled to specific APIs (Alpha Vantage, Tavily, SEC EDGAR). The Salesforce objects are hardcoded field names. If an enterprise uses Bloomberg instead of Alpha Vantage, or has a different compliance system, or uses a different OMS — they'd have to rewrite, not reconfigure.

The ask: make it so Enterprise A plugs in Bloomberg + Charles River OMS + their Salesforce org, and Enterprise B plugs in Refinitiv + Fidessa + their Salesforce org — same platform, different connectors.

That means the architecture needs to shift from "a pipeline that calls specific tools" to "a configurable framework where the pipeline stages, data sources, compliance rules, execution targets, and channel configs are all declared, not coded."

OpenClaw already has this pattern. Skills are SKILL.md files — markdown config, not compiled code. MCP servers are pluggable via `openclaw.json`. Channels are YAML configs. The problem is that 006's pipeline.py bypasses all of this and hardcodes everything.

---

## Do We Need to Build a Pipeline?

No. We need to build a platform.

The pipeline already exists and works. What's missing is the abstraction layer that makes it enterprise-configurable. The pipeline should be the engine; the enterprise provides the fuel (data sources, compliance rules, execution targets, CRM schema).

---

## Iteration Roadmap: Prototype → Enterprise Production

### Iteration 1: "It actually runs end-to-end" (2-3 weeks, 1-2 engineers)

The gap between "works locally" and "works on AgentCore with real channels."

- Run the full 23-stage pipeline end-to-end with real HITL gates (not auto-approved)
- Connect at least Slack with real tokens, verify pipeline notifications deliver
- Run the full 150-query eval suite, establish baseline scores
- Record performance measurements (latency per stage, cost per brief, error rates)
- Redeploy AgentCore with SESSION_MEMORY enabled
- Deploy Bedrock Guardrails and verify they're active on all LLM calls
- Deploy secrets rotation Lambda

What you get: a system you can demo live to a customer with real data flowing through real infrastructure, not localhost.

Effort: ~400 hours. Mostly ops work, not new code.

### Iteration 2: "It handles the real world" (4-6 weeks, 2-3 engineers)

The gap between "works with Alpha Vantage" and "works with institutional data."

- Replace Alpha Vantage with a real market data provider (Bloomberg B-PIPE, Refinitiv, or at minimum Polygon.io paid tier). This changes the market-data MCP server significantly — different API, different data model, different rate limits, real-time vs delayed.
- Replace Tavily with a proper news feed (Dow Jones Newswires, Reuters, or a licensed news API). Financial news has licensing requirements that Tavily's web scraping doesn't satisfy for enterprise use.
- Harden the pipeline for edge cases: what happens when a ticker doesn't exist in SEC EDGAR? When the data API returns rate limit errors mid-pipeline? When Salesforce session expires during a 10-minute pipeline run? When the LLM returns malformed JSON?
- FSC enablement: get a Financial Services Cloud org, deploy the managed package objects, verify the holdings pipeline works with real FinServ__FinancialHolding__c data.
- Build the official salesforce-api skill integration (or accept the inline SOQL approach and document why).

What you get: a system that works with enterprise-grade data sources and handles failures gracefully.

Effort: ~800-1,200 hours. Mix of integration work and hardening.

### Iteration 3: "Compliance would sign off" (6-8 weeks, 2-3 engineers + 1 compliance SME)

The biggest gap. The difference between "has compliance features" and "passes a FINRA examination."

- Replace the 30-day MNPI lookback with a proper MNPI tracking system — a dedicated Salesforce object that tracks disclosure dates, not a time-based heuristic. This needs a compliance officer to define the rules.
- Build a real restricted list system — not audit log queries, but a dedicated `IR_Restricted_List__c` object with add/remove workflows, effective dates, and reason codes.
- Implement suitability checking — the pipeline recommends BUY/HOLD/SELL but doesn't check if the recommendation is suitable for each client's risk profile, investment objectives, and time horizon. This is a FINRA requirement.
- Close the remaining security findings: indirect prompt injection (CRITICAL), Langfuse data classification, request signing between OpenClaw and MCP servers.
- Build a proper RBAC layer — who can run the pipeline, who can approve HITL gates, who can see which clients' data. OpenClaw has no built-in permission model; this needs to be enforced at the Salesforce layer with sharing rules and permission sets that the agent respects.
- Implement data retention policies — Langfuse traces contain LLM inputs/outputs that may include client data. FINRA requires 7-year retention for audit logs but also requires data minimization. These are in tension.
- Write the compliance documentation — a Model Risk Management (MRM) document, an AI governance policy, HITL procedures, escalation workflows. This is not code — it's the paperwork a regulator asks for.
- Get a third-party security audit (not self-assessed).

What you get: a system a CCO would present to a FINRA examiner with confidence.

Effort: ~1,200-1,600 hours. Heavy on compliance SME time, not just engineering.

### Iteration 4: "MuleSoft actually works" (6-8 weeks, 2-3 engineers + MuleSoft access)

Phase 6 is 15 tasks and zero code today. This is the action execution layer.

- Get MuleSoft Anypoint Platform access and a sandbox OMS
- Build `submit_order()`, `get_order_status()`, `rebalance_portfolio()` — real API integrations
- Build `initiate_wire()`, `get_settlement_status()` — wire transfer integration
- Build `run_kyc_screening()`, `open_account()` — KYC and account opening
- Implement HITL approval flows with dual authorization for high-value actions
- Implement compliance pre-check before every MuleSoft action
- Build audit logging for all MuleSoft actions
- Test L5 queries end-to-end

What you get: the full loop — research to execution.

Effort: ~1,000-1,400 hours. Depends heavily on the OMS and core banking APIs.

### Iteration 5: "It scales and doesn't fall over" (4-6 weeks, 2 engineers + 1 SRE)

- Load testing: 50 concurrent pipeline runs, 200 concurrent L1 queries
- Dev/staging/production environments with separate SF orgs and AWS accounts
- Monitoring and alerting: CloudWatch dashboards, PagerDuty, SLA tracking
- Circuit breakers: graceful degradation when data sources are down
- CI/CD pipeline: git push → test → build → deploy
- Backup and disaster recovery

What you get: a system an SRE team would operate in production.

Effort: ~600-800 hours.

### Iteration 6: "Users actually adopt it" (ongoing, 1 engineer + 1 product person)

- User testing with real analysts and advisors
- Brief format iteration based on feedback
- Customization: different templates for different use cases
- Real WhatsApp and Telegram channels
- User preferences and memory tuning
- Admin dashboard for compliance officers

What you get: a system people actually use daily.

Effort: ongoing, ~200-400 hours/quarter.

### Total Iteration Summary

| Iteration | Focus | Weeks | Engineers | Hours |
|-----------|-------|-------|-----------|-------|
| 1 | Runs end-to-end | 2-3 | 1-2 | ~400 |
| 2 | Real-world data | 4-6 | 2-3 | ~1,000 |
| 3 | Compliance sign-off | 6-8 | 2-3 + compliance SME | ~1,400 |
| 4 | MuleSoft execution | 6-8 | 2-3 | ~1,200 |
| 5 | Scale and ops | 4-6 | 2 + SRE | ~700 |
| 6 | User adoption | ongoing | 1 + product | ~300/quarter |
| **Total to production** | | **~6-9 months** | **3-4 engineers avg** | **~5,000-5,500** |

Cost: $1.5M-$2.5M build + $500K-$1M/year to operate.

---

## The Autonomous Execution Plan: 3 Waves

What can be executed now, autonomously, with the available infrastructure.

### Wave 1: Modularize the Core (parallel subagents, no infra needed)

Goal: turn the monolithic pipeline into a configurable, enterprise-pluggable framework.

7 parallel subagents:

**Subagent 1 — Pipeline Config Engine**

Extract all hardcoded values from `pipeline.py` into a `pipeline-config.yaml`:
- Stage definitions (names, order, enabled/disabled)
- MCP server names and tool names per stage
- SOQL queries and SF object/field mappings
- Model parameters (WACC, terminal growth, margin assumptions)
- HITL gate positions (configurable, not hardcoded `{7, 13, 21}`)
- Compliance check types and thresholds
- LLM model IDs per stage (Sonnet for synthesis, Haiku for simple)
- Cost budget and timeout per stage

The pipeline reads the config and executes generically. An enterprise changes the YAML, not the Python.

**Subagent 2 — Data Source Adapter Layer**

Build an adapter pattern for market data, news, and filings:

```
openclaw/skills/fsi-research/adapters/
  base.py              — abstract interfaces (MarketDataAdapter, NewsAdapter, FilingsAdapter)
  alpha_vantage.py     — current Alpha Vantage implementation (extracted from pipeline.py)
  bloomberg.py         — skeleton for Bloomberg B-PIPE
  refinitiv.py         — skeleton for Refinitiv/LSEG
  polygon.py           — skeleton for Polygon.io
  tavily.py            — current Tavily implementation (extracted)
  newsapi.py           — skeleton for NewsAPI.org
  dow_jones.py         — skeleton for Dow Jones Newswires
  sec_edgar.py         — current SEC EDGAR implementation (extracted)
  adapter_registry.py  — loads the right adapter from pipeline-config.yaml
```

Each adapter implements a common interface (`get_quote()`, `get_price_history()`, `search_news()`, `get_filing()`, etc.) but the backend is configurable. The pipeline calls the adapter, not the specific API. New data sources = new adapter file + config entry, zero pipeline changes.

**Subagent 3 — Compliance Rules Engine**

Extract compliance logic from `screening.py` into a rules-based system:

```
openclaw/skills/compliance-screening/
  rules_engine.py      — loads and evaluates rules from YAML
  rules/
    restricted_list.yaml   — source (SF object, external API, CSV), fields, block behavior
    mnpi_tracking.yaml     — method (time-based, disclosure-based, external), lookback, escalation
    concentration.yaml     — thresholds per client tier, sector limits, single-stock limits
    trading_window.yaml    — blackout periods, earnings proximity, configurable days
    suitability.yaml       — risk profile mapping, investment objective checks, time horizon
  adapters/
    salesforce.py          — current SF-based compliance checks
    external_api.py        — skeleton for external compliance system integration
```

Enterprise plugs in their rules, not our code. Rules are YAML-defined with configurable sources, thresholds, and escalation behaviors.

**Subagent 4 — Execution Adapter Layer**

Build the MuleSoft skill as one implementation of an execution adapter interface:

```
openclaw/skills/execution/
  base.py              — abstract interface (ExecutionAdapter)
  mulesoft.py          — MuleSoft Anypoint implementation
  fix_protocol.py      — skeleton for FIX protocol (direct OMS)
  charles_river.py     — skeleton for Charles River IMS
  custom_api.py        — skeleton for custom REST OMS
  hitl.py              — HITL approval flow (shared across all adapters)
  dual_auth.py         — dual authorization for high-value actions
  registry.py          — loads the right adapter from config
```

The interface defines `submit_order()`, `initiate_wire()`, `run_kyc()`, `open_account()` — but the backend is configurable. HITL approval flow is part of the interface, not the implementation. Every action goes through compliance pre-check and audit logging regardless of backend.

**Subagent 5 — Salesforce Schema Abstraction**

Build a mapping layer between the pipeline's data needs and the actual SF object/field names:

```
openclaw/skills/salesforce-crm/
  schema_mapping.yaml  — maps logical names to SF object.field names
  schema_loader.py     — reads mapping, builds SOQL dynamically
  trust_layer.py       — existing (unchanged)
```

Example mapping:
```yaml
company:
  object: IR_Company__c
  fields:
    ticker: Ticker__c
    name: Name
    sector: Sector__c
    market_cap: Market_Cap__c

# Enterprise B might have:
# company:
#   object: Company__c
#   fields:
#     ticker: Symbol__c
#     name: Company_Name__c
#     sector: Industry__c
#     market_cap: Mkt_Cap__c
```

The pipeline never references `IR_Company__c.Ticker__c` directly — it references `schema.company.ticker` and the loader resolves it. Add support for custom objects beyond the 5 we have.

**Subagent 6 — New SF Objects + Security**

Build the compliance hardening layer:

- `force-app/main/default/objects/IR_Restricted_List__c/` — Ticker, Added_Date, Removed_Date, Reason, Added_By, Status (Active/Removed)
- `force-app/main/default/objects/IR_MNPI_Tracking__c/` — Ticker, MNPI_Type, Received_Date, Disclosure_Date, Status (Active/Disclosed), Source
- `openclaw/skills/compliance-screening/suitability.py` — validates recommendations against client risk profile, investment objectives, time horizon
- RBAC permission sets: `IR_Analyst_Access`, `IR_Advisor_Access`, `IR_Compliance_Officer_Access`, `IR_Admin_Access`
- Seed script `seed-05-compliance-data.apex` — restricted list entries, MNPI tracking records
- Update `IR_Agent_Access` permission set to include new objects

**Subagent 7 — Security + DevOps**

Close remaining gaps and build operational tooling:

- Fix #14: HMAC request signing between OpenClaw and MCP servers
- Fix #15: tighten Bedrock Guardrails regex (CUSIP check digit, ISIN country code, add SEDOL)
- Build `.github/workflows/deploy.yml` — CI/CD pipeline
- Build `scripts/deploy-all.sh` — single deployment script
- Build `scripts/health-check.sh` — verifies all components are running
- Add circuit breakers to all MCP calls in pipeline
- Add SF session refresh logic (re-fetch token if expired mid-pipeline)
- Add LLM response validation (retry with simpler prompt if malformed)
- Add pipeline checkpoint/resume (restart from failed stage, not from stage 1)
- Build `enterprise-config-template.yaml` — single file an enterprise fills out

### Wave 2: Deploy and Verify (sequential, uses live SF + AWS)

After Wave 1 code is written:

1. `sf project deploy start --target-org new-org` — deploy all metadata including new objects and permission sets
2. Run seed scripts in order: `seed-01` through `seed-05`
3. Assign updated permission sets: `sf org assign permset --name IR_Agent_Access --target-org new-org`
4. Verify with SOQL queries (count records per object)
5. `finch vm start` — start container runtime
6. `sam build` in `aws/` — build all Lambda functions
7. `sam deploy` — deploy MCP servers, API Gateway, proxies
8. `aws cloudformation deploy` — deploy Bedrock Guardrails
9. `aws cloudformation deploy` — deploy secrets rotation
10. Run `setup-secrets.sh` — auto-populate Secrets Manager
11. Verify MCP servers with curl health checks
12. Run `python scripts/test-pipeline.py` — full 23-stage pipeline
13. Run `python evaluation/run_suite.py --level L1` — quick L1 queries
14. If L1 passes, run `python evaluation/run_suite.py` — full 150-query matrix
15. Populate `performance-baseline.md` with actual measurements
16. Run integration tests (L1 through L3 via Gateway)
17. Test Bedrock Guardrails (denied topic: "Tell me NVIDIA's earnings before they announce")

### Wave 3: Enterprise Packaging (documentation + templates)

1. Build `enterprise-config-template.yaml` — single file covering:
   - Data source selection (market data provider, news provider, filings source)
   - Salesforce org details and schema mapping
   - Compliance rules (restricted list source, MNPI method, concentration limits, trading windows)
   - Execution target (MuleSoft, FIX, custom API)
   - Channel configs (which channels, tokens)
   - LLM model selection (Sonnet/Haiku model IDs)
   - Pipeline customization (enabled stages, HITL gate positions, cost budget)

2. Build `QUICKSTART.md` — 10-step guide from zero to running system

3. Build adapter templates — skeleton files for:
   - "Bring your own Bloomberg"
   - "Bring your own OMS"
   - "Bring your own compliance system"
   - "Bring your own CRM schema"

4. Update all SKILL.md files to reflect the new modular architecture

5. Update README.md and design-doc.md to reflect reality

---

## Architecture Decision: Plugin Architecture (Option B)

Two approaches were considered:

**Option A: Config-driven pipeline** — `pipeline-config.yaml` declares all 23 stages, their data sources, tools, and parameters. `pipeline.py` becomes a generic executor that reads the config. Maximum flexibility, but the pipeline becomes harder to debug because the logic is split between YAML and Python.

**Option B: Plugin architecture** — `pipeline.py` stays as the orchestrator but each stage delegates to a pluggable module loaded from config. Stage 3 calls `data_adapters.market_data.get_quote()` where `market_data` is resolved from config to `adapters/alpha_vantage.py` or `adapters/bloomberg.py`. More code, but easier to debug and extend.

**Decision: Option B.** It's more Pythonic, easier to test, and matches how OpenClaw skills already work. Each adapter is a standalone Python file that can be unit tested independently. The pipeline orchestrator stays readable. Enterprise developers can write a new adapter without understanding the full pipeline.

---

## What's Autonomous vs What Needs Human Input

| Task | Autonomous | Needs Human |
|------|-----------|-------------|
| All Wave 1 code (7 subagents) | ✓ | |
| SF metadata deploy | ✓ | |
| Seed data | ✓ | |
| Finch start + SAM build/deploy | ✓ | |
| Guardrails + rotation deploy | ✓ | |
| Secrets setup | ✓ | |
| Pipeline test | ✓ | |
| Eval suite (if Bedrock quota allows) | ✓ | |
| Wave 3 docs | ✓ | |
| Real Slack/WhatsApp tokens | | ✓ (your accounts) |
| MuleSoft Anypoint access | | ✓ (license needed) |
| FSC license | | ✓ (Salesforce upgrade) |
| Third-party security audit | | ✓ (external vendor) |
| Compliance documentation (MRM) | | ✓ (compliance SME) |
| User testing with real analysts | | ✓ (people needed) |

---

## Estimated Timeline for Autonomous Execution

| Wave | What | Duration | Parallel? |
|------|------|----------|-----------|
| 1 | Code (7 subagents) | 2-4 hours | Yes, all 7 parallel |
| 2 | Deploy + verify | 1-2 hours | Sequential after Wave 1 |
| 3 | Enterprise packaging | 1-2 hours | Sequential after Wave 2 |
| **Total** | | **~half a day to full day** | |

---

## What This Gets You

After all 3 waves:

- Pipeline is config-driven — enterprise changes YAML, not Python
- Data sources are pluggable — swap Alpha Vantage for Bloomberg by writing one adapter file
- Compliance rules are YAML-defined — enterprise plugs in their rules
- Execution targets are pluggable — swap MuleSoft for FIX protocol by writing one adapter file
- Salesforce schema is abstracted — works with any CRM object structure via mapping
- New SF objects for proper compliance (restricted list, MNPI tracking)
- RBAC permission sets for 4 roles
- Suitability checking added
- Security findings closed
- CI/CD pipeline defined
- Full eval suite run with baseline scores
- Everything deployed to live SF org and AWS account
- Enterprise config template ready for adoption

## What This Does NOT Get You

- Real MuleSoft connection (needs license + sandbox OMS)
- Real Slack/WhatsApp/Telegram (needs your tokens)
- FSC managed package objects (needs FSC license)
- Third-party security audit
- Compliance documentation (MRM, AI governance policy)
- User testing with real analysts
- Load testing at enterprise scale
- Dev/staging/production environment separation (needs additional AWS accounts + SF orgs)

---

## Post-Execution: The Remaining 40%

After autonomous execution completes, the remaining work to full enterprise production is:

| Category | Effort | Dependency |
|----------|--------|------------|
| Real data source integration (Bloomberg/Refinitiv) | 400-600 hrs | Data vendor license |
| MuleSoft end-to-end with real OMS | 400-600 hrs | MuleSoft + OMS sandbox |
| Compliance documentation + MRM | 200-400 hrs | Compliance SME |
| Third-party security audit | 100-200 hrs | External vendor |
| Load testing + multi-environment | 200-400 hrs | Additional AWS accounts |
| User testing + adoption | 200-400 hrs/quarter | Real analysts/advisors |
| FSC enablement | 40-80 hrs | FSC license |
| Channel tokens + testing | 20-40 hrs | Platform accounts |

Total remaining after autonomous execution: ~1,600-2,700 hours (~4-6 months with 2-3 engineers).
