# Project 006: Design vs Implementation Reality

> Date: April 9, 2026
> Scope: Line-by-line comparison of design-doc.md (71 tasks, 6 phases) against actual codebase
> Method: Every file in the project read and verified against design claims

---

## Summary Scorecard

| Phase | Tasks | Done | Partial | Not Done | Broken/Deviated |
|-------|-------|------|---------|----------|-----------------|
| 1 Foundation | 12 | 3 | 5 | 3 | 1 |
| 2 MCP Servers | 8 | 8 | 0 | 0 | 0 |
| 3 Pipeline | 12 | 6 | 3 | 1 | 2 |
| 4 Models | 10 | 7 | 0 | 1 | 2 |
| 5 Production | 14 | 4 | 3 | 7 | 0 |
| 6 MuleSoft | 15 | 0 | 0 | 15 | 0 |
| **Total** | **71** | **28** | **11** | **27** | **5** |

28 of 71 tasks done (39%). 11 partial (15%). 27 not done (38%). 5 deviated from design (7%).

---

## Phase 1: Foundation (12 tasks)

| Task | Design | Reality | Verdict |
|------|--------|---------|---------|
| 1.1 AWS account setup: VPC, IAM, Secrets Manager | IAM role, Secrets Manager | `setup-iam-role.sh` and `setup-secrets.sh` exist. Secrets Manager secret has placeholder values (`REPLACE_ME_*`). No VPC config — AgentCore uses `network_mode: PUBLIC`. | PARTIAL |
| 1.2 Deploy OpenClaw on Bedrock AgentCore | OpenClaw running on AgentCore | `.bedrock_agentcore.yaml` shows a real agent ARN, real ECR repo, real CodeBuild project. Container was deployed. But the REST endpoint (`/v1/chat/completions`) returns 500 due to missing `@buape/carbon` module. AgentCore invocations fail. Frontend `.env` points to an AgentCore WSS URL but the gateway token is empty. | BROKEN |
| 1.3 Configure Bedrock model access | Claude Sonnet 4 responding | `openclaw.json` references `us.anthropic.claude-sonnet-4-6` and `us.anthropic.claude-haiku-4-5`. Eval results confirm Bedrock calls work locally. | DONE locally, untested on AgentCore |
| 1.4 Configure Bedrock Guardrails | PII, toxicity, denied topics | `bedrock-guardrails.yaml` is a complete CloudFormation template. PII masking, CUSIP/ISIN regex, content filtering, denied topics (insider trading, unauthorized trading, audit deletion). | DONE (template ready, unclear if deployed) |
| 1.5 Salesforce: create IR_* custom objects | 5 objects deployed | 5 objects in `force-app/`: IR_Audit_Log__c (11 fields), IR_Research_Note__c (12 fields), IR_Company__c, IR_Coverage__c, IR_Watchlist__c. Connected App, Permission Set. | DONE |
| 1.6 Salesforce: FSC objects (FinServ__*) | Holdings, Financial Accounts | Zero FSC objects in metadata. No FinServ__FinancialAccount__c, no FinServ__FinancialHolding__c. The design doc and steering rules (rule 16) list these as required. | NOT DONE |
| 1.7 Connected App + OAuth | OAuth creds in Secrets Manager | `OpenClaw_Agent.connectedApp-meta.xml` exists with PKCE. Frontend `.env` has a real Client ID. But the Secrets Manager secret has placeholder token values. | PARTIAL |
| 1.8 Install salesforce-api skill | OpenClaw can SOQL Salesforce | No standalone skill code. `salesforce-crm/SKILL.md` is documentation only. Pipeline.py does SOQL via raw `requests.get()` calls to the SF REST API. The OpenClaw `salesforce-api` official skill is never installed or configured in `openclaw.json`. | NOT DONE as designed (pipeline has inline workaround) |
| 1.9 Seed data | 10 companies, 3 analysts, coverage, holdings | 3 Apex scripts create 25 accounts, 40 contacts, 30 companies, 30 coverage, 20 watchlist, 5 research notes, 50 audit logs. Exceeds design spec. But no holdings data (because FSC objects don't exist). | PARTIAL |
| 1.10 Langfuse: self-hosted on VPC | Observability running | Using Langfuse Cloud (`https://us.cloud.langfuse.com`), not self-hosted. Deployment notes describe how to self-host but it hasn't been done. Security audit Finding #10 flags this. | NOT DONE |
| 1.11 Connect Langfuse to OpenClaw | Traces visible | Pipeline.py creates Langfuse traces. Eval results show "18 traces captured". Works locally. | DONE locally |
| 1.12 Test: L1 queries via Slack | CRM lookups work | Eval results show Q1-CRM passed ("Who covers Apple?" → correct answer). But via OpenClaw CLI, not Slack. No Slack channel is connected. | PARTIAL |

Phase 1 exit criteria: "Who covers NVIDIA?" in Slack → correct answer from SF. Langfuse shows trace.

Reality: Works via CLI. Not via Slack. Not on AgentCore. Langfuse traces work on cloud, not self-hosted.

---

## Phase 2: MCP Servers (8 tasks)

| Task | Design | Reality | Verdict |
|------|--------|---------|---------|
| 2.1 SEC EDGAR MCP server | 4 tools working | `sec-edgar/app.py`: 5 tools (get_10k, get_10q, get_8k, get_insider_transactions, search_filings). Real SEC EDGAR API calls with rate limiting, CIK cache. | DONE (exceeds spec) |
| 2.2 Market Data MCP server | 4 tools working | `market-data/app.py`: 5 tools (get_quote, get_price_history, get_analyst_consensus, get_options_chain, get_earnings_calendar). Real Alpha Vantage API. | DONE (exceeds spec) |
| 2.3 News Search MCP server | 3 tools working | `news-search/app.py`: 3 tools (search_financial_news, get_headlines, get_news_coverage). Real Tavily API. Renamed from `get_news_sentiment` per tech stack decision (no pre-computed sentiment). | DONE |
| 2.4 API Gateway: all 3 behind gateway | Single gateway, 3 routes | SAM template deploys all 3 behind one API Gateway with API key auth, DLQ, X-Ray, CORS, usage plan. | DONE |
| 2.5 Connect MCP servers to OpenClaw | OpenClaw calls MCP tools | `openclaw.json` has 3 MCP servers configured via stdio bridge (`mcp-rest-bridge.mjs`). Eval results confirm MCP calls work. | DONE |
| 2.6 Langfuse: trace MCP calls | MCP latency visible | Pipeline.py creates spans for every MCP call. Eval shows traces captured. | DONE |
| 2.7 Test: L1 queries (filing, news) | Correct data | Eval Q2-MCP passed ("Show me NVIDIA's latest 10-Q" → full 10-Q breakdown). | DONE |
| 2.8 Test: L2 queries (multi-source) | MCP + SF combined | Eval Q3-Multi passed ("What's happening with NVIDIA ahead of earnings?" → multi-source synthesis). | DONE |

Phase 2 exit criteria: "What's happening with NVIDIA ahead of earnings?" → assembled summary from market + news + CRM. MCP calls traced.

Reality: Met. MCP servers are the strongest part of the project.

---

## Phase 3: AutoResearchClaw Pipeline (12 tasks)

| Task | Design | Reality | Verdict |
|------|--------|---------|---------|
| 3.1 Fork AutoResearchClaw repo | Fork in project | `openclaw/autoresearchclaw/config.arc.yaml` exists with FSI config. `prompts/fsi-research-prompts.yaml` exists. But this is NOT a fork of AutoResearchClaw — it's a custom pipeline written from scratch in `pipeline.py` (1,460 lines). The design says "Fork and adapt — do NOT build a custom pipeline." The steering rules say the same. | DEVIATED |
| 3.2 Replace academic skills with MCP data skills | Stages 3-6 use MCP | Pipeline stages 3-5 call MCP servers (market-data, news-search, sec-edgar). Stage 6 uses LLM for transcript analysis. | DONE |
| 3.3 Add SF data collection to Stage 4 | Pipeline pulls coverage, holdings | Stage 2 pulls IR_Coverage__c, IR_Watchlist__c, IR_Company__c, IR_Research_Note__c. No holdings (FSC objects missing). | PARTIAL |
| 3.4 Adapt output: research brief | Rating, Target, Thesis, Catalysts, Risks | Stages 14-19 produce all of these. Stage 19 assembles structured brief with all sections. | DONE |
| 3.5 Add compliance screening pre-publish | MNPI, restricted list check | Stage 20 does restricted list check, MNPI check, trading window check, anti-fabrication check. | DONE |
| 3.6 Add SF publish: Stage 22 | Brief saved to CRM | Stage 22 creates IR_Research_Note__c via REST API with all fields. | DONE |
| 3.7 Add audit: Stage 23 | Audit trail in SF | Stage 23 creates IR_Audit_Log__c. Plus `_log_audit()` writes audit records at every stage. | DONE |
| 3.8 Configure HITL co-pilot | Gates at 5, 8, 9, 17, 20 | Pipeline has HITL gates at stages 7, 13, 21 (not 5, 8, 9, 17, 20 as in design). The config.arc.yaml says gates at 5, 9, 20. The pipeline code says `HITL_STAGES = {7, 13, 21}`. Mismatch between config and code. | PARTIAL |
| 3.9 Configure OpenClaw bridge | Pipeline notifications via Slack | `config.arc.yaml` has `openclaw_bridge: use_message: true`. But no Slack channel is connected. Notifications go nowhere. | NOT DONE |
| 3.10 Stub financial models | Pipeline runs end-to-end | Stubs were replaced with real models (Phase 4 done). | SUPERSEDED |
| 3.11 Langfuse: trace all 23 stages | Full pipeline trace | Every stage creates a Langfuse span. `_log_audit()` creates Langfuse events. | DONE |
| 3.12 Test: L4 query end-to-end | Complete brief generated | `test-pipeline.py` exists and runs the full 23-stage pipeline with auto-approved HITL gates. Eval Q4-Analysis passed (DCF output). But the full pipeline hasn't been run end-to-end through all 23 stages in the eval results — only 4 targeted queries were tested. | PARTIAL |

Phase 3 exit criteria: "Deep dive on NVIDIA" → 23 stages → HITL gates → simplified brief → SF + audit. Full Langfuse trace.

Reality: Pipeline exists as custom code (not a fork). Works locally with test script. HITL gate numbering doesn't match design. No Slack notifications.

---

## Phase 4: Financial Modeling (10 tasks)

| Task | Design | Reality | Verdict |
|------|--------|---------|---------|
| 4.1 DCF model | `run_dcf()` → fair value | `dcf.py`: Full 5-year DCF with sensitivity table, input validation, NaN guards. 190 lines. | DONE |
| 4.2 Comps | `run_comps()` → relative value | `comps.py`: Peer comparison on 5 metrics, implied prices, narrative. 210 lines. | DONE |
| 4.3 Monte Carlo | `monte_carlo()` → probability dist | `monte_carlo.py`: GBM simulation, percentiles, skew/kurtosis. 120 lines. | DONE |
| 4.4 Sentiment analysis: news | `score_news_sentiment()` | No standalone `sentiment-analysis` skill. Pipeline stage 12 does LLM-based sentiment synthesis inline. Design called for a separate skill. | DEVIATED (inline, not a skill) |
| 4.5 Sentiment analysis: transcript NLP | `analyze_transcript()` | Pipeline stage 6 does LLM-based transcript analysis inline. Design called for Comprehend/FinBERT, but tech stack assessment correctly rejected those. | DEVIATED (inline LLM, correct per tech stack decision) |
| 4.6 Configure sandbox | Isolated execution | `config.arc.yaml` has sandbox config with allowed imports. But the pipeline runs models via direct Python imports (`from dcf import run_dcf`), not in a sandbox. | NOT DONE |
| 4.7 Replace stubs in pipeline | Real models in pipeline | Pipeline stages 9-11 call `run_dcf()`, `run_comps()`, `run_monte_carlo()` directly. | DONE |
| 4.8 Langfuse: trace model execution | Model performance visible | Pipeline creates spans for model execution. | DONE |
| 4.9 Test: L3 queries | Correct analysis | Eval Q4-Analysis passed with 3-scenario DCF. | DONE |
| 4.10 Test: L4 re-run with real models | Brief with real models | `test-pipeline.py` runs the full pipeline with real models. | DONE (script exists) |

Phase 4 exit criteria: Brief includes real fair value (DCF), relative valuation (comps), probability range (Monte Carlo), sentiment. Anti-fabrication verified.

Reality: Financial models are solid. Bonus: `stress_test.py`, `portfolio_impact.py`, `rebalance.py` exist beyond the design spec. Sentiment is LLM-based (correct decision), not a standalone skill.

---

## Phase 5: Production Hardening (14 tasks)

| Task | Design | Reality | Verdict |
|------|--------|---------|---------|
| 5.1 SF Models API (Einstein Trust Layer) | CRM reasoning through Trust Layer | Zero implementation. No code, no config, no reference to SF Models API anywhere in the codebase. | NOT DONE |
| 5.2 Bedrock Guardrails: custom regex | CUSIP, ISIN, acct # | `bedrock-guardrails.yaml` has CUSIP, ISIN, AccountNumber, SWIFTCode, RoutingNumber regex. Security audit Finding #15 says CUSIP regex is too broad. | DONE (with known issues) |
| 5.3 Bedrock Guardrails: denied topics | Insider info blocking | Guardrails template has InsiderTrading, UnauthorizedTrading, DataDeletion denied topics. | DONE |
| 5.4 Build compliance-screening skill | MNPI, restricted, windows, concentration | `compliance-screening/SKILL.md` is documentation only. Pipeline stage 20 implements restricted list, MNPI, and trading window checks inline. No concentration check. Security audit Finding #7 says "MNPI enforcement is documentation-only" — the pipeline checks audit logs but doesn't filter MNPI fields from SOQL results. | PARTIAL |
| 5.5 Build audit-logging skill | Dual-write Langfuse + SF | `audit-logging/SKILL.md` is documentation only. Pipeline `_log_audit()` does dual-write (Langfuse event + SF IR_Audit_Log__c create). Not a standalone skill. | PARTIAL |
| 5.6 MetaClaw cross-run learning | Pipeline learns from failures | `config.arc.yaml` has `metaclaw_bridge: enabled: true`. But there's no MetaClaw code, no learning logic, no lesson storage. The config references a feature that doesn't exist in the custom pipeline. | NOT DONE (config is aspirational) |
| 5.7 Multi-channel: WhatsApp | WhatsApp queries working | `openclaw/channels/whatsapp.yaml` exists as a template. No tokens, no connection. | NOT DONE |
| 5.8 Multi-channel: Telegram | Telegram queries working | `openclaw/channels/telegram.yaml` exists as a template. No tokens, no connection. | NOT DONE |
| 5.9 Secrets Manager auto-rotation | Quarterly credential rotation | `rotate-sf-token.sh` exists and works (fetches fresh SF token, updates Secrets Manager). But no Lambda rotation function, no EventBridge schedule. Manual only. | PARTIAL |
| 5.10 Build 25-query evaluation suite | Automated regression testing | `run_suite.py` with LLM-as-Judge, 7-dimension rubric, 150-query matrix (exceeds 25-query spec). | DONE (framework) |
| 5.11 Configure LLM-as-Judge rubric | 5-dimension scoring | Rubric has 7 dimensions (accuracy, completeness, relevance, safety, actionability, attribution, reasoning). Exceeds spec. | DONE |
| 5.12 Run full suite, establish baseline | Baseline in Langfuse | 4 out of 150 queries run. Performance baseline template is completely empty (`_pending_` everywhere). | NOT DONE |
| 5.13 Security review | Checklist passed | `006-security-audit.md` is thorough: 15 findings, OWASP mapped, severity rated. But it identifies 2 CRITICAL and 5 HIGH findings that are unresolved. | DONE (audit exists, findings unresolved) |
| 5.14 Performance test | Baseline documented | `performance-baseline.md` is a blank template. Zero measurements. | NOT DONE |

Phase 5 exit criteria: 25 queries pass thresholds. Dual trust layer active. Multi-channel. MetaClaw. Audit complete. Security passed.

Reality: None of the exit criteria are met. Eval suite framework exists but hasn't been run at scale. No dual trust layer. No channels. No MetaClaw. Security audit exists but findings are open.

---

## Phase 6: MuleSoft Action Execution (15 tasks)

| Task | Design | Reality | Verdict |
|------|--------|---------|---------|
| 6.1 MuleSoft: Connected App for OpenClaw | OAuth in Secrets Manager | `mulesoft-api/SKILL.md` is documentation only. | NOT DONE |
| 6.2 MuleSoft: API policies | Gateway policies active | Documentation only. | NOT DONE |
| 6.3 `submit_order()` | Trade to OMS | Documentation only. | NOT DONE |
| 6.4 `get_order_status()` | Fill monitoring | Documentation only. | NOT DONE |
| 6.5 `rebalance_portfolio()` | Basket orders | Documentation only. | NOT DONE |
| 6.6 `initiate_wire()` | Wire submission | Documentation only. | NOT DONE |
| 6.7 `get_settlement_status()` | Settlement tracking | Documentation only. | NOT DONE |
| 6.8 `run_kyc_screening()` | Sanctions/PEP/adverse media | Documentation only. | NOT DONE |
| 6.9 `open_account()` | Core banking + custodian | Documentation only. | NOT DONE |
| 6.10 HITL approval flow | Approve/reject/edit in Slack | Documentation only. | NOT DONE |
| 6.11 Dual auth: wire >$100K, trade >$500K | Second approver | Documentation only. | NOT DONE |
| 6.12 Compliance pre-check | Blocked if fails | Documentation only. | NOT DONE |
| 6.13 Audit: log all MuleSoft actions | Full action trail | Documentation only. | NOT DONE |
| 6.14 Test: L5 queries 22-25 | Actions execute with HITL | Documentation only. | NOT DONE |
| 6.15 Re-run full 25-query suite | All levels pass | Documentation only. | NOT DONE |

Phase 6 exit criteria: "Trim Client F's NVDA by 30%" → compliance check → HITL approve → OMS order → fill confirmed → CRM updated → audit logged.

Reality: Entirely documentation. Zero code.

---

## Design Claims vs Reality

### Claim 1: "AgentCore from day one"

Design doc says: "Single environment. No migration. AgentCore from day one."

Reality: AgentCore was deployed (real ARN exists: `fsi_research_agent-Sr1m3j3MUh`). But the REST endpoint (`/v1/chat/completions`) returns 500 due to a missing `@buape/carbon` module. The adapter.js bridges AgentCore HTTP to OpenClaw REST — since the REST endpoint is broken, every `POST /invocations` from AgentCore returns 502. Health check (`GET /ping`) passes because that's Express responding directly. Everything actually works locally only. The frontend `.env` points to an AgentCore WSS URL with an empty gateway token.

### Claim 2: "12+ channels"

Design doc says: "12+ (Slack, WhatsApp, Telegram, Discord, web, API, etc.)"

Reality: Zero channels connected. Channel YAML templates exist for Slack, Telegram, WhatsApp with no tokens. The only working interfaces are the local web frontend and CLI.

### Claim 3: "AutoResearchClaw fork"

Design doc says: "Fork and adapt — do NOT build a custom pipeline." Steering rules repeat this.

Reality: `pipeline.py` is a 1,460-line custom pipeline written from scratch. It's not a fork of AutoResearchClaw. The `config.arc.yaml` references AutoResearchClaw features (MetaClaw, sandbox, stage policies) that the custom pipeline doesn't implement. The HITL gate numbering in the config (5, 9, 20) doesn't match the pipeline code (7, 13, 21).

### Claim 4: "Dual trust layer (Bedrock Guardrails + Einstein Trust Layer)"

Design doc says: "Trust layers: 2 (Bedrock Guardrails + Einstein Trust Layer via SF Models API)"

Reality: Only Bedrock Guardrails exist (as a CloudFormation template — unclear if deployed to AWS). Einstein Trust Layer / SF Models API: zero implementation. No code, no config, no reference anywhere.

### Claim 5: "Zero custom security code — all config"

Design doc says: "No custom security code — Bedrock Guardrails + SF Models API = zero build."

Reality: The security audit found 2 CRITICAL and 5 HIGH vulnerabilities. MNPI enforcement is documentation-only (Finding #7). HITL enforcement for MuleSoft is prompt-based only (Finding #13). Gateway token was exposed in the browser bundle (Finding #2). The "all config" claim is false — significant security code is needed and hasn't been written.

### Claim 6: "Persistent per-user memory"

Design doc says: "Memory: persistent per-user"

Reality: `.bedrock_agentcore.yaml` shows `memory: { mode: NO_MEMORY }`. Memory is disabled.

### Claim 7: "FSC objects: FinServ__FinancialAccount__c, FinServ__FinancialHolding__c"

Steering rule 16 says these are required.

Reality: Not in metadata. Not deployed. No holdings data exists. Seed data creates accounts and companies but no financial accounts or holdings.

### Claim 8: "salesforce-api official skill"

Design doc says: "Install + configure salesforce-api skill"

Reality: Never installed. Not in `openclaw.json`. Pipeline does raw HTTP calls to SF REST API via `requests.get()` and `requests.post()` instead.

---

## What Actually Works (Locally)

- 3 MCP servers (SEC EDGAR, Market Data, News Search) — real code, real APIs, MCP-compliant
- 23-stage pipeline orchestrator — custom build, all stages implemented, Langfuse traced
- Financial models (DCF, comps, Monte Carlo, stress test, portfolio impact, rebalance)
- Salesforce metadata (5 objects, 39 fields, Connected App, Permission Set, seed data)
- Frontend (React 19, WebSocket client, pipeline tracker, HITL panel, brief viewer)
- Evaluation framework (150-query matrix, LLM-as-Judge, 7-dimension rubric)
- 4 targeted queries passed (L1-CRM, L1-MCP, L2-Multi, L3-Analysis)

## What Doesn't Work

- AgentCore deployment (REST endpoint 500s, adapter path broken)
- Any messaging channel (Slack, WhatsApp, Telegram — all template-only)
- Einstein Trust Layer (zero implementation)
- MetaClaw cross-run learning (config only, no code)
- MNPI field-level filtering (documentation only)
- Full evaluation suite (4/150 queries run, performance baseline empty)
- MuleSoft integration (entirely documentation)
- FSC objects / holdings data
- Self-hosted Langfuse
- Sandbox isolation for financial models
- Automated secrets rotation

---

## Unresolved Security Findings (from 006-security-audit.md)

| # | Severity | Finding | Status |
|---|----------|---------|--------|
| 1 | CRITICAL | Indirect prompt injection via MCP responses | OPEN |
| 2 | CRITICAL | Gateway token in browser bundle | OPEN |
| 3 | HIGH | No input sanitization on MCP tools | OPEN |
| 4 | HIGH | CORS wildcard in shared protocol | OPEN |
| 5 | HIGH | Error message leakage | OPEN |
| 6 | HIGH | No WebSocket rate limiting | OPEN |
| 7 | HIGH | MNPI enforcement is documentation-only | OPEN |
| 8 | MEDIUM | Static SF access token | OPEN |
| 9 | MEDIUM | No auth on evaluation suite | OPEN |
| 10 | MEDIUM | Langfuse traces contain sensitive data | OPEN |
| 11 | MEDIUM | No Content Security Policy on frontend | OPEN |
| 12 | MEDIUM | Memory persistence without encryption | OPEN |
| 13 | MEDIUM | MuleSoft HITL enforcement is prompt-based only | OPEN |
| 14 | LOW | No request signing between OpenClaw and MCP | OPEN |
| 15 | LOW | Bedrock Guardrails missing financial-specific patterns | OPEN |
