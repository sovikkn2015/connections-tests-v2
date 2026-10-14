#!/bin/bash
# ──────────────────────────────────────────────────────────────────────
# Build and deploy the Wealth Advisor Workbench frontend to S3 + CloudFront.
#
# Usage:
#   ./scripts/deploy-frontend.sh              # uses default stack name
#   ./scripts/deploy-frontend.sh my-stack      # custom stack name
#
# Prerequisites:
#   1. SAM stack deployed:
#      cd aws && sam build && sam deploy --guided
#   2. frontend/.env configured (copy from .env.example)
#   3. Node.js 20+, AWS CLI 2.x
# ──────────────────────────────────────────────────────────────────────
set -e

STACK_NAME=${1:-wa-workbench}
REGION=${AWS_DEFAULT_REGION:-us-east-1}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo "══════════════════════════════════════════════════"
echo "  Wealth Advisor Workbench — Frontend Deploy"
echo "══════════════════════════════════════════════════"
echo ""
echo "Stack:  $STACK_NAME"
echo "Region: $REGION"
echo ""

# ── 1. Read stack outputs ──
echo "[1/5] Reading CloudFormation stack outputs..."

BUCKET=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
    --output text 2>/dev/null)

CF_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendUrl'].OutputValue" \
    --output text 2>/dev/null)

CF_DIST_ID=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='CloudFrontDistributionId'].OutputValue" \
    --output text 2>/dev/null)

API_URL=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey=='ApiGatewayUrl'].OutputValue" \
    --output text 2>/dev/null)

if [ -z "$BUCKET" ] || [ "$BUCKET" = "None" ]; then
    echo "ERROR: Could not find FrontendBucketName in stack '$STACK_NAME'."
    echo "Deploy the SAM stack first:"
    echo "  cd aws && sam build && sam deploy --stack-name $STACK_NAME --capabilities CAPABILITY_IAM --resolve-s3"
    exit 1
fi

echo "  S3 Bucket:    $BUCKET"
echo "  CloudFront:   $CF_URL"
echo "  Distribution: $CF_DIST_ID"
echo "  API Gateway:  $API_URL"
echo ""

# ── 2. Check .env exists ──
echo "[2/5] Checking frontend configuration..."
if [ ! -f "$PROJECT_DIR/frontend/.env" ]; then
    echo "WARNING: frontend/.env not found. Creating from .env.example..."
    if [ -f "$PROJECT_DIR/frontend/.env.example" ]; then
        cp "$PROJECT_DIR/frontend/.env.example" "$PROJECT_DIR/frontend/.env"
        echo "  Created frontend/.env — edit it with your Salesforce credentials."
        echo "  Required: VITE_SF_CLIENT_ID, VITE_SF_REDIRECT_URI ($CF_URL/callback)"
        echo "  Then re-run this script."
        exit 1
    else
        echo "ERROR: No .env.example found either. Create frontend/.env manually."
        exit 1
    fi
fi
echo "  frontend/.env found."
echo ""

# ── 3. Build frontend ──
echo "[3/5] Building frontend..."
cd "$PROJECT_DIR/frontend"
npm install --silent
npm run build
echo "  Build complete: $(du -sh dist | cut -f1) in dist/"
echo ""

# ── 4. Sync to S3 ──
echo "[4/5] Uploading to S3..."
aws s3 sync dist/ "s3://$BUCKET/" --delete --region "$REGION" --quiet
echo "  Synced to s3://$BUCKET/"
echo ""

# ── 5. Invalidate CloudFront cache ──
if [ -n "$CF_DIST_ID" ] && [ "$CF_DIST_ID" != "None" ]; then
    echo "[5/5] Invalidating CloudFront cache..."
    INVALIDATION_ID=$(aws cloudfront create-invalidation \
        --distribution-id "$CF_DIST_ID" \
        --paths "/*" \
        --query "Invalidation.Id" \
        --output text 2>/dev/null)
    echo "  Invalidation: $INVALIDATION_ID"
else
    echo "[5/5] Skipping CloudFront invalidation (no distribution ID)."
fi

echo ""
echo "══════════════════════════════════════════════════"
echo "  Deploy complete!"
echo ""
echo "  URL: $CF_URL"
echo ""
echo "  First deploy takes 5-10 min for CloudFront propagation."
echo "══════════════════════════════════════════════════"
echo ""
