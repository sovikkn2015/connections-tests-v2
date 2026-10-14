#!/usr/bin/env bash
# ============================================================
# Rotate Salesforce Access Token in AWS Secrets Manager
#
# Gets a fresh SF access token via the Salesforce CLI and
# updates the Secrets Manager secret with the new value.
#
# Usage:
#   ./rotate-sf-token.sh
#
# Override defaults:
#   AWS_REGION=us-west-2 SF_TARGET_ORG=my-org SECRET_NAME=my-secret ./rotate-sf-token.sh
#
# Schedule via cron (daily at 2am):
#   0 2 * * * /path/to/rotate-sf-token.sh >> /var/log/sf-token-rotation.log 2>&1
#
# Schedule via EventBridge (CloudFormation):
#   Type: AWS::Events::Rule
#   Properties:
#     ScheduleExpression: "rate(12 hours)"
#     Targets:
#       - Arn: !GetAtt RotationLambda.Arn
#
# Prerequisites:
#   - Salesforce CLI (sf) installed and authenticated
#   - AWS CLI configured with permissions to update Secrets Manager
#   - jq installed
# ============================================================

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
SECRET_NAME="${SECRET_NAME:-openclaw-fsi-secrets}"
SF_TARGET_ORG="${SF_TARGET_ORG:-new-org}"

echo "=== SF Token Rotation ==="
echo "Region:     ${AWS_REGION}"
echo "Secret:     ${SECRET_NAME}"
echo "SF Org:     ${SF_TARGET_ORG}"
echo "Timestamp:  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Get fresh SF access token from Salesforce CLI
# ---------------------------------------------------------------------------
echo "[1/3] Getting fresh access token from Salesforce CLI..."

SF_ORG_INFO=$(sf org display --target-org "${SF_TARGET_ORG}" --json 2>&1)

SF_ACCESS_TOKEN=$(echo "${SF_ORG_INFO}" | jq -r '.result.accessToken')
SF_INSTANCE_URL=$(echo "${SF_ORG_INFO}" | jq -r '.result.instanceUrl')

if [ -z "${SF_ACCESS_TOKEN}" ] || [ "${SF_ACCESS_TOKEN}" = "null" ]; then
  echo "ERROR: Failed to get access token. SF CLI output:"
  echo "${SF_ORG_INFO}"
  exit 1
fi

echo "  Access token obtained (${#SF_ACCESS_TOKEN} chars)"
echo "  Instance URL: ${SF_INSTANCE_URL}"

# ---------------------------------------------------------------------------
# Step 2: Read current secret and merge new token
# ---------------------------------------------------------------------------
echo "[2/3] Reading current secret from Secrets Manager..."

CURRENT_SECRET=$(aws secretsmanager get-secret-value \
  --secret-id "${SECRET_NAME}" \
  --region "${AWS_REGION}" \
  --query 'SecretString' \
  --output text 2>&1)

if [ $? -ne 0 ]; then
  echo "ERROR: Failed to read secret. AWS CLI output:"
  echo "${CURRENT_SECRET}"
  exit 1
fi

UPDATED_SECRET=$(echo "${CURRENT_SECRET}" | jq \
  --arg token "${SF_ACCESS_TOKEN}" \
  --arg url "${SF_INSTANCE_URL}" \
  '.SF_ACCESS_TOKEN = $token | .SF_INSTANCE_URL = $url')

# ---------------------------------------------------------------------------
# Step 3: Update the secret
# ---------------------------------------------------------------------------
echo "[3/3] Updating secret in Secrets Manager..."

aws secretsmanager put-secret-value \
  --secret-id "${SECRET_NAME}" \
  --secret-string "${UPDATED_SECRET}" \
  --region "${AWS_REGION}" \
  > /dev/null 2>&1

if [ $? -ne 0 ]; then
  echo "ERROR: Failed to update secret."
  exit 1
fi

echo ""
echo "=== Token rotation complete ==="
echo "  SF_ACCESS_TOKEN: updated"
echo "  SF_INSTANCE_URL: ${SF_INSTANCE_URL}"
echo "  Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
