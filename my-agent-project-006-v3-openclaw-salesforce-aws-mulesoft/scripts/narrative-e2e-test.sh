#!/usr/bin/env bash
# End-to-end narrative test harness.
#
# For each narrative this script replays EXACTLY the API calls the v2 UI
# makes (via HttpAgentTransport) and verifies the envelope carries the
# fields the UI needs to render the narrative correctly.
#
# Not a unit test — a live probe against deployed infrastructure with
# honest assessment of what actually works vs what the UI would see fail.

set -u

API="${API_URL:-https://e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3}"
AUTH="Authorization: Bearer dev-token"
CT="Content-Type: application/json"

pass=0
fail=0
SID_BASE="n-e2e-$(date +%s)"

probe() {
    local label="$1"
    local method="$2"
    local endpoint="$3"
    local payload="$4"
    local timeout="${5:-30}"
    local out_file="/tmp/narr-${label//[^a-zA-Z0-9]/_}.json"
    printf "\n--- %s ---\n" "$label"
    code=$(curl -s -X "$method" "${API}${endpoint}" -H "$AUTH" -H "$CT" --data "$payload" --max-time "$timeout" -o "$out_file" -w "%{http_code}")
    size=$(wc -c < "$out_file" | tr -d ' ')
    printf "HTTP %s · %s bytes → %s\n" "$code" "$size" "$out_file"
    if [[ "$code" == "200" ]]; then return 0; else return 1; fi
}

check() {
    local label="$1"
    local expr="$2"
    local file="$3"
    if python3 -c "
import json, sys
try:
    env = json.load(open('$file'))
    assert $expr, 'assertion failed'
    print('  PASS  $label')
except Exception as e:
    print('  FAIL  $label — ' + str(e))
    sys.exit(1)
" 2>&1; then
        pass=$((pass + 1))
    else
        fail=$((fail + 1))
    fi
}

echo "================================================================"
echo "NARRATIVE END-TO-END TEST — live probes against deployed stack"
echo "================================================================"

# ============================================================
# NARRATIVE 1 — Earnings Morning (research persona)
# ============================================================
probe "N1_research_brief" POST "/agent/invoke" \
  "{\"prompt\":\"Research NVDA ahead of earnings - focus on data-center mix and China exposure\",\"persona\":\"fsi_research\",\"principal_id\":\"sarah\",\"session_id\":\"${SID_BASE}-n1-aaaaaaaaaaaaaaaaaaaa\",\"correlation_id\":\"${SID_BASE}-n1-001\",\"turn_number\":1}" \
  40

F=/tmp/narr-N1_research_brief.json
check "N1: envelope has non-empty text body" "len(env.get('text','')) > 100" "$F"
check "N1: specialist_trace has 3+ specialists (parallel fanout — allows 1 timeout)" "len(env.get('specialist_trace',[])) >= 3" "$F"
check "N1: at least one of market/filings specialists ran" "any(a in [s['agent_id'] for s in env.get('specialist_trace',[])] for a in ('market_specialist','filings_specialist'))" "$F"
check "N1: compliance_specialist always runs (trust gate)" "'compliance_specialist' in [s['agent_id'] for s in env.get('specialist_trace',[])]" "$F"
check "N1: gate_trace uses canonical names only" "all(g['gate'] in {'guardrails','mnpi_filter','compliance','hitl','dual_auth','mulesoft','audit'} for g in env.get('gate_trace',[]))" "$F"
check "N1: compliance gate passed (ALLOW)" "any(g['gate']=='compliance' and g['status']=='passed' for g in env.get('gate_trace',[]))" "$F"
check "N1: turn completed within 30s" "env.get('duration_ms',99999) < 30000" "$F"

# ============================================================
# NARRATIVE 2 — Client drives research (liaison → handoff → RM)
# ============================================================
probe "N2_client_message" POST "/agent/invoke" \
  "{\"prompt\":\"Marcus I am nervous about NVDA earnings. Should we lock some gains?\",\"persona\":\"fsi_client_liaison\",\"principal_id\":\"eleanor\",\"session_id\":\"${SID_BASE}-n2-aaaaaaaaaaaaaaaaaaaa\",\"correlation_id\":\"${SID_BASE}-n2-001\",\"turn_number\":1}" \
  30

F=/tmp/narr-N2_client_message.json
check "N2: liaison responds" "len(env.get('text','')) > 50" "$F"
check "N2: mentions RM handoff" "'RM' in env.get('text','') or 'marcus' in env.get('text','').lower()" "$F"
check "N2: disclaimer present" "'informational' in env.get('text','').lower() or 'recommendation' in env.get('text','').lower()" "$F"
check "N2: queue_updates emitted (handoff to RM)" "env.get('queue_updates') is not None and len(env.get('queue_updates',[])) > 0" "$F"
check "N2: turn completed within 25s (liaison + rm_handoff round-trip)" "env.get('duration_ms',99999) < 25000" "$F"

# ============================================================
# NARRATIVE 3 — Risk Alert (slide-only by design)
# ============================================================
echo
echo "--- N3 Risk Alert (slide-only by design) ---"
echo "  Design doc marks this as V4/slide-only. No live narrative test."
echo "  UI consumes pre-seeded Client_Alert__c rows in Salesforce."

# ============================================================
# NARRATIVE 4 — Demand Signal (slide-only by design)
# ============================================================
echo
echo "--- N4 Demand Signal (slide-only by design) ---"
echo "  Design doc marks this as V4/slide-only. No live narrative test."
echo "  UI DemandSignalsTab consumes pre-seeded queue items."

# ============================================================
# NARRATIVE 5 — Large Liquidation (advisor write path)
# ============================================================
probe "N5_advisor_draft" POST "/agent/invoke" \
  "{\"prompt\":\"Trim Eleanor Vance NVDA from 14.2% to 9.5% of equity sleeve, limit 211.10\",\"persona\":\"fsi_advisor\",\"principal_id\":\"marcus\",\"session_id\":\"${SID_BASE}-n5-aaaaaaaaaaaaaaaaaaaa\",\"correlation_id\":\"${SID_BASE}-n5-001\",\"turn_number\":1}" \
  30

F=/tmp/narr-N5_advisor_draft.json
check "N5: draft text returned" "len(env.get('text','')) > 50" "$F"
check "N5: action_plan surfaced (this is the key v2 fix)" "env.get('action_plan') is not None" "$F"
check "N5: action_plan has plan_id" "env.get('action_plan',{}).get('plan_id') is not None" "$F"
check "N5: action_plan has plan_hash (for HITL binding)" "env.get('action_plan',{}).get('plan_hash') is not None and len(env.get('action_plan',{}).get('plan_hash','')) == 64" "$F"
check "N5: gate_trace shows gates 1-3 passed (draft mode)" "sum(1 for g in env.get('gate_trace',[]) if g['gate'] in {'guardrails','mnpi_filter','compliance'} and g['status']=='passed') >= 3" "$F"
check "N5: draft turn completed within 30s (fits gateway timeout)" "env.get('duration_ms',99999) < 30000" "$F"

# Extract plan_id/plan_hash for approval round-trip
PLAN_ID=$(python3 -c "import json; d=json.load(open('$F')); print(d.get('action_plan',{}).get('plan_id','MISSING'))")
PLAN_HASH=$(python3 -c "import json; d=json.load(open('$F')); print(d.get('action_plan',{}).get('plan_hash','MISSING'))")
echo "  plan_id=$PLAN_ID"
echo "  plan_hash=${PLAN_HASH:0:16}..."

probe "N5_approve" POST "/agent/approve" \
  "{\"plan_id\":\"$PLAN_ID\",\"plan_hash\":\"$PLAN_HASH\",\"approved\":true,\"approver_principal_id\":\"marcus\"}" \
  10

F=/tmp/narr-N5_approve.json
check "N5: approve returns hitl gate" "any(g['gate']=='hitl' for g in env.get('gate_trace',[]))" "$F"
check "N5: hitl gate passed (token verified)" "any(g['gate']=='hitl' and g['status']=='passed' for g in env.get('gate_trace',[]))" "$F"
check "N5: dual_auth gate returned" "any(g['gate']=='dual_auth' for g in env.get('gate_trace',[]))" "$F"
check "N5: mulesoft gate honestly failed (CloudHub not deployed)" "any(g['gate']=='mulesoft' and g['status']=='failed' for g in env.get('gate_trace',[]))" "$F"
check "N5: audit gate passed (even on mulesoft failure)" "any(g['gate']=='audit' and g['status']=='passed' for g in env.get('gate_trace',[]))" "$F"

echo
echo "================================================================"
echo "RESULT: $pass passed · $fail failed"
echo "================================================================"
if (( fail > 0 )); then exit 1; fi
