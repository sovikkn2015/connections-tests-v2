#!/bin/bash
# Configure Langfuse observability for both AWS Lambda agents and Salesforce Named Credential.
# Run after SAM deploy + Salesforce org setup:
#   ./scripts/configure-langfuse.sh <LANGFUSE_HOST> <PUBLIC_KEY> <SECRET_KEY>
#
# Example (Langfuse Cloud):
#   ./scripts/configure-langfuse.sh https://cloud.langfuse.com pk-lf-abc123 sk-lf-xyz789
#
# Example (self-hosted):
#   ./scripts/configure-langfuse.sh https://langfuse.mycompany.com pk-lf-abc123 sk-lf-xyz789

set -e

if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ]; then
    echo "Usage: ./scripts/configure-langfuse.sh <LANGFUSE_HOST> <PUBLIC_KEY> <SECRET_KEY>"
    echo ""
    echo "  LANGFUSE_HOST:  Langfuse URL (e.g., https://cloud.langfuse.com)"
    echo "  PUBLIC_KEY:     Langfuse public key (starts with pk-lf-)"
    echo "  SECRET_KEY:     Langfuse secret key (starts with sk-lf-)"
    echo ""
    echo "Get keys from: https://cloud.langfuse.com → Settings → API Keys"
    exit 1
fi

LANGFUSE_HOST=$1
PUBLIC_KEY=$2
SECRET_KEY=$3
REGION=${AWS_DEFAULT_REGION:-us-east-1}

echo "=== Configuring Langfuse Observability ==="
echo "Host: ${LANGFUSE_HOST}"
echo "Region: ${REGION}"
echo ""
# ---- Step 1: Update AWS Lambda functions ----
echo "--- Step 1: Updating AWS Lambda environment variables ---"
echo ""

# Get current env vars for financial-analysis and merge with Langfuse vars
echo "Updating ir-financial-analysis-prod..."
CURRENT_FA_ENV=$(aws lambda get-function-configuration \
    --function-name ir-financial-analysis-prod \
    --region "$REGION" \
    --query "Environment.Variables" \
    --output json 2>/dev/null || echo "{}")

UPDATED_FA_ENV=$(echo "$CURRENT_FA_ENV" | python3 -c "
import sys, json
env = json.load(sys.stdin)
env['LANGFUSE_HOST'] = '$LANGFUSE_HOST'
env['LANGFUSE_PUBLIC_KEY'] = '$PUBLIC_KEY'
env['LANGFUSE_SECRET_KEY'] = '$SECRET_KEY'
print(json.dumps({'Variables': env}))
")

aws lambda update-function-configuration \
    --function-name ir-financial-analysis-prod \
    --environment "$UPDATED_FA_ENV" \
    --region "$REGION" \
    --output text --query "FunctionName"

echo "Updating ir-sentiment-analysis-prod..."
CURRENT_SA_ENV=$(aws lambda get-function-configuration \
    --function-name ir-sentiment-analysis-prod \
    --region "$REGION" \
    --query "Environment.Variables" \
    --output json 2>/dev/null || echo "{}")

UPDATED_SA_ENV=$(echo "$CURRENT_SA_ENV" | python3 -c "
import sys, json
env = json.load(sys.stdin)
env['LANGFUSE_HOST'] = '$LANGFUSE_HOST'
env['LANGFUSE_PUBLIC_KEY'] = '$PUBLIC_KEY'
env['LANGFUSE_SECRET_KEY'] = '$SECRET_KEY'
print(json.dumps({'Variables': env}))
")

aws lambda update-function-configuration \
    --function-name ir-sentiment-analysis-prod \
    --environment "$UPDATED_SA_ENV" \
    --region "$REGION" \
    --output text --query "FunctionName"

echo "Lambda functions updated."
echo ""

# ---- Step 2: Deploy Langfuse Named Credential to Salesforce ----
echo "--- Step 2: Deploying Langfuse Named Credential to Salesforce ---"
echo ""

TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

mkdir -p "$TEMP_DIR/namedCredentials" "$TEMP_DIR/remoteSiteSettings"

# Replace placeholders in Named Credential (legacy Password protocol for Basic auth)
sed -e "s|https://REPLACE_WITH_LANGFUSE_HOST|${LANGFUSE_HOST}|g" \
    -e "s|REPLACE_WITH_LANGFUSE_PUBLIC_KEY|${PUBLIC_KEY}|g" \
    -e "s|REPLACE_WITH_LANGFUSE_SECRET_KEY|${SECRET_KEY}|g" \
    force-app/main/default/namedCredentials/Langfuse_API.namedCredential-meta.xml \
    > "$TEMP_DIR/namedCredentials/Langfuse_API.namedCredential-meta.xml"

# Create Remote Site Setting for Langfuse
printf '<?xml version="1.0" encoding="UTF-8"?>\n<RemoteSiteSetting xmlns="http://soap.sforce.com/2006/04/metadata">\n    <disableProtocolSecurity>false</disableProtocolSecurity>\n    <isActive>true</isActive>\n    <url>%s</url>\n</RemoteSiteSetting>\n' "${LANGFUSE_HOST}" \
    > "$TEMP_DIR/remoteSiteSettings/Langfuse_API.remoteSite-meta.xml"

echo "Deploying Named Credential (legacy Password protocol with Basic auth)..."
sf project deploy start --source-dir "$TEMP_DIR/namedCredentials" --wait 20

echo "Deploying Remote Site Setting..."
sf project deploy start --source-dir "$TEMP_DIR/remoteSiteSettings" --wait 20

echo ""
echo "=== Done ==="
echo ""
echo "REMAINING MANUAL STEPS:"
echo "  1. Verify: Check Langfuse dashboard for traces after running an agent query"
echo "     Dashboard: ${LANGFUSE_HOST}"
