#!/usr/bin/env bash
# Create/update the V3 AgentCore runtime to point at the `v3-latest` ECR image.
#
# This script handles the runtime-creation + runtime-update portion of the
# AgentCore deploy. The image build + ECR push is a separate, prior step
# handled by `scripts/build-and-push-openclaw.sh` (also called by
# `deploy-all.sh` Wave 5 before this script).
#
# Idempotent: if a v3 runtime already exists, update it; otherwise create.
#
# Requires the image `${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/openclaw-agentcore:v3-latest`
# to already exist in ECR. If it doesn't, run
# `bash scripts/build-and-push-openclaw.sh` first.
#
# Env vars pulled from SSM at invoke time (AgentCore resolves them).
# Zero credentials in this script.

set -euo pipefail

REGION=us-east-1
ACCOUNT=875460787302
IMAGE_URI="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/openclaw-agentcore:v3-latest"
RUNTIME_NAME="openclaw_v3_agent"
ROLE_ARN="arn:aws:iam::${ACCOUNT}:role/AmazonBedrockAgentCoreSDKRuntime-us-east-1-a63986f981"

# Verify the image exists in ECR before attempting runtime update.
# A new user who skips the build step would otherwise hit
# ImageManifestNotFound at update-agent-runtime time.
if ! aws ecr describe-images \
       --repository-name openclaw-agentcore \
       --region "$REGION" \
       --image-ids imageTag=v3-latest \
       >/dev/null 2>&1; then
  echo "[create-v3-agentcore] ECR image ${IMAGE_URI} not found"
  echo "[create-v3-agentcore] Run: bash scripts/build-and-push-openclaw.sh"
  exit 2
fi

# Collect env from SSM (String, not SecureString — AgentCore doesn't decrypt)
MCP_API_KEY=$(aws ssm get-parameter --region "$REGION" --name /006-v3/mcp/api-key --with-decryption --query 'Parameter.Value' --output text)
MCP_API_URL="https://e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3"
AGENTCORE_SIGNING_KEY=$(aws ssm get-parameter --region "$REGION" --name /006-v3/agentcore/session-signing-key --with-decryption --query 'Parameter.Value' --output text)
HITL_SIGNING_KEY=$(aws ssm get-parameter --region "$REGION" --name /006-v3/hitl/signing_key --with-decryption --query 'Parameter.Value' --output text)
LANGFUSE_HOST=$(aws ssm get-parameter --region "$REGION" --name /006-v3/langfuse/host --query 'Parameter.Value' --output text)
LANGFUSE_PK=$(aws ssm get-parameter --region "$REGION" --name /006-v3/langfuse/public_key --with-decryption --query 'Parameter.Value' --output text)
LANGFUSE_SK=$(aws ssm get-parameter --region "$REGION" --name /006-v3/langfuse/secret_key --with-decryption --query 'Parameter.Value' --output text)
GUARDRAIL_ID=$(aws ssm get-parameter --region "$REGION" --name /006-v3/bedrock/guardrail-id --query 'Parameter.Value' --output text)
GUARDRAIL_VERSION=$(aws ssm get-parameter --region "$REGION" --name /006-v3/bedrock/guardrail-version --query 'Parameter.Value' --output text)

# Build environment variables JSON for the runtime
ENV_JSON=$(cat <<EOF
{
  "MCP_API_KEY": "$MCP_API_KEY",
  "MCP_API_URL": "$MCP_API_URL",
  "AGENTCORE_SESSION_SIGNING_KEY": "$AGENTCORE_SIGNING_KEY",
  "HITL_SIGNING_KEY": "$HITL_SIGNING_KEY",
  "LANGFUSE_BASE_URL": "$LANGFUSE_HOST",
  "LANGFUSE_PUBLIC_KEY": "$LANGFUSE_PK",
  "LANGFUSE_SECRET_KEY": "$LANGFUSE_SK",
  "BEDROCK_GUARDRAIL_ID": "$GUARDRAIL_ID",
  "BEDROCK_GUARDRAIL_VERSION": "$GUARDRAIL_VERSION",
  "AWS_REGION_BEDROCK": "$REGION",
  "BEDROCK_SONNET_MODEL_ID": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
  "BEDROCK_HAIKU_MODEL_ID": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
  "BEDROCK_KB_ID": "NBR5AFTREI",
  "OPENCLAW_DEV": "false",
  "MULESOFT_MODE": "mock"
}
EOF
)

# Check if runtime exists
EXISTING=$(aws bedrock-agentcore-control list-agent-runtimes --region "$REGION" \
  --query "agentRuntimes[?agentRuntimeName=='$RUNTIME_NAME'].agentRuntimeId" \
  --output text 2>&1 || echo "")

if [ -n "$EXISTING" ] && [ "$EXISTING" != "None" ]; then
  echo "Runtime $RUNTIME_NAME exists (id=$EXISTING), updating..."
  aws bedrock-agentcore-control update-agent-runtime \
    --region "$REGION" \
    --agent-runtime-id "$EXISTING" \
    --agent-runtime-artifact "containerConfiguration={containerUri=$IMAGE_URI}" \
    --role-arn "$ROLE_ARN" \
    --network-configuration "networkMode=PUBLIC" \
    --protocol-configuration "serverProtocol=HTTP" \
    --environment-variables "$ENV_JSON" \
    --output json > /tmp/agentcore-update.json
  RUNTIME_ID="$EXISTING"
else
  echo "Creating new runtime $RUNTIME_NAME..."
  aws bedrock-agentcore-control create-agent-runtime \
    --region "$REGION" \
    --agent-runtime-name "$RUNTIME_NAME" \
    --agent-runtime-artifact "containerConfiguration={containerUri=$IMAGE_URI}" \
    --role-arn "$ROLE_ARN" \
    --network-configuration "networkMode=PUBLIC" \
    --protocol-configuration "serverProtocol=HTTP" \
    --environment-variables "$ENV_JSON" \
    --output json > /tmp/agentcore-create.json
  RUNTIME_ID=$(python3 -c "import json;print(json.load(open('/tmp/agentcore-create.json'))['agentRuntimeId'])")
fi

echo "RUNTIME_ID=$RUNTIME_ID"

# Wait for READY
echo "Waiting for $RUNTIME_ID to reach READY..."
for i in $(seq 1 30); do
  STATE=$(aws bedrock-agentcore-control get-agent-runtime \
    --region "$REGION" --agent-runtime-id "$RUNTIME_ID" \
    --query 'status' --output text 2>&1 || echo "UNKNOWN")
  echo "attempt $i: $STATE"
  if [ "$STATE" = "READY" ]; then
    break
  fi
  if [ "$STATE" = "FAILED" ]; then
    echo "FAILED"
    aws bedrock-agentcore-control get-agent-runtime --region "$REGION" --agent-runtime-id "$RUNTIME_ID" > /tmp/agentcore-failed.json
    cat /tmp/agentcore-failed.json | python3 -m json.tool | head -30
    exit 1
  fi
  sleep 15
done

echo ""
echo "==> AgentCore v3 runtime READY"
ARN=$(aws bedrock-agentcore-control get-agent-runtime --region "$REGION" --agent-runtime-id "$RUNTIME_ID" --query 'agentRuntimeArn' --output text)
echo "AGENTCORE_AGENT_ARN=$ARN"
echo "$ARN" > /tmp/agentcore-v3-arn.txt
