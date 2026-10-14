#!/usr/bin/env bash
# ============================================================================
# deploy-all.sh - One-command reproducible deploy for Project 006
#
# Usage:
#   ./scripts/deploy-all.sh                   # full deploy
#   ./scripts/deploy-all.sh --skip-sf         # skip Salesforce step
#   ./scripts/deploy-all.sh --skip-sam        # skip SAM step
#   ./scripts/deploy-all.sh --skip-agentcore  # skip AgentCore redeploy
#   ./scripts/deploy-all.sh --verify-only     # just run smoke tests
#
# Prereqs (verified by the script):
#   - sf CLI authenticated to target org (alias: my-org, override via SF_TARGET_ORG)
#   - AWS CLI authenticated with bedrock + cloudformation + secretsmanager perms
#   - Python 3.10 on PATH (for SAM build)
#   - Docker running (for SAM build)
#   - agentcore CLI installed + authenticated (for AgentCore redeploy)
#
# Steps (all idempotent - safe to re-run after partial failures):
#   1. Verify prereqs
#   2. Deploy Salesforce metadata + permission set
#   3. Seed Salesforce data (4 idempotent scripts)
#   4. Build + deploy SAM (4 MCP servers + API Gateway + DLQ)
#   5. Deploy Bedrock Guardrails CloudFormation stack
#   6. Populate Secrets Manager (setup-secrets.sh auto-discovers)
#   7. Redeploy AgentCore to pick up new openclaw.json + bridge
#   8. Smoke test: 4 targeted queries via AgentCore
# ============================================================================

set -euo pipefail

SKIP_SF=false
SKIP_SAM=false
SKIP_AGENTCORE=false
VERIFY_ONLY=false

for arg in "$@"; do
  case "$arg" in
    --skip-sf) SKIP_SF=true ;;
    --skip-sam) SKIP_SAM=true ;;
    --skip-agentcore) SKIP_AGENTCORE=true ;;
    --verify-only) VERIFY_ONLY=true; SKIP_SF=true; SKIP_SAM=true; SKIP_AGENTCORE=true ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

SF_TARGET_ORG="${SF_TARGET_ORG:-my-org}"
AWS_REGION="${AWS_REGION:-us-east-1}"
# v2 gets its own stack so v1 (openclaw-mcp-006) keeps running untouched.
SAM_STACK_NAME="${SAM_STACK_NAME:-openclaw-mcp-006-v2}"
GUARDRAILS_STACK_NAME="${GUARDRAILS_STACK_NAME:-openclaw-006-v2-guardrails}"
SECRET_NAME="${SECRET_NAME:-openclaw-fsi-secrets}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

log()   { printf "\033[1;34m[deploy-all]\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m[deploy-all WARN]\033[0m %s\n" "$*" >&2; }
fatal() { printf "\033[1;31m[deploy-all FATAL]\033[0m %s\n" "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Step 0: Verify prereqs
# ---------------------------------------------------------------------------
step_verify_prereqs() {
  log "Step 0: verifying prereqs"
  command -v sf >/dev/null || fatal "sf CLI not found. npm install -g @salesforce/cli"
  command -v aws >/dev/null || fatal "aws CLI not found. brew install awscli"
  if ! $SKIP_SAM; then
    command -v sam >/dev/null || fatal "sam CLI not found. brew install aws-sam-cli"
    command -v docker >/dev/null || fatal "docker not found. Start Docker Desktop."
    docker info >/dev/null 2>&1 || fatal "Docker is not running."
  fi
  if ! $SKIP_AGENTCORE; then
    command -v agentcore >/dev/null 2>&1 || warn "agentcore CLI missing - step 7 will be skipped"
  fi
  aws sts get-caller-identity --region "${AWS_REGION}" >/dev/null 2>&1 || \
    fatal "AWS CLI not authenticated. Run: aws configure"
  if ! $SKIP_SF; then
    sf org display --target-org "${SF_TARGET_ORG}" --json >/dev/null 2>&1 || \
      fatal "SF CLI not authenticated to '${SF_TARGET_ORG}'. Run: sf org login web --alias ${SF_TARGET_ORG}"
  fi
  log "Prereqs OK"
}

# ---------------------------------------------------------------------------
# Step 1 + 2: Salesforce metadata + seed
# ---------------------------------------------------------------------------
step_salesforce() {
  if $SKIP_SF; then log "Skipping Salesforce steps"; return; fi
  log "Step 1: Deploy Salesforce metadata"
  sf project deploy start --target-org "${SF_TARGET_ORG}"
  sf org assign permset --name IR_Agent_Access --target-org "${SF_TARGET_ORG}" || \
    warn "Permset assignment skipped (may already be assigned)"

  log "Step 2: Seed Salesforce data (idempotent scripts)"
  for s in \
      scripts/apex/seed-01-accounts-companies.apex \
      scripts/apex/seed-02-coverage-watchlist-notes.apex \
      scripts/apex/seed-03-audit-logs.apex \
      scripts/apex/seed-04-financial-holdings.apex; do
    if [[ -f "${s}" ]]; then
      log "  running ${s}"
      sf apex run --file "${s}" --target-org "${SF_TARGET_ORG}"
    else
      warn "  ${s} not found, skipping"
    fi
  done
}

# ---------------------------------------------------------------------------
# Step 3: SAM deploy
# ---------------------------------------------------------------------------
step_sam() {
  if $SKIP_SAM; then log "Skipping SAM deploy"; return; fi
  log "Step 3: SAM build + deploy"
  [[ -f aws/samconfig.toml ]] || fatal "aws/samconfig.toml missing. Copy aws/samconfig.toml.example."
  (
    cd aws
    sam build
    sam deploy --no-confirm-changeset --no-fail-on-empty-changeset
  )
  log "SAM deploy complete"
}

# ---------------------------------------------------------------------------
# Step 4: Bedrock Guardrails
# ---------------------------------------------------------------------------
step_guardrails() {
  if $SKIP_SAM; then log "Skipping Guardrails"; return; fi
  log "Step 4: Deploy Bedrock Guardrails"
  aws cloudformation deploy \
    --template-file aws/guardrails/bedrock-guardrails.yaml \
    --stack-name "${GUARDRAILS_STACK_NAME}" \
    --region "${AWS_REGION}" \
    --no-fail-on-empty-changeset || warn "Guardrails deploy had warnings"
}

# ---------------------------------------------------------------------------
# Step 5: Secrets Manager
# ---------------------------------------------------------------------------
step_secrets() {
  if $VERIFY_ONLY; then log "Skipping secrets population"; return; fi
  log "Step 5: Populate Secrets Manager"
  if [[ -x scripts/aws/setup-secrets.sh ]]; then
    scripts/aws/setup-secrets.sh || warn "setup-secrets.sh returned non-zero"
  else
    warn "scripts/aws/setup-secrets.sh missing or not executable"
  fi
}

# ---------------------------------------------------------------------------
# Step 6: AgentCore redeploy
# ---------------------------------------------------------------------------
step_agentcore() {
  if $SKIP_AGENTCORE; then log "Skipping AgentCore redeploy"; return; fi
  if ! command -v agentcore >/dev/null 2>&1; then
    warn "agentcore CLI missing - skipping redeploy"
    return
  fi
  log "Step 6: Redeploy AgentCore (picks up new openclaw.json + bridge)"
  (
    cd agentcore
    cp -r ../openclaw ./openclaw
    agentcore deploy || warn "agentcore deploy returned non-zero"
    rm -rf ./openclaw
  )
}

# ---------------------------------------------------------------------------
# Step 7: Smoke test
# ---------------------------------------------------------------------------
step_smoke() {
  log "Step 7: Smoke test (4 targeted queries)"
  local test_dir test_out
  test_dir="$(mktemp -d)"
  test_out="${test_dir}/smoke-results.json"

  : "${EVAL_AUTH_TOKEN:=$(openssl rand -hex 8)}"
  export EVAL_AUTH_TOKEN

  if [[ ! -f evaluation/run_suite.py ]]; then
    warn "evaluation/run_suite.py missing - skipping smoke"
    return
  fi

  (
    cd evaluation
    for qid in 1 21 51 76; do
      python3 run_suite.py --query-id "${qid}" --output "${test_out}" 2>&1 | tail -3 || true
    done
  )

  if [[ -f "${test_out}" ]]; then
    python3 -c "
import json, sys
d = json.load(open('${test_out}'))
p, f, e, t = d.get('passed',0), d.get('failed',0), d.get('errors',0), d.get('total_queries',0)
print(f'  smoke: passed={p} failed={f} errors={e} total={t}')
sys.exit(1 if (e>0 or p==0) else 0)
" || warn "Smoke indicates issues - inspect ${test_out}"
  fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
step_verify_prereqs
step_salesforce
step_sam
step_guardrails
step_secrets
step_agentcore
step_smoke

log "All steps complete."
log "Next:"
log "  - Full eval:     (cd evaluation && EVAL_AUTH_TOKEN=\$(openssl rand -hex 16) python3 run_suite.py)"
log "  - Langfuse:      https://us.cloud.langfuse.com"
log "  - Secrets check: aws secretsmanager describe-secret --secret-id ${SECRET_NAME} --region ${AWS_REGION}"
