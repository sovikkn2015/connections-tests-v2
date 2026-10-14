#!/bin/bash
# Configure Sentiment Analysis Agent with News API connection
# Run after SAM deploy: ./scripts/configure-sentiment-agent.sh <API_GATEWAY_ID> <API_KEY>

set -e

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: ./scripts/configure-sentiment-agent.sh <API_GATEWAY_ID> <API_KEY>"
    echo "  API_GATEWAY_ID: From SAM deploy output (e.g., og256a1neb)"
    echo "  API_KEY:        The ApiKeyValue you used during sam deploy"
    exit 1
fi

NEWS_URL="https://${1}.execute-api.us-east-1.amazonaws.com/prod/news-search"

echo "Configuring Sentiment Analysis Agent..."
aws lambda update-function-configuration \
    --function-name ir-sentiment-analysis-prod \
    --environment "Variables={BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0,NEWS_API_URL=${NEWS_URL},NEWS_API_KEY=${2}}" \
    --region us-east-1 --query "FunctionName" --output text

echo "Done."
