#!/usr/bin/env bash
# ============================================================================
# ui-test-10-queries.sh — Simulate 10 queries through the SAME path the
# React frontend uses in production.
#
# Path: This script -> POST /agent/query (API Gateway) -> agent-proxy Lambda
#       -> AgentCore -> OpenClaw container -> Bedrock + MCP Lambdas -> response
#
# This is IDENTICAL to what happens when a user types in the React UI and
# clicks Send. The only difference is curl instead of a browser.
#
# Usage:
#   ./scripts/ui-test-10-queries.sh
#   ./scripts/ui-test-10-queries.sh --verbose   # show full responses
# ============================================================================

set -uo pipefail

PROXY_URL="https://2ifxjh92ig.execute-api.us-east-1.amazonaws.com/prod/agent/query"
VERBOSE=false
for arg in "$@"; do
  case "$arg" in
    --verbose) VERBOSE=true ;;
  esac
done

QUERIES=(
  "What's NVIDIA trading at?"
  "Give me TSLA's 52-week high and low"
  "What's the S&P 500 at?"
  "Who covers Apple on our team?"
  "What's on my watchlist?"
  "Any news about Tesla today?"
  "Show me NVIDIA's latest 10-Q"
  "Compare NVDA and AMD -- which is the better buy right now?"
  "When does JPMorgan report earnings?"
  "Where's crude oil trading?"
)

PASS=0; FAIL=0; ERRORS=0
RESULTS_DIR=$(mktemp -d)

echo "============================================================"
echo "  006 UI Path Test -- 10 queries via agent-proxy Lambda"
echo "  Endpoint: ${PROXY_URL}"
echo "  Results:  ${RESULTS_DIR}"
echo "============================================================"
echo ""

for i in "${!QUERIES[@]}"; do
  qnum=$((i + 1))
  query="${QUERIES[$i]}"
  session="ui-test-$(date +%s)-${qnum}"
  outfile="${RESULTS_DIR}/q${qnum}.json"

  printf "[%2d/10] %-55s " "${qnum}" "${query}"

  HTTP_CODE=$(curl -sS -o "${outfile}" -w "%{http_code}" \
    --max-time 180 \
    -X POST \
    -H "Content-Type: application/json" \
    -d "{\"message\": \"${query}\", \"sessionKey\": \"${session}\"}" \
    "${PROXY_URL}" 2>/dev/null)

  if [[ "${HTTP_CODE}" == "200" ]]; then
    RESP_INFO=$(python3 -c "
import json
d = json.load(open('${outfile}'))
text = d.get('response', '')
tools = d.get('toolResults', [])
ok = len(text) > 50 and 'ERROR' not in text[:20]
print(f'{len(text)} chars {len(tools)} tools {\"PASS\" if ok else \"FAIL\"}')" 2>/dev/null)

    STATUS=$(echo "${RESP_INFO}" | awk '{print $NF}')
    if [[ "${STATUS}" == "PASS" ]]; then
      printf "\033[32mPASS\033[0m  %s\n" "${RESP_INFO}"
      PASS=$((PASS + 1))
    else
      printf "\033[31mFAIL\033[0m  %s\n" "${RESP_INFO}"
      FAIL=$((FAIL + 1))
    fi

    if $VERBOSE; then
      python3 -c "
import json
d = json.load(open('${outfile}'))
text = d.get('response', '')
print('  Response:', text[:300])
if len(text) > 300: print('  ... (%d chars total)' % len(text))
tools = d.get('toolResults', [])
if tools: print('  Tools:', [t.get('name','?') for t in tools])
print()" 2>/dev/null
    fi
  else
    printf "\033[31mERROR\033[0m  HTTP %s\n" "${HTTP_CODE}"
    ERRORS=$((ERRORS + 1))
  fi

  sleep 2
done

echo ""
echo "============================================================"
echo "  Results: ${PASS} PASS, ${FAIL} FAIL, ${ERRORS} ERROR"
echo "  Pass rate: $(( PASS * 100 / 10 ))%"
echo "  Full responses: ${RESULTS_DIR}"
echo "============================================================"
