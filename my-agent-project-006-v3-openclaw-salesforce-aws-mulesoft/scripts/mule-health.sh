#!/usr/bin/env bash
# ============================================================================
# mule-health.sh — Dynamic /api/health probe for the three v3 Mule apps.
#
# Why a script (not a Makefile recipe): we need to OAuth with Anypoint and
# look up each app's publicUrl at runtime, because the CloudHub subdomain
# (e.g. "5sc6y6-3.usa-e2.cloudhub.io") is per-business-group and can't be
# hardcoded in a portable Makefile.
#
# Reads from AWS (idempotent — same source of truth as every other Mule
# script in this project):
#   /006-v3/mulesoft/client-id       (SSM)
#   /006-v3/mulesoft/client-secret   (SSM)
#
# Usage:
#   bash scripts/mule-health.sh                # all 3 apps
#   bash scripts/mule-health.sh submit-order   # one app
#   bash scripts/mule-health.sh --env=Production   # switch env
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

AWS_REGION="${AWS_REGION_BEDROCK:-us-east-1}"
ANYPOINT_BASE="${ANYPOINT_BASE:-https://anypoint.mulesoft.com}"
ANYPOINT_ENV_NAME="${ANYPOINT_ENVIRONMENT:-Sandbox}"

APPS=("openclaw-v3-submit-order" "openclaw-v3-initiate-wire" "openclaw-v3-order-status-webhook")
FILTER_APP=""

for arg in "$@"; do
  case "$arg" in
    --env=*) ANYPOINT_ENV_NAME="${arg#--env=}" ;;
    openclaw-v3-*) FILTER_APP="$arg" ;;
    submit-order|initiate-wire|order-status-webhook)
      FILTER_APP="openclaw-v3-$arg" ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

log()  { printf "\033[1;34m[mule-health]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[mule-health WARN]\033[0m %s\n" "$*" >&2; }

ANYPOINT_CLIENT_ID="$(aws ssm get-parameter --region "${AWS_REGION}" \
  --name /006-v3/mulesoft/client-id --with-decryption \
  --query 'Parameter.Value' --output text 2>/dev/null || echo '')"
ANYPOINT_CLIENT_SECRET="$(aws ssm get-parameter --region "${AWS_REGION}" \
  --name /006-v3/mulesoft/client-secret --with-decryption \
  --query 'Parameter.Value' --output text 2>/dev/null || echo '')"

if [[ -z "$ANYPOINT_CLIENT_ID" || -z "$ANYPOINT_CLIENT_SECRET" ]]; then
  warn "Anypoint creds missing in SSM — run scripts/seed-secrets.sh first"
  exit 1
fi

BEARER="$(curl -s --max-time 20 \
  -X POST "${ANYPOINT_BASE}/accounts/api/v2/oauth2/token" \
  -H 'Content-Type: application/json' \
  -d "$(jq -cn \
    --arg ci "$ANYPOINT_CLIENT_ID" --arg cs "$ANYPOINT_CLIENT_SECRET" \
    '{grant_type:"client_credentials",client_id:$ci,client_secret:$cs}')" \
  | jq -r '.access_token // empty')"
[[ -n "$BEARER" ]] || { warn "Anypoint OAuth failed"; exit 1; }

ME_JSON="$(curl -s --max-time 20 \
  -H "Authorization: Bearer ${BEARER}" \
  "${ANYPOINT_BASE}/accounts/api/me")"
ORG_ID="$(echo "$ME_JSON" | jq -r '.user.organization.id // empty')"
[[ -n "$ORG_ID" ]] || { warn "Could not resolve organizationId"; exit 1; }

ENV_ID="$(curl -s --max-time 20 \
  -H "Authorization: Bearer ${BEARER}" \
  "${ANYPOINT_BASE}/accounts/api/organizations/${ORG_ID}/environments" \
  | jq -r --arg n "$ANYPOINT_ENV_NAME" \
      '.data[] | select(.name==$n) | .id' | head -1)"
[[ -n "$ENV_ID" ]] || { warn "Env '${ANYPOINT_ENV_NAME}' not found"; exit 1; }

FAILED=0
for app in "${APPS[@]}"; do
  if [[ -n "$FILTER_APP" && "$app" != "$FILTER_APP" ]]; then continue; fi
  echo ""
  echo "==> ${app} ==="

  # Step 1: list deployments by name -> deployment id
  DEP_ID="$(curl -s --max-time 20 \
    -H "Authorization: Bearer ${BEARER}" \
    -H "X-ANYPNT-ORG-ID: ${ORG_ID}" \
    -H "X-ANYPNT-ENV-ID: ${ENV_ID}" \
    "${ANYPOINT_BASE}/amc/application-manager/api/v2/organizations/${ORG_ID}/environments/${ENV_ID}/deployments?name=${app}" \
    | jq -r --arg n "$app" '[.items[] | select(.name==$n)] | .[0].id // empty')"

  if [[ -z "$DEP_ID" || "$DEP_ID" == "null" ]]; then
    warn "${app}: no deployment found"
    FAILED=$((FAILED+1)); continue
  fi

  # Step 2: GET the full deployment object -> publicUrl lives under
  #         .target.deploymentSettings.http.inbound.publicUrl
  URL="$(curl -s --max-time 20 \
    -H "Authorization: Bearer ${BEARER}" \
    -H "X-ANYPNT-ORG-ID: ${ORG_ID}" \
    -H "X-ANYPNT-ENV-ID: ${ENV_ID}" \
    "${ANYPOINT_BASE}/amc/application-manager/api/v2/organizations/${ORG_ID}/environments/${ENV_ID}/deployments/${DEP_ID}" \
    | jq -r '.target.deploymentSettings.http.inbound.publicUrl // empty')"

  if [[ -z "$URL" || "$URL" == "null" ]]; then
    warn "${app}: deployment has no publicUrl (generateDefaultPublicUrl=false?)"
    FAILED=$((FAILED+1)); continue
  fi

  echo "    URL: ${URL}"
  BODY="$(curl -fsS --max-time 10 "${URL%/}/api/health" 2>/dev/null || echo '')"
  if [[ -z "$BODY" ]]; then
    warn "${app}: /api/health unreachable at ${URL}"
    FAILED=$((FAILED+1))
  else
    echo "    $BODY"
  fi
done

echo ""
if [[ $FAILED -gt 0 ]]; then
  warn "${FAILED} app(s) unhealthy — see above"; exit 1
fi
log "All probed apps healthy."
