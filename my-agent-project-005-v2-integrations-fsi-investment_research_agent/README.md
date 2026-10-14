# Project 005: Investment Research Agent

Cross-platform multi-agent system for equity research analysts. Salesforce Agentforce orchestrator + AWS MCP servers + Strands agents + Langfuse governance.

## Prerequisites

- Salesforce Agentforce Developer Edition org
- Salesforce CLI: `npm install -g @salesforce/cli`
- AWS CLI + SAM CLI (for Sprint 2+): `brew install awscli aws-sam-cli`
- Python 3.12+ (for Sprint 2+): `brew install python@3.12`
- Node.js 20+ (for Sprint 4 React frontend): `brew install node`

## Deploy to a Fresh Org (Reproducible)

```bash
cd my-agent-project-005-integrations-fsi-investment_research_agent

# 1. Authenticate to your Salesforce org
sf org login web --alias ir-org --set-default

# 2. Deploy objects (5 objects, 35 fields)
sf project deploy start --source-dir force-app/main/default/objects --wait 20

# 3. Deploy Apex classes (10 classes)
sf project deploy start --source-dir force-app/main/default/classes --wait 20

# 4. Grant field-level security (34 permissionable fields to System Administrator)
sf apex run --file scripts/apex/grant-fls.apex

# 4b. Grant object + field permissions to Einstein Agent User (5 objects, 34 fields)
sf apex run --file scripts/apex/grant-agent-fls.apex

# 5. Seed data (10 companies, 20 coverage, 8 watchlist, 5 research notes)
#    NOTE: Use the deployed class, not the anonymous script.
#    Anonymous Apex may have stale metadata cache on first deploy.
echo "IR_SeedDataRunner.run();" > /tmp/seed.apex && sf apex run --file /tmp/seed.apex

# 6. Grant Apex class access to Einstein Agent User (10 classes)
sf apex run --file scripts/apex/grant-permissions.apex

# 6b. Configure Langfuse observability (optional but recommended)
#     Get keys from https://cloud.langfuse.com → Settings → API Keys
./scripts/configure-langfuse.sh YOUR_LANGFUSE_HOST YOUR_PUBLIC_KEY YOUR_SECRET_KEY

# 7. Deploy agent bundle
sf project deploy start --source-dir force-app/main/default/aiAuthoringBundles --wait 20

# 8. MANUAL: Activate agent in Setup UI
#    Setup > Agents > IR Research Agent > Assign user > New Version > Commit > Activate

# 9. Deploy test definitions (requires active agent with BotVersion)
sf project deploy start --source-dir force-app/main/default/aiEvaluationDefinitions --wait 20

# 10. Verify deployment
echo "IR_VerifyData.run();" > /tmp/verify.apex && sf apex run --file /tmp/verify.apex
```

## Connect Salesforce to AWS (After SAM Deploy)

```bash
# Automated: deploys External Credential + Named Credential + Remote Site Setting
# Pass your API Gateway ID and API key from the SAM deploy output
./scripts/configure-aws-connection.sh YOUR_API_GATEWAY_ID YOUR_API_KEY

# ONE MANUAL STEP: Permission Set assignment for External Credential Principal
# See docs/manual-setup-guide.md Part D for details
```

## Deploy AWS (Sprint 2 MCP Servers + Sprint 3 Analysis Agents)

```bash
cd aws

# 1. Build (bundles Python dependencies)
sam build --template-file sam-template.yaml

# 2. Deploy (creates 5 Lambda functions + API Gateway)
#    IMPORTANT: deploy the BUILT template, not the source
sam deploy --template-file .aws-sam/build/template.yaml \
  --stack-name ir-research-mcp \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --no-confirm-changeset \
  --parameter-overrides \
    "ApiKeyValue=YOUR_API_KEY_20_PLUS_CHARS \
     SecEdgarUserAgent=YOUR_EMAIL \
     AlphaVantageApiKey=YOUR_AV_KEY \
     TavilyApiKey=YOUR_TAVILY_KEY"

# 3. Note the API Gateway ID from the output URL
#    (e.g., og256a1neb from https://og256a1neb.execute-api...)

# 4. Configure Salesforce Named Credential
cd ..
./scripts/configure-aws-connection.sh YOUR_API_GATEWAY_ID YOUR_API_KEY

# 5. Configure Sentiment Agent news connection
./scripts/configure-sentiment-agent.sh YOUR_API_GATEWAY_ID YOUR_API_KEY

# 6. ONE MANUAL STEP: Permission Set assignment
#    Setup > Permission Sets > AWS IR API Access
#    > External Credential Principal Access > Enable the principal
#    > Manage Assignments > Add your user + Einstein Agent User
```

## What's Deployed

| Component | Count | Sprint |
|-----------|-------|--------|
| CRM Objects | 5 (IR_Company, IR_Coverage, IR_Watchlist, IR_Research_Note, IR_Audit_Log) | 1 |
| Custom Fields | 35 (34 permissionable + Ticker__c required) | 1 |
| Apex Classes | 12 (6 CRM + 3 MCP callout + 2 Bedrock callout + SeedDataRunner) | 1-3 |
| Agent Topics | 10 (5 CRM + 2 MCP + financial analysis + sentiment + escalation + off-topic) | 1-3 |
| Seed Data | 43 records (10 companies, 20 coverage, 8 watchlist, 5 notes) | 1 |
| Test Definitions | 3 files, 44 test queries | 1-2 |
| AWS Lambda Functions | 5 (SEC EDGAR, Market Data, News Search, Financial Analysis, Sentiment Analysis) | 2-3 |
| MCP Tools | 11 (4 + 4 + 3) | 2 |
| Bedrock Agent Tools | 8 (4 financial + 4 sentiment) | 3 |
| React Frontend | 1 app (10 components, SLDS-styled, seed data for 10 tickers) | 4 |

## Known Issues

1. **Anonymous Apex cache**: On first deploy to a fresh org, anonymous Apex scripts may fail with "Field does not exist" even though fields are deployed. Use `IR_SeedDataRunner.run()` instead of `seed-data.apex` directly.
2. **IR_Company__c.Ticker__c non-permissionable**: This field is `required + unique + externalId`, making it non-permissionable via FieldPermissions. The grant-fls scripts exclude it. The Einstein Agent User can still read it because `with sharing` classes access required fields automatically.
3. **MCP callout actions**: Sprint 2 Apex actions (IR_SecFilingsAction, IR_MarketDataAction, IR_NewsSearchAction) require Named Credential `AWS_IR_API` pointing to the API Gateway URL. Without it, they return a helpful fallback message.
4. **Test definitions**: Must be deployed AFTER agent activation (requires BotVersion).

## Manual Steps (UI Required)

Some steps require the Salesforce Setup UI or AWS Console. See **[docs/manual-setup-guide.md](docs/manual-setup-guide.md)** for step-by-step instructions with exact field values for:

1. **Named Credential** — connects Salesforce to AWS API Gateway (External Credential + Named Credential + Remote Site Setting)
2. **Agent Activation** — assign user, commit version, activate
3. **Test Definition Deploy** — after agent activation
4. **Alpha Vantage API Key** — free registration + Lambda env var update
5. **Tavily API Key** — Lambda env var update

## React Frontend (Sprint 4B)

The Investment Research Workbench is a React app styled with Salesforce Lightning Design System (SLDS) that connects to the IR Research Agent via the Salesforce Agent API.

### Install

```bash
cd frontend
npm install
```

### Configure

```bash
cp .env.example .env
# Edit .env with your Salesforce Connected App values:
#   VITE_SF_CLIENT_ID     — from your Connected App (OAuth2 PKCE, no secret)
#   VITE_SF_REDIRECT_URI  — http://localhost:5173/callback
#   VITE_SF_AGENT_ID      — your IR Research Agent ID
#   VITE_LANGFUSE_HOST    — your Langfuse instance URL
```

### Run (Development)

```bash
npm run dev
# Opens http://localhost:5173
```

### Build for Production

```bash
npm run build
# Output in frontend/dist/
```

### Deploy to S3 + CloudFront (Production)

The SAM template creates an S3 bucket and CloudFront distribution automatically. After `sam deploy`:

```bash
# One-command build + deploy (from project root)
./scripts/deploy-frontend.sh

# Or specify a custom stack name
./scripts/deploy-frontend.sh ir-research-mcp
```

The script will:
1. Read the S3 bucket name and CloudFront URL from stack outputs
2. Run `npm install && npm run build` in the `frontend/` directory
3. Sync `dist/` to S3 and invalidate the CloudFront cache

First deployment takes 5-10 minutes for CloudFront propagation.

### Frontend Architecture

| Component | Purpose |
|-----------|---------|
| `App.tsx` | OAuth2 PKCE auth via react-oauth2-code-pkce |
| `ChatPanel.tsx` | Left panel — agent chat with SSE streaming, auto-loads ticker data |
| `ResearchPanel.tsx` | Right panel — tabbed research data with dot indicators and filing filters |
| `CompanyCard.tsx` | Company tab — price header, 2×4 metrics grid, 52W range, sentiment badge |
| `CoverageTable.tsx` | Coverage tab — consensus bar, target price range, analyst table |
| `FinancialChart.tsx` | Analysis tab — chart toggle (Revenue/Margins/EPS/FCF), fair value, peer comps |
| `TracePanel.tsx` | Bottom panel — Langfuse trace timeline (collapsible) |
| `data/seedData.ts` | Hardcoded data for 10 tickers — instant UI without API calls |
| `services/responseParser.ts` | Extracts tickers from chat, detects relevant tab, formatting helpers |
| `services/agentApi.ts` | Salesforce Agent API client (session + messages + SSE + Apex fallback) |
| `store/agentStore.ts` | Zustand store — company, coverage, valuation, sentiment, filings state |

## Architecture

See `docs/design-doc.md` for the full architecture, security model, and build plan.

## No Credentials in Git

All API keys, org URLs, and secrets are stored in:
- Salesforce: Named Credentials
- AWS: SAM template parameters + Secrets Manager
- Local: ~/.aws/credentials + .env files (gitignored)
