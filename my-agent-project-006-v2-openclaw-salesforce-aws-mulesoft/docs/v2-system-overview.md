# 006 v2 System Overview

> **Audience:** anyone joining the project — engineers, auditors, new hires, Claude-the-other-assistant.
> **Purpose:** the one doc to read first. Everything else hangs off this.
> **Date:** April 2026 (Phase 6 in progress).

006 v2 is an **FSI (Financial Services Industry) Equity Research Agent** that can (a) answer deep research questions using a 23-stage pipeline, and (b) execute real enterprise actions — trades, wires, KYC — through MuleSoft, with HITL gates, dual-auth, and a full audit trail. It spans three clouds (AWS, Salesforce, MuleSoft/Anypoint) and two external vendors (Alpaca, Langfuse).

---

## Where every component lives

| Component | Cloud | Region | Reproducible from git? | Doc link |
|---|---|---|---|---|
| OpenClaw agent runtime (`fsi-research`) | AWS AgentCore (Bedrock) | `us-east-1` | Yes — `agentcore/openclaw.json`, `Dockerfile`, `agentcore-config.yaml` | [how-kiro-connects-to-salesforce.md](../../docs/how-kiro-connects-to-salesforce.md) |
| Bedrock model (Claude Sonnet 4.6 / Haiku 4.5) | AWS Bedrock | `us-east-1` | No — inference-only, managed | [openclaw/AGENTS.md](../openclaw/AGENTS.md) |
| Bedrock Guardrails (`financial_actions` topic) | AWS Bedrock | `us-east-1` | Yes — `aws/guardrails/bedrock-guardrails.yaml` | [v2-design-doc.md](./v2-design-doc.md) |
| 7 MCP servers (market-data, sec-edgar, news-search, salesforce-crm, research-pipeline, mulesoft-actions, shared) | AWS Lambda + API Gateway | `us-east-2` | Yes — `aws/sam-template.yaml` | [deployment-guide.md](./deployment-guide.md) |
| SF auth proxy | AWS Lambda | `us-east-2` | Yes — `aws/sf-auth-proxy/app.py` | [deployment-guide.md](./deployment-guide.md) |
| Agent proxy (WebSocket → agent) | AWS Lambda | `us-east-2` | Yes — `aws/agent-proxy/app.py` | [deployment-guide.md](./deployment-guide.md) |
| Secrets Manager entries (`/006-v2/*`) | AWS Secrets Manager | `us-east-1` | Structure yes; values no (manual seed) | [006-security-audit.md](./006-security-audit.md) |
| Lambda VPC + NAT gateway (for Anypoint IP allowlist) | AWS VPC | `us-east-2` | Yes — `aws/sam-template.yaml` | [v2-mulesoft-process-api-deploy.md](./v2-mulesoft-process-api-deploy.md) |
| Salesforce org (FSC-enabled, FSI data) | Salesforce | Salesforce multi-tenant | Partial — SObjects + Apex in `force-app/`; data seed is manual | [fsc-objects-note.md](./fsc-objects-note.md) |
| SObjects: `IR_Audit_Log__c`, `IR_Pending_Approval__c` | Salesforce | — | Yes — `force-app/main/default/objects/` | [v2-how-mulesoft-stitches-to-openclaw.md](./v2-how-mulesoft-stitches-to-openclaw.md) |
| Salesforce Connected App (for the CRM MCP server) | Salesforce | — | No — manual screen-driven create | [external-client-app-setup-instructions.md](../../docs/external-client-app-setup-instructions.md) |
| OpenClaw skills (actions.py, hitl.py, dual_auth.py, compliance-screening, audit-logging, fsi-research, financial-analysis) | AWS AgentCore filesystem (bundled in Docker image) | `us-east-1` | Yes — `openclaw/skills/*` | [openclaw/AGENTS.md](../openclaw/AGENTS.md) |
| MuleSoft Process APIs (6: submit-order, initiate-wire, rebalance-portfolio, run-kyc-screening, open-account, close-account) | MuleSoft CloudHub 2.0 | `us-east-2` | **submit-order only** (Maven project); others are loose files pending Maven-ification | [v2-mulesoft-process-api-deploy.md](./v2-mulesoft-process-api-deploy.md) |
| Anypoint API Manager policies (rate limit, client-id, JSON threat, IP allowlist) | MuleSoft | — | Yes — `mulesoft/policies/process-api-policies.json` | [v2-mulesoft-process-api-deploy.md](./v2-mulesoft-process-api-deploy.md) |
| Anypoint Connected App (client credentials for the Lambda) | MuleSoft | — | No — manual create in Access Management | [v2-mulesoft-onboarding-steps.md](./v2-mulesoft-onboarding-steps.md) |
| Alpaca paper-trading account | Alpaca (external) | — | No — manual vendor signup | [v2-vendor-onboarding-tracker.md](./v2-vendor-onboarding-tracker.md) |
| Langfuse trace sink | Langfuse Cloud (external) | EU or US tenant | No — hosted SaaS, project must be created in UI | [006-honest-status-and-architecture.md](./006-honest-status-and-architecture.md) |
| Frontend (React + Vite) | AWS S3 + CloudFront (v2 INDEPENDENT) | us-east-1 | Yes — `frontend/` + `aws/cloudfront-v2-distribution.json` | Live at https://d2f1500216cuaw.cloudfront.net |
| Kiro specs + steering rules | Git only | — | Yes — `.kiro/steering/006-v2-mulesoft.md` | [006-v2-mulesoft.md](../../.kiro/steering/006-v2-mulesoft.md) |

AWS account: **875460787302** (already in CI logs — safe to cite).

---

## Request flow: user types a query → audit logged

Every query, regardless of complexity level, traverses a subset of the same nine hops. The L5 trade path adds hops 4a-4d (compliance + HITL + dual-auth + signed token) between hop 4 and hop 5.

```
1. User types in Slack / Telegram / WhatsApp / Web frontend
2. Channel adapter (openclaw/channels/*.yaml)
3. OpenClaw gateway (agentcore, WebSocket, port 18789)
4. fsi-research agent (Claude Sonnet 4.6 on Bedrock, us-east-1)

   -- L5 WRITE ACTIONS ONLY --
   4a. mulesoft-api skill (openclaw/skills/mulesoft-api/actions.py)
   4b. compliance-screening skill (DENY = hard stop)
   4c. hitl.py (WebSocket stream event, HMAC-SHA256 ApprovalToken, 5-min TTL)
   4d. dual_auth.py (if trade > $500K or wire > $100K)
   -- / --

5. MCP tool call (stdio transport via openclaw/mcp-rest-bridge.mjs to API Gateway)
6. MCP server Lambda (aws/mcp-servers/*/app.py)
7. External: Salesforce, Alpaca, SEC EDGAR, Finnhub, Alpha Vantage, Tavily, MuleSoft
8. Response flows back up. MuleSoft writes go: CloudHub Process API -> Alpaca -> back
9. Audit write: audit-logging skill -> CRM MCP server -> Salesforce IR_Audit_Log__c

All 9 hops are traced in Langfuse. Approval tokens are hashed before logging (raw token never crosses the Langfuse boundary — v2 steering rule 22).
```

---

## Three clouds at play

### AWS — what lives here, why

- **Compute for everything intelligent.** Agents, skills, pipelines, MCP servers. Bedrock gives us Claude without running Python ML infra. Lambda gives us per-call pricing (great for the MCP servers — they sit idle between queries).
- **The guardrails & audit plumbing.** Bedrock Guardrails blocks the `financial_actions` bypass topic. Lambda + API Gateway is the only path to MuleSoft (no direct-from-browser). Secrets Manager holds every credential.
- **The VPC.** Only the `mulesoft-actions` Lambda needs it — the NAT EIP is what Anypoint IP-allowlists in the ip-allowlist policy. Other Lambdas stay public-subnet for cheapness.

Full inventory in [`deployment-guide.md`](./deployment-guide.md).

### Salesforce — what lives here, why

- **Financial Services Cloud (FSC) objects.** `Account`, `Client__c`, `Position`, `Financial_Account__c` — the canonical source of "who owns what". The CRM MCP server redacts MNPI fields (share counts, market values) before surfacing to the LLM.
- **Audit + approval queue.** `IR_Audit_Log__c` is the immutable record of every decision ever made by the agent. `IR_Pending_Approval__c` is the waiting queue for dual-auth actions that need a second signer.
- **Session auth** flows through the SF auth proxy Lambda — the CRM MCP server hits the proxy first to get a short-lived OAuth token, never storing the raw org password.

Why Salesforce and not Postgres? Because the wealth management desk **already** uses FSC. Writing audit logs there means auditors and compliance officers use the tools they know. Also: FSC's OWD, sharing rules, and field-level security already encode the institutional "who can see what" rules — we get them for free.

Full list of SObjects in [`fsc-objects-note.md`](./fsc-objects-note.md).

### MuleSoft (Anypoint) — what lives here, why

- **6 Process APIs** that translate the canonical 006 schemas (e.g. `SubmitOrderRequest`) into vendor-specific shapes (e.g. Alpaca's `/v2/orders` body).
- **API Manager policies** — rate-limit, client-id enforcement, JSON threat protection, **IP allowlist** to the Lambda NAT EIP.
- **Secure Properties** — where vendor credentials (Alpaca `key_id`, `secret`) actually live at runtime. The YAML in git only has placeholders.

Why MuleSoft and not a Lambda-per-vendor? Because:

1. **Policy surface.** Rate limit + IP allowlist + contract validation at the API-gateway level is one-click-configured. Re-implementing that in Lambdas is a mini-platform project.
2. **Vendor swap.** When a vendor changes auth or shape, the DataWeave transform changes. Lambda + agent code doesn't touch. The canonical contract (RAML) stays stable.
3. **Enterprise optics.** Banks already own Anypoint. Dropping an API in their existing org means compliance approval goes through paths that already exist.

Today (Phase 6): **submit-order** is live-ready against Alpaca paper. The other 5 are scaffolded (RAML + XML + DataWeave) but not yet Maven-ified or deployed.

### External vendors

- **Alpaca** (paper trading) — the only live broker-side integration in v2. Credentials in Secrets Manager `/006-v2/vendors/alpaca`, never in git.
- **Langfuse** (observability) — every LLM call + every skill invocation logs a trace. Helps debug the 23-stage pipeline. Free for <50K observations/month.
- Market data sources (Finnhub, Alpha Vantage, Tavily, SEC EDGAR) are read-only and not gated by MuleSoft — they're invoked directly by their respective MCP servers.

---

## Data flow for each query type

### L1 query — "What's NVDA trading at?"

A direct market-data lookup. No pipeline, no MuleSoft, no HITL. Roughly 3 seconds end-to-end.

```
User "What's NVDA trading at?"
  -> channel adapter
  -> OpenClaw gateway (port 18789)
  -> fsi-research agent (Claude Sonnet 4.6)
  -> agent reads system prompt: "market data = MUST call market-data MCP"
  -> MCP tool call: market-data.get_quote(symbol="NVDA")
  -> market-data Lambda hits Finnhub (fallback: Alpha Vantage)
  -> returns {price: 135.00, ts: ..., source: "finnhub"}
  -> agent responds: "NVDA is at $135.00 as of 14:23 UTC. Source: market-data (Finnhub)."
  -> Langfuse logs the trace (single LLM call + single MCP call)
```

No audit log entry for read-only L1 queries — too chatty, not valuable.

### L3 query — "Stress test Client Nakamura's portfolio"

Invokes the **research pipeline** MCP server, which internally runs the 23-stage AutoResearchClaw pipeline (multi-step research + analysis). This path **does** touch Salesforce (to fetch Nakamura's holdings, MNPI-redacted) and **may** pause at HITL gates (stages 7, 13, 21 per `autoresearchclaw/config.arc.yaml`).

```
User "Stress test Client Nakamura's portfolio"
  -> agent -> research-pipeline MCP tool call(run_research_pipeline, ticker=null, query=...)
  -> pipeline kicks off, 23 stages:
      stage 1-6:   gather holdings (CRM MCP, MNPI-redacted shares) + benchmarks + macro context
      stage 7:     HITL gate — "Proceed with these assumptions?" — token required to continue
      stage 8-12:  run Monte Carlo via financial-analysis skill (scenario shocks, VaR, CVaR)
      stage 13:    HITL gate — "These results look reasonable? Draft the client memo?"
      stage 14-20: draft memo, compliance review (MNPI filter), formatting
      stage 21:    HITL gate — final sign-off before distribution
      stage 22-23: render PDF, file in Salesforce Research_Note__c
  -> agent streams intermediate updates to the channel; user sees progress
  -> no MuleSoft, no trades
  -> audit log entry per HITL gate decision
```

Typical latency: 2-5 minutes depending on how fast HITL approvals come back.

### L5 trade query — "Buy 100 AAPL for Client Patel" — the 7-gate path

This is the write-action path. Every write-action L5 query passes through the same 7 gates, in order, no exceptions. Skipping any gate is a config-level impossibility per steering rules 1 and 8.

```
User "Buy 100 AAPL for Client Patel"

  GATE 1: Intent classification
    -> Bedrock Guardrail screens for bypass language ("execute without approval", etc.)
    -> If flagged: hard-stop, never reaches agent. Audit row still written.

  GATE 2: Agent decides "this is an L5 action, invoke mulesoft-api skill"
    -> openclaw.json does NOT expose mulesoft-actions directly — skill is the only door.

  GATE 3: Compliance pre-check (compliance-screening skill)
    -> check_restricted_list, check_trading_window, check_mnpi_flags, check_concentration
    -> DENY = hard stop + IR_Audit_Log__c row with Action__c = COMPLIANCE_BLOCKED
    -> ALLOW = proceed

  GATE 4: Build ActionPlan + compute plan_hash
    -> { ticker: AAPL, side: BUY, quantity: 100, client_id: Patel-sf-id, ... }
    -> plan_hash = sha256(canonical_json(ActionPlan))
    -> This plan_hash is bound to whatever token the user approves.

  GATE 5: HITL approval (hitl.py)
    -> WebSocket stream="hitl" event emits the ActionPlan to the user's channel/UI
    -> User reviews, clicks [Approve] or [Reject]
    -> If approved: hitl.py mints ApprovalToken = HMAC-SHA256(plan_hash + user_id + ts)
    -> Token has 5-min TTL, bound to plan_hash, single-use
    -> If rejected / timed out: IR_Audit_Log__c row with TRADE_REJECTED / TRADE_TIMEOUT

  GATE 6: Dual-auth check (dual_auth.py)
    -> Notional = 100 x $175 = $17,500 -> under $500K threshold -> skip.
    -> If over: request_second_approval blocks, writes IR_Pending_Approval__c,
      pings a Senior_Compliance_Approver, waits for second signed token.

  GATE 7: MCP tool call -> Lambda -> CloudHub -> Alpaca
    -> POST /mulesoft-actions/tools/call name=submit_order
      arguments include approval_token (hashed before logging, per rule 22)
    -> Lambda reads mode; in sandbox it hits CloudHub
    -> CloudHub submit-order flow: validate -> normalize -> alpaca-request.dwl
    -> HTTPS to paper-api.alpaca.markets/v2/orders with APCA-* headers
    -> Alpaca returns {id, status, created_at, ...}
    -> alpaca-response.dwl maps to canonical SubmitOrderResponse
    -> Lambda returns to skill
    -> Skill writes IR_Audit_Log__c: Action__c=TRADE_SUBMITTED,
       MuleSoft_Reference__c=MS-REF-..., Approved_By__c=user_sf_id

  Response to user: "Order submitted. ID ALPACA-xxxx. Ref MS-REF-xxxx. Notify on fill."
```

Full deep-dive with diagram and every file path in [`v2-how-mulesoft-stitches-to-openclaw.md`](./v2-how-mulesoft-stitches-to-openclaw.md).

---

## Credential locations (never in git)

| Secret name | Stored in | Rotation procedure | Owning component |
|---|---|---|---|
| `/006-v2/mulesoft/credentials` (`client_id`, `client_secret`, `base_url`, `process_api_base_url`) | AWS Secrets Manager | Anypoint -> Access Management -> Connected Apps -> rotate secret -> `aws secretsmanager update-secret` | `aws/mcp-servers/mulesoft-actions/mulesoft_client.py` |
| `/006-v2/vendors/alpaca` (`key_id`, `secret`, `endpoint`, `account_number`) | AWS Secrets Manager | Alpaca dashboard -> API keys -> regenerate -> Anypoint Runtime Manager Secure Properties | `submit-order` Process API (CloudHub Secure Properties at runtime) |
| `SF_ACCESS_TOKEN`, `SF_INSTANCE_URL` | AWS Secrets Manager (seeded at deploy) + short-lived from SF auth proxy | Handled by `aws/sf-auth-proxy/app.py`; refresh every 2h | `aws/mcp-servers/salesforce-crm/app.py` |
| `MCP_API_KEY` | AWS Secrets Manager | Regenerate in AWS + update Lambda env + redeploy agent | All 7 MCP servers + the mcp-rest-bridge |
| `OPENCLAW_GATEWAY_TOKEN` | AWS Secrets Manager | Rotate + update AgentCore env + restart | `agentcore/openclaw.json` |
| `OPENCLAW_HOOKS_TOKEN` | AWS Secrets Manager | Rotate + update | AgentCore hooks endpoint |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | AWS Secrets Manager | Langfuse UI -> rotate -> update SM | All agents (trace sink) |
| `ALPHA_VANTAGE_API_KEY`, `TAVILY_API_KEY`, `FINNHUB_API_KEY` | AWS Secrets Manager | Vendor dashboard -> rotate -> update SM | `market-data`, `news-search` MCP servers |
| `HITL_SIGNING_KEY` (HMAC secret for ApprovalToken) | AWS Secrets Manager | Regenerate -> update -> drain in-flight tokens (they'll fail signature check, which is desired) | `openclaw/skills/mulesoft-api/hitl.py` |
| `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `TELEGRAM_BOT_TOKEN`, WhatsApp tokens | AWS Secrets Manager | Channel vendor UI -> rotate -> update | `openclaw/channels/*.yaml` |
| `ANYPOINT_CONNECTED_APP_ID`, `ANYPOINT_CONNECTED_APP_SECRET` (deploy-time only) | CI secret store (e.g. GitHub Actions secrets) + operator shell | Regenerate in Anypoint -> paste to CI | `mulesoft/process-apis/submit-order/pom.xml` (via env vars) |

**Nothing in this table appears in any file in git.** Every name above resolves to an env var reference (`${...}`) or a Secrets Manager ARN. The 5 manual-seed steps are documented in the "How to rebuild from zero" section below.

---

## Reproducibility status

### Fully reproducible from git (clone, run commands, done)

- All 7 MCP servers (SAM template in `aws/sam-template.yaml`).
- Agent proxy Lambda + SF auth proxy Lambda.
- Bedrock Guardrails configuration.
- OpenClaw skill code (`openclaw/skills/*`).
- AgentCore container definition (`agentcore/Dockerfile`, `docker-compose.yml`, `agentcore-config.yaml`).
- Salesforce SObjects (`IR_Audit_Log__c`, `IR_Pending_Approval__c`) via `sfdx force:source:deploy`.
- Frontend (`frontend/`) — `npm install && npm run build`.
- **submit-order Process API** — now a proper Maven project (`pom.xml`, `mule-artifact.json`, `src/main/mule/...`).
- MUnit test suite for submit-order.
- Kiro specs, steering rules, build plans — all markdown, all in git.

### One-command manual steps (script exists, operator runs it)

- Secrets Manager seeding: `scripts/seed-secrets.sh` reads a local `.env` (gitignored) and creates all ~14 secrets. Operator must supply the raw values once.
- Salesforce metadata deploy: `sf project deploy start -d force-app`.
- AgentCore container push: `docker build && aws ecr get-login-password | docker login && docker push`.
- MCP servers: `sam build && sam deploy --guided` (first time), `sam deploy` thereafter.

### Human-only (point-and-click in a vendor console)

- **Anypoint Connected App** creation. Access Management -> Connected Apps -> New. Copy the secret ONCE — Anypoint doesn't show it again.
- **Anypoint Business Group / Org** setup if starting from a fresh trial.
- **CloudHub 2.0 app name** choice — must be globally unique in the MuleSoft org (`006-v2-trade-process-api` is taken in our org).
- **Anypoint API Manager** policy application per deployed app (4 policies x 6 APIs once all 6 are live = 24 clicks).
- **CloudHub Secure Properties** UI — where Alpaca `key_id` / `secret` actually land.
- **Salesforce Connected App** (external client app for the CRM MCP). Step-by-step in [`external-client-app-setup-instructions.md`](../../docs/external-client-app-setup-instructions.md).
- **Alpaca paper account** creation + API key generation.
- **Langfuse project** creation + public/secret key generation.
- **Slack / Telegram / WhatsApp** bot creation in the respective vendor dashboards.
- The 5 other Process APIs (`initiate-wire`, `rebalance-portfolio`, `run-kyc-screening`, `open-account`, `close-account`) still need the Maven treatment that submit-order just got.

---

## How to rebuild from zero

Starting state: empty AWS account, empty Salesforce org, fresh Anypoint trial, brand-new laptop.

```bash
# ===== 0. Prereqs on the laptop =====
# Install: aws cli v2, sam cli, sfdx cli, node 20, python 3.11, maven 3.8+, jdk 17, docker, jq.
# Sign in to AWS (`aws configure sso` or `aws configure`), account 875460787302, region us-east-1.

# ===== 1. Clone =====
git clone <this-repo>
cd my-agent-project-006-v2-openclaw-salesforce-aws-mulesoft

# ===== 2. MANUAL: create external accounts =====
#   a. Alpaca paper account    -> grab key_id + secret
#   b. Langfuse project        -> grab public_key + secret_key
#   c. Salesforce Dev Hub + scratch org (or a real sandbox)
#   d. Anypoint trial          -> create a business group, note its ORG_ID
#   e. Anypoint Connected App (client_credentials grant) -> note CLIENT_ID + CLIENT_SECRET
#   f. Slack / Telegram / WhatsApp bots per channel you want

# ===== 3. Seed Secrets Manager =====
cp aws/.env.example aws/.env        # fill in every value
scripts/seed-secrets.sh             # reads aws/.env, creates all /006-v2/* secrets
rm aws/.env                         # immediately — never commit

# ===== 4. Deploy AWS infra (VPC + 7 MCP servers + 2 proxies + Guardrails) =====
cd aws
sam build
sam deploy --guided                 # first time only, pick us-east-2 for Lambda, us-east-1 for Bedrock/Guardrails
cd ..

# ===== 5. Deploy Salesforce metadata =====
sf org create scratch -f config/project-scratch-def.json -a fsi-v2
sf project deploy start -d force-app -o fsi-v2

# ===== 6. MANUAL: set up Salesforce Connected App =====
#   See docs/external-client-app-setup-instructions.md.
#   Take the consumer_key/secret, run scripts/update-sf-secret.sh.

# ===== 7. Build + push AgentCore container =====
cd agentcore
docker build -t openclaw:v2 .
aws ecr create-repository --repository-name openclaw --region us-east-1
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 875460787302.dkr.ecr.us-east-1.amazonaws.com
docker tag openclaw:v2 875460787302.dkr.ecr.us-east-1.amazonaws.com/openclaw:v2
docker push 875460787302.dkr.ecr.us-east-1.amazonaws.com/openclaw:v2
cd ..

# ===== 8. Deploy the agent on AgentCore =====
#   The Bedrock AgentCore console expects the ECR image + an env-vars YAML.
#   Point it at agentcore/agentcore-config.yaml.

# ===== 9. Deploy the submit-order MuleSoft Process API =====
cd mulesoft/process-apis/submit-order
export ANYPOINT_CONNECTED_APP_ID="<from step 2e>"
export ANYPOINT_CONNECTED_APP_SECRET="<from step 2e>"
export ANYPOINT_ORG_ID="<from step 2d>"
mvn clean install
mvn deploy -Pcloudhub-sandbox
cd ../../..

# ===== 10. MANUAL: Anypoint Runtime Manager -> Secure Properties =====
#   Paste Alpaca key_id + secret into the app's Secure Properties panel.
#   See docs/v2-mulesoft-process-api-deploy.md section "Deploying submit-order with live Alpaca backend".

# ===== 11. MANUAL: Anypoint API Manager -> apply the 4 policies =====
#   For each policy in mulesoft/policies/process-api-policies.json, click Apply.
#   The ip-allowlist policy needs the NAT EIP from step 4's CloudFormation output.

# ===== 12. Deploy frontend (optional but recommended) =====
cd frontend
npm install
npm run build
# Upload dist/ to S3+CloudFront, Vercel, or Amplify — per your flavor.
cd ..

# ===== 13. Smoke test =====
scripts/smoke-test.sh              # hits the WebSocket endpoint with 3 sample queries (L1, L3, L5)

# ===== 14. Run the L5 eval in mock mode =====
cd evaluation
python run-l5-eval.py --mode mock  # all 20 queries 121-140 should pass

# Now flip mulesoft-actions Lambda to MULESOFT_MODE=sandbox
aws lambda update-function-configuration \
  --function-name mulesoft-actions \
  --environment "Variables={MULESOFT_MODE=sandbox,MULESOFT_SECRET_NAME=/006-v2/mulesoft/credentials}"

# And rerun in sandbox mode (real Alpaca paper orders will land)
python run-l5-eval.py --mode sandbox
```

Total wall-clock for someone who's done it before: about **4 hours** of active work, split by a **1-2 hour wait** for Anypoint Connected App propagation and CloudHub first-deploy cold start.

---

## Steering rules summary

The 27+1 non-negotiables. Full text + context in [.kiro/steering/006-v2-mulesoft.md](../../.kiro/steering/006-v2-mulesoft.md) and the v1 base steering at `.kiro/steering/006-openclaw-fsi.md`.

**Single choke point**

1. All MuleSoft calls go through `openclaw/skills/mulesoft-api/actions.py`. No other door.

**HITL**

2. Every write action requires a valid ApprovalToken (HMAC-SHA256, 5-min TTL).
3. The token is bound to a specific `plan_hash` — no reuse across actions.
4. Timeouts = ACTION ABORTED. No silent skip.

**Dual auth**

5. Wire > $100K, trade > $500K, any account closure -> dual approval required.
6. Second approver must be distinct from first.
7. Second approver must hold `Senior_Compliance_Approver` perm set.

**Compliance pre-check**

8. compliance-screening runs BEFORE HITL. DENY = hard stop, no override.
9. A DENY still writes `IR_Audit_Log__c` with `Action__c = COMPLIANCE_BLOCKED`.

**Audit**

10. Every attempt — approved, rejected, timed out, compliance-blocked — writes to `IR_Audit_Log__c`.
11. Dual-auth waiting states additionally write to `IR_Pending_Approval__c`.
12. `Action__c` picklist extended in v2: TRADE_SUBMITTED, TRADE_REJECTED, WIRE_INITIATED, WIRE_BLOCKED, KYC_SCREENING, ACCOUNT_OPENED, COMPLIANCE_BLOCKED.
13. `MuleSoft_Reference__c` captured from MCP response. `Approved_By__c` + `Dual_Approver__c` required where applicable.

**Mock mode**

14. MCP server defaults `MULESOFT_MODE=mock` until vendor sandbox approved.
15. Mock must return realistic shapes (valid order_ids, refs) for eval coverage.
16. All 20 L5 eval queries (121-140) must pass in mock BEFORE first vendor call.

**Deployment**

17. AgentCore required for v2. No localhost gateway in Phase 6.
18. `MULESOFT_CLIENT_ID`, `MULESOFT_CLIENT_SECRET`, `MULESOFT_BASE_URL` only in AWS Secrets Manager. Zero credentials in git.
19. mulesoft-actions Lambda runs in a VPC with NAT egress. Anypoint allowlists the NAT EIP.

**Security**

20. Bedrock Guardrail `financial_actions` topic flags HITL-bypass attempts.
21. MNPI never reaches the LLM. Plan summaries shown in HITL go to humans, not prompts.
22. Approval tokens never logged to Langfuse in raw form — hash only.

**v1 mistakes to avoid (Phase 6 specific)**

23. No "autopilot mode" config flag — HITL is always live.
24. LLM does not synthesize MuleSoft args directly. Structured ActionPlan -> user review -> signed token.
25. AutoResearchClaw pipeline does NOT call the mulesoft-api skill. Pipelines recommend, skill executes.
26. Log plan_hash + approver_id + timestamp. Never the raw token.
27. Never mix mock and sandbox responses in the same eval run.

**And the +1: dataway discipline**

28. Vendor contracts change. Canonical 006 schemas do not. When Alpaca changes a field, it changes in `alpaca-request.dwl` / `alpaca-response.dwl` only — the RAML, the skill, and the audit log never notice.

---

## What is NOT production-ready

Honest list. Bullets, not paragraphs.

- Only **1 of 6** Process APIs is Maven-ified + deployable (submit-order). The other 5 (`initiate-wire`, `rebalance-portfolio`, `run-kyc-screening`, `open-account`, `close-account`) are loose XML + RAML files — not buildable as-is.
- Only **1 of 6** vendors is actually integrated. Alpaca paper is live-ready; no sandbox yet for wire provider (candidate: Dwolla), KYC (candidate: Plaid), account-open, account-close, or portfolio rebalance vendor.
- **HITL** skill (`hitl.py`) is scaffolded but not fully tested against a real user on the frontend. HitlPanel React component is pending. No human has clicked [Approve] end-to-end.
- **Dual-auth** skill (`dual_auth.py`) is scaffolded. IR_Pending_Approval__c queue logic exists; second-approver routing (SMS / email / Slack DM) is not wired.
- **L5 eval** (queries 121-140) has no ground-truth JSON yet. `docs/v2-eval-l5-ground-truth.md` is a placeholder.
- **MULESOFT_MODE = production** has never been flipped. Only mock + sandbox have been exercised.
- **Secrets rotation** is documented per-secret but not automated. Nothing expires anything today; ops must rotate by hand.
- **VPC stack** exists in `sam-template.yaml` but NAT EIP cost (~$35/mo) is not justified until a second vendor comes online.
- **MNPI filtering** in `compliance-screening/mnpi_filter.py` is regex-based. Sophisticated paraphrasing would bypass it. Needs a Bedrock-content-moderation layer for real production.
- **Frontend** has no auth. Anyone with the WebSocket URL can talk to the agent. Good enough for a demo on a laptop; not good enough for a customer-facing URL.
- **Channels** (Slack/Telegram/WhatsApp) are scaffolded but not verified past a single message ping. No threaded conversation state yet.
- **Langfuse** tenant is a personal account. No SSO, no team-level access.
- **CloudHub 2.0 app name** is globally scoped in the MuleSoft org — two teams can't both call theirs `006-v2-trade-process-api`. That's fine for a single-team project but a landmine for enterprise rollout.
- **Disaster recovery** — there's no DR plan. Salesforce and Anypoint handle their own side; if the AWS us-east-2 region goes down, the MCP servers and the Process API are both unreachable. An L5 trade queued at that moment will time out and be audit-logged as TRADE_TIMEOUT, which is the correct failure mode — but there is no automatic retry.
- **Compliance-screening** does not yet integrate with a real restricted-list provider (DTCC, internal compliance DB). It reads from a hardcoded JSON in the skill folder.
- **Cost** — at Bedrock Sonnet 4.6 prices (~$3/$15 per M tokens in/out), an L3 query with the 23-stage pipeline costs $0.40-$0.80. A busy desk running 500 queries/day costs $150-$400/day. Not free. See [`cost-analysis-001-to-006.md`](../../docs/cost-analysis-001-to-006.md) for the full breakdown.

---

*End of document.*
*For detailed operational procedures see `deployment-guide.md`, `v2-mulesoft-process-api-deploy.md`, and `v2-how-mulesoft-stitches-to-openclaw.md`.*


---

## Reproducibility Audit (April 2026)

**Git state:** everything in this folder is committed to
`https://github.com/sovikkn2015/connections-tests.git` (main branch).
Commit `97eac55..` covers the full Phase 6 scaffold; commit `99f4505..` updates hooks/steering.

**Gitignored (intentional, zero-cred rule 18):**
- `aws/samconfig.toml` (SAM deploy params with vendor API keys for market-data / news-search)
- `mulesoft/process-apis/submit-order/.anypoint-settings.xml` (Maven Anypoint creds via env vars)
- `mulesoft/process-apis/submit-order/target/` (Maven build output)
- `frontend/node_modules/` and build caches

**Rebuild from clean clone (order matters):**

1. Clone repo + cd into v2 tree.
2. Pre-reqs (one-time per machine):
   ```bash
   brew install awscli jq openjdk@17 maven aws-sam-cli
   export JAVA_HOME=/opt/homebrew/opt/openjdk@17
   ```
3. AWS Secrets Manager — seed 3 secrets manually (UI or `aws secretsmanager create-secret`):
   - `/006-v2/mulesoft/credentials` = `{client_id, client_secret, base_url, organization_id, environment_id}`
   - `/006-v2/vendors/alpaca`       = `{key_id, secret, endpoint, account_number}`
   - `/006-v2/hitl/signing-key`     = `{signing_key}` (auto-created by `scripts/seed-secrets-manager.sh`)
4. Create `aws/samconfig.toml` from `aws/samconfig.toml.example` and fill in:
   - Tavily, Langfuse, (optional Alpha Vantage, Finnhub) API keys
5. Deploy AWS stack: `cd aws && sam build --use-container && sam deploy`
   → produces `openclaw-mcp-006-v2` CloudFormation stack with API Gateway, 7 Lambdas.
6. Deploy Salesforce metadata: `sf project deploy start --target-org <alias>`
   + run the 4 apex seed scripts from `scripts/apex/`.
7. MuleSoft Anypoint:
   - Sign in as admin user (Connected Apps cannot publish to Exchange).
   - Set env: `ANYPOINT_USERNAME`, `ANYPOINT_PASSWORD`, `ANYPOINT_ORG_ID`.
   - Create local `mulesoft/process-apis/submit-order/.anypoint-settings.xml`
     (copy from earlier commit or regenerate — template is inline in pom.xml comments).
   - `cd mulesoft/process-apis/submit-order && mvn clean deploy -s .anypoint-settings.xml -DskipTests -Dmunit.skip=true`
   - `mvn mule:deploy -s .anypoint-settings.xml -DskipTests -Dmunit.skip=true`
   - Copy the resulting `*.cloudhub.io` URL.
   - Paste Alpaca `key_id` + `secret` into Runtime Manager → Secure Properties.
   - Apply 4 policies from `mulesoft/policies/process-api-policies.json` in API Manager.
8. Wire the CloudHub URL into AWS:
   ```bash
   aws secretsmanager update-secret --secret-id /006-v2/mulesoft/credentials \
       --secret-string "$(aws secretsmanager get-secret-value \
                              --secret-id /006-v2/mulesoft/credentials \
                              --query SecretString --output text \
                          | jq --arg url "$CLOUDHUB_URL" '. + {process_api_base_url: $url}')"
   aws lambda update-function-configuration \
       --function-name openclaw-mcp-006-v2-mulesoft-actions \
       --environment "Variables={MULESOFT_MODE=sandbox,MULESOFT_SECRET_NAME=/006-v2/mulesoft/credentials}"
   ```
9. Verify: `./scripts/verify-006-v2.sh` — expect 6/6 PASS.
10. Mock regression: `export HITL_SIGNING_KEY=$(openssl rand -hex 32) && python3 scripts/test-mulesoft-mock.py` — expect 15/15.
11. Live E2E: `CLOUDHUB_APP_URL=<url> MULESOFT_CLIENT_ID=<id> ./scripts/run-alpaca-e2e-test.sh` — submits a real paper order to Alpaca.

**Non-reproducible bits (external/UI-gated by design):**
| Step | Why non-automated |
|---|---|
| Alpaca account creation | Vendor-side, KYC required. |
| Anypoint account creation | Vendor-side, verified email. |
| Anypoint Connected App scopes | UI screen for Runtime Manager + Exchange scopes (can automate later via Access Management API). |
| Anypoint Maven Exchange publish | Connected Apps cannot publish assets; user-credential `mvn deploy` required. |
| CloudHub 2.0 app ingress endpoints | API is JSON-patchable but UI click is more reliable. |
| Langfuse workspace creation | Vendor-side. |
| Langfuse v2 project (`006-v2`) creation + per-project key pair | Vendor UI step — Langfuse Cloud does not expose a public project-create API. Create a dedicated project named `006-v2`, mint public/secret keys, paste into `/006-v2/observability/langfuse` Secrets Manager entry, then redeploy Lambdas. SAM template accepts `LangfuseProject` parameter; `frontend/.env.production` has `VITE_LANGFUSE_PROJECT=006-v2`. |
| SF scratch org creation + FSC-enabling | `sfdx force:org:create` + contact Salesforce for FSC license. |

Everything else reproduces from `git clone` + the 11-step runbook above.

**Known state at commit 99f4505:**
- AWS SAM stack `openclaw-mcp-006-v2` DEPLOYED (API Gateway `caodv9yori`).
- mulesoft-actions Lambda LIVE in mock mode.
- Mule asset `submit-order-process-api:1.0.3` published to Anypoint Exchange.
- CloudHub 2.0 app `openclaw-v2-trade-process-api` RUNNING, public URL `https://openclaw-v2-trade-process-api-q73tdv.5sc6y6-2.usa-e2.cloudhub.io`.
- Ingress endpoints still to be finalized through Runtime Manager UI (`Add Endpoint` → Public).
- Mock test suite 15/15.
- Secrets Manager all 3 entries present.
