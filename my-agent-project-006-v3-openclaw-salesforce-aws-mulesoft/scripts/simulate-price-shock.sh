#!/usr/bin/env bash
# Narrative 3 demo trigger: simulate a -8% NVDA drawdown.
#
# Per v3-narrative-arc.md:
#   "For V3 demo this runs from a manual 'Simulate NVDA -8%' trigger, not a
#    live scheduler. The narrative is real; the trigger timing is staged."
#
# This script:
#   1. Queries IR_Position__c for all households holding NVDA at or above
#      the concentration threshold (default 5%).
#   2. For each household, writes a Client_Inquiry__c row with Type__c=alert,
#      Auto_Send_Eligible__c based on Client_Preferences__c.
#   3. Prints a one-line summary the demo operator can narrate.
#
# Requirements: sf CLI authed as 'new-org'. Read-write on IR_Position__c
# and Client_Inquiry__c (covered by V3_IR_Position_Access + V3_Client_Inquiry_Access
# permsets).

set -euo pipefail

TICKER=${1:-NVDA}
PRICE_CHANGE_PCT=${2:--8.0}
THRESHOLD_PCT=${3:-5.0}
ORG=${ORG:-new-org}

TOKEN=$(sf org display --target-org "$ORG" --json 2>/dev/null \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['result']['accessToken'])")
INST=$(sf org display --target-org "$ORG" --json 2>/dev/null \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['result']['instanceUrl'])")

echo "==> Simulating ${PRICE_CHANGE_PCT}% move on ${TICKER} (threshold ${THRESHOLD_PCT}%)"
echo ""

# Step 1: find households at/above threshold
SOQL="SELECT+Id,Ticker__c,Client_Contact__c,Position_Size_Pct__c+FROM+IR_Position__c+WHERE+Ticker__c='${TICKER}'+AND+Position_Size_Pct__c+>=+${THRESHOLD_PCT}"
curl -sS "${INST}/services/data/v60.0/query/?q=${SOQL}" \
  -H "Authorization: Bearer ${TOKEN}" > /tmp/sps-positions.json

COUNT=$(python3 -c "import json;print(json.load(open('/tmp/sps-positions.json'))['totalSize'])")
echo "==> Found ${COUNT} households holding ${TICKER} at or above ${THRESHOLD_PCT}%"

if [ "${COUNT}" = "0" ]; then
  echo "No affected clients. Exiting."
  exit 0
fi

# Step 2: for each household, write Client_Inquiry__c with Type__c=alert
ALERTS_WRITTEN=0
python3 <<PYEOF | tee /tmp/sps-plan.txt
import json
d=json.load(open('/tmp/sps-positions.json'))
for r in d.get('records',[]):
    cid=r.get('Client_Contact__c','')
    pct=r.get('Position_Size_Pct__c',0)
    print(f"{cid}|{pct}")
PYEOF

while IFS='|' read -r cid pct; do
  [ -z "${cid}" ] && continue
  body="Volatility alert: ${TICKER} moved ${PRICE_CHANGE_PCT}% — your position is ${pct}% of portfolio."
  payload=$(python3 -c "
import json
print(json.dumps({
  'Client_Contact_Id__c': '${cid}',
  'Type__c': 'alert',
  'Inquiry_Text__c': '${body}',
  'Channel__c': 'Email',
  'Ticker_Mentions__c': '${TICKER}',
  'Auto_Send_Eligible__c': False
}))")
  resp=$(curl -sS -X POST "${INST}/services/data/v60.0/sobjects/Client_Inquiry__c/" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "${payload}")
  inquiry_id=$(echo "${resp}" | python3 -c "import json,sys;print(json.load(sys.stdin).get('id',''))")
  if [ -n "${inquiry_id}" ]; then
    echo "    wrote Client_Inquiry__c ${inquiry_id} for ${cid} (${pct}%)"
    ALERTS_WRITTEN=$((ALERTS_WRITTEN + 1))
  else
    echo "    FAILED for ${cid}: ${resp}"
  fi
done < /tmp/sps-plan.txt

echo ""
echo "==> Wrote ${ALERTS_WRITTEN} alert rows. Panel: check Client_Inquiry__c list view for Type=alert."
