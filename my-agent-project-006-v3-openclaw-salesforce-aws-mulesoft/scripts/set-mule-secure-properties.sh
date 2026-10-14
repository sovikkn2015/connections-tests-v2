#!/usr/bin/env bash
# ============================================================================
# set-mule-secure-properties.sh
#
# Idempotently set per-app plain + secure properties in Anypoint Runtime
# Manager for the three v3 CloudHub 2.0 apps (submit-order, initiate-wire,
# order-status-webhook).
#
# WHY THIS SCRIPT EXISTS:
#   Mule 4.9 apps cannot boot without their per-app secure properties (Alpaca
#   keys, Dwolla creds, webhook HMAC) set in Runtime Manager. In the April
#   2026 deploy cycle we did this by hand via raw `curl` PATCH against the
#   Anypoint API — this script replaces that ad-hoc step and ties it to
#   AWS Secrets Manager / SSM as the single source of truth.
#
# WHAT IT DOES, per app:
#   1. OAuth client_credentials against anypoint.mulesoft.com -> bearer token
#   2. Resolve organizationId + Sandbox environmentId
#   3. Resolve the app's CloudHub 2.0 deploymentId
#   4. GET current deployment object
#   5. Merge in plain + secure properties (plus mule.secure.properties.key)
#   6. PATCH the deployment
#   7. Wait for the app to finish APPLYING and return RUNNING
#
# PREREQS:
#   - bash, jq, curl, python3, awscli-v2 authenticated with read access to
#     /006-v3/mulesoft/* SSM params and /006-v3/vendors/* Secrets Manager
#   - seed-secrets.sh has been run at least once
#
# USAGE:
#   ./scripts/set-mule-secure-properties.sh              # all 3 apps
#   ./scripts/set-mule-secure-properties.sh submit-order # one app
#   ./scripts/set-mule-secure-properties.sh --dry-run    # preview only
#   ./scripts/set-mule-secure-properties.sh --no-wait    # skip status poll
#
# IDEMPOTENT: safe to run repeatedly. Each run re-reads current values from
# AWS and PATCHes Anypoint with the same result.
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

AWS_REGION="${AWS_REGION_BEDROCK:-us-east-1}"
ANYPOINT_BASE="${ANYPOINT_BASE:-https://anypoint.mulesoft.com}"
ANYPOINT_ENV_NAME="${ANYPOINT_ENVIRONMENT:-Sandbox}"

# Apps the script knows about. Order matters for deploy verification only.
APPS=("openclaw-v3-submit-order" "openclaw-v3-initiate-wire" "openclaw-v3-order-status-webhook")

DRY_RUN=false
NO_WAIT=false
FILTER_APP=""

for arg in "$@"; do
  case "$arg" in
    --dry-run)  DRY_RUN=true ;;
    --no-wait)  NO_WAIT=true ;;
    -h|--help)  sed -n '2,38p' "$0"; exit 0 ;;
    openclaw-v3-*) FILTER_APP="$arg" ;;
    submit-order|initiate-wire|order-status-webhook)
      FILTER_APP="openclaw-v3-$arg" ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

log()   { printf "\033[1;34m[set-mule-props]\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m[set-mule-props WARN]\033[0m %s\n" "$*" >&2; }
fatal() { printf "\033[1;31m[set-mule-props FATAL]\033[0m %s\n" "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || fatal "Missing required tool: $1"; }
need aws; need jq; need curl; need python3

# ---------------------------------------------------------------------------
# Read all secrets/params up front (one call each, fail loudly if missing).
# ---------------------------------------------------------------------------
ssm_get() {
  local name="$1"
  aws ssm get-parameter --region "${AWS_REGION}" --name "$name" \
    --with-decryption --query 'Parameter.Value' --output text 2>/dev/null || true
}

sm_get_json() {
  local id="$1"
  aws secretsmanager get-secret-value --region "${AWS_REGION}" --secret-id "$id" \
    --query SecretString --output text 2>/dev/null || true
}

log "Reading sources from AWS..."

ANYPOINT_CLIENT_ID="$(ssm_get /006-v3/mulesoft/client-id)"
ANYPOINT_CLIENT_SECRET="$(ssm_get /006-v3/mulesoft/client-secret)"
MULE_SECURE_KEY="$(ssm_get /006-v3/mulesoft/secure-properties-key)"
MCP_API_KEY="$(ssm_get /006-v3/mcp/api-key)"

[[ -n "$ANYPOINT_CLIENT_ID" && "$ANYPOINT_CLIENT_ID" != "None" ]] || \
  fatal "/006-v3/mulesoft/client-id missing — run seed-secrets.sh first"
[[ -n "$ANYPOINT_CLIENT_SECRET" && "$ANYPOINT_CLIENT_SECRET" != "None" ]] || \
  fatal "/006-v3/mulesoft/client-secret missing — run seed-secrets.sh first"
[[ -n "$MULE_SECURE_KEY" && "$MULE_SECURE_KEY" != "None" ]] || \
  fatal "/006-v3/mulesoft/secure-properties-key missing — run seed-secrets.sh first"

ALPACA_JSON="$(sm_get_json /006-v3/vendors/alpaca)"
DWOLLA_JSON="$(sm_get_json /006-v3/vendors/dwolla)"
WEBHOOK_JSON="$(sm_get_json /006-v3/vendors/alpaca-webhook)"

ALPACA_KEY_ID="$(echo "$ALPACA_JSON" | jq -r '.APCA_API_KEY_ID // .key_id // empty')"
ALPACA_SECRET="$(echo "$ALPACA_JSON" | jq -r '.APCA_API_SECRET_KEY // .secret // empty')"
DWOLLA_CLIENT_ID="$(echo "$DWOLLA_JSON" | jq -r '.client_id // .key // empty')"
DWOLLA_CLIENT_SECRET="$(echo "$DWOLLA_JSON" | jq -r '.client_secret // .secret // empty')"
WEBHOOK_HMAC="$(echo "$WEBHOOK_JSON" | jq -r '.hmac_secret // empty')"
WEBHOOK_MCP_BEARER="$(echo "$WEBHOOK_JSON" | jq -r '.mcp_bearer_token // empty')"

[[ -n "$ALPACA_KEY_ID"      ]] || fatal "/006-v3/vendors/alpaca: APCA_API_KEY_ID missing"
[[ -n "$ALPACA_SECRET"      ]] || fatal "/006-v3/vendors/alpaca: APCA_API_SECRET_KEY missing"
[[ -n "$DWOLLA_CLIENT_ID"   ]] || fatal "/006-v3/vendors/dwolla: client_id missing"
[[ -n "$DWOLLA_CLIENT_SECRET" ]] || fatal "/006-v3/vendors/dwolla: client_secret missing"
[[ -n "$WEBHOOK_HMAC"       ]] || fatal "/006-v3/vendors/alpaca-webhook: hmac_secret missing"
[[ -n "$WEBHOOK_MCP_BEARER" ]] || WEBHOOK_MCP_BEARER="$MCP_API_KEY"

log "Sources OK."

# ---------------------------------------------------------------------------
# Detect API Gateway host for the MCP (webhook needs it as a plain property).
# Falls back to /006-v3/api-gateway/host if no REST API found.
# ---------------------------------------------------------------------------
MCP_API_HOST="$(aws apigateway get-rest-apis --region "${AWS_REGION}" \
  --query "items[?name=='006-v3-mcp-api'].id" --output text 2>/dev/null || true)"
if [[ -n "$MCP_API_HOST" && "$MCP_API_HOST" != "None" ]]; then
  MCP_API_HOST="${MCP_API_HOST}.execute-api.${AWS_REGION}.amazonaws.com"
else
  MCP_API_HOST="$(ssm_get /006-v3/api-gateway/host)"
fi
[[ -n "$MCP_API_HOST" && "$MCP_API_HOST" != "None" ]] || \
  warn "MCP API host unresolved — webhook will default to localhost (demo broken)"

# ---------------------------------------------------------------------------
# OAuth -> bearer token.
# ---------------------------------------------------------------------------
log "Authenticating with Anypoint Connected App..."
TOKEN_JSON="$(curl -s --fail-with-body --max-time 20 \
  -X POST "${ANYPOINT_BASE}/accounts/api/v2/oauth2/token" \
  -H 'Content-Type: application/json' \
  -d "$(jq -cn \
    --arg ci "$ANYPOINT_CLIENT_ID" --arg cs "$ANYPOINT_CLIENT_SECRET" \
    '{grant_type:"client_credentials",client_id:$ci,client_secret:$cs}')" \
  || echo '{}')"

BEARER="$(echo "$TOKEN_JSON" | jq -r '.access_token // empty')"
[[ -n "$BEARER" ]] || fatal "Anypoint OAuth failed — check ANYPOINT_CLIENT_ID/SECRET. Response: $TOKEN_JSON"

# ---------------------------------------------------------------------------
# Resolve organizationId + target environmentId.
# ---------------------------------------------------------------------------
ME_JSON="$(curl -s --fail-with-body --max-time 20 \
  -H "Authorization: Bearer ${BEARER}" \
  "${ANYPOINT_BASE}/accounts/api/me" || echo '{}')"
ORG_ID="$(echo "$ME_JSON" | jq -r '.user.organization.id // empty')"
[[ -n "$ORG_ID" ]] || fatal "Could not resolve organizationId from /accounts/api/me"

ENVS_JSON="$(curl -s --fail-with-body --max-time 20 \
  -H "Authorization: Bearer ${BEARER}" \
  "${ANYPOINT_BASE}/accounts/api/organizations/${ORG_ID}/environments" || echo '{}')"
ENV_ID="$(echo "$ENVS_JSON" | jq -r --arg n "$ANYPOINT_ENV_NAME" \
  '.data[] | select(.name==$n) | .id' | head -1)"
[[ -n "$ENV_ID" ]] || fatal "Env '${ANYPOINT_ENV_NAME}' not found in org ${ORG_ID}"

log "Org: ${ORG_ID}  Env(${ANYPOINT_ENV_NAME}): ${ENV_ID}"

# ---------------------------------------------------------------------------
# Build property sets for each app. Keep non-secret in 'properties', secret
# in 'secureProperties'. Alpaca key/secret ARE treated as secure. Bearer +
# HMAC likewise. `mule.secure.properties.key` is a system property (not an
# app property) — goes in 'system.properties' on the target.
# ---------------------------------------------------------------------------
build_plain_props() {
  local app="$1"
  case "$app" in
    openclaw-v3-submit-order)
      jq -cn --arg host "paper-api.alpaca.markets" --arg path "/v2" \
        '{"alpaca.endpoint_host":$host,"alpaca.endpoint_path":$path,"mock_mode":"false"}'
      ;;
    openclaw-v3-initiate-wire)
      jq -cn --arg h "api-sandbox.dwolla.com" --arg p "/" \
             --arg th "api-sandbox.dwolla.com" --arg tp "/token" \
        '{"dwolla.endpoint_host":$h,"dwolla.endpoint_path":$p,
          "dwolla.token_host":$th,"dwolla.token_path":$tp,
          "ofac.sdn_url":"https://www.treasury.gov/ofac/downloads/sdn.xml",
          "wire.dual_auth_threshold_usd":"100000","mock_mode":"false"}'
      ;;
    openclaw-v3-order-status-webhook)
      jq -cn --arg host "$MCP_API_HOST" \
             --arg path "/v3/mcp/mulesoft-actions/tools/call" \
        '{"mcp.endpoint_host":$host,"mcp.endpoint_path":$path,"mock_mode":"false"}'
      ;;
  esac
}

build_secure_props() {
  local app="$1"
  case "$app" in
    openclaw-v3-submit-order)
      jq -cn --arg k "$ALPACA_KEY_ID" --arg s "$ALPACA_SECRET" \
        '{"alpaca.key_id":$k,"alpaca.secret":$s}'
      ;;
    openclaw-v3-initiate-wire)
      jq -cn --arg k "$DWOLLA_CLIENT_ID" --arg s "$DWOLLA_CLIENT_SECRET" \
        '{"dwolla.client_id":$k,"dwolla.client_secret":$s}'
      ;;
    openclaw-v3-order-status-webhook)
      jq -cn --arg h "$WEBHOOK_HMAC" --arg t "$WEBHOOK_MCP_BEARER" \
        '{"webhook.hmac_secret":$h,"mcp.api_key":$t}'
      ;;
  esac
}

# ---------------------------------------------------------------------------
# Resolve the CloudHub 2.0 deployment id for an app name.
# ---------------------------------------------------------------------------
resolve_deployment() {
  local app="$1"
  curl -s --fail-with-body --max-time 20 \
    -H "Authorization: Bearer ${BEARER}" \
    -H "X-ANYPNT-ORG-ID: ${ORG_ID}" \
    -H "X-ANYPNT-ENV-ID: ${ENV_ID}" \
    "${ANYPOINT_BASE}/amc/application-manager/api/v2/organizations/${ORG_ID}/environments/${ENV_ID}/deployments?name=${app}" \
    | jq -r --arg n "$app" '.items[] | select(.name==$n) | .id' | head -1
}

# ---------------------------------------------------------------------------
# PATCH one app. Anypoint requires us to re-send the whole deployment object
# with properties merged in.
# ---------------------------------------------------------------------------
patch_app() {
  local app="$1"
  log "--- ${app} ---"

  local dep_id
  dep_id="$(resolve_deployment "$app")"
  [[ -n "$dep_id" ]] || { warn "No deployment found for ${app} — deploy the app first, then re-run."; return 1; }

  local cur
  cur="$(curl -s --fail-with-body --max-time 20 \
    -H "Authorization: Bearer ${BEARER}" \
    -H "X-ANYPNT-ORG-ID: ${ORG_ID}" \
    -H "X-ANYPNT-ENV-ID: ${ENV_ID}" \
    "${ANYPOINT_BASE}/amc/application-manager/api/v2/organizations/${ORG_ID}/environments/${ENV_ID}/deployments/${dep_id}")"
  [[ -n "$cur" ]] || { warn "GET deployment ${dep_id} returned empty"; return 1; }

  local plain secure patch_body
  plain="$(build_plain_props "$app")"
  secure="$(build_secure_props "$app")"

  patch_body="$(echo "$cur" | jq \
    --argjson plain "$plain" \
    --argjson secure "$secure" \
    --arg skey "$MULE_SECURE_KEY" \
    '{
        application: (.application
          | .ref //= {}
          | .configuration //= {}
          | .configuration."mule.agent.application.properties.service" //= {}
          | .configuration."mule.agent.application.properties.service".properties = $plain
          | .configuration."mule.agent.application.properties.service".secureProperties = $secure
          | .configuration."mule.agent.application.properties.service".applicationName = .ref.artifactId
          | .properties = $plain
          | .secureProperties = $secure
        )
     }')"

  if $DRY_RUN; then
    log "DRY-RUN patch body for ${app}:"
    echo "$patch_body" | jq '{ properties: .application.properties,
                               secure_keys: (.application.secureProperties | keys) }'
    return 0
  fi

  local http_code
  http_code="$(curl -s -o /tmp/mule-patch-${app}.json -w '%{http_code}' \
    -X PATCH --max-time 30 \
    -H "Authorization: Bearer ${BEARER}" \
    -H "X-ANYPNT-ORG-ID: ${ORG_ID}" \
    -H "X-ANYPNT-ENV-ID: ${ENV_ID}" \
    -H 'Content-Type: application/json' \
    -d "$patch_body" \
    "${ANYPOINT_BASE}/amc/application-manager/api/v2/organizations/${ORG_ID}/environments/${ENV_ID}/deployments/${dep_id}")"

  if [[ "$http_code" != "200" && "$http_code" != "202" ]]; then
    warn "PATCH ${app} returned HTTP ${http_code}. Response:"
    cat /tmp/mule-patch-${app}.json >&2; echo >&2
    return 1
  fi

  log "PATCH ${app} accepted (HTTP ${http_code})"
}

# ---------------------------------------------------------------------------
# Wait for app to finish APPLYING and reach RUNNING.
# ---------------------------------------------------------------------------
wait_for_running() {
  local app="$1"
  local dep_id="$2"
  local i status
  for i in $(seq 1 60); do  # 60 * 10s = 10 min max
    status="$(curl -s --max-time 15 \
      -H "Authorization: Bearer ${BEARER}" \
      -H "X-ANYPNT-ORG-ID: ${ORG_ID}" \
      -H "X-ANYPNT-ENV-ID: ${ENV_ID}" \
      "${ANYPOINT_BASE}/amc/application-manager/api/v2/organizations/${ORG_ID}/environments/${ENV_ID}/deployments/${dep_id}" \
      | jq -r '.application.status // .status // "UNKNOWN"')"
    case "$status" in
      RUNNING|APPLIED|DEPLOYED)
        log "${app}: ${status} ✓"; return 0 ;;
      APPLYING|DEPLOYING|STARTING)
        printf "    %ds  %s…\r" "$((i*10))" "$status" ;;
      FAILED|NOT_RUNNING|UNDEPLOYED)
        warn "${app}: ${status} — check Runtime Manager logs"; return 1 ;;
      *)
        printf "    %ds  %s\r" "$((i*10))" "$status" ;;
    esac
    sleep 10
  done
  warn "${app}: did not reach RUNNING within 10 min"; return 1
}

# ---------------------------------------------------------------------------
# Main loop.
# ---------------------------------------------------------------------------
FAILED=0
for app in "${APPS[@]}"; do
  if [[ -n "$FILTER_APP" && "$app" != "$FILTER_APP" ]]; then continue; fi
  if ! patch_app "$app"; then FAILED=$((FAILED+1)); continue; fi
  if $DRY_RUN || $NO_WAIT; then continue; fi
  dep_id="$(resolve_deployment "$app")"
  wait_for_running "$app" "$dep_id" || FAILED=$((FAILED+1))
done

if [[ $FAILED -gt 0 ]]; then
  warn "${FAILED} app(s) did not converge — see messages above and Runtime Manager UI"
  exit 1
fi

log "All requested apps updated and reached RUNNING."
