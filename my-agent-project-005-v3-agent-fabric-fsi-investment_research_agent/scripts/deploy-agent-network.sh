#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy-agent-network.sh — Phase 3: push agent-network.yaml to Agent Registry
#
# Deploys agent-fabric/agent-network.yaml to Anypoint Agent Fabric via:
#   1. `anypoint-cli-v4 agent-fabric registry apply -f` (preferred)
#   2. Fallback: Anypoint Platform REST API with client-credentials OAuth
#      (POST https://anypoint.mulesoft.com/accounts/api/v2/oauth2/token).
#
# OUTPUTS:
#   agent-fabric/.registered-agents.json — registration receipts
#
# ENTITLEMENT GATE: this step is gated on agent_fabric=true in
# .entitlement-check.json. If the entitlement check says otherwise we SKIP
# with a receipt documenting the B-fallback path.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/_common.sh"

trap 'error "deploy-agent-network.sh failed on line $LINENO"; exit 1' ERR

NETWORK_FILE="${NETWORK_FILE:-${V3_AGENT_FABRIC_DIR}/agent-network.yaml}"
OUTPUT_FILE="${V3_AGENT_FABRIC_DIR}/.registered-agents.json"
ANYPOINT_HOST="${ANYPOINT_HOST:-https://anypoint.mulesoft.com}"

write_skip_receipt() {
    local reason="$1"
    python3 - "$OUTPUT_FILE" "$reason" <<'PYEOF'
import json, sys, datetime
out, reason = sys.argv[1:3]
payload = {
    "timestamp":    datetime.datetime.utcnow().isoformat() + "Z",
    "status":       "skipped",
    "path":         "B-fallback",
    "reason":       reason,
    "agents":       [],
    "mcp_servers":  [],
    "routing":      [],
}
with open(out, "w") as f:
    json.dump(payload, f, indent=2)
PYEOF
    info "Wrote skip receipt → $OUTPUT_FILE"
}

entitlement_gate() {
    local entitle_file="${V3_AGENT_FABRIC_DIR}/.entitlement-check.json"
    if [[ ! -f "$entitle_file" ]]; then
        die "Entitlement check required. Run verify-entitlement.sh first."
    fi
    local agent_fabric_ok
    agent_fabric_ok="$(python3 -c "import json;print(json.load(open('$entitle_file'))['agent_fabric'])")"
    if [[ "$agent_fabric_ok" != "True" ]]; then
        warn "Agent Fabric NOT entitled — skipping agent-network push (B-fallback path)"
        write_skip_receipt "Agent Fabric not in org entitlement (subscription category: Developer/Trial)"
        exit 0
    fi
    info "Entitlement gate passed (agent_fabric=true)"
}

# Try CLI first. The CLI version 1.6.14 does not ship the `agent-fabric`
# subcommand so the CLI path will miss — caught by the fallback.
try_cli_push() {
    require_cli
    if anypoint-cli-v4 --help 2>&1 | grep -qE '^\s*agent-fabric\b'; then
        info "CLI supports agent-fabric subcommand — using it"
        local tmp_apply
        tmp_apply="$(mktemp)"
        anypoint-cli-v4 agent-fabric registry apply \
            -f "$NETWORK_FILE" \
            --client_id "$ANYPOINT_CLIENT_ID" \
            --client_secret "$ANYPOINT_CLIENT_SECRET" \
            --organization "${ANYPOINT_ORG_NAME:-$ANYPOINT_ORG_ID}" \
            --environment "${ANYPOINT_ENV_NAME:-$ANYPOINT_ENV_ID}" \
            --output json > "$tmp_apply" \
            || { rm -f "$tmp_apply"; die "CLI agent-fabric registry apply failed"; }
        USED_PATH="cli"
        RAW_RESPONSE="$(cat "$tmp_apply")"
        rm -f "$tmp_apply"
        return 0
    fi
    info "CLI version $ANYPOINT_CLI_VERSION has no 'agent-fabric' subcommand — falling back to REST"
    return 1
}

# REST fallback. Agent Fabric Registry REST API:
#   POST   /agent-fabric/api/v1/organizations/{org}/environments/{env}/agent-networks
#   PUT    /agent-fabric/api/v1/organizations/{org}/environments/{env}/agent-networks/{name}
rest_push() {
    info "Obtaining OAuth2 bearer token"
    local token
    token="$(anypoint_bearer_token)"

    local network_name
    network_name="$(python3 -c "
import yaml
with open('$NETWORK_FILE') as f:
    d = yaml.safe_load(f)
print(d['metadata']['name'])
")"
    info "Network name: $network_name"

    local payload_file
    payload_file="$(mktemp)"
    python3 -c "
import yaml, json
with open('$NETWORK_FILE') as f:
    d = yaml.safe_load(f)
with open('$payload_file','w') as f:
    json.dump(d, f)
"

    local api_base
    api_base="${ANYPOINT_HOST}/agent-fabric/api/v1/organizations/${ANYPOINT_ORG_ID}/environments/${ANYPOINT_ENV_ID}"

    # Probe for existing network
    local probe_code
    probe_code="$(curl -sS -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $token" \
        "${api_base}/agent-networks/${network_name}")"

    local method path
    if [[ "$probe_code" == "200" ]]; then
        info "Existing network — PUT update"
        method="PUT"; path="/agent-networks/${network_name}"
    else
        info "New network — POST create (probe=$probe_code)"
        method="POST"; path="/agent-networks"
    fi

    local resp_file http_code
    resp_file="$(mktemp)"
    http_code="$(curl -sS -X "$method" "${api_base}${path}" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json" \
        --data "@${payload_file}" \
        -o "$resp_file" \
        -w "%{http_code}")"
    rm -f "$payload_file"

    RAW_RESPONSE="$(cat "$resp_file")"
    rm -f "$resp_file"
    USED_PATH="rest"

    if [[ ! "$http_code" =~ ^2 ]]; then
        error "REST $method $path returned HTTP $http_code"
        error "$RAW_RESPONSE"
        die "REST push failed"
    fi
    info "REST push succeeded (HTTP $http_code)"
}

write_receipt() {
    python3 - "$OUTPUT_FILE" "$USED_PATH" "$RAW_RESPONSE" "$NETWORK_FILE" <<'PYEOF'
import json, sys, datetime, yaml
out_path, used_path, raw_resp, network_file = sys.argv[1:5]
with open(network_file) as f:
    net = yaml.safe_load(f)
agents = [a.get("id") for a in net.get("agents", [])]
mcp    = [m.get("id") for m in net.get("mcpServers", [])]
routing = [p.get("name") for p in net.get("routing", {}).get("policies", [])]
try:
    parsed = json.loads(raw_resp)
except Exception:
    parsed = raw_resp
payload = {
    "timestamp":     datetime.datetime.utcnow().isoformat() + "Z",
    "status":        "registered",
    "path":          used_path,       # cli | rest
    "network_name":  net["metadata"]["name"],
    "agents":        agents,
    "mcp_servers":   mcp,
    "routing":       routing,
    "raw_response":  parsed,
}
with open(out_path, "w") as f:
    json.dump(payload, f, indent=2)
PYEOF
    info "Wrote registration receipt → $OUTPUT_FILE"
}

main() {
    info "── Agent Network deploy starting ──"
    [[ -f "$NETWORK_FILE" ]] || die "Network file missing: $NETWORK_FILE"

    load_mulesoft_secret
    entitlement_gate          # may exit 0 via write_skip_receipt

    try_cli_push || rest_push
    write_receipt
    info "── Agent Network deploy complete (via $USED_PATH) ──"
}

main "$@"
