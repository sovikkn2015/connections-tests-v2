#!/bin/bash
# Configure Salesforce to AWS connection (Named Credential + External Credential + Remote Site)
# Run after SAM deploy: ./scripts/configure-aws-connection.sh <API_GATEWAY_ID> <API_KEY>
#
# Example:
#   ./scripts/configure-aws-connection.sh og256a1neb mySecureApiKey1234567890abcdef

set -e

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: ./scripts/configure-aws-connection.sh <API_GATEWAY_ID> <API_KEY>"
    echo ""
    echo "  API_GATEWAY_ID: From SAM deploy output (e.g., og256a1neb)"
    echo "  API_KEY:        The ApiKeyValue you used during sam deploy (20+ chars)"
    exit 1
fi

API_GATEWAY_ID=$1
API_KEY=$2

echo "=== Configuring Salesforce to AWS Connection ==="
echo "API Gateway: https://${API_GATEWAY_ID}.execute-api.us-east-1.amazonaws.com/prod"

TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

mkdir -p "$TEMP_DIR/externalCredentials" "$TEMP_DIR/namedCredentials" "$TEMP_DIR/remoteSiteSettings"

sed "s|REPLACE_WITH_YOUR_API_KEY|${API_KEY}|g" \
    force-app/main/default/externalCredentials/AWS_IR_API_Credential.externalCredential-meta.xml \
    > "$TEMP_DIR/externalCredentials/AWS_IR_API_Credential.externalCredential-meta.xml"

sed "s|REPLACE_WITH_YOUR_API_GATEWAY_ID|${API_GATEWAY_ID}|g" \
    force-app/main/default/namedCredentials/AWS_IR_API.namedCredential-meta.xml \
    > "$TEMP_DIR/namedCredentials/AWS_IR_API.namedCredential-meta.xml"

sed "s|REPLACE_WITH_YOUR_API_GATEWAY_ID|${API_GATEWAY_ID}|g" \
    force-app/main/default/remoteSiteSettings/AWS_IR_MCP_API.remoteSiteSetting-meta.xml \
    > "$TEMP_DIR/remoteSiteSettings/AWS_IR_MCP_API.remoteSiteSetting-meta.xml"

echo "Deploying External Credential..."
sf project deploy start --source-dir "$TEMP_DIR/externalCredentials" --wait 20

echo "Deploying Remote Site Setting..."
sf project deploy start --source-dir "$TEMP_DIR/remoteSiteSettings" --wait 20

echo "Deploying Named Credential..."
sf project deploy start --source-dir "$TEMP_DIR/namedCredentials" --wait 20

echo ""
echo "=== Done ==="
echo "REMAINING MANUAL STEP: Permission Set assignment"
echo "  Setup > Permission Sets > create or use existing > External Credential Principal Access"
echo "  Enable: AWS_IR_API_Credential - AWS_IR_API_Principal"
echo "  Assign to your user + Einstein Agent User"
