#!/usr/bin/env bash
# Start OpenClaw Gateway (background) and HTTP adapter (foreground) simultaneously.
# Gateway: :18789, Adapter: :8080. AgentCore requires :8080 within 120s.
# The adapter has its own gateway health polling — no need to block here.
#
# Official OpenClaw Docker image has openclaw at /app/openclaw.mjs
# Adapter is at /adapter/adapter.js
#
# IAM role credentials bootstrap (required by OpenClaw's bundled
# amazon-bedrock plugin): the plugin only reads AWS_* env vars and does not
# use the SDK default provider chain (no IMDS/ECS metadata fallback). We
# resolve credentials via @aws-sdk/credential-providers at boot and export
# them so the plugin can authenticate.

set -e

echo "[start] resolving AWS credentials from container metadata ..."
AWS_CREDS_JSON=$(node -e "
(async () => {
  const { fromNodeProviderChain } = require('@aws-sdk/credential-providers');
  try {
    const provider = fromNodeProviderChain();
    const creds = await provider();
    process.stdout.write(JSON.stringify(creds));
  } catch (e) {
    process.stderr.write('[creds-bootstrap] ' + e.message + '\n');
    process.exit(1);
  }
})();
") || { echo "[start] FAILED to resolve AWS credentials"; exit 1; }

export AWS_ACCESS_KEY_ID=$(node -e "process.stdout.write((JSON.parse(process.argv[1]).accessKeyId)||'')" "$AWS_CREDS_JSON")
export AWS_SECRET_ACCESS_KEY=$(node -e "process.stdout.write((JSON.parse(process.argv[1]).secretAccessKey)||'')" "$AWS_CREDS_JSON")
export AWS_SESSION_TOKEN=$(node -e "process.stdout.write((JSON.parse(process.argv[1]).sessionToken)||'')" "$AWS_CREDS_JSON")
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"

if [ -z "$AWS_ACCESS_KEY_ID" ]; then
  echo "[start] WARNING: credential bootstrap produced empty access key"
else
  echo "[start] AWS credentials resolved (region=$AWS_REGION, akid=${AWS_ACCESS_KEY_ID:0:8}...)"
fi

echo "[start] launching OpenClaw Gateway on :18789 (loopback, mode=local) ..."
OPENCLAW_CONFIG_PATH=/app/openclaw.json node /app/openclaw.mjs gateway --port 18789 --bind loopback &

# Start adapter immediately — it polls gateway health internally
echo "[start] launching adapter on :8080 ..."
exec node /adapter/adapter.js
