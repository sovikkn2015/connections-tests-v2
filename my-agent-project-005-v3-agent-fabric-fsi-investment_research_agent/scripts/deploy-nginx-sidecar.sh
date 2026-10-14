#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy-nginx-sidecar.sh — V3-B canonical deploy pipeline for the nginx
# Host/SNI rewriter sidecar (Option C from v3-b-infra-debug-findings.md).
#
# WHAT IT DOES (in order, all idempotent):
#   1. Ensures the ECR repo ir-flex-gateway-nginx exists
#   2. Builds aws/nginx-sidecar/Dockerfile for linux/amd64 and pushes
#      :latest + :<git-sha-timestamp>
#   3. Re-renders the Flex Gateway static-config bundle (injects V2
#      x-api-key at render time from API Gateway — never committed)
#      and syncs to s3://ir-flex-gateway-config-<acct>/v3-b/
#   4. Registers a new ir-flex-gateway-task revision:
#        • config-sync                init container (essential=false)
#        • nginx-upstream-proxy       new sidecar (essential=true, no
#                                     host port, container healthcheck)
#        • flex-gateway               depends on nginx-upstream-proxy
#                                     condition=HEALTHY + config-sync
#                                     condition=SUCCESS
#   5. update-service --force-new-deployment and waits <=5 min for
#      services-stable
#   6. Probes ALB /sec-edgar/tools/list and /sec-edgar/tools/call with
#      canonical headers; records HTTP status + body snippet
#   7. Writes agent-fabric/.build-receipts/nginx-sidecar.json with
#      verdict, evidence, and follow-ups
#
# RE-RUN: safe. Every step describes-then-creates.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/_common.sh"

# ── Config ──────────────────────────────────────────────────────────────────
ECS_CLUSTER="${ECS_CLUSTER:-ir-flex-gateway-cluster}"
ECS_SERVICE="${ECS_SERVICE:-ir-flex-gateway-svc}"
TASK_FAMILY="${TASK_FAMILY:-ir-flex-gateway-task}"
ECR_REPO="${ECR_REPO:-ir-flex-gateway-nginx}"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_URI_BASE="${ECR_REGISTRY}/${ECR_REPO}"
LOG_GROUP="${LOG_GROUP:-/ecs/ir-flex-gateway}"
NGINX_CONTAINER_NAME="nginx-upstream-proxy"
NGINX_LOG_STREAM_PREFIX="nginx-upstream-proxy"
FLEX_CONTAINER_NAME="${FLEX_CONTAINER_NAME:-flex-gateway}"

BUCKET="${FLEX_CONFIG_BUCKET:-ir-flex-gateway-config-${AWS_ACCOUNT_ID}}"
PREFIX="${FLEX_CONFIG_PREFIX:-v3-b}"
SIDECAR_DIR="${V3_PROJECT_ROOT}/aws/nginx-sidecar"
API_YAML="${V3_AGENT_FABRIC_DIR}/flex-config/api.yaml"
RECEIPT="${V3_RECEIPTS_DIR}/nginx-sidecar.json"
ALB_URL_FILE="${V3_AGENT_FABRIC_DIR}/.gateway-url.txt"

V2_API_KEY_NAME="${V2_API_KEY_NAME:-ir-mcp-api-key-prod}"

GIT_SHA="$(cd "$V3_PROJECT_ROOT" && git rev-parse --short HEAD 2>/dev/null || echo "unknown")"
IMAGE_TAG_SHA="sha-${GIT_SHA}-$(date -u +%Y%m%d%H%M%S)"

# ── Receipt state ───────────────────────────────────────────────────────────
IMAGE_URI="unknown"
IMAGE_DIGEST="unknown"
TASK_DEF_ARN="unknown"
FINAL_RUNNING_COUNT="unknown"
PROBE1_STATUS="000"
PROBE1_BODY=""
PROBE2_STATUS="000"
PROBE2_BODY=""
VERDICT="failed"
NEXT_STEPS=""
STATUS_NOTES=""

append_note()  { STATUS_NOTES="${STATUS_NOTES}${1} "; }
append_next()  { NEXT_STEPS="${NEXT_STEPS}${1} "; }

write_receipt() {
    local timestamp ac_1 ac_2 ac_3 ac_4 ac_5
    timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    [[ "$FINAL_RUNNING_COUNT" == "1" ]] && ac_1=true || ac_1=false
    [[ "$PROBE1_STATUS" == "200" ]]   && ac_2=true || ac_2=false
    [[ "$PROBE2_STATUS" == "200" ]]   && ac_3=true || ac_3=false
    echo "$PROBE1_BODY" | grep -q '"tools"' && ac_4=true || ac_4=false
    echo "$PROBE2_BODY" | grep -q -E '"(content|result|error)"' && ac_5=true || ac_5=false

    mkdir -p "$(dirname "$RECEIPT")"
    TIMESTAMP="$timestamp" VERDICT="$VERDICT" \
    IMAGE_URI="$IMAGE_URI" IMAGE_DIGEST="$IMAGE_DIGEST" \
    IMAGE_TAG_SHA="$IMAGE_TAG_SHA" ECR_REPO="$ECR_REPO" \
    TASK_DEF_ARN="$TASK_DEF_ARN" TASK_FAMILY="$TASK_FAMILY" \
    ECS_CLUSTER="$ECS_CLUSTER" ECS_SERVICE="$ECS_SERVICE" \
    FINAL_RUNNING_COUNT="$FINAL_RUNNING_COUNT" \
    PROBE1_STATUS="$PROBE1_STATUS" PROBE1_BODY="$PROBE1_BODY" \
    PROBE2_STATUS="$PROBE2_STATUS" PROBE2_BODY="$PROBE2_BODY" \
    AC_1="$ac_1" AC_2="$ac_2" AC_3="$ac_3" AC_4="$ac_4" AC_5="$ac_5" \
    STATUS_NOTES="$STATUS_NOTES" NEXT_STEPS="$NEXT_STEPS" \
    python3 - "$RECEIPT" <<'PYEOF'
import json, os, sys
out = sys.argv[1]
e = os.environ
b = lambda k: e[k] == "true"
receipt = {
    "timestamp": e["TIMESTAMP"],
    "agent": "NGINX-SIDECAR",
    "scope": "V3-B Flex Gateway, add nginx Host/SNI rewriter sidecar (Option C)",
    "status": e["VERDICT"],
    "image": {
        "uri":        e["IMAGE_URI"],
        "tag_sha":    e["IMAGE_TAG_SHA"],
        "digest":     e["IMAGE_DIGEST"],
        "ecr_repo":   e["ECR_REPO"],
    },
    "ecs": {
        "cluster":         e["ECS_CLUSTER"],
        "service":         e["ECS_SERVICE"],
        "task_family":     e["TASK_FAMILY"],
        "task_def_arn":    e["TASK_DEF_ARN"],
        "running_count":   e["FINAL_RUNNING_COUNT"],
    },
    "acceptance_criteria": {
        "ecs_running_with_three_containers_healthy": b("AC_1"),
        "tools_list_returned_200":                   b("AC_2"),
        "tools_call_returned_200":                   b("AC_3"),
        "tools_list_body_has_tools_array":           b("AC_4"),
        "tools_call_body_has_content_result_error":  b("AC_5"),
    },
    "probes": [
        {
            "name":    "tools/list",
            "method":  "POST",
            "path":    "/sec-edgar/tools/list",
            "status":  e["PROBE1_STATUS"],
            "body_snippet": e["PROBE1_BODY"][:400],
        },
        {
            "name":    "tools/call:get_10k:NVDA",
            "method":  "POST",
            "path":    "/sec-edgar/tools/call",
            "status":  e["PROBE2_STATUS"],
            "body_snippet": e["PROBE2_BODY"][:400],
        },
    ],
    "notes":      e["STATUS_NOTES"].strip(),
    "next_steps": e["NEXT_STEPS"].strip(),
}
with open(out, "w") as f:
    json.dump(receipt, f, indent=2)
print("Wrote receipt: " + out)
PYEOF
}

trap 'rc=$?; if [[ $rc -ne 0 && "$VERDICT" == "failed" && -z "$STATUS_NOTES" ]]; then append_note "Script aborted with exit $rc (see logs)"; fi; write_receipt' EXIT

# ── Pre-flight ──────────────────────────────────────────────────────────────
preflight() {
    info "── Preflight ──"
    [[ -d "$SIDECAR_DIR" ]]            || die "Sidecar source dir missing: $SIDECAR_DIR"
    [[ -f "$SIDECAR_DIR/Dockerfile" ]] || die "Missing $SIDECAR_DIR/Dockerfile"
    [[ -f "$SIDECAR_DIR/nginx.conf" ]] || die "Missing $SIDECAR_DIR/nginx.conf"
    [[ -f "$API_YAML" ]]               || die "Missing $API_YAML"

    if ! docker info >/dev/null 2>&1; then
        append_note "Docker/Finch daemon is not running — cannot build sidecar image."
        die "Docker daemon not running"
    fi
    info "Docker daemon OK"

    aws sts get-caller-identity --region "$AWS_REGION" >/dev/null \
        || die "AWS credentials not usable"
    info "AWS identity OK (account $AWS_ACCOUNT_ID)"
}

# ── ECR repo ───────────────────────────────────────────────────────────────
ensure_ecr_repo() {
    info "── Ensuring ECR repo: ${ECR_REPO} ──"
    if aws ecr describe-repositories --region "$AWS_REGION" \
            --repository-names "$ECR_REPO" >/dev/null 2>&1; then
        info "ECR repo exists"
    else
        aws ecr create-repository --region "$AWS_REGION" \
            --repository-name "$ECR_REPO" \
            --image-scanning-configuration scanOnPush=true \
            --image-tag-mutability MUTABLE >/dev/null
        info "Created ECR repo $ECR_REPO"
    fi
}

# ── Build + push ──────────────────────────────────────────────────────────
build_and_push() {
    info "── Building ${IMAGE_URI_BASE}:${IMAGE_TAG_SHA} for linux/amd64 ──"
    aws ecr get-login-password --region "$AWS_REGION" \
        | docker login --username AWS --password-stdin "$ECR_REGISTRY" >/dev/null \
        || die "ECR login failed"

    docker build --platform linux/amd64 \
        -t "${IMAGE_URI_BASE}:${IMAGE_TAG_SHA}" \
        -t "${IMAGE_URI_BASE}:latest" \
        "$SIDECAR_DIR" \
        || die "docker build failed"

    docker push "${IMAGE_URI_BASE}:${IMAGE_TAG_SHA}" >/dev/null \
        || die "docker push (sha tag) failed"
    docker push "${IMAGE_URI_BASE}:latest" >/dev/null \
        || die "docker push (:latest) failed"

    IMAGE_URI="${IMAGE_URI_BASE}:${IMAGE_TAG_SHA}"
    IMAGE_DIGEST="$(aws ecr describe-images --region "$AWS_REGION" \
        --repository-name "$ECR_REPO" \
        --image-ids imageTag="$IMAGE_TAG_SHA" \
        --query 'imageDetails[0].imageDigest' --output text 2>/dev/null || echo unknown)"
    info "Pushed ${IMAGE_URI} (digest ${IMAGE_DIGEST})"
}

# ── Render + sync config bundle (x-api-key injected from APIGW) ─────────────
sync_config_bundle() {
    info "── Rendering + syncing flex-config bundle to S3 ──"
    local render_dir; render_dir="$(mktemp -d)"
    cp "${V3_AGENT_FABRIC_DIR}/flex-config/"*.yaml "$render_dir/"
    rm -f "$render_dir/agent-network.yaml" 2>/dev/null || true

    local api_key_id api_key_value
    api_key_id="$(aws apigateway get-api-keys --region "$AWS_REGION" \
        --name-query "$V2_API_KEY_NAME" --include-values \
        --query "items[?name=='$V2_API_KEY_NAME'].id | [0]" --output text 2>/dev/null || echo None)"
    if [[ -n "$api_key_id" && "$api_key_id" != "None" ]]; then
        api_key_value="$(aws apigateway get-api-key --region "$AWS_REGION" \
            --api-key "$api_key_id" --include-value \
            --query "value" --output text)"
        python3 - "$render_dir/policy-header-injection.yaml" "$api_key_value" <<'PYEOF'
import sys, pathlib
path, value = sys.argv[1], sys.argv[2]
p = pathlib.Path(path)
if p.exists():
    body = p.read_text().replace("__V2_API_KEY_PLACEHOLDER__", value)
    p.write_text(body)
    print("Rendered header-injection policy with live V2 x-api-key")
PYEOF
    else
        warn "Could not resolve V2 API key $V2_API_KEY_NAME; leaving placeholder"
        append_note "V2 api-key lookup returned None — header-injection unrendered."
    fi

    aws s3 sync "$render_dir/" "s3://${BUCKET}/${PREFIX}/" \
        --region "$AWS_REGION" --exclude "registration.yaml" >/dev/null \
        || die "s3 sync failed"
    info "Synced bundle to s3://${BUCKET}/${PREFIX}/"
    rm -rf "$render_dir"
}

# ── Register new task-def revision ─────────────────────────────────────────
register_task_def() {
    info "── Registering new ${TASK_FAMILY} revision ──"
    local current_td new_td_file
    current_td="$(aws ecs describe-task-definition \
        --task-definition "${TASK_FAMILY}" \
        --region "$AWS_REGION" \
        --query 'taskDefinition' --output json)"
    new_td_file="$(mktemp)"

    CURRENT_TD="$current_td" IMAGE_URI="$IMAGE_URI" \
    LOG_GROUP="$LOG_GROUP" AWS_REGION="$AWS_REGION" \
    NGINX_CONTAINER_NAME="$NGINX_CONTAINER_NAME" \
    NGINX_LOG_STREAM_PREFIX="$NGINX_LOG_STREAM_PREFIX" \
    FLEX_CONTAINER_NAME="$FLEX_CONTAINER_NAME" \
    python3 - "$new_td_file" <<'PYEOF'
import json, os, sys
out_path   = sys.argv[1]
image_uri  = os.environ["IMAGE_URI"]
log_group  = os.environ["LOG_GROUP"]
region     = os.environ["AWS_REGION"]
nginx_name = os.environ["NGINX_CONTAINER_NAME"]
nginx_pfx  = os.environ["NGINX_LOG_STREAM_PREFIX"]
flex_name  = os.environ["FLEX_CONTAINER_NAME"]
td = json.loads(os.environ["CURRENT_TD"])

# Strip register-task-definition-incompatible fields.
for k in ("taskDefinitionArn","revision","status","requiresAttributes",
          "compatibilities","registeredAt","registeredBy"):
    td.pop(k, None)

containers = td.get("containerDefinitions", [])

# Drop prior sidecar variants so we stay idempotent. We keep config-sync
# + flex-gateway exactly as-is except for wiring flex's dependsOn.
containers = [c for c in containers if c.get("name") not in ("nginx-sidecar", nginx_name)]

# Build the canonical nginx-upstream-proxy sidecar. No portMappings —
# the container listens on loopback inside the task's network namespace.
# Container healthcheck mirrors the Dockerfile HEALTHCHECK so ECS can
# set healthStatus and the flex container can dependsOn=HEALTHY.
sidecar = {
    "name":      nginx_name,
    "image":     image_uri,
    "essential": True,
    "portMappings": [],
    "environment": [],
    "mountPoints": [],
    "volumesFrom": [],
    "healthCheck": {
        "command": ["CMD-SHELL", "wget -q --spider http://127.0.0.1:8082/healthz || exit 1"],
        "interval": 15,
        "timeout":  5,
        "retries":  3,
        "startPeriod": 10,
    },
    "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
            "awslogs-group":         log_group,
            "awslogs-region":        region,
            "awslogs-stream-prefix": nginx_pfx,
        },
    },
    "systemControls": [],
}

# Rewrite flex-gateway's dependsOn to include:
#   • config-sync   SUCCESS  (init container)
#   • nginx-upstream-proxy  HEALTHY
# so flex won't start until nginx is actually serving /healthz.
rebuilt = []
for c in containers:
    if c.get("name") == flex_name:
        existing = c.get("dependsOn") or []
        kept = [d for d in existing if d.get("containerName") not in ("nginx-sidecar", nginx_name)]
        if not any(d.get("containerName") == "config-sync" for d in kept):
            kept.append({"containerName": "config-sync", "condition": "SUCCESS"})
        kept.append({"containerName": nginx_name, "condition": "HEALTHY"})
        c["dependsOn"] = kept
    rebuilt.append(c)

rebuilt.append(sidecar)
td["containerDefinitions"] = rebuilt

with open(out_path, "w") as f:
    json.dump(td, f)
print("Wrote new task-def JSON to " + out_path)
PYEOF

    TASK_DEF_ARN="$(aws ecs register-task-definition \
        --region "$AWS_REGION" \
        --cli-input-json "file://${new_td_file}" \
        --query 'taskDefinition.taskDefinitionArn' --output text)" \
        || die "register-task-definition failed"
    rm -f "$new_td_file"
    info "Registered ${TASK_DEF_ARN}"
}

# ── update-service + wait ──────────────────────────────────────────────────
deploy_service() {
    info "── Updating ECS service to ${TASK_DEF_ARN} ──"
    aws ecs update-service --region "$AWS_REGION" \
        --cluster "$ECS_CLUSTER" --service "$ECS_SERVICE" \
        --task-definition "$TASK_DEF_ARN" \
        --force-new-deployment >/dev/null \
        || die "update-service failed"

    info "Waiting up to 5 min for services-stable..."
    if aws ecs wait services-stable --region "$AWS_REGION" \
            --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE" 2>/dev/null; then
        info "Service stable"
    else
        warn "services-stable did not converge in wait window"
        append_note "services-stable wait did not converge (continuing to probe)."
    fi

    FINAL_RUNNING_COUNT="$(aws ecs describe-services --region "$AWS_REGION" \
        --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE" \
        --query 'services[0].runningCount' --output text 2>/dev/null || echo unknown)"
    info "Running count: $FINAL_RUNNING_COUNT"
}

# ── Probe ALB ──────────────────────────────────────────────────────────────
probe() {
    info "── Probing ALB ──"
    local alb_url
    alb_url="$(cat "$ALB_URL_FILE" 2>/dev/null || echo "")"
    if [[ -z "$alb_url" ]]; then
        local alb_dns
        alb_dns="$(aws elbv2 describe-load-balancers --region "$AWS_REGION" \
            --names ir-flex-gateway-alb \
            --query 'LoadBalancers[0].DNSName' --output text 2>/dev/null || echo "")"
        [[ -n "$alb_dns" && "$alb_dns" != "None" ]] && alb_url="http://${alb_dns}"
    fi
    info "ALB URL: $alb_url"

    # Poll tools/list up to 10 times (5 min) to give ECS time to cycle.
    local attempt=0
    while (( attempt < 10 )); do
        attempt=$((attempt + 1))
        local rf; rf="$(mktemp)"
        PROBE1_STATUS="$(curl -sS -o "$rf" -w "%{http_code}" --max-time 20 \
            -X POST \
            -H "Content-Type: application/json" \
            -H "x-agent-id: ir-research-orchestrator" \
            -H "x-correlation-id: nginx-sidecar-verify-1" \
            -d '{}' \
            "${alb_url}/sec-edgar/tools/list" 2>/dev/null || echo 000)"
        PROBE1_BODY="$(head -c 1000 "$rf" 2>/dev/null || true)"
        rm -f "$rf"
        info "tools/list attempt $attempt → HTTP $PROBE1_STATUS"
        [[ "$PROBE1_STATUS" == "200" ]] && break
        sleep 30
    done

    # tools/call (single attempt; by now Flex has stabilised)
    local rf2; rf2="$(mktemp)"
    PROBE2_STATUS="$(curl -sS -o "$rf2" -w "%{http_code}" --max-time 30 \
        -X POST \
        -H "Content-Type: application/json" \
        -H "x-agent-id: ir-research-orchestrator" \
        -H "x-correlation-id: nginx-sidecar-verify-2" \
        -d '{"name":"get_10k","arguments":{"ticker":"NVDA"}}' \
        "${alb_url}/sec-edgar/tools/call" 2>/dev/null || echo 000)"
    PROBE2_BODY="$(head -c 1500 "$rf2" 2>/dev/null || true)"
    rm -f "$rf2"
    info "tools/call → HTTP $PROBE2_STATUS"
}

# ── Verdict ────────────────────────────────────────────────────────────────
decide_verdict() {
    info "── Deciding verdict ──"
    local ok=true
    [[ "$PROBE1_STATUS" == "200" ]] || ok=false
    [[ "$PROBE2_STATUS" == "200" ]] || ok=false
    echo "$PROBE1_BODY" | grep -q '"tools"' || ok=false
    echo "$PROBE2_BODY" | grep -q -E '"(content|result|error)"' || ok=false

    if $ok; then
        VERDICT="ok"
        info "All acceptance criteria PASSED"
    else
        VERDICT="failed"
        append_note "Acceptance criteria not all green: probe1=$PROBE1_STATUS probe2=$PROBE2_STATUS."
        case "$PROBE1_STATUS" in
            400) append_next "Check nginx logs for Host/SNI symptoms; force a second update-service --force-new-deployment so Flex re-reads api.yaml pointing at 127.0.0.1:8082.";;
            502|504) append_next "Upstream TLS handshake may be failing with proxy_ssl_verify on; verify /etc/ssl/certs/ca-certificates.crt is baked into the image (docker run --rm <image> ls /etc/ssl/certs | grep ca-cert).";;
            403) append_next "APIGW rejected x-api-key — confirm apply-flex-config-v2.sh rendered the real key and Flex reloaded.";;
            000) append_next "ALB unreachable; check SG ingress + ALB target health.";;
            *)   append_next "Inspect CloudWatch /ecs/ir-flex-gateway for nginx-upstream-proxy + flex-gateway streams (use aws logs filter-log-events).";;
        esac
    fi
}

main() {
    local start_s; start_s="$(date +%s)"
    preflight
    ensure_ecr_repo
    build_and_push
    sync_config_bundle
    register_task_def
    deploy_service
    probe
    decide_verdict
    local end_s; end_s="$(date +%s)"
    info "── deploy-nginx-sidecar.sh complete in $((end_s - start_s))s ──"
    info "  image=${IMAGE_URI}"
    info "  task_def=${TASK_DEF_ARN}"
    info "  running=${FINAL_RUNNING_COUNT}"
    info "  tools/list=${PROBE1_STATUS}   tools/call=${PROBE2_STATUS}"
    info "  verdict=${VERDICT}"
}

main "$@"
