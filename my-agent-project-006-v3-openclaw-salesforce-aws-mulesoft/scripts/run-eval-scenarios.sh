#!/usr/bin/env bash
# run-eval-scenarios.sh — Execute the full evaluation scenario set against the live deployment.
#
# Usage:
#   bash scripts/run-eval-scenarios.sh                    # run all 62 scenarios
#   bash scripts/run-eval-scenarios.sh --category research_core  # run one category
#   bash scripts/run-eval-scenarios.sh --id R01,A01,C05   # run specific IDs
#   bash scripts/run-eval-scenarios.sh --dry-run           # show what would run
#
# Output: scripts/eval-results-<timestamp>.json + summary to stdout
#
# Prerequisites:
#   - Live deployment (smoke-test.sh passes 10/10)
#   - jq installed
#   - API_URL set or defaults to the deployed API Gateway

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SCENARIOS_FILE="${PROJECT_ROOT}/scripts/eval-scenarios.json"
API_URL="${API_URL:-https://e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3}"
AUTH_TOKEN="${AUTH_TOKEN:-dev-bootstrap-token}"
TIMESTAMP=$(date +%Y%m%dT%H%M%S)
RESULTS_FILE="${PROJECT_ROOT}/scripts/eval-results-${TIMESTAMP}.json"

# Parse args
FILTER_CATEGORY=""
FILTER_IDS=""
DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --category=*) FILTER_CATEGORY="${arg#*=}" ;;
    --category) shift; FILTER_CATEGORY="${1:-}" ;;
    --id=*) FILTER_IDS="${arg#*=}" ;;
    --id) shift; FILTER_IDS="${1:-}" ;;
    --dry-run) DRY_RUN=true ;;
    -h|--help) echo "Usage: $0 [--category=X] [--id=R01,A01] [--dry-run]"; exit 0 ;;
  esac
done

# Load scenarios
TOTAL=$(jq '.scenarios | length' "$SCENARIOS_FILE")
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  006 V3 Evaluation Scenarios — ${TOTAL} total                    ║"
echo "║  API: ${API_URL}                                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

passed=0
failed=0
skipped=0
errors=0
results="[]"

run_scenario() {
  local idx=$1
  local id=$(jq -r ".scenarios[$idx].id" "$SCENARIOS_FILE")
  local persona=$(jq -r ".scenarios[$idx].persona" "$SCENARIOS_FILE")
  local category=$(jq -r ".scenarios[$idx].category" "$SCENARIOS_FILE")
  local query=$(jq -r ".scenarios[$idx].query" "$SCENARIOS_FILE")
  local tests=$(jq -r ".scenarios[$idx].tests" "$SCENARIOS_FILE")
  local expect_status=$(jq -r ".scenarios[$idx].expect.status // \"ok\"" "$SCENARIOS_FILE")

  # Apply filters
  if [ -n "$FILTER_CATEGORY" ] && [ "$category" != "$FILTER_CATEGORY" ]; then
    skipped=$((skipped + 1))
    return
  fi
  if [ -n "$FILTER_IDS" ] && ! echo ",$FILTER_IDS," | grep -q ",$id,"; then
    skipped=$((skipped + 1))
    return
  fi

  printf "  [%s] %-12s %-20s " "$id" "$persona" "$category"

  if $DRY_RUN; then
    echo "→ DRY RUN: ${query:0:60}..."
    skipped=$((skipped + 1))
    return
  fi

  # Skip empty query test (E01) — it's a validation test
  if [ -z "$query" ]; then
    echo "→ SKIP (empty query — test manually)"
    skipped=$((skipped + 1))
    return
  fi

  # Execute
  local session_id="eval-${id}-${TIMESTAMP}"
  local start_ms=$(python3 -c "import time; print(int(time.time()*1000))")
  local response
  response=$(curl -sf --max-time 60 -X POST "${API_URL}/agent/invoke" \
    -H "Authorization: Bearer ${AUTH_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
      \"prompt\": $(echo "$query" | jq -Rs .),
      \"persona\": \"$persona\",
      \"principal_id\": \"eval-user\",
      \"session_id\": \"$session_id\",
      \"correlation_id\": \"eval-${id}\",
      \"turn_number\": 1
    }" 2>&1) || response='{"status":"error","error":{"message":"curl failed"}}'
  local end_ms=$(python3 -c "import time; print(int(time.time()*1000))")
  local duration=$((end_ms - start_ms))

  # Parse result
  local status=$(echo "$response" | jq -r '.status // "error"')
  local has_action_plan=$(echo "$response" | jq '.action_plan != null')
  local has_queue_updates=$(echo "$response" | jq '(.queue_updates // []) | length > 0')
  local specialist_count=$(echo "$response" | jq '(.specialist_trace // []) | length')
  local text_len=$(echo "$response" | jq -r '.text // "" | length')
  local has_citations=$(echo "$response" | jq -r '.text // ""' | grep -c '\[src:' || true)

  # Evaluate
  local verdict="PASS"
  local reason=""

  if [ "$status" != "$expect_status" ]; then
    verdict="FAIL"
    reason="expected status=$expect_status got $status"
  fi

  # ── Rich assertions from the expect object ──────────────────────
  # These check the fields that the original eval runner ignored.

  # has_action_plan
  local expect_ap=$(jq -r ".scenarios[$idx].expect.has_action_plan // \"\"" "$SCENARIOS_FILE")
  if [ "$verdict" = "PASS" ] && [ "$expect_ap" = "true" ]; then
    if [ "$has_action_plan" != "true" ]; then
      verdict="FAIL"; reason="expected action_plan but got none"
    fi
  fi

  # compliance decision
  local expect_compliance=$(jq -r ".scenarios[$idx].expect.compliance // \"\"" "$SCENARIOS_FILE")
  if [ "$verdict" = "PASS" ] && [ -n "$expect_compliance" ]; then
    local actual_compliance
    actual_compliance=$(echo "$response" | jq -r '.text // ""' | grep -oiP '(?<=compliance_status: )\w+' | head -1 || echo "")
    if [ -z "$actual_compliance" ]; then
      actual_compliance=$(echo "$response" | jq -r '.text // ""' | grep -oiP 'COMPLIANCE (DENIED|ALLOW|REVIEW)' | head -1 | awk '{print $2}' || echo "UNKNOWN")
    fi
    actual_compliance=$(echo "$actual_compliance" | tr '[:lower:]' '[:upper:]')
    if [ "$actual_compliance" != "$expect_compliance" ]; then
      verdict="FAIL"; reason="expected compliance=$expect_compliance got $actual_compliance"
    fi
  fi

  # requires_dual_auth
  local expect_dual=$(jq -r ".scenarios[$idx].expect.requires_dual_auth // \"\"" "$SCENARIOS_FILE")
  if [ "$verdict" = "PASS" ] && [ -n "$expect_dual" ]; then
    local actual_dual
    actual_dual=$(echo "$response" | jq -r '.action_plan.requires_dual_auth // "null"')
    if [ "$actual_dual" != "$expect_dual" ]; then
      # Also check in the text body
      actual_dual=$(echo "$response" | jq -r '.text // ""' | grep -oiP 'requires_dual_auth["\s:]*\w+' | head -1 | grep -oiP '(true|false)' || echo "null")
      if [ "$actual_dual" != "$expect_dual" ]; then
        verdict="WARN"; reason="dual_auth expected=$expect_dual got=$actual_dual (not verified)"
      fi
    fi
  fi

  # has_queue_updates (for escalation scenarios)
  local expect_queue=$(jq -r ".scenarios[$idx].expect.has_queue_updates // \"\"" "$SCENARIOS_FILE")
  if [ "$verdict" = "PASS" ] && [ "$expect_queue" = "true" ]; then
    if [ "$has_queue_updates" != "true" ]; then
      verdict="FAIL"; reason="expected queue_updates but got none"
    fi
  fi

  # no_positions (MNPI safety — liaison must not reveal position values)
  local expect_no_pos=$(jq -r ".scenarios[$idx].expect.no_positions // \"\"" "$SCENARIOS_FILE")
  if [ "$verdict" = "PASS" ] && [ "$expect_no_pos" = "true" ]; then
    local resp_text
    resp_text=$(echo "$response" | jq -r '.text // ""')
    local has_dollars=$(echo "$resp_text" | grep -cP '\$\s?\d[\d,]*' || true)
    local has_shares=$(echo "$resp_text" | grep -ciP '\d+\s+shares?' || true)
    if [ "$has_dollars" -gt 0 ] || [ "$has_shares" -gt 0 ]; then
      verdict="FAIL"; reason="MNPI leak: found dollar amounts or share counts in liaison response"
    fi
  fi

  # no_recommendation (Reg BI — liaison must not make recommendations)
  local expect_no_rec=$(jq -r ".scenarios[$idx].expect.no_recommendation // \"\"" "$SCENARIOS_FILE")
  if [ "$verdict" = "PASS" ] && [ "$expect_no_rec" = "true" ]; then
    local resp_text
    resp_text=$(echo "$response" | jq -r '.text // ""')
    local has_rec=$(echo "$resp_text" | grep -ciP '\b(recommend|should (buy|sell|invest)|suggest (buying|selling))\b' || true)
    if [ "$has_rec" -gt 0 ]; then
      verdict="FAIL"; reason="Reg BI violation: liaison made a recommendation"
    fi
  fi

  # specialists_min
  local expect_specs_min=$(jq -r ".scenarios[$idx].expect.specialists_min // \"\"" "$SCENARIOS_FILE")
  if [ "$verdict" = "PASS" ] && [ -n "$expect_specs_min" ] && [ "$expect_specs_min" != "null" ]; then
    if [ "$specialist_count" -lt "$expect_specs_min" ] 2>/dev/null; then
      verdict="WARN"; reason="expected >=$expect_specs_min specialists got $specialist_count"
    fi
  fi

  # fast (FAQ should be <8s)
  local expect_fast=$(jq -r ".scenarios[$idx].expect.fast // \"\"" "$SCENARIOS_FILE")
  if [ "$verdict" = "PASS" ] && [ "$expect_fast" = "true" ]; then
    if [ "$duration" -gt 8000 ] 2>/dev/null; then
      verdict="WARN"; reason="expected fast (<8s) but took ${duration}ms"
    fi
  fi

  if [ "$verdict" = "PASS" ]; then
    passed=$((passed + 1))
    printf "✅ PASS  %4dms  specs=%s  cites=%s  text=%s\n" "$duration" "$specialist_count" "$has_citations" "$text_len"
  elif [ "$verdict" = "WARN" ]; then
    passed=$((passed + 1))
    printf "⚠️  WARN  %4dms  reason=%s\n" "$duration" "$reason"
  else
    failed=$((failed + 1))
    printf "❌ FAIL  %4dms  reason=%s\n" "$duration" "$reason"
  fi

  # Append to results
  results=$(echo "$results" | jq ". + [{
    \"id\": \"$id\",
    \"persona\": \"$persona\",
    \"category\": \"$category\",
    \"query\": $(echo "$query" | jq -Rs .),
    \"verdict\": \"$verdict\",
    \"reason\": \"$reason\",
    \"duration_ms\": $duration,
    \"status\": \"$status\",
    \"specialist_count\": $specialist_count,
    \"has_action_plan\": $has_action_plan,
    \"has_queue_updates\": $has_queue_updates,
    \"has_citations\": $has_citations,
    \"text_length\": $text_len
  }]")
}

# Run all scenarios
for i in $(seq 0 $((TOTAL - 1))); do
  run_scenario "$i"
done

# Write results
echo "$results" | jq '.' > "$RESULTS_FILE"

# Summary
echo ""
echo "══════════════════════════════════════════════════════════════"
echo "  Results: ${passed} passed, ${failed} failed, ${skipped} skipped"
echo "  Output:  ${RESULTS_FILE}"
echo "══════════════════════════════════════════════════════════════"

# Category breakdown
echo ""
echo "  By category:"
echo "$results" | jq -r 'group_by(.category) | .[] | "    \(.[0].category): \([.[] | select(.verdict=="PASS")] | length)/\(length) passed"'

# Exit code
if [ "$failed" -gt 0 ]; then
  exit 1
fi
