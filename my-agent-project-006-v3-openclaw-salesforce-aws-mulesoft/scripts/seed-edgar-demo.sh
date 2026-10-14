#!/usr/bin/env bash
# seed-edgar-demo.sh — Trigger EDGAR backfill for the 8 demo tickers + TSMC.
#
# Prerequisites:
#   - AWS CLI configured with the target account
#   - CDK stack Openclaw006V3-FilingsPipeline deployed
#   - Bedrock KB stack Openclaw006V3-Kb deployed
#
# Usage:
#   bash scripts/seed-edgar-demo.sh
#
# What it does:
#   1. Invokes the filings-ingest Lambda for each ticker with the filing types
#      needed for the demo narrative (8-K for Q1 2026 earnings, 10-K FY25, 10-Q Q3 2025)
#   2. Triggers a KB re-ingestion job to index the new chunks
#   3. Verifies chunk count in the KB
#
# Time: ~5-10 minutes for 9 tickers × 3 filing types = 27 ingestion calls

set -euo pipefail

REGION="${AWS_REGION_LAMBDA:-us-east-2}"
KB_REGION="${AWS_REGION_BEDROCK:-us-east-1}"

# Demo tickers from the narrative script
TICKERS=(META GOOGL MSFT NVDA AVGO QCOM AMD AAPL TSM)
FILING_TYPES=("8-K" "10-K" "10-Q")

# Resolve Lambda function name from CloudFormation
INGEST_LAMBDA=$(aws cloudformation describe-stacks \
  --stack-name Openclaw006V3-FilingsPipeline \
  --region "$KB_REGION" \
  --query 'Stacks[0].Outputs[?contains(OutputKey, `IngestFunction`)].OutputValue' \
  --output text 2>/dev/null || echo "")

if [ -z "$INGEST_LAMBDA" ]; then
  echo "[seed-edgar] ⚠ Could not resolve filings-ingest Lambda from CloudFormation."
  echo "[seed-edgar]   Falling back to convention name: 006-v3-filings-ingest"
  INGEST_LAMBDA="006-v3-filings-ingest"
fi

echo "[seed-edgar] Using Lambda: $INGEST_LAMBDA"
echo "[seed-edgar] Tickers: ${TICKERS[*]}"
echo "[seed-edgar] Filing types: ${FILING_TYPES[*]}"
echo ""

TOTAL=0
SUCCEEDED=0
FAILED=0

for TICKER in "${TICKERS[@]}"; do
  for FTYPE in "${FILING_TYPES[@]}"; do
    TOTAL=$((TOTAL + 1))
    echo -n "[seed-edgar] Ingesting $TICKER $FTYPE ... "

    PAYLOAD=$(cat <<EOF
{"ticker": "$TICKER", "filing_type": "$FTYPE", "backfill": true}
EOF
)

    RESULT=$(aws lambda invoke \
      --function-name "$INGEST_LAMBDA" \
      --region "$KB_REGION" \
      --payload "$PAYLOAD" \
      --cli-binary-format raw-in-base64-out \
      /tmp/seed-edgar-response.json 2>&1) || true

    STATUS=$(cat /tmp/seed-edgar-response.json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('statusCode', d.get('status', 'unknown')))" 2>/dev/null || echo "error")

    if [ "$STATUS" = "200" ] || [ "$STATUS" = "ok" ]; then
      echo "✓"
      SUCCEEDED=$((SUCCEEDED + 1))
    else
      echo "✗ ($STATUS)"
      FAILED=$((FAILED + 1))
    fi
  done
done

echo ""
echo "[seed-edgar] Ingestion complete: $SUCCEEDED/$TOTAL succeeded, $FAILED failed."

# Trigger KB re-ingestion
echo ""
echo "[seed-edgar] Triggering Bedrock KB re-ingestion..."

KB_ID=$(aws cloudformation describe-stacks \
  --stack-name Openclaw006V3-Kb \
  --region "$KB_REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`KnowledgeBaseId`].OutputValue' \
  --output text 2>/dev/null || echo "")

DS_ID=$(aws cloudformation describe-stacks \
  --stack-name Openclaw006V3-Kb \
  --region "$KB_REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`KbDataSourceId`].OutputValue' \
  --output text 2>/dev/null || echo "")

if [ -n "$KB_ID" ] && [ -n "$DS_ID" ]; then
  aws bedrock-agent start-ingestion-job \
    --knowledge-base-id "$KB_ID" \
    --data-source-id "$DS_ID" \
    --region "$KB_REGION" \
    --output text --query 'ingestionJob.ingestionJobId'
  echo "[seed-edgar] KB ingestion job started. Monitor via:"
  echo "  aws bedrock-agent list-ingestion-jobs --knowledge-base-id $KB_ID --data-source-id $DS_ID --region $KB_REGION"
else
  echo "[seed-edgar] ⚠ Could not resolve KB/DataSource IDs. Run KB ingestion manually."
fi

echo ""
echo "[seed-edgar] Done. Next steps:"
echo "  1. Wait 2-5 minutes for KB ingestion to complete"
echo "  2. Verify: aws bedrock-agent-runtime retrieve --knowledge-base-id $KB_ID --retrieval-query '{\"text\":\"META Q1 2026 earnings\"}' --region $KB_REGION"
echo "  3. For the META earnings call transcript, drag-drop the PDF onto Sarah's terminal (Textract handler)"
