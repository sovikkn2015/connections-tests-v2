#!/usr/bin/env bash
# =============================================================================
# run-alpaca-e2e-test.sh - Full end-to-end Alpaca integration test.
#
# Requires a deployed MuleSoft CloudHub app reachable at $CLOUDHUB_APP_URL and
# the MuleSoft_Client_ID policy header value provisioned via API Manager.
#
# Flow:
#   1. GET  {URL}/api/health             -> expect {"mode":"alpaca-paper"}
#   2. POST {URL}/api/orders             -> sample AAPL BUY 1 MARKET
#   3. Parse response, extract order_id starting with "ALPACA-"
#   4. Read Alpaca creds from AWS Secrets Manager at runtime (never echoed).
#   5. GET  paper-api.alpaca.markets/v2/orders/{alpaca_order_id} to verify
#      the order actually landed at the broker.
#   6. Print summary.
#
# Required env vars:
#   CLOUDHUB_APP_URL        e.g. https://006-v2-trade-process-api.us-e2.cloudhub.io
#   MULESOFT_CLIENT_ID      client-id policy header value
#
# Optional env vars:
#   AWS_REGION              (us-east-1)
#   ALPACA_SECRET_ID        (/006-v2/vendors/alpaca)
#   ALPACA_BASE_URL         (https://paper-api.alpaca.markets)
# =============================================================================

set -uo pipefail

CLOUDHUB_APP_URL="${CLOUDHUB_APP_URL:-}"
MULESOFT_CLIENT_ID="${MULESOFT_CLIENT_ID:-}"
AWS_REGION="${AWS_REGION:-us-east-1}"
ALPACA_SECRET_ID="${ALPACA_SECRET_ID:-/006-v2/vendors/alpaca}"
ALPACA_BASE_URL="${ALPACA_BASE_URL:-https://paper-api.alpaca.markets}"

# --- colors -----------------------------------------------------------------
GREEN=$'\033[1;32m'
RED=$'\033[1;31m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[1;34m'
RESET=$'\033[0m'

log()   { printf "%b[alpaca-e2e]%b %s\n" "${BLUE}" "${RESET}" "$*"; }
pass()  { printf "%b  PASS %b %s\n" "${GREEN}" "${RESET}" "$*"; }
fail()  { printf "%b  FAIL %b %s\n" "${RED}"   "${RESET}" "$*"; }
warn()  { printf "%b  WARN %b %s\n" "${YELLOW}" "${RESET}" "$*"; }
fatal() { printf "%b[alpaca-e2e FATAL]%b %s\n" "${RED}" "${RESET}" "$*" >&2; exit 1; }

# --- preflight --------------------------------------------------------------
[[ -n "${CLOUDHUB_APP_URL}"  ]] || fatal "CLOUDHUB_APP_URL env var required (e.g. https://006-v2-trade-process-api.us-e2.cloudhub.io)"
[[ -n "${MULESOFT_CLIENT_ID}" ]] || fatal "MULESOFT_CLIENT_ID env var required"

command -v aws  >/dev/null || fatal "aws CLI not found"
command -v jq   >/dev/null || fatal "jq not found"
command -v curl >/dev/null || fatal "curl not found"

aws sts get-caller-identity --region "${AWS_REGION}" >/dev/null 2>&1 \
  || fatal "AWS CLI not authenticated"

# ============================================================================
# Step 1: CloudHub app health
# ============================================================================
log "Step 1/5: GET ${CLOUDHUB_APP_URL}/api/health"
health="$(curl -sS --max-time 15 \
           -H "client_id: ${MULESOFT_CLIENT_ID}" \
           "${CLOUDHUB_APP_URL}/api/health" 2>&1 || echo "CURL_FAIL")"

mode="$(echo "${health}" | jq -r '.mode // ""' 2>/dev/null || echo "")"
if [[ "${mode}" == "alpaca-paper" ]]; then
  pass "health mode=alpaca-paper"
else
  fail "health check failed"
  echo "  response: ${health:0:200}"
  exit 1
fi

# ============================================================================
# Step 2: Submit sample order via CloudHub
# ============================================================================
log "Step 2/5: POST ${CLOUDHUB_APP_URL}/api/orders  (AAPL BUY 1 MARKET)"
client_order_id="e2e-$(date +%s)-$(openssl rand -hex 4)"
order_payload="$(jq -cn \
  --arg coid "${client_order_id}" \
  '{
    client_order_id: $coid,
    ticker: "AAPL",
    side: "BUY",
    quantity: 1,
    order_type: "MARKET",
    time_in_force: "DAY"
  }')"

order_resp="$(curl -sS --max-time 30 -X POST \
                -H "client_id: ${MULESOFT_CLIENT_ID}" \
                -H "Content-Type: application/json" \
                -d "${order_payload}" \
                "${CLOUDHUB_APP_URL}/api/orders" 2>&1 || echo "CURL_FAIL")"

if ! echo "${order_resp}" | jq . >/dev/null 2>&1; then
  fail "submit order returned non-JSON"
  echo "  response: ${order_resp:0:200}"
  exit 1
fi

order_id="$(echo "${order_resp}" | jq -r '.order_id // ""')"
alpaca_ref="$(echo "${order_resp}" | jq -r '.alpaca_order_id // .mulesoft_reference // ""')"

if [[ -z "${order_id}" || "${order_id}" == "null" ]]; then
  fail "no order_id in response"
  echo "  response: ${order_resp}"
  exit 1
fi

if [[ "${order_id}" != ALPACA-* ]]; then
  warn "order_id does not start with ALPACA- : '${order_id}'"
fi
pass "order submitted: order_id=${order_id}"

# ============================================================================
# Step 3: Parse alpaca-native order id (the UUID Alpaca assigned)
# ============================================================================
log "Step 3/5: extract native Alpaca order UUID"
# Try a few likely field names - the canonical response may expose the raw
# Alpaca UUID under alpaca_order_id, or embed it after the ALPACA- prefix.
alpaca_uuid=""
if [[ -n "${alpaca_ref}" && "${alpaca_ref}" != "null" ]]; then
  alpaca_uuid="${alpaca_ref}"
elif [[ "${order_id}" == ALPACA-* ]]; then
  alpaca_uuid="${order_id#ALPACA-}"
fi

if [[ -z "${alpaca_uuid}" ]]; then
  fail "could not extract Alpaca order UUID from response"
  echo "  response: ${order_resp}"
  exit 1
fi
pass "alpaca order uuid extracted"

# ============================================================================
# Step 4: Read Alpaca creds from Secrets Manager (never echo them)
# ============================================================================
log "Step 4/5: verify order directly at Alpaca (read creds from Secrets Manager)"

# --- secure subshell: read creds, call Alpaca, never export to parent env ---
verify_output="$(
  set +x
  secret_json="$(aws secretsmanager get-secret-value \
                  --secret-id "${ALPACA_SECRET_ID}" \
                  --region "${AWS_REGION}" \
                  --query SecretString --output text 2>/dev/null || echo "")"
  if [[ -z "${secret_json}" ]]; then
    echo "SECRET_READ_FAIL"
    exit 0
  fi
  key_id="$(echo "${secret_json}"  | jq -r '.key_id // .APCA_API_KEY_ID // ""')"
  secret="$(echo "${secret_json}"  | jq -r '.secret // .APCA_API_SECRET_KEY // ""')"
  unset secret_json
  if [[ -z "${key_id}" || -z "${secret}" ]]; then
    echo "SECRET_MISSING_FIELDS"
    exit 0
  fi
  # Call Alpaca directly.
  alpaca_resp="$(curl -sS --max-time 15 \
                  -H "APCA-API-KEY-ID: ${key_id}" \
                  -H "APCA-API-SECRET-KEY: ${secret}" \
                  "${ALPACA_BASE_URL}/v2/orders/${alpaca_uuid}" 2>&1 || echo "CURL_FAIL")"
  unset key_id secret
  echo "${alpaca_resp}"
)"

if [[ "${verify_output}" == "SECRET_READ_FAIL" ]]; then
  fail "could not read Alpaca secret ${ALPACA_SECRET_ID}"
  exit 1
fi
if [[ "${verify_output}" == "SECRET_MISSING_FIELDS" ]]; then
  fail "Alpaca secret is missing key_id or secret fields"
  exit 1
fi

if ! echo "${verify_output}" | jq . >/dev/null 2>&1; then
  fail "Alpaca returned non-JSON"
  echo "  response: ${verify_output:0:200}"
  exit 1
fi

alpaca_status="$(echo "${verify_output}" | jq -r '.status // ""')"
alpaca_symbol="$(echo "${verify_output}" | jq -r '.symbol // ""')"
alpaca_qty="$(echo "${verify_output}"    | jq -r '.qty // ""')"
alpaca_side="$(echo "${verify_output}"   | jq -r '.side // ""')"

if [[ -z "${alpaca_status}" || "${alpaca_status}" == "null" ]]; then
  fail "Alpaca did not return a recognizable order"
  echo "  response: ${verify_output:0:200}"
  exit 1
fi

pass "Alpaca confirms: symbol=${alpaca_symbol} qty=${alpaca_qty} side=${alpaca_side} status=${alpaca_status}"

# ============================================================================
# Step 5: Summary
# ============================================================================
log "Step 5/5: summary"
echo ""
printf "%b============================================%b\n" "${BLUE}" "${RESET}"
printf "  Alpaca E2E: OK\n"
printf "  client_order_id    : %s\n" "${client_order_id}"
printf "  canonical order_id : %s\n" "${order_id}"
printf "  alpaca uuid        : %s\n" "${alpaca_uuid}"
printf "  alpaca status      : %s\n" "${alpaca_status}"
printf "%b============================================%b\n" "${BLUE}" "${RESET}"
