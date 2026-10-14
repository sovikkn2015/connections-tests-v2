#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# test-registry.sh — Phase 2+4: Registry + Routing verification
#
# Queries the deployed Agent Fabric network and asserts:
#   1. All 7 registry components are present (4 agents + 3 MCP servers)
#   2. All 3 routing policies are active (l1-l2-direct-tools,
#      l3-l4-analysis, compliance-routing)
#   3. Each policy's 'route' payload matches agent-network.yaml
#
# Exits 0 on full match, non-zero with a diff on mismatch.
# Writes a machine-readable summary to .phase2-test-result.json.
#
# REQUIRED ENV:
#   ANYPOINT_ORG_ID, ANYPOINT_ENV_ID
#   ANYPOINT_ACCESS_TOKEN (or configured via `anypoint-cli-v4 conf`)
#
# OPTIONAL ENV:
#   ANYPOINT_HOST (default https://anypoint.mulesoft.com)
#   NETWORK_NAME  (default fsi-investment-research-v3)
#   OUTPUT_FILE   (default .phase2-test-result.json)
# ─────────────────────────────────────────────────────────────────────────────

set -Eeuo pipefail
IFS=$'\n\t'

_ts()   { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
info()  { printf "[INFO  %s] %s\n" "$(_ts)" "$*" >&2; }
warn()  { printf "[WARN  %s] %s\n" "$(_ts)" "$*" >&2; }
error() { printf "[ERROR %s] %s\n" "$(_ts)" "$*" >&2; }

ANYPOINT_HOST="${ANYPOINT_HOST:-https://anypoint.mulesoft.com}"
NETWORK_NAME="${NETWORK_NAME:-fsi-investment-research-v3}"
OUTPUT_FILE="${OUTPUT_FILE:-.phase2-test-result.json}"

: "${ANYPOINT_ORG_ID:?ANYPOINT_ORG_ID is required}"
: "${ANYPOINT_ENV_ID:?ANYPOINT_ENV_ID is required}"

API_BASE="${ANYPOINT_HOST}/agent-fabric/api/v1/organizations/${ANYPOINT_ORG_ID}/environments/${ANYPOINT_ENV_ID}"

have_cli=0
if command -v anypoint-cli-v4 >/dev/null 2>&1; then have_cli=1; fi
command -v curl >/dev/null 2>&1 || { error "curl required"; exit 2; }
command -v jq   >/dev/null 2>&1 || { error "jq required";   exit 2; }

resolve_token() {
    if [[ -n "${ANYPOINT_ACCESS_TOKEN:-}" ]]; then
        echo "$ANYPOINT_ACCESS_TOKEN"; return
    fi
    if [[ $have_cli -eq 1 ]]; then
        local tok
        tok="$(anypoint-cli-v4 account bearer-token 2>/dev/null || true)"
        [[ -n "$tok" ]] && { echo "$tok"; return; }
    fi
    error "No auth token"; exit 2
}
TOKEN="$(resolve_token)"

# ── Result accumulator ──────────────────────────────────────────────────────
RESULT_JSON='{}'
FAILURES=()
record_fail() { FAILURES+=("$1"); error "FAIL: $1"; }

# ── Expected registry ids ───────────────────────────────────────────────────
EXPECTED_IDS=(
    ir-research-orchestrator
    ir-compliance-agent
    financial-analysis-agent
    sentiment-analysis-agent
    sec-edgar
    market-data
    news-search
)

# ── Expected policies: name:agent:model:delegate_count ─────────────────────
EXPECTED_POLICIES=(
    "l1-l2-direct-tools:ir-research-orchestrator:haiku:0"
    "l3-l4-analysis:ir-research-orchestrator:sonnet:2"
    "compliance-routing:ir-compliance-agent::0"
)

http_get() {
    local path="$1"
    local url="${API_BASE}${path}"
    local tmp_body tmp_code
    tmp_body="$(mktemp)"; tmp_code="$(mktemp)"
    curl -sS -H "Authorization: Bearer ${TOKEN}" -H "Accept: application/json" \
        -o "$tmp_body" -w "%{http_code}" "$url" > "$tmp_code" || true
    local code body
    code="$(cat "$tmp_code")"; body="$(cat "$tmp_body")"
    rm -f "$tmp_code" "$tmp_body"
    if [[ ! "$code" =~ ^2 ]]; then
        error "GET $path -> HTTP $code  body=$body"
        return 1
    fi
    printf "%s" "$body"
}

# ── Step 1: Registry check ──────────────────────────────────────────────────
info "── Registry check ──"

registry_json=""
if [[ $have_cli -eq 1 ]] && anypoint-cli-v4 agent-fabric registry list --help >/dev/null 2>&1; then
    registry_json="$(anypoint-cli-v4 agent-fabric registry list --output json \
        --organization "$ANYPOINT_ORG_ID" --environment "$ANYPOINT_ENV_ID" 2>/dev/null || true)"
fi
if [[ -z "$registry_json" ]] || ! echo "$registry_json" | jq empty 2>/dev/null; then
    registry_json="$(http_get "/registry?type=all" || echo '{"items":[]}')"
fi

actual_ids_json="$(echo "$registry_json" | jq '[(.items // .)[] | .id] | sort')"
actual_ids_arr=()
while IFS= read -r id; do
    actual_ids_arr+=("$id")
done < <(echo "$actual_ids_json" | jq -r '.[]')

info "Found ${#actual_ids_arr[@]} registry entries"

missing_ids=()
for id in "${EXPECTED_IDS[@]}"; do
    if ! printf '%s\n' "${actual_ids_arr[@]}" | grep -Fxq "$id"; then
        missing_ids+=("$id")
    fi
done

unexpected_ids=()
for id in "${actual_ids_arr[@]}"; do
    found=0
    for exp in "${EXPECTED_IDS[@]}"; do
        [[ "$exp" == "$id" ]] && { found=1; break; }
    done
    [[ $found -eq 0 ]] && unexpected_ids+=("$id")
done

registry_pass="true"
if [[ ${#missing_ids[@]} -gt 0 ]]; then
    registry_pass="false"
    for id in "${missing_ids[@]}"; do record_fail "Missing registry id: $id"; done
fi
if [[ ${#unexpected_ids[@]} -gt 0 ]]; then
    warn "Unexpected registry ids (not blocking): ${unexpected_ids[*]}"
fi

expected_ids_json="$(printf '%s\n' "${EXPECTED_IDS[@]}" | jq -R . | jq -s 'sort')"
missing_ids_json="$(printf '%s\n' "${missing_ids[@]:-}" | grep -v '^$' | jq -R . | jq -s 'sort' 2>/dev/null || echo '[]')"
unexpected_ids_json="$(printf '%s\n' "${unexpected_ids[@]:-}" | grep -v '^$' | jq -R . | jq -s 'sort' 2>/dev/null || echo '[]')"

RESULT_JSON="$(echo "$RESULT_JSON" | jq \
    --argjson expected   "$expected_ids_json" \
    --argjson actual     "$actual_ids_json" \
    --argjson missing    "$missing_ids_json" \
    --argjson unexpected "$unexpected_ids_json" \
    --arg     pass       "$registry_pass" \
    '.registry = {
        expected_count: ($expected | length),
        actual_count:   ($actual   | length),
        expected:       $expected,
        actual:         $actual,
        missing:        $missing,
        unexpected:     $unexpected,
        pass:           ($pass == "true")
    }')"

# ── Step 2: Routing policy checks ───────────────────────────────────────────
info "── Routing policy checks ──"

routing_pass="true"
policies_result='[]'

for entry in "${EXPECTED_POLICIES[@]}"; do
    IFS=':' read -r pname pagent pmodel pdelcount <<<"$entry"

    info "Verifying policy: $pname"

    policy_json=""
    if [[ $have_cli -eq 1 ]] && anypoint-cli-v4 agent-fabric routing describe --help >/dev/null 2>&1; then
        policy_json="$(anypoint-cli-v4 agent-fabric routing describe \
            --network "$NETWORK_NAME" --policy "$pname" --output json 2>/dev/null || true)"
    fi
    if [[ -z "$policy_json" ]] || ! echo "$policy_json" | jq empty 2>/dev/null; then
        policy_json="$(http_get "/agent-networks/${NETWORK_NAME}/routing/${pname}" || echo '{}')"
    fi

    actual_agent="$(echo "$policy_json" | jq -r '.route.agent // empty')"
    actual_model="$(echo "$policy_json" | jq -r '.route.model // empty')"
    actual_delegates_json="$(echo "$policy_json" | jq '[.route.delegateTo // [] | .[]]')"
    actual_delcount="$(echo "$actual_delegates_json" | jq 'length')"

    policy_pass="true"
    errors_for_policy='[]'

    if [[ "$actual_agent" != "$pagent" ]]; then
        policy_pass="false"; routing_pass="false"
        record_fail "Policy '$pname': agent expected='$pagent' actual='$actual_agent'"
        errors_for_policy="$(echo "$errors_for_policy" | jq --arg m "agent mismatch: expected=$pagent actual=$actual_agent" '. + [$m]')"
    fi

    if [[ -n "$pmodel" && "$actual_model" != "$pmodel" ]]; then
        policy_pass="false"; routing_pass="false"
        record_fail "Policy '$pname': model expected='$pmodel' actual='$actual_model'"
        errors_for_policy="$(echo "$errors_for_policy" | jq --arg m "model mismatch: expected=$pmodel actual=$actual_model" '. + [$m]')"
    fi

    if [[ "$actual_delcount" != "$pdelcount" ]]; then
        policy_pass="false"; routing_pass="false"
        record_fail "Policy '$pname': delegate count expected=$pdelcount actual=$actual_delcount"
        errors_for_policy="$(echo "$errors_for_policy" | jq --arg m "delegate count mismatch: expected=$pdelcount actual=$actual_delcount" '. + [$m]')"
    fi

    if [[ "$pname" == "l3-l4-analysis" ]]; then
        for required_del in financial-analysis-agent sentiment-analysis-agent; do
            if ! echo "$actual_delegates_json" | jq -e --arg d "$required_del" 'index($d)' >/dev/null; then
                policy_pass="false"; routing_pass="false"
                record_fail "Policy '$pname': missing delegate '$required_del'"
                errors_for_policy="$(echo "$errors_for_policy" | jq --arg m "missing delegate: $required_del" '. + [$m]')"
            fi
        done
    fi

    policies_result="$(echo "$policies_result" | jq \
        --arg     name       "$pname" \
        --arg     e_agent    "$pagent" \
        --arg     a_agent    "$actual_agent" \
        --arg     e_model    "$pmodel" \
        --arg     a_model    "$actual_model" \
        --arg     e_delcount "$pdelcount" \
        --arg     a_delcount "$actual_delcount" \
        --argjson a_deleg    "$actual_delegates_json" \
        --argjson errs       "$errors_for_policy" \
        --arg     pass       "$policy_pass" \
        '. + [{
            name:           $name,
            expected_agent: $e_agent,
            actual_agent:   $a_agent,
            expected_model: $e_model,
            actual_model:   $a_model,
            expected_delegate_count: ($e_delcount | tonumber),
            actual_delegate_count:   ($a_delcount | tonumber),
            actual_delegates: $a_deleg,
            errors:         $errs,
            pass:           ($pass == "true")
        }]')"
done

RESULT_JSON="$(echo "$RESULT_JSON" | jq \
    --argjson ps   "$policies_result" \
    --arg     pass "$routing_pass" \
    '.routing = {
        pass:     ($pass == "true"),
        policies: $ps
    }')"

# ── Step 3: Summary ─────────────────────────────────────────────────────────
overall_pass="true"
[[ "$registry_pass" != "true" ]] && overall_pass="false"
[[ "$routing_pass"  != "true" ]] && overall_pass="false"

failures_json="$(printf '%s\n' "${FAILURES[@]:-}" | grep -v '^$' | jq -R . | jq -s 'sort' 2>/dev/null || echo '[]')"

RESULT_JSON="$(echo "$RESULT_JSON" | jq \
    --arg     ts             "$(_ts)" \
    --arg     network        "$NETWORK_NAME" \
    --arg     org            "$ANYPOINT_ORG_ID" \
    --arg     env            "$ANYPOINT_ENV_ID" \
    --arg     pass           "$overall_pass" \
    --argjson failures       "$failures_json" \
    '. + {
        timestamp:       $ts,
        network_name:    $network,
        organization_id: $org,
        environment_id:  $env,
        overall_pass:    ($pass == "true"),
        failure_count:   ($failures | length),
        failures:        $failures
    }')"

echo "$RESULT_JSON" | jq . > "$OUTPUT_FILE"
info "Summary written to $OUTPUT_FILE"

echo
echo "──────────────────────────────────────────────────────────────────────"
echo " Agent Fabric Registry + Routing Test Summary"
echo "──────────────────────────────────────────────────────────────────────"
echo " Network        : $NETWORK_NAME"
echo " Registry check : $([ "$registry_pass" == "true" ] && echo PASS || echo FAIL)"
echo "   expected 7   : found ${#actual_ids_arr[@]}"
if [[ ${#missing_ids[@]} -gt 0 ]]; then
    echo "   missing      : ${missing_ids[*]}"
fi
echo " Routing check  : $([ "$routing_pass" == "true" ] && echo PASS || echo FAIL)"
echo "$policies_result" | jq -r '.[] | "   \(.name): \(if .pass then "PASS" else "FAIL" end) (agent=\(.actual_agent), model=\(.actual_model), delegates=\(.actual_delegate_count))"'
echo " Overall        : $([ "$overall_pass" == "true" ] && echo PASS || echo FAIL)"
if [[ ${#FAILURES[@]} -gt 0 ]]; then
    echo " Failures:"
    printf "   - %s\n" "${FAILURES[@]}"
fi
echo "──────────────────────────────────────────────────────────────────────"

if [[ "$overall_pass" == "true" ]]; then
    exit 0
else
    exit 1
fi
