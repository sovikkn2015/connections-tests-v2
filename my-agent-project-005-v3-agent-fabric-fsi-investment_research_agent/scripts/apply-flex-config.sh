#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# apply-flex-config.sh — V3-B committed path. Self-managed Flex Gateway.
#
# Replaces the manual flexctl register + Exchange asset publish steps with
# a static config bundle uploaded to S3 and mounted into the ECS task via a
# config-sync init container. No Anypoint API Manager registration required.
#
# Outputs:
#   agent-fabric/.flex-config-applied.json
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/_common.sh"

trap 'error "apply-flex-config.sh failed on line $LINENO"; exit 1' ERR

CONFIG_DIR="${V3_AGENT_FABRIC_DIR}/flex-config"
BUCKET="${FLEX_CONFIG_BUCKET:-ir-flex-gateway-config-${AWS_ACCOUNT_ID}}"
PREFIX="${FLEX_CONFIG_PREFIX:-v3-b}"
RECEIPT="${V3_AGENT_FABRIC_DIR}/.flex-config-applied.json"
ECS_CLUSTER="${ECS_CLUSTER:-ir-flex-gateway-cluster}"
ECS_SERVICE="${ECS_SERVICE:-ir-flex-gateway-svc}"
TASK_FAMILY="${TASK_FAMILY:-ir-flex-gateway-task}"
EXEC_ROLE_NAME="${EXEC_ROLE_NAME:-ir-flex-gateway-task-exec}"

[[ -d "$CONFIG_DIR" ]] || die "Config dir missing: $CONFIG_DIR"

ensure_bucket() {
    info "── Ensuring S3 bucket: $BUCKET ──"
    if aws s3api head-bucket --bucket "$BUCKET" --region "$AWS_REGION" 2>/dev/null; then
        info "Bucket exists"
    else
        if [[ "$AWS_REGION" == "us-east-1" ]]; then
            aws s3api create-bucket --bucket "$BUCKET" --region "$AWS_REGION" >/dev/null
        else
            aws s3api create-bucket --bucket "$BUCKET" --region "$AWS_REGION" \
                --create-bucket-configuration "LocationConstraint=$AWS_REGION" >/dev/null
        fi
        aws s3api put-public-access-block --bucket "$BUCKET" \
            --public-access-block-configuration \
            "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" >/dev/null
        info "Bucket created and locked down"
    fi
}

upload_config() {
    info "── Uploading config files to s3://${BUCKET}/${PREFIX}/ ──"
    local tmp; tmp="$(mktemp -d)"
    cp "$CONFIG_DIR"/*.yaml "$tmp/"
    rm -f "$tmp/policy-header-injection.yaml"
    aws s3 sync "$tmp/" "s3://${BUCKET}/${PREFIX}/" \
        --region "$AWS_REGION" --delete >/dev/null
    rm -rf "$tmp"
    info "Uploaded $(ls "$CONFIG_DIR"/*.yaml | wc -l | tr -d ' ') files (minus header-injection)"
}

grant_task_role_s3() {
    info "── Granting S3 read to task execution role ──"
    aws iam put-role-policy --role-name "$EXEC_ROLE_NAME" \
        --policy-name "AllowFlexConfigBucket" \
        --policy-document "$(cat <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:GetObject","s3:ListBucket"],
    "Resource": [
      "arn:aws:s3:::${BUCKET}",
      "arn:aws:s3:::${BUCKET}/*"
    ]
  }]
}
POLICY
)" >/dev/null
    info "S3 read policy attached"
}

register_new_task_def() {
    info "── Registering new task def with config-sync init container ──"
    local secret_arn
    secret_arn="$(aws secretsmanager describe-secret \
        --secret-id "$MULESOFT_SECRET_ID" --region "$AWS_REGION" \
        --query ARN --output text)"
    local exec_role_arn="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${EXEC_ROLE_NAME}"

    local task_def
    task_def="$(cat <<JSON
{
  "family": "$TASK_FAMILY",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "$exec_role_arn",
  "taskRoleArn": "$exec_role_arn",
  "volumes": [{"name": "flex-conf", "host": {}}],
  "containerDefinitions": [
    {
      "name": "config-sync",
      "image": "public.ecr.aws/aws-cli/aws-cli:latest",
      "essential": false,
      "command": [
        "s3","sync",
        "s3://${BUCKET}/${PREFIX}/","/shared/",
        "--region","${AWS_REGION}"
      ],
      "mountPoints": [{"sourceVolume":"flex-conf","containerPath":"/shared"}],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {"awslogs-group":"/ecs/ir-flex-gateway","awslogs-region":"$AWS_REGION","awslogs-stream-prefix":"config-sync"}
      }
    },
    {
      "name": "flex-gateway",
      "image": "875460787302.dkr.ecr.${AWS_REGION}.amazonaws.com/ir-flex-gateway:latest",
      "essential": true,
      "dependsOn": [{"containerName":"config-sync","condition":"SUCCESS"}],
      "portMappings": [{"containerPort": 8081, "protocol": "tcp"}],
      "environment": [
        {"name": "FLEX_LOG_LEVEL", "value": "info"},
        {"name": "FLEX_PORT",      "value": "8081"}
      ],
      "mountPoints": [{"sourceVolume":"flex-conf","containerPath":"/etc/mulesoft/flex-gateway/conf.d/custom"}],
      "secrets": [
        {"name": "FLEX_RTMGR_ORG",           "valueFrom": "${secret_arn}:organization_id::"},
        {"name": "FLEX_RTMGR_ENV",           "valueFrom": "${secret_arn}:environment_id::"},
        {"name": "FLEX_RTMGR_CLIENT_ID",     "valueFrom": "${secret_arn}:client_id::"},
        {"name": "FLEX_RTMGR_CLIENT_SECRET", "valueFrom": "${secret_arn}:client_secret::"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {"awslogs-group":"/ecs/ir-flex-gateway","awslogs-region":"$AWS_REGION","awslogs-stream-prefix":"flex"}
      }
    }
  ]
}
JSON
)"
    local tmp; tmp="$(mktemp)"
    printf '%s' "$task_def" > "$tmp"
    TASK_DEF_ARN="$(aws ecs register-task-definition --region "$AWS_REGION" \
        --cli-input-json "file://$tmp" \
        --query "taskDefinition.taskDefinitionArn" --output text)"
    rm -f "$tmp"
    export TASK_DEF_ARN
    info "New task def: $TASK_DEF_ARN"
}

update_service() {
    info "── Updating ECS service + enabling execute-command ──"
    aws ecs update-service --region "$AWS_REGION" \
        --cluster "$ECS_CLUSTER" --service "$ECS_SERVICE" \
        --task-definition "$TASK_DEF_ARN" \
        --enable-execute-command \
        --force-new-deployment >/dev/null
    info "Waiting up to 4 min for service-stable..."
    aws ecs wait services-stable --region "$AWS_REGION" \
        --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE" 2>/dev/null || warn "services-stable timed out"
}

verify() {
    info "── Verifying ──"
    LAST_RUNNING_COUNT="$(aws ecs describe-services --region "$AWS_REGION" \
        --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE" \
        --query 'services[0].runningCount' --output text)"
    info "runningCount=$LAST_RUNNING_COUNT"
    local alb_url
    alb_url="$(cat "${V3_AGENT_FABRIC_DIR}/.gateway-url.txt" 2>/dev/null || echo unknown)"
    LAST_CURL_CODE="$(curl -sS -o /dev/null -w "%{http_code}" --max-time 15 "$alb_url/" 2>&1 || echo 000)"
    info "curl $alb_url/ -> HTTP $LAST_CURL_CODE"
    export LAST_CURL_CODE LAST_RUNNING_COUNT
}

write_receipt() {
    python3 - "$RECEIPT" "$TASK_DEF_ARN" "$BUCKET" "$PREFIX" \
        "$LAST_RUNNING_COUNT" "$LAST_CURL_CODE" <<'PYEOF'
import json, sys, datetime
out, td, bucket, prefix, running, code = sys.argv[1:]
receipt = {
  "timestamp":        datetime.datetime.utcnow().isoformat() + "Z",
  "task_definition":  td,
  "config_bucket":    bucket,
  "config_prefix":    prefix,
  "running_count":    int(running) if running.isdigit() else running,
  "alb_probe_status": int(code) if code.isdigit() else code,
  "mode":             "self-managed-static-config",
  "notes":            "Flex Gateway in self-managed mode. Config synced from S3 by an init container. No Anypoint API Manager registration required. Agent Fabric Registry skipped (Developer/Trial subscription).",
}
with open(out, "w") as f:
    json.dump(receipt, f, indent=2)
PYEOF
    info "Wrote receipt: $RECEIPT"
}

main() {
    info "── apply-flex-config.sh (V3-B) starting ──"
    load_mulesoft_secret
    ensure_bucket
    upload_config
    grant_task_role_s3
    register_new_task_def
    update_service
    verify
    write_receipt
    info "── apply-flex-config.sh complete ──"
    info "  ECS runningCount=$LAST_RUNNING_COUNT  ALB probe=$LAST_CURL_CODE"
}

main "$@"
