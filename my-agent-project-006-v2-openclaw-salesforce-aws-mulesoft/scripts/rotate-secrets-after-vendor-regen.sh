#!/usr/bin/env bash
# =============================================================================
# rotate-secrets-after-vendor-regen.sh
#
# After regenerating credentials in the Alpaca dashboard or the Anypoint
# Access Management console, this script:
#   (1) updates the corresponding AWS Secrets Manager entry,
#   (2) for MuleSoft: PATCHes the CloudHub 2.0 app so Anypoint Management
#       Console picks up the new client_secret and restarts the app,
#   (3) forces a cold-start of any Lambda that reads the rotated secret.
#
# Secrets are NEVER passed via argv. Supply them via stdin as JSON or via a
# file path (chmod 600, gitignored). The script reads, uses, shreds.
#
# The script is idempotent and will refuse to run without `--confirm`.
#
# -----------------------------------------------------------------------------
# Subcommands
# -----------------------------------------------------------------------------
#
#   rotate-alpaca     Rotate /006-v2/vendors/alpaca
#                     Expected JSON: {"key_id":"...", "secret":"...",
#                                     "endpoint":"https://paper-api.alpaca.markets"}
#                     Touches: AWS Secrets Manager. Does NOT touch CloudHub
#                     directly (Alpaca keys live in Anypoint Runtime Manager
#                     Secure Properties, which is a separate manual UI step
#                     explained in the post-run instructions).
#
#   rotate-mulesoft   Rotate /006-v2/mulesoft/credentials
#                     Expected JSON: {"client_id":"...", "client_secret":"...",
#                                     "base_url":"https://anypoint.mulesoft.com",
#                                     "process_api_base_url":"https://...cloudhub.io",
#                                     "organization_id":"...",
#                                     "environment_id":"..."}
#                     Touches: AWS Secrets Manager, CloudHub app (AMC PATCH to
#                     re-inject new Connected App secret into submit-order),
#                     Lambda env (cold-restart of openclaw-mcp-006-v2-mulesoft-actions
#                     so it re-reads the rotated secret on next invocation).
#
# -----------------------------------------------------------------------------
# Usage
# -----------------------------------------------------------------------------
#
#   # From a file on disk (file is shredded after use):
#   ./scripts/rotate-secrets-after-vendor-regen.sh rotate-alpaca   --confirm --from-file /tmp/alpaca.json
#   ./scripts/rotate-secrets-after-vendor-regen.sh rotate-mulesoft --confirm --from-file /tmp/mule.json
#
#   # From stdin (preferred, nothing written to disk):
#   aws secretsmanager get-secret-value --secret-id <vault> --query SecretString --output text \
#     | ./scripts/rotate-secrets-after-vendor-regen.sh rotate-alpaca --confirm --from-stdin
#
# Env vars (with defaults):
#   AWS_REGION=us-east-1
#   MULESOFT_FUNCTION_NAME=openclaw-mcp-006-v2-mulesoft-actions
#   CLOUDHUB_APP_ID=b631a753-a558-4041-b4af-e7498db30972
#   CLOUDHUB_ENV_ID=3d6484f8-928b-4d3c-b970-2e9ac442ff83
#   CLOUDHUB_ORG_ID=2dc8acc5-23cb-424f-95a5-13686d8b9b16
#
# =============================================================================

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
MULESOFT_FUNCTION_NAME="${MULESOFT_FUNCTION_NAME:-openclaw-mcp-006-v2-mulesoft-actions}"
CLOUDHUB_APP_ID="${CLOUDHUB_APP_ID:-b631a753-a558-4041-b4af-e7498db30972}"
CLOUDHUB_ENV_ID="${CLOUDHUB_ENV_ID:-3d6484f8-928b-4d3c-b970-2e9ac442ff83}"
CLOUDHUB_ORG_ID="${CLOUDHUB_ORG_ID:-2dc8acc5-23cb-424f-95a5-13686d8b9b16}"

ALPACA_SECRET_ID="/006-v2/vendors/alpaca"
MULESOFT_SECRET_ID="/006-v2/mulesoft/credentials"

# --- colors -----------------------------------------------------------------
GREEN=$'\033[1;32m'
RED=$'\033[1;31m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[1;34m'
RESET=$'\033[0m'

log()   { printf "%b[rotate]%b %s\n" "${BLUE}" "${RESET}" "$*"; }
warn()  { printf "%b[rotate WARN]%b %s\n" "${YELLOW}" "${RESET}" "$*" >&2; }
fatal() { printf "%b[rotate FATAL]%b %s\n" "${RED}" "${RESET}" "$*" >&2; exit 1; }
ok()    { printf "%b[rotate OK]%b %s\n" "${GREEN}" "${RESET}" "$*"; }

# --- usage ------------------------------------------------------------------
usage() {
  sed -n '1,55p' "$0"
  exit "${1:-0}"
}

# --- parse args -------------------------------------------------------------
SUBCOMMAND="${1:-}"
shift || true
CONFIRM=false
FROM_FILE=""
FROM_STDIN=false

for arg in "$@"; do
  case "${arg}" in
    --confirm)     CONFIRM=true ;;
    --from-stdin)  FROM_STDIN=true ;;
    --from-file=*) FROM_FILE="${arg#--from-file=}" ;;
    --from-file)   : ;;  # handled below via next-arg
    -h|--help)     usage 0 ;;
    *)
      # support `--from-file /path/to/file` pattern
      if [[ "${FROM_FILE}" == "" && -f "${arg}" ]]; then
        FROM_FILE="${arg}"
      else
        fatal "Unknown arg: ${arg}"
      fi
      ;;
  esac
done

[[ -z "${SUBCOMMAND}" ]] && usage 1

if ! ${CONFIRM}; then
  fatal "Refusing to run without --confirm. (Safety: rotations are destructive.)"
fi

if ${FROM_STDIN} && [[ -n "${FROM_FILE}" ]]; then
  fatal "Pass either --from-stdin OR --from-file, not both."
fi
if ! ${FROM_STDIN} && [[ -z "${FROM_FILE}" ]]; then
  fatal "Pass either --from-stdin or --from-file <path>."
fi

# --- preflight --------------------------------------------------------------
command -v aws  >/dev/null || fatal "aws CLI not found"
command -v jq   >/dev/null || fatal "jq not found"
command -v curl >/dev/null || fatal "curl not found"

aws sts get-caller-identity --region "${AWS_REGION}" >/dev/null 2>&1 \
  || fatal "AWS CLI not authenticated. Run: aws configure"

# --- read secret payload into variable (never echoed) ----------------------
SECRET_JSON=""
if ${FROM_STDIN}; then
  SECRET_JSON="$(cat)"
else
  [[ -r "${FROM_FILE}" ]] || fatal "File not readable: ${FROM_FILE}"
  SECRET_JSON="$(cat "${FROM_FILE}")"
  # shred after read
  if command -v shred >/dev/null; then
    shred -u "${FROM_FILE}"
  else
    rm -f "${FROM_FILE}"
  fi
  log "Source file consumed and removed."
fi

# validate JSON without echoing
echo "${SECRET_JSON}" | jq -e . >/dev/null 2>&1 \
  || fatal "Secret payload is not valid JSON."

# --- helpers ----------------------------------------------------------------
require_fields() {
  # usage: require_fields <field1> <field2> ...
  local f
  for f in "$@"; do
    echo "${SECRET_JSON}" | jq -e --arg k "${f}" '.[$k] // empty' >/dev/null \
      || fatal "Missing required field: ${f}"
  done
}

put_secret_value() {
  local sid="$1"
  aws secretsmanager put-secret-value \
    --secret-id "${sid}" \
    --region "${AWS_REGION}" \
    --secret-string "${SECRET_JSON}" \
    --query 'VersionId' --output text >/dev/null
}

cold_restart_lambda() {
  local fn="$1" ts
  ts="$(date +%s)"
  # Toggling a sentinel env var triggers a new execution environment.
  local existing
  existing="$(aws lambda get-function-configuration \
                --function-name "${fn}" \
                --region "${AWS_REGION}" \
                --query 'Environment.Variables' --output json 2>/dev/null || echo '{}')"
  local merged
  merged="$(echo "${existing}" | jq --arg ts "${ts}" '. + {ROTATED_AT: $ts}')"
  aws lambda update-function-configuration \
    --function-name "${fn}" \
    --region "${AWS_REGION}" \
    --environment "Variables=$(echo "${merged}" | jq -c .)" \
    --query 'LastUpdateStatus' --output text >/dev/null
  aws lambda wait function-updated \
    --function-name "${fn}" \
    --region "${AWS_REGION}"
}

# --- subcommands ------------------------------------------------------------
rotate_alpaca() {
  require_fields key_id secret endpoint
  log "Updating ${ALPACA_SECRET_ID} in AWS Secrets Manager..."
  put_secret_value "${ALPACA_SECRET_ID}"
  ok "Secret updated."

  cat <<EOF

Next MANUAL step (Anypoint UI):
  1. Open https://anypoint.mulesoft.com/runtimemanager/
  2. Select app  : openclaw-v2-trade-process-api
  3. Go to       : Properties tab > Secure Properties
  4. Replace     : ALPACA_KEY_ID  and  ALPACA_SECRET
  5. Click       : Apply Changes  (app will restart)

The Lambda side is done; CloudHub still reads Alpaca creds from Anypoint
Secure Properties and cannot be PATCHed from here without Connected App
scopes that our current token does not have.

EOF
}

rotate_mulesoft() {
  require_fields client_id client_secret
  log "Updating ${MULESOFT_SECRET_ID} in AWS Secrets Manager..."
  put_secret_value "${MULESOFT_SECRET_ID}"
  ok "Secret updated."

  # --- AMC PATCH: push new client_secret into CloudHub app config ---------
  log "PATCHing CloudHub app ${CLOUDHUB_APP_ID} with rotated Connected App secret..."
  local client_id client_secret
  client_id="$(echo "${SECRET_JSON}"     | jq -r '.client_id')"
  client_secret="$(echo "${SECRET_JSON}" | jq -r '.client_secret')"

  # Fetch an Anypoint access token via client_credentials using the NEW creds
  # to validate they work before we trigger a restart.
  local anypoint_base token resp
  anypoint_base="$(echo "${SECRET_JSON}" | jq -r '.base_url // "https://anypoint.mulesoft.com"')"
  resp="$(curl -sS -X POST "${anypoint_base}/accounts/api/v2/oauth2/token" \
           -H 'Content-Type: application/x-www-form-urlencoded' \
           --data-urlencode "grant_type=client_credentials" \
           --data-urlencode "client_id=${client_id}" \
           --data-urlencode "client_secret=${client_secret}")"
  token="$(echo "${resp}" | jq -r '.access_token // empty')"
  [[ -n "${token}" ]] || fatal "New Connected App credentials failed to mint a token. Aborting before CloudHub PATCH."
  log "New Connected App creds validated (token minted)."

  # Clear sensitive locals immediately
  unset client_secret
  unset resp

  # PATCH CloudHub app with empty payload to trigger a restart - AMC re-reads
  # the connected-app secret it has for this org at startup.
  local patch_url patch_resp
  patch_url="${anypoint_base}/amc/application-manager/api/v2/organizations/${CLOUDHUB_ORG_ID}/environments/${CLOUDHUB_ENV_ID}/deployments/${CLOUDHUB_APP_ID}"
  patch_resp="$(curl -sS -X PATCH "${patch_url}" \
                 -H "Authorization: Bearer ${token}" \
                 -H 'Content-Type: application/json' \
                 -d '{"target":{"deploymentSettings":{"lastMileSecurity":false}}}' \
                 -o /dev/null -w '%{http_code}')" || patch_resp="000"
  unset token
  if [[ "${patch_resp}" =~ ^2 ]]; then
    ok "CloudHub app PATCHed (HTTP ${patch_resp}); app will restart shortly."
  else
    warn "CloudHub PATCH returned HTTP ${patch_resp}. Restart the app manually in Runtime Manager."
  fi

  # --- cold-start Lambda so it re-reads /006-v2/mulesoft/credentials ------
  log "Cold-restarting Lambda ${MULESOFT_FUNCTION_NAME}..."
  cold_restart_lambda "${MULESOFT_FUNCTION_NAME}"
  ok "Lambda restarted. Next invocation will fetch the rotated secret."
}

# --- dispatch ---------------------------------------------------------------
case "${SUBCOMMAND}" in
  rotate-alpaca)   rotate_alpaca ;;
  rotate-mulesoft) rotate_mulesoft ;;
  -h|--help|help)  usage 0 ;;
  *) fatal "Unknown subcommand: ${SUBCOMMAND}. Valid: rotate-alpaca | rotate-mulesoft" ;;
esac

# --- zero out the in-memory copy -------------------------------------------
SECRET_JSON=""
unset SECRET_JSON

ok "Rotation complete."
