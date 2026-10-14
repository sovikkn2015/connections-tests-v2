# Manual Setup Guide — Project 005

Every step that requires the Salesforce UI or AWS Console is documented here with exact field values.

---

## Step 1: Named Credential — AWS_IR_API

This connects the Salesforce Apex callout actions to the AWS API Gateway MCP servers.

### Prerequisites
- AWS MCP servers deployed (see README "Deploy AWS MCP Servers")
- Note your API Gateway URL from the SAM deploy output (format: `https://XXXXXXXX.execute-api.us-east-1.amazonaws.com/prod`)
- Note your API key value (the one you passed as `ApiKeyValue` during `sam deploy`)

### Part A: Create External Credential

1. Go to **Setup** then search "Named Credentials"
2. Click the **External Credentials** tab (not Named Credentials tab)
3. Click **New**
4. Fill in:
   - **Label**: `AWS IR API Credential`
   - **Name**: `AWS_IR_API_Credential`
   - **Authentication Protocol**: `Custom`
5. Click **Save**

You'll land on the External Credential detail page. Now add the Principal and Custom Header:

### Part B: Add Principal

1. On the External Credential detail page, scroll down to **Principals** section
2. Click **New**
3. Fill in:
   - **Parameter Name**: `AWS_IR_API_Principal`
   - **Sequence Number**: `1`
   - **Identity Type**: `Named Principal`
4. Click **Save**

### Part C: Add Custom Header (API Key)

1. Still on the External Credential detail page, scroll to **Custom Headers** section
2. Click **New**
3. Fill in:
   - **Name**: `x-api-key`
   - **Value**: Your API key value (the 40+ character key you used as ApiKeyValue during `sam deploy`)
   - **Sequence Number**: `1`
4. Click **Save**

At this point your External Credential page should show:
- Principals: 1 row (AWS_IR_API_Principal, Sequence 1)
- Custom Headers: 1 row (x-api-key, your key value, Sequence 1)

### Part D: Grant Permission Set Access to the Principal

This step is critical — without it, the Named Credential callout will fail with a 401 error.

1. Go to **Setup** then search "Permission Sets"
2. Click **System Administrator** (or whichever permission set your user has)
3. Click **External Credential Principal Access**
4. Click **Edit**
5. Find `AWS_IR_API_Credential - AWS_IR_API_Principal` in the Available list
6. Move it to the **Enabled** list using the right arrow
7. Click **Save**

### Part E: Create Named Credential

1. Go to **Setup** then search "Named Credentials"
2. Click the **Named Credentials** tab (not External Credentials)
3. Click **New**
4. Fill in:
   - **Label**: `AWS IR API`
   - **Name**: `AWS_IR_API`
   - **URL**: Your API Gateway URL from SAM deploy output
     - Format: `https://XXXXXXXX.execute-api.us-east-1.amazonaws.com/prod`
     - Replace XXXXXXXX with your API Gateway ID
     - Include `/prod` at the end, no trailing slash
   - **Enabled for Callouts**: Toggle ON
   - **External Credential**: Select `AWS IR API Credential` from dropdown
5. Scroll down to **Callout Options**:
   - **Generate Authorization Header**: UNCHECK this box
   - **Allow Formulas in HTTP Header**: Leave unchecked
   - **Allow Formulas in HTTP Body**: Leave unchecked
6. Click **Save**

### Part F: Add Remote Site Setting

1. Go to **Setup** then search "Remote Site Settings"
2. Click **New Remote Site**
3. Fill in:
   - **Remote Site Name**: `AWS_IR_MCP_API`
   - **Remote Site URL**: Same API Gateway URL as above
   - **Active**: Checked
4. Click **Save**

### Verify

After setup, ask the agent: "Show me NVIDIA's latest 10-K"
It should return real SEC filing data instead of the fallback message.

---

## Step 2: Activate Agent

1. Go to **Setup** then search "Agents" then click **Agents**
2. Find **IR Research Agent** in the list
3. Click on it
4. Click **Assign User** (select the current user)
5. Click **New Version**
6. Click **Commit**
7. Click **Activate**

---

## Step 3: Deploy Test Definitions

After agent activation (Step 2):

```bash
sf project deploy start --source-dir force-app/main/default/aiEvaluationDefinitions --wait 20
```

---

## Step 4: Register Alpha Vantage API Key (Free)

1. Go to https://www.alphavantage.co/support/#api-key
2. Enter your email, click "Get Free API Key"
3. Copy the key
4. Update Lambda:

```bash
aws lambda update-function-configuration \
  --function-name ir-market-data-mcp-prod \
  --environment "Variables={ALPHA_VANTAGE_API_KEY=YOUR_KEY_HERE}" \
  --region us-east-1
```

---

## Step 5: Update Tavily API Key

```bash
aws lambda update-function-configuration \
  --function-name ir-news-search-mcp-prod \
  --environment "Variables={TAVILY_API_KEY=YOUR_KEY_HERE}" \
  --region us-east-1
```

---

## Step 6: Verify End-to-End

In Salesforce Setup then Agents then IR Research Agent then Test:

| Query | Expected Result |
|-------|----------------|
| Tell me about NVIDIA | Company info: NVDA, Technology, NASDAQ, $2.8T |
| Who covers NVIDIA? | Sarah Kim (Buy, $180), Priya Sharma (Hold, $145) |
| When does NVIDIA report? | May 28, 2026 |
| Show me NVIDIA latest 10-K | Real SEC filing data (after Named Credential) |
| Can I trade NVIDIA? | Compliance report (restricted list, quiet period, MNPI) |
| What is on my watchlist? | 8 entries with priorities |
| Any news about NVIDIA? | News articles (after Tavily key) |

---

## Step 7: Configure Langfuse Observability (Sprint 4)

Langfuse provides cross-platform tracing so you can see every agent action, LLM call, and tool invocation in a single dashboard — across both Salesforce and AWS.

### Part A: Get Langfuse API Keys

**Option 1: Langfuse Cloud (recommended for getting started)**
1. Go to https://cloud.langfuse.com and create a free account
2. Create a new project (e.g., "IR Research Agent")
3. Go to **Settings** then **API Keys**
4. Click **Create API Key**
5. Copy the **Public Key** (starts with `pk-lf-`) and **Secret Key** (starts with `sk-lf-`)
6. Note the **Host URL**: `https://cloud.langfuse.com`

**Option 2: Self-hosted Langfuse**
1. Deploy Langfuse via Docker: https://langfuse.com/docs/deployment/self-host
2. Create a project and API keys from your instance's Settings page
3. Note your host URL (e.g., `https://langfuse.mycompany.com`)

### Part B: Run the Configure Script

The script updates both AWS Lambda functions and the Salesforce Named Credential in one step:

```bash
./scripts/configure-langfuse.sh <LANGFUSE_HOST> <PUBLIC_KEY> <SECRET_KEY>
```

Example:
```bash
./scripts/configure-langfuse.sh https://cloud.langfuse.com pk-lf-abc123 sk-lf-xyz789
```

This will:
1. Update `ir-financial-analysis-prod` and `ir-sentiment-analysis-prod` Lambda env vars
2. Deploy the `Langfuse_API` Named Credential and External Credential to Salesforce

### Part C: Grant Permission Set Access (Salesforce)

1. Go to **Setup** then search "Permission Sets"
2. Click **System Administrator** (or your permission set)
3. Click **External Credential Principal Access**
4. Click **Edit**
5. Find `Langfuse_API_Credential - Langfuse_API_Principal` in the Available list
6. Move it to the **Enabled** list
7. Click **Save**

### Part D: Verify Traces

1. Run an agent query in Salesforce (e.g., "What's NVIDIA's fair value?")
2. Open your Langfuse dashboard
3. Go to **Traces** — you should see a trace with:
   - Trace name matching the agent action
   - Spans for each callout (SEC EDGAR, Market Data, etc.)
   - Generations for any LLM calls (Bedrock Claude)
4. Traces from both Salesforce (Apex) and AWS (Lambda) will appear with `ir-` prefixed IDs

---

## Step 8: Deploy Frontend to S3 + CloudFront (Sprint 4)

The React frontend (Investment Research Workbench) is deployed to S3 and served via CloudFront. The SAM template creates both resources automatically.

### Prerequisites

- Node.js 20+ installed (`node --version`)
- npm 10+ installed (`npm --version`)
- SAM stack deployed with frontend resources (the `sam deploy` from the README)
- AWS CLI configured with credentials that can access the stack

### Part A: Configure Frontend Environment

1. Navigate to the `frontend/` directory
2. Copy the example env file:

```bash
cd frontend
cp .env.example .env
```

3. Edit `.env` with your values:

```
VITE_SF_CLIENT_ID=YOUR_CONNECTED_APP_CLIENT_ID
VITE_SF_REDIRECT_URI=https://YOUR_CLOUDFRONT_DOMAIN/callback
VITE_SF_LOGIN_URL=https://login.salesforce.com
VITE_SF_AGENT_ID=YOUR_IR_RESEARCH_AGENT_ID
VITE_LANGFUSE_HOST=https://cloud.langfuse.com
```

- `VITE_SF_CLIENT_ID` — from your Salesforce Connected App (see Part B below)
- `VITE_SF_REDIRECT_URI` — your CloudFront URL + `/callback` (get the URL from `sam deploy` output: `FrontendUrl`)
- `VITE_SF_AGENT_ID` — the IR Research Agent ID from Salesforce Setup > Agents

### Part B: Create Salesforce Connected App (OAuth2 PKCE)

The Connected App is deployed programmatically. Run from the project root:

```bash
./scripts/setup-frontend-auth.sh
```

This deploys the Connected App with:
- PKCE required (no client secret needed)
- Callback URLs: CloudFront domain + localhost for dev
- OAuth scopes: api, refresh_token

Then get the Consumer Key:

1. Go to **Setup** then search "App Manager"
2. Find **IR Research Workbench** in the list
3. Click the dropdown arrow on the right then **Manage Consumer Details**
4. You may need to verify your identity (email code)
5. Copy the **Consumer Key** (this is your `VITE_SF_CLIENT_ID`)

Then configure and deploy:

```bash
# Edit frontend/.env
VITE_SF_CLIENT_ID=<paste your Consumer Key here>
VITE_SF_REDIRECT_URI=https://YOUR_CLOUDFRONT_DOMAIN/callback

# Build and deploy
./scripts/deploy-frontend.sh
```

### Part C: Build and Deploy

From the project root:

```bash
# One-command deploy
./scripts/deploy-frontend.sh
```

Or manually:

```bash
cd frontend
npm install
npm run build

# Get bucket name from stack outputs
BUCKET=$(aws cloudformation describe-stacks --stack-name ir-research-mcp \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" --output text)

aws s3 sync dist/ "s3://$BUCKET/" --delete
```

### Part D: Access the Frontend

1. Get the CloudFront URL from the SAM deploy output (`FrontendUrl`) or run:

```bash
aws cloudformation describe-stacks --stack-name ir-research-mcp \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendUrl'].OutputValue" --output text
```

2. Open the URL in your browser
3. You'll be redirected to Salesforce login (OAuth2 PKCE flow)
4. After login, the Research Workbench loads with the chat panel and research panels

### Notes

- First CloudFront deployment takes 5-10 minutes to propagate globally
- The CloudFront distribution handles SPA routing (403/404 → index.html)
- S3 bucket has public access blocked — all access goes through CloudFront OAC
- To redeploy after code changes, just run `./scripts/deploy-frontend.sh` again

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| "SEC filings integration requires AWS MCP server configuration" | Named Credential not set up | Follow Step 1 |
| "Market Data API returned status 403" | API key mismatch | Verify x-api-key in External Credential matches SAM deploy ApiKeyValue |
| "BotVersion not found" on test deploy | Agent not activated | Follow Step 2 |
| "Field does not exist: Sector__c" | Anonymous Apex cache | Use deployed class: `echo "IR_SeedDataRunner.run();" > /tmp/s.apex && sf apex run --file /tmp/s.apex` |
| "No recent filings found" | SEC EDGAR rate limit | Wait 10 seconds, retry |
| "Langfuse ingestion returned 401" | Invalid Langfuse API keys | Verify public/secret keys in Named Credential or Lambda env vars |
| "Langfuse ingestion failed" | Langfuse host unreachable | Check LANGFUSE_HOST URL; ensure Remote Site Setting exists for Langfuse |
| No traces in Langfuse dashboard | Credentials not configured | Run `./scripts/configure-langfuse.sh`; check Permission Set access |
| "Could not find FrontendBucketName" | SAM stack missing frontend resources | Redeploy SAM template with the latest `sam-template.yaml` that includes frontend resources |
| CloudFront returns 403 | Bucket policy not applied yet | Wait 1-2 minutes after deploy; verify `FrontendBucketPolicy` in CloudFormation |
| OAuth redirect fails | Wrong callback URL | Ensure Connected App callback URL matches your CloudFront domain + `/callback` |
