#!/usr/bin/env bash
# ============================================================================
# sf-obo-setup.sh — Scripted half of the Salesforce OBO Connected App fix.
#
# The other half (creating the Connected App + uploading a cert in the
# Salesforce UI) is manual — Salesforce requires an admin to click through
# Setup -> App Manager. This script does EVERYTHING else:
#   - generates a fresh RSA keypair + self-signed cert locally
#   - shows the .crt content so you can paste-upload it to SF
#   - waits for you to paste back the Connected App Consumer Key
#   - builds the secret JSON and PUTs it into AWS Secrets Manager
#   - busts the Lambda cold-start cache
#   - runs the live verification probe
#   - shreds temp files
#
# Full context: docs/v3-p0-sf-obo-fix.md
#
# Usage:
#   ./scripts/sf-obo-setup.sh
#   ./scripts/sf-obo-setup.sh --verify-only    # skip setup, only run probe
#   ./scripts/sf-obo-setup.sh --probe-only     # run the HTTP probe against the running stack
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

AWS_REGION="${AWS_REGION_BEDROCK:-us-east-1}"
SECRET_ID="/006-v3/sf/bootstrap-creds"
LAMBDA_NAME="006-v3-sf-auth-proxy"

VERIFY_ONLY=false
PROBE_ONLY=false
for arg in "$@"; do
  case "$arg" in
    --verify-only) VERIFY_ONLY=true ;;
    --probe-only)  PROBE_ONLY=true ;;
    -h|--help)     sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

log()  { printf "\033[1;34m[sf-obo]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[sf-obo WARN]\033[0m %s\n" "$*" >&2; }
fatal(){ printf "\033[1;31m[sf-obo FATAL]\033[0m %s\n" "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || fatal "Missing required tool: $1"; }
need aws; need openssl; need jq; need curl; need python3

# ---------------------------------------------------------------------------
# Probe path — runs HTTP against the live stack to verify the fix landed.
# ---------------------------------------------------------------------------
run_probe() {
  log "Running live verification probe..."

  local mcp_key api_id
  mcp_key="$(aws ssm get-parameter --region "${AWS_REGION}" \
    --name /006-v3/mcp/api-key --with-decryption \
    --query 'Parameter.Value' --output text 2>/dev/null || echo '')"
  [[ -n "$mcp_key" ]] || fatal "Could not resolve MCP API key from SSM"

  api_id="$(aws apigateway get-rest-apis --region "${AWS_REGION}" \
    --query "items[?name=='006-v3-mcp-api'].id" --output text 2>/dev/null || echo '')"
  [[ -n "$api_id" ]] || fatal "Could not resolve 006-v3-mcp-api REST API id"

  local url="https://${api_id}.execute-api.${AWS_REGION}.amazonaws.com/v3/mcp/salesforce-crm/tools/call"

  log "POST ${url}"
  local body
  body="$(jq -cn --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg sid "verify-obo-$(date +%s)000000" --arg cid "verify-obo-$(date +%s)" \
    '{name:"write_audit_log",arguments:{record:{
        Action__c:"ADVISORY_QUERY",
        Principal_Id__c:"sarah",
        Agent_Id__c:"research_orchestrator",
        Session_Id__c:$sid,
        Correlation_Id__c:$cid,
        Timestamp__c:$ts,
        Payload__c:{probe:"sf-obo-setup-live"}
    }}}')"

  local http_code
  http_code="$(curl -s -o /tmp/sf-obo-probe-result.json -w '%{http_code}' \
    --max-time 20 \
    -X POST "$url" \
    -H "X-MCP-API-Key: $mcp_key" \
    -H "X-Principal-Id: sarah" \
    -H "X-Agent-Id: research_orchestrator" \
    -H "X-Persona: research" \
    -H 'Content-Type: application/json' \
    -d "$body")"

  if [[ "$http_code" == "200" ]]; then
    local sf_id
    sf_id="$(jq -r '.result.Id // .result.id // "?"' /tmp/sf-obo-probe-result.json 2>/dev/null || echo '?')"
    log "PROBE PASSED — HTTP 200, IR_Audit_Log__c Id=${sf_id}"
    log "Now firing a research turn to double-check publish_brief lands..."
    agent_url="https://$(aws apigateway get-rest-apis --region "${AWS_REGION}" \
      --query "items[?name=='006-v3-mcp-api'].id" --output text).execute-api.${AWS_REGION}.amazonaws.com/v3/agent/invoke"
    turn_sid="verify-obo-$(date +%s)"
    curl -s -X POST "$agent_url" \
      -H "Authorization: Bearer dev-bootstrap-token" \
      -H "Content-Type: application/json" \
      --max-time 40 \
      -d "$(jq -cn --arg sid "$turn_sid" \
        '{prompt:"NVDA one-liner post-OBO-fix",persona:"fsi_research",session_id:$sid,principal_id:"sarah"}')" \
      -o /tmp/sf-obo-turn.json -w 'turn HTTP:%{http_code} time:%{time_total}s\n' || true
    sleep 8
    log "Rows today after turn:"
    for obj in Research_Brief__c IR_Audit_Log__c; do
      sf data query --target-org new-org \
        --query "SELECT COUNT() FROM $obj WHERE CreatedDate = TODAY" 2>/dev/null \
        | sed -n 's/^[ \t]*[0-9][0-9]*[ \t]*[0-9][0-9]*[ \t]*$/FOUND/p' >/dev/null
      count="$(python3 -c "
import subprocess,json
r=subprocess.run(['sf','data','query','--target-org','new-org',
  '--query','SELECT COUNT(Id) ct FROM $obj WHERE CreatedDate = TODAY','--json'],
  capture_output=True,text=True,timeout=20)
print(json.loads(r.stdout)['result']['records'][0]['ct'])" 2>/dev/null || echo '?')"
      log "  $obj today: $count"
    done
    return 0
  else
    warn "PROBE FAILED — HTTP ${http_code}. Response body:"
    cat /tmp/sf-obo-probe-result.json >&2; echo >&2
    log ""
    log "Common causes at this point:"
    log "  1. Secret is empty or has placeholder values — run script without --probe-only"
    log "  2. Connected App 'Use digital signatures' unchecked — go back to SF Setup"
    log "  3. Wrong cert uploaded — regenerate via this script and re-upload"
    log "  4. Integration user not preauth'd — 'Admin approved users are pre-authorized' in policies"
    log "  5. Cache-bust didn't propagate yet — wait 30s and retry --probe-only"
    return 1
  fi
}

if $PROBE_ONLY; then
  run_probe; exit $?
fi

# ---------------------------------------------------------------------------
# Verify-only — inspect the current secret shape without modifying anything.
# ---------------------------------------------------------------------------
verify_secret_shape() {
  log "Inspecting /006-v3/sf/bootstrap-creds..."
  local body
  body="$(aws secretsmanager get-secret-value --region "${AWS_REGION}" \
    --secret-id "${SECRET_ID}" --query 'SecretString' --output text 2>/dev/null || echo '{}')"

  python3 - <<PY
import json
try:
    d = json.loads('''${body//\'/\\\'}''')
except Exception:
    d = {}
checks = [
    ("client_id",        bool(d.get("client_id")) and not d.get("client_id","").startswith("<")),
    ("subject_pattern",  bool(d.get("subject_pattern"))),
    ("audience",         d.get("audience") == "https://login.salesforce.com"),
    ("private_key_pem",  bool(d.get("private_key_pem")) and "BEGIN" in d.get("private_key_pem","")),
]
for name, ok in checks:
    mark = "\033[1;32m✓\033[0m" if ok else "\033[1;31m✗\033[0m"
    print(f"  {mark} {name}")
all_ok = all(ok for _, ok in checks)
if not all_ok:
    print("\n  Secret is incomplete — run this script without --verify-only to set it up.")
    raise SystemExit(1)
print("\n  Secret looks complete. Try ./scripts/sf-obo-setup.sh --probe-only to verify live.")
PY
}

if $VERIFY_ONLY; then
  verify_secret_shape; exit $?
fi

# ---------------------------------------------------------------------------
# Full setup path.
# ---------------------------------------------------------------------------

log "=== Salesforce OBO Connected App setup ==="
log ""
log "This script does EVERYTHING on the AWS side. The Salesforce side requires"
log "ONE manual step: creating a Connected App via the SF Setup UI and uploading"
log "the cert we'll generate below. Follow the prompts."
log ""
log "Reference playbook: docs/v3-p0-sf-obo-fix.md"
log ""
read -r -p "Press ENTER to continue or Ctrl-C to abort... " _

# ---------------------------------------------------------------------------
# Step 1 — generate keypair + cert
# ---------------------------------------------------------------------------
TMP_DIR="$(mktemp -d -t fsi-obo-XXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

KEY_FILE="${TMP_DIR}/fsi-obo.key"
CRT_FILE="${TMP_DIR}/fsi-obo.crt"

log "Step 1/5: generating RSA keypair + self-signed cert..."
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -subj "/CN=fsi-workforce-360/O=FSI/C=US" \
  -keyout "$KEY_FILE" \
  -out "$CRT_FILE" 2>/dev/null
log "  Key: $KEY_FILE"
log "  Cert: $CRT_FILE"

# ---------------------------------------------------------------------------
# Step 2 — show cert so user can paste-upload it
# ---------------------------------------------------------------------------
echo ""
log "Step 2/5: upload this cert in Salesforce Setup."
log ""
log "  In Salesforce ('new-org'):"
log "    Setup -> App Manager -> New Connected App"
log "    Name:        'FSI Workforce 360 OBO'"
log "    API Name:    'FSI_Workforce_360_OBO'"
log "    Enable OAuth Settings: ✓"
log "    Callback URL: https://login.salesforce.com/services/oauth2/callback"
log "    Scopes:      api, refresh_token offline_access, full"
log "    Use digital signatures: ✓"
log "    Upload the cert shown below."
log ""
log "  Then: Manage Connected Apps -> the app -> Edit Policies"
log "    Permitted Users: Admin approved users are pre-authorized"
log ""
log "  ---------- CERT (paste or upload the file) ----------"
cat "$CRT_FILE"
log "  -----------------------------------------------------"
log ""
log "  Cert file path (if you want to upload instead of paste): $CRT_FILE"
echo ""
read -r -p "Press ENTER once you've saved the Connected App... " _

# ---------------------------------------------------------------------------
# Step 3 — collect Consumer Key + integration user from user
# ---------------------------------------------------------------------------
log "Step 3/5: paste the values from Salesforce."
echo ""

read -r -p "Consumer Key (from Connected App 'View' page): " CONSUMER_KEY
if [[ -z "$CONSUMER_KEY" || "$CONSUMER_KEY" == "<"* ]]; then
  fatal "Consumer Key is required"
fi

SF_INTEGRATION_USER_DEFAULT="$(aws secretsmanager get-secret-value --region "${AWS_REGION}" \
  --secret-id "${SECRET_ID}" --query 'SecretString' --output text 2>/dev/null \
  | jq -r '.integration_user // empty' 2>/dev/null || echo '')"
[[ -z "$SF_INTEGRATION_USER_DEFAULT" ]] && SF_INTEGRATION_USER_DEFAULT="multipleplatforms001.63e8e336be48@agentforce.com"

read -r -p "Integration user email [${SF_INTEGRATION_USER_DEFAULT}]: " SF_USER
SF_USER="${SF_USER:-$SF_INTEGRATION_USER_DEFAULT}"

# ---------------------------------------------------------------------------
# Step 4 — build secret JSON, PUT to Secrets Manager
# ---------------------------------------------------------------------------
log "Step 4/5: writing secret to /006-v3/sf/bootstrap-creds..."

SECRET_JSON="${TMP_DIR}/secret.json"
python3 - <<PY > "$SECRET_JSON"
import json
body = {
    "client_id":       "${CONSUMER_KEY}",
    "subject_pattern": "${SF_USER}",
    "audience":        "https://login.salesforce.com",
    "private_key_pem": open("${KEY_FILE}").read(),
}
print(json.dumps(body))
PY

aws secretsmanager put-secret-value --region "${AWS_REGION}" \
  --secret-id "${SECRET_ID}" \
  --secret-string "file://${SECRET_JSON}" >/dev/null \
  || fatal "put-secret-value failed"

log "  Secret updated."

# ---------------------------------------------------------------------------
# Step 5 — cache-bust the sf-auth-proxy Lambda and probe.
# ---------------------------------------------------------------------------
log "Step 5/5: busting sf-auth-proxy cold-start cache + running probe..."

existing_env="$(aws lambda get-function-configuration --region "${AWS_REGION}" \
  --function-name "${LAMBDA_NAME}" --query 'Environment.Variables' --output json 2>/dev/null || echo '{}')"
bump="$(date +%s)"
new_env="$(echo "$existing_env" | jq --arg b "$bump" '. + {CACHE_BUST:$b}')"

aws lambda update-function-configuration --region "${AWS_REGION}" \
  --function-name "${LAMBDA_NAME}" \
  --environment "Variables=$(echo "$new_env" | jq -c '.' | sed 's/"/\\"/g')" \
  >/dev/null \
  || warn "Lambda env update failed — probe may still pass if previous instance already expired"

sleep 10
run_probe && log "=== DONE. SF OBO is live. ===" || {
  warn "Probe did not pass — re-run with --probe-only after ~30s to retry."
  exit 1
}
