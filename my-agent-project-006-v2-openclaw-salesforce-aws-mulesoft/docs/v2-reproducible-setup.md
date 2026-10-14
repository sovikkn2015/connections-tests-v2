# 006 v2 — Reproducible Setup

Bootstrap a fresh AWS account from a clean clone. Zero credentials in git.

## Prerequisites

- AWS CLI authenticated (`aws sts get-caller-identity` returns your account)
- AWS SAM CLI + Docker (for `sam build --use-container` if you lack Python 3.12 locally)
- Salesforce CLI (`sf`) logged into your org: `sf org login web --alias new-org`
- Vendor API keys (free tiers are fine):
  - Finnhub — https://finnhub.io/register
  - Alpha Vantage — https://www.alphavantage.co/support/#api-key
  - Tavily — https://tavily.com
  - Langfuse — https://us.cloud.langfuse.com (optional but recommended)

## Secrets layout

All vendor credentials live in AWS Secrets Manager. The Lambdas hydrate them
via `aws/mcp-servers/shared/secrets_loader.py` at cold start. Nothing is passed
to SAM as a plaintext parameter.

| Secret name | Contents | Consumer |
|-------------|----------|----------|
| `/006-v2/vendors/market-data` | `{"FINNHUB_API_KEY":"...","ALPHA_VANTAGE_API_KEY":"..."}` | market-data Lambda |
| `/006-v2/vendors/news-search` | `{"TAVILY_API_KEY":"..."}` | news-search Lambda |
| `/006-v2/mulesoft/credentials` | `{"client_id":"...","client_secret":"...","base_url":"...","organization_id":"...","environment_id":"..."}` | mulesoft-actions Lambda |
| `/006-v2/vendors/alpaca` | `{"api_key":"...","api_secret":"...","base_url":"..."}` | mulesoft-actions (when MULESOFT_MODE=sandbox) |
| `/006-v2/hitl/signing-key` | `{"HITL_SIGNING_KEY":"<64-hex>"}` | mulesoft-api skill (HMAC for approval tokens) |

## One-time bootstrap

```bash
export AWS_REGION=us-east-1

# 1. Create vendor secrets (replace $FINNHUB_KEY etc with your values)
aws secretsmanager create-secret \
  --name /006-v2/vendors/market-data \
  --secret-string "{\"FINNHUB_API_KEY\":\"$FINNHUB_KEY\",\"ALPHA_VANTAGE_API_KEY\":\"$ALPHA_VANTAGE_KEY\"}" \
  --region $AWS_REGION

aws secretsmanager create-secret \
  --name /006-v2/vendors/news-search \
  --secret-string "{\"TAVILY_API_KEY\":\"$TAVILY_KEY\"}" \
  --region $AWS_REGION

# MuleSoft (mock mode — no real credentials needed until vendor sandbox approval)
aws secretsmanager create-secret \
  --name /006-v2/mulesoft/credentials \
  --secret-string '{"client_id":"mock","client_secret":"mock","base_url":"https://mock.local","organization_id":"mock","environment_id":"mock"}' \
  --region $AWS_REGION

# HITL signing key — regenerate for every environment
aws secretsmanager create-secret \
  --name /006-v2/hitl/signing-key \
  --secret-string "{\"HITL_SIGNING_KEY\":\"$(openssl rand -hex 32)\"}" \
  --region $AWS_REGION

# Alpaca (optional — only needed for sandbox/production MuleSoft mode)
aws secretsmanager create-secret \
  --name /006-v2/vendors/alpaca \
  --secret-string '{"api_key":"placeholder","api_secret":"placeholder","base_url":"https://paper-api.alpaca.markets"}' \
  --region $AWS_REGION

# 2. Deploy the stack. Langfuse keys and FrontendOrigin still come from
#    samconfig.toml (gitignored). Vendor keys DO NOT.
cd aws
sam build --use-container
sam deploy

# 3. Populate the shared openclaw-fsi-secrets (used by the agent runtime)
cd ..
./scripts/aws/setup-secrets.sh

# 4. Verify end-to-end
./scripts/verify-006-v2.sh
```

## Why this is reproducible

- `sam deploy` on a fresh account provisions identical Lambdas + IAM + API
  Gateway. The template grants each Lambda `secretsmanager:GetSecretValue`
  on its own secret only (least privilege).
- Lambda code imports `shared/secrets_loader.py`, which reads
  `VENDOR_SECRET_NAME` env var (set by SAM), calls Secrets Manager, and merges
  keys into `os.environ` before the rest of the module reads them. Existing
  env vars win, so local dev still works.
- Rotating a key = one call to `put-secret-value` + one Lambda restart. No
  code change, no redeploy.
- `samconfig.toml` is gitignored and now carries only Langfuse public/secret
  and the CloudFront origin. Everything else moved to Secrets Manager.

## Rotating a key

```bash
aws secretsmanager put-secret-value \
  --secret-id /006-v2/vendors/market-data \
  --secret-string "{\"FINNHUB_API_KEY\":\"$NEW_FINNHUB\",\"ALPHA_VANTAGE_API_KEY\":\"$EXISTING_AV\"}" \
  --region us-east-1

aws lambda update-function-configuration \
  --function-name openclaw-mcp-006-v2-market-data \
  --environment "$(aws lambda get-function-configuration \
     --function-name openclaw-mcp-006-v2-market-data \
     --query 'Environment' --output json)" \
  --region us-east-1 >/dev/null
# The above is a no-op update that forces Lambda to drop warm containers,
# so the next invocation re-hydrates from Secrets Manager.
```

## What is NOT in Secrets Manager (by design)

- **Langfuse keys** — observability-only, no data access, pk-lf/sk-lf scoped.
  Live in samconfig.toml (gitignored). Move to Secrets Manager if you're
  paranoid.
- **SF_ACCESS_TOKEN** — lifecycled by `scripts/refresh-sf-token.py`; rotated
  via a scheduled Lambda (`openclaw-006-sf-rotation-rotate`). Don't persist.
- **MCP_API_KEY** — issued by API Gateway at stack creation, retrieved via
  `aws apigateway get-api-key`. Not a secret in the vendor sense.
- **FRONTEND_ORIGIN** — public CloudFront URL, not a secret.
