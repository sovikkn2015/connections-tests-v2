#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────
# registration.sh — pull Anypoint creds from Secrets Manager, run flexctl
# ──────────────────────────────────────────────────────────────────────────
# Invoked by entrypoint.sh at container start.
#
# Required env (set by ECS task definition):
#   MULESOFT_SECRET_ID    — AWS Secrets Manager secret id (e.g.
#                           /006-v2/mulesoft/credentials)
#   AWS_REGION            — region to call Secrets Manager in (task role
#                           scoped to this secret only)
#   ANYPOINT_ORG_ID       — Anypoint business-group / org UUID
#   ANYPOINT_ENV_ID       — Anypoint environment UUID (prod / staging)
#   GATEWAY_NAME          — human name shown in Runtime Manager
#                           (e.g. ir-flex-gateway-prod-${TASK_ID})
#
# Secrets Manager JSON blob is expected to contain:
#   { "client_id": "...", "client_secret": "...",
#     "connected_app_id": "...",  (optional — falls back to client_id)
#     "anypoint_platform_url": "https://anypoint.mulesoft.com" (optional) }
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail

log() { echo "[registration] $(date -u +%FT%TZ) $*"; }

# ---- Preflight ---------------------------------------------------------
: "${MULESOFT_SECRET_ID:?MULESOFT_SECRET_ID must be set (e.g. /006-v2/mulesoft/credentials)}"
: "${AWS_REGION:?AWS_REGION must be set}"
: "${ANYPOINT_ORG_ID:?ANYPOINT_ORG_ID must be set}"
: "${ANYPOINT_ENV_ID:?ANYPOINT_ENV_ID must be set}"

GATEWAY_NAME="${GATEWAY_NAME:-ir-flex-gateway-${HOSTNAME:-unknown}}"
REG_FILE="${REG_FILE:-/opt/flex-gateway/registration.yaml}"

# ---- Fetch secret ------------------------------------------------------
log "Fetching secret '${MULESOFT_SECRET_ID}' from region '${AWS_REGION}'"
SECRET_JSON="$(
  aws secretsmanager get-secret-value \
    --region "${AWS_REGION}" \
    --secret-id "${MULESOFT_SECRET_ID}" \
    --query 'SecretString' \
    --output text
)"

if [[ -z "${SECRET_JSON}" || "${SECRET_JSON}" == "None" ]]; then
  log "ERROR: empty SecretString for ${MULESOFT_SECRET_ID}"
  exit 1
fi

CLIENT_ID="$(echo "${SECRET_JSON}" | jq -r '.client_id // empty')"
CLIENT_SECRET="$(echo "${SECRET_JSON}" | jq -r '.client_secret // empty')"
CONNECTED_APP_ID="$(echo "${SECRET_JSON}" | jq -r '.connected_app_id // .client_id // empty')"
ANYPOINT_URL_FROM_SECRET="$(echo "${SECRET_JSON}" | jq -r '.anypoint_platform_url // empty')"

if [[ -z "${CLIENT_ID}" || -z "${CLIENT_SECRET}" ]]; then
  log "ERROR: secret is missing client_id and/or client_secret"
  exit 1
fi

# env > secret > default, so operators can pin the control plane URL
ANYPOINT_PLATFORM_URL="${ANYPOINT_PLATFORM_URL:-${ANYPOINT_URL_FROM_SECRET:-https://anypoint.mulesoft.com}}"
export ANYPOINT_PLATFORM_URL

# ---- Idempotency — skip if already registered -------------------------
if [[ -s "${REG_FILE}" ]]; then
  log "Registration file ${REG_FILE} already populated — skipping flexctl register"
  exit 0
fi

# ---- Register ----------------------------------------------------------
log "Registering gateway '${GATEWAY_NAME}' with org=${ANYPOINT_ORG_ID} env=${ANYPOINT_ENV_ID}"
flexctl register "${GATEWAY_NAME}" \
  --anypoint-platform-url="${ANYPOINT_PLATFORM_URL}" \
  --client-id="${CLIENT_ID}" \
  --client-secret="${CLIENT_SECRET}" \
  --connected-app-id="${CONNECTED_APP_ID}" \
  --organization="${ANYPOINT_ORG_ID}" \
  --environment="${ANYPOINT_ENV_ID}" \
  --connectivity-mode=connected \
  --output-directory="$(dirname "${REG_FILE}")"

# flexctl writes registration.yaml into output-directory; normalize name
if [[ -f "$(dirname "${REG_FILE}")/registration.yaml" && ! -s "${REG_FILE}" ]]; then
  :  # already correct
elif [[ -f "$(dirname "${REG_FILE}")/${GATEWAY_NAME}.yaml" ]]; then
  mv "$(dirname "${REG_FILE}")/${GATEWAY_NAME}.yaml" "${REG_FILE}"
fi

# Scrub the in-memory vars so they can't leak into child processes
unset CLIENT_ID CLIENT_SECRET CONNECTED_APP_ID SECRET_JSON

log "Registration complete → ${REG_FILE}"
