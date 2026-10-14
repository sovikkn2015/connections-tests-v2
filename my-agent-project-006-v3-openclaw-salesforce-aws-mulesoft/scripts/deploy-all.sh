#!/usr/bin/env bash
# ============================================================================
# deploy-all.sh — One-command reproducible deploy for Project 006 V3
#
# Usage:
#   ./scripts/deploy-all.sh                   # full deploy
#   ./scripts/deploy-all.sh --skip-sf         # skip Salesforce step
#   ./scripts/deploy-all.sh --skip-sam        # skip SAM step
#   ./scripts/deploy-all.sh --skip-agentcore  # skip AgentCore redeploy
#   ./scripts/deploy-all.sh --skip-mulesoft   # skip Mulesoft Process APIs
#   ./scripts/deploy-all.sh --skip-frontend   # skip frontend build + upload
#   ./scripts/deploy-all.sh --verify-only     # just run smoke tests
#
# All steps are idempotent — safe to re-run after partial failures.
# ============================================================================

set -euo pipefail

SKIP_SF=false
SKIP_SAM=false
SKIP_AGENTCORE=false
SKIP_MULESOFT=false
SKIP_FRONTEND=false
SKIP_CDK=false
VERIFY_ONLY=false

for arg in "$@"; do
  case "$arg" in
    --skip-sf) SKIP_SF=true ;;
    --skip-sam) SKIP_SAM=true ;;
    --skip-agentcore) SKIP_AGENTCORE=true ;;
    --skip-mulesoft) SKIP_MULESOFT=true ;;
    --skip-frontend) SKIP_FRONTEND=true ;;
    --skip-cdk) SKIP_CDK=true ;;
    --verify-only)
      VERIFY_ONLY=true; SKIP_SF=true; SKIP_SAM=true
      SKIP_AGENTCORE=true; SKIP_MULESOFT=true; SKIP_FRONTEND=true
      SKIP_CDK=true ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
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

log()   { printf "\033[1;34m[deploy-all]\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m[deploy-all WARN]\033[0m %s\n" "$*" >&2; }
fatal() { printf "\033[1;31m[deploy-all FATAL]\033[0m %s\n" "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Step 0: Verify prereqs + seed secrets
# ---------------------------------------------------------------------------
step_prereqs() {
  log "Step 0: verifying prereqs"
  command -v aws >/dev/null || fatal "aws CLI not found"
  aws sts get-caller-identity --region "${AWS_REGION_BEDROCK}" >/dev/null 2>&1 \
    || fatal "aws not authenticated (run: aws configure)"

  if ! $SKIP_SF; then command -v sf >/dev/null || fatal "sf CLI not found"; fi
  if ! $SKIP_SAM; then
    command -v sam >/dev/null || fatal "sam CLI not found"
    command -v docker >/dev/null 2>&1 || command -v finch >/dev/null 2>&1 \
      || fatal "Need docker OR finch for SAM build"
  fi
  if ! $SKIP_MULESOFT; then command -v mvn >/dev/null || warn "maven not found — Mulesoft step will be skipped"; fi
  if ! $SKIP_FRONTEND; then command -v npm >/dev/null || fatal "npm not found"; fi
  # AgentCore uses `aws bedrock-agentcore-control` commands (no separate CLI needed).

  if ! $VERIFY_ONLY; then
    [[ -f .env ]] || fatal ".env missing (copy from .env.example, fill values)"
    log "Seeding AWS Secrets Manager + SSM from .env"
    "${SCRIPT_DIR}/seed-secrets.sh"
  fi
}

# ---------------------------------------------------------------------------
# Step 1: Salesforce — metadata + permsets + scaffolded SObjects
# ---------------------------------------------------------------------------
step_salesforce() {
  $SKIP_SF && { log "Skipping Salesforce"; return; }
  log "Step 1: Salesforce deploy"
  (
    cd salesforce
    sf project deploy start --target-org "${SF_TARGET_ORG}" --wait 20
    sf org assign permset -n Research_Analyst -o "${SF_TARGET_ORG}" || true
    sf org assign permset -n Wealth_Advisor -o "${SF_TARGET_ORG}" || true
    sf org assign permset -n Senior_Compliance_Approver -o "${SF_TARGET_ORG}" || true
    log "Salesforce deploy complete"
  )
}

# ---------------------------------------------------------------------------
# Step 1b: CDK — VPC, Aurora+pgvector, Bedrock KB, data pipelines
# ---------------------------------------------------------------------------
step_cdk() {
  $SKIP_CDK && { log "Skipping CDK"; return; }
  [[ -d aws/cdk ]] || { warn "aws/cdk/ not present — skipping"; return; }
  command -v cdk >/dev/null || { warn "cdk CLI missing — skipping"; return; }
  log "Step 1b: CDK deploy (VPC, Aurora, Bedrock KB, data pipelines)"
  (
    cd aws/cdk
    [[ -d .venv ]] || python3 -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    pip install -q -r requirements.txt
    cdk bootstrap "aws://$(aws sts get-caller-identity --query Account --output text)/${AWS_REGION_BEDROCK}" || true
    cdk deploy --all --require-approval never --region "${AWS_REGION_BEDROCK}"
    deactivate
    log "CDK deploy complete"
  )
}

# ---------------------------------------------------------------------------
# Step 1c: Cognito — User Pool + App Client + demo users (idempotent)
# ---------------------------------------------------------------------------
step_cognito() {
  log "Step 1c: Cognito setup (User Pool + App Client + demo users)"
  if [[ -f "${SCRIPT_DIR}/setup-cognito.sh" ]]; then
    bash "${SCRIPT_DIR}/setup-cognito.sh" --pool-only \
      || warn "Cognito pool setup had issues — see output above"
    bash "${SCRIPT_DIR}/setup-cognito.sh" --users-only \
      || warn "Cognito user creation had issues — see output above"
  else
    warn "scripts/setup-cognito.sh not found — skipping Cognito"
  fi
}

# ---------------------------------------------------------------------------
# Step 1d: SF OBO Connected App — deploy metadata + grant access
# ---------------------------------------------------------------------------
step_sf_obo() {
  $SKIP_SF && { log "Skipping SF OBO (--skip-sf)"; return; }
  log "Step 1d: SF OBO Connected App"
  # Deploy the ConnectedApp metadata if it exists locally
  local ca_dir="salesforce/force-app/main/default/connectedApps"
  if [[ -f "${ca_dir}/FSI_Workforce_360_OBO.connectedApp-meta.xml" ]]; then
    log "  ConnectedApp metadata already in source tree"
  else
    log "  Generating OBO keypair + ConnectedApp metadata..."
    local tmp_dir
    tmp_dir="$(mktemp -d)"
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
      -subj "/CN=fsi-workforce-360-obo/O=FSI/C=US" \
      -keyout "${tmp_dir}/fsi-obo.key" -out "${tmp_dir}/fsi-obo.crt" 2>/dev/null
    local cert_body
    cert_body="$(sed -e '1d;$d' "${tmp_dir}/fsi-obo.crt" | tr -d '\n')"
    mkdir -p "${ca_dir}"
    cat > "${ca_dir}/FSI_Workforce_360_OBO.connectedApp-meta.xml" <<CAXML
<?xml version="1.0" encoding="UTF-8"?>
<ConnectedApp xmlns="http://soap.sforce.com/2006/04/metadata">
    <contactEmail>admin@fsi-workforce-360.example.com</contactEmail>
    <label>FSI Workforce 360 OBO</label>
    <oauthConfig>
        <callbackUrl>https://login.salesforce.com/services/oauth2/callback</callbackUrl>
        <certificate>${cert_body}</certificate>
        <isAdminApproved>true</isAdminApproved>
        <isConsumerSecretOptional>false</isConsumerSecretOptional>
        <scopes>Api</scopes>
        <scopes>RefreshToken</scopes>
        <scopes>Full</scopes>
    </oauthConfig>
    <oauthPolicy>
        <ipRelaxation>BYPASS</ipRelaxation>
        <refreshTokenPolicy>infinite</refreshTokenPolicy>
    </oauthPolicy>
</ConnectedApp>
CAXML
    # Save the private key for the secret population step
    cp "${tmp_dir}/fsi-obo.key" "${PROJECT_ROOT}/.obo-key.pem"
    rm -rf "${tmp_dir}"
  fi

  # Deploy via sf project deploy (includes the ConnectedApp)
  (
    cd salesforce
    sf project deploy start --target-org "${SF_TARGET_ORG}" --wait 10 || true
  )

  # Retrieve the deployed app to get the auto-generated ConsumerKey
  local retrieve_dir="${PROJECT_ROOT}/.scratch/obo-retrieve"
  rm -rf "${retrieve_dir}"; mkdir -p "${retrieve_dir}/force-app/main/default"
  cat > "${retrieve_dir}/sfdx-project.json" <<JSON
{"packageDirectories":[{"path":"force-app","default":true}],"sourceApiVersion":"60.0"}
JSON
  (
    cd "${retrieve_dir}"
    sf project retrieve start --target-org "${SF_TARGET_ORG}" \
      --metadata "ConnectedApp:FSI_Workforce_360_OBO" --wait 5 2>/dev/null || true
  )
  local ca_xml="${retrieve_dir}/force-app/main/default/connectedApps/FSI_Workforce_360_OBO.connectedApp-meta.xml"
  if [[ -f "$ca_xml" ]]; then
    local consumer_key
    consumer_key="$(python3 -c "
import xml.etree.ElementTree as ET
ns = {'m': 'http://soap.sforce.com/2006/04/metadata'}
tree = ET.parse('${ca_xml}')
ck = tree.find('.//m:consumerKey', ns)
print(ck.text if ck is not None else '')
")"
    if [[ -n "$consumer_key" ]]; then
      log "  ConsumerKey: ${consumer_key:0:20}..."
      # Populate the bootstrap secret if we have the private key
      local key_file="${PROJECT_ROOT}/.obo-key.pem"
      if [[ -f "$key_file" ]]; then
        local sf_user
        sf_user="$(sf org display --target-org "${SF_TARGET_ORG}" --json 2>/dev/null \
          | python3 -c "import json,sys;print(json.load(sys.stdin)['result']['username'])" 2>/dev/null || echo '')"
        [[ -z "$sf_user" ]] && sf_user="multipleplatforms001.63e8e336be48@agentforce.com"
        python3 -c "
import json
secret = {
    'client_id': '${consumer_key}',
    'subject_pattern': '${sf_user}',
    'audience': 'https://login.salesforce.com',
    'private_key_pem': open('${key_file}').read(),
}
open('/tmp/obo-secret.json','w').write(json.dumps(secret))
"
        aws secretsmanager put-secret-value --region "${AWS_REGION_BEDROCK}" \
          --secret-id /006-v3/sf/bootstrap-creds \
          --secret-string "file:///tmp/obo-secret.json" >/dev/null 2>&1 \
          && log "  SF OBO secret populated" \
          || warn "  SF OBO secret update failed — run scripts/sf-obo-setup.sh manually"
        rm -f /tmp/obo-secret.json "${key_file}"
      fi
    fi
  fi
  rm -rf "${retrieve_dir}"

  # Grant the integration user access via Apex
  sf apex run --target-org "${SF_TARGET_ORG}" -f <(cat <<'APEX'
ConnectedApplication ca = [SELECT Id FROM ConnectedApplication WHERE Name='FSI Workforce 360 OBO' LIMIT 1];
PermissionSet ps = [SELECT Id FROM PermissionSet WHERE Name='Research_Analyst' LIMIT 1];
try { insert new SetupEntityAccess(ParentId=ps.Id, SetupEntityId=ca.Id); }
catch (DmlException e) { if (!e.getMessage().contains('DUPLICATE_VALUE')) throw e; }
APEX
  ) 2>/dev/null || warn "  SetupEntityAccess grant may have failed — check manually"

  # Cache-bust sf-auth-proxy Lambda
  aws lambda update-function-configuration --region "${AWS_REGION_BEDROCK}" \
    --function-name "006-v3-sf-auth-proxy" \
    --environment "Variables={CACHE_BUST=$(date +%s)}" >/dev/null 2>&1 || true
  log "  SF OBO setup complete"
}

# ---------------------------------------------------------------------------
# Step 2: SAM — 5 MCP servers + SF Auth Proxy + VPC + API Gateway
# ---------------------------------------------------------------------------
step_sam() {
  $SKIP_SAM && { log "Skipping SAM"; return; }
  log "Step 2: SAM build + deploy (MCP servers, SF Auth Proxy, VPC endpoints)"

  # Resolve Cognito params from SSM if they exist (set by setup-cognito.sh).
  local cognito_pool cognito_client
  cognito_pool="$(aws ssm get-parameter --region "${AWS_REGION_BEDROCK}" \
    --name /006-v3/cognito/user-pool-id --query 'Parameter.Value' --output text 2>/dev/null || echo '')"
  cognito_client="$(aws ssm get-parameter --region "${AWS_REGION_BEDROCK}" \
    --name /006-v3/cognito/app-client-id --query 'Parameter.Value' --output text 2>/dev/null || echo '')"

  local param_overrides=""
  if [[ -n "$cognito_pool" && "$cognito_pool" != "None" ]]; then
    param_overrides="CognitoUserPoolIdParam=${cognito_pool} CognitoAppClientIdParam=${cognito_client}"
    log "  Cognito params: pool=${cognito_pool} client=${cognito_client}"
  else
    log "  No Cognito pool in SSM — agent-proxy will use dev-bootstrap fallback"
  fi

  (
    cd aws
    sam build --template-file sam-template.yaml
    sam deploy \
      --template-file .aws-sam/build/template.yaml \
      --stack-name "${SAM_STACK_NAME}" \
      --region "${AWS_REGION_BEDROCK}" \
      --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
      --no-confirm-changeset --no-fail-on-empty-changeset \
      --resolve-s3 \
      ${param_overrides:+--parameter-overrides "$param_overrides"}
    log "SAM deploy complete"
  )

  # ── Post-deploy patches ──────────────────────────────────────────
  # SAM can't self-reference its own API Gateway URL (circular dep).
  # Patch agent-proxy with the real MCP_API_URL + SF_AUTH_PROXY_URL
  # so /agent/approve makes real MCP calls and salesforce-crm can
  # reach the sf-auth-proxy.
  log "Step 2b: post-deploy env var patches (MCP_API_URL, SF_AUTH_PROXY_URL)"

  local api_url
  api_url="$(aws cloudformation describe-stacks \
    --stack-name "${SAM_STACK_NAME}" --region "${AWS_REGION_BEDROCK}" \
    --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' --output text 2>/dev/null || echo '')"

  if [[ -n "$api_url" && "$api_url" != "None" ]]; then
    local mcp_key
    mcp_key="$(aws ssm get-parameter --region "${AWS_REGION_BEDROCK}" \
      --name /006-v3/mcp/api-key --with-decryption --query 'Parameter.Value' --output text 2>/dev/null || echo '')"

    # Patch agent-proxy: set MCP_API_URL so /agent/approve works
    local ap_env
    ap_env="$(aws lambda get-function-configuration \
      --function-name "006-${EnvName}-agent-proxy" --region "${AWS_REGION_BEDROCK}" \
      --query 'Environment.Variables' --output json 2>/dev/null || echo '{}')"
    python3 -c "
import json
d = json.loads('''${ap_env}''')
d['MCP_API_URL'] = '${api_url}'
if '${mcp_key}': d['MCP_API_KEY'] = '${mcp_key}'
with open('/tmp/_ap_env.json', 'w') as f:
    json.dump({'Variables': d}, f)
"
    aws lambda update-function-configuration \
      --function-name "006-${EnvName}-agent-proxy" --region "${AWS_REGION_BEDROCK}" \
      --environment file:///tmp/_ap_env.json >/dev/null 2>&1 \
      && log "  agent-proxy MCP_API_URL=${api_url}" \
      || warn "  agent-proxy env patch failed"
    rm -f /tmp/_ap_env.json

    # Patch salesforce-crm: set SF_AUTH_PROXY_URL
    local sf_env
    sf_env="$(aws lambda get-function-configuration \
      --function-name "006-${EnvName}-salesforce-crm" --region "${AWS_REGION_BEDROCK}" \
      --query 'Environment.Variables' --output json 2>/dev/null || echo '{}')"
    local sf_auth_url="${api_url}/internal/sf-auth"
    python3 -c "
import json
d = json.loads('''${sf_env}''')
d['SF_AUTH_PROXY_URL'] = '${sf_auth_url}'
with open('/tmp/_sf_env.json', 'w') as f:
    json.dump({'Variables': d}, f)
"
    aws lambda update-function-configuration \
      --function-name "006-${EnvName}-salesforce-crm" --region "${AWS_REGION_BEDROCK}" \
      --environment file:///tmp/_sf_env.json >/dev/null 2>&1 \
      && log "  salesforce-crm SF_AUTH_PROXY_URL=${sf_auth_url}" \
      || warn "  salesforce-crm env patch failed"
    rm -f /tmp/_sf_env.json
  else
    warn "  Could not resolve API URL from CloudFormation — post-deploy patches skipped"
  fi
}

# ---------------------------------------------------------------------------
# Step 3: Mulesoft — full chain: verify-mule -> package -> deploy -> secure
#         properties -> health. Reproduces what docs/v3-mulesoft-deploy-runbook.md
#         describes phase by phase. Every phase is idempotent.
# ---------------------------------------------------------------------------
step_mulesoft() {
  $SKIP_MULESOFT && { log "Skipping Mulesoft"; return; }
  if ! command -v mvn >/dev/null; then
    warn "maven not found — Mulesoft step skipped"; return
  fi
  [[ -d mulesoft/process-apis ]] || { warn "mulesoft/ not built in this wave — skipping"; return; }

  # All three Anypoint creds from SSM (set once by seed-secrets.sh).
  export ANYPOINT_CONNECTED_APP_ID=${ANYPOINT_CONNECTED_APP_ID:-$(aws ssm get-parameter --region "${AWS_REGION_BEDROCK}" --name /006-v3/mulesoft/client-id --with-decryption --query 'Parameter.Value' --output text 2>/dev/null || echo '')}
  export ANYPOINT_CONNECTED_APP_SECRET=${ANYPOINT_CONNECTED_APP_SECRET:-$(aws ssm get-parameter --region "${AWS_REGION_BEDROCK}" --name /006-v3/mulesoft/client-secret --with-decryption --query 'Parameter.Value' --output text 2>/dev/null || echo '')}
  export ANYPOINT_ORG_ID=${ANYPOINT_ORG_ID:-$(aws ssm get-parameter --region "${AWS_REGION_BEDROCK}" --name /006-v3/mulesoft/org_id --query 'Parameter.Value' --output text 2>/dev/null || echo '')}

  if [[ -z "$ANYPOINT_CONNECTED_APP_ID" || -z "$ANYPOINT_CONNECTED_APP_SECRET" || -z "$ANYPOINT_ORG_ID" ]]; then
    warn "Anypoint creds missing in SSM (/006-v3/mulesoft/client-id|client-secret|org_id) — skipping Mulesoft."
    warn "Run scripts/seed-secrets.sh after populating MULESOFT_* in .env, then re-run deploy-all."
    return
  fi

  # JDK 17 required for Mule 4.9 mule-maven-plugin. Use it if available.
  if [[ -z "${JAVA_HOME:-}" && -x /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home/bin/java ]]; then
    export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
    export PATH="$JAVA_HOME/bin:$PATH"
  fi

  # Phase 1: verify-mule — local checks, catches the 4 Mule 4.9 gotchas.
  log "Step 3a (mule): make verify-mule"
  make verify-mule || fatal "verify-mule failed — see docs/v3-mulesoft-gotchas.md"

  # Phase 2+3: package + mvn deploy (Exchange publish + CloudHub deploy).
  # make mule-deploy depends on mule-package, so one target does both.
  log "Step 3b (mule): make mule-deploy (package + Exchange publish + CloudHub)"
  make mule-deploy || fatal "mule-deploy failed — see mvn output above"

  # Phase 4: set per-app plain + secure properties in Runtime Manager.
  # Reads AWS secrets, OAuths, PATCHes each deployment, waits for RUNNING.
  log "Step 3c (mule): set-mule-secure-properties.sh"
  bash "${SCRIPT_DIR}/set-mule-secure-properties.sh" \
    || warn "set-mule-secure-properties.sh did not fully converge — see output above"

  # Phase 5: health probe. Non-fatal — deploy can be good even if one
  # health endpoint is momentarily unreachable.
  log "Step 3d (mule): mule-health (dynamic URL discovery)"
  bash "${SCRIPT_DIR}/mule-health.sh" \
    || warn "mule-health probe failed — retry manually after 60s"
}

# ---------------------------------------------------------------------------
# Step 4: AgentCore — build + push container then update runtime
# ---------------------------------------------------------------------------
step_agentcore() {
  $SKIP_AGENTCORE && { log "Skipping AgentCore"; return; }
  log "Step 4a: AgentCore v3 container build + ECR push"
  bash "${SCRIPT_DIR}/build-and-push-openclaw.sh"
  log "Step 4b: AgentCore v3 runtime update (pick up new image)"
  bash "${SCRIPT_DIR}/create-v3-agentcore.sh"
}

# ---------------------------------------------------------------------------
# Step 5: Frontend — build + upload to S3/CloudFront
# ---------------------------------------------------------------------------
step_frontend() {
  $SKIP_FRONTEND && { log "Skipping frontend"; return; }
  log "Step 5: Frontend build + CloudFront deploy"
  (
    cd frontend
    npm ci
    npm run build
  )
  # deploy-frontend-cloudfront.sh creates/reuses bucket + OAC + distribution
  # and prints the public URL at the end.
  bash "${SCRIPT_DIR}/deploy-frontend-cloudfront.sh"
}

step_smoke() {
  log "Step 6: Smoke tests — live-infra probes"
  bash "${SCRIPT_DIR}/smoke-test.sh" || warn "smoke-test failed — see output above"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
step_prereqs
step_salesforce
step_sf_obo
step_cdk
step_cognito
step_sam
step_mulesoft
step_agentcore
step_frontend
step_smoke

log "==========================================="
log "006 V3 deploy complete."
log ""
log "Next steps:"
log "  - Open Langfuse: \${LANGFUSE_HOST}"
log "  - Tail Lambda:   aws logs tail /aws/lambda/006-v3-market-data --follow"
log "  - Frontend:      https://\${FRONTEND_CF_DIST_ID}.cloudfront.net"
log "  - Demo warm-up:  ./scripts/warm-start.sh"
log "==========================================="
