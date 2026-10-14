# v3 P0 — Salesforce OBO Chain Fix

**Status:** Not fixable from code alone. Requires Salesforce Connected App + private key to be populated in the Secrets Manager bootstrap secret.

**Impact:** Fixing this single secret closes TWO P0 items at once:
1. `IR_Audit_Log__c` zero rows today (audit_logging skill silently failing on OBO)
2. `Research_Request__c` 401 (N2 handoff loop broken)

---

## Root cause — live-probed

```
POST /v3/mcp/salesforce-crm/tools/call  (write_audit_log)
→ 401  SF OBO failed: 502
  "OBO failed: SF token exchange failed: 400 invalid_grant"
```

The agent-proxy → salesforce-crm MCP → sf-auth-proxy chain is
dispatching correctly. The sf-auth-proxy mints a JWT, sends it to
`https://login.salesforce.com/services/oauth2/token`, and Salesforce
rejects with `invalid_grant`. 

The **secret** backing the JWT signing is **empty**:

```bash
aws secretsmanager get-secret-value \
  --region us-east-1 \
  --secret-id /006-v3/sf/bootstrap-creds \
  --query 'SecretString' --output text | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('client_id:', d.get('client_id', '')[:40])
print('subject_pattern:', d.get('subject_pattern'))
print('audience:', d.get('audience'))
print('has private_key_pem:', bool(d.get('private_key_pem')))
"
# OUTPUT:
# client_id: (empty)
# subject_pattern: None
# audience: None
# has private_key_pem: False
```

Every field is null. The secret was created (so SAM + sf-auth-proxy
don't blow up) but never populated with real Connected App creds.

---

## Fix — one-time Salesforce admin + SSM update

### Step 1 — Create a Connected App in the Salesforce org

1. In the target org (`new-org`), go to **Setup → App Manager → New Connected App**.
2. Set:
   - Connected App Name: `FSI Workforce 360 OBO`
   - API Name: `FSI_Workforce_360_OBO`
   - Contact Email: any valid email
   - Enable OAuth Settings: ✓
   - Callback URL: `https://login.salesforce.com/services/oauth2/callback` (unused for JWT Bearer flow — but SF requires the field)
   - Selected OAuth Scopes:
     - Manage user data via APIs (`api`)
     - Perform requests at any time (`refresh_token, offline_access`)
     - Access custom permissions (`custom_permissions`)
     - Full access (`full`) — optional but simplest
   - **Use digital signatures**: ✓
   - Upload `.crt` file from the cert-key pair you generate below.
3. Save. Go back to **App Manager → the app → View**. Capture **Consumer Key (client_id)**.
4. Go to **Manage Connected Apps → the app → Edit Policies**:
   - Permitted Users: **Admin approved users are pre-authorized**
   - Save.
5. Assign the Connected App to a permset or profile that the integration user belongs to.

### Step 2 — Generate the self-signed cert locally

```bash
# Generate a 2048-bit RSA key + self-signed cert (SF accepts both)
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -subj "/CN=fsi-workforce-360/O=FSI/C=US" \
  -keyout /tmp/fsi-obo.key \
  -out /tmp/fsi-obo.crt

# Upload /tmp/fsi-obo.crt to the Connected App (Step 1.2).
# KEEP /tmp/fsi-obo.key safe — this is the signing key.
```

### Step 3 — Decide the subject pattern

The JWT's `sub` claim must match a valid Salesforce user. Options:

**Option A (simplest, demo-only):** hardcoded integration user.
```
subject_pattern: "integration-user@new-org.example.com"
```

**Option B (multi-user, production):** map principal_id to SF user email via a
lookup table. Requires more work. For v3 demo, use Option A.

### Step 4 — Populate the secret

```bash
PRIVATE_KEY_PEM=$(cat /tmp/fsi-obo.key)

# Build the JSON body
python3 <<'PY'
import json, os
secret = {
    "client_id": "<paste Consumer Key from Step 1.3>",
    "subject_pattern": "<integration-user email from Step 3>",
    "audience": "https://login.salesforce.com",
    "private_key_pem": open("/tmp/fsi-obo.key").read(),
}
print(json.dumps(secret))
PY > /tmp/fsi-obo-secret.json

# Update the secret
aws secretsmanager put-secret-value \
  --region us-east-1 \
  --secret-id /006-v3/sf/bootstrap-creds \
  --secret-string file:///tmp/fsi-obo-secret.json
```

### Step 5 — Verify + clean up

```bash
# Verify fields are populated
aws secretsmanager get-secret-value \
  --region us-east-1 \
  --secret-id /006-v3/sf/bootstrap-creds \
  --query 'SecretString' --output text | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('client_id present:', bool(d.get('client_id')))
print('subject_pattern present:', bool(d.get('subject_pattern')))
print('audience present:', bool(d.get('audience')))
print('private_key_pem length:', len(d.get('private_key_pem', '')))
"

# Securely delete local copies
shred -u /tmp/fsi-obo.key /tmp/fsi-obo.crt /tmp/fsi-obo-secret.json
# or on macOS without shred:
# rm -P /tmp/fsi-obo.key /tmp/fsi-obo.crt /tmp/fsi-obo-secret.json
```

### Step 6 — Trigger sf-auth-proxy secret cache refresh

The Lambda caches `_BOOTSTRAP_CACHE` at module load. Force a cold start:

```bash
aws lambda update-function-configuration \
  --region us-east-1 \
  --function-name 006-v3-sf-auth-proxy \
  --environment "Variables={SF_AUTH_PROXY_KEY=<preserve existing>,SF_AUTH_PROXY_MODE=live,CACHE_BUST=$(date +%s)}"
```

### Step 7 — Live-verify the fix

```bash
MCP_KEY=$(aws ssm get-parameter --region us-east-1 \
  --name /006-v3/mcp/api-key --with-decryption \
  --query 'Parameter.Value' --output text)

curl -s -X POST https://e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3/mcp/salesforce-crm/tools/call \
  -H "X-MCP-API-Key: $MCP_KEY" \
  -H "X-Principal-Id: sarah" \
  -H "X-Agent-Id: research_orchestrator" \
  -H "X-Persona: research" \
  -H 'Content-Type: application/json' \
  -d '{"name":"write_audit_log","arguments":{"record":{
        "Action__c":"ADVISORY_QUERY",
        "Principal_Id__c":"sarah",
        "Agent_Id__c":"research_orchestrator",
        "Session_Id__c":"verify-fix-aaaaaaaaaaaaaaaa",
        "Correlation_Id__c":"verify-fix-001",
        "Timestamp__c":"2026-05-01T10:00:00Z",
        "Payload__c":{"probe":"post-fix"}
  }}}'
# Expected: HTTP 200 with {"status":"ok","result":{"Id":"a0M..."}}
```

Then run a real turn + check audit table:

```bash
curl -s -X POST https://e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3/agent/invoke \
  -H 'Authorization: Bearer dev-bootstrap-token' \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"NVDA quick brief","persona":"fsi_research",
       "principal_id":"sarah",
       "session_id":"post-fix-obo-aaaaaaaaaaaaaaaa",
       "correlation_id":"post-fix-001",
       "turn_number":1}'

sleep 15
sf data query \
  --query "SELECT COUNT() FROM IR_Audit_Log__c WHERE CreatedDate = TODAY" \
  --target-org new-org
# Expected: > 0 rows
```

---

## Why I didn't script this fully

Generating a Salesforce Connected App + private key requires Salesforce
admin actions (uploading .crt, getting consumer key). The AWS-side parts
(secret update, Lambda config) are scripted above, but the SF-side is a
one-time manual setup.

---

## When this fix lands, these regressions clear

| Regression | Evidence today | Expected after fix |
|---|---|---|
| Zero audit rows today | SOQL `WHERE CreatedDate = TODAY` returns 0 | Every turn writes 1-3 rows |
| N2 "Research_Request__c" appears as RREQ-LOCAL | AgentCore logs show `research_request_write_degraded status=401` | Real `a0R...` Salesforce id |
| `publish_brief` audit write | Silent failure | Real audit row linked via `Research_Brief_Id__c` |
| dual_auth record-first audit | Silent failure | Real audit row |
| HITL approved/rejected audit | Silent failure | Real audit row |

**Net effect:** the trust-spine promise ("audit row on every outcome") becomes
real instead of aspirational. Three narratives become more demo-credible.
