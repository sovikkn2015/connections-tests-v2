#!/usr/bin/env bash
# ============================================================
# Create or update AWS Secrets Manager secret for OpenClaw FSI
#
# Auto-populates credentials from:
#   1. Salesforce CLI (sf org display)
#   2. SAM stack outputs (CloudFormation)
#   3. Environment variables
#   4. Existing Secrets Manager values (preserves what's already set)
#
# NEVER writes REPLACE_ME_* placeholders. If a value can't be
# determined, the existing secret value is preserved.
#
# Idempotent — safe to run multiple times.
#
# Usage:
#   ./setup-secrets.sh
#   ./setup-secrets.sh --sam-stack-name my-custom-stack
#
# Override defaults via env vars:
#   AWS_REGION=us-west-2 SF_TARGET_ORG=my-org ./setup-secrets.sh
# ============================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults & CLI args
# ---------------------------------------------------------------------------
AWS_REGION="${AWS_REGION:-us-east-1}"
SECRET_NAME="${SECRET_NAME:-openclaw-fsi-secrets}"
SF_TARGET_ORG="${SF_TARGET_ORG:-new-org}"
SAM_STACK_NAME="openclaw-006-mcp"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sam-stack-name)
      SAM_STACK_NAME="$2"
      shift 2
      ;;
    --sam-stack-name=*)
      SAM_STACK_NAME="${1#*=}"
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

echo "=== OpenClaw FSI — Secrets Manager Setup ==="
echo "Region:     ${AWS_REGION}"
echo "Secret:     ${SECRET_NAME}"
echo "SF Org:     ${SF_TARGET_ORG}"
echo "SAM Stack:  ${SAM_STACK_NAME}"
echo "Timestamp:  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# ---------------------------------------------------------------------------
# Helper: track populated vs missing for summary
# ---------------------------------------------------------------------------
declare -A SOURCE_MAP
POPULATED=()
MISSING=()

track() {
  local key="$1" val="$2" source="$3"
  if [ -n "${val}" ]; then
    SOURCE_MAP["${key}"]="${source}"
    POPULATED+=("${key}")
  else
    MISSING+=("${key}")
  fi
}

# ---------------------------------------------------------------------------
# Step 1: Read existing secret (if it exists)
# ---------------------------------------------------------------------------
echo "[1/5] Reading existing secret..."
EXISTING_SECRET=""
SECRET_EXISTS=false

if aws secretsmanager describe-secret \
    --secret-id "${SECRET_NAME}" \
    --region "${AWS_REGION}" &>/dev/null; then
  SECRET_EXISTS=true
  EXISTING_SECRET=$(aws secretsmanager get-secret-value \
    --secret-id "${SECRET_NAME}" \
    --region "${AWS_REGION}" \
    --query 'SecretString' \
    --output text 2>/dev/null || echo "{}")
  echo "  Existing secret found."
else
  echo "  No existing secret — will create new."
  EXISTING_SECRET="{}"
fi

# Helper: get existing value for a key (returns empty if missing or REPLACE_ME)
existing_val() {
  local val
  val=$(echo "${EXISTING_SECRET}" | jq -r --arg k "$1" '.[$k] // ""')
  # Treat REPLACE_ME_* placeholders as empty
  if [[ "${val}" == REPLACE_ME* ]]; then
    val=""
  fi
  echo "${val}"
}

# ---------------------------------------------------------------------------
# Step 2: Auto-fetch from Salesforce CLI
# ---------------------------------------------------------------------------
echo "[2/5] Fetching Salesforce credentials..."
SF_INSTANCE_URL=""
SF_ACCESS_TOKEN=""

if command -v sf &>/dev/null; then
  SF_ORG_JSON=$(sf org display --target-org "${SF_TARGET_ORG}" --json 2>/dev/null || echo "{}")
  SF_INSTANCE_URL=$(echo "${SF_ORG_JSON}" | jq -r '.result.instanceUrl // ""')
  SF_ACCESS_TOKEN=$(echo "${SF_ORG_JSON}" | jq -r '.result.accessToken // ""')
  if [ -n "${SF_INSTANCE_URL}" ] && [ "${SF_INSTANCE_URL}" != "null" ]; then
    echo "  SF_INSTANCE_URL: fetched from CLI"
  else
    SF_INSTANCE_URL=""
    echo "  SF_INSTANCE_URL: CLI returned empty"
  fi
  if [ -n "${SF_ACCESS_TOKEN}" ] && [ "${SF_ACCESS_TOKEN}" != "null" ]; then
    echo "  SF_ACCESS_TOKEN: fetched from CLI (${#SF_ACCESS_TOKEN} chars)"
  else
    SF_ACCESS_TOKEN=""
    echo "  SF_ACCESS_TOKEN: CLI returned empty"
  fi
else
  echo "  Salesforce CLI (sf) not found — skipping."
fi

# Fall back to env, then existing secret
SF_INSTANCE_URL="${SF_INSTANCE_URL:-$(existing_val SF_INSTANCE_URL)}"
SF_ACCESS_TOKEN="${SF_ACCESS_TOKEN:-$(existing_val SF_ACCESS_TOKEN)}"

track "SF_INSTANCE_URL" "${SF_INSTANCE_URL}" "sf-cli/env/existing"
track "SF_ACCESS_TOKEN" "${SF_ACCESS_TOKEN}" "sf-cli/env/existing"

# ---------------------------------------------------------------------------
# Step 3: Auto-fetch from SAM stack outputs (MCP Gateway)
# ---------------------------------------------------------------------------
echo "[3/5] Fetching MCP Gateway from SAM stack '${SAM_STACK_NAME}'..."
MCP_GATEWAY_URL=""
MCP_API_KEY=""

MCP_GATEWAY_URL=$(aws cloudformation describe-stacks \
  --stack-name "${SAM_STACK_NAME}" \
  --region "${AWS_REGION}" \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
  --output text 2>/dev/null || echo "")

if [ -n "${MCP_GATEWAY_URL}" ] && [ "${MCP_GATEWAY_URL}" != "None" ]; then
  echo "  MCP_GATEWAY_URL: fetched from stack outputs"
else
  MCP_GATEWAY_URL=""
  echo "  MCP_GATEWAY_URL: stack not found or no output"
fi

API_KEY_ID=$(aws cloudformation describe-stacks \
  --stack-name "${SAM_STACK_NAME}" \
  --region "${AWS_REGION}" \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiKeyId`].OutputValue' \
  --output text 2>/dev/null || echo "")

if [ -n "${API_KEY_ID}" ] && [ "${API_KEY_ID}" != "None" ]; then
  MCP_API_KEY=$(aws apigateway get-api-key \
    --api-key "${API_KEY_ID}" \
    --include-value \
    --region "${AWS_REGION}" \
    --query 'value' \
    --output text 2>/dev/null || echo "")
  if [ -n "${MCP_API_KEY}" ]; then
    echo "  MCP_API_KEY: fetched from API Gateway"
  else
    echo "  MCP_API_KEY: key ID found but value retrieval failed"
  fi
else
  echo "  MCP_API_KEY: no ApiKeyId in stack outputs"
fi

# Fall back to env, then existing secret
MCP_GATEWAY_URL="${MCP_GATEWAY_URL:-$(existing_val MCP_GATEWAY_URL)}"
MCP_API_KEY="${MCP_API_KEY:-$(existing_val MCP_API_KEY)}"

track "MCP_GATEWAY_URL" "${MCP_GATEWAY_URL}" "sam-stack/env/existing"
track "MCP_API_KEY" "${MCP_API_KEY}" "sam-stack/env/existing"

# ---------------------------------------------------------------------------
# Step 4: Environment variable fallbacks + gateway token generation
# ---------------------------------------------------------------------------
echo "[4/5] Resolving remaining values from environment..."

# Gateway token: env → existing → generate new
OPENCLAW_GATEWAY_TOKEN="${OPENCLAW_GATEWAY_TOKEN:-$(existing_val OPENCLAW_GATEWAY_TOKEN)}"
if [ -z "${OPENCLAW_GATEWAY_TOKEN}" ]; then
  OPENCLAW_GATEWAY_TOKEN=$(openssl rand -hex 32)
  echo "  OPENCLAW_GATEWAY_TOKEN: generated new (64 chars)"
  track "OPENCLAW_GATEWAY_TOKEN" "${OPENCLAW_GATEWAY_TOKEN}" "generated"
else
  echo "  OPENCLAW_GATEWAY_TOKEN: from env/existing"
  track "OPENCLAW_GATEWAY_TOKEN" "${OPENCLAW_GATEWAY_TOKEN}" "env/existing"
fi

# Tavily: env → existing
TAVILY_API_KEY="${TAVILY_API_KEY:-$(existing_val TAVILY_API_KEY)}"
echo "  TAVILY_API_KEY: $([ -n "${TAVILY_API_KEY}" ] && echo 'set' || echo 'NOT SET')"
track "TAVILY_API_KEY" "${TAVILY_API_KEY}" "env/existing"

# Alpha Vantage: env → existing
ALPHA_VANTAGE_API_KEY="${ALPHA_VANTAGE_API_KEY:-$(existing_val ALPHA_VANTAGE_API_KEY)}"
echo "  ALPHA_VANTAGE_API_KEY: $([ -n "${ALPHA_VANTAGE_API_KEY}" ] && echo 'set' || echo 'NOT SET')"
track "ALPHA_VANTAGE_API_KEY" "${ALPHA_VANTAGE_API_KEY}" "env/existing"

# Langfuse: env → existing
LANGFUSE_SECRET_KEY="${LANGFUSE_SECRET_KEY:-$(existing_val LANGFUSE_SECRET_KEY)}"
echo "  LANGFUSE_SECRET_KEY: $([ -n "${LANGFUSE_SECRET_KEY}" ] && echo 'set' || echo 'NOT SET')"
track "LANGFUSE_SECRET_KEY" "${LANGFUSE_SECRET_KEY}" "env/existing"

LANGFUSE_PUBLIC_KEY="${LANGFUSE_PUBLIC_KEY:-$(existing_val LANGFUSE_PUBLIC_KEY)}"
echo "  LANGFUSE_PUBLIC_KEY: $([ -n "${LANGFUSE_PUBLIC_KEY}" ] && echo 'set' || echo 'NOT SET')"
track "LANGFUSE_PUBLIC_KEY" "${LANGFUSE_PUBLIC_KEY}" "env/existing"

LANGFUSE_BASE_URL="${LANGFUSE_BASE_URL:-$(existing_val LANGFUSE_BASE_URL)}"
LANGFUSE_BASE_URL="${LANGFUSE_BASE_URL:-https://us.cloud.langfuse.com}"
echo "  LANGFUSE_BASE_URL: ${LANGFUSE_BASE_URL}"
track "LANGFUSE_BASE_URL" "${LANGFUSE_BASE_URL}" "env/existing/default"

# ---------------------------------------------------------------------------
# Step 5: Build final JSON and write to Secrets Manager
# ---------------------------------------------------------------------------
echo ""
echo "[5/5] Writing secret to Secrets Manager..."

NEW_JSON=$(jq -n \
  --arg gw_token  "${OPENCLAW_GATEWAY_TOKEN}" \
  --arg sf_url    "${SF_INSTANCE_URL}" \
  --arg sf_token  "${SF_ACCESS_TOKEN}" \
  --arg mcp_url   "${MCP_GATEWAY_URL}" \
  --arg mcp_key   "${MCP_API_KEY}" \
  --arg tavily    "${TAVILY_API_KEY}" \
  --arg alpha     "${ALPHA_VANTAGE_API_KEY}" \
  --arg lf_secret "${LANGFUSE_SECRET_KEY}" \
  --arg lf_public "${LANGFUSE_PUBLIC_KEY}" \
  --arg lf_url    "${LANGFUSE_BASE_URL}" \
  '{
    OPENCLAW_GATEWAY_TOKEN: $gw_token,
    SF_INSTANCE_URL:        $sf_url,
    SF_ACCESS_TOKEN:        $sf_token,
    MCP_GATEWAY_URL:        $mcp_url,
    MCP_API_KEY:            $mcp_key,
    TAVILY_API_KEY:         $tavily,
    ALPHA_VANTAGE_API_KEY:  $alpha,
    LANGFUSE_SECRET_KEY:    $lf_secret,
    LANGFUSE_PUBLIC_KEY:    $lf_public,
    LANGFUSE_BASE_URL:      $lf_url
  }')

# Merge: start with existing, overlay only non-empty new values
MERGED_JSON=$(echo "${EXISTING_SECRET}" | jq --argjson new "${NEW_JSON}" '
  . as $old |
  $new | to_entries | reduce .[] as $e ($old;
    if ($e.value | length) > 0 then .[$e.key] = $e.value else . end
  )
')

if [ "${SECRET_EXISTS}" = true ]; then
  aws secretsmanager put-secret-value \
    --secret-id "${SECRET_NAME}" \
    --secret-string "${MERGED_JSON}" \
    --region "${AWS_REGION}" \
    > /dev/null
  echo "  Secret updated."
else
  aws secretsmanager create-secret \
    --name "${SECRET_NAME}" \
    --description "OpenClaw FSI agent credentials (Project 006)" \
    --secret-string "${MERGED_JSON}" \
    --region "${AWS_REGION}" \
    --tags Key=project,Value=006-openclaw-fsi Key=environment,Value=production \
    > /dev/null
  echo "  Secret created."
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== Summary ==="
echo ""

if [ ${#POPULATED[@]} -gt 0 ]; then
  echo "Populated (${#POPULATED[@]}):"
  for key in "${POPULATED[@]}"; do
    echo "  ✓ ${key} — ${SOURCE_MAP[${key}]:-unknown}"
  done
fi

echo ""

if [ ${#MISSING[@]} -gt 0 ]; then
  echo "Still missing (${#MISSING[@]}):"
  for key in "${MISSING[@]}"; do
    echo "  ✗ ${key} — set via environment variable or update secret directly"
  done
  echo ""
  echo "To set missing values, export them and re-run:"
  echo "  export TAVILY_API_KEY=... ALPHA_VANTAGE_API_KEY=..."
  echo "  ./setup-secrets.sh"
else
  echo "All 10 credential values are populated."
fi

echo ""
echo "Retrieve with:"
echo "  aws secretsmanager get-secret-value --secret-id ${SECRET_NAME} --region ${AWS_REGION} --query SecretString --output text | jq ."
