#!/usr/bin/env bash
# ============================================================================
# 0-preflight.sh — Zero-to-deploy validator for Project 006 V3
#
# Runs every check that must pass BEFORE you touch AWS. Fails loudly with the
# exact remediation command for each failure. Idempotent; safe to re-run.
#
# Usage:
#   bash scripts/0-preflight.sh
#   bash scripts/0-preflight.sh --generate-signing-keys   (auto-fill missing)
#   bash scripts/0-preflight.sh --skip-vendor-reachability (offline / fast mode)
#   bash scripts/0-preflight.sh --help
#
# Exit codes:
#   0  — all checks passed, cleared to deploy
#   1  — one or more checks failed, see output
#   2  — invalid arguments
# ============================================================================

set -uo pipefail

GENERATE_KEYS=false
SKIP_VENDOR=false

for arg in "$@"; do
  case "$arg" in
    --generate-signing-keys) GENERATE_KEYS=true ;;
    --skip-vendor-reachability) SKIP_VENDOR=true ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# ANSI colors
BLUE='\033[1;34m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
RED='\033[1;31m'
RESET='\033[0m'

pass=0
fail=0
warn=0

log()   { printf "${BLUE}[0-preflight]${RESET} %s\n" "$*"; }
pass()  { printf "${BLUE}[0-preflight]${RESET} ${GREEN}✓${RESET} %s\n" "$*"; pass=$((pass + 1)); }
fail()  { printf "${BLUE}[0-preflight]${RESET} ${RED}✗${RESET} %s\n" "$*"; fail=$((fail + 1)); }
warning() { printf "${BLUE}[0-preflight]${RESET} ${YELLOW}⚠${RESET}  %s\n" "$*"; warn=$((warn + 1)); }
hint()  { printf "${BLUE}[0-preflight]${RESET}    → %s\n" "$*"; }

header() { printf "\n${BLUE}═══ %s ═══${RESET}\n" "$*"; }

# ============================================================================
# Check 1 — Local tools with version floors
# ============================================================================
header "1/7  Local tools"

# ver_ge "3.9.0" "3.8.1" → returns 0 if first is >= second
ver_ge() {
  printf '%s\n%s' "$1" "$2" | sort -V -C -r
}

check_tool() {
  local name="$1"
  local cmd="$2"
  local min_version="$3"
  local version_cmd="$4"

  if ! command -v "$cmd" >/dev/null 2>&1; then
    fail "$name not installed"
    hint "Install: see RUNBOOK.md Section 1.1"
    return 1
  fi

  local actual
  actual=$(eval "$version_cmd" 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)

  if [[ -z "$actual" ]]; then
    warning "$name version unknown (installed but couldn't parse version)"
    return 0
  fi

  if ver_ge "$actual" "$min_version"; then
    pass "$name $actual (need >= $min_version)"
  else
    fail "$name $actual is too old (need >= $min_version)"
    hint "Upgrade: see RUNBOOK.md Section 1.1"
    return 1
  fi
}

check_tool "AWS CLI"   "aws"     "2.15.0"  "aws --version"
check_tool "SAM CLI"   "sam"     "1.158.0" "sam --version"
check_tool "sf CLI"    "sf"      "2.128.5" "sf --version"
check_tool "Node"      "node"    "20.0.0"  "node --version"
check_tool "Python"    "python3" "3.12.0"  "python3 --version"
check_tool "Maven"     "mvn"     "3.9.0"   "mvn --version"
check_tool "Java"      "java"    "17.0.0"  "java --version 2>&1"
check_tool "CDK"       "cdk"     "2.1114"  "cdk --version"
check_tool "jq"        "jq"      "1.6"     "jq --version"

# Docker or Finch (either works)
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  pass "Docker running"
elif command -v finch >/dev/null 2>&1 && finch info >/dev/null 2>&1; then
  pass "Finch running"
else
  fail "Neither Docker nor Finch is running"
  hint "Start Docker Desktop or run: finch vm init && finch vm start"
fi

# ============================================================================
# Check 2 — AWS credentials + account identity
# ============================================================================
header "2/7  AWS credentials"

if ! aws sts get-caller-identity --region us-east-1 >/dev/null 2>&1; then
  fail "AWS credentials not configured or invalid"
  hint "Run: aws configure"
else
  account=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
  arn=$(aws sts get-caller-identity --query Arn --output text 2>/dev/null)
  pass "AWS identity: $arn"
  pass "AWS account: $account"

  # Warn if running as root user (should use IAM user or role)
  if [[ "$arn" == *":root" ]]; then
    warning "Running as AWS root user — strongly prefer an IAM user with AdministratorAccess"
    hint "Create IAM user: aws iam create-user --user-name 006-v3-deployer"
  fi
fi

# ============================================================================
# Check 3 — Bedrock model access
# ============================================================================
header "3/7  Bedrock model access"

check_bedrock_model() {
  local profile_id="$1"
  local human_name="$2"

  # Probe with a minimal converse call — 1 token out
  local resp
  resp=$(aws bedrock-runtime converse \
    --model-id "$profile_id" \
    --messages '[{"role":"user","content":[{"text":"ok"}]}]' \
    --inference-config '{"maxTokens":1}' \
    --region us-east-1 \
    --output json 2>&1)

  if echo "$resp" | grep -q "AccessDeniedException"; then
    fail "$human_name not granted ($profile_id)"
    hint "Open: https://console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess"
    hint "Request access to '$human_name' and re-run preflight"
    return 1
  elif echo "$resp" | grep -q '"stopReason"'; then
    pass "$human_name responds ($profile_id)"
  else
    warning "$human_name probe inconclusive — check manually"
    hint "Unexpected response: $(echo "$resp" | head -c 120)"
  fi
}

check_bedrock_model "us.anthropic.claude-sonnet-4-5-20250929-v1:0" "Claude Sonnet 4.5"
check_bedrock_model "us.anthropic.claude-haiku-4-5-20251001-v1:0" "Claude Haiku 4.5"

# Titan v2 is invoke-model, not converse
titan_resp=$(aws bedrock-runtime invoke-model \
  --model-id "amazon.titan-embed-text-v2:0" \
  --body '{"inputText":"ok"}' \
  --content-type "application/json" \
  --region us-east-1 \
  --cli-binary-format raw-in-base64-out \
  /tmp/.0-preflight-titan.json 2>&1)

if echo "$titan_resp" | grep -q "AccessDeniedException"; then
  fail "Amazon Titan Text Embeddings v2 not granted"
  hint "Open: https://console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess"
  hint "Request access to 'Titan Text Embeddings v2' and re-run preflight"
elif [[ -s /tmp/.0-preflight-titan.json ]]; then
  pass "Titan Text Embeddings v2 responds"
  rm -f /tmp/.0-preflight-titan.json
else
  warning "Titan v2 probe inconclusive"
fi

# Check NAT gateway quota — known failure mode
header "3b/7  VPC NAT gateway quota"

nat_quota=$(aws service-quotas get-service-quota \
  --service-code vpc --quota-code L-FE5A380F \
  --region us-east-1 \
  --query 'Quota.Value' --output text 2>/dev/null)

nat_used=$(aws ec2 describe-nat-gateways \
  --filter "Name=state,Values=available" \
  --region us-east-1 \
  --query 'length(NatGateways)' --output text 2>/dev/null)

if [[ -n "$nat_quota" && -n "$nat_used" ]]; then
  quota_int=${nat_quota%.*}
  if [[ "$nat_used" -lt $((quota_int - 1)) ]]; then
    pass "NAT gateway quota $nat_used/$quota_int (need at least 2 free for v3)"
  else
    fail "NAT gateway quota tight: $nat_used/$quota_int in use"
    hint "Either release unused NAT gateways or request increase:"
    hint "aws service-quotas request-service-quota-increase --service-code vpc --quota-code L-FE5A380F --desired-value 10 --region us-east-1"
  fi
else
  warning "Could not determine NAT gateway quota"
fi

# ============================================================================
# Check 4 — .env file exists and has real values
# ============================================================================
header "4/7  .env file"

if [[ ! -f ".env" ]]; then
  fail ".env file not found"
  hint "Copy template: cp .env.example .env"
  hint "Then edit .env and fill in real values (see RUNBOOK.md Section 1.4)"
else
  pass ".env file exists"

  # Check for placeholder values
  placeholder_count=$(grep -cE '<YOUR_|<GENERATE_|PLACEHOLDER' .env 2>/dev/null || echo 0)
  if [[ "$placeholder_count" -gt 0 ]]; then
    fail ".env has $placeholder_count placeholder values"
    hint "Run: grep -nE '<YOUR_|<GENERATE_|PLACEHOLDER' .env"
    hint "Replace each with the real credential"
  else
    pass ".env has no <YOUR_...> or <GENERATE_...> placeholders"
  fi

  # Source it to get vars available
  set -a; source .env 2>/dev/null; set +a
fi

# ============================================================================
# Check 5 — Signing keys (auto-generate if missing, --generate-signing-keys)
# ============================================================================
header "5/7  Signing keys"

check_hex_key() {
  local name="$1"
  local value="${2:-}"

  if [[ -z "$value" ]]; then
    if $GENERATE_KEYS; then
      local new_key
      new_key=$(openssl rand -hex 32)
      # write back to .env
      if grep -q "^$name=" .env 2>/dev/null; then
        # macOS sed requires ''
        sed -i.bak "s|^$name=.*|$name=$new_key|" .env && rm -f .env.bak
      else
        echo "$name=$new_key" >> .env
      fi
      pass "$name generated + written to .env"
    else
      fail "$name missing"
      hint "Generate: openssl rand -hex 32"
      hint "Or run: bash scripts/0-preflight.sh --generate-signing-keys"
    fi
  elif [[ ${#value} -lt 32 ]]; then
    fail "$name too short (${#value} chars, need at least 32 hex)"
  else
    pass "$name set (${#value} chars)"
  fi
}

check_hex_key "AGENTCORE_SESSION_SIGNING_KEY" "${AGENTCORE_SESSION_SIGNING_KEY:-}"
check_hex_key "HITL_SIGNING_KEY" "${HITL_SIGNING_KEY:-}"
check_hex_key "MCP_API_KEY" "${MCP_API_KEY:-}"

# MuleSoft key is AES-128 = 16 ASCII chars exactly
mule_key="${MULE_SECURE_PROPERTIES_KEY:-}"
if [[ -z "$mule_key" ]]; then
  warning "MULE_SECURE_PROPERTIES_KEY not set (needed only if deploying MuleSoft)"
  hint "Must be exactly 16 ASCII chars. Pick one like: MyMuleKey12345AB"
elif [[ ${#mule_key} -ne 16 ]]; then
  fail "MULE_SECURE_PROPERTIES_KEY is ${#mule_key} chars (must be exactly 16 for AES-128)"
else
  pass "MULE_SECURE_PROPERTIES_KEY set (16 chars)"
fi

# ============================================================================
# Check 6 — Vendor API reachability
# ============================================================================
header "6/7  Vendor API reachability"

if $SKIP_VENDOR; then
  warning "Skipping vendor reachability checks (--skip-vendor-reachability)"
else
  # Finnhub
  if [[ -n "${FINNHUB_API_KEY:-}" && "$FINNHUB_API_KEY" != *PLACEHOLDER* ]]; then
    if curl -sf -m 10 "https://finnhub.io/api/v1/quote?symbol=AAPL&token=$FINNHUB_API_KEY" | grep -q '"c"'; then
      pass "Finnhub responds with live AAPL quote"
    else
      fail "Finnhub API unreachable or key invalid"
      hint "Check key at https://finnhub.io/dashboard"
    fi
  else
    warning "FINNHUB_API_KEY not set or placeholder — market-data MCP will fail at runtime"
  fi

  # Tavily
  if [[ -n "${TAVILY_API_KEY:-}" && "$TAVILY_API_KEY" != *PLACEHOLDER* ]]; then
    if curl -sf -m 10 -X POST "https://api.tavily.com/search" \
        -H "Content-Type: application/json" \
        -d "{\"api_key\":\"$TAVILY_API_KEY\",\"query\":\"test\",\"max_results\":1}" >/dev/null 2>&1; then
      pass "Tavily responds"
    else
      fail "Tavily API unreachable or key invalid"
      hint "Check key at https://tavily.com"
    fi
  else
    warning "TAVILY_API_KEY not set or placeholder — news-search MCP will fail at runtime"
  fi

  # Alpaca paper
  if [[ -n "${ALPACA_KEY_ID:-}" && -n "${ALPACA_SECRET:-}" ]]; then
    if curl -sf -m 10 -H "APCA-API-KEY-ID: $ALPACA_KEY_ID" \
        -H "APCA-API-SECRET-KEY: $ALPACA_SECRET" \
        "https://paper-api.alpaca.markets/v2/account" | grep -q '"status"'; then
      pass "Alpaca paper account responds"
    else
      fail "Alpaca paper auth failed"
      hint "Check keys at https://app.alpaca.markets/paper/dashboard/overview"
    fi
  else
    warning "Alpaca credentials not set — mulesoft-actions will fail at runtime"
  fi

  # Dwolla sandbox
  if [[ -n "${DWOLLA_KEY:-}" && -n "${DWOLLA_SECRET:-}" ]]; then
    if curl -sf -m 10 -X POST "https://api-sandbox.dwolla.com/token" \
        -u "$DWOLLA_KEY:$DWOLLA_SECRET" \
        -d "grant_type=client_credentials" | grep -q '"access_token"'; then
      pass "Dwolla sandbox auth works"
    else
      fail "Dwolla sandbox auth failed"
      hint "Check keys at https://accounts-sandbox.dwolla.com"
    fi
  else
    warning "Dwolla credentials not set — initiate-wire will fail at runtime"
  fi

  # Langfuse
  if [[ -n "${LANGFUSE_PUBLIC_KEY:-}" && -n "${LANGFUSE_SECRET_KEY:-}" ]]; then
    if curl -sf -m 10 -u "$LANGFUSE_PUBLIC_KEY:$LANGFUSE_SECRET_KEY" \
        "${LANGFUSE_HOST:-https://us.cloud.langfuse.com}/api/public/projects" >/dev/null 2>&1; then
      pass "Langfuse API responds"
    else
      fail "Langfuse auth failed"
      hint "Check keys at https://us.cloud.langfuse.com/project/<your-project>/settings"
    fi
  else
    warning "Langfuse credentials not set — observability will fall back to stub"
  fi

  # Anypoint MuleSoft
  if [[ -n "${MULESOFT_CLIENT_ID:-}" && -n "${MULESOFT_CLIENT_SECRET:-}" ]]; then
    if curl -sf -m 10 -X POST "https://anypoint.mulesoft.com/accounts/api/v2/oauth2/token" \
        -d "grant_type=client_credentials&client_id=$MULESOFT_CLIENT_ID&client_secret=$MULESOFT_CLIENT_SECRET" \
        -H "Content-Type: application/x-www-form-urlencoded" | grep -q '"access_token"'; then
      pass "Anypoint OAuth works"
    else
      fail "Anypoint OAuth failed"
      hint "Check Connected App creds at https://anypoint.mulesoft.com/accounts"
    fi
  else
    warning "MuleSoft credentials not set — CloudHub deploy will be skipped"
  fi
fi

# ============================================================================
# Check 7 — Salesforce CLI auth
# ============================================================================
header "7/7  Salesforce CLI"

sf_orgs=$(sf org list --json 2>/dev/null | jq -r '.result.other[]?.alias, .result.devHubs[]?.alias' 2>/dev/null | sort -u)

if [[ -z "$sf_orgs" ]]; then
  fail "No Salesforce orgs connected"
  hint "Run: sf org login web --alias new-org"
else
  target="${SF_TARGET_ORG:-new-org}"
  if echo "$sf_orgs" | grep -qx "$target"; then
    pass "Salesforce org '$target' connected"
  else
    fail "SF_TARGET_ORG='$target' not in connected orgs"
    hint "Available orgs: $(echo $sf_orgs | tr '\n' ' ')"
    hint "Either change SF_TARGET_ORG in .env or run: sf org login web --alias $target"
  fi
fi

# ============================================================================
# Summary
# ============================================================================
header "Preflight Summary"
printf "  passed: ${GREEN}%d${RESET}\n" "$pass"
printf "  failed: ${RED}%d${RESET}\n" "$fail"
printf "  warnings: ${YELLOW}%d${RESET}\n" "$warn"
echo

if [[ "$fail" -gt 0 ]]; then
  printf "${RED}✗${RESET}  %d checks failed. Fix them and re-run preflight.\n" "$fail"
  echo
  exit 1
elif [[ "$warn" -gt 0 ]]; then
  printf "${YELLOW}⚠${RESET}  %d warnings. Deploy will work but some narratives may be degraded.\n" "$warn"
  printf "${GREEN}✓${RESET}  Cleared to deploy.\n"
  echo
  printf "Next step: bash scripts/deploy-all.sh\n"
  exit 0
else
  printf "${GREEN}✓${RESET}  All %d checks passed. You are cleared to deploy.\n" "$pass"
  echo
  printf "Next step: bash scripts/deploy-all.sh\n"
  exit 0
fi
