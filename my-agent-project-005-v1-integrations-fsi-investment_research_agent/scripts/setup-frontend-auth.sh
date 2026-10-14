#!/bin/bash
# Set up Salesforce Connected App for frontend OAuth2 PKCE + rebuild + deploy frontend
# Run after SAM deploy: ./scripts/setup-frontend-auth.sh [STACK_NAME]
set -e

STACK_NAME=${1:-ir-research-mcp}
REGION=${AWS_DEFAULT_REGION:-us-east-1}

echo "=== Setting Up Frontend Authentication ==="

CF_URL=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendUrl'].OutputValue" --output text)
CF_DOMAIN=$(echo "$CF_URL" | sed 's|https://||')

if [ -z "$CF_DOMAIN" ] || [ "$CF_DOMAIN" = "None" ]; then
    echo "ERROR: Could not find FrontendUrl in stack outputs."
    exit 1
fi
echo "CloudFront: $CF_DOMAIN"

# Deploy Connected App with correct callback URL
echo "Deploying Connected App..."
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT
mkdir -p "$TEMP_DIR/connectedApps"
sed "s|REPLACE_WITH_CLOUDFRONT_DOMAIN|${CF_DOMAIN}|g" \
    force-app/main/default/connectedApps/IR_Research_Workbench.connectedApp-meta.xml \
    > "$TEMP_DIR/connectedApps/IR_Research_Workbench.connectedApp-meta.xml"
sf project deploy start --source-dir "$TEMP_DIR/connectedApps" --wait 20

echo ""
echo "Connected App deployed. To complete setup:"
echo "  1. Setup > App Manager > IR Research Workbench > Manage Consumer Details"
echo "  2. Copy the Consumer Key"
echo "  3. Edit frontend/.env: VITE_SF_CLIENT_ID=<your key>"
echo "  4. Set VITE_SF_REDIRECT_URI=https://${CF_DOMAIN}/callback"
echo "  5. Run: ./scripts/deploy-frontend.sh"
