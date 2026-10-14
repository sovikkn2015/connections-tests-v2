#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# register-api-and-policies.sh — Phase 2: register the MCP API + apply policies
#
# Once the Flex Gateway is running in ECS, this script:
#   1. Registers a Flex API instance named `fsi-mcp-servers` pointing at the V2
#      API Gateway endpoint (the upstream for the MCP servers).
#   2. Applies all 5 policy bindings from agent-fabric/policies/ to that API.
#
# OUTPUTS:
#   agent-fabric/.registered-apis.json  — API id + per-policy apply results
#
# The V2 upstream URL is read from the CloudFormation stack output
# `ApiGatewayUrl` (stack name configurable via V2_SAM_STACK, defaults to
# `ir-research-mcp`). Override with V2_API_GATEWAY_URL env var if needed.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/_common.sh"

trap 'error "register-api-and-policies.sh failed on line $LINENO"; exit 1' ERR

V2_SAM_STACK="${V2_SAM_STACK:-ir-research-mcp}"
API_INSTANCE_LABEL="${API_INSTANCE_LABEL:-fsi-mcp-servers}"
API_ASSET_ID="${API_ASSET_ID:-fsi-mcp-servers}"
API_ASSET_VERSION="${API_ASSET_VERSION:-1.0.0}"
POLICIES_DIR="${V3_AGENT_FABRIC_DIR}/policies"
OUTPUT_FILE="${V3_AGENT_FABRIC_DIR}/.registered-apis.json"

# Resolve the V2 API Gateway upstream URL (source of truth: V2 SAM stack)
resolve_upstream_url() {
    if [[ -n "${V2_API_GATEWAY_URL:-}" ]]; then
        info "Using V2_API_GATEWAY_URL from env: $V2_API_GATEWAY_URL"
        return
    fi
    info "Resolving V2 upstream from CloudFormation stack: $V2_SAM_STACK"
    V2_API_GATEWAY_URL="$(aws cloudformation describe-stacks \
        --region "$AWS_REGION" \
        --stack-name "$V2_SAM_STACK" \
        --query "Stacks[0].Outputs[?OutputKey=='ApiGatewayUrl'].OutputValue" \
        --output text 2>/dev/null)" \
        || die "Failed to describe stack $V2_SAM_STACK"
    [[ -n "$V2_API_GATEWAY_URL" && "$V2_API_GATEWAY_URL" != "None" ]] \
        || die "Stack $V2_SAM_STACK has no ApiGatewayUrl output"
    export V2_API_GATEWAY_URL
    info "Upstream: $V2_API_GATEWAY_URL"
}

# REST fallback: create a non-Exchange-backed API instance. Used when the
# CLI requires an Exchange asset that doesn't exist yet.
# The Anypoint API-Mgr REST endpoint accepts a minimal body with a
# `technology:flexGateway` marker so the instance binds to a Flex runtime.
#   $1 scheme, $2 host, $3 port, $4 path
rest_register_api() {
    local scheme="$1" host="$2" port="$3" path="$4"
    info "REST fallback: creating API instance via api-mgr REST API"
    local token
    token="$(anypoint_bearer_token)"
    local api_base
    api_base="https://anypoint.mulesoft.com/apimanager/api/v1/organizations/${ANYPOINT_ORG_ID}/environments/${ANYPOINT_ENV_ID}/apis"

    local body
    body="$(python3 -c "
import json
print(json.dumps({
  'instanceLabel': '$API_INSTANCE_LABEL',
  'technology':   'flexGateway',
  'endpoint': {
    'type': 'http',
    'deploymentType': 'HY',
    'uri':  '$V2_API_GATEWAY_URL',
    'proxyUri': None,
    'muleVersion4OrAbove': None,
    'isCloudHub': None,
  },
  'spec': {
    'assetId':   '$API_ASSET_ID',
    'version':   '$API_ASSET_VERSION',
    'groupId':   '$ANYPOINT_ORG_ID',
  }
}))
")"

    local resp_file http_code
    resp_file="$(mktemp)"
    http_code="$(curl -sS -X POST "$api_base" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json" \
        -d "$body" \
        -o "$resp_file" \
        -w "%{http_code}")"
    local resp
    resp="$(cat "$resp_file")"
    rm -f "$resp_file"

    if [[ ! "$http_code" =~ ^2 ]]; then
        error "REST API instance create returned HTTP $http_code"
        error "$resp"
        MANUAL_STEP_REQUIRED=1; warn "REST fallback failed — API instance requires a pre-published Exchange asset."; warn "See docs/v3-gateway-runbook.md FAQ 6.6 for manual step."; return 1
    fi

    API_INSTANCE_ID="$(printf '%s' "$resp" | python3 -c "
import json, sys
d = json.loads(sys.stdin.read())
print(d.get('id') or d.get('Id') or '')
")"
    [[ -n "$API_INSTANCE_ID" ]] || die "REST create returned no id"
    info "REST API instance registered: id=$API_INSTANCE_ID (HTTP $http_code)"
    export API_INSTANCE_ID
}

# Register the API instance in API Manager via anypoint-cli-v4.
# We use the `api-mgr api manage` subcommand with --isFlex so the instance is
# bound to the Flex Gateway runtime (not Mule/CloudHub).
register_api() {
    info "── Registering API instance: $API_INSTANCE_LABEL ──"

    # Parse upstream URL components
    local scheme host port path
    scheme="$(printf '%s' "$V2_API_GATEWAY_URL" | python3 -c "import sys,urllib.parse as u;p=u.urlparse(sys.stdin.read().strip());print(p.scheme)")"
    host="$(printf '%s'   "$V2_API_GATEWAY_URL" | python3 -c "import sys,urllib.parse as u;p=u.urlparse(sys.stdin.read().strip());print(p.hostname)")"
    port="$(printf '%s'   "$V2_API_GATEWAY_URL" | python3 -c "import sys,urllib.parse as u;p=u.urlparse(sys.stdin.read().strip());print(p.port or (443 if p.scheme=='https' else 80))")"
    path="$(printf '%s'   "$V2_API_GATEWAY_URL" | python3 -c "import sys,urllib.parse as u;p=u.urlparse(sys.stdin.read().strip());print(p.path or '/')")"

    info "Upstream parsed: scheme=$scheme host=$host port=$port path=$path"

    # If an instance with the same label already exists, reuse its id.
    local existing_list existing_id
    existing_list="$(anypoint-cli-v4 api-mgr api list \
        --client_id "$ANYPOINT_CLIENT_ID" \
        --client_secret "$ANYPOINT_CLIENT_SECRET" \
        --organization "${ANYPOINT_ORG_NAME:-$ANYPOINT_ORG_ID}" \
        --environment "${ANYPOINT_ENV_NAME:-$ANYPOINT_ENV_ID}" \
        --output json 2>/dev/null || echo '[]')"

    existing_id="$(printf '%s' "$existing_list" | python3 -c "
import json, sys
try:
    data = json.loads(sys.stdin.read())
except Exception:
    print(''); sys.exit(0)
items = data if isinstance(data, list) else data.get('items', [])
for it in items:
    label = it.get('InstanceLabel') or it.get('instanceLabel') or it.get('Instance Label','')
    asset = it.get('AssetId')      or it.get('assetId')      or it.get('Asset Id','')
    if str(label) == '$API_INSTANCE_LABEL' or str(asset) == '$API_ASSET_ID':
        print(it.get('Id') or it.get('id') or it.get('ID',''))
        sys.exit(0)
print('')
" 2>/dev/null || echo "")"

    if [[ -n "$existing_id" ]]; then
        info "API instance already registered: id=$existing_id — reusing"
        API_INSTANCE_ID="$existing_id"
    else
        info "Creating new Flex API instance"
        local create_out
        create_out="$(anypoint-cli-v4 api-mgr api manage \
            "$API_ASSET_ID" "$API_ASSET_VERSION" \
            --client_id "$ANYPOINT_CLIENT_ID" \
            --client_secret "$ANYPOINT_CLIENT_SECRET" \
            --organization "${ANYPOINT_ORG_NAME:-$ANYPOINT_ORG_ID}" \
            --environment "${ANYPOINT_ENV_NAME:-$ANYPOINT_ENV_ID}" \
            --isFlex \
            --type http \
            --uri "$V2_API_GATEWAY_URL" \
            --scheme "$scheme" \
            --port "$port" \
            --path "$path" \
            --apiInstanceLabel "$API_INSTANCE_LABEL" \
            --output json 2>&1)" || {
                warn "api-mgr api manage failed — falling back to REST API:"
                warn "$create_out"
                rest_register_api "$scheme" "$host" "$port" "$path" || return 1
                return 0
            }
        API_INSTANCE_ID="$(printf '%s' "$create_out" | python3 -c "
import json, sys, re
raw = sys.stdin.read()
m = re.search(r'[\\[\\{]', raw)
if not m: sys.exit('no json')
obj,_ = json.JSONDecoder().raw_decode(raw[m.start():])
if isinstance(obj, list): obj = obj[0] if obj else {}
print(obj.get('Id') or obj.get('id') or obj.get('ID',''))
")"
        [[ -n "$API_INSTANCE_ID" ]] || die "Could not parse API instance id from create response"
        info "API instance registered: id=$API_INSTANCE_ID"
    fi
    export API_INSTANCE_ID
}

# Apply a single policy from its YAML binding file.
#   $1 = path to policy YAML
# Emits one-line JSON on stdout: {name, policyRef, status, ...}
apply_policy() {
    local policy_file="$1"
    local policy_binding_name policy_ref policy_config_json
    policy_binding_name="$(python3 -c "
import yaml
with open('$policy_file') as f:
    d = yaml.safe_load(f)
print(d['metadata']['name'])
")"
    policy_ref="$(python3 -c "
import yaml
with open('$policy_file') as f:
    d = yaml.safe_load(f)
print(d['spec']['policyRef']['name'])
")"
    policy_config_json="$(python3 -c "
import yaml, json
with open('$policy_file') as f:
    d = yaml.safe_load(f)
print(json.dumps(d.get('spec',{}).get('config',{}) or {}))
")"

    info "  → Applying policy: $policy_binding_name (policyRef=$policy_ref)"

    # Map symbolic policyRef names to the Anypoint marketplace asset id/version.
    # Anypoint publishes policies with standardised asset ids; we pin the
    # versions here and let unknown ones fall through as the ref name.
    local asset_id asset_version
    case "$policy_ref" in
        rate-limiting)         asset_id="rate-limiting";         asset_version="1.4.0" ;;
        client-id-enforcement) asset_id="client-id-enforcement"; asset_version="1.3.0" ;;
        message-logging)       asset_id="message-logging";       asset_version="2.0.3" ;;
        tls-inbound)           asset_id="tls";                   asset_version="1.3.0" ;;
        circuit-breaker)       asset_id="circuit-breaker";       asset_version="1.0.1" ;;
        content-filter)        asset_id="message-logging";       asset_version="2.0.3" ;; # MNPI logger
        *)                     asset_id="$policy_ref";           asset_version="1.0.0" ;;
    esac

    local cfg_file apply_out apply_exit=0
    cfg_file="$(mktemp)"
    printf '%s' "$policy_config_json" > "$cfg_file"

    apply_out="$(anypoint-cli-v4 api-mgr policy apply \
        "$API_INSTANCE_ID" "$asset_id" \
        --policyVersion "$asset_version" \
        --configFile "$cfg_file" \
        --label "$policy_binding_name" \
        --allowDuplicated \
        --client_id "$ANYPOINT_CLIENT_ID" \
        --client_secret "$ANYPOINT_CLIENT_SECRET" \
        --organization "${ANYPOINT_ORG_NAME:-$ANYPOINT_ORG_ID}" \
        --environment "${ANYPOINT_ENV_NAME:-$ANYPOINT_ENV_ID}" \
        --output json 2>&1)" || apply_exit=$?
    rm -f "$cfg_file"

    if [[ $apply_exit -eq 0 ]]; then
        info "    ✓ applied"
        printf '{"name":"%s","policyRef":"%s","assetId":"%s","assetVersion":"%s","status":"applied","raw":%s}\n' \
            "$policy_binding_name" "$policy_ref" "$asset_id" "$asset_version" \
            "$(printf '%s' "$apply_out" | python3 -c "
import json, sys, re
raw = sys.stdin.read()
m = re.search(r'[\\[\\{]', raw)
print(json.dumps(json.JSONDecoder().raw_decode(raw[m.start():])[0]) if m else 'null')
" 2>/dev/null || echo 'null')"
    else
        warn "    ✗ failed (exit $apply_exit)"
        warn "      $apply_out"
        printf '{"name":"%s","policyRef":"%s","assetId":"%s","assetVersion":"%s","status":"failed","error":%s}\n' \
            "$policy_binding_name" "$policy_ref" "$asset_id" "$asset_version" \
            "$(printf '%s' "$apply_out" | python3 -c "import json,sys;print(json.dumps(sys.stdin.read()))")"
    fi
}

apply_all_policies() {
    info "── Applying policies from $POLICIES_DIR ──"
    [[ -d "$POLICIES_DIR" ]] || die "Policies directory missing: $POLICIES_DIR"

    local results="["
    local first=1
    for f in "$POLICIES_DIR"/*.yaml; do
        [[ -f "$f" ]] || continue
        [[ $first -eq 1 ]] || results+=","
        first=0
        results+="$(apply_policy "$f")"
    done
    results+="]"
    export POLICY_RESULTS_JSON="$results"
}

write_receipt() {
    python3 - "$OUTPUT_FILE" "$API_INSTANCE_ID" "$API_INSTANCE_LABEL" \
        "$V2_API_GATEWAY_URL" "$POLICY_RESULTS_JSON" <<'PYEOF'
import json, sys, datetime
out_path, api_id, api_label, upstream, results_json = sys.argv[1:6]
receipt = {
    "timestamp":            datetime.datetime.utcnow().isoformat() + "Z",
    "api_instance_id":      api_id,
    "api_instance_label":   api_label,
    "upstream_url":         upstream,
    "policies":             json.loads(results_json),
    "policies_applied":     sum(1 for p in json.loads(results_json) if p.get("status") == "applied"),
    "policies_failed":      sum(1 for p in json.loads(results_json) if p.get("status") == "failed"),
}
with open(out_path, "w") as f:
    json.dump(receipt, f, indent=2)
PYEOF
    info "Wrote registration receipt → $OUTPUT_FILE"
}

main() {
    info "── Register API + apply policies ──"
    require_cli
    load_mulesoft_secret
    resolve_upstream_url

    MANUAL_STEP_REQUIRED=0
    API_INSTANCE_ID=""
    POLICY_RESULTS_JSON="[]"

    if register_api; then
        apply_all_policies
    else
        warn "API instance registration failed — skipping policy apply."
        warn "Policies will auto-apply on next run once the Exchange asset exists."
    fi

    write_receipt
    if [[ "$MANUAL_STEP_REQUIRED" == "1" ]]; then
        warn "── Registration partial (manual step required) ──"
        exit 3
    fi
    info "── Registration complete ──"
}

main "$@"
