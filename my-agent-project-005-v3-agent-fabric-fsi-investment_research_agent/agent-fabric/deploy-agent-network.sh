#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy-agent-network.sh — Phase 2+4: Agent Registry + Broker Routing
#
# Deploys agent-fabric/agent-network.yaml to Anypoint Agent Fabric.
# Registers the 7 components (4 agents + 3 MCP servers) and applies the
# 3 routing policies (l1-l2-direct-tools, l3-l4-analysis, compliance-routing).
#
# REQUIRED ENV (injected by caller from AWS Secrets Manager):
#   ANYPOINT_ORG_ID           — MuleSoft org UUID
#   ANYPOINT_ENV_ID           — Target environment UUID
#   ANYPOINT_ACCESS_TOKEN     — Bearer token (or rely on `anypoint-cli-v4 conf`)
#
# OPTIONAL ENV:
#   ANYPOINT_HOST             — default https://anypoint.mulesoft.com
#   NETWORK_FILE              — default agent-fabric/agent-network.yaml
#   DRY_RUN                   — if set, validate only, do not deploy
#
# USAGE:
#   ./agent-fabric/deploy-agent-network.sh
#   DRY_RUN=1 ./agent-fabric/deploy-agent-network.sh
# ─────────────────────────────────────────────────────────────────────────────

set -Eeuo pipefail
IFS=$'\n\t'

# ── Logging helpers ──────────────────────────────────────────────────────────
_ts()   { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
info()  { printf "[INFO  %s] %s\n" "$(_ts)" "$*" >&2; }
warn()  { printf "[WARN  %s] %s\n" "$(_ts)" "$*" >&2; }
error() { printf "[ERROR %s] %s\n" "$(_ts)" "$*" >&2; }
die()   { error "$*"; exit 1; }

trap 'error "deploy failed on line $LINENO"; exit 1' ERR

# ── Config ───────────────────────────────────────────────────────────────────
ANYPOINT_HOST="${ANYPOINT_HOST:-https://anypoint.mulesoft.com}"
NETWORK_FILE="${NETWORK_FILE:-agent-fabric/agent-network.yaml}"
DRY_RUN="${DRY_RUN:-}"

: "${ANYPOINT_ORG_ID:?ANYPOINT_ORG_ID is required (inject from Secrets Manager)}"
: "${ANYPOINT_ENV_ID:?ANYPOINT_ENV_ID is required (inject from Secrets Manager)}"

[[ -f "$NETWORK_FILE" ]] || die "Network file not found: $NETWORK_FILE"

API_BASE="${ANYPOINT_HOST}/agent-fabric/api/v1/organizations/${ANYPOINT_ORG_ID}/environments/${ANYPOINT_ENV_ID}"

# ── Tool detection ───────────────────────────────────────────────────────────
have_cli=0
if command -v anypoint-cli-v4 >/dev/null 2>&1; then
    have_cli=1
    info "anypoint-cli-v4 detected: $(anypoint-cli-v4 --version 2>/dev/null || echo unknown)"
else
    warn "anypoint-cli-v4 not found on PATH — falling back to REST API"
fi

command -v curl >/dev/null 2>&1 || die "curl is required"
command -v jq   >/dev/null 2>&1 || die "jq is required"

# ── Auth token resolution ────────────────────────────────────────────────────
resolve_token() {
    if [[ -n "${ANYPOINT_ACCESS_TOKEN:-}" ]]; then
        echo "$ANYPOINT_ACCESS_TOKEN"
        return
    fi
    if [[ $have_cli -eq 1 ]]; then
        local tok
        tok="$(anypoint-cli-v4 account bearer-token 2>/dev/null || true)"
        if [[ -n "$tok" ]]; then
            echo "$tok"
            return
        fi
    fi
    die "No auth token. Set ANYPOINT_ACCESS_TOKEN or run 'anypoint-cli-v4 conf' first."
}

TOKEN="$(resolve_token)"

# ── Curl wrapper: fails on non-2xx ───────────────────────────────────────────
api_call() {
    local method="$1"
    local path="$2"
    local data="${3:-}"
    local url="${API_BASE}${path}"
    local tmp_body tmp_code
    tmp_body="$(mktemp)"
    tmp_code="$(mktemp)"

    if [[ -n "$data" ]]; then
        curl -sS -X "$method" "$url" \
            -H "Authorization: Bearer ${TOKEN}" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json" \
            -d "$data" \
            -o "$tmp_body" \
            -w "%{http_code}" > "$tmp_code" || true
    else
        curl -sS -X "$method" "$url" \
            -H "Authorization: Bearer ${TOKEN}" \
            -H "Accept: application/json" \
            -o "$tmp_body" \
            -w "%{http_code}" > "$tmp_code" || true
    fi

    local code body
    code="$(cat "$tmp_code")"
    body="$(cat "$tmp_body")"
    rm -f "$tmp_code" "$tmp_body"

    if [[ ! "$code" =~ ^2 ]]; then
        error "API $method $path returned HTTP $code"
        error "Body: $body"
        return 1
    fi
    printf "%s" "$body"
}

# ── YAML → JSON helper ───────────────────────────────────────────────────────
yaml_to_json() {
    local f="$1"
    if command -v yq >/dev/null 2>&1; then
        yq eval -o=json '.' "$f"
    elif command -v python3 >/dev/null 2>&1; then
        python3 -c "import sys,yaml,json; print(json.dumps(yaml.safe_load(open('$f'))))"
    else
        die "Need yq or python3 to convert YAML → JSON"
    fi
}

# ── Step 1: Validate ─────────────────────────────────────────────────────────
validate_network() {
    info "Validating $NETWORK_FILE …"

    if command -v yq >/dev/null 2>&1; then
        yq eval '.' "$NETWORK_FILE" > /dev/null \
            || die "YAML parse failed for $NETWORK_FILE"
    fi

    if [[ $have_cli -eq 1 ]]; then
        if anypoint-cli-v4 agent-fabric validate --help >/dev/null 2>&1; then
            anypoint-cli-v4 agent-fabric validate --file "$NETWORK_FILE" \
                || die "anypoint-cli-v4 validation failed"
            info "CLI validation passed"
            return 0
        else
            warn "anypoint-cli-v4 agent-fabric validate subcommand unavailable — using REST"
        fi
    fi

    local payload
    payload="$(yaml_to_json "$NETWORK_FILE")"
    api_call POST "/agent-networks/validate" "$payload" > /dev/null \
        || die "REST validation failed"
    info "REST validation passed"
}

# ── Step 2: Deploy (idempotent upsert) ───────────────────────────────────────
deploy_network() {
    local network_name
    network_name="$(yq eval '.metadata.name' "$NETWORK_FILE" 2>/dev/null \
        || python3 -c "import yaml; print(yaml.safe_load(open('$NETWORK_FILE'))['metadata']['name'])")"
    info "Deploying agent network: $network_name"

    if [[ -n "$DRY_RUN" ]]; then
        info "DRY_RUN set — skipping deploy"
        return 0
    fi

    if [[ $have_cli -eq 1 ]] && anypoint-cli-v4 agent-fabric deploy --help >/dev/null 2>&1; then
        anypoint-cli-v4 agent-fabric deploy \
            --file "$NETWORK_FILE" \
            --organization "$ANYPOINT_ORG_ID" \
            --environment  "$ANYPOINT_ENV_ID" \
            || die "CLI deploy failed"
        info "CLI deploy succeeded"
        return 0
    fi

    local payload
    payload="$(yaml_to_json "$NETWORK_FILE")"

    info "Checking if network '$network_name' already exists …"
    local existing_code
    existing_code="$(curl -sS -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer ${TOKEN}" \
        "${API_BASE}/agent-networks/${network_name}")"

    if [[ "$existing_code" == "200" ]]; then
        info "Network exists — updating (PUT)"
        api_call PUT "/agent-networks/${network_name}" "$payload" > /dev/null \
            || die "PUT failed"
    elif [[ "$existing_code" == "404" ]]; then
        info "Network does not exist — creating (POST)"
        api_call POST "/agent-networks" "$payload" > /dev/null \
            || die "POST failed"
    else
        die "Unexpected status $existing_code checking existing network"
    fi
    info "Deploy succeeded"
}

# ── Step 3: Verify registry ──────────────────────────────────────────────────
verify_registry() {
    info "Verifying registry — expecting 7 components (4 agents + 3 MCP servers)"

    local json
    if [[ $have_cli -eq 1 ]] && anypoint-cli-v4 agent-fabric registry list --help >/dev/null 2>&1; then
        json="$(anypoint-cli-v4 agent-fabric registry list --output json \
            --organization "$ANYPOINT_ORG_ID" \
            --environment  "$ANYPOINT_ENV_ID")" \
            || die "registry list failed"
    else
        json="$(api_call GET "/registry?type=all")" \
            || die "REST registry list failed"
    fi

    local count
    count="$(echo "$json" | jq 'if type=="array" then length else (.items // []) | length end')"
    info "Registry returned $count items"

    if [[ "$count" != "7" ]]; then
        warn "Expected 7 components, got $count"
        echo "$json" | jq .
        die "Registry verification failed"
    fi

    local expected=( ir-research-orchestrator ir-compliance-agent \
                     financial-analysis-agent sentiment-analysis-agent \
                     sec-edgar market-data news-search )
    for id in "${expected[@]}"; do
        if ! echo "$json" | jq -e --arg id "$id" \
            '(.items // .)[] | select(.id == $id)' > /dev/null; then
            die "Missing registry entry: $id"
        fi
        info "  ✓ $id"
    done
    info "Registry verification passed (7/7)"
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
    info "── Agent Fabric deploy starting ──"
    info "Org: $ANYPOINT_ORG_ID   Env: $ANYPOINT_ENV_ID"
    info "File: $NETWORK_FILE"

    validate_network
    deploy_network
    [[ -z "$DRY_RUN" ]] && verify_registry

    info "── Deploy complete ──"
}

main "$@"
