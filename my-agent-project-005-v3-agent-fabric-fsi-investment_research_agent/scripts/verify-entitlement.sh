#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# verify-entitlement.sh — Phase 0 gate for 005 V3 Agent Fabric
#
# Pulls MuleSoft client-credentials from AWS Secrets Manager, authenticates
# against Anypoint Platform, calls `account business-group describe`, and
# determines whether Agent Fabric + Flex Gateway are in the org's entitlement.
#
# OUTPUTS:
#   agent-fabric/.entitlement-check.json — pass/fail + raw Anypoint response
#
# EXIT CODES:
#   0  — Agent Fabric + Flex Gateway both entitled (full V3 path)
#   2  — Agent Fabric NOT entitled (caller should degrade to B scope)
#   1  — Any other failure (auth, network, CLI missing, etc.)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/_common.sh"

trap 'error "verify-entitlement.sh failed on line $LINENO"; exit 1' ERR

OUTPUT_FILE="${V3_AGENT_FABRIC_DIR}/.entitlement-check.json"

# REST fallback when the CLI is unavailable or returns non-JSON.
rest_describe_business_group() {
    info "REST fallback: fetching business-group via Anypoint REST API"
    local token host resp
    token="$(anypoint_bearer_token)"
    host="${ANYPOINT_HOST:-https://anypoint.mulesoft.com}"
    resp="$(curl -sS \
        -H "Authorization: Bearer $token" \
        -H "Accept: application/json" \
        "${host}/accounts/api/organizations/${ANYPOINT_ORG_ID}")" \
        || die "REST describe failed"
    printf '%s' "$resp"
}

main() {
    info "── Entitlement check starting ──"

    require_cli
    load_mulesoft_secret

    # The CLI accepts --client_id / --client_secret flags directly so we do
    # not need to persist anything to ~/.anypoint-cli-v4/config.json.
    info "Calling anypoint-cli-v4 account business-group describe ..."
    local describe_raw=""
    local describe_exit=0
    describe_raw="$(anypoint-cli-v4 account business-group describe \
        --client_id "$ANYPOINT_CLIENT_ID" \
        --client_secret "$ANYPOINT_CLIENT_SECRET" \
        --output json 2>&1)" || describe_exit=$?

    local clean_json=""
    if [[ $describe_exit -eq 0 ]]; then
        # Strip any non-JSON prefix the CLI sometimes emits
        clean_json="$(printf '%s' "$describe_raw" | python3 -c '
import json, sys, re
raw = sys.stdin.read()
m = re.search(r"[\[{]", raw)
if not m:
    sys.exit(2)
raw = raw[m.start():]
obj, _ = json.JSONDecoder().raw_decode(raw)
print(json.dumps(obj))
' 2>/dev/null)" || clean_json=""
    fi

    if [[ -z "$clean_json" ]]; then
        warn "CLI describe unusable — falling back to REST"
        clean_json="$(rest_describe_business_group)"
    fi

    # Entitlement parsing — recursively scan the business-group payload for
    # flags matching 'agent' (Agent Fabric) and 'flex' (Flex Gateway).
    info "Parsing entitlement flags ..."
    local analysis tmp_json tmp_py
    tmp_json="$(mktemp)"
    tmp_py="$(mktemp --suffix=.py 2>/dev/null || mktemp)"
    printf '%s' "$clean_json" > "$tmp_json"
    cat > "$tmp_py" <<'PYEOF'
import json, sys
with open(sys.argv[1]) as f:
    data = json.load(f)

def leaf_truthy(v):
    """Deep check: is any leaf under this value a truthy 'enabled'-ish signal?"""
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v > 0
    if isinstance(v, str):
        return v.strip().lower() in ("true", "enabled", "active", "yes")
    if isinstance(v, dict):
        if v.get("enabled") is True:
            return True
        return any(leaf_truthy(x) for x in v.values())
    if isinstance(v, list):
        return any(leaf_truthy(x) for x in v)
    return False

def scan(obj, needle, path=""):
    needle = needle.lower()
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = path + "." + k
            if needle in k.lower():
                hits.append((p, leaf_truthy(v), repr(v)[:80]))
            if isinstance(v, (dict, list)):
                hits.extend(scan(v, needle, p))
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            if isinstance(x, str) and needle in x.lower():
                hits.append((f"{path}[{i}]", True, x))
            elif isinstance(x, (dict, list)):
                hits.extend(scan(x, needle, f"{path}[{i}]"))
    return hits

def truthy(hits):
    return any(v for _, v, _ in hits)

def is_fabric_hit(path):
    p = path.lower()
    return ("fabric" in p) or ("agentnetwork" in p)

flex_hits_all   = scan(data, "flex")
fabric_hits_all = scan(data, "agent")
fabric_hits     = [h for h in fabric_hits_all if is_fabric_hit(h[0])]

print(json.dumps({
    "agent_fabric_entitled": truthy(fabric_hits),
    "flex_gateway_entitled": truthy(flex_hits_all),
    "agent_fabric_hits":     [{"path": p, "truthy": t, "value": v} for p, t, v in fabric_hits[:10]],
    "flex_gateway_hits":     [{"path": p, "truthy": t, "value": v} for p, t, v in flex_hits_all[:10]],
    "agent_other_hits":      [{"path": p, "truthy": t, "value": v} for p, t, v in fabric_hits_all if not is_fabric_hit(p)][:5],
    "top_level_keys":        sorted(list(data.keys()))[:40] if isinstance(data, dict) else [],
}))
PYEOF
    analysis="$(python3 "$tmp_py" "$tmp_json")"
    rm -f "$tmp_json" "$tmp_py"

    local agent_fabric_entitled flex_entitled
    agent_fabric_entitled="$(printf '%s' "$analysis" | python3 -c "import json,sys;print(json.load(sys.stdin)['agent_fabric_entitled'])")"
    flex_entitled="$(printf '%s' "$analysis" | python3 -c "import json,sys;print(json.load(sys.stdin)['flex_gateway_entitled'])")"

    info "Agent Fabric entitled: $agent_fabric_entitled"
    info "Flex Gateway entitled: $flex_entitled"

    # Write receipt
    local status overall
    if [[ "$agent_fabric_entitled" == "True" && "$flex_entitled" == "True" ]]; then
        status="full"; overall="pass"
    elif [[ "$flex_entitled" == "True" ]]; then
        status="flex_only"; overall="degraded"
    else
        status="none"; overall="fail"
    fi

    python3 - "$clean_json" "$analysis" "$overall" "$status" \
        "$ANYPOINT_ORG_ID" "$ANYPOINT_ENV_ID" "$OUTPUT_FILE" <<'PYEOF'
import json, sys, datetime
raw_describe, analysis, overall, status, org, env, out_path = sys.argv[1:8]
receipt = {
    "timestamp":          datetime.datetime.utcnow().isoformat() + "Z",
    "organization_id":    org,
    "environment_id":     env,
    "overall":            overall,        # pass | degraded | fail
    "entitlement_status": status,         # full | flex_only | none
    "agent_fabric":       json.loads(analysis)["agent_fabric_entitled"],
    "flex_gateway":       json.loads(analysis)["flex_gateway_entitled"],
    "analysis":           json.loads(analysis),
    "raw_response":       json.loads(raw_describe) if raw_describe else {},
}
with open(out_path, "w") as f:
    json.dump(receipt, f, indent=2, default=str)
PYEOF

    info "Wrote receipt → $OUTPUT_FILE"

    if [[ "$agent_fabric_entitled" != "True" ]]; then
        warn "Agent Fabric NOT entitled — caller should degrade to B scope"
        exit 2
    fi
    info "── Entitlement check PASSED ──"
    exit 0
}

main "$@"
