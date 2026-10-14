# Reproducibility From Zero — 005 v2 Investment Research Agent

This is the unabridged path from a blank laptop + empty Salesforce + empty AWS account to a working Investment Research Agent with live chat, live market data, SEC filings, DCF valuations, and Bedrock sentiment. No shortcuts. Every command is copy-pasteable. Every manual step is called out.

**Today's deployment (for cross-reference while reading):**

| Thing | Value |
|---|---|
| Salesforce org (my-domain) | `https://orgfarm-035b70d101-dev-ed.develop.my.salesforce.com` |
| Agent BotDefinition Id | `0XxgK000001JItVSAW` |
| Latest agent bundle deploy | `0AfgK00000JdUGESA3` |
| Token proxy | `https://og256a1neb.execute-api.us-east-1.amazonaws.com/prod/oauth/agent-token` |
| Agent API base | `https://api.salesforce.com/einstein/ai-agent/v1` |
| API Gateway (AWS stack `ir-research-mcp`) | `https://og256a1neb.execute-api.us-east-1.amazonaws.com/prod` |
| Frontend (CloudFront) | `https://d5n93zwamizsc.cloudfront.net` |
| AWS region | `us-east-1` |

---

## Prerequisites

Install once on your workstation:

- Salesforce CLI — `npm install -g @salesforce/cli` (v2.60+ recommended). Verify: `sf --version`
- AWS CLI v2 — `brew install awscli` (or platform equivalent). Configure: `aws configure` (region `us-east-1`, output `json`)
- AWS SAM CLI — `brew install aws-sam-cli`. Verify: `sam --version` (1.100+)
- Node.js 18+ — `brew install node@20`. Verify: `node --version`
- Python 3.10+ — `brew install python@3.10`. Verify: `python3 --version`
- A Salesforce org with **Agentforce** enabled. A fresh **Developer Edition** org works; sign up at https://developer.salesforce.com/signup
- A free **Alpha Vantage** API key — https://www.alphavantage.co/support/#api-key
- A free **Tavily** API key — https://tavily.com (create account, grab key from dashboard)
- An email address for the SEC EDGAR `User-Agent` header (SEC requires this — they will block anonymous scrapers)

Clone the repo and `cd` into the project root:

```bash
git clone <your-fork-url> connections-test
cd connections-test/my-agent-project-005-v2-integrations-fsi-investment_research_agent
```

All `sf project deploy …` commands below assume you are inside this directory.

---

## Step 1 — Create or identify the Salesforce org

You have two options.

**Option A: scratch org from an existing Dev Hub** (clean-slate, short-lived, ideal for testing):

```bash
sf org login web --alias my-devhub --set-default-dev-hub
sf org create scratch -f config/project-scratch-def.json -a my-new-org --duration-days 30
sf org open -o my-new-org
```

**Option B: use an existing Agentforce-enabled Developer Edition org** (what the reference deployment uses):

```bash
sf org login web --alias my-new-org --instance-url https://login.salesforce.com
sf config set target-org=my-new-org
```

Confirm:

```bash
sf org display --target-org my-new-org
```

Record the value of **Instance Url** (the `https://...my.salesforce.com` my-domain). You will need it in Steps 6, 9, and 10.

---

## Step 2 — Deploy Apex classes and custom objects

Deploy everything under `force-app/main/default` except the AI bundles (those depend on classes existing first — Step 8). You can do it in one shot, or in the phases shown in `README.md`. The one-shot form:

```bash
sf project deploy start \
  --source-dir force-app/main/default/objects \
  --target-org my-new-org --wait 20

sf project deploy start \
  --source-dir force-app/main/default/classes \
  --target-org my-new-org --wait 20

sf project deploy start \
  --source-dir force-app/main/default/permissionsets \
  --target-org my-new-org --wait 20

sf project deploy start \
  --source-dir force-app/main/default/labels \
  --target-org my-new-org --wait 20
```

What gets deployed:

- **5 custom objects** — `IR_Company__c`, `IR_Coverage__c`, `IR_Watchlist__c`, `IR_Research_Note__c`, `IR_Audit_Log__c` (35 fields total, 1 required `Ticker__c` on Company)
- **~12 Apex classes** — `IR_CompanyLookupAction`, `IR_CoverageCheckAction`, `IR_EarningsCalendarAction`, `IR_WatchlistAction`, `IR_ComplianceAction`, `IR_MarketDataAction`, `IR_SecFilingsAction`, `IR_NewsSearchAction`, `IR_FinancialAnalysisAction`, `IR_SentimentAnalysisAction`, plus `IR_SeedDataRunner`, `IR_VerifyData`
- **Permission sets** — `IR_Agent_Access` (object + field + class grants for the Einstein Agent User)
- **Custom labels** — `IR_AWS_API_URL`, `IR_AWS_API_KEY` (values are placeholders until Step 6)

Then grant FLS and Apex access to the Einstein Agent User:

```bash
sf apex run --file scripts/apex/grant-fls.apex        --target-org my-new-org
sf apex run --file scripts/apex/grant-agent-fls.apex  --target-org my-new-org
sf apex run --file scripts/apex/grant-permissions.apex --target-org my-new-org
```

Verify the classes compiled:

```bash
sf apex run --target-org my-new-org <<'APEX'
System.debug('Classes: ' + [SELECT COUNT() FROM ApexClass WHERE Name LIKE 'IR\_%' ESCAPE '\\']);
APEX
```

---

## Step 3 — Seed Data Cloud  *(gap — mostly manual today)*

The agent's `Company Lookup`, `Coverage Check`, `Watchlist`, and `Compliance` Topics all read from Data Cloud / standard objects in the org. You need:

- **Company records (7 minimum)** — NVIDIA (NVDA), Apple (AAPL), Microsoft (MSFT), Tesla (TSLA), Alphabet (GOOGL), Amazon (AMZN), Meta (META). Market cap, Next earnings date, Sector, Industry, Exchange fields should be populated.
- **`IR_Coverage__c` records** — one analyst (e.g., Sarah Chen) covering NVDA / AAPL / MSFT / TSLA / GOOGL with a Rating (Buy/Hold/Sell/Underweight), Target Price, and Last Updated date.
- **`IR_Watchlist__c` records** (optional, ~8) and a handful of `IR_Research_Note__c` rows.

**Recommended path** — run the seed class that ships with the project:

```bash
echo "IR_SeedDataRunner.run();" > /tmp/seed.apex
sf apex run --file /tmp/seed.apex --target-org my-new-org
```

This creates 43 records: 10 companies, 20 coverage, 8 watchlist, 5 notes. If the anonymous Apex fails with "Field does not exist", wait 60 seconds (metadata cache) and retry.

Verify:

```bash
sf data query -q "SELECT COUNT() FROM IR_Company__c" --target-org my-new-org
sf data query -q "SELECT Name, Rating__c, Target_Price__c FROM IR_Coverage__c LIMIT 5" --target-org my-new-org
```

**Gap being tracked:**

- Real Data Cloud DMOs (vs. custom objects) are not wired in 005. If you want to use actual Data Cloud ingestion, that's a separate project (see 003).
- The seed class hard-codes April 2026 dates. For a deployment intended to stay current, fork the class and parameterize the dates.
- TODO: ship an `sf data import tree` version so non-Apex users can reseed.

---

## Step 4 — Create External Client App (ECA)  *(manual — Salesforce UI)*

This is the OAuth client that the token proxy Lambda uses to mint Agentforce Agent API tokens via Client Credentials Flow. There is no CLI for this today.

1. Setup → **App Manager** → **New External Client App**
2. **Basic information**:
   - Label: `Agent API`
   - API Name: `Agent_API`
   - Contact email: your email
   - Distribution state: **LOCAL**  *(critical — "External" requires App Review)*
3. **API (Enable OAuth Settings)**:
   - Enable OAuth: **yes**
   - Callback URL: `http://localhost:1717/OauthRedirect` (placeholder — not used for client-credentials)
   - Selected OAuth scopes: `api`, `refresh_token`, `chatbot_api`, `sfap_api`
   - Enable Client Credentials Flow: **yes**
   - **Run As** user: a System Administrator (this is the identity the agent runs as)
4. Save.
5. Go to the new app → **Manage Consumer Details**. Capture the **Consumer Key** and **Consumer Secret**. These become `EcaClientId` and `EcaClientSecret` in Step 7.

Reference screenshots for this step live in `docs/external-client-app-setup-instructions.md` (in the repo root).

---

## Step 5 — Create Connected App for PKCE frontend login  *(manual)*

This is a separate app from the ECA. The frontend uses OAuth2 **Authorization Code + PKCE** (no secret), not client credentials.

1. Setup → **App Manager** → **New Connected App** → **Create a Connected App**
2. Name: `IR_Frontend_PKCE`; API Name: `IR_Frontend_PKCE`
3. **API (Enable OAuth Settings)**:
   - Enable OAuth: yes
   - Callback URL: `https://<CLOUDFRONT_URL>/callback` (use the actual CloudFront domain after Step 7, or a placeholder like `https://example.cloudfront.net/callback` and edit later)
   - For local dev you can also add `http://localhost:5173/callback` on a second line
   - Selected OAuth scopes: `api`, `refresh_token`
   - **Require Proof Key for Code Exchange (PKCE)**: **yes**
   - **Require Secret for Web Server Flow**: **no**
   - **Require Secret for Refresh Token Flow**: **no**
4. Save, then **Manage Consumer Details** → capture the **Consumer Key** only (no secret needed for PKCE).
5. Wait ~10 minutes for Salesforce to provision the app across the platform (yes, really).

---

## Step 6 — Configure Custom Labels  *(do this after Step 7 — come back here)*

The Apex classes read the AWS URL and API key from these two Custom Labels. Their values aren't known until the AWS stack is up.

After Step 7 completes and you have the API Gateway URL + API key, set the labels:

**UI path:** Setup → **Custom Labels** → `IR_AWS_API_URL` → Edit → paste URL; same for `IR_AWS_API_KEY`.

**CLI path** (uses the metadata file already in the repo — re-deploy with new values):

```bash
# Edit force-app/main/default/labels/IR_AWS_API_URL.labels-meta.xml with the new values, then:
sf project deploy start \
  --source-dir force-app/main/default/labels \
  --target-org my-new-org --wait 20
```

---

## Step 7 — Deploy AWS stack

```bash
cd aws
sam build --template-file sam-template.yaml
```

First-time deploy (guided — you'll be prompted for parameters):

```bash
sam deploy --guided --template-file .aws-sam/build/template.yaml
```

Answer the prompts:

| Prompt | Value |
|---|---|
| Stack Name | `ir-research-mcp` |
| AWS Region | `us-east-1` |
| Parameter `Stage` | `prod` |
| Parameter `ApiKeyValue` | A random 20+ char string. Generate: `openssl rand -base64 32` |
| Parameter `SecEdgarUserAgent` | Your real email (SEC EDGAR requires this) |
| Parameter `AlphaVantageApiKey` | From https://www.alphavantage.co |
| Parameter `TavilyApiKey` | From https://tavily.com |
| Parameter `EcaClientId` | Consumer Key from Step 4 |
| Parameter `EcaClientSecret` | Consumer Secret from Step 4 |
| Parameter `SfInstanceUrl` | The my-domain URL from Step 1 |
| Parameter `SfClientId` / `SfClientSecret` | Leave default `CONFIGURE_AFTER_DEPLOY` for now; used only by Strands agents that call back into Salesforce |
| Confirm changes before deploy | `y` |
| Allow SAM CLI IAM role creation | `y` |
| Save arguments to configuration file | `y` (saves `samconfig.toml`) |

After the deploy finishes, capture the outputs:

```bash
aws cloudformation describe-stacks --stack-name ir-research-mcp \
  --query 'Stacks[0].Outputs' --output table
```

Record **`ApiGatewayUrl`** (e.g., `https://og256a1neb.execute-api.us-east-1.amazonaws.com/prod`) and **`FrontendUrl`** (the CloudFront domain). The CloudFront distribution is created automatically by this template.

For subsequent deploys (after you've edited Lambda code or changed parameters), the saved config means you can just:

```bash
sam build --template-file sam-template.yaml
sam deploy --template-file .aws-sam/build/template.yaml
```

Now **go back to Step 6** and set the `IR_AWS_API_URL` and `IR_AWS_API_KEY` Custom Labels in Salesforce.

Also wire up the Named Credential so Apex can call AWS:

```bash
cd ..
./scripts/configure-aws-connection.sh <API_GATEWAY_ID> <API_KEY>
# Example:
#   ./scripts/configure-aws-connection.sh og256a1neb <the random string from ApiKeyValue above>
```

That script deploys the `AWS_IR_API_Credential` External Credential, `AWS_IR_API` Named Credential, and `AWS_IR_MCP_API` Remote Site Setting, with placeholders filled in. One more manual bit: Setup → Permission Sets → `IR_Agent_Access` → **External Credential Principal Access** → enable `AWS_IR_API_Credential - AWS_IR_API_Principal`, then Manage Assignments → add yourself + the Einstein Agent User.

---

## Step 8 — Deploy the agent bundle  *(often forgotten — do not skip)*

The AI Authoring Bundle is what actually wires the deployed Apex actions as Topics the agent can reason about. If you skip this step, the agent will default to whatever is in the target org's `IR_Research_Agent` (possibly an older version with fewer Topics), and queries that hit unwired actions will come back as "this feature will be available in a future update". We hit this exact failure mode on deploy `0AfgK00000JdUGESA3` — see `docs/end-to-end-test-results-30-queries.md`.

**Publishing the bundle is a TWO-STEP process.** The docs say publish activates automatically. It does not. You must activate separately.

```bash
# Step 8a: Publish the authoring bundle — compiles the .agent file into Bot + BotVersion + GenAi* metadata
sf agent publish authoring-bundle \
  --api-name IR_Research_Agent \
  --target-org my-new-org \
  --skip-retrieve

# Step 8b: Activate the new BotVersion — without this, the agent still serves the OLD version at runtime
sf agent activate \
  --api-name IR_Research_Agent \
  --target-org my-new-org
```

If you have a companion compliance agent, repeat for it:

```bash
sf agent publish authoring-bundle --api-name IR_Compliance_Agent --target-org my-new-org --skip-retrieve
sf agent activate             --api-name IR_Compliance_Agent --target-org my-new-org
```

Verify the new BotVersion is live:

```bash
sf data query -o my-new-org \
  -q "SELECT VersionNumber, Status, LastModifiedDate FROM BotVersion WHERE BotDefinition.DeveloperName='IR_Research_Agent' ORDER BY VersionNumber DESC"
```

Expected output: one Active row (the version you just published) and older rows as Inactive.

Sanity-check the bot id from the CLI:

```bash
sf data query -q "SELECT Id, DeveloperName, MasterLabel FROM BotDefinition WHERE DeveloperName='IR_Research_Agent'" \
  --target-org my-new-org
```

Record the `Id` — that's the `VITE_SF_AGENT_ID` for Step 9.

**Troubleshooting — if `sf agent publish authoring-bundle` errors on a specific GenAiFunctionDefinition:**
The `.agent` file references an Apex class that isn't compatible with Agentforce's function-definition generator (usually a missing `@InvocableVariable` annotation or a return type it can't serialize). Option A: fix the Apex class. Option B: remove the offending Topic from the `.agent` file, republish, and treat it as a backlog item. We hit this on `research_brief` → `IR_ResearchBriefAction` during the reference deployment. The other 11 Topics published cleanly.

---

## Step 9 — Configure frontend `.env`

```bash
cd frontend
cp .env.example .env
```

Edit `.env`:

```ini
VITE_SF_LOGIN_URL=https://orgfarm-035b70d101-dev-ed.develop.my.salesforce.com   # from Step 1
VITE_SF_CLIENT_ID=<Consumer Key from Step 5>
VITE_SF_REDIRECT_URI=https://d5n93zwamizsc.cloudfront.net/callback              # from Step 7 FrontendUrl + /callback
VITE_SF_AGENT_ID=0XxgK000001JItVSAW                                              # from Step 8 sf data query
VITE_API_GATEWAY_URL=https://og256a1neb.execute-api.us-east-1.amazonaws.com/prod # from Step 7
VITE_AWS_API_KEY=<the random ApiKeyValue from Step 7>
VITE_LANGFUSE_HOST=https://us.cloud.langfuse.com                                 # optional — only if using Langfuse
VITE_LANGFUSE_PUBLIC_KEY=<from cloud.langfuse.com Settings → API Keys>           # optional
```

Get the agent Id from the CLI if you don't have it handy:

```bash
sf data query -q "SELECT Id, DeveloperName FROM BotDefinition" --target-org my-new-org
```

---

## Step 10 — Build and deploy the frontend

The S3 bucket and CloudFront distribution already exist — they were created by the SAM template in Step 7. You just need to build the React app and sync it.

```bash
# From the project root
./scripts/deploy-frontend.sh ir-research-mcp
```

That script does the equivalent of:

```bash
cd frontend
npm install
npm run build

BUCKET=$(aws cloudformation describe-stacks --stack-name ir-research-mcp \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" --output text)
DIST_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Comment=='IR Research Workbench V2 - prod'].Id | [0]" --output text)

aws s3 sync dist/ "s3://$BUCKET/" --delete
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths '/*'
```

First-time CloudFront propagation takes 5–10 minutes. Subsequent deploys are visible within 30 seconds of the invalidation completing.

---

## Step 11 — Smoke test

1. Open the CloudFront URL in a browser (e.g., `https://d5n93zwamizsc.cloudfront.net`)
2. You'll be redirected to Salesforce for PKCE login. Sign in as your admin user.
3. You land in the Workbench. The chat panel on the left shows the agent greeting. The research panel on the right is empty.
4. Type `Tell me about NVDA` → within 5 seconds you see a streaming company profile (market cap $3.2T, exchange NASDAQ, next earnings…).
5. Click the `NVDA` chip that appeared in the chat message → the right-side panel populates: live price from Alpha Vantage, P/E, Forward P/E, EPS, Beta, 52W range, 50D/200D MA, and the latest 10-K from SEC EDGAR.
6. Ask `DCF valuation for NVDA` → agent returns Bedrock-computed DCF and Monte Carlo numbers (should be around DCF $869.88, Monte Carlo $125.62 with 2026 seed data).
7. Ask `Latest news on Tesla` → real Tavily headlines, not a company-profile fallback.

If any of those come back as "this feature will be available in a future update", you've hit the Topic-wiring gap — revisit Step 8, confirm all 11 Topics are present, cut a new version, and activate.

From the CLI you can replicate the chat leg directly:

```bash
TOKEN=$(curl -s -X POST https://og256a1neb.execute-api.us-east-1.amazonaws.com/prod/oauth/agent-token \
  -H "Content-Type: application/json" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

SID=$(curl -s -X POST "https://api.salesforce.com/einstein/ai-agent/v1/agents/0XxgK000001JItVSAW/sessions" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"externalSessionKey":"'"$(uuidgen)"'","instanceConfig":{"endpoint":"https://orgfarm-035b70d101-dev-ed.develop.my.salesforce.com"},"streamingCapabilities":{"chunkTypes":["Text"]},"bypassUser":true}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['sessionId'])")

curl -sN -X POST "https://api.salesforce.com/einstein/ai-agent/v1/sessions/$SID/messages/stream" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -H "Accept: text/event-stream" \
  -d '{"message":{"type":"Text","text":"Tell me about NVDA","sequenceId":1}}' --max-time 45
```

---

## Known gaps / manual bits

These are the places where the build story is not fully automated today. Each is a candidate for a follow-up spec.

| # | Gap | Impact | Who owns |
|---|---|---|---|
| 1 | Data Cloud / CRM seed is custom-object based and manual. Real Data Cloud DMO ingestion is not wired. | Agent only knows the 10 seeded tickers. | 005 / 003 |
| 2 | **External Client App creation is UI-only.** No Metadata API coverage for `ExternalClientApplication`. | Every new org requires ~5 minutes of clicking. Screenshots in `docs/external-client-app-setup-instructions.md`. | Salesforce platform |
| 3 | **PKCE Connected App creation is UI-only** in practice (metadata exists but provisioning lag is unreliable). | Another 5 minutes of clicking; 10 minute wait after save. | Salesforce platform |
| 4 | Custom Label values (`IR_AWS_API_URL`, `IR_AWS_API_KEY`) must be set after the AWS stack exists. | A two-phase deploy — can't do it all in one `sf project deploy`. | 005 |
| 5 | Permission Set → External Credential Principal mapping is UI-only. | One-time 1-minute click after `configure-aws-connection.sh`. | Salesforce platform |
| 6 | Agent Topic activation (`New Version → Commit → Activate`) is UI-only. | Easiest step to forget. Was the root cause of the `0AfgK00000JdUGESA3` deflect regression. | Salesforce platform |
| 7 | CloudFront invalidation after frontend deploy takes 5–10 min on first deploy. | Acceptable; not a blocker. | AWS |
| 8 | No end-to-end smoke test script. Smoke test is manual browser-based. | Medium — hard to catch regressions like the Topic wiring. Recommend promoting `.kiro-tmp-005-e2e/run_10_queries.py` into `scripts/`. | 005 |

---

## Reference — what lives where

```
my-agent-project-005-v2-integrations-fsi-investment_research_agent/
├── aws/                                  # SAM app — 7 Lambdas + API Gateway + CloudFront + S3
│   ├── sam-template.yaml
│   ├── mcp-servers/{sec-edgar,market-data,news-search}/
│   ├── strands-agents/{financial-analysis,sentiment-analysis,sse-proxy}/
│   └── token-proxy/
├── force-app/main/default/
│   ├── aiAuthoringBundles/IR_Research_Agent/    # 11 Topics live here — Step 8
│   ├── aiAuthoringBundles/IR_Compliance_Agent/  # Companion compliance agent
│   ├── classes/                                 # 12 Apex classes
│   ├── objects/                                 # 5 custom objects
│   ├── externalCredentials/                     # AWS_IR_API_Credential
│   ├── namedCredentials/                        # AWS_IR_API
│   ├── remoteSiteSettings/                      # AWS_IR_MCP_API
│   ├── labels/IR_AWS_API_URL.labels-meta.xml    # IR_AWS_API_URL + IR_AWS_API_KEY
│   └── permissionsets/IR_Agent_Access/
├── frontend/                             # React + Vite + SLDS
│   ├── .env.example                      # Template for Step 9
│   └── src/
├── scripts/
│   ├── configure-aws-connection.sh       # Step 7 hand-off
│   ├── configure-langfuse.sh             # Optional observability
│   ├── configure-sentiment-agent.sh      # Wires News API URL into sentiment Lambda
│   ├── deploy-frontend.sh                # Step 10
│   └── setup-frontend-auth.sh
└── docs/
    ├── end-to-end-test-results-30-queries.md   # The 2026-04-18 test run
    ├── external-client-app-setup-instructions.md
    ├── manual-setup-guide.md                    # UI-only steps expanded
    └── reproducibility-from-zero.md             # This file
```
