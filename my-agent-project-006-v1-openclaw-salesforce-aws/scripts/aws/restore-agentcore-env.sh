#!/usr/bin/env bash
# ============================================================================
# restore-agentcore-env.sh — Rebuild AgentCore runtime env vars after deploy
#
# `agentcore launch` wipes the runtime environmentVariables on every deploy.
# This script reconstructs them from authoritative sources (Secrets Manager,
# SAM outputs, Salesforce CLI) and re-applies them via update-agent-runtime.
#
# Idempotent — safe to run multiple times.
#
# Usage:
#   ./scripts/aws/restore-agentcore-env.sh
#   ./scripts/aws/restore-agentcore-env.sh --agent fsi_research_agent-Sr1m3j3MUh
#   ./scripts/aws/restore-agentcore-env.sh --dry-run
#   AWS_REGION=us-east-1 ./scripts/aws/restore-agentcore-env.sh
# ============================================================================

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
AGENT_RUNTIME_ID="${AGENT_RUNTIME_ID:-fsi_research_agent-Sr1m3j3MUh}"
SAM_STACK_NAME="${SAM_STACK_NAME:-openclaw-mcp-006}"
SF_TARGET_ORG="${SF_TARGET_ORG:-new-org}"
EXEC_ROLE_ARN="${EXEC_ROLE_ARN:-arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/AmazonBedrockAgentCoreSDKRuntime-us-east-1-a63986f981}"

MARKET_DATA_SECRET="${MARKET_DATA_SECRET:-/006/vendors/market-data}"
NEWS_SEARCH_SECRET="${NEWS_SEARCH_SECRET:-/006/vendors/news-search}"
GATEWAY_TOKEN_SECRET="${GATEWAY_TOKEN_SECRET:-openclaw/gateway-token}"
LANGFUSE_SECRET_NAME="${LANGFUSE_SECRET_NAME:-whalthy-v27/langfuse}"

DRY_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent) AGENT_RUNTIME_ID="$2"; shift 2 ;;
    --region) AWS_REGION="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

log()   { printf "\033[1;34m[restore-env]\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m[restore-env WARN]\033[0m %s\n" "$*" >&2; }
fatal() { printf "\033[1;31m[restore-env FATAL]\033[0m %s\n" "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Fetch current runtime metadata
# ---------------------------------------------------------------------------
log "Fetching runtime state: ${AGENT_RUNTIME_ID}"
RUNTIME_JSON=$(aws bedrock-agentcore-control get-agent-runtime \
  --agent-runtime-id "${AGENT_RUNTIME_ID}" \
  --region "${AWS_REGION}" \
  --output json) || fatal "Runtime ${AGENT_RUNTIME_ID} not found in ${AWS_REGION}"

CURRENT_IMG=$(echo "${RUNTIME_JSON}" | python3 -c "import json,sys; print(json.load(sys.stdin)['agentRuntimeArtifact']['containerConfiguration']['containerUri'])")
CURRENT_STATUS=$(echo "${RUNTIME_JSON}" | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])")
CURRENT_VER=$(echo "${RUNTIME_JSON}" | python3 -c "import json,sys; print(json.load(sys.stdin)['agentRuntimeVersion'])")
MEMORY_ID=$(echo "${RUNTIME_JSON}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('environmentVariables',{}).get('BEDROCK_AGENTCORE_MEMORY_ID',''))")
MEMORY_NAME=$(echo "${RUNTIME_JSON}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('environmentVariables',{}).get('BEDROCK_AGENTCORE_MEMORY_NAME',''))")

log "  image:    ${CURRENT_IMG}"
log "  status:   ${CURRENT_STATUS} (v${CURRENT_VER})"
log "  memory:   ${MEMORY_ID}"

if [[ "${CURRENT_STATUS}" != "READY" ]]; then
  fatal "Runtime is ${CURRENT_STATUS}, not READY. Wait for it to stabilize."
fi

# ---------------------------------------------------------------------------
# Resolve all env values from authoritative sources
# ---------------------------------------------------------------------------
log "Resolving env values..."

# MCP gateway URL + API key from SAM stack outputs
MCP_GATEWAY_URL=$(aws cloudformation describe-stacks \
  --stack-name "${SAM_STACK_NAME}" --region "${AWS_REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiGatewayUrl'].OutputValue" \
  --output text 2>/dev/null || echo "")
API_KEY_ID=$(aws cloudformation describe-stacks \
  --stack-name "${SAM_STACK_NAME}" --region "${AWS_REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='ApiKeyId'].OutputValue" \
  --output text 2>/dev/null || echo "")
MCP_API_KEY=""
if [[ -n "${API_KEY_ID}" && "${API_KEY_ID}" != "None" ]]; then
  MCP_API_KEY=$(aws apigateway get-api-key --api-key "${API_KEY_ID}" \
    --include-value --region "${AWS_REGION}" --query value --output text 2>/dev/null || echo "")
fi
[[ -z "${MCP_GATEWAY_URL}" ]] && warn "MCP_GATEWAY_URL not resolved from SAM stack ${SAM_STACK_NAME}"
[[ -z "${MCP_API_KEY}" ]] && warn "MCP_API_KEY not resolved from SAM stack"

# Salesforce from sf CLI
SF_URL=""; SF_TOK=""
if command -v sf >/dev/null 2>&1; then
  SF_JSON=$(sf org display --target-org "${SF_TARGET_ORG}" --json 2>/dev/null || echo "{}")
  SF_URL=$(echo "${SF_JSON}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('result',{}).get('instanceUrl',''))")
  SF_TOK=$(echo "${SF_JSON}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('result',{}).get('accessToken',''))")
fi
[[ -z "${SF_URL}" ]] && warn "SF_INSTANCE_URL not resolved (sf org display ${SF_TARGET_ORG} failed)"

# Vendor keys from Secrets Manager
read_secret_field() {
  local secret="$1" field="$2"
  aws secretsmanager get-secret-value --secret-id "${secret}" --region "${AWS_REGION}" \
    --query SecretString --output text 2>/dev/null \
    | python3 -c "import json,sys; d=json.loads(sys.stdin.read() or '{}'); print(d.get('${field}',''))" 2>/dev/null || echo ""
}

FINNHUB_API_KEY=$(read_secret_field "${MARKET_DATA_SECRET}" "FINNHUB_API_KEY")
ALPHA_VANTAGE_API_KEY=$(read_secret_field "${MARKET_DATA_SECRET}" "ALPHA_VANTAGE_API_KEY")
TAVILY_API_KEY=$(read_secret_field "${NEWS_SEARCH_SECRET}" "TAVILY_API_KEY")

# Shared tokens and Langfuse keys (from separate Secrets Manager entries)
# - GATEWAY_TOKEN_SECRET stores the raw token string (not JSON)
# - LANGFUSE_SECRET_NAME stores JSON with keys: secret_key, public_key (or LANGFUSE_*)
OPENCLAW_GATEWAY_TOKEN=$(aws secretsmanager get-secret-value --secret-id "${GATEWAY_TOKEN_SECRET}" --region "${AWS_REGION}" --query SecretString --output text 2>/dev/null || echo "")
# If gateway token JSON has .OPENCLAW_GATEWAY_TOKEN, extract it; otherwise assume raw string
if [[ "${OPENCLAW_GATEWAY_TOKEN}" == \{* ]]; then
  OPENCLAW_GATEWAY_TOKEN=$(echo "${OPENCLAW_GATEWAY_TOKEN}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('OPENCLAW_GATEWAY_TOKEN', d.get('token', '')))")
fi

LANGFUSE_JSON=$(aws secretsmanager get-secret-value --secret-id "${LANGFUSE_SECRET_NAME}" --region "${AWS_REGION}" --query SecretString --output text 2>/dev/null || echo "{}")
get_langfuse() {
  echo "${LANGFUSE_JSON}" | python3 -c "import json,sys; d=json.loads(sys.stdin.read() or '{}'); print(d.get('$1', d.get('$2', '')))"
}
LANGFUSE_SECRET_KEY=$(get_langfuse LANGFUSE_SECRET_KEY secret_key)
LANGFUSE_PUBLIC_KEY=$(get_langfuse LANGFUSE_PUBLIC_KEY public_key)
LANGFUSE_BASE_URL=$(get_langfuse LANGFUSE_BASE_URL base_url)
[[ -z "${LANGFUSE_BASE_URL}" ]] && LANGFUSE_BASE_URL="https://us.cloud.langfuse.com"

# Hooks token: preserve existing if on runtime, else generate (OpenClaw requires
# hooks.token != gateway.auth.token).
OPENCLAW_HOOKS_TOKEN=$(echo "${RUNTIME_JSON}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('environmentVariables',{}).get('OPENCLAW_HOOKS_TOKEN',''))")
if [[ -z "${OPENCLAW_HOOKS_TOKEN}" || "${OPENCLAW_HOOKS_TOKEN}" == "${OPENCLAW_GATEWAY_TOKEN}" ]]; then
  warn "Hooks token missing or equal to gateway token — generating a distinct one"
  OPENCLAW_HOOKS_TOKEN=$(openssl rand -hex 32)
fi

# ---------------------------------------------------------------------------
# Build env JSON (drops empty values)
# ---------------------------------------------------------------------------
TMP_ENV=$(mktemp -t agentcore-env.XXXXXX)
mv "${TMP_ENV}" "${TMP_ENV}.json"
TMP_ENV="${TMP_ENV}.json"
python3 <<EOF > "${TMP_ENV}"
import json
env = {
    "BEDROCK_AGENTCORE_MEMORY_ID": "${MEMORY_ID}",
    "BEDROCK_AGENTCORE_MEMORY_NAME": "${MEMORY_NAME}",
    "OPENCLAW_GATEWAY_TOKEN": "${OPENCLAW_GATEWAY_TOKEN}",
    "OPENCLAW_HOOKS_TOKEN": "${OPENCLAW_HOOKS_TOKEN}",
    "MCP_GATEWAY_URL": "${MCP_GATEWAY_URL}",
    "MCP_API_KEY": "${MCP_API_KEY}",
    "SF_INSTANCE_URL": "${SF_URL}",
    "SF_ACCESS_TOKEN": "${SF_TOK}",
    "LANGFUSE_SECRET_KEY": "${LANGFUSE_SECRET_KEY}",
    "LANGFUSE_PUBLIC_KEY": "${LANGFUSE_PUBLIC_KEY}",
    "LANGFUSE_BASE_URL": "${LANGFUSE_BASE_URL}",
    "FINNHUB_API_KEY": "${FINNHUB_API_KEY}",
    "ALPHA_VANTAGE_API_KEY": "${ALPHA_VANTAGE_API_KEY}",
    "TAVILY_API_KEY": "${TAVILY_API_KEY}",
}
env = {k: v for k, v in env.items() if v}
print(json.dumps(env))
EOF

# ---------------------------------------------------------------------------
# Summary (counts only, never values)
# ---------------------------------------------------------------------------
log "Env var summary:"
python3 <<EOF
import json
d = json.loads(open('${TMP_ENV}').read())
for k in sorted(d.keys()):
    v = d[k]
    print(f'  {k}: SET ({len(v)} chars)' if v else f'  {k}: EMPTY')
print(f'Total: {len(d)} vars')
EOF

if [[ "${DRY_RUN}" == "1" ]]; then
  log "DRY-RUN: not updating runtime. Env saved to ${TMP_ENV}"
  exit 0
fi

# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------
log "Applying env to ${AGENT_RUNTIME_ID}..."
aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id "${AGENT_RUNTIME_ID}" \
  --region "${AWS_REGION}" \
  --role-arn "${EXEC_ROLE_ARN}" \
  --network-configuration 'networkMode=PUBLIC' \
  --agent-runtime-artifact "containerConfiguration={containerUri=${CURRENT_IMG}}" \
  --environment-variables "file://${TMP_ENV}" \
  --query '{Status:status,Ver:agentRuntimeVersion}' --output json

log "Waiting for runtime to reach READY..."
for i in {1..30}; do
  STATE=$(aws bedrock-agentcore-control get-agent-runtime \
    --agent-runtime-id "${AGENT_RUNTIME_ID}" \
    --region "${AWS_REGION}" \
    --query 'status' --output text 2>/dev/null || echo "UNKNOWN")
  if [[ "${STATE}" == "READY" ]]; then
    log "Runtime READY."
    break
  fi
  sleep 10
done

rm -f "${TMP_ENV}"
log "Done."
