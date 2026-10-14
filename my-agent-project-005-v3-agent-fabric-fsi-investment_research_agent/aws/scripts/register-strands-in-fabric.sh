#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# register-strands-in-fabric.sh — Register the Financial Analysis and
# Sentiment Analysis A2A agents with the MuleSoft Anypoint Agent Registry.
#
# Usage:
#   ./register-strands-in-fabric.sh [--stack STACK_NAME] [--region REGION]
#                                   [--registry-url URL] [--dry-run]
#
# Discovery order for prerequisites:
#
#   1. CloudFormation stack outputs (read via `aws cloudformation describe-stacks`):
#        - FinancialAnalysisA2AManifestUrl
#        - SentimentAnalysisA2AManifestUrl
#      Stack name defaults to $STACK_NAME env var or "ir-research-v3".
#
#   2. Anypoint Agent Registry base URL, in order:
#        a. --registry-url flag
#        b. $ANYPOINT_AGENT_REGISTRY_URL env var
#        c. prefix `https://anypoint.mulesoft.com/agent-registry/api/v1/organizations/${ANYPOINT_ORG_ID}`
#      If none resolves, the script exits with status 2 and marks PENDING
#      in the receipt so the GATEWAY subagent can fill it in later.
#
#   3. Auth — Anypoint access token from $ANYPOINT_ACCESS_TOKEN, fallback to
#      `anypoint-cli-v4 account profile --current --output token 2>/dev/null`.
#
# Registry behaviour is idempotent:
#   * POST /agents with body {name, manifestUrl, ...}  returns 201 or 409.
#   * On 409 we fetch the existing agent id and PATCH with the new manifestUrl.
#
# Output:
#   * stdout — a JSON blob containing agent ids for each Strands agent
#   * ${RECEIPT_FILE:-agent-fabric/.build-receipts/strands-registration.json}
#     — same blob persisted for downstream receipts.
# -----------------------------------------------------------------------------

set -euo pipefail

STACK_NAME="${STACK_NAME:-ir-research-v3}"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
REGISTRY_URL=""
DRY_RUN="false"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RECEIPT_FILE="${RECEIPT_FILE:-$REPO_ROOT/agent-fabric/.build-receipts/strands-registration.json}"

# ---------- arg parsing ----------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --stack)
            STACK_NAME="$2"; shift 2;;
        --region)
            REGION="$2"; shift 2;;
        --registry-url)
            REGISTRY_URL="$2"; shift 2;;
        --dry-run)
            DRY_RUN="true"; shift;;
        -h|--help)
            sed -n '/^# Usage:/,/^# ----/p' "$0" | sed 's/^# //; s/^#//'
            exit 0;;
        *)
            echo "Unknown argument: $1" >&2; exit 64;;
    esac
done

log()  { printf '[register-strands] %s\n' "$*" >&2; }
fail() { printf '[register-strands] ERROR: %s\n' "$*" >&2; exit 1; }

# ---------- prerequisites ----------
command -v aws  >/dev/null 2>&1 || fail "aws CLI not found on PATH"
command -v jq   >/dev/null 2>&1 || fail "jq not found on PATH"
command -v curl >/dev/null 2>&1 || fail "curl not found on PATH"

# ---------- stack outputs ----------
log "Reading stack outputs: stack=$STACK_NAME region=$REGION"
STACK_OUTPUTS_JSON="$(
    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs' \
        --output json 2>/dev/null \
    || echo '[]'
)"

if [[ "$STACK_OUTPUTS_JSON" == "[]" ]]; then
    fail "CloudFormation stack '$STACK_NAME' not found in $REGION. Deploy first with 'sam deploy'."
fi

get_output() {
    echo "$STACK_OUTPUTS_JSON" | jq -r ".[] | select(.OutputKey==\"$1\") | .OutputValue"
}

FIN_MANIFEST_URL="$(get_output FinancialAnalysisA2AManifestUrl)"
FIN_AGENT_URL="$(get_output FinancialAnalysisA2AAgentUrl)"
SENT_MANIFEST_URL="$(get_output SentimentAnalysisA2AManifestUrl)"
SENT_AGENT_URL="$(get_output SentimentAnalysisA2AAgentUrl)"

[[ -n "$FIN_MANIFEST_URL"  ]] || fail "Missing stack output FinancialAnalysisA2AManifestUrl"
[[ -n "$SENT_MANIFEST_URL" ]] || fail "Missing stack output SentimentAnalysisA2AManifestUrl"

log "Financial manifest:  $FIN_MANIFEST_URL"
log "Sentiment manifest:  $SENT_MANIFEST_URL"

# ---------- manifest sanity check ----------
for url in "$FIN_MANIFEST_URL" "$SENT_MANIFEST_URL"; do
    log "Validating manifest reachable: $url"
    status="$(curl -sS -o /dev/null -w '%{http_code}' -H "x-api-key: ${API_KEY_VALUE:-}" "$url" || echo '000')"
    if [[ "$status" != "200" ]]; then
        log "WARN: manifest $url returned HTTP $status (continuing; registry may fetch later)"
    fi
done

# ---------- registry URL resolution ----------
if [[ -z "$REGISTRY_URL" ]]; then
    REGISTRY_URL="${ANYPOINT_AGENT_REGISTRY_URL:-}"
fi
if [[ -z "$REGISTRY_URL" && -n "${ANYPOINT_ORG_ID:-}" ]]; then
    REGISTRY_URL="https://anypoint.mulesoft.com/agent-registry/api/v1/organizations/${ANYPOINT_ORG_ID}"
fi

# ---------- auth resolution ----------
ANYPOINT_TOKEN="${ANYPOINT_ACCESS_TOKEN:-}"
if [[ -z "$ANYPOINT_TOKEN" ]] && command -v anypoint-cli-v4 >/dev/null 2>&1; then
    ANYPOINT_TOKEN="$(anypoint-cli-v4 account profile --current --output token 2>/dev/null || true)"
fi

# ---------- emit receipt helper ----------
write_receipt() {
    local status="$1"
    local fin_id="${2:-}"
    local sent_id="${3:-}"
    local note="${4:-}"
    mkdir -p "$(dirname "$RECEIPT_FILE")"
    cat > "$RECEIPT_FILE" <<EOF
{
  "status": "$status",
  "stackName": "$STACK_NAME",
  "region": "$REGION",
  "registryUrl": "${REGISTRY_URL:-PENDING}",
  "note": "$note",
  "agents": {
    "financial-analysis": {
      "manifestUrl": "$FIN_MANIFEST_URL",
      "agentUrl": "$FIN_AGENT_URL",
      "registryAgentId": "$fin_id"
    },
    "sentiment-analysis": {
      "manifestUrl": "$SENT_MANIFEST_URL",
      "agentUrl": "$SENT_AGENT_URL",
      "registryAgentId": "$sent_id"
    }
  },
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
    log "Receipt written: $RECEIPT_FILE"
    cat "$RECEIPT_FILE"
}

if [[ -z "$REGISTRY_URL" || -z "$ANYPOINT_TOKEN" ]]; then
    reason="REGISTRY_URL"
    [[ -z "$ANYPOINT_TOKEN" ]] && reason="ANYPOINT_ACCESS_TOKEN"
    write_receipt "PENDING" "" "" "Missing $reason — GATEWAY subagent must supply this before registration."
    log "PENDING — Anypoint registry URL or token not available. Receipt written; exiting 2."
    exit 2
fi

# ---------- registration helper ----------
register_agent() {
    local name="$1"
    local manifest_url="$2"

    local payload
    payload="$(jq -cn \
        --arg name "$name" \
        --arg manifest "$manifest_url" \
        '{name: $name, manifestUrl: $manifest, provider: "ir-research-v3", protocol: "a2a/v0.1.0"}')"

    if [[ "$DRY_RUN" == "true" ]]; then
        log "DRY RUN: POST $REGISTRY_URL/agents  body=$payload"
        echo "dry-run-$(date +%s)"
        return
    fi

    local resp status body
    resp="$(curl -sS -w $'\n%{http_code}' \
        -X POST "$REGISTRY_URL/agents" \
        -H "Authorization: Bearer $ANYPOINT_TOKEN" \
        -H "Content-Type: application/json" \
        -d "$payload")"
    status="$(echo "$resp" | tail -n1)"
    body="$(echo "$resp" | sed '$d')"

    case "$status" in
        201|200)
            echo "$body" | jq -r '.id // .agentId // "unknown"';;
        409)
            log "Agent '$name' already registered — fetching id and PATCHing manifest URL"
            local existing_id
            existing_id="$(curl -sS \
                -H "Authorization: Bearer $ANYPOINT_TOKEN" \
                "$REGISTRY_URL/agents?name=$name" \
                | jq -r '.items[0].id // .[0].id // ""')"
            if [[ -z "$existing_id" ]]; then
                fail "409 on POST but could not fetch existing agent id for '$name'"
            fi
            curl -sS -X PATCH "$REGISTRY_URL/agents/$existing_id" \
                -H "Authorization: Bearer $ANYPOINT_TOKEN" \
                -H "Content-Type: application/json" \
                -d "$payload" >/dev/null
            echo "$existing_id";;
        *)
            fail "Registry returned HTTP $status for '$name': $body";;
    esac
}

log "Registering Financial Analysis Agent..."
FIN_ID="$(register_agent 'Financial Analysis Agent' "$FIN_MANIFEST_URL")"
log "  -> id=$FIN_ID"

log "Registering Sentiment Analysis Agent..."
SENT_ID="$(register_agent 'Sentiment Analysis Agent' "$SENT_MANIFEST_URL")"
log "  -> id=$SENT_ID"

write_receipt "REGISTERED" "$FIN_ID" "$SENT_ID" "Registered in Anypoint Agent Registry."
log "Done."
