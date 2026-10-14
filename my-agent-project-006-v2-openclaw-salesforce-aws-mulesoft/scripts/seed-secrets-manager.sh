#!/usr/bin/env bash
# =============================================================================
# seed-secrets-manager.sh - Ensure AWS Secrets Manager entries for 006 v2 exist.
#
# This script is additive. It NEVER deletes or overwrites the two existing
# secrets that were created manually during Phase 6 bring-up:
#
#   /006-v2/mulesoft/credentials        (MuleSoft Anypoint Connected App creds)
#   /006-v2/vendors/alpaca              (Alpaca paper trading creds)
#
# It manages one secret end-to-end:
#
#   /006-v2/hitl/signing-key            (HMAC-SHA256 key for HITL approval tokens)
#     - creates it on first run with `openssl rand -hex 32`
#     - with --force-refresh, rotates it via put-secret-value
#
# Secret VALUES are never printed. Only ARNs, status, and last-rotated dates.
#
# Usage:
#   ./scripts/seed-secrets-manager.sh                  # ensure all 3 exist
#   ./scripts/seed-secrets-manager.sh --force-refresh  # rotate the HITL key
#
# Env vars (with defaults):
#   AWS_REGION (us-east-1)
# =============================================================================

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
FORCE_REFRESH=false

# --- colors -----------------------------------------------------------------
GREEN=$'\033[1;32m'
RED=$'\033[1;31m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[1;34m'
RESET=$'\033[0m'

log()   { printf "%b[seed-secrets]%b %s\n" "${BLUE}" "${RESET}" "$*"; }
warn()  { printf "%b[seed-secrets WARN]%b %s\n" "${YELLOW}" "${RESET}" "$*" >&2; }
fatal() { printf "%b[seed-secrets FATAL]%b %s\n" "${RED}" "${RESET}" "$*" >&2; exit 1; }

# --- args -------------------------------------------------------------------
for arg in "$@"; do
  case "$arg" in
    --force-refresh) FORCE_REFRESH=true ;;
    -h|--help)
      sed -n '2,25p' "$0"
      exit 0
      ;;
    *) fatal "Unknown arg: ${arg}" ;;
  esac
done

# --- preflight --------------------------------------------------------------
command -v aws >/dev/null     || fatal "aws CLI not found"
command -v jq >/dev/null      || fatal "jq not found"
command -v openssl >/dev/null || fatal "openssl not found"

aws sts get-caller-identity --region "${AWS_REGION}" >/dev/null 2>&1 \
  || fatal "AWS CLI not authenticated. Run: aws configure"

# Secret identifiers. (AWS appends a 6-char random suffix to the ARN, but the
# Name portion — what we use as secret-id — is just the plain path.)
MULESOFT_SECRET_ID="/006-v2/mulesoft/credentials"
ALPACA_SECRET_ID="/006-v2/vendors/alpaca"
HITL_SECRET_ID="/006-v2/hitl/signing-key"

# State trackers per secret (parallel indexed arrays -> portable to bash 3.2
# which is macOS default; associative arrays would require bash 4+).
SECRET_IDS=()
SECRET_STATUSES=()
SECRET_ARNS=()
SECRET_ROTATEDS=()

# Helpers to set values by index
_find_idx() {
  local target="$1" i
  for i in "${!SECRET_IDS[@]}"; do
    [[ "${SECRET_IDS[$i]}" == "${target}" ]] && { echo "$i"; return 0; }
  done
  return 1
}
_record() {
  # usage: _record <sid> <status> <arn> <rotated>
  local sid="$1" status="$2" arn="$3" rotated="$4" idx
  if idx="$(_find_idx "${sid}")"; then
    SECRET_STATUSES[$idx]="${status}"
    SECRET_ARNS[$idx]="${arn}"
    SECRET_ROTATEDS[$idx]="${rotated}"
  else
    SECRET_IDS+=("${sid}")
    SECRET_STATUSES+=("${status}")
    SECRET_ARNS+=("${arn}")
    SECRET_ROTATEDS+=("${rotated}")
  fi
}

# -----------------------------------------------------------------------------
# describe_existing <secret-id>  -> echoes "ARN|LastChangedDate" on success, empty on miss
# Does NOT fetch the value, only metadata.
# -----------------------------------------------------------------------------
describe_existing() {
  local sid="$1" desc arn rotated
  if desc="$(aws secretsmanager describe-secret \
              --secret-id "${sid}" \
              --region "${AWS_REGION}" 2>/dev/null)"; then
    arn="$(echo "${desc}" | jq -r '.ARN // ""')"
    rotated="$(echo "${desc}" | jq -r '.LastRotatedDate // .LastChangedDate // "unknown"')"
    echo "${arn}|${rotated}"
    return 0
  fi
  return 1
}

# -----------------------------------------------------------------------------
# ensure_existing_only <secret-id>  (no creation, no mutation)
# -----------------------------------------------------------------------------
ensure_existing_only() {
  local sid="$1" info arn rotated
  if info="$(describe_existing "${sid}")"; then
    arn="${info%%|*}"
    rotated="${info#*|}"
    _record "${sid}" "exists" "${arn}" "${rotated}"
    log "OK: ${sid} exists"
  else
    _record "${sid}" "MISSING" "-" "-"
    warn "${sid} NOT FOUND. This script does not create it - create manually, then re-run."
  fi
}

# -----------------------------------------------------------------------------
# ensure_hitl_key  - creates the HITL signing key if missing; rotates if --force-refresh.
# -----------------------------------------------------------------------------
ensure_hitl_key() {
  local sid="${HITL_SECRET_ID}"
  local key info arn rotated

  if info="$(describe_existing "${sid}")"; then
    arn="${info%%|*}"
    rotated="${info#*|}"
    if $FORCE_REFRESH; then
      key="$(openssl rand -hex 32)"
      aws secretsmanager put-secret-value \
        --secret-id "${sid}" \
        --region "${AWS_REGION}" \
        --secret-string "$(jq -cn --arg k "${key}" '{signing_key: $k}')" \
        >/dev/null
      # refresh metadata
      info="$(describe_existing "${sid}")"
      arn="${info%%|*}"; rotated="${info#*|}"
      _record "${sid}" "refreshed" "${arn}" "${rotated}"
      log "HITL signing key rotated."
    else
      _record "${sid}" "exists" "${arn}" "${rotated}"
      log "OK: ${sid} exists (use --force-refresh to rotate)"
    fi
    unset key
    return 0
  fi

  # Does not exist - create it.
  key="$(openssl rand -hex 32)"
  arn="$(aws secretsmanager create-secret \
          --name "${sid}" \
          --description "HMAC-SHA256 signing key for HITL approval tokens (006 v2 Phase 6)" \
          --region "${AWS_REGION}" \
          --secret-string "$(jq -cn --arg k "${key}" '{signing_key: $k}')" \
          --tags Key=project,Value=006-v2 Key=purpose,Value=hitl-signing \
          --query 'ARN' --output text)"
  unset key
  info="$(describe_existing "${sid}")"
  rotated="${info#*|}"
  _record "${sid}" "created" "${arn}" "${rotated}"
  log "Created ${sid}"
}

# --- main -------------------------------------------------------------------
log "Region: ${AWS_REGION}"
$FORCE_REFRESH && log "Mode: --force-refresh (will rotate HITL key)"

ensure_existing_only "${MULESOFT_SECRET_ID}"
ensure_existing_only "${ALPACA_SECRET_ID}"
ensure_hitl_key

# --- summary ---------------------------------------------------------------
echo ""
printf "%b=== Secrets summary ===%b\n" "${BLUE}" "${RESET}"
printf "%-40s %-12s %-30s %s\n" "SECRET" "STATUS" "LAST_ROTATED" "ARN"
printf "%-40s %-12s %-30s %s\n" "------" "------" "------------" "---"
any_missing=0
for i in "${!SECRET_IDS[@]}"; do
  sid="${SECRET_IDS[$i]}"
  status="${SECRET_STATUSES[$i]}"
  arn="${SECRET_ARNS[$i]}"
  rotated="${SECRET_ROTATEDS[$i]}"
  color="${GREEN}"
  [[ "${status}" == "MISSING"   ]] && { color="${RED}";    any_missing=1; }
  [[ "${status}" == "refreshed" ]] && color="${YELLOW}"
  printf "%b%-40s %-12s %-30s %s%b\n" "${color}" "${sid}" "${status}" "${rotated}" "${arn}" "${RESET}"
done
echo ""

if (( any_missing )); then
  fatal "One or more pre-existing secrets are missing. Fix manually and re-run."
fi

log "Done."
