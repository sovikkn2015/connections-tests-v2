#!/usr/bin/env bash
# ============================================================
# Create IAM execution role for AgentCore OpenClaw container
#
# This script is idempotent — safe to run multiple times.
# Creates the role and policy only if they don't already exist.
#
# Permissions granted:
#   - bedrock:InvokeModel          (LLM calls via Bedrock)
#   - secretsmanager:GetSecretValue (read credentials)
#   - logs:CreateLogGroup/Stream, logs:PutLogEvents (CloudWatch)
#
# Trust policy: bedrock-agentcore.amazonaws.com
#
# Usage:
#   ./setup-iam-role.sh
#
# Override region/account:
#   AWS_REGION=us-west-2 AWS_ACCOUNT_ID=123456789012 ./setup-iam-role.sh
# ============================================================

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:?Set AWS_ACCOUNT_ID}"
ROLE_NAME="agentcore-openclaw-execution-role"
POLICY_NAME="agentcore-openclaw-policy"
SECRET_NAME="openclaw-fsi-secrets"

echo "=== AgentCore IAM Role Setup ==="
echo "Region:  ${AWS_REGION}"
echo "Account: ${AWS_ACCOUNT_ID}"
echo "Role:    ${ROLE_NAME}"
echo ""

# ---------------------------------------------------------------------------
# Trust policy — allows AgentCore to assume this role
# ---------------------------------------------------------------------------
TRUST_POLICY=$(cat <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "bedrock-agentcore.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
)

# ---------------------------------------------------------------------------
# Step 1: Create the IAM role (if it doesn't exist)
# ---------------------------------------------------------------------------
echo "[1/3] Checking IAM role..."
if aws iam get-role --role-name "${ROLE_NAME}" &>/dev/null; then
    echo "Role '${ROLE_NAME}' already exists — updating trust policy..."
    aws iam update-assume-role-policy \
        --role-name "${ROLE_NAME}" \
        --policy-document "${TRUST_POLICY}"
else
    echo "Creating role '${ROLE_NAME}'..."
    aws iam create-role \
        --role-name "${ROLE_NAME}" \
        --assume-role-policy-document "${TRUST_POLICY}" \
        --description "Execution role for OpenClaw AgentCore container (Project 006)" \
        --tags Key=project,Value=006-openclaw-fsi Key=environment,Value=production
fi

# ---------------------------------------------------------------------------
# Step 2: Create and attach the permissions policy
# ---------------------------------------------------------------------------
echo "[2/3] Setting up permissions policy..."

POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/${POLICY_NAME}"

POLICY_DOC=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockInvoke",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:${AWS_REGION}::foundation-model/anthropic.*"
    },
    {
      "Sid": "SecretsManagerRead",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:${AWS_REGION}:${AWS_ACCOUNT_ID}:secret:${SECRET_NAME}-*"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:${AWS_REGION}:${AWS_ACCOUNT_ID}:log-group:/aws/agentcore/*"
    }
  ]
}
EOF
)

# Check if policy exists; create or update
if aws iam get-policy --policy-arn "${POLICY_ARN}" &>/dev/null; then
    echo "Policy '${POLICY_NAME}' exists — creating new version..."
    # Delete oldest non-default version if at limit (max 5 versions)
    OLDEST_VERSION=$(aws iam list-policy-versions \
        --policy-arn "${POLICY_ARN}" \
        --query 'Versions[?IsDefaultVersion==\`false\`] | [0].VersionId' \
        --output text 2>/dev/null || echo "None")
    if [ "${OLDEST_VERSION}" != "None" ] && [ "${OLDEST_VERSION}" != "" ]; then
        aws iam delete-policy-version \
            --policy-arn "${POLICY_ARN}" \
            --version-id "${OLDEST_VERSION}" 2>/dev/null || true
    fi
    aws iam create-policy-version \
        --policy-arn "${POLICY_ARN}" \
        --policy-document "${POLICY_DOC}" \
        --set-as-default
else
    echo "Creating policy '${POLICY_NAME}'..."
    aws iam create-policy \
        --policy-name "${POLICY_NAME}" \
        --policy-document "${POLICY_DOC}" \
        --description "Permissions for OpenClaw AgentCore (Bedrock + Secrets + Logs)" \
        --tags Key=project,Value=006-openclaw-fsi Key=environment,Value=production
fi

# ---------------------------------------------------------------------------
# Step 3: Attach policy to role
# ---------------------------------------------------------------------------
echo "[3/3] Attaching policy to role..."
aws iam attach-role-policy \
    --role-name "${ROLE_NAME}" \
    --policy-arn "${POLICY_ARN}" 2>/dev/null || true

ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${ROLE_NAME}"

echo ""
echo "=== IAM Role Ready ==="
echo "Role ARN: ${ROLE_ARN}"
echo ""
echo "This role is referenced in agentcore/agentcore-config.yaml as:"
echo "  executionRole: \"${ROLE_ARN}\""
echo ""
echo "Permissions:"
echo "  - bedrock:InvokeModel (Anthropic models in ${AWS_REGION})"
echo "  - secretsmanager:GetSecretValue (${SECRET_NAME})"
echo "  - logs:CreateLogGroup/Stream, logs:PutLogEvents (CloudWatch)"
