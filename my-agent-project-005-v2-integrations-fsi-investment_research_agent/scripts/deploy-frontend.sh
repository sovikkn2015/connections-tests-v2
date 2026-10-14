#!/bin/bash
# Build and deploy the React frontend to S3 + CloudFront
# Run after SAM deploy: ./scripts/deploy-frontend.sh
#
# Prerequisites:
#   - SAM stack deployed (creates S3 bucket + CloudFront)
#   - frontend/.env configured with Salesforce OAuth details
#   - Node.js 20+ installed

set -e

STACK_NAME=${1:-ir-research-mcp}
REGION=${AWS_DEFAULT_REGION:-us-east-1}

echo "=== Building and Deploying Frontend ==="

# Get bucket name and CloudFront distribution from stack outputs
BUCKET=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" --output text)
CF_DOMAIN=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendUrl'].OutputValue" --output text)
CF_DIST_ID=$(aws cloudfront list-distributions --query "DistributionList.Items[?Comment=='IR Research Workbench - prod'].Id" --output text)

if [ -z "$BUCKET" ]; then
    echo "ERROR: Could not find FrontendBucketName in stack outputs."
    echo "Make sure the SAM stack is deployed with frontend resources."
    exit 1
fi

echo "S3 Bucket: $BUCKET"
echo "CloudFront: $CF_DOMAIN"

# Build frontend
echo "Building frontend..."
cd frontend
npm install
npm run build

# Sync to S3
echo "Uploading to S3..."
aws s3 sync dist/ "s3://$BUCKET/" --delete --region "$REGION"

# Invalidate CloudFront cache
if [ -n "$CF_DIST_ID" ]; then
    echo "Invalidating CloudFront cache..."
    aws cloudfront create-invalidation --distribution-id "$CF_DIST_ID" --paths "/*" --region "$REGION" > /dev/null
fi

echo ""
echo "=== Frontend Deployed ==="
echo "URL: $CF_DOMAIN"
echo ""
echo "NOTE: First CloudFront deployment takes 5-10 minutes to propagate."
