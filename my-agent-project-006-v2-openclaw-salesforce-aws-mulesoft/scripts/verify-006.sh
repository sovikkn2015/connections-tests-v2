#!/usr/bin/env bash
# ============================================================================
# verify-006.sh - Reproducible health check for Project 006.
#
# Probes each integration point and reports PASS/FAIL/WARN:
#   1. AWS auth + Bedrock model access
#   2. SF metadata + seed data counts
#   3. 4 MCP servers (info + tools/list)
#   4. AgentCore agent runtime (invoke)
#   5. Secrets Manager has all required keys
#
# Usage:
#   ./scripts/verify-006.sh              # colored table
#   ./scripts/verify-006.sh --json       # JSON for CI
#   ./scripts/verify-006.sh --fail-fast  # exit on first FAIL
#
# Read-only. Safe anytime. No side effects.
# ============================================================================

set -uo pipefail

JSON=false
FAIL_FAST=false
for arg in "$@"; do
  case "$arg" in
    --json) JSON=true ;;
    --fail-fast) FAIL_FAST=true ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
  esac
done

AWS_REGION="${AWS_REGION:-us-east-1}"
SAM_STACK_NAME="${SAM_STACK_NAME:-openclaw-006-mcp}"
SECRET_NAME="${SECRET_NAME:-openclaw-fsi-secrets}"
SF_TARGET_ORG="${SF_TARGET_ORG:-my-org}"
AGENTCORE_AGENT_ARN="${AGENTCORE_AGENT_ARN:-}"

declare -a CHECKS STATUSES DETAILS

record() {
  CHECKS+=("$1"); STATUSES+=("$2"); DETAILS+=("$3")
  if ! $JSON; then
    local color
    case "$2" in
      PASS) color="\033[1;32m" ;;
      FAIL) color="\033[1;31m" ;;
      WARN) color="\033[1;33m" ;;
    esac
    printf "%b%-6s\033[0m %-25s %s\n" "${color}" "$2" "$1" "$3"
  fi
  if $FAIL_FAST && [[ "$2" == "FAIL" ]]; then emit; exit 1; fi
}

emit() {
  if $JSON; then
    printf '{\n  "checks": [\n'
    local n=${#CHECKS[@]}
    for i in $(seq 0 $((n-1))); do
      printf '    {"name": "%s", "status": "%s", "detail": "%s"}%s\n' \
        "${CHECKS[$i]}" "${STATUSES[$i]}" "${DETAILS[$i]//\"/\\\"}" \
        $([[ $i -lt $((n-1)) ]] && echo "," || echo "")
    done
    printf '  ]\n}\n'
  fi
}

# 1. AWS auth
if aws sts get-caller-identity --region "${AWS_REGION}" >/dev/null 2>&1; then
  acct="$(aws sts get-caller-identity --region "${AWS_REGION}" --query Account --output text)"
  record "aws-auth" "PASS" "account=${acct}"
else
  record "aws-auth" "FAIL" "run: aws configure"
fi

# 2. Bedrock models
if aws bedrock list-foundation-models --region "${AWS_REGION}" --output json 2>/dev/null | \
   grep -q "claude-sonnet-4"; then
  record "bedrock-sonnet-4.6" "PASS" "model visible"
else
  record "bedrock-sonnet-4.6" "WARN" "could not list - request model access"
fi

# 3. Secrets
if aws secretsmanager describe-secret --secret-id "${SECRET_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1; then
  sj="$(aws secretsmanager get-secret-value --secret-id "${SECRET_NAME}" --region "${AWS_REGION}" --query SecretString --output text 2>/dev/null || echo '{}')"
  missing=""
  for key in OPENCLAW_GATEWAY_TOKEN SF_INSTANCE_URL SF_ACCESS_TOKEN MCP_GATEWAY_URL MCP_API_KEY ALPHA_VANTAGE_API_KEY TAVILY_API_KEY; do
    val="$(echo "${sj}" | python3 -c "import json,sys; print(json.load(sys.stdin).get('${key}',''))" 2>/dev/null || echo "")"
    if [[ -z "${val}" || "${val}" == REPLACE_ME* ]]; then missing="${missing}${key} "; fi
  done
  if [[ -z "${missing}" ]]; then
    record "secrets-manager" "PASS" "7/7 keys populated"
  else
    record "secrets-manager" "FAIL" "missing/placeholder: ${missing}"
  fi
else
  record "secrets-manager" "FAIL" "secret '${SECRET_NAME}' not found"
fi

# 4. SAM stack
MCP_GATEWAY_URL=""; MCP_API_KEY=""
if aws cloudformation describe-stacks --stack-name "${SAM_STACK_NAME}" --region "${AWS_REGION}" >/dev/null 2>&1; then
  MCP_GATEWAY_URL="$(aws cloudformation describe-stacks --stack-name "${SAM_STACK_NAME}" --region "${AWS_REGION}" \
    --query "Stacks[0].Outputs[?contains(OutputKey, 'Url') || contains(OutputKey, 'Endpoint')].OutputValue | [0]" \
    --output text 2>/dev/null || echo "")"
  ApiKeyId="$(aws cloudformation describe-stacks --stack-name "${SAM_STACK_NAME}" --region "${AWS_REGION}" \
    --query "Stacks[0].Outputs[?contains(OutputKey, 'ApiKeyId') || contains(OutputKey, 'McpApiKey')].OutputValue | [0]" \
    --output text 2>/dev/null || echo "")"
  if [[ -n "${ApiKeyId}" && "${ApiKeyId}" != "None" ]]; then
    MCP_API_KEY="$(aws apigateway get-api-key --api-key "${ApiKeyId}" --include-value --region "${AWS_REGION}" --query value --output text 2>/dev/null || echo "")"
  fi
  if [[ -n "${MCP_GATEWAY_URL}" && "${MCP_GATEWAY_URL}" != "None" ]]; then
    record "sam-stack" "PASS" "${MCP_GATEWAY_URL}"
  else
    record "sam-stack" "WARN" "stack found but no URL output"
  fi
else
  record "sam-stack" "FAIL" "stack '${SAM_STACK_NAME}' not found"
fi

# 5. Each MCP server
if [[ -n "${MCP_GATEWAY_URL}" && "${MCP_GATEWAY_URL}" != "None" && -n "${MCP_API_KEY}" ]]; then
  for server in market-data sec-edgar news-search salesforce-crm; do
    info="$(curl -sS --max-time 10 -H "x-api-key: ${MCP_API_KEY}" "${MCP_GATEWAY_URL}/${server}" 2>&1 || echo "CURL_FAIL")"
    if echo "${info}" | grep -q "\"name\""; then
      tl="$(curl -sS --max-time 10 -X POST -H "x-api-key: ${MCP_API_KEY}" -H "Content-Type: application/json" -d '{}' "${MCP_GATEWAY_URL}/${server}/tools/list" 2>&1 || echo "CURL_FAIL")"
      cnt="$(echo "${tl}" | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d.get('tools', [])))" 2>/dev/null || echo "0")"
      if [[ "${cnt}" -gt 0 ]]; then
        record "mcp-${server}" "PASS" "${cnt} tools"
      else
        record "mcp-${server}" "WARN" "info ok but tools/list empty"
      fi
    else
      record "mcp-${server}" "FAIL" "${info:0:80}"
    fi
  done
else
  for server in market-data sec-edgar news-search salesforce-crm; do
    record "mcp-${server}" "WARN" "skipped - no gateway url/key"
  done
fi

# 6. SF seed data
if sf org display --target-org "${SF_TARGET_ORG}" --json >/dev/null 2>&1; then
  cnt="$(sf data query --query 'SELECT COUNT() FROM IR_Company__c' --target-org "${SF_TARGET_ORG}" --json 2>/dev/null | \
    python3 -c "import json,sys; print(json.load(sys.stdin)['result']['totalSize'])" 2>/dev/null || echo "0")"
  if [[ "${cnt}" -ge 30 ]]; then
    record "sf-seed-data" "PASS" "IR_Company__c=${cnt}"
  else
    record "sf-seed-data" "WARN" "IR_Company__c=${cnt} (expected >=30)"
  fi
else
  record "sf-seed-data" "FAIL" "org '${SF_TARGET_ORG}' not accessible"
fi

# 7. AgentCore (optional)
if [[ -n "${AGENTCORE_AGENT_ARN}" ]]; then
  tmp="$(mktemp)"
  # AgentCore requires sessionId to be 33+ chars
  SID="verify-$(date +%s)-$(openssl rand -hex 12)"
  payload_b64="$(printf '{"prompt":"ping"}' | base64 | tr -d '\n')"
  resp="$(aws bedrock-agentcore invoke-agent-runtime \
    --agent-runtime-arn "${AGENTCORE_AGENT_ARN}" \
    --runtime-session-id "${SID}" \
    --content-type application/json \
    --accept application/json \
    --payload "${payload_b64}" \
    --region "${AWS_REGION}" \
    "${tmp}" 2>&1 || echo "INVOKE_FAIL")"
  if echo "${resp}" | grep -q "INVOKE_FAIL"; then
    record "agentcore-invoke" "FAIL" "${resp:0:80}"
  else
    record "agentcore-invoke" "PASS" "response saved to ${tmp}"
  fi
else
  record "agentcore-invoke" "WARN" "set AGENTCORE_AGENT_ARN to enable"
fi

emit

p=0; f=0; w=0
for s in "${STATUSES[@]}"; do
  case "$s" in
    PASS) p=$((p+1)) ;;
    FAIL) f=$((f+1)) ;;
    WARN) w=$((w+1)) ;;
  esac
done
if ! $JSON; then
  printf "\n\033[1mSummary:\033[0m %d PASS  %d FAIL  %d WARN\n" "${p}" "${f}" "${w}"
fi
exit $([[ ${f} -eq 0 ]] && echo 0 || echo 1)
