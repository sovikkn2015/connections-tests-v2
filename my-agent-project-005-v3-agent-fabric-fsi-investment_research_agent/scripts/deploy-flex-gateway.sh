#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deploy-flex-gateway.sh — Phase 1: self-host Flex Gateway on AWS ECS Fargate
#
# Pushes mulesoft/flex-gateway to a private ECR repo, creates an ECS cluster,
# a Fargate task definition, service, and a public ALB so Agentforce Named
# Credentials have a stable URL. All MuleSoft creds are loaded from
# Secrets Manager at RUNTIME (the task definition resolves secrets via
# `secrets:` not `environment:`).
#
# OUTPUTS:
#   agent-fabric/.gateway-url.txt  — ALB DNS name (http://<alb>/)
#   agent-fabric/.gateway-deploy.json — full inventory of created resources
#
# IDEMPOTENT: every step first describes / checks for existence before
# creating. Re-running this after partial failure is safe.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/_common.sh"

trap 'error "deploy-flex-gateway.sh failed on line $LINENO"; exit 1' ERR

# ── Config ──────────────────────────────────────────────────────────────────
ECR_REPO="${ECR_REPO:-ir-flex-gateway}"
ECS_CLUSTER="${ECS_CLUSTER:-ir-flex-gateway-cluster}"
ECS_SERVICE="${ECS_SERVICE:-ir-flex-gateway-svc}"
TASK_FAMILY="${TASK_FAMILY:-ir-flex-gateway-task}"
CONTAINER_NAME="${CONTAINER_NAME:-flex-gateway}"
ALB_NAME="${ALB_NAME:-ir-flex-gateway-alb}"
TG_NAME="${TG_NAME:-ir-flex-gateway-tg}"
SG_NAME="${SG_NAME:-ir-flex-gateway-sg}"
LOG_GROUP="${LOG_GROUP:-/ecs/ir-flex-gateway}"
EXEC_ROLE_NAME="${EXEC_ROLE_NAME:-ir-flex-gateway-task-exec}"
FLEX_IMAGE_SOURCE="${FLEX_IMAGE_SOURCE:-mulesoft/flex-gateway:latest}"
FLEX_CONTAINER_PORT="${FLEX_CONTAINER_PORT:-8081}"

GATEWAY_URL_FILE="${V3_AGENT_FABRIC_DIR}/.gateway-url.txt"
DEPLOY_JSON_FILE="${V3_AGENT_FABRIC_DIR}/.gateway-deploy.json"

# ── Pre-flight ──────────────────────────────────────────────────────────────
pre_flight() {
    info "── Pre-flight checks ──"

    local caller_account
    caller_account="$(aws sts get-caller-identity --query Account --output text)"
    [[ "$caller_account" == "$AWS_ACCOUNT_ID" ]] \
        || die "AWS caller account $caller_account != expected $AWS_ACCOUNT_ID"
    info "AWS account: $caller_account, region: $AWS_REGION"

    command -v docker >/dev/null 2>&1 || die "docker is required to push Flex image"
    docker info >/dev/null 2>&1 \
        || die "docker daemon not running — start Docker Desktop and retry"

    aws secretsmanager describe-secret --secret-id "$MULESOFT_SECRET_ID" \
        --region "$AWS_REGION" >/dev/null \
        || die "Secret $MULESOFT_SECRET_ID not found"

    # Entitlement gate — deploy only if Flex Gateway is entitled.
    local entitle_file="${V3_AGENT_FABRIC_DIR}/.entitlement-check.json"
    if [[ -f "$entitle_file" ]]; then
        local flex_ok
        flex_ok="$(python3 -c "import json;print(json.load(open('$entitle_file'))['flex_gateway'])")"
        [[ "$flex_ok" == "True" ]] \
            || die "Entitlement check says Flex Gateway=false — refusing to deploy. Fix org entitlement first."
        info "Entitlement gate passed (flex_gateway=true)"
    else
        warn "No entitlement-check.json found — run verify-entitlement.sh first. Continuing anyway."
    fi
}

# ── ECR ─────────────────────────────────────────────────────────────────────
ensure_ecr_repo() {
    info "── Ensuring ECR repo: $ECR_REPO ──"
    if aws ecr describe-repositories --repository-names "$ECR_REPO" \
            --region "$AWS_REGION" >/dev/null 2>&1; then
        info "ECR repo already exists"
    else
        aws ecr create-repository \
            --repository-name "$ECR_REPO" \
            --region "$AWS_REGION" \
            --image-scanning-configuration scanOnPush=true \
            >/dev/null
        info "ECR repo created"
    fi
    ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
    export ECR_URI
    info "ECR URI: $ECR_URI"
}

# Pull upstream Flex Gateway image, tag, and push to ECR.
push_flex_image() {
    info "── Pulling + pushing Flex Gateway image ──"
    info "docker login to ECR"
    aws ecr get-login-password --region "$AWS_REGION" \
        | docker login --username AWS --password-stdin "$ECR_URI" >/dev/null

    info "Pulling $FLEX_IMAGE_SOURCE (linux/amd64) — this can take a few minutes"
    docker pull --platform linux/amd64 "$FLEX_IMAGE_SOURCE" >/dev/null

    docker tag "$FLEX_IMAGE_SOURCE" "${ECR_URI}:latest"
    info "Pushing to $ECR_URI:latest"
    docker push "${ECR_URI}:latest" >/dev/null
    info "Image push complete"
}

# ── IAM: task execution role ────────────────────────────────────────────────
ensure_exec_role() {
    info "── Ensuring task execution role: $EXEC_ROLE_NAME ──"
    if aws iam get-role --role-name "$EXEC_ROLE_NAME" >/dev/null 2>&1; then
        info "Role exists"
    else
        aws iam create-role --role-name "$EXEC_ROLE_NAME" \
            --assume-role-policy-document '{
              "Version":"2012-10-17",
              "Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]
            }' >/dev/null
        aws iam attach-role-policy --role-name "$EXEC_ROLE_NAME" \
            --policy-arn "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy" >/dev/null
        info "Role created + managed policy attached"
    fi

    # Inline policy: allow reading the MuleSoft secret at runtime
    aws iam put-role-policy --role-name "$EXEC_ROLE_NAME" \
        --policy-name "AllowMulesoftSecret" \
        --policy-document "$(cat <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["secretsmanager:GetSecretValue","secretsmanager:DescribeSecret"],
    "Resource": "arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:${MULESOFT_SECRET_ID}*"
  }]
}
POLICY
)" >/dev/null
    EXEC_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${EXEC_ROLE_NAME}"
    export EXEC_ROLE_ARN
    info "Role ARN: $EXEC_ROLE_ARN"
}

# ── Networking: default VPC + subnets + SG ──────────────────────────────────
ensure_networking() {
    info "── Discovering default VPC + public subnets ──"
    VPC_ID="$(aws ec2 describe-vpcs --region "$AWS_REGION" \
        --filters Name=isDefault,Values=true \
        --query "Vpcs[0].VpcId" --output text)"
    [[ -n "$VPC_ID" && "$VPC_ID" != "None" ]] \
        || die "No default VPC found in $AWS_REGION. Create one or set VPC_ID explicitly."

    SUBNETS=()
    while IFS= read -r s; do
        [[ -n "$s" ]] && SUBNETS+=("$s")
    done < <(aws ec2 describe-subnets --region "$AWS_REGION" \
        --filters Name=vpc-id,Values="$VPC_ID" Name=default-for-az,Values=true \
        --query "Subnets[].SubnetId" --output text | tr '\t' '\n')
    [[ ${#SUBNETS[@]} -ge 2 ]] \
        || die "Need >=2 default subnets for ALB, got ${#SUBNETS[@]}"

    info "VPC: $VPC_ID, subnets: ${SUBNETS[*]}"

    # Security group
    SG_ID="$(aws ec2 describe-security-groups --region "$AWS_REGION" \
        --filters Name=vpc-id,Values="$VPC_ID" Name=group-name,Values="$SG_NAME" \
        --query "SecurityGroups[0].GroupId" --output text 2>/dev/null || echo None)"
    if [[ "$SG_ID" == "None" || -z "$SG_ID" ]]; then
        SG_ID="$(aws ec2 create-security-group --region "$AWS_REGION" \
            --group-name "$SG_NAME" \
            --description "IR Flex Gateway task + ALB" \
            --vpc-id "$VPC_ID" --query GroupId --output text)"
        info "Created SG $SG_ID"
    else
        info "SG already exists: $SG_ID"
    fi

    # Idempotent ingress rule — port 80 from anywhere (ALB) + task port from itself
    aws ec2 authorize-security-group-ingress --region "$AWS_REGION" \
        --group-id "$SG_ID" --protocol tcp --port 80 --cidr 0.0.0.0/0 \
        >/dev/null 2>&1 || true
    aws ec2 authorize-security-group-ingress --region "$AWS_REGION" \
        --group-id "$SG_ID" --protocol tcp --port "$FLEX_CONTAINER_PORT" \
        --source-group "$SG_ID" >/dev/null 2>&1 || true

    export VPC_ID SG_ID
    SUBNETS_CSV="$(IFS=,; echo "${SUBNETS[*]}")"
    export SUBNETS_CSV
}

# ── ECS cluster + log group ─────────────────────────────────────────────────
ensure_cluster() {
    info "── Ensuring ECS cluster: $ECS_CLUSTER ──"
    local status
    status="$(aws ecs describe-clusters --region "$AWS_REGION" \
        --clusters "$ECS_CLUSTER" \
        --query "clusters[0].status" --output text 2>/dev/null || echo MISSING)"
    if [[ "$status" == "ACTIVE" ]]; then
        info "Cluster active"
    else
        aws ecs create-cluster --region "$AWS_REGION" \
            --cluster-name "$ECS_CLUSTER" \
            --capacity-providers FARGATE \
            --default-capacity-provider-strategy capacityProvider=FARGATE,weight=1 \
            >/dev/null
        info "Cluster created"
    fi

    aws logs describe-log-groups --region "$AWS_REGION" \
        --log-group-name-prefix "$LOG_GROUP" \
        --query "logGroups[?logGroupName=='$LOG_GROUP']" --output text \
        | grep -q "$LOG_GROUP" \
        || aws logs create-log-group --region "$AWS_REGION" \
            --log-group-name "$LOG_GROUP" >/dev/null
    info "Log group ready: $LOG_GROUP"
}

# ── Task definition ─────────────────────────────────────────────────────────
# Each MuleSoft credential field is injected as a container env var from
# Secrets Manager via the `secrets:` block. The JSON syntax:
#   valueFrom = "<secret-arn>:<json-key>::"
register_task_def() {
    info "── Registering task definition: $TASK_FAMILY ──"
    local secret_arn
    secret_arn="$(aws secretsmanager describe-secret \
        --secret-id "$MULESOFT_SECRET_ID" --region "$AWS_REGION" \
        --query ARN --output text)"

    local td_json
    td_json="$(cat <<JSON
{
  "family": "$TASK_FAMILY",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "$EXEC_ROLE_ARN",
  "containerDefinitions": [{
    "name": "$CONTAINER_NAME",
    "image": "${ECR_URI}:latest",
    "essential": true,
    "portMappings": [{"containerPort": $FLEX_CONTAINER_PORT, "protocol": "tcp"}],
    "environment": [
      {"name": "FLEX_LOG_LEVEL", "value": "info"},
      {"name": "FLEX_PORT",      "value": "$FLEX_CONTAINER_PORT"}
    ],
    "secrets": [
      {"name": "FLEX_RTMGR_ORG",           "valueFrom": "${secret_arn}:organization_id::"},
      {"name": "FLEX_RTMGR_ENV",           "valueFrom": "${secret_arn}:environment_id::"},
      {"name": "FLEX_RTMGR_CLIENT_ID",     "valueFrom": "${secret_arn}:client_id::"},
      {"name": "FLEX_RTMGR_CLIENT_SECRET", "valueFrom": "${secret_arn}:client_secret::"}
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group":         "$LOG_GROUP",
        "awslogs-region":        "$AWS_REGION",
        "awslogs-stream-prefix": "flex"
      }
    }
  }]
}
JSON
)"
    local tmp_td; tmp_td="$(mktemp)"
    printf '%s' "$td_json" > "$tmp_td"
    TASK_DEF_ARN="$(aws ecs register-task-definition --region "$AWS_REGION" \
        --cli-input-json "file://$tmp_td" \
        --query "taskDefinition.taskDefinitionArn" --output text)"
    rm -f "$tmp_td"
    export TASK_DEF_ARN
    info "Registered task def: $TASK_DEF_ARN"
}

# ── ALB + target group ──────────────────────────────────────────────────────
ensure_alb() {
    info "── Ensuring ALB: $ALB_NAME ──"
    ALB_ARN="$(aws elbv2 describe-load-balancers --region "$AWS_REGION" \
        --names "$ALB_NAME" --query "LoadBalancers[0].LoadBalancerArn" \
        --output text 2>/dev/null || echo None)"
    if [[ "$ALB_ARN" == "None" || -z "$ALB_ARN" ]]; then
        ALB_ARN="$(aws elbv2 create-load-balancer --region "$AWS_REGION" \
            --name "$ALB_NAME" \
            --subnets "${SUBNETS[@]}" \
            --security-groups "$SG_ID" \
            --scheme internet-facing \
            --type application \
            --query "LoadBalancers[0].LoadBalancerArn" --output text)"
        info "ALB created: $ALB_ARN"
    else
        info "ALB exists: $ALB_ARN"
    fi

    ALB_DNS="$(aws elbv2 describe-load-balancers --region "$AWS_REGION" \
        --load-balancer-arns "$ALB_ARN" \
        --query "LoadBalancers[0].DNSName" --output text)"
    info "ALB DNS: $ALB_DNS"

    # Target group
    TG_ARN="$(aws elbv2 describe-target-groups --region "$AWS_REGION" \
        --names "$TG_NAME" --query "TargetGroups[0].TargetGroupArn" \
        --output text 2>/dev/null || echo None)"
    if [[ "$TG_ARN" == "None" || -z "$TG_ARN" ]]; then
        TG_ARN="$(aws elbv2 create-target-group --region "$AWS_REGION" \
            --name "$TG_NAME" --protocol HTTP --port "$FLEX_CONTAINER_PORT" \
            --vpc-id "$VPC_ID" --target-type ip \
            --health-check-path "/" --health-check-interval-seconds 30 \
            --health-check-timeout-seconds 10 \
            --healthy-threshold-count 2 --unhealthy-threshold-count 5 \
            --matcher HttpCode=200-499 \
            --query "TargetGroups[0].TargetGroupArn" --output text)"
        info "Target group created: $TG_ARN"
    else
        info "Target group exists: $TG_ARN"
    fi

    # Listener
    local listener_arn
    listener_arn="$(aws elbv2 describe-listeners --region "$AWS_REGION" \
        --load-balancer-arn "$ALB_ARN" \
        --query "Listeners[?Port==\`80\`].ListenerArn" --output text 2>/dev/null || echo "")"
    if [[ -z "$listener_arn" ]]; then
        aws elbv2 create-listener --region "$AWS_REGION" \
            --load-balancer-arn "$ALB_ARN" \
            --protocol HTTP --port 80 \
            --default-actions "Type=forward,TargetGroupArn=$TG_ARN" \
            >/dev/null
        info "Listener :80 created"
    else
        info "Listener :80 exists"
    fi

    export ALB_ARN ALB_DNS TG_ARN
}

# ── ECS service ─────────────────────────────────────────────────────────────
ensure_service() {
    info "── Ensuring ECS service: $ECS_SERVICE ──"
    local svc_status
    svc_status="$(aws ecs describe-services --region "$AWS_REGION" \
        --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE" \
        --query "services[0].status" --output text 2>/dev/null || echo MISSING)"

    if [[ "$svc_status" == "ACTIVE" ]]; then
        info "Service exists — updating to latest task-def revision"
        aws ecs update-service --region "$AWS_REGION" \
            --cluster "$ECS_CLUSTER" --service "$ECS_SERVICE" \
            --task-definition "$TASK_DEF_ARN" \
            --force-new-deployment \
            >/dev/null
    else
        aws ecs create-service --region "$AWS_REGION" \
            --cluster "$ECS_CLUSTER" \
            --service-name "$ECS_SERVICE" \
            --task-definition "$TASK_DEF_ARN" \
            --desired-count 1 \
            --launch-type FARGATE \
            --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS_CSV],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
            --load-balancers "targetGroupArn=$TG_ARN,containerName=$CONTAINER_NAME,containerPort=$FLEX_CONTAINER_PORT" \
            >/dev/null
        info "Service created"
    fi
}

# ── Receipt ─────────────────────────────────────────────────────────────────
write_receipt() {
    printf 'http://%s\n' "$ALB_DNS" > "$GATEWAY_URL_FILE"
    info "Wrote gateway URL → $GATEWAY_URL_FILE"

    python3 - "$DEPLOY_JSON_FILE" "$AWS_ACCOUNT_ID" "$AWS_REGION" \
        "$ECR_URI" "$ECS_CLUSTER" "$ECS_SERVICE" "$TASK_DEF_ARN" \
        "$ALB_ARN" "$ALB_DNS" "$TG_ARN" "$VPC_ID" "$SG_ID" "$EXEC_ROLE_ARN" <<'PYEOF'
import json, sys, datetime
out = sys.argv[1]
keys = ["aws_account_id","aws_region","ecr_uri","ecs_cluster","ecs_service",
        "task_definition_arn","alb_arn","alb_dns","target_group_arn",
        "vpc_id","security_group_id","execution_role_arn"]
payload = {k: v for k, v in zip(keys, sys.argv[2:])}
payload["timestamp"]   = datetime.datetime.utcnow().isoformat() + "Z"
payload["gateway_url"] = f"http://{payload['alb_dns']}"
with open(out, "w") as f:
    json.dump(payload, f, indent=2)
PYEOF
    info "Wrote deploy inventory → $DEPLOY_JSON_FILE"
}

main() {
    info "── Flex Gateway deploy starting ──"
    load_mulesoft_secret       # fail fast if creds missing
    pre_flight
    ensure_ecr_repo
    push_flex_image
    ensure_exec_role
    ensure_networking
    ensure_cluster
    register_task_def
    ensure_alb
    ensure_service
    write_receipt
    info "── Flex Gateway deploy complete ──"
    info "ALB URL: http://${ALB_DNS}"
    info "NOTE: the ECS task takes ~3-5 minutes to register with the target group."
    info "      Verify with: curl -I http://${ALB_DNS}/"
}

main "$@"
