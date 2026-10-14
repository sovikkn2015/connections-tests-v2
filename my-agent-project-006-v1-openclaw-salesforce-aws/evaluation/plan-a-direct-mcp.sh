#!/usr/bin/env bash
# Plan A: 20 direct MCP calls against the live v1 gateway, with structured
# pass/fail. Run after the Secrets Manager + deps hardening to confirm
# every tool returns real (non-null, non-error) data.
#
# Usage: bash plan-a-direct-mcp.sh
# Output: plan-a-results.jsonl (one line per query)

set -u

GW="${GW:-https://2ifxjh92ig.execute-api.us-east-1.amazonaws.com/prod}"
KEY_ID=$(aws cloudformation describe-stacks --stack-name openclaw-mcp-006 \
  --region us-east-1 \
  --query "Stacks[0].Outputs[?OutputKey=='ApiKeyId'].OutputValue" --output text)
KEY=$(aws apigateway get-api-key --api-key "$KEY_ID" --include-value \
  --region us-east-1 --query value --output text)

OUT=plan-a-results.jsonl
: > "$OUT"

PASS=0; FAIL=0

run() {
  local qid=$1 srv=$2 tool=$3 args=$4 must_contain=$5
  local t0=$(python3 -c 'import time; print(int(time.time()*1000))')
  local resp
  resp=$(curl -sS --max-time 30 -X POST \
    -H "x-api-key: $KEY" -H "Content-Type: application/json" \
    -d "{\"name\":\"$tool\",\"arguments\":$args}" \
    "$GW/$srv/tools/call" 2>&1)
  local ms=$(( $(python3 -c 'import time; print(int(time.time()*1000))') - t0 ))

  local status inner
  if echo "$resp" | grep -qE '"error"[[:space:]]*:|"isError"[[:space:]]*:[[:space:]]*true|Internal server error'; then
    status=FAIL
  else
    inner=$(echo "$resp" | python3 -c "
import json,sys
try:
    d=json.loads(sys.stdin.read())
    c=d.get('content',[])
    if not c:
        print(''); sys.exit()
    t=c[0].get('text','')
    print(t)
except Exception as e:
    print('')
")
    if echo "$inner" | grep -qiE "$must_contain"; then
      status=PASS
    else
      status=FAIL
    fi
  fi

  if [[ $status == PASS ]]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); fi

  python3 -c "
import json
print(json.dumps({
    'id': $qid, 'server': '$srv', 'tool': '$tool',
    'status': '$status', 'latency_ms': $ms,
    'preview': '''${resp:0:180}'''.replace(chr(10),' ')[:180]
}))" >> "$OUT"

  printf "  %-4s Q%-3s %-14s %-30s %4dms\n" "$status" "$qid" "$srv" "$tool" "$ms"
}

echo "=== Plan A: 20 direct MCP queries ==="
echo "--- market-data (8) ---"
run  1 market-data     get_quote            '{"symbol":"NVDA"}'                 '"price": [0-9]'
run  2 market-data     get_quote            '{"symbol":"AAPL"}'                 '"price": [0-9]'
run  3 market-data     get_52_week_range    '{"symbol":"TSLA"}'                 'fiftyTwoWeek'
run  4 market-data     get_quote            '{"symbol":"\^GSPC"}'               '"price": [0-9]'
run  5 market-data     get_price_history    '{"symbol":"MSFT","period":"30d"}'  '"prices"'
run  6 market-data     get_quote            '{"symbol":"AMD"}'                  '"price": [0-9]'
run  9 market-data     get_quote            '{"symbol":"\^TNX"}'                '"price": [0-9]'
run 10 market-data     get_quote            '{"symbol":"CL=F"}'                 '"price": [0-9]'

echo "--- sec-edgar (2) ---"
run 21 sec-edgar       get_10q              '{"ticker":"NVDA"}'                 'filings|form|accession|cik'
run 24 sec-edgar       get_insider_transactions '{"ticker":"MSFT"}'             'filings|transactions|form|owner'

echo "--- news-search (4) ---"
run 25 news-search     search_financial_news '{"query":"Tesla","max_results":2}'         '"results"|"title"'
run 26 news-search     search_financial_news '{"query":"Fed rate decision","max_results":2}' '"results"|"title"'
run 28 news-search     search_financial_news '{"query":"NVIDIA ARM deal","max_results":2}'  '"results"|"title"'
run 30 news-search     search_financial_news '{"query":"tech layoffs","max_results":2}'     '"results"|"title"'

echo "--- salesforce-crm (2) ---"
run 11 salesforce-crm  run_soql_query       '{"query":"SELECT Id, Name FROM IR_Coverage__c LIMIT 3"}' '"records"|"Id"'
run 13 salesforce-crm  run_soql_query       '{"query":"SELECT Id FROM IR_Watchlist__c LIMIT 3"}'      '"records"|"Id"'

echo "--- multi-tool probes (4) ---"
run 34 market-data     get_quote            '{"symbol":"GOOGL"}'                '"price": [0-9]'
run 33 market-data     get_earnings_calendar '{"symbol":"MSFT","horizon":"3month"}' 'earnings|calendar|symbol'
run 31 market-data     get_earnings_calendar '{"symbol":"NVDA","horizon":"3month"}' 'earnings|calendar|symbol'
run 36 market-data     get_analyst_consensus '{"symbol":"GOOGL"}'               'recommendations|target|symbol'

echo
echo "=== RESULT: $PASS PASS, $FAIL FAIL of 20 ==="
echo "Details: $OUT"
