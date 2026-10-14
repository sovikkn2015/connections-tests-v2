#!/usr/bin/env bash
# Build the OpenClaw AgentCore container image and push to ECR.
#
# This is the FIRST half of the AgentCore deploy (the runtime update lives in
# `create-v3-agentcore.sh`). Called automatically from `deploy-all.sh` Wave 5
# and can also be re-run standalone whenever backend Python changes.
#
# Prerequisites:
#   - finch or docker available in PATH
#   - AWS credentials with `ecr:CreateRepository`, `ecr:PutImage` in target
#     account/region
#   - The openclaw/ source tree at repo root (already present in the repo)
#
# Idempotent:
#   - Creates the ECR repo if it doesn't exist
#   - Builds for linux/arm64 (AgentCore requires arm64)
#   - Pushes the `v3-latest` tag (mutable; callers that need a pin should
#     tag explicitly with a date/sha after this step)
#
# Exit codes:
#   0  success
#   1  prerequisite missing (finch/docker, AWS creds)
#   2  build or push failure

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

REGION="${AWS_REGION_BEDROCK:-${AWS_REGION:-us-east-1}}"
ACCOUNT="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text 2>/dev/null || true)}"
REPO_NAME="${OPENCLAW_ECR_REPO:-openclaw-agentcore}"
IMAGE_TAG="${OPENCLAW_IMAGE_TAG:-v3-latest}"
IMAGE_URI="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}:${IMAGE_TAG}"

log() { printf '[build-openclaw] %s\n' "$*"; }
fail() { printf '[build-openclaw] ERROR: %s\n' "$*" >&2; exit "${2:-2}"; }

# ---------------------------------------------------------------------------
# 1. Pick a container builder. Prefer finch (AgentCore-native on macOS arm64)
#    then docker.
# ---------------------------------------------------------------------------
if command -v finch >/dev/null 2>&1; then
  BUILDER="finch"
elif command -v docker >/dev/null 2>&1; then
  BUILDER="docker"
else
  fail "neither finch nor docker found in PATH — install one (brew install finch)" 1
fi
log "using builder: $BUILDER"

# ---------------------------------------------------------------------------
# 2. Verify AWS creds + account ID
# ---------------------------------------------------------------------------
if [[ -z "${ACCOUNT:-}" ]]; then
  fail "cannot resolve AWS account — set AWS_ACCOUNT_ID or run 'aws configure'" 1
fi
log "account=$ACCOUNT region=$REGION image=$IMAGE_URI"

# ---------------------------------------------------------------------------
# 3. Ensure ECR repo exists
# ---------------------------------------------------------------------------
if ! aws ecr describe-repositories --repository-names "$REPO_NAME" \
       --region "$REGION" >/dev/null 2>&1; then
  log "ECR repo $REPO_NAME missing — creating with scan-on-push enabled"
  aws ecr create-repository \
    --repository-name "$REPO_NAME" \
    --region "$REGION" \
    --image-scanning-configuration scanOnPush=true \
    --image-tag-mutability MUTABLE \
    >/dev/null
else
  log "ECR repo $REPO_NAME exists"
fi

# ---------------------------------------------------------------------------
# 4. ECR login
# ---------------------------------------------------------------------------
log "logging in to ECR..."
aws ecr get-login-password --region "$REGION" \
  | "$BUILDER" login --username AWS --password-stdin "${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

# ---------------------------------------------------------------------------
# 5. Build for linux/arm64 (AgentCore requirement)
# ---------------------------------------------------------------------------
log "building image for linux/arm64 from $REPO_ROOT ..."
(
  cd "$REPO_ROOT"
  "$BUILDER" build \
    --platform linux/arm64 \
    -t "${REPO_NAME}:${IMAGE_TAG}" \
    .
)

# ---------------------------------------------------------------------------
# 6. Tag + push
# ---------------------------------------------------------------------------
log "tagging + pushing ${IMAGE_URI} ..."
"$BUILDER" tag "${REPO_NAME}:${IMAGE_TAG}" "$IMAGE_URI"
"$BUILDER" push "$IMAGE_URI"

# ---------------------------------------------------------------------------
# 7. Verify digest landed
# ---------------------------------------------------------------------------
log "verifying image in ECR..."
DIGEST=$(aws ecr describe-images \
  --repository-name "$REPO_NAME" \
  --region "$REGION" \
  --image-ids imageTag="$IMAGE_TAG" \
  --query 'imageDetails[0].imageDigest' \
  --output text 2>/dev/null || echo "")

if [[ -z "$DIGEST" || "$DIGEST" == "None" ]]; then
  fail "push appeared to succeed but describe-images returned no digest" 2
fi

log "success — digest $DIGEST"
log "next step: bash scripts/create-v3-agentcore.sh  (updates runtime to pull this image)"
