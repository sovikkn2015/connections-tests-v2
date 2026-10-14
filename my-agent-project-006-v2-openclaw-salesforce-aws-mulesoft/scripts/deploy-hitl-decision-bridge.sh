#!/usr/bin/env bash
# Deploy or refresh the hitl-decision-bridge Lambda + /prod/hitl/decision route.
#
# Why a bespoke script: local `sam build --use-container` hits the Python 3.10
# tarfile extraction-filter bug on this developer machine. Rather than force
# every engineer to swap Python versions, this script deploys the one new
# Lambda directly via AWS CLI. The SAM template still describes the final
# state for reproducibility - re-running `sam deploy` from a Python 3.12
# host is always valid.
#
# Usage:
#   ./scripts/deploy-hitl-decision-bridge.sh
#
# Idempotent: creates on first run, updates thereafter.
set -euo pipefail

STACK=openclaw-mcp-006-v2
REGION=us-east-1
FUNCTION_NAME="${STACK}-hitl-decision-bridge"
ROLE_NAME="${STACK}-hitl-decision-bridge-role"
API_ID=caodv9yori
STAGE=prod
FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-https://d2f1500216cuaw.cloudfront.net}"

# Salesforce env vars: read from existing salesforce-crm Lambda so they stay
# in sync. These are CloudFormation parameter values, not secrets.
SF_INSTANCE_URL=$(aws lambda get-function-configuration \
    --function-name "${STACK}-salesforce-crm" --region "${REGION}" \
    --query 'Environment.Variables.SF_INSTANCE_URL' --output text)
SF_ACCESS_TOKEN=$(aws lambda get-function-configuration \
    --function-name "${STACK}-salesforce-crm" --region "${REGION}" \
    --query 'Environment.Variables.SF_ACCESS_TOKEN' --output text)

MULESOFT_ACTIONS_URL="https://${API_ID}.execute-api.${REGION}.amazonaws.com/${STAGE}/mulesoft-actions"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
SOURCE_DIR="${REPO_ROOT}/aws/mcp-servers/hitl-decision-bridge"

# ---- 1. Package -----------------------------------------------------------
echo "==> Packaging Lambda from ${SOURCE_DIR}"
TMP=$(mktemp -d)
cp "${SOURCE_DIR}/app.py" "${TMP}/"
cp "${SOURCE_DIR}/requirements.txt" "${TMP}/"
ZIP_PATH="${TMP}/hitl-decision-bridge.zip"
(cd "${TMP}" && zip -q "${ZIP_PATH}" app.py requirements.txt)

# ---- 2. IAM role (create if missing) --------------------------------------
if ! aws iam get-role --role-name "${ROLE_NAME}" >/dev/null 2>&1; then
    echo "==> Creating IAM role ${ROLE_NAME}"
    aws iam create-role --role-name "${ROLE_NAME}" \
        --assume-role-policy-document '{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }' >/dev/null
    aws iam attach-role-policy --role-name "${ROLE_NAME}" \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    aws iam put-role-policy --role-name "${ROLE_NAME}" \
        --policy-name read-hitl-signing-key \
        --policy-document '{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
                "Resource": "arn:aws:secretsmanager:us-east-1:*:secret:/006-v2/hitl/*"
            }]
        }'
    echo "==> Waiting 10s for IAM propagation"
    sleep 10
fi

ROLE_ARN=$(aws iam get-role --role-name "${ROLE_NAME}" --query 'Role.Arn' --output text)

# ---- 3. Lambda (create or update) -----------------------------------------
ENV_VARS="Variables={CORS_ALLOW_ORIGIN=${FRONTEND_ORIGIN},MULESOFT_ACTIONS_URL=${MULESOFT_ACTIONS_URL},SF_INSTANCE_URL=${SF_INSTANCE_URL},SF_ACCESS_TOKEN=${SF_ACCESS_TOKEN},HITL_SECRET_NAME=/006-v2/hitl/signing-key}"

if aws lambda get-function --function-name "${FUNCTION_NAME}" --region "${REGION}" >/dev/null 2>&1; then
    echo "==> Updating existing Lambda ${FUNCTION_NAME}"
    aws lambda update-function-code \
        --function-name "${FUNCTION_NAME}" \
        --region "${REGION}" \
        --zip-file "fileb://${ZIP_PATH}" >/dev/null
    aws lambda wait function-updated \
        --function-name "${FUNCTION_NAME}" \
        --region "${REGION}"
    aws lambda update-function-configuration \
        --function-name "${FUNCTION_NAME}" \
        --region "${REGION}" \
        --timeout 15 --memory-size 128 \
        --environment "${ENV_VARS}" >/dev/null
else
    echo "==> Creating Lambda ${FUNCTION_NAME}"
    aws lambda create-function \
        --function-name "${FUNCTION_NAME}" \
        --region "${REGION}" \
        --runtime python3.12 \
        --role "${ROLE_ARN}" \
        --handler app.lambda_handler \
        --timeout 15 --memory-size 128 \
        --zip-file "fileb://${ZIP_PATH}" \
        --environment "${ENV_VARS}" \
        --tags Project=006-v2-fsi,Phase=6 >/dev/null
    aws lambda wait function-active \
        --function-name "${FUNCTION_NAME}" \
        --region "${REGION}"
fi

LAMBDA_ARN=$(aws lambda get-function --function-name "${FUNCTION_NAME}" \
    --region "${REGION}" --query 'Configuration.FunctionArn' --output text)

# ---- 4. API Gateway route (create /hitl/decision if absent) ---------------
ROOT_ID=$(aws apigateway get-resources --rest-api-id "${API_ID}" --region "${REGION}" \
    --query 'items[?path==`/`].id' --output text)

HITL_ID=$(aws apigateway get-resources --rest-api-id "${API_ID}" --region "${REGION}" \
    --query 'items[?path==`/hitl`].id' --output text 2>/dev/null || echo "")
if [[ -z "${HITL_ID}" || "${HITL_ID}" == "None" ]]; then
    echo "==> Creating /hitl resource"
    HITL_ID=$(aws apigateway create-resource \
        --rest-api-id "${API_ID}" --region "${REGION}" \
        --parent-id "${ROOT_ID}" --path-part "hitl" \
        --query 'id' --output text)
fi

DECISION_ID=$(aws apigateway get-resources --rest-api-id "${API_ID}" --region "${REGION}" \
    --query 'items[?path==`/hitl/decision`].id' --output text 2>/dev/null || echo "")
if [[ -z "${DECISION_ID}" || "${DECISION_ID}" == "None" ]]; then
    echo "==> Creating /hitl/decision resource"
    DECISION_ID=$(aws apigateway create-resource \
        --rest-api-id "${API_ID}" --region "${REGION}" \
        --parent-id "${HITL_ID}" --path-part "decision" \
        --query 'id' --output text)
fi

for METHOD in POST OPTIONS; do
    if ! aws apigateway get-method --rest-api-id "${API_ID}" --region "${REGION}" \
         --resource-id "${DECISION_ID}" --http-method "${METHOD}" >/dev/null 2>&1; then
        echo "==> Adding ${METHOD} /hitl/decision"
        aws apigateway put-method --rest-api-id "${API_ID}" --region "${REGION}" \
            --resource-id "${DECISION_ID}" --http-method "${METHOD}" \
            --authorization-type NONE --no-api-key-required >/dev/null
        aws apigateway put-integration --rest-api-id "${API_ID}" --region "${REGION}" \
            --resource-id "${DECISION_ID}" --http-method "${METHOD}" \
            --type AWS_PROXY --integration-http-method POST \
            --uri "arn:aws:apigateway:${REGION}:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations" >/dev/null
    fi
done

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
STATEMENT_ID="apigw-${API_ID}-hitl-decision"
if ! aws lambda get-policy --function-name "${FUNCTION_NAME}" --region "${REGION}" 2>/dev/null \
    | grep -q "${STATEMENT_ID}"; then
    echo "==> Granting API Gateway invoke permission"
    aws lambda add-permission \
        --function-name "${FUNCTION_NAME}" --region "${REGION}" \
        --statement-id "${STATEMENT_ID}" \
        --action lambda:InvokeFunction \
        --principal apigateway.amazonaws.com \
        --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*/*/hitl/decision" >/dev/null
fi

# ---- 5. Deploy the stage --------------------------------------------------
echo "==> Deploying stage ${STAGE}"
aws apigateway create-deployment \
    --rest-api-id "${API_ID}" --region "${REGION}" \
    --stage-name "${STAGE}" \
    --description "Add /hitl/decision route (Tier-4 #13)" >/dev/null

rm -rf "${TMP}"

echo
echo "Done."
echo "  Endpoint: https://${API_ID}.execute-api.${REGION}.amazonaws.com/${STAGE}/hitl/decision"
