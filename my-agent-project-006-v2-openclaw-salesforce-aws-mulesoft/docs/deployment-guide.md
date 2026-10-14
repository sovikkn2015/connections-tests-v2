# Project 006: Complete Deployment Guide

> From zero to a working FSI Investment Research Agent. Every step, every command, every gotcha.
>
> Last updated: 2026-04-09

---

## Table of Contents

1. [What Gets Deployed (Architecture)](#1-what-gets-deployed-architecture)
2. [Prerequisites](#2-prerequisites)
3. [Step-by-Step Deployment](#3-step-by-step-deployment)
4. [Environment Variables Reference](#4-environment-variables-reference)
5. [Troubleshooting](#5-troubleshooting)
6. [What's NOT Automated](#6-whats-not-automated)
7. [Cleanup](#7-cleanup)

---

## 1. What Gets Deployed (Architecture)

### System Overview

An analyst types "Deep dive on NVIDIA ahead of earnings" in a browser. They get back a
compliance-screened research brief with rating, target price, thesis, DCF valuation, and
Monte Carlo simulation. Every step is auditable for FINRA.

### Architecture Diagram

```
User (Browser)
  |
  |  HTTPS (static assets)
  v
CloudFront ---- S3 Bucket (React SPA: React 19 + Vite 6 + Zustand 5 + SLDS)
  |
  |  WebSocket (wss://)
  v
AgentCore API Gateway (WebSocket endpoint)
  |
  v
AgentCore Runtime (Firecracker microVM)
  |-- OpenClaw Gateway (port 18789)
  |     |-- FSI Research Agent (default, Sonnet 4.6)
  |     +-- FSI Research Agent Fast (Haiku 4.5, L1-L2 queries)
  |
  |-- Bedrock LLM
  |     |-- Claude Sonnet 4.6  (us.anthropic.claude-sonnet-4-6)
  |     +-- Claude Haiku 4.5   (us.anthropic.claude-haiku-4-5-20251001-v1:0)
  |
  |-- Bedrock Guardrails (CloudFormation)
  |     PII masking | toxicity | denied topics | prompt injection
  |
  |-- MCP Servers (Lambda + API Gateway, SAM stack)
  |     |-- SEC EDGAR    (10-K, 10-Q, 8-K filings)
  |     |-- Market Data  (Alpha Vantage: quotes, history, fundamentals)
  |     +-- News Search  (Tavily: financial news, sentiment)
  |
  |-- Salesforce CRM (REST API, OAuth2)
  |     |-- IR_Company__c        (30 companies)
  |     |-- IR_Coverage__c       (30 analyst assignments)
  |     |-- IR_Watchlist__c      (20 watchlist items)
  |     |-- IR_Research_Note__c  (5+ research briefs)
  |     |-- IR_Audit_Log__c      (50+ FINRA audit entries)
  |     |-- Account              (25 institutional accounts)
  |     +-- Contact              (40 contacts)
  |
  |-- OpenClaw Skills (6)
  |     |-- fsi-research         (AutoResearchClaw 23-stage pipeline)
  |     |-- financial-analysis   (DCF, comps, Monte Carlo, stress test)
  |     |-- salesforce-crm       (SOQL queries, record CRUD)
  |     |-- audit-logging        (FINRA audit trail -> IR_Audit_Log__c)
  |     |-- compliance-screening (MNPI, suitability, restricted list)
  |     +-- mulesoft-api         (trade/wire execution with HITL)
  |
  +-- Langfuse (observability: traces, evals, cost tracking)
      https://us.cloud.langfuse.com (or self-hosted)
```

### What Gets Created (Resource Count)

| Layer | Resources |
|-------|-----------|
| Salesforce | 5 custom objects, 39 fields, 1 Connected App, 1 Permission Set, ~170 seed records |
| AWS Lambda | 3 functions (SEC EDGAR, Market Data, News Search), 256 MB each, Python 3.10 |
| API Gateway | 1 REST API, 9 routes (3 per MCP server), API key auth, usage plan |
| SQS | 1 dead-letter queue for Lambda errors |
| Bedrock Guardrails | 1 guardrail (9 PII entity types + 5 regex patterns, 5 content filters, 3 denied topics) |
| AgentCore | 1 runtime, 1 API Gateway (WebSocket), 1 ECR image, 1 memory resource |
| Secrets Manager | 1 secret (openclaw-fsi-secrets) with 10 key-value pairs |
| Frontend | React SPA deployed to S3 + CloudFront (or localhost for dev) |

---

## 2. Prerequisites

### Required Tools (exact versions)

| Tool | Version | Install Command | Why |
|------|---------|-----------------|-----|
| Salesforce CLI (`sf`) | 2.x | `npm install -g @salesforce/cli` | Deploy metadata, run Apex scripts, get access tokens |
| AWS CLI | 2.x | `brew install awscli` | Manage AWS resources, retrieve API keys |
| AWS SAM CLI | 1.x | `brew install aws-sam-cli` | Build and deploy Lambda MCP servers |
| AWS CDK | 2.x | `npm install -g aws-cdk` | Deploy AgentCore infrastructure |
| Node.js | 20+ | `brew install node` | Frontend build, OpenClaw Gateway, MCP bridge |
| Python | **3.10** | `brew install python@3.10` | Lambda runtime is pinned to 3.10 (SAM build) |
| Python | 3.11+ | System Python or `brew install python` | AgentCore CDK scripts, evaluation suite |
| Docker | Latest | Docker Desktop | SAM build (Lambda packaging), AgentCore container |
| Git | 2.x | `brew install git` | Clone repos |
| OpenClaw CLI | Latest | See OpenClaw installation docs | Agent runtime CLI and Gateway |
| bedrock-agentcore-toolkit | Latest | `pip install bedrock-agentcore-toolkit` | AgentCore CLI for runtime management |

> **Python version matters.** `sam build` will fail with Python 3.12+ because the SAM template pins `Runtime: python3.10`. Install Python 3.10 and ensure `python3.10` is on your PATH, or set `SAM_CLI_PYTHON_VERSION=3.10`.

### Verify installations

```bash
sf --version          # @salesforce/cli/2.x
aws --version         # aws-cli/2.x
sam --version         # SAM CLI, version 1.x
cdk --version         # 2.x
node --version        # v20+
python3.10 --version  # Python 3.10.x
docker --version      # Docker version 2x+
```

### Required Accounts and API Keys

| Credential | Where to Get It | Used By | Required? |
|-----------|----------------|---------|-----------|
| AWS Account (us-east-1) | aws.amazon.com | Lambda, API Gateway, Bedrock, AgentCore, Secrets Manager | Yes |
| Salesforce Org | developer.salesforce.com (Developer Edition) or Enterprise | CRM data, OAuth, audit trail | Yes |
| Alpha Vantage API Key | alphavantage.co/support/#api-key | Market Data MCP server | Yes |
| Tavily API Key | tavily.com | News Search MCP server | Yes |
| Langfuse Account | us.cloud.langfuse.com | Observability traces, evals, cost tracking | Recommended |

### AWS Bedrock Model Access (do this FIRST — before any other AWS step)

Enable these models in the AWS Bedrock console (us-east-1 region):

1. Go to **Bedrock Console** -> **Model access** -> **Manage model access**
2. Request access for:
   - `us.anthropic.claude-sonnet-4-6` (primary model for L3-L5 queries and pipeline stages)
   - `us.anthropic.claude-haiku-4-5-20251001-v1:0` (fast model for L1-L2 queries)
3. Wait for approval (usually instant for Anthropic models)

> **Model ID format matters.** Use `us.anthropic.claude-sonnet-4-6`, NOT `anthropic.claude-sonnet-4-6`. The `us.` prefix is required for cross-region inference in us-east-1.

---

## 3. Step-by-Step Deployment

### Step 1: Clone the Repository

```bash
git clone <repo-url>
cd my-agent-project-006-v1-openclaw-salesforce-aws
```

**Verify project structure:**

```bash
ls force-app/main/default/objects/
# Expected: IR_Audit_Log__c  IR_Company__c  IR_Coverage__c  IR_Research_Note__c  IR_Watchlist__c

ls aws/mcp-servers/
# Expected: market-data  news-search  sec-edgar  shared

ls openclaw/skills/
# Expected: audit-logging  compliance-screening  financial-analysis  fsi-research  mulesoft-api  salesforce-crm
```

**Checkpoint:** You should see 5 object directories, 4 MCP server directories, and 6 skill directories.

---

### Step 2: Salesforce — Deploy Metadata and Load Seed Data

#### 2a. Login to your Salesforce org

```bash
sf org login web --alias my-org --instance-url https://login.salesforce.com
```

A browser window opens. Log in with your Salesforce credentials. The CLI stores the auth token locally.

**Verify:**
```bash
sf org display --target-org my-org
# Should show your org ID, username, instance URL, and access token
```

#### 2b. Deploy all metadata

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

**Verify:**
```bash
sf project deploy report --target-org my-org
# Should show all components deployed successfully
```

#### 2c. Assign the permission set

```bash
sf org assign permset --name IR_Agent_Access --target-org my-org
```

#### 2d. Load seed data (run in order — script 1 before 2, 2 before 3)

```bash
sf apex run --file scripts/apex/seed-01-accounts-companies.apex --target-org my-org
sf apex run --file scripts/apex/seed-02-coverage-watchlist-notes.apex --target-org my-org
sf apex run --file scripts/apex/seed-03-audit-logs.apex --target-org my-org
```

What gets created:
- Script 1: Cleans all existing IR_* data, creates 25 accounts (with BillingCountry), 40 contacts, 30 companies
- Script 2: Creates 30 coverage records, 20 watchlist items, 5 research briefs
- Script 3: Creates 50 audit log entries

Scripts are idempotent — safe to re-run. Script 1 deletes all IR_* records first.

> **Do NOT use `scripts/apex/seed-data.apex`** — it is a reference copy that exceeds the anonymous Apex 100K character limit. Always use the three split scripts.

#### 2e. Verify seed data

```bash
sf data query --query "SELECT COUNT() FROM IR_Company__c" --target-org my-org
# Expected: 30

sf data query --query "SELECT COUNT() FROM Account WHERE BillingCountry != null" --target-org my-org
# Expected: 25

sf data query --query "SELECT COUNT() FROM IR_Coverage__c" --target-org my-org
# Expected: 30

sf data query --query "SELECT COUNT() FROM IR_Watchlist__c" --target-org my-org
# Expected: 20

sf data query --query "SELECT COUNT() FROM IR_Research_Note__c" --target-org my-org
# Expected: 5

sf data query --query "SELECT COUNT() FROM IR_Audit_Log__c" --target-org my-org
# Expected: 50
```

#### 2f. Get the Connected App Client ID

After deploy, go to **Setup -> App Manager -> OpenClaw Agent -> View** and copy the **Consumer Key**. You need this for the frontend `.env` file (Step 7).

> The Connected App deploys with `isPkceRequired: true` and `OpenID` scope. Callback URLs include both `https://login.salesforce.com/services/oauth2/callback` and `http://localhost:5173/callback`. No manual Connected App configuration needed.

**Checkpoint:** 5 objects deployed, ~170 seed records loaded, permission set assigned, Consumer Key copied.

---

### Step 3: AWS — Deploy MCP Servers (SAM)

#### 3a. Configure SAM

```bash
cd aws
cp samconfig.toml.example samconfig.toml
```

Edit `samconfig.toml` — replace all placeholder values:

```toml
version = 0.1

[default.deploy.parameters]
stack_name = "openclaw-mcp-006"
resolve_s3 = true
s3_prefix = "openclaw-mcp-006"
region = "us-east-1"
confirm_changeset = true
capabilities = "CAPABILITY_IAM"
parameter_overrides = [
    "AlphaVantageApiKey=<your-alpha-vantage-key>",
    "TavilyApiKey=<your-tavily-key>",
    "LangfuseSecretKey=<your-langfuse-secret-key>",
    "LangfusePublicKey=<your-langfuse-public-key>",
    "LangfuseBaseUrl=https://us.cloud.langfuse.com",
    "FrontendOrigin=http://localhost:5173",
]
tags = "Project=\"006-fsi\" Environment=\"production\""
```

#### 3b. Build

```bash
sam build
```

> Requires Docker running and Python 3.10 on PATH. If you see `Runtime python3.10 is not supported`, install Python 3.10: `brew install python@3.10`.

#### 3c. Deploy

```bash
sam deploy
```

For first-time deploy, use `sam deploy --guided` and accept defaults. Subsequent deploys just use `sam deploy`.

#### 3d. Capture outputs

The CloudFormation stack outputs two critical values:

```bash
# Get the API Gateway URL
aws cloudformation describe-stacks \
  --stack-name openclaw-mcp-006 \
  --query "Stacks[0].Outputs[?OutputKey=='ApiGatewayUrl'].OutputValue" \
  --output text
# Example output: https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod

# Get the API Key ID
aws cloudformation describe-stacks \
  --stack-name openclaw-mcp-006 \
  --query "Stacks[0].Outputs[?OutputKey=='ApiKeyId'].OutputValue" \
  --output text
# Example output: abc123def456

# Get the actual API key value from the ID
aws apigateway get-api-key \
  --api-key <ApiKeyId-from-above> \
  --include-value \
  --query 'value' \
  --output text
# Example output: aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890
```

**Save these two values** — you need them everywhere:
- `MCP_GATEWAY_URL` = the API Gateway URL
- `MCP_API_KEY` = the API key value

#### 3e. Test the MCP servers

```bash
# Health check — each should return server info JSON
curl -H "x-api-key: <your-key>" https://<your-url>/prod/sec-edgar
curl -H "x-api-key: <your-key>" https://<your-url>/prod/market-data
curl -H "x-api-key: <your-key>" https://<your-url>/prod/news-search

# Tool catalog — should return list of available tools with JSON schemas
curl -H "x-api-key: <your-key>" -X POST https://<your-url>/prod/market-data/tools/list

# Tool call — should return AAPL stock quote
curl -H "x-api-key: <your-key>" -X POST https://<your-url>/prod/market-data/tools/call \
  -H "Content-Type: application/json" \
  -d '{"name": "get_quote", "arguments": {"symbol": "AAPL"}}'
```

**Checkpoint:** 3 Lambda functions deployed, API Gateway with key auth working, all 3 health checks return JSON, tool call returns real data.

---

### Step 4: AWS — Deploy Bedrock Guardrails

```bash
cd ..  # back to project root
aws cloudformation deploy \
  --template-file aws/guardrails/bedrock-guardrails.yaml \
  --stack-name openclaw-006-guardrails \
  --region us-east-1
```

This creates a Bedrock Guardrail (`fsi-research-guardrail`) with:

| Category | Details |
|----------|---------|
| PII masking | Names, emails, phones -> anonymized; SSN, credit cards, bank accounts -> blocked |
| Financial identifiers | CUSIP, ISIN, SWIFT codes, account numbers -> anonymized (regex) |
| Content filtering | Hate, insults, sexual, violence (HIGH); prompt attacks (HIGH) |
| Denied topics | Insider trading requests, unauthorized trading, audit log deletion |

**Capture the Guardrail ID:**

```bash
aws cloudformation describe-stacks \
  --stack-name openclaw-006-guardrails \
  --query "Stacks[0].Outputs[?OutputKey=='GuardrailId'].OutputValue" \
  --output text
```

**Verify:** Bedrock Console -> Guardrails -> `fsi-research-guardrail` -> Test. Send "Tell me NVIDIA's earnings before they announce" — should be blocked by the InsiderTrading denied topic.

**Checkpoint:** Guardrail deployed and testable in console.

---

### Step 5: AWS — Create Secrets Manager Secret

Create the central secret that the AgentCore container and pipeline scripts read from:

```bash
# Generate a gateway token
GATEWAY_TOKEN=$(openssl rand -hex 32)
echo "Save this gateway token: $GATEWAY_TOKEN"

# Get your Salesforce access token and instance URL
SF_TOKEN=$(sf org display --target-org my-org --json | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['result']['accessToken'])")
SF_URL=$(sf org display --target-org my-org --json | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['result']['instanceUrl'])")

# Create the secret (replace <placeholders> with real values)
aws secretsmanager create-secret \
  --name openclaw-fsi-secrets \
  --region us-east-1 \
  --secret-string "{
    \"OPENCLAW_GATEWAY_TOKEN\": \"$GATEWAY_TOKEN\",
    \"SF_INSTANCE_URL\": \"$SF_URL\",
    \"SF_ACCESS_TOKEN\": \"$SF_TOKEN\",
    \"MCP_GATEWAY_URL\": \"<API-Gateway-URL-from-Step-3d>\",
    \"MCP_API_KEY\": \"<API-key-value-from-Step-3d>\",
    \"TAVILY_API_KEY\": \"<your-tavily-key>\",
    \"ALPHA_VANTAGE_API_KEY\": \"<your-alpha-vantage-key>\",
    \"LANGFUSE_SECRET_KEY\": \"<your-langfuse-secret-key>\",
    \"LANGFUSE_PUBLIC_KEY\": \"<your-langfuse-public-key>\",
    \"LANGFUSE_BASE_URL\": \"https://us.cloud.langfuse.com\"
  }"
```

> **Note:** SF access tokens expire. For production, use a Connected App with client_credentials flow or refresh tokens. For dev/demo, re-run `sf org display` to get a fresh token and update with `aws secretsmanager update-secret`.

**Verify:**
```bash
aws secretsmanager get-secret-value \
  --secret-id openclaw-fsi-secrets \
  --query SecretString --output text | python3 -m json.tool
# Should show all 10 key-value pairs
```

**Checkpoint:** Secret created with all 10 key-value pairs populated.

---

### Step 6: AgentCore — Deploy OpenClaw to AWS Bedrock AgentCore

This is the production deployment. OpenClaw runs in a Firecracker microVM on AgentCore — serverless, zero idle cost, per-user isolation.

#### 6a. Clone the AWS sample repo

```bash
cd ~  # or wherever you keep repos
git clone https://github.com/aws-samples/sample-host-openclaw-on-amazon-bedrock-agentcore.git
cd sample-host-openclaw-on-amazon-bedrock-agentcore
```

#### 6b. Configure CDK

```bash
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
export CDK_DEFAULT_REGION=us-east-1
```

Edit `cdk.json` — set your account, region, and model:
```json
{
  "account": "<your-aws-account-id>",
  "region": "us-east-1",
  "default_model_id": "us.anthropic.claude-sonnet-4-6"
}
```

#### 6c. Install CDK dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 6d. Bootstrap CDK (first time only per account/region)

```bash
cdk bootstrap aws://$CDK_DEFAULT_ACCOUNT/$CDK_DEFAULT_REGION
```

#### 6e. Deploy (3-phase automated script)

```bash
./scripts/deploy.sh
```

The deploy script runs 3 phases:
1. **CDK foundation** — VPC, security groups, ECR repo, IAM roles
2. **AgentCore Toolkit** — registers the runtime, builds and pushes the bridge container
3. **CDK dependent** — API Gateway (WebSocket), CloudFront, observability

This takes 15-30 minutes on first run.

> **VPC EIP limit:** If your account hits the Elastic IP limit (default: 5), see [Troubleshooting - EIP Limit Error](#eip-limit-error).

#### 6f. Store the gateway token

```bash
aws secretsmanager update-secret \
  --secret-id openclaw/gateway-token \
  --secret-string "$(openssl rand -hex 32)" \
  --region us-east-1
```

#### 6g. Copy Project 006 skills into the bridge container

The AWS sample deploys a generic OpenClaw container. You need to add the 006-specific configuration and skills:

```bash
# From the AWS sample repo root — copy 006 skills and config
PROJECT_006_PATH=/path/to/my-agent-project-006-v1-openclaw-salesforce-aws

cp -r $PROJECT_006_PATH/openclaw/skills/* bridge/skills/
cp $PROJECT_006_PATH/openclaw/openclaw.json bridge/openclaw.json
cp $PROJECT_006_PATH/openclaw/mcp-rest-bridge.mjs bridge/mcp-rest-bridge.mjs
```

#### 6h. Rebuild and push the container to ECR

```bash
# Get ECR login
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  $CDK_DEFAULT_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com

# Build the container
docker build -t openclaw-agentcore:latest bridge/

# Tag and push
docker tag openclaw-agentcore:latest \
  $CDK_DEFAULT_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/bedrock-agentcore-openclaw_agent:latest
docker push \
  $CDK_DEFAULT_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/bedrock-agentcore-openclaw_agent:latest
```

#### 6i. Wire MCP servers to AgentCore

The container reads environment variables from Secrets Manager at startup. The `openclaw.json` config references `${MCP_GATEWAY_URL}` and `${MCP_API_KEY}` which resolve from the `openclaw-fsi-secrets` secret created in Step 5. Ensure those values are populated.

#### 6j. Verify

```bash
# First invocation triggers cold start — takes ~1-2 minutes
agentcore invoke '{"prompt": "Hello", "action": "chat", "userId": "test", "actorId": "test:1"}'
```

> **Lazy init:** The first invocation after deploy will show `openclawReady: false` while the container boots OpenClaw Gateway internally. Wait 1-2 minutes and retry. Subsequent invocations are fast.

**Checkpoint:** AgentCore runtime registered, container pushed to ECR, first invocation returns a response from the FSI Research Agent.

---

### Step 7: Frontend — Build and Deploy

#### 7a. Install dependencies

```bash
cd my-agent-project-006-v1-openclaw-salesforce-aws/frontend
npm install
```

#### 7b. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
VITE_OPENCLAW_GATEWAY_URL=ws://localhost:18789
VITE_OPENCLAW_GATEWAY_TOKEN=<your-gateway-token-from-Step-5>
VITE_SF_LOGIN_URL=https://login.salesforce.com
VITE_SF_CLIENT_ID=<Consumer-Key-from-Step-2f>
VITE_SF_REDIRECT_URI=http://localhost:5173/callback
VITE_LANGFUSE_HOST=https://us.cloud.langfuse.com
```

For AgentCore production deployment, change the gateway URL to the WebSocket endpoint:
```env
VITE_OPENCLAW_GATEWAY_URL=wss://<AgentCore-API-Gateway-URL-from-Step-6>
```

#### 7c. Type check and build

```bash
npx tsc --noEmit   # Type check — should exit 0 with no errors
npm run build       # Production build -> frontend/dist/
```

#### 7d. Run locally (development)

```bash
npm run dev
```

Open http://localhost:5173. Click "Sign in with Salesforce" — uses OAuth2 PKCE via the Connected App deployed in Step 2.

Stack: React 19 + TypeScript + Vite 6 + Zustand 5 + Recharts + SLDS. Frontend connects to OpenClaw via WebSocket — does NOT call Salesforce APIs directly for agent queries.

#### 7e. Deploy to S3/CloudFront (production)

```bash
# Create S3 bucket for static hosting
aws s3 mb s3://006-fsi-research-frontend --region us-east-1

# Upload the build output
aws s3 sync frontend/dist/ s3://006-fsi-research-frontend/ --delete

# Create CloudFront distribution pointing to the S3 bucket:
# - Default root object: index.html
# - Custom error response: 403 -> /index.html (HTTP 200) for SPA routing
# - Custom error response: 404 -> /index.html (HTTP 200) for SPA routing
```

> If AgentCore CDK already created a CloudFront distribution, use that instead of creating a new one.

**Checkpoint:** Frontend loads in browser, Salesforce OAuth login works, WebSocket connects to OpenClaw Gateway.

---

### Step 8: Verify End-to-End

#### 8a. Quick smoke test (via frontend)

1. Open the frontend (http://localhost:5173 or CloudFront URL)
2. Sign in with Salesforce
3. Type: `Who covers NVIDIA?`
4. Expected: Agent queries Salesforce CRM via the salesforce-crm skill, returns coverage data from IR_Coverage__c

#### 8b. MCP server integration test

Type: `What is NVIDIA's current stock price?`

Expected: Agent calls Market Data MCP server -> Lambda -> Alpha Vantage -> returns real-time quote.

#### 8c. Multi-source test

Type: `What are the latest SEC filings for Apple?`

Expected: Agent calls SEC EDGAR MCP server -> Lambda -> EDGAR API -> returns recent 10-K/10-Q/8-K filings.

#### 8d. Full pipeline test (via script)

```bash
cd my-agent-project-006-v1-openclaw-salesforce-aws

# Set environment variables
export SF_INSTANCE_URL=<your-sf-instance-url>
export MCP_GATEWAY_URL=<your-api-gateway-url>
export MCP_API_KEY=<your-mcp-api-key>
export LANGFUSE_SECRET_KEY=<your-langfuse-secret-key>
export LANGFUSE_PUBLIC_KEY=<your-langfuse-public-key>
export LANGFUSE_BASE_URL=https://us.cloud.langfuse.com

# Install Python deps for the pipeline
pip install -r openclaw/skills/fsi-research/requirements.txt

# Run the 23-stage AutoResearchClaw pipeline for NVDA
python3 scripts/test-pipeline.py
```

Expected: 23 stages complete, rating + target price for NVDA, 3 HITL gates auto-approved.

> If you used a different org alias (not `my-org`), set `export SF_TARGET_ORG=your-alias` before running.

#### 8e. Evaluation suite (optional but recommended)

```bash
cd evaluation
pip install -r requirements.txt

# Quick test — L1 queries only
python run_suite.py --level L1

# Full test — 150-query matrix across 6 personas
python run_suite.py
```

Scoring thresholds (from `eval_config.yaml`):

| Level | Threshold | Description |
|-------|-----------|-------------|
| L1 | 4.5 | Simple lookups (price, holdings) |
| L2 | 4.0 | Multi-step queries (compare, summarize) |
| L3 | 3.5 | Research briefs (full pipeline) |
| L4 | 3.0 | Complex analysis (DCF, Monte Carlo) |
| L5 | 3.5 | Multi-client, cross-portfolio |
| Edge | refusal | Compliance boundaries (MNPI, unauthorized) |

**Checkpoint:** End-to-end flow works. CRM queries return data, MCP servers respond, pipeline completes, evaluation scores meet thresholds.

---

## 4. Environment Variables Reference

### Every variable, where it comes from, and where it is used

| Variable | Value / Source | Used In | Required? |
|----------|---------------|---------|-----------|
| `OPENCLAW_GATEWAY_TOKEN` | Generate: `openssl rand -hex 32` | Secrets Manager, frontend `.env`, eval config | Yes |
| `SF_INSTANCE_URL` | From `sf org display` -> `instanceUrl` | Secrets Manager, `openclaw.json`, pipeline scripts | Yes |
| `SF_ACCESS_TOKEN` | From `sf org display --json` -> `result.accessToken` | Secrets Manager, `openclaw.json`, pipeline scripts | Yes |
| `SF_TARGET_ORG` | Your SF CLI org alias (default: `my-org`) | Pipeline test script (`test-pipeline.py`) | No (defaults to `my-org`) |
| `MCP_GATEWAY_URL` | SAM stack output `ApiGatewayUrl` | Secrets Manager, `openclaw.json`, pipeline scripts | Yes |
| `MCP_API_KEY` | Retrieved via `aws apigateway get-api-key` | Secrets Manager, `openclaw.json`, pipeline scripts | Yes |
| `ALPHA_VANTAGE_API_KEY` | From alphavantage.co/support/#api-key | `samconfig.toml` (SAM parameter), Secrets Manager | Yes |
| `TAVILY_API_KEY` | From tavily.com | `samconfig.toml` (SAM parameter), Secrets Manager | Yes |
| `LANGFUSE_SECRET_KEY` | From Langfuse dashboard -> Settings -> API Keys | `samconfig.toml`, Secrets Manager, eval config | Recommended |
| `LANGFUSE_PUBLIC_KEY` | From Langfuse dashboard -> Settings -> API Keys | `samconfig.toml`, Secrets Manager, eval config | Recommended |
| `LANGFUSE_BASE_URL` | `https://us.cloud.langfuse.com` (or self-hosted URL) | `samconfig.toml`, Secrets Manager, eval config | Recommended |
| `VITE_OPENCLAW_GATEWAY_URL` | `ws://localhost:18789` (dev) or `wss://<agentcore-url>` (prod) | Frontend `.env` | Yes |
| `VITE_OPENCLAW_GATEWAY_TOKEN` | Same as `OPENCLAW_GATEWAY_TOKEN` | Frontend `.env` | Yes |
| `VITE_SF_LOGIN_URL` | `https://login.salesforce.com` | Frontend `.env` | Yes |
| `VITE_SF_CLIENT_ID` | Connected App Consumer Key (from SF Setup -> App Manager) | Frontend `.env` | Yes |
| `VITE_SF_REDIRECT_URI` | `http://localhost:5173/callback` (dev) or production URL | Frontend `.env` | Yes |
| `VITE_LANGFUSE_HOST` | `https://us.cloud.langfuse.com` | Frontend `.env` | No |
| `CDK_DEFAULT_ACCOUNT` | From `aws sts get-caller-identity --query Account` | AgentCore CDK deploy | Yes (for AgentCore) |
| `CDK_DEFAULT_REGION` | `us-east-1` | AgentCore CDK deploy | Yes (for AgentCore) |

### Where each config file lives

| Config File | Location | Contains |
|-------------|----------|----------|
| `samconfig.toml` | `aws/samconfig.toml` | SAM deploy params: API keys, Langfuse keys, frontend origin |
| `openclaw.json` | `openclaw/openclaw.json` | Agent config: models, MCP servers, skills, env var refs |
| Frontend `.env` | `frontend/.env` | Vite env vars: gateway URL/token, SF OAuth, Langfuse |
| `eval_config.yaml` | `evaluation/eval_config.yaml` | Eval suite: gateway URL/token, judge model, thresholds |
| Secrets Manager | AWS `openclaw-fsi-secrets` | All runtime secrets (10 key-value pairs) |
| `cdk.json` | AgentCore sample repo root | AWS account, region, default model ID |

### Variable flow diagram

```
You generate/obtain credentials
        |
        v
samconfig.toml -----> SAM deploy -----> Lambda env vars (API keys, Langfuse)
        |
        v
Secrets Manager -----> AgentCore container -----> openclaw.json (runtime resolution)
        |
        v
frontend/.env -----> Vite build -----> Browser (VITE_* vars baked into JS bundle)
        |
        v
eval_config.yaml -----> run_suite.py -----> Langfuse traces + scores
```

---

## 5. Troubleshooting

Every error encountered during deployment and how to fix it.

---

### EIP Limit Error

**Error:** `CREATE_FAILED: VpcStack - The maximum number of addresses has been reached` or similar EIP quota error during AgentCore CDK deploy.

**Cause:** AWS accounts default to 5 Elastic IPs per region. The AgentCore VPC stack requests new EIPs.

**Fix (Option A — increase quota):**
```bash
aws service-quotas request-service-quota-increase \
  --service-code ec2 \
  --quota-code L-0263D0A3 \
  --desired-value 10 \
  --region us-east-1
```
Wait for approval (usually minutes), then retry the deploy.

**Fix (Option B — import existing VPC):**
Edit `stacks/vpc_stack.py` in the AgentCore sample repo to use an existing VPC:
```python
vpc = ec2.Vpc.from_lookup(self, "ExistingVpc", vpc_id="vpc-xxxxxxxx")
```

---

### Python 3.10 Requirement for SAM

**Error:** `Runtime python3.10 is not supported` during `sam build`.

**Cause:** The SAM template pins `Runtime: python3.10`. SAM CLI needs Python 3.10 installed to build Lambda packages.

**Fix:**
```bash
brew install python@3.10
python3.10 --version   # verify
export SAM_CLI_PYTHON_VERSION=3.10   # if SAM still can't find it
sam build
```

> Python 3.11+ and 3.12+ will NOT work for `sam build`. The Lambda runtime is pinned to 3.10.

---

### BillingCountry / BillingState Picklist Error in Seed Data

**Error:** `FIELD_INTEGRITY_EXCEPTION: BillingState: value not valid for the field` during seed script execution.

**Cause:** Your Salesforce org has State and Country/Territory Picklists enabled. The seed data uses free-text state names that may not match picklist values.

**Fix (Option A — disable picklists):**
Setup -> State and Country/Territory Picklists -> Disable.

**Fix (Option B — use picklist codes):**
The split seed scripts already use standard country/state codes. If you still get errors, check your org's picklist configuration and update the seed scripts to match.

---

### Description__c Field Not Existing on Org

**Error:** `INVALID_FIELD: Description__c` during seed data execution.

**Cause:** The old monolithic `seed-data.apex` references `Description__c` on `IR_Company__c`, but this field was never added to the metadata.

**Fix:** Use the split seed scripts instead:
```bash
sf apex run --file scripts/apex/seed-01-accounts-companies.apex --target-org my-org
sf apex run --file scripts/apex/seed-02-coverage-watchlist-notes.apex --target-org my-org
sf apex run --file scripts/apex/seed-03-audit-logs.apex --target-org my-org
```
These scripts do NOT reference `Description__c`.

---

### Bedrock Model ID Format

**Error:** `ValidationException: The provided model identifier is invalid` or `ResourceNotFoundException` when calling Bedrock.

**Cause:** Using `anthropic.claude-sonnet-4-6` instead of `us.anthropic.claude-sonnet-4-6`. The `us.` prefix is required for cross-region inference profiles in us-east-1.

**Fix:** Update model IDs everywhere:

| Wrong | Correct |
|-------|---------|
| `anthropic.claude-sonnet-4-6` | `us.anthropic.claude-sonnet-4-6` |
| `anthropic.claude-haiku-4-5-20251001-v1:0` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |

Files to check:
- `openclaw/openclaw.json` -> `models.providers.bedrock.models[].id` and `agents.list[].model`
- `evaluation/eval_config.yaml` -> `judge_model`
- AgentCore `cdk.json` -> `default_model_id`

---

### OpenClaw Config Validation Errors (api field)

**Error:** OpenClaw Gateway fails to start with config validation errors about the `api` field.

**Cause:** Using `"api": "bedrock"` instead of `"api": "bedrock-converse-stream"` in `openclaw.json`.

**Fix:** In `openclaw/openclaw.json`, ensure the Bedrock provider uses the correct API type:
```json
"providers": {
  "bedrock": {
    "baseUrl": "https://bedrock-runtime.us-east-1.amazonaws.com",
    "api": "bedrock-converse-stream"
  }
}
```

The valid value is `bedrock-converse-stream`, NOT `bedrock` or `bedrock-converse`.

---

### AgentCore Lazy Init (openclawReady: false)

**Error:** First invocation after deploy returns `{"openclawReady": false}` or times out.

**Cause:** The AgentCore container runs a bridge (`agentcore-contract.js` on port 8080) that starts OpenClaw Gateway internally (port 18789). The first invocation triggers this boot process, which takes 1-2 minutes.

**Fix:** Wait 1-2 minutes and retry. This is expected behavior on cold start.

```bash
# First call — may timeout or return openclawReady: false
agentcore invoke '{"prompt": "Hello", "action": "chat", "userId": "test", "actorId": "test:1"}'

# Wait 90 seconds, then retry
sleep 90
agentcore invoke '{"prompt": "Hello", "action": "chat", "userId": "test", "actorId": "test:1"}'
# Should now return a proper response
```

---

### Clock Skew Causing InvalidSignatureException

**Error:** `InvalidSignatureException: Signature expired` or `Date in Credential scope does not match YYYYMMDD` when calling AWS APIs.

**Cause:** System clock out of sync with AWS. SigV4 signatures are time-sensitive (5-minute window).

**Fix (macOS):**
```bash
sudo sntp -sS time.apple.com
```

**Fix (Linux):**
```bash
sudo ntpdate pool.ntp.org
# or
sudo timedatectl set-ntp true
```

**Fix (Docker):**
Restart Docker Desktop (resyncs the VM clock).

**Fix (AgentCore):**
Usually transient. Redeploy the container or wait for the next invocation.

---

### SAM Deploy Changeset Failure (First Deploy)

**Error:** Changeset creation fails or `No changes to deploy` on first deploy.

**Cause:** First deploy needs guided mode to create the initial stack.

**Fix:**
```bash
sam deploy --guided
```
Accept all defaults. After the first guided deploy, subsequent deploys use `sam deploy`.

---

### Seed Data Script Too Large

**Error:** `Script too large` or `Maximum size of request reached` when running `seed-data.apex`.

**Cause:** The monolithic `scripts/apex/seed-data.apex` exceeds the anonymous Apex 100K character limit.

**Fix:** Always use the split scripts:
```bash
sf apex run --file scripts/apex/seed-01-accounts-companies.apex --target-org my-org
sf apex run --file scripts/apex/seed-02-coverage-watchlist-notes.apex --target-org my-org
sf apex run --file scripts/apex/seed-03-audit-logs.apex --target-org my-org
```

---

### Frontend OAuth Redirect Fails

**Error:** OAuth redirect loop or "invalid_client" error after clicking "Sign in with Salesforce".

**Cause:** Wrong Consumer Key in `VITE_SF_CLIENT_ID`, or Connected App hasn't propagated yet.

**Fix:**
1. Verify the Consumer Key: Setup -> App Manager -> OpenClaw Agent -> View -> Consumer Key
2. Wait 2-10 minutes after deploy for the Connected App to propagate
3. Ensure `VITE_SF_REDIRECT_URI` matches a callback URL in the Connected App

---

### Frontend WebSocket Connection Refused

**Error:** WebSocket connection to `ws://localhost:18789` refused.

**Cause:** OpenClaw Gateway is not running locally, or the URL is wrong.

**Fix:**
- For local dev: Start the gateway with `openclaw gateway start`, verify with `curl http://localhost:18789/ping`
- For AgentCore: Change `VITE_OPENCLAW_GATEWAY_URL` to `wss://<agentcore-api-gateway-url>`

---

### CORS Error on MCP Server Calls

**Error:** `Access-Control-Allow-Origin` CORS error when calling MCP servers.

**Cause:** `FrontendOrigin` in `samconfig.toml` doesn't match the actual frontend origin.

**Fix:** Update `FrontendOrigin` in `samconfig.toml`, then redeploy:
```bash
cd aws
# Edit samconfig.toml: FrontendOrigin=https://your-cloudfront-domain.cloudfront.net
sam build
sam deploy
```

---

### Bedrock AccessDeniedException

**Error:** `AccessDeniedException` when calling Bedrock models.

**Cause:** Model access not enabled, or IAM role missing `bedrock:InvokeModel`.

**Fix:**
1. Bedrock Console -> Model access -> Enable the required models
2. For AgentCore: Ensure execution role has `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream`

---

### Bedrock ThrottlingException

**Error:** `ThrottlingException` during pipeline execution or evaluation.

**Cause:** Bedrock rate limits exceeded.

**Fix:**
- Wait and retry (pipeline has built-in retry logic)
- Request quota increase in AWS Service Quotas for Bedrock
- Use Haiku for L1-L2 queries to reduce Sonnet load

---

### Pipeline Missing Environment Variables

**Error:** `Missing env vars: [SF_INSTANCE_URL, MCP_GATEWAY_URL, ...]` when running `test-pipeline.py`.

**Cause:** Required environment variables not set before running the script.

**Fix:** Set all 6 required env vars:
```bash
export SF_INSTANCE_URL=<your-sf-instance-url>
export MCP_GATEWAY_URL=<your-api-gateway-url>
export MCP_API_KEY=<your-mcp-api-key>
export LANGFUSE_SECRET_KEY=<your-langfuse-secret-key>
export LANGFUSE_PUBLIC_KEY=<your-langfuse-public-key>
export LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
```

`SF_ACCESS_TOKEN` is auto-fetched from `sf org display` if not set. The script uses `SF_TARGET_ORG` (defaults to `my-org`).

---

### Ad-hoc Fields (Dev Org Only — NOT in Source)

These fields exist on the original dev org but are NOT in source metadata. A fresh deploy will NOT create them. No code depends on them. Ignore any references.

| Object | Field | Status |
|--------|-------|--------|
| IR_Audit_Log__c | Duration_Ms__c | Orphaned |
| IR_Audit_Log__c | Platform__c | Orphaned |
| IR_Company__c | Earnings_Date__c | Orphaned (pipeline uses IR_Watchlist__c.Earnings_Date__c) |
| IR_Company__c | Last_Price__c | Orphaned |
| IR_Research_Note__c | Data_Sources__c | Orphaned |
| IR_Research_Note__c | Status__c | Only in deprecated seed-data.apex |
| IR_Watchlist__c | Analyst__c | Orphaned |

---

## 6. What's NOT Automated (Manual Steps Required)

| Step | What You Must Do Manually | Why It Can't Be Automated |
|------|--------------------------|--------------------------|
| Bedrock model access | Enable models in AWS Console -> Bedrock -> Model access | AWS Console-only, no CLI/API |
| Connected App Client ID | Copy Consumer Key from SF Setup -> App Manager after deploy | Generated server-side, not in metadata |
| SF access token refresh | Re-run `sf org display` when token expires, update Secrets Manager | Tokens are ephemeral |
| AgentCore ECR push | Docker build + tag + push (account-specific ECR URI) | ECR URI contains AWS account ID |
| AgentCore skills copy | Copy 006 skills into the AWS sample bridge directory | Two separate repos |
| Slack/WhatsApp channels | Configure channel tokens in OpenClaw channel configs | Channel tokens are org-specific, not in git |
| Langfuse project setup | Create project in Langfuse dashboard, get API keys | UI-only action |
| S3/CloudFront setup | Create bucket, distribution, configure error pages | Account-specific resource names |
| EIP quota increase | Request via AWS Service Quotas if needed | Account-level quota |
| `samconfig.toml` | Copy from example, fill in 6 API key values | Secrets cannot be in git |
| `frontend/.env` | Copy from example, fill in 6 values | Secrets cannot be in git |
| `openclaw.json` placeholders | Replace `${VAR_NAME}` with real values (or set env vars) | Secrets cannot be in git |

### What IS fully automated (zero manual steps after config)

| Step | Command | Time |
|------|---------|------|
| SF metadata deploy (5 objects, 39 fields, Connected App, PermSet) | `sf project deploy start` | ~30s |
| SF seed data (170 records across 7 object types) | 3x `sf apex run --file` | ~15s |
| MCP servers (3 Lambdas, API Gateway, DLQ, usage plan) | `sam build` + `sam deploy` | ~3 min |
| Bedrock Guardrails (PII, toxicity, denied topics) | `aws cloudformation deploy` | ~1 min |
| AgentCore infrastructure (VPC, ECR, runtime, API GW) | `./scripts/deploy.sh` | ~20 min |
| Frontend build | `npm run build` | ~10s |
| Evaluation suite (150 queries) | `python run_suite.py` | ~30 min |

---

## 7. Cleanup (How to Tear Down Everything)

Tear down in reverse order of deployment. Each step is independent — you can tear down partially.

### 7a. Frontend (S3 + CloudFront)

```bash
# If using a custom CloudFront distribution:
# 1. Disable the distribution in AWS Console
# 2. Wait for status to change to "Deployed"
# 3. Delete the distribution

# Empty and delete the S3 bucket
aws s3 rm s3://006-fsi-research-frontend --recursive
aws s3 rb s3://006-fsi-research-frontend
```

### 7b. AgentCore

```bash
cd sample-host-openclaw-on-amazon-bedrock-agentcore

# Destroy all CDK stacks (reverse order)
source .venv/bin/activate
cdk destroy --all

# Delete ECR images
aws ecr batch-delete-image \
  --repository-name bedrock-agentcore-openclaw_agent \
  --image-ids imageTag=latest \
  --region us-east-1

# Delete the ECR repository
aws ecr delete-repository \
  --repository-name bedrock-agentcore-openclaw_agent \
  --force \
  --region us-east-1
```

### 7c. Secrets Manager

```bash
aws secretsmanager delete-secret \
  --secret-id openclaw-fsi-secrets \
  --force-delete-without-recovery \
  --region us-east-1

aws secretsmanager delete-secret \
  --secret-id openclaw/gateway-token \
  --force-delete-without-recovery \
  --region us-east-1
```

### 7d. Bedrock Guardrails

```bash
aws cloudformation delete-stack \
  --stack-name openclaw-006-guardrails \
  --region us-east-1
```

### 7e. MCP Servers (SAM)

```bash
cd my-agent-project-006-v1-openclaw-salesforce-aws/aws
sam delete --stack-name openclaw-mcp-006 --region us-east-1
```

This removes: 3 Lambda functions, API Gateway + stage + API key + usage plan, SQS dead-letter queue, SAM deployment bucket.

### 7f. Salesforce

```bash
# Option A: Delete the entire org (if scratch org or dev org you don't need)
sf org delete scratch --target-org my-org --no-prompt

# Option B: Remove just the 006 data (keep the org)
sf apex run --target-org my-org -c "
  delete [SELECT Id FROM IR_Audit_Log__c];
  delete [SELECT Id FROM IR_Research_Note__c];
  delete [SELECT Id FROM IR_Watchlist__c];
  delete [SELECT Id FROM IR_Coverage__c];
  delete [SELECT Id FROM IR_Company__c];
"
# Then manually delete the 5 custom objects in Setup -> Object Manager if desired
```

### 7g. CDK Bootstrap (optional)

```bash
# WARNING: Only do this if no other CDK apps use the bootstrap stack in this account/region
aws cloudformation delete-stack --stack-name CDKToolkit --region us-east-1
```

### Cleanup verification

After teardown, verify nothing is left:

```bash
# Check CloudFormation stacks
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query "StackSummaries[?contains(StackName, 'openclaw') || contains(StackName, '006')].[StackName]" \
  --output text
# Should return empty

# Check Lambda functions
aws lambda list-functions \
  --query "Functions[?contains(FunctionName, 'openclaw')].[FunctionName]" \
  --output text
# Should return empty

# Check Secrets Manager
aws secretsmanager list-secrets \
  --query "SecretList[?contains(Name, 'openclaw')].[Name]" \
  --output text
# Should return empty

# Check ECR repositories
aws ecr describe-repositories \
  --query "repositories[?contains(repositoryName, 'openclaw') || contains(repositoryName, 'agentcore')].[repositoryName]" \
  --output text
# Should return empty
```

---

## Appendix: Project Structure Reference

```
my-agent-project-006-v1-openclaw-salesforce-aws/
|
|-- force-app/                    SF metadata
|   +-- main/default/
|       |-- objects/              5 custom objects, 39 fields
|       |   |-- IR_Audit_Log__c/     (11 fields - FINRA audit trail)
|       |   |-- IR_Company__c/       (5 fields - company master)
|       |   |-- IR_Coverage__c/      (6 fields - analyst coverage)
|       |   |-- IR_Research_Note__c/ (12 fields - research briefs)
|       |   +-- IR_Watchlist__c/     (5 fields - watchlists)
|       |-- connectedApps/        OpenClaw_Agent (OAuth2 PKCE + OpenID)
|       +-- permissionsets/       IR_Agent_Access (FLS for all IR_* objects)
|
|-- aws/
|   |-- sam-template.yaml         SAM: 3 Lambdas, API GW, DLQ, usage plan
|   |-- samconfig.toml.example    Config template (copy and fill)
|   |-- .env.example              Env var template
|   |-- mcp-servers/
|   |   |-- sec-edgar/            SEC EDGAR Lambda (app.py, mcp_protocol.py)
|   |   |-- market-data/          Market Data Lambda (Alpha Vantage)
|   |   |-- news-search/          News Search Lambda (Tavily)
|   |   +-- shared/               Shared MCP protocol utilities
|   +-- guardrails/
|       +-- bedrock-guardrails.yaml  Bedrock Guardrails CloudFormation
|
|-- openclaw/
|   |-- openclaw.json             Agent config (models, MCP servers, skills, env)
|   |-- mcp-rest-bridge.mjs       REST-to-stdio bridge for MCP servers
|   |-- autoresearchclaw/         Pipeline config + stage prompts
|   |   |-- config.arc.yaml
|   |   +-- prompts/
|   |-- channels/                 Channel configs (Slack, Telegram, WhatsApp)
|   +-- skills/                   6 OpenClaw skills
|       |-- fsi-research/         23-stage AutoResearchClaw pipeline
|       |-- financial-analysis/   DCF, comps, Monte Carlo, stress test
|       |-- salesforce-crm/       SOQL queries, record CRUD
|       |-- audit-logging/        FINRA audit trail -> IR_Audit_Log__c
|       |-- compliance-screening/ MNPI, suitability, restricted list
|       +-- mulesoft-api/         Trade/wire execution with HITL gates
|
|-- agentcore/
|   +-- README.md                 AgentCore deployment (links to AWS sample)
|
|-- frontend/                     React 19 SPA
|   |-- .env.example              Env var template (6 vars)
|   |-- package.json              React 19 + Vite 6 + Zustand 5 + SLDS
|   |-- tsconfig.json
|   |-- vite.config.ts
|   |-- index.html
|   |-- src/                      Components, stores, types, hooks
|   +-- dist/                     Production build output
|
|-- evaluation/                   150-query test suite
|   |-- eval_config.yaml          Config: gateway, judge model, thresholds
|   |-- 006-query-matrix.json     150 queries across 6 personas, 6 levels
|   |-- run_suite.py              Evaluation runner with LLM-as-Judge
|   +-- requirements.txt          langfuse, boto3, requests, pyyaml
|
|-- scripts/
|   |-- apex/                     Salesforce seed data
|   |   |-- seed-01-accounts-companies.apex     25 accounts, 40 contacts, 30 companies
|   |   |-- seed-02-coverage-watchlist-notes.apex  30 coverage, 20 watchlist, 5 notes
|   |   |-- seed-03-audit-logs.apex             50 audit log entries
|   |   +-- seed-data.apex                      DO NOT USE (exceeds 100K limit)
|   |-- aws/                      AWS helper scripts
|   +-- test-pipeline.py          Full 23-stage pipeline test for NVDA
|
+-- docs/                         Design docs, architecture, security
    |-- deployment-guide.md       THIS FILE
    |-- design-doc.md             Full architecture, 6 phases, 71 tasks
    |-- 006-tech-stack-assessment.md  Every technology choice justified
    |-- 006-query-matrix-expanded.md  150 test queries
    |-- 006-security-audit.md     15 findings, OWASP mapped
    |-- 006-data-sources-and-evaluation-strategy.md  7 data layers, 3-layer eval
    |-- 006-frontend-assessment-openclaw.md  React + OpenClaw integration
    |-- deployment-notes.md       Langfuse self-hosting notes
    +-- performance-baseline.md   Template for latency/cost metrics
```