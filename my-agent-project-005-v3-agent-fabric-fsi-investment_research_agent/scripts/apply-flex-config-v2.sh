#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# apply-flex-config-v2.sh — iterated V3-B config push.
#
# Differences vs apply-flex-config.sh:
#   • Uses the named-service routing model in api.yaml so Envoy auto-SNI
#     and auto-host-rewrite for the V2 API Gateway upstream.
#   • Adds a header-injection PolicyBinding that injects the V2 x-api-key
#     on every inbound request. The key value is fetched from AWS API
#     Gateway at render time and written into a tempdir copy of
#     policy-header-injection.yaml before upload — NEVER committed.
#   • Keeps the registration.yaml that the upstream flex-gateway container
#     needs to bootstrap in local mode.
#
# Outputs: agent-fabric/.flex-config-applied.json
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/_common.sh"

trap 'error "apply-flex-config-v2.sh failed on line $LINENO"; exit 1' ERR

CONFIG_DIR="${V3_AGENT_FABRIC_DIR}/flex-config"
BUCKET="${FLEX_CONFIG_BUCKET:-ir-flex-gateway-config-${AWS_ACCOUNT_ID}}"
PREFIX="${FLEX_CONFIG_PREFIX:-v3-b}"
RECEIPT="${V3_AGENT_FABRIC_DIR}/.flex-config-applied.json"
ECS_CLUSTER="${ECS_CLUSTER:-ir-flex-gateway-cluster}"
ECS_SERVICE="${ECS_SERVICE:-ir-flex-gateway-svc}"

V2_API_KEY_NAME="${V2_API_KEY_NAME:-ir-mcp-api-key-prod}"

[[ -d "$CONFIG_DIR" ]] || die "Config dir missing: $CONFIG_DIR"

render_bundle() {
    info "── Rendering config bundle (resolving x-api-key from API Gateway) ──"
    RENDER_DIR="$(mktemp -d)"
    cp "$CONFIG_DIR"/*.yaml "$RENDER_DIR/"
    rm -f "$RENDER_DIR/agent-network.yaml" 2>/dev/null || true

    local api_key_id
    api_key_id="$(aws apigateway get-api-keys --region "$AWS_REGION" \
        --name-query "$V2_API_KEY_NAME" --include-values \
        --query "items[?name=='$V2_API_KEY_NAME'].id | [0]" --output text)"
    [[ -n "$api_key_id" && "$api_key_id" != "None" ]] \
        || die "V2 API key $V2_API_KEY_NAME not found in API Gateway"

    local api_key_value
    api_key_value="$(aws apigateway get-api-key --region "$AWS_REGION" \
        --api-key "$api_key_id" --include-value \
        --query "value" --output text)"

    python3 - "$RENDER_DIR/policy-header-injection.yaml" "$api_key_value" <<'PYEOF'
import sys
path, value = sys.argv[1], sys.argv[2]
with open(path) as f:
    body = f.read()
body = body.replace("__V2_API_KEY_PLACEHOLDER__", value)
with open(path, "w") as f:
    f.write(body)
PYEOF
    info "Rendered header-injection policy with live V2 x-api-key"
    export RENDER_DIR
}

upload_bundle() {
    info "── Uploading rendered bundle to s3://${BUCKET}/${PREFIX}/ ──"
    aws s3 sync "$RENDER_DIR/" "s3://${BUCKET}/${PREFIX}/" \
        --region "$AWS_REGION" --exclude "registration.yaml" >/dev/null
    local uploaded
    uploaded="$(aws s3 ls "s3://${BUCKET}/${PREFIX}/" --region "$AWS_REGION" | wc -l | tr -d ' ')"
    info "Bucket now has $uploaded files"
    rm -rf "$RENDER_DIR"
}

force_deploy() {
    info "── Forcing new ECS deployment to pick up fresh config ──"
    aws ecs update-service --region "$AWS_REGION" \
        --cluster "$ECS_CLUSTER" --service "$ECS_SERVICE" \
        --force-new-deployment >/dev/null
    info "Waiting up to 4 min for service-stable..."
    aws ecs wait services-stable --region "$AWS_REGION" \
        --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE" 2>/dev/null \
        || warn "services-stable timed out"
}

verify() {
    info "── Verifying ──"
    local alb_url
    alb_url="$(cat "${V3_AGENT_FABRIC_DIR}/.gateway-url.txt" 2>/dev/null || echo unknown)"
    LAST_RUNNING_COUNT="$(aws ecs describe-services --region "$AWS_REGION" \
        --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE" \
        --query 'services[0].runningCount' --output text)"
    info "runningCount=$LAST_RUNNING_COUNT"

    LAST_CURL_CODE="$(curl -sS -o /dev/null -w "%{http_code}" --max-time 20 \
        -X POST -H 'Content-Type: application/json' -d '{}' \
        "$alb_url/sec-edgar/tools/list" 2>&1 || echo 000)"
    info "POST $alb_url/sec-edgar/tools/list -> HTTP $LAST_CURL_CODE"
    export LAST_CURL_CODE LAST_RUNNING_COUNT
}

write_receipt() {
    python3 - "$RECEIPT" "$BUCKET" "$PREFIX" \
        "$LAST_RUNNING_COUNT" "$LAST_CURL_CODE" <<'PYEOF'
import json, sys, datetime
out, bucket, prefix, running, code = sys.argv[1:]
receipt = {
    "timestamp":        datetime.datetime.utcnow().isoformat() + "Z",
    "config_bucket":    bucket,
    "config_prefix":    prefix,
    "running_count":    int(running) if running.isdigit() else running,
    "probe_status":     int(code) if code.isdigit() else code,
    "probe_path":       "/sec-edgar/tools/list",
    "mode":             "self-managed-static-config-v2",
    "notes":            "Iterated bundle: named-service routing + header-injection for V2 x-api-key. registration.yaml preserved from prior apply.",
}
with open(out, "w") as f:
    json.dump(receipt, f, indent=2)
PYEOF
    info "Wrote receipt: $RECEIPT"
}

main() {
    info "── apply-flex-config-v2.sh (V3-B iteration) starting ──"
    render_bundle
    upload_bundle
    force_deploy
    verify
    write_receipt
    info "── apply-flex-config-v2.sh complete ──"
    info "  ECS runningCount=$LAST_RUNNING_COUNT  ALB probe=$LAST_CURL_CODE"
}

main "$@"
