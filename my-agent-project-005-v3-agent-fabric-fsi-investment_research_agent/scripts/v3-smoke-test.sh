#!/usr/bin/env bash
# 005 V3 — 5-minute smoke test for post-deploy verification.
#
# Checks:
#   1. Flex Gateway /health returns 200
#   2. One MCP call through the gateway succeeds
#   3. MNPI redaction — POST a payload containing FinServ__Shares__c,
#      verify it is redacted in the response / audit
#   4. Rate-limit trip — hammer the gateway above 25 req/s, verify at
#      least one 429 is returned
#
# Env (required unless --only is used to restrict scope):
#   FLEX_GW_URL      — e.g. https://flex-gw.ir-prod.example.com
#   FLEX_GW_API_KEY  — API key (used as fallback alongside mTLS)
#
# Usage:
#   ./v3-smoke-test.sh                 # run all 4 checks
#   ./v3-smoke-test.sh --only health   # just check 1
#   ./v3-smoke-test.sh --only mcp
#   ./v3-smoke-test.sh --only mnpi
#   ./v3-smoke-test.sh --only rate-limit
#
# Exit code:
#   0 — all requested checks passed
#   N > 0 — the first failing check number

set -u
# Intentionally NOT set -e: we want each check to run and report.

ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY="$2"; shift 2 ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

should_run() {
  [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]
}

fail() {
  local code="$1"; shift
  echo "FAIL: $*" >&2
  exit "$code"
}

require_env() {
  for var in "$@"; do
    if [ -z "${!var:-}" ]; then
      fail 2 "env var $var is not set"
    fi
  done
}

# ────────────────────────────────────────────────────────────
# CHECK 1 — Flex Gateway health
# ────────────────────────────────────────────────────────────
check_health() {
  require_env FLEX_GW_URL
  echo "[1] Flex Gateway health..."
  local code
  code=$(curl -sS -o /tmp/v3-smoke-health.json -w "%{http_code}" \
    --max-time 10 "$FLEX_GW_URL/health" || echo "000")
  if [ "$code" != "200" ]; then
    fail 1 "[1] /health returned $code (expected 200). Body: $(cat /tmp/v3-smoke-health.json 2>/dev/null)"
  fi
  echo "[1] PASS — /health = 200"
}

# ────────────────────────────────────────────────────────────
# CHECK 2 — One MCP call through gateway
# ────────────────────────────────────────────────────────────
check_mcp() {
  require_env FLEX_GW_URL FLEX_GW_API_KEY
  echo "[2] MCP call through gateway (market-data.get_quote NVDA)..."
  local resp_file=/tmp/v3-smoke-mcp.json
  local code
  code=$(curl -sS -o "$resp_file" -w "%{http_code}" \
    --max-time 15 \
    -X POST "$FLEX_GW_URL/market-data/tools/call" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $FLEX_GW_API_KEY" \
    -H "X-Agent-ID: smoke-test" \
    -H "X-Correlation-Id: smoke-$(date +%s)-mcp" \
    -d '{"name":"get_quote","arguments":{"symbol":"NVDA"}}' || echo "000")
  if [ "$code" != "200" ]; then
    fail 2 "[2] MCP call returned $code (expected 200). Body: $(cat "$resp_file" 2>/dev/null)"
  fi
  if ! grep -q '"NVDA"' "$resp_file"; then
    fail 2 "[2] MCP response missing NVDA symbol. Body: $(cat "$resp_file")"
  fi
  echo "[2] PASS — MCP call succeeded, response contains NVDA"
}

# ────────────────────────────────────────────────────────────
# CHECK 3 — MNPI redaction
# ────────────────────────────────────────────────────────────
check_mnpi() {
  require_env FLEX_GW_URL FLEX_GW_API_KEY
  echo "[3] MNPI redaction (FinServ__Shares__c must be blocked)..."
  local resp_file=/tmp/v3-smoke-mnpi.json
  local cid="smoke-$(date +%s)-mnpi"
  local code
  # Sentinel value 12345 — if it leaks through, reviewer check #5
  # looks for this string in IR_Audit_Log__c and fails.
  code=$(curl -sS -o "$resp_file" -w "%{http_code}" \
    --max-time 15 \
    -X POST "$FLEX_GW_URL/market-data/tools/call" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $FLEX_GW_API_KEY" \
    -H "X-Agent-ID: smoke-test" \
    -H "X-Correlation-Id: $cid" \
    -d '{
          "name":"get_quote",
          "arguments":{
            "symbol":"NVDA",
            "FinServ__Shares__c": 12345,
            "FinServ__MarketValue__c": 12345000
          }
        }' || echo "000")

  # We accept 200 (redact-and-forward) or 400 (block). Both are consistent
  # with mnpi-filter.yaml (currently set to redact, not block).
  if [ "$code" != "200" ] && [ "$code" != "400" ]; then
    fail 3 "[3] MNPI test returned $code. Body: $(cat "$resp_file" 2>/dev/null)"
  fi

  # The sentinel value must NOT echo back in the response body.
  if grep -q '12345' "$resp_file"; then
    fail 3 "[3] MNPI VIOLATION — sentinel value 12345 appeared in response body. $(cat "$resp_file")"
  fi

  # The response SHOULD contain a redaction marker (best-effort).
  # If the gateway does not surface the marker in the body, that's OK —
  # reviewer check #5 also verifies via IR_Audit_Log__c.
  if grep -qi 'redact' "$resp_file"; then
    echo "[3] PASS — redaction marker present, sentinel not echoed"
  else
    echo "[3] PASS — sentinel not echoed (redaction marker not in body, audit log will confirm)"
  fi
  echo "correlationId=$cid" > /tmp/v3-smoke-mnpi.cid
}

# ────────────────────────────────────────────────────────────
# CHECK 4 — Rate-limit trip
# ────────────────────────────────────────────────────────────
check_rate_limit() {
  require_env FLEX_GW_URL FLEX_GW_API_KEY
  echo "[4] Rate-limit trip (>25 req/s must produce >=1 429)..."
  local log=/tmp/v3-smoke-ratelimit.log
  : > "$log"

  # Fire 60 requests as fast as curl can in parallel. Threshold is
  # 25 req/s with burst of 50, so 60 rapid shots should see throttles.
  local i
  for i in $(seq 1 60); do
    curl -sS -o /dev/null -w "%{http_code} %{time_total}\n" \
      --max-time 5 \
      -X POST "$FLEX_GW_URL/market-data/tools/call" \
      -H "Content-Type: application/json" \
      -H "X-API-Key: $FLEX_GW_API_KEY" \
      -H "X-Agent-ID: smoke-test" \
      -d '{"name":"get_quote","arguments":{"symbol":"NVDA"}}' >> "$log" 2>&1 &
  done
  wait

  local throttled
  throttled=$(grep -c "^429 " "$log" || echo 0)
  if [ "$throttled" -lt 1 ]; then
    fail 4 "[4] No 429 responses observed in 60 rapid calls. Log: $(head -20 "$log")"
  fi
  echo "[4] PASS — observed $throttled rate-limit 429s out of 60 calls"
}

# ────────────────────────────────────────────────────────────
# Run
# ────────────────────────────────────────────────────────────
start=$(date +%s)

should_run health      && check_health
should_run mcp         && check_mcp
should_run mnpi        && check_mnpi
should_run rate-limit  && check_rate_limit

elapsed=$(( $(date +%s) - start ))
echo "All requested checks passed (${elapsed}s)."
exit 0
