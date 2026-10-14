#!/usr/bin/env bash
# =============================================================================
# verify-006-v2.sh - End-to-end smoke test for 006 v2.
#
# Read-only checks. Run after deploy to confirm the stack is wired correctly.
#
# Checks:
#   1. AWS Lambda mulesoft-actions health (GET /mulesoft-actions)
#   2. AWS Lambda mulesoft-actions MCP tools/list
#   3. AWS Lambda mulesoft-actions MCP tools/call for who_am_i
#      (proves MuleSoft Anypoint OAuth works end-to-end)
#   4. Secrets Manager read check (describes all 3 secrets, does NOT show values)
#   5. Local mock test suite (expects 15/15)
#   6. Frontend reachability (curl S3/CloudFront URL, expect 200)
#
# Prints a green PASS / red FAIL per check. Exits nonzero if any fail.
#
# Usage:
#   ./scripts/verify-006-v2.sh
#
# Env vars (with defaults):
#   AWS_REGION          (us-east-1)
#   SAM_STACK_NAME      (openclaw-006-mcp)
#   FRONTEND_URL        (derived from CloudFront output if set; else skipped)
#   FRONTEND_BUCKET     (fallback: https://<bucket>.s3.<region>.amazonaws.com/index.html)
# =============================================================================

set -uo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
SAM_STACK_NAME="${SAM_STACK_NAME:-openclaw-mcp-006-v2}"
FRONTEND_URL="${FRONTEND_URL:-}"
FRONTEND_BUCKET="${FRONTEND_BUCKET:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# --- colors -----------------------------------------------------------------
GREEN=$'\033[1;32m'
RED=$'\033[1;31m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[1;34m'
RESET=$'\033[0m'

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

pass() {
  printf "%b  PASS  %b %-30s %s\n" "${GREEN}" "${RESET}" "$1" "${2:-}"
  PASS_COUNT=$((PASS_COUNT + 1))
}
fail() {
  printf "%b  FAIL  %b %-30s %s\n" "${RED}" "${RESET}" "$1" "${2:-}"
  FAIL_COUNT=$((FAIL_COUNT + 1))
}
warn() {
  printf "%b  WARN  %b %-30s %s\n" "${YELLOW}" "${RESET}" "$1" "${2:-}"
  WARN_COUNT=$((WARN_COUNT + 1))
}
header() { printf "\n%b==> %s%b\n" "${BLUE}" "$1" "${RESET}"; }

# --- preflight --------------------------------------------------------------
command -v aws  >/dev/null || { echo "aws CLI missing"; exit 2; }
command -v jq   >/dev/null || { echo "jq missing";     exit 2; }
command -v curl >/dev/null || { echo "curl missing";   exit 2; }
command -v python3 >/dev/null || { echo "python3 missing"; exit 2; }

if ! aws sts get-caller-identity --region "${AWS_REGION}" >/dev/null 2>&1; then
  echo "AWS CLI not authenticated."
  exit 2
fi

# --- resolve API Gateway URL + key from SAM stack outputs -------------------
header "Resolving MCP API Gateway from SAM stack '${SAM_STACK_NAME}'"
MCP_GATEWAY_URL=""
MCP_API_KEY=""

if aws cloudformation describe-stacks \
     --stack-name "${SAM_STACK_NAME}" \
     --region "${AWS_REGION}" >/dev/null 2>&1; then
  MCP_GATEWAY_URL="$(aws cloudformation describe-stacks \
    --stack-name "${SAM_STACK_NAME}" --region "${AWS_REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='ApiGatewayUrl'].OutputValue" \
    --output text 2>/dev/null || echo "")"
  API_KEY_ID="$(aws cloudformation describe-stacks \
    --stack-name "${SAM_STACK_NAME}" --region "${AWS_REGION}" \
    --query "Stacks[0].Outputs[?OutputKey=='ApiKeyId'].OutputValue" \
    --output text 2>/dev/null || echo "")"
  if [[ -n "${API_KEY_ID}" && "${API_KEY_ID}" != "None" ]]; then
    MCP_API_KEY="$(aws apigateway get-api-key \
      --api-key "${API_KEY_ID}" --include-value \
      --region "${AWS_REGION}" --query value --output text 2>/dev/null || echo "")"
  fi
fi

if [[ -z "${MCP_GATEWAY_URL}" || "${MCP_GATEWAY_URL}" == "None" ]]; then
  echo "Could not resolve ApiGatewayUrl from stack outputs."
  echo "Checks 1-3 will be skipped."
fi

# ============================================================================
# 1. mulesoft-actions health (GET /mulesoft-actions)
# ============================================================================
header "Check 1/6: mulesoft-actions Lambda health"
if [[ -n "${MCP_GATEWAY_URL}" && -n "${MCP_API_KEY}" ]]; then
  resp="$(curl -sS --max-time 10 \
             -H "x-api-key: ${MCP_API_KEY}" \
             "${MCP_GATEWAY_URL}/mulesoft-actions" 2>&1 || echo "CURL_FAIL")"
  if echo "${resp}" | jq -e '.name' >/dev/null 2>&1; then
    mode="$(echo "${resp}" | jq -r '.mode // .mulesoft_mode // "unknown"')"
    pass "mulesoft-actions-health" "mode=${mode}"
  else
    fail "mulesoft-actions-health" "unexpected response: ${resp:0:100}"
  fi
else
  warn "mulesoft-actions-health" "skipped (no gateway url or api key)"
fi

# ============================================================================
# 2. mulesoft-actions tools/list
# ============================================================================
header "Check 2/6: mulesoft-actions tools/list"
TOOLS_LIST_OK=false
if [[ -n "${MCP_GATEWAY_URL}" && -n "${MCP_API_KEY}" ]]; then
  resp="$(curl -sS --max-time 10 -X POST \
            -H "x-api-key: ${MCP_API_KEY}" \
            -H "Content-Type: application/json" \
            -d '{}' \
            "${MCP_GATEWAY_URL}/mulesoft-actions/tools/list" 2>&1 || echo "CURL_FAIL")"
  cnt="$(echo "${resp}" | jq -r '.tools | length' 2>/dev/null || echo "0")"
  if [[ "${cnt}" -gt 0 ]]; then
    pass "mulesoft-actions-tools-list" "${cnt} tools"
    TOOLS_LIST_OK=true
  else
    fail "mulesoft-actions-tools-list" "unexpected: ${resp:0:100}"
  fi
else
  warn "mulesoft-actions-tools-list" "skipped"
fi

# ============================================================================
# 3. mulesoft-actions tools/call for who_am_i
# ============================================================================
header "Check 3/6: mulesoft-actions who_am_i (end-to-end MuleSoft OAuth)"
if [[ -n "${MCP_GATEWAY_URL}" && -n "${MCP_API_KEY}" ]] && $TOOLS_LIST_OK; then
  payload='{"name":"who_am_i","arguments":{}}'
  resp="$(curl -sS --max-time 30 -X POST \
            -H "x-api-key: ${MCP_API_KEY}" \
            -H "Content-Type: application/json" \
            -d "${payload}" \
            "${MCP_GATEWAY_URL}/mulesoft-actions/tools/call" 2>&1 || echo "CURL_FAIL")"
  # Accept either an isError response or a normal content blob.
  if echo "${resp}" | jq -e '.content' >/dev/null 2>&1; then
    if echo "${resp}" | jq -e '.isError == true' >/dev/null 2>&1; then
      fail "mulesoft-actions-who-am-i" "error: $(echo "${resp}" | jq -r '.content[0].text' 2>/dev/null | head -c 120)"
    else
      pass "mulesoft-actions-who-am-i" "MuleSoft OAuth OK"
    fi
  else
    fail "mulesoft-actions-who-am-i" "unexpected: ${resp:0:120}"
  fi
else
  warn "mulesoft-actions-who-am-i" "skipped"
fi

# ============================================================================
# 4. Secrets Manager read check (describe only - no values read)
# ============================================================================
header "Check 4/6: Secrets Manager (describe only, no values)"
for sid in "/006-v2/mulesoft/credentials" "/006-v2/vendors/alpaca" "/006-v2/hitl/signing-key"; do
  if aws secretsmanager describe-secret \
       --secret-id "${sid}" --region "${AWS_REGION}" >/dev/null 2>&1; then
    pass "secret-exists" "${sid}"
  else
    fail "secret-exists" "${sid} NOT FOUND"
  fi
done

# ============================================================================
# 5. Local mock test suite
# ============================================================================
header "Check 5/6: Local mock test suite (expect 15/15)"
if [[ -f scripts/test-mulesoft-mock.py ]]; then
  # Need HITL_SIGNING_KEY; generate a throwaway one if operator didn't set it.
  export HITL_SIGNING_KEY="${HITL_SIGNING_KEY:-$(openssl rand -hex 32)}"
  mock_out="$(python3 scripts/test-mulesoft-mock.py 2>&1 || true)"
  # Parse "  Results: X/Y passed, Z failed"
  line="$(echo "${mock_out}" | grep -E '^\s+Results:' | head -1 || echo "")"
  if [[ -z "${line}" ]]; then
    fail "mock-test-suite" "could not parse results"
    echo "${mock_out}" | tail -20
  else
    parsed="$(echo "${line}" | sed -E 's/.*Results: ([0-9]+)\/([0-9]+) passed, ([0-9]+) failed.*/\1 \2 \3/')"
    read -r p t f <<< "${parsed}"
    if [[ "${p}" == "${t}" && "${f}" == "0" && "${t}" -ge 15 ]]; then
      pass "mock-test-suite" "${p}/${t} passed"
    else
      fail "mock-test-suite" "${p}/${t} passed, ${f} failed"
    fi
  fi
else
  fail "mock-test-suite" "scripts/test-mulesoft-mock.py missing"
fi

# ============================================================================
# 6. Frontend reachability
# ============================================================================
header "Check 6/6: Frontend reachability"
url=""
if [[ -n "${FRONTEND_URL}" ]]; then
  url="${FRONTEND_URL}"
elif [[ -n "${FRONTEND_BUCKET}" ]]; then
  url="https://${FRONTEND_BUCKET}.s3.${AWS_REGION}.amazonaws.com/index.html"
fi

if [[ -n "${url}" ]]; then
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 "${url}" || echo "000")"
  if [[ "${code}" == "200" ]]; then
    pass "frontend-reachable" "${url} -> 200"
  else
    fail "frontend-reachable" "${url} -> HTTP ${code}"
  fi
else
  warn "frontend-reachable" "set FRONTEND_URL or FRONTEND_BUCKET to enable"
fi

# --- summary ----------------------------------------------------------------
echo ""
printf "%b==========================================%b\n" "${BLUE}" "${RESET}"
printf "  %bPASS%b: %d  %bFAIL%b: %d  %bWARN%b: %d\n" \
  "${GREEN}" "${RESET}" "${PASS_COUNT}" \
  "${RED}"   "${RESET}" "${FAIL_COUNT}" \
  "${YELLOW}" "${RESET}" "${WARN_COUNT}"
printf "%b==========================================%b\n" "${BLUE}" "${RESET}"

exit $(( FAIL_COUNT == 0 ? 0 : 1 ))
