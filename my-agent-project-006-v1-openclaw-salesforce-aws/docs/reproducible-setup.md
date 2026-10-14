# 006 v1 — Reproducible Setup

Bootstrap a fresh AWS account from a clean clone. Zero vendor credentials in git.

## What this addresses

Task 1.1 from `docs/006-design-vs-reality-assessment.md` was PARTIAL because
Secrets Manager entries had placeholder values and vendor API keys were passed
as plaintext SAM parameters. This doc covers the finished pattern.

## Prerequisites

- AWS CLI authenticated (`aws sts get-caller-identity` works)
- AWS SAM CLI + Python 3.12 (or Docker for `sam build --use-container`)
- Salesforce CLI logged into your org
- Vendor API keys:
  - Finnhub — https://finnhub.io/register
  - Alpha Vantage — https://www.alphavantage.co/support/#api-key
  - Tavily — https://tavily.com
  - Langfuse — https://us.cloud.langfuse.com (optional)

## Secrets layout

Vendor credentials live in AWS Secrets Manager. The Lambdas hydrate them via
`aws/mcp-servers/shared/secrets_loader.py` at cold start.

| Secret name | Contents | Consumer |
|-------------|----------|----------|
| `/006/vendors/market-data` | `{"FINNHUB_API_KEY":"...","ALPHA_VANTAGE_API_KEY":"..."}` | market-data Lambda |
| `/006/vendors/news-search` | `{"TAVILY_API_KEY":"..."}` | news-search Lambda |
| `openclaw-fsi-secrets` | OAuth, gateway tokens, Langfuse, MCP key | OpenClaw runtime, scripts |

## One-time bootstrap

```bash
export AWS_REGION=us-east-1

# 1. Create vendor secrets
aws secretsmanager create-secret \
  --name /006/vendors/market-data \
  --secret-string "{\"FINNHUB_API_KEY\":\"$FINNHUB_KEY\",\"ALPHA_VANTAGE_API_KEY\":\"$ALPHA_VANTAGE_KEY\"}" \
  --region $AWS_REGION

aws secretsmanager create-secret \
  --name /006/vendors/news-search \
  --secret-string "{\"TAVILY_API_KEY\":\"$TAVILY_KEY\"}" \
  --region $AWS_REGION

# 2. Deploy the stack. Vendor keys are NOT passed as SAM parameters anymore.
cd aws
sam build --use-container
sam deploy --stack-name openclaw-mcp-006 --resolve-s3 --capabilities CAPABILITY_IAM

# 3. Populate the runtime secret
cd ..
./scripts/aws/setup-secrets.sh

# 4. Verify
./scripts/verify-006.sh
```

## Why this is reproducible

- `sam deploy` on a fresh AWS account provisions identical Lambdas + IAM + API
  Gateway. The template grants each Lambda `secretsmanager:GetSecretValue` on
  its own secret only (least privilege).
- Lambda code imports `shared/secrets_loader.py`, which reads
  `VENDOR_SECRET_NAME` env var (set by SAM), calls Secrets Manager, merges
  keys into `os.environ` before the module's own reads. Existing env vars
  win, so local dev still works.
- Rotating a key = one `put-secret-value` + one Lambda env no-op update to
  force a cold start. No code change, no redeploy.

## Rotating a key

```bash
# 1. Put new value
aws secretsmanager put-secret-value \
  --secret-id /006/vendors/market-data \
  --secret-string "{\"FINNHUB_API_KEY\":\"$NEW\",\"ALPHA_VANTAGE_API_KEY\":\"$EXISTING_AV\"}" \
  --region us-east-1

# 2. Force Lambda to drop warm containers so next call re-hydrates
aws lambda update-function-configuration \
  --function-name openclaw-mcp-006-market-data \
  --environment "$(aws lambda get-function-configuration \
      --function-name openclaw-mcp-006-market-data \
      --query 'Environment' --output json)" \
  --region us-east-1 >/dev/null
```

## What is NOT in Secrets Manager (by design)

- Langfuse keys — observability only, no data access. Live in samconfig.toml
  (gitignored) or similar.
- SF_ACCESS_TOKEN — lifecycled by rotation Lambda.
- MCP_API_KEY — issued by API Gateway at stack creation.
- FRONTEND_ORIGIN — public CloudFront URL, not a secret.

## What changed vs the original plaintext-params layout

1. `aws/mcp-servers/shared/secrets_loader.py` — new shared helper
2. `aws/mcp-servers/market-data/app.py` — imports loader, reads from
   `/006/vendors/market-data`
3. `aws/mcp-servers/news-search/app.py` — imports loader, reads from
   `/006/vendors/news-search`
4. `aws/sam-template.yaml` — each Lambda gets a least-privilege
   `secretsmanager:GetSecretValue` policy and a `VENDOR_SECRET_NAME` env var.
   The `AlphaVantageApiKey`, `FinnhubApiKey`, `TavilyApiKey` parameters
   are now deprecated no-ops kept only for backwards compat.
