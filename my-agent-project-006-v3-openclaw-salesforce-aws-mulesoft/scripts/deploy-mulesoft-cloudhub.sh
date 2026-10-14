#!/usr/bin/env bash
# deploy-mulesoft-cloudhub.sh — Deploy 3 MuleSoft apps to CloudHub Sandbox
# using the Anypoint Platform REST API (not Maven, which has Exchange version conflicts).
#
# Prerequisites:
#   - Anypoint creds in SSM: /006-v3/mulesoft/{org_id,client-id,client-secret}
#   - Alpaca creds in Secrets Manager: /006-v3/vendors/alpaca
#   - Dwolla creds in Secrets Manager: /006-v3/vendors/dwolla
#   - Secure properties key in SSM: /006-v3/mulesoft/secure-properties-key
#   - Apps already published to Exchange (mvn deploy -Pcloudhub-sandbox)
#
# Usage: bash scripts/deploy-mulesoft-cloudhub.sh

set -euo pipefail

echo "=== MuleSoft CloudHub Deploy ==="

# 1. Fetch credentials from AWS
echo "[1/6] Fetching Anypoint credentials from SSM..."
ORG_ID=$(aws ssm get-parameter --region us-east-1 --name /006-v3/mulesoft/org_id --with-decryption --query 'Parameter.Value' --output text)
CLIENT_ID=$(aws ssm get-parameter --region us-east-1 --name /006-v3/mulesoft/client-id --with-decryption --query 'Parameter.Value' --output text)
CLIENT_SECRET=$(aws ssm get-parameter --region us-east-1 --name /006-v3/mulesoft/client-secret --with-decryption --query 'Parameter.Value' --output text)
SECURE_KEY=$(aws ssm get-parameter --region us-east-1 --name /006-v3/mulesoft/secure-properties-key --with-decryption --query 'Parameter.Value' --output text)

echo "  ORG_ID: ${ORG_ID:0:8}..."
echo "  CLIENT_ID: ${CLIENT_ID:0:8}..."

# 2. Get Anypoint access token
echo "[2/6] Getting Anypoint access token..."
TOKEN=$(curl -sf -X POST https://anypoint.mulesoft.com/accounts/api/v2/oauth2/token \
  -H 'Content-Type: application/json' \
  -d "{\"grant_type\":\"client_credentials\",\"client_id\":\"$CLIENT_ID\",\"client_secret\":\"$CLIENT_SECRET\"}" | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")
echo "  Token obtained (${#TOKEN} chars)"

# 3. Get Sandbox environment ID
echo "[3/6] Getting Sandbox environment ID..."
ENV_ID=$(curl -sf "https://anypoint.mulesoft.com/accounts/api/organizations/$ORG_ID/environments" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "
import json,sys
for e in json.load(sys.stdin).get('data',[]):
    if 'sandbox' in e.get('name','').lower():
        print(e['id']); break
")
echo "  Sandbox ENV_ID: $ENV_ID"

# 4. Fetch vendor credentials for secure properties
echo "[4/6] Fetching vendor credentials..."
ALPACA_KEY=$(aws secretsmanager get-secret-value --region us-east-1 --secret-id /006-v3/vendors/alpaca --query 'SecretString' --output text | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('key_id',''))")
ALPACA_SECRET=$(aws secretsmanager get-secret-value --region us-east-1 --secret-id /006-v3/vendors/alpaca --query 'SecretString' --output text | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('secret',''))")
DWOLLA_KEY=$(aws secretsmanager get-secret-value --region us-east-1 --secret-id /006-v3/vendors/dwolla --query 'SecretString' --output text | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('client_id',''))")
DWOLLA_SECRET=$(aws secretsmanager get-secret-value --region us-east-1 --secret-id /006-v3/vendors/dwolla --query 'SecretString' --output text | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('client_secret',''))")
MCP_KEY=$(aws ssm get-parameter --region us-east-1 --name /006-v3/mcp/api-key --with-decryption --query 'Parameter.Value' --output text)
WEBHOOK_HMAC=$(aws secretsmanager get-secret-value --region us-east-1 --secret-id /006-v3/vendors/alpaca-webhook --query 'SecretString' --output text 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('hmac_secret','defaulthmac'))" 2>/dev/null || echo "defaulthmac")

echo "  Alpaca key: ${ALPACA_KEY:0:8}..."
echo "  Dwolla key: ${DWOLLA_KEY:0:8}..."

# 5. Deploy each app via CloudHub API
echo "[5/6] Deploying apps to CloudHub Sandbox..."

deploy_app() {
  local APP_NAME=$1
  local PROPERTIES=$2

  echo "  Deploying $APP_NAME..."

  # Check if app exists
  local EXISTS=$(curl -sf "https://anypoint.mulesoft.com/cloudhub/api/v2/applications/$APP_NAME" \
    -H "Authorization: Bearer $TOKEN" \
    -H "X-ANYPNT-ENV-ID: $ENV_ID" 2>/dev/null | python3 -c "import json,sys; print('yes')" 2>/dev/null || echo "no")

  local METHOD="POST"
  local URL="https://anypoint.mulesoft.com/cloudhub/api/v2/applications"
  if [ "$EXISTS" = "yes" ]; then
    METHOD="PUT"
    URL="https://anypoint.mulesoft.com/cloudhub/api/v2/applications/$APP_NAME"
  fi

  local RESULT=$(curl -sf -X "$METHOD" "$URL" \
    -H "Authorization: Bearer $TOKEN" \
    -H "X-ANYPNT-ENV-ID: $ENV_ID" \
    -H "Content-Type: application/json" \
    -d "{
      \"domain\": \"$APP_NAME\",
      \"muleVersion\": {\"version\": \"4.9.0\"},
      \"region\": \"us-east-1\",
      \"workers\": {\"amount\": 1, \"type\": {\"name\": \"Micro\", \"weight\": 0.1}},
      \"properties\": $PROPERTIES,
      \"monitoringAutoRestart\": true,
      \"persistentQueues\": false
    }" 2>&1)

  echo "$RESULT" | python3 -c "
import json,sys
try:
    d = json.load(sys.stdin)
    print(f'    Status: {d.get(\"status\", d.get(\"domain\",\"?\"))}')
except:
    print(f'    Response: {sys.stdin.read()[:200]}')
" 2>/dev/null || echo "    Deploy request sent"
}

# submit-order
deploy_app "openclaw-v3-submit-order" "{
  \"mule.secure.properties.key\": \"$SECURE_KEY\",
  \"alpaca.endpoint_host\": \"paper-api.alpaca.markets\",
  \"alpaca.endpoint_path\": \"/v2/orders\",
  \"alpaca.key_id\": \"$ALPACA_KEY\",
  \"alpaca.secret\": \"$ALPACA_SECRET\",
  \"mock_mode\": \"false\"
}"

# initiate-wire
deploy_app "openclaw-v3-initiate-wire" "{
  \"mule.secure.properties.key\": \"$SECURE_KEY\",
  \"dwolla.endpoint_host\": \"api-sandbox.dwolla.com\",
  \"dwolla.endpoint_path\": \"/transfers\",
  \"dwolla.token_host\": \"api-sandbox.dwolla.com\",
  \"dwolla.token_path\": \"/token\",
  \"dwolla.client_id\": \"$DWOLLA_KEY\",
  \"dwolla.client_secret\": \"$DWOLLA_SECRET\",
  \"mock_mode\": \"false\"
}"

# order-status-webhook
deploy_app "openclaw-v3-order-status-webhook" "{
  \"mule.secure.properties.key\": \"$SECURE_KEY\",
  \"mcp.endpoint_host\": \"e5zbqnkmx8.execute-api.us-east-1.amazonaws.com\",
  \"mcp.endpoint_path\": \"/v3/mcp/mulesoft-actions/tools/call\",
  \"mcp.api_key\": \"$MCP_KEY\",
  \"webhook.hmac_secret\": \"$WEBHOOK_HMAC\",
  \"mock_mode\": \"false\"
}"

# 6. Verify
echo ""
echo "[6/6] Checking app status..."
sleep 5
curl -sf "https://anypoint.mulesoft.com/cloudhub/api/v2/applications" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-ANYPNT-ENV-ID: $ENV_ID" | python3 -c "
import json,sys
apps = json.load(sys.stdin)
for a in apps:
    d = a.get('domain','')
    if 'openclaw' in d:
        print(f'  {d}: {a.get(\"status\",\"?\")}')
" 2>/dev/null || echo "  (check Anypoint Runtime Manager UI)"

echo ""
echo "=== Done. Apps deploying to CloudHub Sandbox. ==="
echo "Monitor at: https://anypoint.mulesoft.com/cloudhub/#/console/applications"
echo ""
echo "After apps reach STARTED status, update the agent config:"
echo "  Set MULESOFT_MODE=sandbox in AgentCore env"
echo "  Rebuild: bash scripts/build-and-push-openclaw.sh && bash scripts/create-v3-agentcore.sh"
