#!/usr/bin/env bash
# =============================================================================
# redeploy-everything.sh - One-command rebuild of the full 006 v2 stack.
#
# Idempotent. Running twice produces the same end state. Where human action is
# required (MuleSoft CloudHub deploy), the script prints loud, specific
# instructions and keeps going.
#
# Ordered steps:
#   1. Preflight check (CLIs + AWS/SF auth)
#   2. AWS deploy (delegates to scripts/deploy-all.sh)
#   3. Salesforce deploy (sf project deploy start + seed)
#   4. Seed AWS Secrets Manager (scripts/seed-secrets-manager.sh)
#   5. Frontend build + S3 sync + CloudFront invalidation
#   6. MuleSoft deploy (manual instructions; optional CLI path if creds present)
#   7. Mock test suite (expect 15/15)
#   8. Final status summary
#
# Usage:
#   ./scripts/redeploy-everything.sh
#
# Configuration (override via env or .env file loaded before invocation):
#   AWS_REGION          (us-east-1)
#   SF_ORG_ALIAS        (006-v2-org)
#   FRONTEND_BUCKET     (empty -> step 5 skips S3 sync)
#   CF_DIST_ID          (empty -> step 5 skips CloudFront invalidation)
#   ANYPOINT_ORG_ID     (for optional CLI deploy)
#   ANYPOINT_ENV_ID     (for optional CLI deploy)
#   ANYPOINT_USERNAME   (for optional CLI deploy)
#   ANYPOINT_PASSWORD   (for optional CLI deploy)
# =============================================================================

set -euo pipefail

# --- config -----------------------------------------------------------------
AWS_REGION="${AWS_REGION:-us-east-1}"
SF_ORG_ALIAS="${SF_ORG_ALIAS:-006-v2-org}"
FRONTEND_BUCKET="${FRONTEND_BUCKET:-}"
CF_DIST_ID="${CF_DIST_ID:-}"
ANYPOINT_ORG_ID="${ANYPOINT_ORG_ID:-}"
ANYPOINT_ENV_ID="${ANYPOINT_ENV_ID:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# Load .env if present (non-fatal if missing).
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a; source .env; set +a
fi

# --- colors + logging -------------------------------------------------------
GREEN=$'\033[1;32m'
RED=$'\033[1;31m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[1;34m'
BOLD=$'\033[1m'
RESET=$'\033[0m'

log()    { printf "%b[redeploy]%b %s\n" "${BLUE}"   "${RESET}" "$*"; }
ok()     { printf "%b[redeploy]%b %b%s%b\n" "${BLUE}" "${RESET}" "${GREEN}" "$*" "${RESET}"; }
warn()   { printf "%b[redeploy WARN]%b %b%s%b\n" "${BLUE}" "${RESET}" "${YELLOW}" "$*" "${RESET}" >&2; }
manual() { printf "%b[MANUAL STEP]%b %b%s%b\n" "${BLUE}" "${RESET}" "${YELLOW}" "$*" "${RESET}"; }
fatal()  { printf "%b[redeploy FATAL]%b %b%s%b\n" "${BLUE}" "${RESET}" "${RED}" "$*" "${RESET}" >&2; exit 1; }
step()   { printf "\n%b================================================%b\n" "${BLUE}" "${RESET}"
           printf "%b %s%b\n" "${BOLD}" "$*" "${RESET}"
           printf "%b================================================%b\n" "${BLUE}" "${RESET}"; }

CURRENT_STEP="start"

on_error() {
  local rc=$?
  printf "\n%b[redeploy FATAL]%b failed during step: %b%s%b (exit code %d)\n" \
    "${BLUE}" "${RESET}" "${RED}" "${CURRENT_STEP}" "${RESET}" "${rc}" >&2
  printf "%b[redeploy FATAL]%b inspect the log above, fix the cause, and re-run this script.\n" \
    "${BLUE}" "${RESET}" >&2
  printf "%b[redeploy FATAL]%b It is safe to re-run - every step is idempotent.\n" \
    "${BLUE}" "${RESET}" >&2
  exit "${rc}"
}
trap on_error ERR

# ============================================================================
# Step 1: Preflight
# ============================================================================
step "Step 1/8: Preflight"
CURRENT_STEP="preflight"

missing_bins=()
for bin in aws jq curl python3 openssl; do
  command -v "${bin}" >/dev/null || missing_bins+=("${bin}")
done
if ((${#missing_bins[@]} > 0)); then
  fatal "Missing required CLIs: ${missing_bins[*]}"
fi
ok "base CLIs present: aws jq curl python3 openssl"

if ! command -v sf >/dev/null; then
  fatal "sf CLI not found. npm install -g @salesforce/cli"
fi
ok "sf CLI present"

if ! aws sts get-caller-identity --region "${AWS_REGION}" >/dev/null 2>&1; then
  fatal "AWS CLI not authenticated for region ${AWS_REGION}. Run: aws configure"
fi
aws_acct="$(aws sts get-caller-identity --region "${AWS_REGION}" --query Account --output text)"
ok "AWS auth ok (account=${aws_acct}, region=${AWS_REGION})"

if ! sf org display --target-org "${SF_ORG_ALIAS}" --json >/dev/null 2>&1; then
  fatal "SF CLI not authenticated to '${SF_ORG_ALIAS}'. Run: sf org login web --alias ${SF_ORG_ALIAS}"
fi
ok "SF org auth ok (alias=${SF_ORG_ALIAS})"

if command -v anypoint-cli-v4 >/dev/null; then
  ok "anypoint-cli-v4 present (MuleSoft CLI deploy path available)"
  HAS_ANYPOINT_CLI=true
else
  warn "anypoint-cli-v4 not installed - MuleSoft deploy will require the Anypoint UI"
  HAS_ANYPOINT_CLI=false
fi

# ============================================================================
# Step 2: AWS deploy
# ============================================================================
step "Step 2/8: AWS deploy (SAM + secrets + guardrails + agentcore)"
CURRENT_STEP="aws-deploy"

if [[ -x scripts/deploy-all.sh ]]; then
  # Honor operator preference for incremental re-runs: if SKIP_AWS=1, skip this.
  if [[ "${SKIP_AWS:-0}" == "1" ]]; then
    warn "SKIP_AWS=1 set - skipping scripts/deploy-all.sh"
  else
    log "delegating to scripts/deploy-all.sh"
    # deploy-all.sh also runs SF; we pass --skip-sf because step 3 does SF.
    AWS_REGION="${AWS_REGION}" SF_TARGET_ORG="${SF_ORG_ALIAS}" \
      scripts/deploy-all.sh --skip-sf
    ok "scripts/deploy-all.sh completed"
  fi
else
  fatal "scripts/deploy-all.sh not found or not executable"
fi

# ============================================================================
# Step 3: Salesforce deploy
# ============================================================================
step "Step 3/8: Salesforce deploy + seed"
CURRENT_STEP="salesforce"

log "sf project deploy start --target-org ${SF_ORG_ALIAS}"
sf project deploy start --target-org "${SF_ORG_ALIAS}"
ok "SF metadata deployed"

# Permset assignment (idempotent - ignore 'already assigned').
sf org assign permset --name IR_Agent_Access --target-org "${SF_ORG_ALIAS}" \
  >/dev/null 2>&1 || warn "IR_Agent_Access permset assignment skipped (may already be assigned)"

# Seed Apex scripts (idempotent by design in v1/v2).
for s in \
    scripts/apex/seed-01-accounts-companies.apex \
    scripts/apex/seed-02-coverage-watchlist-notes.apex \
    scripts/apex/seed-03-audit-logs.apex \
    scripts/apex/seed-04-financial-holdings.apex; do
  if [[ -f "${s}" ]]; then
    log "running ${s}"
    sf apex run --file "${s}" --target-org "${SF_ORG_ALIAS}" >/dev/null
  else
    warn "  ${s} not found - skipping"
  fi
done
ok "SF seed scripts complete"

# ============================================================================
# Step 4: Seed Secrets Manager
# ============================================================================
step "Step 4/8: AWS Secrets Manager seed"
CURRENT_STEP="secrets"

if [[ -x scripts/seed-secrets-manager.sh ]]; then
  AWS_REGION="${AWS_REGION}" scripts/seed-secrets-manager.sh
  ok "secrets seeded"
else
  fatal "scripts/seed-secrets-manager.sh not found or not executable"
fi

# ============================================================================
# Step 5: Frontend build + S3 sync + CloudFront invalidation
# ============================================================================
step "Step 5/8: Frontend build + deploy"
CURRENT_STEP="frontend"

if [[ ! -d frontend ]]; then
  warn "frontend/ directory not found - skipping"
else
  (
    cd frontend
    if [[ -f package-lock.json ]]; then
      log "npm ci (frontend)"
      npm ci --no-audit --no-fund
    else
      log "npm install (frontend)"
      npm install --no-audit --no-fund
    fi
    log "npm run build (frontend)"
    npm run build
  )
  ok "frontend build complete -> frontend/dist/"

  if [[ -n "${FRONTEND_BUCKET}" ]]; then
    log "aws s3 sync frontend/dist/ s3://${FRONTEND_BUCKET}"
    aws s3 sync frontend/dist/ "s3://${FRONTEND_BUCKET}" \
      --delete \
      --region "${AWS_REGION}" \
      --cache-control "public, max-age=300"
    ok "frontend synced to s3://${FRONTEND_BUCKET}"

    if [[ -n "${CF_DIST_ID}" ]]; then
      log "cloudfront invalidation for ${CF_DIST_ID}"
      aws cloudfront create-invalidation \
        --distribution-id "${CF_DIST_ID}" \
        --paths '/*' \
        --region "${AWS_REGION}" >/dev/null
      ok "cloudfront invalidated"
    else
      warn "CF_DIST_ID not set - skipping CloudFront invalidation"
    fi
  else
    warn "FRONTEND_BUCKET not set - skipping S3 sync and CloudFront invalidation"
  fi
fi

# ============================================================================
# Step 6: MuleSoft CloudHub deploy (manual by default)
# ============================================================================
step "Step 6/8: MuleSoft CloudHub deploy"
CURRENT_STEP="mulesoft"

manual "MuleSoft CloudHub deploy requires Anypoint UI for first-time policy setup."
manual "Full runbook: docs/v2-mulesoft-process-api-deploy.md"
manual "  1. Package each process API under mulesoft/process-apis/<name>/ in Anypoint Code Builder"
manual "  2. Deploy via 'Deploy to CloudHub 2.0'"
manual "  3. Apply policies from mulesoft/policies/process-api-policies.json in API Manager"
manual "  4. Set secure properties (alpaca.key_id, alpaca.secret) - see runbook"
manual "  5. Capture client_id for MULESOFT_CLIENT_ID env var"

# Optional CLI path - only if operator set everything up.
if $HAS_ANYPOINT_CLI \
    && [[ -n "${ANYPOINT_USERNAME:-}" ]] \
    && [[ -n "${ANYPOINT_PASSWORD:-}" ]] \
    && [[ -n "${ANYPOINT_ORG_ID}" ]] \
    && [[ -n "${ANYPOINT_ENV_ID}" ]]; then
  log "anypoint-cli-v4 detected + creds present - attempting CLI deploy"
  log "(individual app deploys are best handled per-process-api; see runbook)"
  # We do NOT call the raw deploy here because the exact app name, file path
  # (.jar vs source), and CloudHub target must be supplied per-process-api.
  # The operator's follow-up call is:
  #
  #   anypoint-cli-v4 runtime-mgr cloudhub2-application deploy \
  #     --organization "${ANYPOINT_ORG_ID}" \
  #     --environment  "${ANYPOINT_ENV_ID}" \
  #     --target        cloudhub-us-east-1 \
  #     --file          mulesoft/process-apis/<name>/target/<name>.jar \
  #     <app-name>
  #
  manual "To CLI-deploy: run 'anypoint-cli-v4 runtime-mgr cloudhub2-application deploy ...'"
  manual "  per-app parameters documented in docs/v2-mulesoft-process-api-deploy.md"
else
  if ! $HAS_ANYPOINT_CLI; then
    manual "anypoint-cli-v4 not installed - Anypoint UI is the only path"
  else
    manual "ANYPOINT_USERNAME/PASSWORD/ORG_ID/ENV_ID not all set - Anypoint UI required"
  fi
fi

# ============================================================================
# Step 6b: CloudHub 2.0 ingress-restore
#
# CloudHub 2.0 rolling updates wipe the http.inbound.endpoints[] array from
# the deployment spec, which causes external traffic to 404 even though the
# app reports RUNNING. This step re-applies the endpoints block via PATCH
# /deployments/{id}. Idempotent. Only fires when Anypoint user creds are
# present AND ANYPOINT_APP_ID / ANYPOINT_APP_PUBLIC_URL are set.
# ============================================================================
step "Step 6b/8: CloudHub ingress-restore"
CURRENT_STEP="cloudhub-ingress-restore"

if [[ -n "${ANYPOINT_USERNAME:-}" ]] \
    && [[ -n "${ANYPOINT_PASSWORD:-}" ]] \
    && [[ -n "${ANYPOINT_ORG_ID:-}" ]] \
    && [[ -n "${ANYPOINT_ENV_ID:-}" ]] \
    && [[ -n "${ANYPOINT_APP_ID:-}" ]] \
    && [[ -n "${ANYPOINT_APP_PUBLIC_URL:-}" ]]; then

  log "fetching Anypoint user token"
  ingress_token="$(curl -sS --max-time 15 \
                    -X POST https://anypoint.mulesoft.com/accounts/login \
                    -H 'Content-Type: application/json' \
                    -d "$(jq -cn --arg u "${ANYPOINT_USERNAME}" \
                                --arg p "${ANYPOINT_PASSWORD}" \
                                '{username:$u,password:$p}')" \
                    | jq -r '.access_token // ""')"

  if [[ -z "${ingress_token}" || "${ingress_token}" == "null" ]]; then
    warn "Anypoint login failed - skipping ingress-restore. Fix creds and re-run."
  else
    log "PATCH deployments/${ANYPOINT_APP_ID} with endpoints[]"
    patch_body="$(jq -cn --arg url "${ANYPOINT_APP_PUBLIC_URL}" \
      '{target:{deploymentSettings:{http:{inbound:{
         publicUrl: $url,
         endpoints: [{url: $url, access: "external"}]
       }}}}}')"

    patch_code="$(curl -sS -o /tmp/ingress-patch.json \
                    -w '%{http_code}' \
                    -X PATCH \
                    "https://anypoint.mulesoft.com/amc/application-manager/api/v2/organizations/${ANYPOINT_ORG_ID}/environments/${ANYPOINT_ENV_ID}/deployments/${ANYPOINT_APP_ID}" \
                    -H "Authorization: Bearer ${ingress_token}" \
                    -H "Content-Type: application/json" \
                    -d "${patch_body}" || echo '000')"

    if [[ "${patch_code}" == "200" ]]; then
      ok "ingress endpoints restored (HTTP 200)"
    else
      warn "ingress-restore returned HTTP ${patch_code} - inspect /tmp/ingress-patch.json"
    fi
    unset ingress_token patch_body
    rm -f /tmp/ingress-patch.json
  fi
else
  manual "ingress-restore skipped. To enable, export these vars before running:"
  manual "  ANYPOINT_USERNAME / ANYPOINT_PASSWORD  (operator user creds)"
  manual "  ANYPOINT_ORG_ID / ANYPOINT_ENV_ID"
  manual "  ANYPOINT_APP_ID           (UUID from AMC deployments list)"
  manual "  ANYPOINT_APP_PUBLIC_URL   (https://<app>-<hash>.usa-e2.cloudhub.io)"
fi

# ============================================================================
# Step 7: Mock test suite
# ============================================================================
step "Step 7/8: Mock test suite (expect 15/15)"
CURRENT_STEP="mock-tests"

export HITL_SIGNING_KEY
HITL_SIGNING_KEY="$(openssl rand -hex 32)"
log "HITL_SIGNING_KEY generated (32 bytes, hex)"

if [[ ! -f scripts/test-mulesoft-mock.py ]]; then
  fatal "scripts/test-mulesoft-mock.py missing"
fi

# Capture output so we can parse the pass/fail line.
mock_log="$(mktemp)"
if ! python3 scripts/test-mulesoft-mock.py 2>&1 | tee "${mock_log}"; then
  fatal "mock test suite exited non-zero - see ${mock_log}"
fi

# Parse "  Results: X/Y passed, Z failed" - require 15/15 exactly.
results_line="$(grep -E '^\s+Results:' "${mock_log}" | head -1 || true)"
if [[ -z "${results_line}" ]]; then
  fatal "could not find Results: line in mock test output (${mock_log})"
fi
parsed="$(echo "${results_line}" \
  | sed -E 's/.*Results: ([0-9]+)\/([0-9]+) passed, ([0-9]+) failed.*/\1 \2 \3/')"
read -r p t f <<< "${parsed}"
if [[ "${p}" != "${t}" || "${f}" != "0" || "${t}" -lt 15 ]]; then
  fatal "mock test suite: ${p}/${t} passed, ${f} failed (required 15/15)"
fi
# Purge the signing key out of the environment before any further subshells run.
unset HITL_SIGNING_KEY
ok "mock test suite: ${p}/${t} passed"

# ============================================================================
# Step 8: Final status
# ============================================================================
step "Step 8/8: Final status"
CURRENT_STEP="summary"

# Try to resolve the API Gateway URL from the SAM stack outputs for display.
SAM_STACK_NAME="${SAM_STACK_NAME:-openclaw-mcp-006-v2}"
api_url="$(aws cloudformation describe-stacks \
            --stack-name "${SAM_STACK_NAME}" --region "${AWS_REGION}" \
            --query "Stacks[0].Outputs[?OutputKey=='ApiGatewayUrl'].OutputValue" \
            --output text 2>/dev/null || echo "")"

echo ""
printf "%b==========================================%b\n" "${GREEN}" "${RESET}"
printf "%b  006 v2 redeploy: DONE%b\n" "${GREEN}${BOLD}" "${RESET}"
printf "%b==========================================%b\n" "${GREEN}" "${RESET}"
printf "\n"
printf "%bWhat's deployed:%b\n" "${BOLD}" "${RESET}"
printf "  - AWS SAM stack        : %s (region=%s)\n" "${SAM_STACK_NAME}" "${AWS_REGION}"
if [[ -n "${api_url}" && "${api_url}" != "None" ]]; then
  printf "  - MCP API Gateway      : %s\n" "${api_url}"
else
  printf "  - MCP API Gateway      : (no ApiGatewayUrl output)\n"
fi
printf "  - Salesforce org       : %s\n" "${SF_ORG_ALIAS}"
printf "  - Secrets Manager      : /006-v2/mulesoft/credentials, /006-v2/vendors/alpaca-*, /006-v2/hitl/signing-key\n"
if [[ -n "${FRONTEND_BUCKET}" ]]; then
  printf "  - Frontend (S3)        : s3://%s\n" "${FRONTEND_BUCKET}"
else
  printf "  - Frontend (S3)        : (skipped - FRONTEND_BUCKET not set)\n"
fi
if [[ -n "${CF_DIST_ID}" ]]; then
  printf "  - CloudFront           : %s (invalidated)\n" "${CF_DIST_ID}"
else
  printf "  - CloudFront           : (skipped - CF_DIST_ID not set)\n"
fi
printf "  - Mock test suite      : %s/%s passed\n" "${p}" "${t}"
printf "\n"
printf "%bVerify:%b\n" "${BOLD}" "${RESET}"
printf "  ./scripts/verify-006-v2.sh\n"
printf "\n"
printf "%bManual steps still required:%b\n" "${BOLD}" "${RESET}"
printf "  %b-%b MuleSoft CloudHub deploy  (docs/v2-mulesoft-process-api-deploy.md)\n" "${YELLOW}" "${RESET}"
printf "  %b-%b Set MULESOFT_CLIENT_ID env var from API Manager after policies applied\n" "${YELLOW}" "${RESET}"
printf "  %b-%b Run Alpaca E2E after CloudHub is up:  ./scripts/run-alpaca-e2e-test.sh\n" "${YELLOW}" "${RESET}"
printf "\n"
