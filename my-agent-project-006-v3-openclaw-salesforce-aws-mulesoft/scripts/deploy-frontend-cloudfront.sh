#!/usr/bin/env bash
# Host the V3 SPA on S3 (private) + CloudFront with Origin Access Control.
# The account has S3 Block Public Access on, so public website mode is off.
# CloudFront OAC is the production-correct path anyway.
#
# Idempotent: reuses bucket/OAC/distribution if they exist.

set -e

REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID=875460787302
BUCKET="${FRONTEND_BUCKET:-openclaw-v3-frontend-${ACCOUNT_ID}}"
OAC_NAME="${OAC_NAME:-openclaw-v3-oac}"
CALLER_REF="openclaw-v3-$(date +%s)"

cd "$(dirname "$0")/../frontend"
if [ ! -d dist ]; then
  echo "dist/ not present — run npm run build first" >&2
  exit 2
fi

# 1) bucket (private)
if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "[bucket] $BUCKET exists"
else
  echo "[bucket] creating $BUCKET..."
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null
fi

# 2) upload dist/
echo "[sync] uploading dist/ to s3://$BUCKET/"
aws s3 sync dist/ "s3://$BUCKET/" \
  --delete \
  --cache-control "max-age=3600" \
  --exclude "*.map"
aws s3 cp dist/index.html "s3://$BUCKET/index.html" \
  --cache-control "no-cache,no-store,must-revalidate" \
  --content-type "text/html; charset=utf-8"

# 3) OAC
OAC_ID=$(aws cloudfront list-origin-access-controls \
  --query "OriginAccessControlList.Items[?Name=='${OAC_NAME}'].Id" \
  --output text 2>/dev/null || echo "")
if [ -z "$OAC_ID" ] || [ "$OAC_ID" = "None" ]; then
  echo "[oac] creating $OAC_NAME..."
  cat > /tmp/oac.json <<EOF
{
  "Name": "${OAC_NAME}",
  "Description": "OAC for openclaw v3 frontend",
  "OriginAccessControlOriginType": "s3",
  "SigningBehavior": "always",
  "SigningProtocol": "sigv4"
}
EOF
  OAC_ID=$(aws cloudfront create-origin-access-control \
    --origin-access-control-config file:///tmp/oac.json \
    --query 'OriginAccessControl.Id' --output text)
fi
echo "[oac] id=$OAC_ID"

# 4) distribution (reuse existing if present)
DIST_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?contains(Comment, 'openclaw-v3-frontend')].Id | [0]" \
  --output text 2>/dev/null || echo "")

if [ -z "$DIST_ID" ] || [ "$DIST_ID" = "None" ]; then
  echo "[dist] creating CloudFront distribution..."
  cat > /tmp/dist.json <<EOF
{
  "CallerReference": "${CALLER_REF}",
  "Comment": "openclaw-v3-frontend demo",
  "Enabled": true,
  "DefaultRootObject": "index.html",
  "Origins": {
    "Quantity": 1,
    "Items": [{
      "Id": "s3-origin",
      "DomainName": "${BUCKET}.s3.${REGION}.amazonaws.com",
      "OriginAccessControlId": "${OAC_ID}",
      "S3OriginConfig": { "OriginAccessIdentity": "" },
      "ConnectionAttempts": 3,
      "ConnectionTimeout": 10,
      "OriginShield": { "Enabled": false },
      "CustomHeaders": { "Quantity": 0 }
    }]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "s3-origin",
    "ViewerProtocolPolicy": "redirect-to-https",
    "AllowedMethods": {
      "Quantity": 2,
      "Items": ["GET", "HEAD"],
      "CachedMethods": { "Quantity": 2, "Items": ["GET", "HEAD"] }
    },
    "Compress": true,
    "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
    "ResponseHeadersPolicyId": "60669652-455b-4ae9-85a4-c4c02393f86c",
    "SmoothStreaming": false,
    "TrustedSigners": { "Enabled": false, "Quantity": 0 },
    "TrustedKeyGroups": { "Enabled": false, "Quantity": 0 },
    "FieldLevelEncryptionId": "",
    "LambdaFunctionAssociations": { "Quantity": 0 },
    "FunctionAssociations": { "Quantity": 0 }
  },
  "CustomErrorResponses": {
    "Quantity": 1,
    "Items": [{
      "ErrorCode": 403,
      "ResponsePagePath": "/index.html",
      "ResponseCode": "200",
      "ErrorCachingMinTTL": 10
    }]
  },
  "PriceClass": "PriceClass_100",
  "ViewerCertificate": { "CloudFrontDefaultCertificate": true },
  "HttpVersion": "http2",
  "IsIPV6Enabled": true
}
EOF
  OUT=$(aws cloudfront create-distribution --distribution-config file:///tmp/dist.json)
  DIST_ID=$(echo "$OUT" | python3 -c "import json,sys;print(json.load(sys.stdin)['Distribution']['Id'])")
  DIST_DOMAIN=$(echo "$OUT" | python3 -c "import json,sys;print(json.load(sys.stdin)['Distribution']['DomainName'])")
else
  echo "[dist] reusing $DIST_ID"
  DIST_DOMAIN=$(aws cloudfront get-distribution --id "$DIST_ID" --query 'Distribution.DomainName' --output text)
fi
echo "[dist] id=$DIST_ID domain=$DIST_DOMAIN"

# 5) bucket policy granting CloudFront via OAC
DIST_ARN="arn:aws:cloudfront::${ACCOUNT_ID}:distribution/${DIST_ID}"
cat > /tmp/bp.json <<EOF
{
  "Version": "2008-10-17",
  "Id": "PolicyForCloudFrontOAC",
  "Statement": [{
    "Sid": "AllowCloudFrontServicePrincipal",
    "Effect": "Allow",
    "Principal": { "Service": "cloudfront.amazonaws.com" },
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::${BUCKET}/*",
    "Condition": {
      "StringEquals": { "AWS:SourceArn": "${DIST_ARN}" }
    }
  }]
}
EOF
aws s3api put-bucket-policy --bucket "$BUCKET" --policy file:///tmp/bp.json

# 6) cache invalidation for index.html so fresh SPA loads
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" \
  --query 'Invalidation.Id' --output text > /tmp/invalidation-id.txt
echo "[invalidation] id=$(cat /tmp/invalidation-id.txt)"

echo ""
echo "==> FRONTEND DEPLOYED"
echo "    URL: https://${DIST_DOMAIN}/"
echo "    S3 bucket: ${BUCKET}"
echo "    Distribution ID: ${DIST_ID}"
echo "    (First-time deploys take 5-8 min to propagate globally.)"
