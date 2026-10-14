#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy-all.sh — Orchestrator for the full 005 V3 Agent Fabric build
#
# Runs the four phase scripts in order:
#   0. verify-entitlement.sh
#   1. deploy-flex-gateway.sh
#   2. register-api-and-policies.sh
#   3. deploy-agent-network.sh         (skipped automatically if entitlement=false)
#
# Then runs acceptance tests and writes:
#   agent-fabric/.build-receipts/gateway.json       — acceptance test results
#   agent-fabric/.build-receipts/gateway-summary.md — human-readable summary
#
# macOS-compatible: uses plain shell vars instead of bash-4 associative arrays.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/_common.sh"

trap 'error "deploy-all.sh failed on line $LINENO"; exit 1' ERR

# ── Phase state (flat vars for bash 3.2 compatibility) ──────────────────────
PHASE_STATUS_entitlement="not_run";      PHASE_MESSAGE_entitlement=""
PHASE_STATUS_gateway="not_run";          PHASE_MESSAGE_gateway=""
PHASE_STATUS_api_policies="not_run";     PHASE_MESSAGE_api_policies=""
PHASE_STATUS_agent_network="not_run";    PHASE_MESSAGE_agent_network=""
PHASE_STATUS_accept_flex_list="not_run"; PHASE_MESSAGE_accept_flex_list=""
PHASE_STATUS_accept_api_list="not_run";  PHASE_MESSAGE_accept_api_list=""
PHASE_STATUS_accept_alb_curl="not_run";  PHASE_MESSAGE_accept_alb_curl=""
ENTITLEMENT_PATH="unknown"
ACCEPT_ALB_URL=""
ACCEPT_ALB_CODE=""

set_status()  { eval "PHASE_STATUS_$1=\"\$2\""; }
set_message() { eval "PHASE_MESSAGE_$1=\"\$2\""; }
get_status()  { eval "printf '%s' \"\${PHASE_STATUS_$1:-not_run}\""; }
get_message() { eval "printf '%s' \"\${PHASE_MESSAGE_$1:-}\""; }

run_phase() {
    local name="$1" script="$2" allow_skip="${3:-no}"
    info "▶ Phase: $name → $script"
    local exit_code=0
    bash "$script" || exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        set_status  "$name" "ok"
        set_message "$name" "exit 0"
    elif [[ $exit_code -eq 2 && "$allow_skip" == "yes" ]]; then
        set_status  "$name" "degraded"
        set_message "$name" "exit 2 — entitlement missing, caller downgraded"
    elif [[ $exit_code -eq 3 ]]; then
        # Partial success: some resources created, others require manual step.
        # Do not abort the orchestrator — record as degraded and continue.
        set_status  "$name" "degraded"
        set_message "$name" "exit 3 — partial success, manual step required (see runbook)"
        return 0
    else
        set_status  "$name" "failed"
        set_message "$name" "exit $exit_code"
        return $exit_code
    fi
    return 0
}

phase_entitlement() {
    info "════ Phase 0: entitlement check ════"
    local exit_code=0
    bash "$SCRIPT_DIR/verify-entitlement.sh" || exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
        set_status  entitlement "ok"
        set_message entitlement "Agent Fabric + Flex Gateway entitled"
        ENTITLEMENT_PATH="full"
    elif [[ $exit_code -eq 2 ]]; then
        set_status  entitlement "degraded"
        set_message entitlement "Agent Fabric not entitled — B-fallback path"
        ENTITLEMENT_PATH="B-fallback"
    else
        set_status  entitlement "failed"
        set_message entitlement "exit $exit_code"
        return $exit_code
    fi

    # Abort if Flex Gateway itself is not entitled.
    local flex_ok
    flex_ok="$(python3 -c "import json;print(json.load(open('${V3_AGENT_FABRIC_DIR}/.entitlement-check.json'))['flex_gateway'])")"
    if [[ "$flex_ok" != "True" ]]; then
        set_status  entitlement "failed"
        set_message entitlement "Neither Flex Gateway nor Agent Fabric entitled — cannot build V3. Upgrade Anypoint subscription or stay on V2."
        warn "No Flex Gateway entitlement — aborting build"
        return 2
    fi
}

# ── Acceptance tests ────────────────────────────────────────────────────────
accept_flex_gateway_list() {
    info "── Acceptance: anypoint-cli-v4 runtime-mgr gateways managed list ──"
    local out exit_code=0
    out="$(anypoint-cli-v4 runtime-mgr gateways managed list \
        --client_id "$ANYPOINT_CLIENT_ID" \
        --client_secret "$ANYPOINT_CLIENT_SECRET" \
        --organization "${ANYPOINT_ORG_NAME:-$ANYPOINT_ORG_ID}" \
        --environment "${ANYPOINT_ENV_NAME:-$ANYPOINT_ENV_ID}" \
        --output json 2>&1)" || exit_code=$?

    if [[ $exit_code -eq 0 ]] && printf '%s' "$out" | grep -qiE 'Connected|RUNNING'; then
        set_status  accept_flex_list "ok"
        set_message accept_flex_list "At least one gateway in Connected/RUNNING state"
    else
        set_status  accept_flex_list "failed"
        set_message accept_flex_list "No Connected gateway found. ECS-hosted self-managed gateways need one-time token-exchange (see runbook FAQ 6.2) before they show Connected."
    fi
}

accept_api_list() {
    info "── Acceptance: anypoint-cli-v4 api-mgr api list ──"
    local out exit_code=0
    out="$(anypoint-cli-v4 api-mgr api list \
        --client_id "$ANYPOINT_CLIENT_ID" \
        --client_secret "$ANYPOINT_CLIENT_SECRET" \
        --organization "${ANYPOINT_ORG_NAME:-$ANYPOINT_ORG_ID}" \
        --environment "${ANYPOINT_ENV_NAME:-$ANYPOINT_ENV_ID}" \
        --output json 2>&1)" || exit_code=$?

    if [[ $exit_code -eq 0 ]] && printf '%s' "$out" | grep -q 'fsi-mcp-servers'; then
        local pcount=0
        if [[ -f "${V3_AGENT_FABRIC_DIR}/.registered-apis.json" ]]; then
            pcount="$(python3 -c "import json;print(json.load(open('${V3_AGENT_FABRIC_DIR}/.registered-apis.json')).get('policies_applied',0))")"
        fi
        set_status  accept_api_list "ok"
        set_message accept_api_list "fsi-mcp-servers API present, $pcount policies applied"
    else
        set_status  accept_api_list "failed"
        set_message accept_api_list "fsi-mcp-servers not found in api-mgr list"
    fi
}

accept_alb_curl() {
    info "── Acceptance: curl the ALB URL ──"
    local url="http://unknown"
    if [[ -f "${V3_AGENT_FABRIC_DIR}/.gateway-url.txt" ]]; then
        url="$(head -1 "${V3_AGENT_FABRIC_DIR}/.gateway-url.txt")"
    fi
    local code
    code="$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo 000)"
    if [[ "$code" =~ ^[1-4] ]]; then
        set_status  accept_alb_curl "ok"
        set_message accept_alb_curl "curl $url returned HTTP $code (non-5xx)"
    else
        set_status  accept_alb_curl "failed"
        set_message accept_alb_curl "curl $url returned HTTP $code — check ECS task logs: aws logs tail /ecs/ir-flex-gateway"
    fi
    ACCEPT_ALB_URL="$url"
    ACCEPT_ALB_CODE="$code"
}

# ── Receipts ────────────────────────────────────────────────────────────────
write_gateway_json() {
    local receipt="${V3_RECEIPTS_DIR}/gateway.json"
    python3 - "$receipt" "$ENTITLEMENT_PATH" \
        "$(get_status entitlement)"      "$(get_message entitlement)" \
        "$(get_status gateway)"          "$(get_message gateway)" \
        "$(get_status api_policies)"     "$(get_message api_policies)" \
        "$(get_status agent_network)"    "$(get_message agent_network)" \
        "$(get_status accept_flex_list)" "$(get_message accept_flex_list)" \
        "$(get_status accept_api_list)"  "$(get_message accept_api_list)" \
        "$(get_status accept_alb_curl)"  "$(get_message accept_alb_curl)" \
        "$ACCEPT_ALB_URL" "$ACCEPT_ALB_CODE" <<'PYEOF'
import json, sys, datetime
args = sys.argv[1:]
out = args[0]
payload = {
    "timestamp":           datetime.datetime.utcnow().isoformat() + "Z",
    "entitlement_path":    args[1],
    "phases": {
        "entitlement":     {"status": args[2],  "message": args[3]},
        "gateway":         {"status": args[4],  "message": args[5]},
        "api_policies":    {"status": args[6],  "message": args[7]},
        "agent_network":   {"status": args[8],  "message": args[9]},
    },
    "acceptance_tests": {
        "flex_gateway_list": {"status": args[10], "message": args[11]},
        "api_mgr_api_list":  {"status": args[12], "message": args[13]},
        "alb_curl":          {"status": args[14], "message": args[15],
                              "url": args[16],    "http_code": args[17]},
    },
}
overall = all(p["status"] in ("ok","degraded") for p in payload["phases"].values())
payload["overall_status"] = "pass" if overall else "fail"
with open(out, "w") as f:
    json.dump(payload, f, indent=2)
PYEOF
    info "Wrote gateway receipt → $receipt"
}

write_summary_md() {
    local md="${V3_RECEIPTS_DIR}/gateway-summary.md"
    {
        printf '# V3 Agent Fabric — Gateway Build Summary\n\n'
        printf 'Generated: %s\n\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
        printf '**Entitlement path:** %s\n\n' "$ENTITLEMENT_PATH"

        printf '## Phase results\n\n'
        printf '| Phase | Status | Message |\n'
        printf '|---|---|---|\n'
        for key in entitlement gateway api_policies agent_network; do
            printf '| %s | %s | %s |\n' \
                "$key" "$(get_status "$key")" "$(get_message "$key")"
        done

        printf '\n## Acceptance tests\n\n'
        printf '| Test | Status | Message |\n'
        printf '|---|---|---|\n'
        for key in accept_flex_list accept_api_list accept_alb_curl; do
            printf '| %s | %s | %s |\n' \
                "$key" "$(get_status "$key")" "$(get_message "$key")"
        done

        printf '\n## Artifacts\n\n'
        printf -- '- `agent-fabric/.entitlement-check.json`\n'
        printf -- '- `agent-fabric/.gateway-deploy.json`\n'
        printf -- '- `agent-fabric/.gateway-url.txt`\n'
        printf -- '- `agent-fabric/.registered-apis.json`\n'
        printf -- '- `agent-fabric/.registered-agents.json`\n'
        printf -- '- `agent-fabric/.build-receipts/gateway.json`\n'

        printf '\n## Manual follow-ups\n\n'
        if [[ "$ENTITLEMENT_PATH" == "B-fallback" ]]; then
            printf -- '- **Agent Fabric is NOT in this Anypoint entitlement.** To activate the full Agent Network registry, upgrade the MuleSoft subscription from Developer/Trial to an Anypoint Platform tier that includes Agent Fabric. Until then the system runs in B-fallback mode: Flex Gateway in ECS proxies MCP traffic and enforces the 5 policies, but Agentforce still calls MCP servers directly via V2 Named Credentials without going through the Agent Registry.\n'
        fi
        printf -- '- **ECS Flex Gateway token exchange:** the Flex container expects a `FLEX_RTMGR_TOKEN` at startup. The ECS task injects `FLEX_RTMGR_CLIENT_ID` / `FLEX_RTMGR_CLIENT_SECRET`. If the container logs show "gateway-not-connected", run the one-time token-exchange documented in `docs/v3-gateway-runbook.md` FAQ 6.2.\n'
        printf -- '- **Policy asset resolution:** the `api-mgr policy apply` calls in `register-api-and-policies.sh` hard-code assetId/version pairs for the 5 Anypoint marketplace policies. If your org mirrors policies to a private Exchange group, override the `groupId` via `--groupId <your-group>` inside `apply_policy()`.\n'
    } > "$md"
    info "Wrote summary → $md"
}

main() {
    info "════════════════════════════════════════════════"
    info "     005 V3 Agent Fabric — full deploy"
    info "════════════════════════════════════════════════"

    load_mulesoft_secret

    phase_entitlement || { write_gateway_json; write_summary_md; die "Entitlement phase failed"; }

    run_phase "gateway" "$SCRIPT_DIR/deploy-flex-gateway.sh" || {
        write_gateway_json; write_summary_md; die "Gateway deploy failed"
    }

    run_phase "api_policies" "$SCRIPT_DIR/register-api-and-policies.sh" || {
        warn "API+policies phase exited non-zero (exit 3 = manual Exchange asset step required — see runbook FAQ 6.6)"
    }

    run_phase "agent_network" "$SCRIPT_DIR/deploy-agent-network.sh" "yes" || {
        warn "Agent network phase failed — continuing to collect receipts"
    }

    info "════ Acceptance tests ════"
    accept_flex_gateway_list || true
    accept_api_list || true
    accept_alb_curl || true

    write_gateway_json
    write_summary_md

    info "════════════════════════════════════════════════"
    info "Build complete. See ${V3_RECEIPTS_DIR}/gateway-summary.md"
    info "════════════════════════════════════════════════"
}

main "$@"
