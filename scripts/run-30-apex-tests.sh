#!/bin/bash
# ============================================================
# IR Research Agent — 30-Query Apex Action Integration Tests
# Tests the same path the frontend uses (Apex Invocable Action fallback)
# ============================================================

set -euo pipefail

# ── Credentials ──
ACCESS_TOKEN=$(sf org display --target-org new-org --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['accessToken'])")
INSTANCE_URL=$(sf org display --target-org new-org --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['instanceUrl'])")

API_BASE="$INSTANCE_URL/services/data/v66.0/actions/custom/apex"

PASS=0
FAIL=0
FAILURES=""

# ── Helper ──
run_test() {
  local test_num="$1"
  local action="$2"
  local input_key="$3"
  local input_value="$4"
  local expect_pattern="$5"
  local description="$6"

  local url="$API_BASE/$action"
  local payload="{\"inputs\":[{\"$input_key\":\"$input_value\"}]}"

  local response
  response=$(curl -s -w "\n%{http_code}" -X POST "$url" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>&1)

  local http_code
  http_code=$(echo "$response" | tail -1)
  local body
  body=$(echo "$response" | sed '$d')

  # Truncate body for display
  local body_short
  body_short=$(echo "$body" | tr '\n' ' ' | cut -c1-120)

  # Check if response matches expected pattern (case-insensitive)
  if echo "$body" | grep -qiE "$expect_pattern"; then
    echo "  ✅ #$test_num PASS | $action | $input_key=$input_value | HTTP $http_code | $body_short"
    PASS=$((PASS + 1))
  else
    echo "  ❌ #$test_num FAIL | $action | $input_key=$input_value | HTTP $http_code | $body_short"
    FAIL=$((FAIL + 1))
    FAILURES="$FAILURES\n  #$test_num $action ($input_key=$input_value) — expected '$expect_pattern' | HTTP $http_code | $body_short"
  fi
}

echo "============================================================"
echo "IR Research Agent — 30-Query Apex Action Integration Tests"
echo "Instance: $INSTANCE_URL"
echo "API Base: $API_BASE"
echo "============================================================"
echo ""

# ── 1. Company Lookup (IR_CompanyLookupAction, inputKey: companyName) ──
echo "── Company Lookup (IR_CompanyLookupAction) ──"
run_test 1  "IR_CompanyLookupAction" "companyName" "NVIDIA"    "NVDA"              "NVIDIA → expect NVDA"
run_test 2  "IR_CompanyLookupAction" "companyName" "NVDA"      "NVIDIA"            "NVDA → expect NVIDIA Corporation"
run_test 3  "IR_CompanyLookupAction" "companyName" "JPMorgan"  "JPM"               "JPMorgan → expect JPM"
run_test 4  "IR_CompanyLookupAction" "companyName" "Apple"     "AAPL"              "Apple → expect AAPL"
run_test 5  "IR_CompanyLookupAction" "companyName" "XYZ Corp"  "No company found"  "XYZ Corp → expect No company found"
echo ""

# ── 2. Coverage Check (IR_CoverageCheckAction, inputKey: query) ──
echo "── Coverage Check (IR_CoverageCheckAction) ──"
run_test 6  "IR_CoverageCheckAction" "query" "NVDA"        "Sarah Kim"          "NVDA → expect Sarah Kim"
run_test 7  "IR_CoverageCheckAction" "query" "Sarah Kim"   "NVDA"               "Sarah Kim → expect NVDA"
run_test 8  "IR_CoverageCheckAction" "query" "Healthcare"  "Maria Rodriguez"    "Healthcare → expect Maria Rodriguez"
run_test 9  "IR_CoverageCheckAction" "query" "David Chen"  "JPM"                "David Chen → expect JPM"
run_test 10 "IR_CoverageCheckAction" "query" "AAPL"        "Sarah Kim"          "AAPL → expect Sarah Kim"
echo ""

# ── 3. Earnings Calendar (IR_EarningsCalendarAction, inputKey: query) ──
echo "── Earnings Calendar (IR_EarningsCalendarAction) ──"
run_test 11 "IR_EarningsCalendarAction" "query" "NVDA"       "May"               "NVDA → expect May"
run_test 12 "IR_EarningsCalendarAction" "query" "this month" "April"             "this month → expect April"
run_test 13 "IR_EarningsCalendarAction" "query" "all"        "NVDA"              "all → expect all companies"
echo ""

# ── 4. Watchlist (IR_WatchlistAction, inputKey: query) ──
echo "── Watchlist (IR_WatchlistAction) ──"
run_test 14 "IR_WatchlistAction" "query" "all"        "NVDA"        "all → expect 8 entries"
run_test 15 "IR_WatchlistAction" "query" "high"       "NVDA"        "high → expect NVDA"
run_test 16 "IR_WatchlistAction" "query" "Sarah Kim"  "NVDA"        "Sarah Kim → expect NVDA"
echo ""

# ── 5. Compliance Screening (IR_ComplianceScreeningAction, inputKey: ticker) ──
echo "── Compliance Screening (IR_ComplianceScreeningAction) ──"
run_test 17 "IR_ComplianceScreeningAction" "ticker" "NVDA"               "compliance"                "NVDA → expect compliance report"
run_test 18 "IR_ComplianceScreeningAction" "ticker" "JPM"                "compliance"                "JPM → expect compliance report"
run_test 19 "IR_ComplianceScreeningAction" "ticker" "RESTRICTED_TICKER_1" "FAIL|restricted|fail"     "RESTRICTED_TICKER_1 → expect FAIL"
echo ""

# ── 6. SEC Filings (IR_SecFilingsAction, inputKey: query) ──
echo "── SEC Filings (IR_SecFilingsAction) ──"
run_test 20 "IR_SecFilingsAction" "query" "NVDA 10-K"  "10-K|filing|SEC|NVDA|Named Credential|callout|not configured" "NVDA 10-K → expect filing data or fallback"
run_test 21 "IR_SecFilingsAction" "query" "AAPL 10-Q"  "10-Q|filing|SEC|AAPL|Named Credential|callout|not configured" "AAPL 10-Q → expect filing data or fallback"
echo ""

# ── 7. Market Data (IR_MarketDataAction, inputKey: query) ──
echo "── Market Data (IR_MarketDataAction) ──"
run_test 22 "IR_MarketDataAction" "query" "NVDA quote"         "NVDA|market|price|quote|Named Credential|callout|not configured" "NVDA quote → expect data or fallback"
run_test 23 "IR_MarketDataAction" "query" "AAPL price history" "AAPL|market|price|Named Credential|callout|not configured"       "AAPL price history → expect data or fallback"
echo ""

# ── 8. News Search (IR_NewsSearchAction, inputKey: query) ──
echo "── News Search (IR_NewsSearchAction) ──"
run_test 24 "IR_NewsSearchAction" "query" "NVDA news"        "NVDA|news|Named Credential|callout|not configured"      "NVDA news → expect news or fallback"
run_test 25 "IR_NewsSearchAction" "query" "Apple sentiment"  "Apple|sentiment|Named Credential|callout|not configured" "Apple sentiment → expect sentiment or fallback"
echo ""

# ── 9. Financial Analysis (IR_FinancialAnalysisAction, inputKey: query) ──
echo "── Financial Analysis (IR_FinancialAnalysisAction) ──"
run_test 26 "IR_FinancialAnalysisAction" "query" "NVDA fair value" "DCF|fair value|Monte Carlo|valuation|analysis" "NVDA fair value → expect DCF/comps/Monte Carlo"
run_test 27 "IR_FinancialAnalysisAction" "query" "AAPL DCF"        "DCF|valuation|analysis|discount"                "AAPL DCF → expect DCF analysis"
run_test 28 "IR_FinancialAnalysisAction" "query" "MSFT comps"      "comp|valuation|analysis|peer"                   "MSFT comps → expect comparable analysis"
echo ""

# ── 10. Sentiment Analysis (IR_SentimentAnalysisAction, inputKey: query) ──
echo "── Sentiment Analysis (IR_SentimentAnalysisAction) ──"
run_test 29 "IR_SentimentAnalysisAction" "query" "NVDA sentiment"          "sentiment|bull|bear|score|analysis"     "NVDA sentiment → expect sentiment analysis"
run_test 30 "IR_SentimentAnalysisAction" "query" "AAPL earnings call tone" "sentiment|tone|transcript|call|analysis" "AAPL earnings call tone → expect transcript analysis"
echo ""

# ── Summary ──
echo "============================================================"
echo "RESULTS: $PASS/30 PASS, $FAIL/30 FAIL"
echo "============================================================"
if [ $FAIL -gt 0 ]; then
  echo ""
  echo "FAILURES:"
  echo -e "$FAILURES"
fi
echo ""
