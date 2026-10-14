#!/usr/bin/env bash
# ============================================================================
# 9-destroy.sh — Clean teardown of Project 006 V3
#
# Removes everything deploy-all.sh created, in reverse dependency order.
# Each destructive step is confirmation-gated unless --force is passed.
#
# Usage:
#   bash scripts/9-destroy.sh            # interactive, prompts before each step
#   bash scripts/9-destroy.sh --force    # non-interactive (for CI cleanup)
#   bash scripts/9-destroy.sh --dry-run  # show what would happen, no execution
#   bash scripts/9-destroy.sh --help
#
# What it does NOT destroy:
#   - Your local .env file (preserved; you decide whether to delete it)
#   - Your IAM user / AWS account
#   - Your Salesforce org / user records (only removes deployed metadata)
#   - Your Langfuse project (deleted via Langfuse UI only)
#   - Vendor API keys in Finnhub/Tavily/Alpaca/Dwolla/Anypoint
#   - cached docker images on your local machine
#
# Exit codes:
#   0 — teardown complete
#   1 — one or more destroy steps failed (check output for details)
#   2 — invalid arguments
# ============================================================================

set -uo pipefail

FORCE=false
DRY_RUN=false

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=true ;;
    --dry-run) DRY_RUN=true ;;
    -h|--help) sed -n '2,28p' "$0"; exit 0 ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

[[ -f .env ]] && { set -a; source .env; set +a; }

: "${AWS_REGION_BEDROCK:=us-east-1}"
: "${AWS_REGION_LAMBDA:=us-east-2}"
: "${SF_TARGET_ORG:=new-org}"
: "${SAM_STACK_NAME:=openclaw-mcp-006-v3}"

BLUE='\033[1;34m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
RED='\033[1;31m'
RESET='\033[0m'

log()    { printf "${BLUE}[9-destroy]${RESET} %s\n" "$*"; }
warning(){ printf "${BLUE}[9-destroy]${RESET} ${YELLOW}⚠${RESET}  %s\n" "$*"; }
success(){ printf "${BLUE}[9-destroy]${RESET} ${GREEN}✓${RESET} %s\n" "$*"; }
err()    { printf "${BLUE}[9-destroy]${RESET} ${RED}✗${RESET} %s\n" "$*" >&2; }
section(){ printf "\n${BLUE}═══ %s ═══${RESET}\n" "$*"; }

# Confirm or fail
confirm() {
  local prompt="$1"
  if $FORCE; then return 0; fi
  read -r -p "$(printf '%b' "${YELLOW}?${RESET} $prompt [y/N]: ")" answer
  [[ "$answer" =~ ^[Yy]$ ]]
}

# Wrap destructive AWS/CLI commands for --dry-run
run() {
  if $DRY_RUN; then
    log "DRY-RUN: $*"
    return 0
  fi
  "$@"
}

# Top-level banner
echo
printf "${RED}══════════════════════════════════════════════════════════════════${RESET}\n"
printf "${RED} 006 V3 TEARDOWN                                                    ${RESET}\n"
printf "${RED}══════════════════════════════════════════════════════════════════${RESET}\n"
echo
log "Target account: $(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo UNKNOWN)"
log "Target SF org:  ${SF_TARGET_ORG}"
log "Target region:  ${AWS_REGION_BEDROCK}"
echo
if $DRY_RUN; then
  warning "DRY-RUN mode — no actual deletions"
else
  warning "This will destroy infrastructure. Nothing is recoverable."
fi
echo

if ! $FORCE && ! $DRY_RUN; then
  if ! confirm "Proceed with teardown?"; then
    log "Aborted by user"
    exit 0
  fi
fi

errors=0

# ============================================================================
# Step 1 — MuleSoft CloudHub apps
# ============================================================================
section "1/9  MuleSoft CloudHub apps"

if command -v mvn >/dev/null 2>&1 && [[ -d "mulesoft/process-apis" ]]; then
  for app in submit-order initiate-wire order-status-webhook; do
    if [[ -d "mulesoft/process-apis/$app" ]]; then
      if confirm "Undeploy $app from CloudHub Sandbox?"; then
        (cd "mulesoft/process-apis/$app" && run mvn -q mule:undeploy -Pcloudhub-sandbox 2>/dev/null) \
          && success "$app undeployed" \
          || { warning "$app undeploy failed (may already be gone)"; errors=$((errors + 1)); }
      fi
    fi
  done
else
  log "mvn not found or mulesoft/ dir missing — skipping CloudHub undeploy"
fi

# ============================================================================
# Step 2 — AgentCore runtime + ECR image
# ============================================================================
section "2/9  AgentCore runtime + ECR image"

if confirm "Destroy AgentCore runtime openclaw_v3_agent?"; then
  runtime_ids=$(aws bedrock-agentcore-control list-agent-runtimes \
    --region "$AWS_REGION_BEDROCK" \
    --query 'agentRuntimes[?contains(agentRuntimeName, `openclaw_v3`)].agentRuntimeId' \
    --output text 2>/dev/null || echo "")

  for rid in $runtime_ids; do
    log "Deleting runtime $rid..."
    run aws bedrock-agentcore-control delete-agent-runtime \
      --agent-runtime-id "$rid" \
      --region "$AWS_REGION_BEDROCK" 2>/dev/null \
      && success "$rid deleted" \
      || { err "failed to delete $rid"; errors=$((errors + 1)); }
  done

  # ECR repo
  if aws ecr describe-repositories --repository-names openclaw-agentcore --region "$AWS_REGION_BEDROCK" >/dev/null 2>&1; then
    log "Emptying and deleting ECR repo openclaw-agentcore..."
    run aws ecr delete-repository \
      --repository-name openclaw-agentcore \
      --region "$AWS_REGION_BEDROCK" \
      --force 2>/dev/null \
      && success "ECR repo deleted" \
      || { warning "ECR repo delete failed"; errors=$((errors + 1)); }
  fi
fi

# ============================================================================
# Step 3 — Frontend CloudFront + S3 bucket
# ============================================================================
section "3/9  Frontend CloudFront + S3"

if confirm "Destroy v3 CloudFront distribution + S3 bucket?"; then
  # Find v3 distribution
  dist_id=$(aws cloudfront list-distributions \
    --query 'DistributionList.Items[?contains(Comment, `openclaw-v3`)].Id' \
    --output text 2>/dev/null | head -1)

  if [[ -n "$dist_id" ]]; then
    log "Disabling CloudFront distribution $dist_id..."
    # Disable first, then delete (CloudFront requires disable → propagation → delete)
    etag=$(aws cloudfront get-distribution-config --id "$dist_id" --query ETag --output text 2>/dev/null)
    if [[ -n "$etag" ]]; then
      run aws cloudfront get-distribution-config --id "$dist_id" \
        --query 'DistributionConfig' --output json > /tmp/.cf-config.json 2>/dev/null
      run python3 -c "
import json
c = json.load(open('/tmp/.cf-config.json'))
c['Enabled'] = False
json.dump(c, open('/tmp/.cf-config-disabled.json','w'))
" 2>/dev/null
      run aws cloudfront update-distribution \
        --id "$dist_id" --if-match "$etag" \
        --distribution-config file:///tmp/.cf-config-disabled.json 2>/dev/null \
        && warning "CloudFront disable submitted. Wait 10-15 min then re-run with --force to delete."
    fi
  else
    log "No v3 CloudFront distribution found"
  fi

  # S3 bucket
  bucket="openclaw-v3-frontend-$(aws sts get-caller-identity --query Account --output text 2>/dev/null)"
  if aws s3 ls "s3://$bucket" >/dev/null 2>&1; then
    log "Emptying and deleting s3://$bucket..."
    run aws s3 rm "s3://$bucket" --recursive 2>/dev/null
    run aws s3 rb "s3://$bucket" 2>/dev/null \
      && success "$bucket deleted" \
      || { warning "$bucket delete failed"; errors=$((errors + 1)); }
  fi
fi

# ============================================================================
# Step 4 — SAM stack
# ============================================================================
section "4/9  SAM stack (openclaw-mcp-006-v3)"

if confirm "Destroy SAM stack ${SAM_STACK_NAME}?"; then
  if aws cloudformation describe-stacks --stack-name "$SAM_STACK_NAME" --region "$AWS_REGION_BEDROCK" >/dev/null 2>&1; then
    log "Deleting SAM stack (this can take 10+ min due to NAT gateway tear-down)..."
    run aws cloudformation delete-stack \
      --stack-name "$SAM_STACK_NAME" \
      --region "$AWS_REGION_BEDROCK" \
      && success "SAM delete submitted" \
      || { err "SAM delete failed to submit"; errors=$((errors + 1)); }

    if ! $DRY_RUN; then
      log "Waiting for SAM stack deletion..."
      aws cloudformation wait stack-delete-complete \
        --stack-name "$SAM_STACK_NAME" \
        --region "$AWS_REGION_BEDROCK" 2>/dev/null \
        && success "SAM stack deleted" \
        || warning "SAM delete wait timed out — check manually"
    fi
  else
    log "SAM stack already gone"
  fi
fi

# ============================================================================
# Step 5 — CDK stacks (reverse order)
# ============================================================================
section "5/9  CDK stacks"

# Order matters: Risk-Alerts + Pipelines + Kb depend on Vpc/Aurora
for stack in \
    "Openclaw006V3-RiskAlerts" \
    "Openclaw006V3-FilingsPipeline" \
    "Openclaw006V3-ResearchPipeline" \
    "Openclaw006V3-Kb" \
    "Openclaw006V3-Aurora" \
    "Openclaw006V3-Vpc"; do

  if aws cloudformation describe-stacks --stack-name "$stack" --region "$AWS_REGION_BEDROCK" >/dev/null 2>&1; then
    if confirm "Destroy CDK stack $stack?"; then
      log "Deleting $stack..."
      run aws cloudformation delete-stack --stack-name "$stack" --region "$AWS_REGION_BEDROCK"
      if ! $DRY_RUN; then
        aws cloudformation wait stack-delete-complete \
          --stack-name "$stack" --region "$AWS_REGION_BEDROCK" 2>/dev/null \
          && success "$stack deleted" \
          || { warning "$stack delete wait failed — check console"; errors=$((errors + 1)); }
      fi
    fi
  else
    log "$stack not found (already deleted)"
  fi
done

# Orphan buckets (KB raw-filings + chunks buckets sometimes survive stack deletion)
log "Cleaning up orphan buckets..."
for bucket in $(aws s3 ls 2>/dev/null | grep -E "openclaw006v3-kb-" | awk '{print $3}'); do
  if confirm "Delete orphan bucket $bucket?"; then
    run aws s3 rm "s3://$bucket" --recursive 2>/dev/null
    run aws s3 rb "s3://$bucket" 2>/dev/null && success "$bucket deleted"
  fi
done

# ============================================================================
# Step 6 — SSM parameters under /006-v3/*
# ============================================================================
section "6/9  SSM parameters"

if confirm "Delete all SSM parameters under /006-v3/*?"; then
  params=$(aws ssm get-parameters-by-path \
    --path /006-v3 --recursive \
    --region "$AWS_REGION_BEDROCK" \
    --query 'Parameters[].Name' \
    --output text 2>/dev/null || echo "")

  if [[ -n "$params" ]]; then
    for p in $params; do
      run aws ssm delete-parameter --name "$p" --region "$AWS_REGION_BEDROCK" 2>/dev/null \
        && success "Deleted SSM: $p" \
        || warning "Failed to delete SSM: $p"
    done
  else
    log "No SSM parameters found under /006-v3/*"
  fi
fi

# ============================================================================
# Step 7 — Secrets Manager secrets
# ============================================================================
section "7/9  Secrets Manager"

if confirm "Delete all Secrets Manager secrets starting with /006-v3/?"; then
  secrets=$(aws secretsmanager list-secrets \
    --region "$AWS_REGION_BEDROCK" \
    --query 'SecretList[?starts_with(Name, `/006-v3/`)].Name' \
    --output text 2>/dev/null || echo "")

  if [[ -n "$secrets" ]]; then
    for s in $secrets; do
      # --force-delete-without-recovery is destructive but fits teardown intent
      run aws secretsmanager delete-secret \
        --secret-id "$s" \
        --force-delete-without-recovery \
        --region "$AWS_REGION_BEDROCK" 2>/dev/null \
        && success "Deleted secret: $s" \
        || warning "Failed to delete secret: $s"
    done
  else
    log "No /006-v3/ secrets found"
  fi
fi

# ============================================================================
# Step 8 — Salesforce permission sets (not the org itself)
# ============================================================================
section "8/9  Salesforce metadata (scaffold only, not the org)"

warning "Salesforce metadata deletion requires a manual destructiveChanges deploy."
warning "The scaffolded SObjects have real data (audit rows, briefs, inquiries)."
warning "Safer to leave them; ask user to run destructiveChanges if truly needed."
log "Skipping automatic SF cleanup. Manual command if you want to remove:"
log "  cd salesforce && sf project deploy start \\"
log "    --manifest manifest/destructiveChanges.xml \\"
log "    --target-org $SF_TARGET_ORG"

# ============================================================================
# Step 9 — Local .env (preserve)
# ============================================================================
section "9/9  Local .env"

if [[ -f .env ]]; then
  if confirm "Delete local .env file? (contains credentials)"; then
    run rm .env && success ".env deleted" \
      || warning ".env delete failed"
  else
    log ".env preserved"
  fi
else
  log ".env not present"
fi

# ============================================================================
# Summary
# ============================================================================
section "Teardown Summary"

if [[ "$errors" -gt 0 ]]; then
  warning "$errors non-fatal errors during teardown. Check output above."
  printf "\nVerify nothing remains:\n"
  printf "  aws cloudformation list-stacks --region %s --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE\n" "$AWS_REGION_BEDROCK"
  printf "  aws ssm get-parameters-by-path --path /006-v3 --region %s\n" "$AWS_REGION_BEDROCK"
  exit 1
else
  success "Teardown complete. Check costs stop dropping after ~60 min."
  printf "\nVerify empty:\n"
  printf "  aws cloudformation list-stacks --region %s --stack-status-filter CREATE_COMPLETE\n" "$AWS_REGION_BEDROCK"
  printf "     (expect: no 006V3 or 006-v3 stacks)\n"
  printf "  aws ssm get-parameters-by-path --path /006-v3 --region %s\n" "$AWS_REGION_BEDROCK"
  printf "     (expect: empty)\n"
  echo
  log "Safe to re-deploy with: bash scripts/0-preflight.sh && bash scripts/deploy-all.sh"
  exit 0
fi
