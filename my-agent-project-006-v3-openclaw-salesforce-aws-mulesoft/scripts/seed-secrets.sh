#!/usr/bin/env bash
# ============================================================================
# seed-secrets.sh — Seed AWS Secrets Manager + SSM Parameter Store from .env
#
# Reads the gitignored ./.env (copied from .env.example), writes every
# required secret to AWS. Idempotent — re-run any time credentials rotate.
#
# Usage:
#   cp .env.example .env         # fill in real values
#   ./scripts/seed-secrets.sh    # pushes to AWS
#   rm .env                      # optional; scripts/deploy-all.sh re-reads
#
# Prereqs: aws CLI authenticated; jq installed.
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

[[ -f .env ]] || { echo "FATAL: .env missing. Copy from .env.example and fill in values."; exit 1; }
set -a
# shellcheck disable=SC1091
source .env
set +a

log() { printf "\033[1;34m[seed-secrets]\033[0m %s\n" "$*"; }

: "${AWS_REGION_BEDROCK:=us-east-1}"

put_ssm() {
  local name="$1" value="$2"
  if [[ -z "${value}" || "${value}" == "<"*">" ]]; then
    log "skip ${name} (placeholder/empty)"; return
  fi
  aws ssm put-parameter \
    --name "${name}" --value "${value}" --type SecureString --overwrite \
    --region "${AWS_REGION_BEDROCK}" >/dev/null
  log "ssm ${name}"
}

put_secret_json() {
  local name="$1" json="$2"
  if aws secretsmanager describe-secret --secret-id "${name}" \
        --region "${AWS_REGION_BEDROCK}" >/dev/null 2>&1; then
    aws secretsmanager put-secret-value --secret-id "${name}" \
          --secret-string "${json}" --region "${AWS_REGION_BEDROCK}" >/dev/null
  else
    aws secretsmanager create-secret --name "${name}" \
          --secret-string "${json}" --region "${AWS_REGION_BEDROCK}" >/dev/null
  fi
  log "secret ${name}"
}

# MCP API key + session signing keys + HITL signing key
put_ssm "/006-v3/mcp/api-key" "${MCP_API_KEY:-}"
put_ssm "/006-v3/agentcore/session-signing-key" "${AGENTCORE_SESSION_SIGNING_KEY:-}"
put_ssm "/006-v3/hitl/signing-key" "${HITL_SIGNING_KEY:-}"

# Vendor API keys
put_ssm "/006-v3/vendors/finnhub" "${FINNHUB_API_KEY:-}"
put_ssm "/006-v3/vendors/alpha-vantage" "${ALPHA_VANTAGE_API_KEY:-}"
put_ssm "/006-v3/vendors/tavily" "${TAVILY_API_KEY:-}"

# Salesforce OAuth bootstrap (Connected App for SF Auth Proxy OBO)
put_secret_json "/006-v3/sf/bootstrap-creds" "$(jq -cn \
  --arg cid "${SF_OAUTH_CLIENT_ID:-}" \
  --arg csec "${SF_OAUTH_CLIENT_SECRET:-}" \
  --arg inst "${SF_INSTANCE_URL:-}" \
  --arg user "${SF_USERNAME:-}" \
  '{consumer_key:$cid, consumer_secret:$csec, instance_url:$inst, integration_user:$user}')"
put_ssm "/006-v3/sf/auth-proxy-key" "${SF_OAUTH_CLIENT_SECRET:-}"

# MuleSoft Anypoint (both hyphenated + underscored names kept for back-compat).
put_ssm "/006-v3/mulesoft/client-id"     "${MULESOFT_CLIENT_ID:-}"
put_ssm "/006-v3/mulesoft/client-secret" "${MULESOFT_CLIENT_SECRET:-}"
put_ssm "/006-v3/mulesoft/client_id"     "${MULESOFT_CLIENT_ID:-}"
put_ssm "/006-v3/mulesoft/client_secret" "${MULESOFT_CLIENT_SECRET:-}"
put_ssm "/006-v3/mulesoft/org_id"        "${MULESOFT_ORG_ID:-}"

# Mule secure-properties bootstrap key (16-char ASCII).
# Used by each CloudHub app as the system property `mule.secure.properties.key`
# to decrypt per-app secure values. Generated if missing.
: "${MULE_SECURE_PROPERTIES_KEY:=$(openssl rand -hex 8 | head -c 16)}"
put_ssm "/006-v3/mulesoft/secure-properties-key" "${MULE_SECURE_PROPERTIES_KEY}"

# Vendor trading/wire creds.
# Key names match what set-mule-secure-properties.sh reads (APCA_API_KEY_ID,
# APCA_API_SECRET_KEY for Alpaca; client_id, client_secret for Dwolla).
put_secret_json "/006-v3/vendors/alpaca" "$(jq -cn \
  --arg kid "${ALPACA_KEY_ID:-}" --arg sec "${ALPACA_SECRET:-}" \
  --arg ep "${ALPACA_ENDPOINT:-https://paper-api.alpaca.markets}" \
  '{APCA_API_KEY_ID:$kid, APCA_API_SECRET_KEY:$sec, endpoint:$ep, mode:"paper"}')"
put_secret_json "/006-v3/vendors/dwolla" "$(jq -cn \
  --arg k "${DWOLLA_KEY:-}" --arg s "${DWOLLA_SECRET:-}" \
  '{client_id:$k, client_secret:$s, environment:"sandbox"}')"

# Webhook HMAC + MCP bearer for order-status-webhook.
: "${WEBHOOK_HMAC_SECRET:=$(openssl rand -hex 32)}"
put_secret_json "/006-v3/vendors/alpaca-webhook" "$(jq -cn \
  --arg h "${WEBHOOK_HMAC_SECRET}" --arg t "${MCP_API_KEY:-}" \
  '{hmac_secret:$h, mcp_bearer_token:$t}')"

# Langfuse
put_secret_json "/006-v3/langfuse/keys" "$(jq -cn \
  --arg pub "${LANGFUSE_PUBLIC_KEY:-}" --arg sec "${LANGFUSE_SECRET_KEY:-}" \
  --arg host "${LANGFUSE_HOST:-https://cloud.langfuse.com}" \
  '{public_key:$pub, secret_key:$sec, host:$host}')"

log "Done."
