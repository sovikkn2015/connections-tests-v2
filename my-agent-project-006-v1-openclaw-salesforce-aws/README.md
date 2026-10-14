# Project 006: OpenClaw + Salesforce + AWS — FSI Investment Research Agent

AI research assistant for financial services. Analyst types "Deep dive on NVIDIA ahead of earnings" in Slack — gets a compliance-screened research brief with rating, target price, thesis, DCF valuation, and Monte Carlo simulation. Every step auditable for FINRA.

```
Analyst (Slack / Web / WhatsApp)
  → OpenClaw Gateway (AgentCore, WebSocket)
    → Claude Sonnet 4.6 / Haiku 4.5 (Bedrock)
    → AutoResearchClaw Pipeline (23 stages, 3 HITL gates)
    → MCP Servers (Lambda): SEC EDGAR, Market Data, News
    → Financial Skills: DCF, comps, Monte Carlo, stress test
    → Salesforce CRM: client data, audit trail, research notes
```

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone and Setup](#2-clone-and-setup)
3. [AWS Setup — Secrets Manager and IAM](#3-aws-setup--secrets-manager-and-iam)
4. [Salesforce — Deploy Metadata](#4-salesforce--deploy-metadata)
5. [Salesforce — Load Seed Data](#5-salesforce--load-seed-data)
6. [AWS — Deploy MCP Servers (SAM)](#6-aws--deploy-mcp-servers-sam)
7. [AWS — Deploy Bedrock Guardrails](#7-aws--deploy-bedrock-guardrails)
8. [OpenClaw — Install and Configure](#8-openclaw--install-and-configure)
9. [MCP Bridge Setup](#9-mcp-bridge-setup)
10. [Pipeline Test](#10-pipeline-test)
11. [Frontend](#11-frontend)
12. [Evaluation Suite](#12-evaluation-suite)
13. [AgentCore Deployment (Optional)](#13-agentcore-deployment-optional)
14. [Troubleshooting](#14-troubleshooting)
15. [Project Structure](#15-project-structure)
16. [Docs](#16-docs)

---

## 1. Prerequisites

### Required Tools

| Tool | Version | Install | Why |
|------|---------|---------|-----|
| Salesforce CLI (`sf`) | 2.x | `npm install -g @salesforce/cli` | Deploy metadata, run seed scripts, fetch access tokens |
| AWS CLI | 2.x | `brew install awscli` | Manage AWS resources, retrieve API keys |
| AWS SAM CLI | 1.x | `brew install aws-sam-cli` | Build and deploy Lambda MCP servers |
| Node.js | 20+ | `brew install node` | Frontend build, OpenClaw Gateway |
| Python | **3.10** | `brew install python@3.10` | Lambda runtime is pinned to 3.10 |
| Docker | Latest | Docker Desktop | SAM build uses Docker for Lambda packaging |

> **Python version matters.** `sam build` will fail with Python 3.12+. The SAM template pins `Runtime: python3.10`. Install 3.10 and ensure `python3.10` is on your PATH, or set `SAM_CLI_PYTHON_VERSION=3.10`.

### Required Accounts and API Keys

| Credential | Where to Get It | Used By |
|-----------|----------------|---------|
| AWS Account (us-east-1, Bedrock access enabled) | AWS Console | Lambda, API Gateway, Bedrock, Guardrails |
| Salesforce Org (Developer Edition or Enterprise) | developer.salesforce.com | CRM data, audit trail, OAuth |
| Salesforce Financial Services Cloud (FSC) | Optional — contact Salesforce AE | Holdings data (`FinServ__FinancialHolding__c`). Pipeline works without it. See `docs/fsc-objects-note.md` |
| Alpha Vantage API Key | alphavantage.co/support/#api-key | Market Data MCP server |
| Tavily API Key | tavily.com | News Search MCP server |
| Langfuse Account (optional but recommended) | us.cloud.langfuse.com | Observability — traces, evals, cost tracking |

### AWS Bedrock Model Access

Before anything else, enable these models in the AWS Bedrock console (us-east-1):

- `us.anthropic.claude-sonnet-4-6` (primary — L3-L5 queries, pipeline stages)
- `us.anthropic.claude-haiku-4-5-20251001-v1:0` (fast — L1-L2 queries)

Go to Bedrock Console → Model access → Manage model access and request access. Approval is usually instant for Anthropic models.

---

## 2. Clone and Setup

```bash
git clone <repo-url>
cd my-agent-project-006-v1-openclaw-salesforce-aws
```

Verify the project structure:
```bash
ls force-app/main/default/objects/  # 5 objects: IR_Audit_Log__c, IR_Company__c, IR_Coverage__c, IR_Research_Note__c, IR_Watchlist__c
ls aws/mcp-servers/                 # market-data, news-search, sec-edgar, shared
ls openclaw/skills/                 # audit-logging, compliance-screening, financial-analysis, fsi-research, mulesoft-api, salesforce-crm
```

---

## 3. AWS Setup — Secrets Manager and IAM

### 3a. Create Secrets Manager Secret

The AgentCore container and pipeline scripts pull credentials from AWS Secrets Manager. Create a secret named `openclaw-fsi-secrets`:

```bash
aws secretsmanager create-secret \
  --name openclaw-fsi-secrets \
  --region us-east-1 \
  --secret-string '{
    "OPENCLAW_GATEWAY_TOKEN": "<generate with: openssl rand -hex 32>",
    "SF_INSTANCE_URL": "https://YOUR_ORG.my.salesforce.com",
    "SF_ACCESS_TOKEN": "<from sf org display after login>",
    "MCP_GATEWAY_URL": "<fill after step 6>",
    "MCP_API_KEY": "<fill after step 6>",
    "TAVILY_API_KEY": "tvly-XXXXX",
    "ALPHA_VANTAGE_API_KEY": "XXXXX",
    "LANGFUSE_SECRET_KEY": "sk-lf-XXXXX",
    "LANGFUSE_PUBLIC_KEY": "pk-lf-XXXXX",
    "LANGFUSE_BASE_URL": "https://us.cloud.langfuse.com"
  }'
```

> You'll update `MCP_GATEWAY_URL` and `MCP_API_KEY` after step 6 (SAM deploy). Use `aws secretsmanager update-secret` to patch them.

### 3b. IAM Role for AgentCore (if deploying to AgentCore)

The AgentCore execution role needs:
- `bedrock:InvokeModel` (for Claude Sonnet/Haiku)
- `secretsmanager:GetSecretValue` (for `openclaw-fsi-secrets`)
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`

See `agentcore/agentcore-config.yaml` for the full role reference.

---

## 4. Salesforce — Deploy Metadata

### 4a. Login to your org

```bash
sf org login web --alias my-org --instance-url https://login.salesforce.com
```

### 4b. Deploy all metadata

```bash
sf project deploy start --target-org my-org
```

This deploys:
- **5 custom objects** with **39 fields** total:
  - `IR_Audit_Log__c` (11 fields) — FINRA audit trail
  - `IR_Research_Note__c` (12 fields) — generated research briefs
  - `IR_Company__c` (5 fields) — company master data
  - `IR_Coverage__c` (6 fields) — analyst coverage assignments
  - `IR_Watchlist__c` (5 fields) — analyst watchlists
- **Connected App** (`OpenClaw_Agent`) — OAuth2 PKCE + OpenID, callback URLs for localhost:5173
- **Permission Set** (`IR_Agent_Access`) — field-level security for all IR_* objects

### 4c. Assign the permission set

```bash
sf org assign permset --name IR_Agent_Access --target-org my-org
```

### 4d. Get the Connected App Client ID

After deploy, go to Setup → App Manager → OpenClaw Agent → View and copy the **Consumer Key**. You'll need this for the frontend `.env` file (step 11).

> The Connected App deploys with `isPkceRequired: true` and `OpenID` scope. Callback URLs include both `https://login.salesforce.com/services/oauth2/callback` and `http://localhost:5173/callback`. No manual Connected App configuration needed.

---

## 5. Salesforce — Load Seed Data

Run the three seed scripts **in order**. Script 1 must complete before 2, and 2 before 3.

```bash
sf apex run --file scripts/apex/seed-01-accounts-companies.apex --target-org my-org
sf apex run --file scripts/apex/seed-02-coverage-watchlist-notes.apex --target-org my-org
sf apex run --file scripts/apex/seed-03-audit-logs.apex --target-org my-org
```

**What gets created:**
- Script 1: Cleans all existing IR_* data, creates 25 accounts (with `BillingCountry`), 40 contacts, 30 companies
- Script 2: Creates 30 coverage records, 20 watchlist items, 5 research briefs
- Script 3: Creates 50 audit log entries

Scripts are idempotent — safe to re-run. Script 1 deletes all IR_* records first.

> **Do NOT use `scripts/apex/seed-data.apex`** — it's a reference copy that exceeds the anonymous Apex 100K character limit. Always use the split scripts.

### Verify seed data

```bash
sf data query --query "SELECT COUNT() FROM IR_Company__c" --target-org my-org
# Expected: 30

sf data query --query "SELECT COUNT() FROM Account WHERE BillingCountry != null" --target-org my-org
# Expected: 25
```

---

## 6. AWS — Deploy MCP Servers (SAM)

### 6a. Configure SAM

```bash
cp aws/samconfig.toml.example aws/samconfig.toml
```

Edit `aws/samconfig.toml` — replace all `YOUR_*` placeholders with real API keys.

### 6b. Build and deploy

```bash
cd aws
sam build
sam deploy
```

> `sam build` requires Docker running and Python 3.10 available. If you see `Runtime python3.10 is not supported`, install Python 3.10 and ensure it's on your PATH.

### 6c. Capture outputs

Note the CloudFormation outputs:
- `ApiGatewayUrl` — this is your `MCP_GATEWAY_URL`
- `ApiKeyId` — use this to retrieve the API key value

```bash
aws apigateway get-api-key --api-key <ApiKeyId> --include-value --query 'value' --output text
```

### 6d. Test the MCP servers

```bash
# Health check (each should return server info JSON)
curl -H "x-api-key: YOUR_KEY" https://YOUR_URL/prod/sec-edgar
curl -H "x-api-key: YOUR_KEY" https://YOUR_URL/prod/market-data
curl -H "x-api-key: YOUR_KEY" https://YOUR_URL/prod/news-search

# Tool catalog
curl -H "x-api-key: YOUR_KEY" -X POST https://YOUR_URL/prod/market-data/tools/list

# Tool call
curl -H "x-api-key: YOUR_KEY" -X POST https://YOUR_URL/prod/market-data/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name": "get_quote", "arguments": {"symbol": "AAPL"}}'
```

### 6e. Update Secrets Manager

Now update the secret with the MCP Gateway URL and API key:

```bash
# Fetch current secret, add MCP values, update
aws secretsmanager update-secret \
  --secret-id openclaw-fsi-secrets \
  --region us-east-1 \
  --secret-string "$(aws secretsmanager get-secret-value --secret-id openclaw-fsi-secrets --query SecretString --output text | python3 -c "
import sys, json
s = json.load(sys.stdin)
s['MCP_GATEWAY_URL'] = 'https://YOUR_API_GATEWAY_ID.execute-api.us-east-1.amazonaws.com/prod'
s['MCP_API_KEY'] = 'YOUR_ACTUAL_API_KEY'
print(json.dumps(s))
")"
```

---

## 7. AWS — Deploy Bedrock Guardrails

```bash
aws cloudformation deploy \
  --template-file aws/guardrails/bedrock-guardrails.yaml \
  --stack-name openclaw-006-guardrails \
  --region us-east-1
```

This creates a Bedrock Guardrail with:
- **PII masking** — names, emails, phones anonymized; SSN, credit cards, bank accounts blocked
- **Financial identifiers** — CUSIP, ISIN, SWIFT codes, account numbers anonymized
- **Content filtering** — hate, insults, sexual content, violence, prompt attacks
- **Denied topics** — insider trading requests, unauthorized trading, audit log deletion

Note the `GuardrailId` from the stack outputs — referenced in Bedrock InvokeModel calls.

---

## 8. OpenClaw — Install and Configure

### 8a. Install OpenClaw

Follow the OpenClaw installation guide to install the CLI and Gateway.

### 8b. Configure the agent

```bash
mkdir -p ~/.openclaw/skills
cp openclaw/openclaw.json ~/.openclaw/openclaw.json
cp -r openclaw/skills/* ~/.openclaw/skills/
```

### 8c. Set environment variables

Edit `~/.openclaw/openclaw.json` — replace all `${VAR_NAME}` placeholders with real values:

| Placeholder | Value |
|------------|-------|
| `${OPENCLAW_GATEWAY_TOKEN}` | Generate: `openssl rand -hex 32` |
| `${SF_INSTANCE_URL}` | Your Salesforce org URL |
| `${SF_ACCESS_TOKEN}` | From `sf org display --target-org my-org --json` → `result.accessToken` |
| `${MCP_GATEWAY_URL}` | API Gateway URL from step 6c |
| `${MCP_API_KEY}` | API key value from step 6c |
| `${TAVILY_API_KEY}` | Your Tavily key |
| `${ALPHA_VANTAGE_API_KEY}` | Your Alpha Vantage key |
| `${LANGFUSE_SECRET_KEY}` | From Langfuse dashboard |
| `${LANGFUSE_PUBLIC_KEY}` | From Langfuse dashboard |
| `${LANGFUSE_BASE_URL}` | `https://us.cloud.langfuse.com` |

### 8d. Start the Gateway

```bash
openclaw gateway start
```

Verify:
```bash
curl http://localhost:18789/ping
# → {"status": "healthy"}
```

---

## 9. MCP Bridge Setup

The MCP servers run on Lambda behind API Gateway (HTTP). OpenClaw expects MCP servers via stdio or WebSocket depending on your version.

### Option A: Native HTTP (if supported by your OpenClaw version)

The `openclaw.json` config already has HTTP endpoints configured with `"type": "http"`. If your OpenClaw version supports HTTP MCP servers natively, no bridge is needed.

### Option B: stdio bridge

If your OpenClaw version requires stdio MCP servers, use the REST-to-stdio bridge:

```bash
node mcp-rest-bridge.mjs \
  --url https://YOUR_API_GATEWAY_URL/prod/market-data \
  --api-key YOUR_MCP_API_KEY
```

Update `openclaw.json` to point MCP servers to the stdio bridge instead of HTTP URLs.

---

## 10. Pipeline Test

### 10a. Set environment variables

```bash
export SF_INSTANCE_URL=https://YOUR_ORG.my.salesforce.com
export MCP_GATEWAY_URL=https://YOUR_API_GATEWAY_ID.execute-api.us-east-1.amazonaws.com/prod
export MCP_API_KEY=YOUR_MCP_API_KEY
export LANGFUSE_SECRET_KEY=sk-lf-XXXXX
export LANGFUSE_PUBLIC_KEY=pk-lf-XXXXX
export LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
```

`SF_ACCESS_TOKEN` is auto-fetched from `sf org display` if not set. The script uses `SF_TARGET_ORG` env var (defaults to `my-org`) to determine which org alias to query.

### 10b. Install Python dependencies

```bash
pip install -r openclaw/skills/fsi-research/requirements.txt
```

### 10c. Run

```bash
python3 scripts/test-pipeline.py
```

Expected: 23 stages complete, rating + target price for NVDA, 3 HITL gates auto-approved.

> If you used a different org alias (not `my-org`), set `export SF_TARGET_ORG=your-alias` before running.

---

## 11. Frontend

### 11a. Install and configure

```bash
cd frontend
npm install
cp .env.example .env
```

Edit `.env`:

```env
VITE_OPENCLAW_GATEWAY_URL=ws://localhost:18789
VITE_OPENCLAW_GATEWAY_TOKEN=<your gateway token from step 8>
VITE_SF_LOGIN_URL=https://login.salesforce.com
VITE_SF_CLIENT_ID=<Consumer Key from step 4d>
VITE_SF_REDIRECT_URI=http://localhost:5173/callback
VITE_LANGFUSE_HOST=https://us.cloud.langfuse.com
```

### 11b. Build and verify

```bash
npx tsc --noEmit   # Should exit 0 with no errors
npm run build       # Production build
```

### 11c. Run locally

```bash
npm run dev
```

Open http://localhost:5173. Click "Sign in with Salesforce" — uses OAuth2 PKCE via the Connected App deployed in step 4.

Stack: React 19 + TypeScript + Vite 6 + Zustand 5 + Recharts + SLDS. Frontend connects to OpenClaw via WebSocket — does NOT call Salesforce APIs directly for agent queries.

---

## 12. Evaluation Suite

### 12a. Install

```bash
cd evaluation
pip install -r requirements.txt
```

### 12b. Configure

Edit `eval_config.yaml` — replace `${VAR_NAME}` placeholders. Gateway URL should point to your running OpenClaw Gateway (default: `http://localhost:18789`).

### 12c. Run

```bash
python run_suite.py --level L1   # Quick: L1 queries only
python run_suite.py               # Full: 150-query matrix
```

Requires OpenClaw Gateway running (step 8d) and `OPENCLAW_GATEWAY_TOKEN` set.

Scoring thresholds (from `eval_config.yaml`):

| Level | Threshold | Description |
|-------|-----------|-------------|
| L1 | 4.5 | Simple lookups (price, holdings) |
| L2 | 4.0 | Multi-step queries (compare, summarize) |
| L3 | 3.5 | Research briefs (full pipeline) |
| L4 | 3.0 | Complex analysis (DCF, Monte Carlo) |
| L5 | 3.5 | Multi-client, cross-portfolio |
| Edge | refusal | Compliance boundaries (MNPI, unauthorized) |

---

## 13. AgentCore Deployment (Optional)

For production on AWS Bedrock AgentCore (serverless container hosting):

### 13a. Prerequisites

- Docker running locally
- ECR repository created: `openclaw-agentcore`
- AgentCore execution role with Bedrock + Secrets Manager permissions
- All secrets populated in `openclaw-fsi-secrets` (step 3)

### 13b. Build and deploy

```bash
cd agentcore

# Copy OpenClaw config into build context
cp -r ../openclaw ./openclaw

# Build
docker build -t openclaw-agentcore:latest .

# Push to ECR (replace ACCOUNT_ID with your AWS account)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
docker tag openclaw-agentcore:latest ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/openclaw-agentcore:latest
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/openclaw-agentcore:latest

# Clean up
rm -rf ./openclaw
```

### 13c. Test locally first

```bash
docker compose up --build
curl http://localhost:8080/ping
# → {"status": "healthy"}
```

> `agentcore/buildspec.yml` is intentionally not committed — it contains an ECR URI with an AWS account ID. Use the manual commands above or create your own buildspec.

---

## 14. Troubleshooting

### Seed Data Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `FIELD_INTEGRITY_EXCEPTION: BillingState` | Org has State/Country picklists enabled, values don't match | Setup → State and Country/Territory Picklists. Disable them or ensure seed data state names match your picklist values. |
| `INVALID_FIELD: Description__c` | Old seed script references a field not on IR_Company__c | Use the split scripts (`seed-01`, `seed-02`, `seed-03`). They do NOT reference `Description__c`. |
| `Script too large` | `seed-data.apex` exceeds anonymous Apex 100K limit | Use the split scripts. |

### SAM Build / Deploy Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Runtime python3.10 is not supported` | Python 3.10 not installed | `brew install python@3.10`. Verify: `python3.10 --version` |
| `sam build` Docker error | Docker not running | Start Docker Desktop. |
| `sam deploy` changeset fails | First deploy needs guided mode | Run `sam deploy --guided` the first time. |
| API key not working | Key not associated with usage plan | Check `ApiKeyId` in CloudFormation outputs. |

### Pipeline Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Missing env vars: [...]` | Required env vars not set | Set all 6 required env vars (step 10a). |
| `sf org display` fails | Wrong org alias | Set `SF_TARGET_ORG=your-alias` or set `SF_ACCESS_TOKEN` directly. |
| `ModuleNotFoundError: pipeline` | Wrong working directory | Run from project root: `python3 scripts/test-pipeline.py` |
| Bedrock `AccessDeniedException` | Model access not enabled | Enable models in Bedrock Console → Model access. |
| `ThrottlingException` | Bedrock rate limit | Wait and retry, or request quota increase. |

### Frontend Errors

| Error | Cause | Fix |
|-------|-------|-----|
| OAuth redirect fails | Wrong Client ID | Copy Consumer Key from Setup → App Manager → OpenClaw Agent → View. |
| WebSocket refused | Gateway not running | Start gateway (step 8d). Check `VITE_OPENCLAW_GATEWAY_URL`. |
| CORS error | Frontend origin mismatch | Update `FrontendOrigin` in `samconfig.toml`, redeploy SAM. |

### Model IDs

If Bedrock model IDs change, update:
- `openclaw/openclaw.json` — `models.providers.bedrock.models[].id` and `agents.list[].model`
- `evaluation/eval_config.yaml` — `judge_model`

Current IDs: `us.anthropic.claude-sonnet-4-6`, `us.anthropic.claude-haiku-4-5-20251001-v1:0`

### Ad-hoc Fields (Dev Org Only — NOT in Source)

These fields exist on the original dev org but are NOT in source metadata. A fresh deploy will not create them. No code depends on them.

| Object | Field | Status |
|--------|-------|--------|
| IR_Audit_Log__c | Duration_Ms__c | Orphaned |
| IR_Audit_Log__c | Platform__c | Orphaned |
| IR_Company__c | Earnings_Date__c | Orphaned — pipeline uses IR_Watchlist__c.Earnings_Date__c |
| IR_Company__c | Last_Price__c | Orphaned |
| IR_Research_Note__c | Data_Sources__c | Orphaned |
| IR_Research_Note__c | Status__c | Only in deprecated seed-data.apex |
| IR_Watchlist__c | Analyst__c | Orphaned |

---

## 15. Project Structure

```
force-app/              SF metadata (5 objects, 39 fields, Connected App, Permission Set)
aws/
  sam-template.yaml      SAM template — 3 Lambda MCP servers, API Gateway, DLQ
  samconfig.toml.example Config template — copy and fill in API keys
  mcp-servers/           Lambda code: sec-edgar/, market-data/, news-search/, shared/
  guardrails/            Bedrock Guardrails CloudFormation (PII, toxicity, denied topics)
openclaw/
  openclaw.json          Agent config — models, MCP servers, skills, env vars
  skills/                6 skills: fsi-research, financial-analysis, salesforce-crm,
                         audit-logging, compliance-screening, mulesoft-api
agentcore/               Docker container for Bedrock AgentCore deployment
  Dockerfile             Multi-stage: node:22-slim + OpenClaw + adapter
  adapter.js             HTTP ↔ WebSocket bridge (AgentCore speaks HTTP, OpenClaw speaks WS)
  agentcore-config.yaml  AgentCore deployment config (secrets from Secrets Manager)
frontend/                React 19 SPA (TypeScript, Vite 6, Zustand 5, Recharts, SLDS)
evaluation/              150-query test suite with LLM-as-Judge scoring
scripts/
  apex/                  Seed data — 3 idempotent scripts (run in order)
  test-pipeline.py       Runs the full 23-stage pipeline for NVDA
docs/                    Design docs, architecture, security audit, tech stack
```

---

## 16. Docs

- [Design Doc](docs/design-doc.md) — full architecture, 6 phases, 71 tasks
- [Tech Stack](docs/006-tech-stack-assessment.md) — every technology choice justified
- [150 Queries](docs/006-query-matrix-expanded.md) — test matrix across 6 personas
- [Security Audit](docs/006-security-audit.md) — 15 findings, OWASP mapped
- [Data & Eval](docs/006-data-sources-and-evaluation-strategy.md) — 7 data layers, 3-layer eval
- [Frontend Assessment](docs/006-frontend-assessment-openclaw.md) — React + OpenClaw integration

---

## What Requires Manual Steps

| Step | Automated? | Manual Action Required |
|------|-----------|----------------------|
| SF metadata deploy | ✅ `sf project deploy start` | None |
| Seed data | ✅ 3 Apex scripts | None |
| MCP servers | ✅ `sam build` + `sam deploy` | Fill `samconfig.toml` with API keys |
| Guardrails | ✅ CloudFormation | None |
| OpenClaw config | ❌ | Copy `openclaw.json`, replace 10 placeholders |
| Connected App Client ID | ❌ | Copy from SF Setup after deploy |
| Secrets Manager | ❌ | Create secret with 10 key-value pairs |
| AgentCore (ECR push) | ❌ | Docker build + push (account-specific) |
| Slack/WhatsApp channels | ❌ | Channel tokens are org-specific, not in git |
| Bedrock model access | ❌ | Enable models in AWS Console |
