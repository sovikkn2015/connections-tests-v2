#!/usr/bin/env bash
# ============================================================================
# cognito-preflight.sh — Validate the 4 Cognito env vars + live JWKS endpoint
# before a frontend build/deploy picks up the Cognito wiring.
#
# Why a preflight: the v3 SPA silently falls back to dev-bootstrap-token
# when any VITE_COGNITO_* value is missing. That fallback is correct for
# a demo build, but surprising if someone intends to enable Cognito.
# This preflight fails loud if the env is partially configured.
#
# Usage:
#   ./scripts/cognito-preflight.sh                    # read frontend/.env.production
#   ./scripts/cognito-preflight.sh frontend/.env      # alternate env file
#   ./scripts/cognito-preflight.sh --skip-jwks        # skip the HTTP probe
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

ENV_FILE="frontend/.env.production"
SKIP_JWKS=false
for arg in "$@"; do
  case "$arg" in
    --skip-jwks) SKIP_JWKS=true ;;
    -h|--help)   sed -n '2,15p' "$0"; exit 0 ;;
    *) ENV_FILE="$arg" ;;
  esac
done

log()  { printf "\033[1;34m[cognito-preflight]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[cognito-preflight WARN]\033[0m %s\n" "$*" >&2; }
fatal(){ printf "\033[1;31m[cognito-preflight FATAL]\033[0m %s\n" "$*" >&2; exit 1; }

REQUIRED=(VITE_COGNITO_REGION VITE_COGNITO_USER_POOL_ID VITE_COGNITO_CLIENT_ID VITE_COGNITO_DOMAIN)

if [[ ! -f "$ENV_FILE" ]]; then
  log "No env file at $ENV_FILE"
  log "v3 frontend will use dev-bootstrap-token fallback. That's fine for demos."
  log "To enable Cognito, follow docs/v3-cognito-setup.md Step 1-3 then re-run."
  exit 0
fi

log "Validating Cognito env in $ENV_FILE..."

any_set=false
all_set=true
for var in "${REQUIRED[@]}"; do
  if grep -qE "^${var}=.+" "$ENV_FILE" 2>/dev/null; then
    val="$(grep -E "^${var}=" "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"'"'" | head -c 40)"
    any_set=true
    log "  ✓ ${var} = ${val}..."
  else
    all_set=false
    log "  ✗ ${var} missing"
  fi
done

if ! $any_set; then
  log "No VITE_COGNITO_* vars set. SPA uses dev-bootstrap-token fallback."
  exit 0
fi

if ! $all_set; then
  fatal "Partial Cognito config: some VITE_COGNITO_* vars are set but not all. SPA will crash at login. Populate all 4 or remove them all."
fi

# ---------------------------------------------------------------------------
# Live JWKS probe — proves the User Pool + region are correct.
# ---------------------------------------------------------------------------
if $SKIP_JWKS; then
  log "Skipping JWKS probe (--skip-jwks)."
  exit 0
fi

REGION="$(grep -E '^VITE_COGNITO_REGION=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"'"'"  )"
POOL="$(grep -E '^VITE_COGNITO_USER_POOL_ID=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"'"'")"

JWKS_URL="https://cognito-idp.${REGION}.amazonaws.com/${POOL}/.well-known/jwks.json"
log "Probing JWKS: $JWKS_URL"

http_code="$(curl -s -o /tmp/cognito-jwks.json -w '%{http_code}' --max-time 10 "$JWKS_URL" || echo '000')"
if [[ "$http_code" != "200" ]]; then
  fatal "JWKS probe HTTP $http_code — check VITE_COGNITO_REGION + VITE_COGNITO_USER_POOL_ID"
fi

key_count="$(jq -r '.keys | length' /tmp/cognito-jwks.json 2>/dev/null || echo 0)"
if [[ "$key_count" -lt 1 ]]; then
  fatal "JWKS returned no keys — pool may not be configured"
fi

log "JWKS OK — $key_count signing key(s) published."
log ""
log "Next steps:"
log "  1. npm --prefix frontend run build"
log "  2. bash scripts/deploy-frontend-cloudfront.sh"
log "  3. (optional) docs/v3-cognito-setup.md Step 4 to wire JWKS verify"
log "     into the agent-proxy Lambda."
