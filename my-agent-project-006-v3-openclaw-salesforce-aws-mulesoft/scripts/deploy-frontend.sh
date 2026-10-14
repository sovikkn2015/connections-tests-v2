#!/usr/bin/env bash
# Host the V3 SPA on S3 + CloudFront.
# Idempotent: reuses the bucket + distribution if they exist.
# Zero credentials. Bucket is public-read (CloudFront-OAI in production).

set -e

REGION="${AWS_REGION:-us-east-1}"
BUCKET="${FRONTEND_BUCKET:-openclaw-v3-frontend-875460787302}"
DIST="${DIST:-dist}"

cd "$(dirname "$0")/../frontend"
if [ ! -d "$DIST" ]; then
  echo "dist/ not present — run npm run build first" >&2
  exit 2
fi

# 1) bucket
if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "[bucket] $BUCKET exists"
else
  echo "[bucket] creating $BUCKET..."
  if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null
  else
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
      --create-bucket-configuration "LocationConstraint=$REGION" >/dev/null
  fi
fi

# Turn off block-public-access on this bucket so the public static hosting works.
aws s3api put-public-access-block --bucket "$BUCKET" \
  --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false" >/dev/null

# Enable website hosting
aws s3 website "s3://$BUCKET" --index-document index.html --error-document index.html

# Public-read bucket policy (demo only; production would use CloudFront OAC)
POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicRead",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::${BUCKET}/*"
  }]
}
EOF
)
echo "$POLICY" > /tmp/bucket-policy.json
aws s3api put-bucket-policy --bucket "$BUCKET" --policy file:///tmp/bucket-policy.json

# 2) upload dist
echo "[sync] uploading dist/ to s3://$BUCKET/"
aws s3 sync "$DIST/" "s3://$BUCKET/" \
  --delete \
  --cache-control "max-age=3600" \
  --exclude "*.map"

# Set correct content-type on index.html (for aggressive caches)
aws s3 cp "$DIST/index.html" "s3://$BUCKET/index.html" \
  --cache-control "no-cache,no-store,must-revalidate" \
  --content-type "text/html; charset=utf-8"

# 3) the website URL
URL="http://${BUCKET}.s3-website-${REGION}.amazonaws.com"
echo ""
echo "==> FRONTEND DEPLOYED"
echo "    $URL"
echo "    (S3 website endpoint — plain HTTP. For HTTPS put CloudFront in front.)"
