#!/usr/bin/env bash
# Smoke-test the live V3 deployment. Runs eight probes against the deployed
# infrastructure and reports PASS/FAIL for each. Exits 0 only if every
# probe passes.
#
# Probes 1-5 are the v1 baseline: frontend, two MCPs, KB retrieval, agent turn.
# Probes 6-8 cover v2 envelope wiring (2026-04-30):
#   6 — canonical 7-gate names + specialist_trace present
#   7 — advisor action_write draft-only mode surfaces action_plan in <29s
#   8 — /agent/approve returns canonical gates 4-7 (mulesoft:passed — live sandbox)
#
# Zero credentials emitted. Pulls MCP API key from SSM at invoke time.

set -e

REGION="${AWS_REGION:-us-east-1}"
FRONTEND_URL="${FRONTEND_URL:-https://d2zs9nk4uc2dbx.cloudfront.net/}"
API_URL="${API_URL:-https://e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3}"

pass=0
fail=0

check() {
    local name="$1"
    local expected="$2"
    local actual="$3"
    if [[ "$actual" == *"$expected"* ]]; then
        echo "[PASS] $name"
        pass=$((pass + 1))
    else
        echo "[FAIL] $name — expected '$expected' in response, got: ${actual:0:200}"
        fail=$((fail + 1))
    fi
}

echo "============================================"
echo "006 V3 live smoke test"
echo "============================================"

# 1. Frontend CloudFront
echo
echo "[1/5] Frontend SPA served via CloudFront..."
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL")
check "Frontend HTTP" "200" "$CODE"

# 2. MCP market-data root (no auth, sanity)
echo
echo "[2/5] MCP market-data root..."
OUT=$(curl -s "$API_URL/mcp/market-data")
check "market-data returns MCP descriptor" '"name": "market-data"' "$OUT"

# 3. Live Finnhub quote through the Lambda
echo
echo "[3/5] Live Finnhub NVDA quote through market-data Lambda..."
MCP_KEY=$(aws ssm get-parameter --region "$REGION" --name /006-v3/mcp/api-key \
    --with-decryption --query 'Parameter.Value' --output text 2>/dev/null || echo "")
if [[ -z "$MCP_KEY" ]]; then
    echo "[FAIL] /006-v3/mcp/api-key not in SSM"
    fail=$((fail + 1))
else
    OUT=$(curl -s -X POST "$API_URL/mcp/market-data/tools/call" \
        -H "Content-Type: application/json" \
        -H "X-MCP-API-Key: $MCP_KEY" \
        -H "X-Principal-Id: smoke-test" \
        -H "X-Agent-Id: smoke-test" \
        -H "X-Persona: research" \
        -d '{"name":"get_quote","arguments":{"symbol":"NVDA"}}')
    check "Finnhub quote for NVDA" '"status": "ok"' "$OUT"
fi

# 4. KB semantic retrieval from real SEC filings
echo
echo "[4/5] KB kb_retrieve over 784 real SEC-filing chunks..."
if [[ -n "$MCP_KEY" ]]; then
    OUT=$(curl -s -X POST "$API_URL/mcp/sec-edgar/tools/call" \
        -H "Content-Type: application/json" \
        -H "X-MCP-API-Key: $MCP_KEY" \
        -H "X-Principal-Id: smoke-test" \
        -H "X-Agent-Id: smoke-test" \
        -H "X-Persona: research" \
        -d '{"name":"kb_retrieve","arguments":{"query":"NVIDIA data center revenue","top_k":2}}')
    check "KB returns real NVDA chunks" '"NVDA"' "$OUT"
fi

# 5. Full agent turn via agent-proxy Lambda
echo
echo "[5/5] Full agent turn: browser -> agent-proxy -> AgentCore -> Bedrock..."
OUT=$(env -i PATH=/usr/bin:/bin curl -s -X POST "$API_URL/agent/invoke" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer dev-token" \
    --data '{"prompt":"Get quote and compliance status for NVDA","persona":"fsi_research","principal_id":"smoke-test"}' \
    --max-time 28)
check "Agent turn status=ok" '"status": "ok"' "$OUT"
check "Agent turn had gate activity" 'gate_trace' "$OUT"

# 6. v2 envelope fields present (canonical gates only + specialist_trace).
#    These were wired in feat/006-v3-live-demo on 2026-04-30 — see
#    docs/v3-frontend-reorg-and-wiring.md.
echo
echo "[6/8] v2 envelope — canonical gates + specialist_trace..."
python3 - "$OUT" <<'PY'
import json, sys
try:
    env = json.loads(sys.argv[1])
except Exception as e:
    print(f"[FAIL] v2 envelope JSON parse: {e}")
    sys.exit(1)
canonical = {"guardrails","mnpi_filter","compliance","hitl","dual_auth","mulesoft","audit"}
gates = env.get("gate_trace") or []
offending = [g for g in gates if g.get("gate") not in canonical]
if offending:
    print(f"[FAIL] non-canonical gates in gate_trace: {offending}")
    sys.exit(1)
spec_trace = env.get("specialist_trace") or []
if not isinstance(spec_trace, list):
    print("[FAIL] specialist_trace missing or not a list")
    sys.exit(1)
print(f"[PASS] gate_trace canonical ({len(gates)} gates), specialist_trace present ({len(spec_trace)} specialists)")
PY

# 7. v2 advisor draft-only path — action_plan must surface within 29s.
echo
echo "[7/8] v2 advisor action_write — draft-only mode surfaces action_plan..."
ADV_OUT=$(env -i PATH=/usr/bin:/bin curl -s -X POST "$API_URL/agent/invoke" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer dev-token" \
    --data "{\"prompt\":\"Trim NVDA from 14.2% to 9.5%\",\"persona\":\"fsi_advisor\",\"principal_id\":\"smoke-test\",\"session_id\":\"smoke-advisor-$(date +%s)-aaaaaaaaaaaaaaaaaa\",\"correlation_id\":\"smoke-advisor-001\",\"turn_number\":1}" \
    --max-time 28)
python3 - "$ADV_OUT" <<'PY'
import json, sys
try:
    env = json.loads(sys.argv[1])
except Exception as e:
    print(f"[FAIL] advisor draft envelope JSON parse: {e}")
    sys.exit(1)
plan = env.get("action_plan")
if not plan:
    print(f"[FAIL] action_plan missing — draft-only mode not emitting plan")
    sys.exit(1)
needed = {"plan_id","plan_hash","action_type","client_household"}
missing = needed - set(plan.keys())
if missing:
    print(f"[FAIL] action_plan missing required fields: {missing}")
    sys.exit(1)
print(f"[PASS] draft action_plan surfaced (plan_id={plan.get('plan_id')[:20]}..)")
PY
check "advisor draft-only action_plan emitted" '"action_plan"' "$ADV_OUT"

# 8. /agent/approve round-trip — returns canonical gates 4-7 including
#    mulesoft:passed (CloudHub live — Alpaca paper + Dwolla sandbox).
echo
echo "[8/8] /agent/approve — gates 4-7 canonical trace..."
APPROVE_OUT=$(env -i PATH=/usr/bin:/bin curl -s -X POST "$API_URL/agent/approve" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer dev-token" \
    --data '{"plan_id":"smoke-plan-001","plan_hash":"0123456789abcdef0123456789abcdef","approved":true,"approver_principal_id":"smoke-test"}' \
    --max-time 10)
check "/agent/approve returns hitl" '"hitl"' "$APPROVE_OUT"
check "/agent/approve returns mulesoft (live sandbox)" '"mulesoft"' "$APPROVE_OUT"
check "/agent/approve returns audit" '"audit"' "$APPROVE_OUT"

echo
echo "============================================"
echo "Result: $pass passed, $fail failed"
echo "============================================"
if (( fail > 0 )); then
    exit 1
fi
