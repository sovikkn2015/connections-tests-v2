#!/usr/bin/env bash
# Repackage and redeploy the mulesoft-actions Lambda.
#
# Why bespoke: the root cause for needing AWS-CLI deploys is the same as for
# hitl-decision-bridge (local Python 3.10 tarfile bug). Re-run `sam deploy`
# from a Python 3.12 host to get the CF-managed path back.
set -euo pipefail

STACK=openclaw-mcp-006-v2
REGION=us-east-1
FUNCTION_NAME="${STACK}-mulesoft-actions"

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
SOURCE_DIR="${REPO_ROOT}/aws/mcp-servers/mulesoft-actions"

echo "==> Packaging Lambda from ${SOURCE_DIR}"
TMP=$(mktemp -d)
cp "${SOURCE_DIR}"/*.py "${TMP}/"
cp "${SOURCE_DIR}/requirements.txt" "${TMP}/" 2>/dev/null || true
ZIP_PATH="${TMP}/mulesoft-actions.zip"
(cd "${TMP}" && zip -q "${ZIP_PATH}" ./*.py requirements.txt 2>/dev/null || zip -q "${ZIP_PATH}" ./*.py)

echo "==> Updating Lambda code"
aws lambda update-function-code \
    --function-name "${FUNCTION_NAME}" \
    --region "${REGION}" \
    --zip-file "fileb://${ZIP_PATH}" \
    --query 'LastUpdateStatus' --output text >/dev/null
aws lambda wait function-updated \
    --function-name "${FUNCTION_NAME}" \
    --region "${REGION}"

rm -rf "${TMP}"
echo "Done."
