#!/usr/bin/env python3
"""
Create Data Model Objects (DMOs) and map DLOs to DMOs via Connect REST API.

Usage:
    python3 scripts/setup-dmo-mappings.py [org-alias]

Default org alias: new-org
"""
import subprocess, json, sys, time

ORG_ALIAS = sys.argv[1] if len(sys.argv) > 1 else "new-org"
API_VERSION = "v66.0"

# Objects to process (skip Audit_Log — CRM only)
SKIP_PATTERNS = ["Audit_Log", "StaticCurrency"]

def get_org_info():
    result = subprocess.run(
        ["sf", "org", "display", "--target-org", ORG_ALIAS, "--json"],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)["result"]
    return data["accessToken"], data["instanceUrl"]

def api_get(token, base, path):
    """Use curl to avoid Python SSL issues on macOS."""
    result = subprocess.run(
        ["curl", "-s", "--max-time", "60",
         "-H", f"Authorization: Bearer {token}",
         f"{base}/services/data/{API_VERSION}{path}"],
        capture_output=True, text=True, timeout=90
    )
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)

def api_post(token, base, path, payload):
    """Use curl to avoid Python SSL issues on macOS."""
    result = subprocess.run(
        ["curl", "-s", "--max-time", "60",
         "-H", f"Authorization: Bearer {token}",
         "-H", "Content-Type: application/json",
         "-X", "POST",
         f"{base}/services/data/{API_VERSION}{path}",
         "-d", json.dumps(payload)],
        capture_output=True, text=True, timeout=90
    )
    try:
        return json.loads(result.stdout)
    except:
        return {"error": result.stdout}

def main():
    print(f"Org: {ORG_ALIAS}")
    token, base = get_org_info()
    print(f"Instance: {base}\n")

    # 1. Get all DLOs
    print("[1/4] Discovering Data Lake Objects...")
    dlos = api_get(token, base, "/ssot/data-lake-objects?limit=50")
    wa_dlos = []
    for dlo in dlos.get("dataLakeObjects", []):
        name = dlo.get("name", "")
        if "WA_" in name and not any(skip in name for skip in SKIP_PATTERNS):
            wa_dlos.append(dlo)
            print(f"  {name} ({dlo.get('category','')}, {dlo.get('status','')})")
    
    if not wa_dlos:
        print("  No WA_* DLOs found. Create data streams first.")
        sys.exit(1)

    # 2. Skip DMO check (slow endpoint) — API returns error if already exists
    print("\n[2/4] Skipping DMO existence check (will handle duplicates)...")
    existing_dmos = set()

    # 3. Create DMOs and mappings
    print("\n[3/4] Creating DMOs and mappings...")
    results = []
    
    for dlo in wa_dlos:
        dlo_name = dlo["name"]  # e.g. WA_Household_c_Home__dll
        dmo_base = dlo_name.replace("__dll", "")  # WA_Household_c_Home
        dmo_name = f"{dmo_base}__dlm"  # WA_Household_c_Home__dlm
        
        print(f"\n  --- {dlo_name} ---")
        
        # Use fields from the list call (detail endpoint returns empty fields)
        dlo_fields = dlo.get("fields", [])
        if not dlo_fields:
            dlo_fields = dlo.get("dataLakeFieldInfoRepresentation", [])
        
        # Create DMO if not exists
        if dmo_name in existing_dmos:
            print(f"  DMO already exists: {dmo_name}")
        else:
            # Build fields for DMO creation (skip system fields that can't be in custom DMOs)
            SKIP_FIELDS = {"KQ_Id__c", "DataSource__c", "DataSourceObject__c", "InternalOrganization__c"}
            dmo_fields = []
            for f in dlo_fields:
                if f["name"] in SKIP_FIELDS:
                    continue
                dmo_fields.append({
                    "name": f["name"],
                    "label": f.get("label", f["name"]),
                    "dataType": f.get("dataType", "Text"),
                    "isPrimaryKey": f.get("isPrimaryKey", False)
                })
            
            category = dlo.get("category", "Other").upper()
            dmo_payload = {
                "name": dmo_base,
                "label": dmo_base.replace("_c_Home", "").replace("_", " "),
                "description": f"Auto-created DMO for {dmo_base}",
                "dataSpaceName": "default",
                "category": category,
                "fields": dmo_fields
            }
            
            print(f"  Creating DMO: {dmo_base} ({len(dmo_fields)} fields)...")
            create_result = api_post(token, base, "/ssot/data-model-objects", dmo_payload)
            
            # Handle response
            if isinstance(create_result, list):
                # Error array
                err = create_result[0].get("message", str(create_result[0])) if create_result else "Unknown"
                if "already exists" in str(err).lower() or "previously used" in str(err).lower():
                    print(f"  DMO already exists, will try mapping...")
                else:
                    print(f"  CREATE ERROR: {str(err)[:200]}")
                    results.append({"dlo": dlo_name, "dmo": dmo_name, "status": "CREATE_FAILED", "error": str(err)[:100]})
                    continue
            elif isinstance(create_result, dict) and create_result.get("name"):
                dmo_name = create_result["name"]
                print(f"  Created: {dmo_name}")
            elif isinstance(create_result, dict) and create_result.get("error"):
                print(f"  CREATE ERROR: {str(create_result['error'])[:200]}")
                results.append({"dlo": dlo_name, "dmo": dmo_name, "status": "CREATE_FAILED", "error": str(create_result)[:100]})
                continue
        
        # Create mapping
        field_mappings = []
        for f in dlo_fields:
            field_mappings.append({
                "sourceFieldDeveloperName": f["name"],
                "targetFieldDeveloperName": f["name"]
            })
        
        mapping_payload = {
            "sourceEntityDeveloperName": dlo_name,
            "targetEntityDeveloperName": dmo_name,
            "fieldMapping": field_mappings
        }
        
        print(f"  Creating mapping: {dlo_name} -> {dmo_name}...")
        map_result = api_post(token, base, "/ssot/data-model-object-mappings?dataspace=default", mapping_payload)
        
        if isinstance(map_result, list):
            err = map_result[0].get("message", str(map_result[0])) if map_result else "Unknown"
            if "already exists" in str(err).lower() or "mapping" in str(err).lower():
                print(f"  Mapping may already exist: {str(err)[:100]}")
                results.append({"dlo": dlo_name, "dmo": dmo_name, "status": "MAP_EXISTS"})
            else:
                print(f"  MAP ERROR: {str(err)[:200]}")
                results.append({"dlo": dlo_name, "dmo": dmo_name, "status": "MAP_FAILED", "error": str(err)[:100]})
        elif isinstance(map_result, dict):
            map_status = map_result.get("status", "")
            map_dev = map_result.get("developerName", "")
            if map_status:
                print(f"  Mapping: {map_status} ({map_dev})")
                results.append({"dlo": dlo_name, "dmo": dmo_name, "status": map_status})
            else:
                print(f"  MAP RESULT: {str(map_result)[:200]}")
                results.append({"dlo": dlo_name, "dmo": dmo_name, "status": "UNKNOWN"})
        else:
            print(f"  MAP RESULT: {str(map_result)[:200]}")
            results.append({"dlo": dlo_name, "dmo": dmo_name, "status": "UNKNOWN"})

    # 4. Summary
    print("\n[4/4] Summary")
    print(f"{'DLO':<40} {'DMO':<40} {'Status'}")
    print("-" * 90)
    for r in results:
        print(f"{r['dlo']:<40} {r['dmo']:<40} {r['status']}")
    
    ok = sum(1 for r in results if r["status"] in ("CREATING", "ACTIVE"))
    fail = len(results) - ok
    print(f"\nCreated: {ok}, Failed: {fail}")
    
    if ok > 0:
        print("\nWaiting 60 seconds for DMOs to become queryable...")
        time.sleep(60)
        print("Done. Run: sf apex run --file scripts/apex/verify-data.apex")

if __name__ == "__main__":
    main()
