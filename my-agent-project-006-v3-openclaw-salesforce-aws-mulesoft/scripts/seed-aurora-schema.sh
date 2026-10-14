#!/usr/bin/env bash
# Apply Aurora research-corpus schema (001_init.sql + 002_rls_policies.sql)
# via bastion / AWS CLI. Runs after the Aurora CDK stack is deployed but
# before the research pipeline goes live.
#
# Reads DB connection info from:
#   SSM: /006-v3/infra/aurora-endpoint (or from stack outputs)
#   Secrets Manager: cluster.secret.arn exported by the Aurora stack
#
# Requires: aws CLI + psql installed locally, PrivateLink/VPN to Aurora
# subnets, or run this from a Lambda with the right VPC config.
#
# Zero secrets printed to stdout or file.

set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
STACK_NAME="${AURORA_STACK:-Openclaw006V3-Aurora}"

echo "Resolving Aurora endpoint from stack '$STACK_NAME'..."
ENDPOINT=$(aws cloudformation describe-stacks --region "$REGION" \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='AuroraEndpoint'].OutputValue" \
    --output text)
SECRET_ARN=$(aws cloudformation describe-stacks --region "$REGION" \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='AuroraSecretArn'].OutputValue" \
    --output text)

if [[ -z "$ENDPOINT" || -z "$SECRET_ARN" ]]; then
    echo "ERROR: couldn't resolve Aurora endpoint or secret ARN from stack outputs."
    exit 1
fi

echo "Resolving master credentials from Secrets Manager..."
SECRET_JSON=$(aws secretsmanager get-secret-value --region "$REGION" \
    --secret-id "$SECRET_ARN" --query SecretString --output text)
DB_USER=$(echo "$SECRET_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin)['username'])")
export PGPASSWORD=$(echo "$SECRET_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin)['password'])")

SCHEMA_DIR="$(dirname "$0")/../aws/data-pipelines/research-corpus/schema"

echo "Applying 001_init.sql..."
psql -h "$ENDPOINT" -U "$DB_USER" -d research -f "$SCHEMA_DIR/001_init.sql"
echo "Applying 002_rls_policies.sql..."
psql -h "$ENDPOINT" -U "$DB_USER" -d research -f "$SCHEMA_DIR/002_rls_policies.sql"

echo "Schema applied. Testing pgvector..."
psql -h "$ENDPOINT" -U "$DB_USER" -d research -c "SELECT extname FROM pg_extension WHERE extname='vector';"

unset PGPASSWORD
echo "Done."
