#!/usr/bin/env bash
# 007 Foundation - module-aligned CloudFormation deploy.
#
# Strict ordering (matches !ImportValue dependencies):
#   1. platform-common  (KMS, staging bucket) — base for every module
#   2. module stacks in parallel (no inter-module Imports, parallel-safe):
#        m1-identity, m10-audit-logger, m8-pipeline-engine, m13-fix-bridge,
#        execution-specialist, onboarding-specialist, memory-service
#   3. irsa  (IAM roles) — pulls ARNs from every module stack
#
# Each step is idempotent. Re-running with no changes produces no events.
# Destroy in reverse order: irsa -> modules -> platform-common.
# WORM bucket + audit DDB + M1 JWT secret are Retain — stack delete keeps them.

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
PREFIX="${PREFIX:-fsi007cf}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
EKS_OIDC_PROVIDER_ARN="${EKS_OIDC_PROVIDER_ARN:-}"

HERE="$(cd "$(dirname "$0")" && pwd)"

echo "[deploy] region=$REGION prefix=$PREFIX environment=$ENVIRONMENT"

deploy_stack() {
  local stack_name="$1"
  local template_file="$2"
  shift 2
  echo "[deploy] >>> $stack_name"
  aws cloudformation deploy \
    --region "$REGION" \
    --stack-name "$stack_name" \
    --template-file "$HERE/$template_file" \
    --capabilities CAPABILITY_NAMED_IAM \
    --no-fail-on-empty-changeset \
    --tags project=007 environment="$ENVIRONMENT" \
    --parameter-overrides \
      Prefix="$PREFIX" \
      Environment="$ENVIRONMENT" \
      "$@"
}

# ── Step 1: platform-common (base) ─────────────────────────────
deploy_stack "${PREFIX}-${ENVIRONMENT}-platform-common" platform-common.yaml

# ── Step 2: module stacks in parallel ──────────────────────────
MODULE_TEMPLATES=(
  m1-identity
  m10-audit-logger
  m8-pipeline-engine
  m13-fix-bridge
  execution-specialist
  onboarding-specialist
  memory-service
)

pids=()
for mod in "${MODULE_TEMPLATES[@]}"; do
  (
    deploy_stack "${PREFIX}-${ENVIRONMENT}-${mod}" "${mod}.yaml"
  ) &
  pids+=($!)
done

failed=0
for pid in "${pids[@]}"; do
  wait "$pid" || failed=1
done
if [[ $failed -ne 0 ]]; then
  echo "[deploy] one or more module stacks failed"
  exit 1
fi

# ── Step 3: IRSA (last, consumes module exports) ───────────────
if [[ -n "$EKS_OIDC_PROVIDER_ARN" ]]; then
  deploy_stack "${PREFIX}-${ENVIRONMENT}-irsa" irsa.yaml \
    EksOidcProviderArn="$EKS_OIDC_PROVIDER_ARN" \
    EksOidcIssuer="${EKS_OIDC_ISSUER:-}"
else
  echo "[deploy] EKS_OIDC_PROVIDER_ARN not set; skipping IRSA stack."
  echo "[deploy] Set it once you have an EKS cluster, then re-run."
fi

echo ""
echo "[deploy] done."
echo ""
echo "Stacks:"
aws cloudformation list-stacks --region "$REGION" \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query "StackSummaries[?starts_with(StackName, '${PREFIX}-${ENVIRONMENT}-')].[StackName,StackStatus,LastUpdatedTime]" \
  --output table
