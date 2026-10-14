#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# _common.sh — shared helpers for 005 V3 Agent Fabric scripts
#
# Sourced (not executed) from every top-level script. Provides:
#   • Timestamped stderr logging (info/warn/error/die)
#   • load_mulesoft_secret — pulls /006-v2/mulesoft/credentials from Secrets Manager
#   • require_cli — fail-fast if anypoint-cli-v4 is missing or version can't be read
#   • anypoint_bearer_token — OAuth2 client-credentials token for REST fallback
# ─────────────────────────────────────────────────────────────────────────────

# Guard against double-sourcing
if [[ -n "${_V3_COMMON_SOURCED:-}" ]]; then return 0; fi
_V3_COMMON_SOURCED=1

# ── Logging ─────────────────────────────────────────────────────────────────
_ts()   { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
info()  { printf "[INFO  %s] %s\n" "$(_ts)" "$*" >&2; }
warn()  { printf "[WARN  %s] %s\n" "$(_ts)" "$*" >&2; }
error() { printf "[ERROR %s] %s\n" "$(_ts)" "$*" >&2; }
die()   { error "$*"; exit 1; }

# ── Paths ───────────────────────────────────────────────────────────────────
# This file lives at <project>/scripts/lib/_common.sh
_this_file="${BASH_SOURCE[0]}"
V3_PROJECT_ROOT="$(cd "$(dirname "$_this_file")/../.." && pwd)"
export V3_PROJECT_ROOT
export V3_AGENT_FABRIC_DIR="${V3_PROJECT_ROOT}/agent-fabric"
export V3_RECEIPTS_DIR="${V3_AGENT_FABRIC_DIR}/.build-receipts"
mkdir -p "$V3_RECEIPTS_DIR"

# ── AWS / MuleSoft config ───────────────────────────────────────────────────
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-875460787302}"
export MULESOFT_SECRET_ID="${MULESOFT_SECRET_ID:-/006-v2/mulesoft/credentials}"

# Load MuleSoft credentials from Secrets Manager into env vars:
#   ANYPOINT_CLIENT_ID, ANYPOINT_CLIENT_SECRET, ANYPOINT_BASE_URL,
#   ANYPOINT_ORG_ID, ANYPOINT_ENV_ID
load_mulesoft_secret() {
    info "Loading MuleSoft credentials from Secrets Manager (${MULESOFT_SECRET_ID})"
    local raw
    raw="$(aws secretsmanager get-secret-value \
        --secret-id "$MULESOFT_SECRET_ID" \
        --region "$AWS_REGION" \
        --query SecretString --output text 2>/dev/null)" \
        || die "Failed to read $MULESOFT_SECRET_ID from Secrets Manager"

    ANYPOINT_CLIENT_ID="$(printf '%s' "$raw"     | python3 -c "import json,sys;print(json.load(sys.stdin)['client_id'])")"
    ANYPOINT_CLIENT_SECRET="$(printf '%s' "$raw" | python3 -c "import json,sys;print(json.load(sys.stdin)['client_secret'])")"
    ANYPOINT_BASE_URL="$(printf '%s' "$raw"      | python3 -c "import json,sys;print(json.load(sys.stdin)['base_url'])")"
    ANYPOINT_ORG_ID="$(printf '%s' "$raw"        | python3 -c "import json,sys;print(json.load(sys.stdin)['organization_id'])")"
    ANYPOINT_ENV_ID="$(printf '%s' "$raw"        | python3 -c "import json,sys;print(json.load(sys.stdin)['environment_id'])")"
    export ANYPOINT_CLIENT_ID ANYPOINT_CLIENT_SECRET ANYPOINT_BASE_URL \
           ANYPOINT_ORG_ID ANYPOINT_ENV_ID

    [[ -n "$ANYPOINT_CLIENT_ID" && -n "$ANYPOINT_CLIENT_SECRET" ]] \
        || die "Secret loaded but client_id/client_secret are empty"

    # Resolve the human-readable org + env names (the CLI needs these for
    # api-mgr subcommands — it rejects UUIDs on some flags). We cache them
    # alongside the IDs so each caller can pick whichever form is accepted.
    _resolve_org_env_names

    info "MuleSoft secret loaded (org=${ANYPOINT_ORG_NAME:-$ANYPOINT_ORG_ID} env=${ANYPOINT_ENV_NAME:-$ANYPOINT_ENV_ID})"
}

# Populate ANYPOINT_ORG_NAME and ANYPOINT_ENV_NAME by calling the Anypoint
# REST API directly (avoids a second CLI invocation).
_resolve_org_env_names() {
    local host="${ANYPOINT_HOST:-https://anypoint.mulesoft.com}"
    local token resp
    token="$(anypoint_bearer_token 2>/dev/null || true)"
    if [[ -z "$token" ]]; then
        warn "Could not obtain OAuth token for name resolution — names will be empty"
        export ANYPOINT_ORG_NAME="" ANYPOINT_ENV_NAME=""
        return
    fi
    resp="$(curl -sS -H "Authorization: Bearer $token" \
        "${host}/accounts/api/organizations/${ANYPOINT_ORG_ID}" 2>/dev/null || true)"
    if [[ -z "$resp" ]]; then
        export ANYPOINT_ORG_NAME="" ANYPOINT_ENV_NAME=""
        return
    fi
    ANYPOINT_ORG_NAME="$(printf '%s' "$resp" | python3 -c "
import json,sys
try:
    d = json.load(sys.stdin)
    print(d.get('name',''))
except Exception:
    print('')
")"
    ANYPOINT_ENV_NAME="$(printf '%s' "$resp" | python3 -c "
import json,sys,os
env_id = os.environ['ANYPOINT_ENV_ID']
try:
    d = json.load(sys.stdin)
    for e in d.get('environments', []):
        if e.get('id') == env_id:
            print(e.get('name',''))
            break
    else:
        print('')
except Exception:
    print('')
")"
    export ANYPOINT_ORG_NAME ANYPOINT_ENV_NAME
}

# Fail-fast if anypoint-cli-v4 isn't available.
require_cli() {
    command -v anypoint-cli-v4 >/dev/null 2>&1 \
        || die "anypoint-cli-v4 not on PATH. Install with: npm install -g anypoint-cli-v4"
    ANYPOINT_CLI_VERSION="$(anypoint-cli-v4 --version 2>/dev/null | head -1)"
    export ANYPOINT_CLI_VERSION
    [[ -n "$ANYPOINT_CLI_VERSION" ]] \
        || die "anypoint-cli-v4 installed but --version failed — toolchain broken"
    info "anypoint-cli-v4 version: $ANYPOINT_CLI_VERSION"
}

# Get an OAuth2 bearer token using client-credentials. Echoes token to stdout.
anypoint_bearer_token() {
    : "${ANYPOINT_CLIENT_ID:?call load_mulesoft_secret first}"
    : "${ANYPOINT_CLIENT_SECRET:?call load_mulesoft_secret first}"
    local host="${ANYPOINT_HOST:-https://anypoint.mulesoft.com}"
    local resp
    resp="$(curl -sS -X POST "${host}/accounts/api/v2/oauth2/token" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "grant_type=client_credentials" \
        -d "client_id=${ANYPOINT_CLIENT_ID}" \
        -d "client_secret=${ANYPOINT_CLIENT_SECRET}")" \
        || die "OAuth2 token request failed"
    local token
    token="$(printf '%s' "$resp" | python3 -c "import json,sys;print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null || true)"
    [[ -n "$token" ]] || die "No access_token in OAuth2 response: $resp"
    printf '%s' "$token"
}
