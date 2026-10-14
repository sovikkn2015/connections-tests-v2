#!/bin/bash
# ============================================================
# Create Data Model Objects (DMOs) and map DLOs to DMOs
# ============================================================
# This script uses the Data Cloud Connect REST API to:
#   1. Discover DLO names in the org
#   2. Create custom DMOs for each WA_* DLO
#   3. Map DLO fields to DMO fields
#
# Prerequisites:
#   - sf CLI authenticated to the target org
#   - Data streams created and Active (DLOs exist)
#   - python3 available
#
# Usage:
#   chmod +x scripts/create-dmo-mappings.sh
#   ./scripts/create-dmo-mappings.sh [org-alias]
#
# Default org alias: new-org (override with first argument)
# ============================================================

set -e

ORG_ALIAS="${1:-new-org}"
API_VERSION="v66.0"

echo "============================================================"
echo "  Create DMO Mappings — Data Cloud Connect API"
echo "  Org: $ORG_ALIAS"
echo "============================================================"

# Get access token and instance URL
ACCESS_TOKEN=$(sf org display --target-org "$ORG_ALIAS" --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['accessToken'])")
INSTANCE_URL=$(sf org display --target-org "$ORG_ALIAS" --json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['instanceUrl'])")

BASE_URL="$INSTANCE_URL/services/data/$API_VERSION"

echo "Instance: $INSTANCE_URL"
echo ""

# Step 1: Get all WA_* DLOs
echo "[1/3] Discovering WA_* Data Lake Objects..."
DLOS=$(curl -s --max-time 30 \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  "$BASE_URL/ssot/data-lake-objects?limit=50")

echo "$DLOS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for dlo in data.get('dataLakeObjects', []):
    name = dlo.get('name','')
    if 'WA_' in name and 'Audit_Log' not in name:
        print(f'  Found: {name}')
"

# Step 2: For each WA_* DLO (excluding Audit_Log), create a custom DMO and map it
echo ""
echo "[2/3] Creating DMOs and mappings..."

# Get DLO names as array
DLO_NAMES=$(echo "$DLOS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for dlo in data.get('dataLakeObjects', []):
    name = dlo.get('name','')
    if 'WA_' in name and 'Audit_Log' not in name:
        print(name)
")

for DLO_NAME in $DLO_NAMES; do
    # Derive DMO name from DLO name: WA_Household_c_Home__dll -> WA_Household_c_Home
    DMO_BASE=$(echo "$DLO_NAME" | sed 's/__dll$//')
    DMO_NAME="${DMO_BASE}__dlm"
    
    echo ""
    echo "  Processing: $DLO_NAME -> $DMO_NAME"
    
    # Get DLO details (fields)
    DLO_DETAIL=$(curl -s --max-time 30 \
      -H "Authorization: Bearer $ACCESS_TOKEN" \
      "$BASE_URL/ssot/data-lake-objects/$DLO_NAME")
    
    # Extract category and fields, build DMO creation payload
    DMO_PAYLOAD=$(echo "$DLO_DETAIL" | python3 -c "
import sys, json
dlo = json.load(sys.stdin)
category = dlo.get('category', 'Other')
fields = []
for f in dlo.get('fields', []):
    field = {
        'name': f['name'],
        'label': f.get('label', f['name']),
        'dataType': f.get('dataType', 'Text'),
        'isPrimaryKey': f.get('isPrimaryKey', False)
    }
    fields.append(field)

dmo_name = '$DMO_BASE'
payload = {
    'name': dmo_name,
    'label': dmo_name.replace('_c_Home', '').replace('_', ' '),
    'description': 'Auto-created DMO for ' + dmo_name,
    'dataSpaceName': 'default',
    'category': category.upper(),
    'fields': fields
}
print(json.dumps(payload))
")
    
    # Create DMO
    echo "    Creating DMO: $DMO_BASE..."
    CREATE_RESULT=$(curl -s --max-time 30 \
      -H "Authorization: Bearer $ACCESS_TOKEN" \
      -H "Content-Type: application/json" \
      -X POST "$BASE_URL/ssot/data-model-objects" \
      -d "$DMO_PAYLOAD")
    
    # Check if creation succeeded
    DMO_STATUS=$(echo "$CREATE_RESULT" | python3 -c "
import sys, json
try:
    r = json.load(sys.stdin)
    name = r.get('name', '')
    if name:
        print('OK: ' + name)
    elif 'errorCode' in str(r) or 'message' in r:
        msg = r.get('message', r.get('detail', str(r)))
        print('ERROR: ' + str(msg)[:200])
    else:
        print('UNKNOWN: ' + str(r)[:200])
except:
    print('PARSE_ERROR')
" 2>&1)
    echo "    $DMO_STATUS"
    
    # If DMO created, create the mapping
    if [[ "$DMO_STATUS" == OK:* ]]; then
        ACTUAL_DMO_NAME=$(echo "$DMO_STATUS" | sed 's/OK: //')
        
        # Build field mapping payload
        MAPPING_PAYLOAD=$(echo "$DLO_DETAIL" | python3 -c "
import sys, json
dlo = json.load(sys.stdin)
field_mappings = []
for f in dlo.get('fields', []):
    field_mappings.append({
        'sourceFieldDeveloperName': f['name'],
        'targetFieldDeveloperName': f['name']
    })

payload = {
    'sourceEntityDeveloperName': '$DLO_NAME',
    'targetEntityDeveloperName': '$ACTUAL_DMO_NAME',
    'fieldMapping': field_mappings
}
print(json.dumps(payload))
")
        
        echo "    Creating mapping: $DLO_NAME -> $ACTUAL_DMO_NAME..."
        MAP_RESULT=$(curl -s --max-time 30 \
          -H "Authorization: Bearer $ACCESS_TOKEN" \
          -H "Content-Type: application/json" \
          -X POST "$BASE_URL/ssot/data-model-object-mappings?dataspace=default" \
          -d "$MAPPING_PAYLOAD")
        
        MAP_STATUS=$(echo "$MAP_RESULT" | python3 -c "
import sys, json
try:
    r = json.load(sys.stdin)
    status = r.get('status', '')
    dev = r.get('developerName', '')
    if status:
        print('OK: ' + status + ' (' + dev + ')')
    elif isinstance(r, list):
        print('ERROR: ' + str(r[0].get('message',''))[:200])
    else:
        print('RESULT: ' + str(r)[:200])
except:
    print('PARSE_ERROR')
" 2>&1)
        echo "    Mapping: $MAP_STATUS"
    fi
done

echo ""
echo "[3/3] Waiting 30 seconds for DMOs to become queryable..."
sleep 30

echo ""
echo "============================================================"
echo "  Done! Verify with:"
echo "    sf apex run --file scripts/apex/verify-data.apex"
echo "============================================================"
