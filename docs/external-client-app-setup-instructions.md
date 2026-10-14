# External Client App Setup — Agentforce Agent API Access

> Required for: Projects 004 and 005
> Org: orgfarm-035b70d101-dev-ed
> Purpose: Enable the Agent API so frontends talk to real Agentforce agents
> Time: ~5 minutes
> Prerequisites: Salesforce admin access to the org

---

## Why This Is Needed

The Agentforce Agent API requires an External Client App (ECA) with the
`chatbot_api` OAuth scope. Without it, the Agent API returns 404 and the
frontends fall back to JavaScript keyword routing (no LLM, no agent reasoning).

The agents are deployed and Active. This is the only missing piece.

---

## Instructions

### 1. Open Salesforce Setup

Go to: https://orgfarm-035b70d101-dev-ed.develop.my.salesforce.com/lightning/setup/SetupOneHome/home

Or: Login → gear icon (top right) → Setup

### 2. Create the External Client App

1. In Quick Find (left sidebar search), type: `External Client App`
2. Click: External Client Apps Manager
3. Click: New External Client App

### 3. Fill in Basic Info

```
Name:           Agent_API
API Name:       Agent_API  (auto-fills)
Contact Email:  [your email address]
```

### 4. Configure OAuth

Check Enable OAuth, then add these scopes (use the Add button):

```
[x]  Manage user data via APIs (api)
[x]  Perform requests at any time (refresh_token, offline_access)
[x]  Access chatbot services (chatbot_api)
[x]  Access the Salesforce API Platform (sfap_api)
```

### 5. Set OAuth Options

```
CHECK these:
  [x]  Enable Client Credentials Flow
  [x]  Issue JWT Web Token (JWT)-based access tokens for named users

UNCHECK these:
  [ ]  Require secret for Web Server Flow
  [ ]  Require secret for Refresh Token Flow
  [ ]  Require Proof Key for Code Exchange (PKCE)
```

### 6. Save

Click Save (or Create depending on the UI version).

### 7. Configure the Policy

1. From the app detail page, click the Policy tab
2. Click Edit
3. In the "OAuth Flows and External Client App Enhancements" section:
   - Check: Enable Client Credentials Flow
   - Set Run As (Username): select your admin user email
     (e.g., multipleplatforms001.63e8e336be48@agentforce.com)
4. Click Save

### 8. Copy the Consumer Key and Secret

1. From the app detail page, click the Settings tab
2. Expand the OAuth Settings section
3. Click Consumer Key and Secret
4. Copy both values:

```
Consumer Key:    [paste here or give to Kiro]
Consumer Secret: [paste here or give to Kiro]
```

These will be stored in AWS Lambda environment variables (never in frontend code).

---

## Verification

After creating the ECA, verify the token works:

```bash
# Replace YOUR_KEY and YOUR_SECRET with the values from Step 8
curl -s -X POST \
  "https://orgfarm-035b70d101-dev-ed.develop.my.salesforce.com/services/oauth2/token" \
  -d "grant_type=client_credentials&client_id=YOUR_KEY&client_secret=YOUR_SECRET"

# Expected: JSON with access_token, instance_url, token_type
# If you get an error, check:
#   - Policy tab has "Enable Client Credentials Flow" checked
#   - Run As user is set
#   - Wait 2-3 minutes after creation (propagation delay)
```

Then verify the Agent API responds:

```bash
TOKEN="[access_token from above]"

# Test with 005's IR_Research_Agent
curl -s -X POST \
  "https://orgfarm-035b70d101-dev-ed.develop.my.salesforce.com/einstein/ai-agent/v1/agents/0XxgK000001JItVSAW/sessions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"externalSessionKey":"verify-001","bypassUser":true}'

# Expected: {"sessionId": "..."}
# If 404: chatbot_api scope may be missing, or agent not Active

# Test with 004's WA_P1to5_Advisor
curl -s -X POST \
  "https://orgfarm-035b70d101-dev-ed.develop.my.salesforce.com/einstein/ai-agent/v1/agents/0XxgK000001IlSySAK/sessions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"externalSessionKey":"verify-002","bypassUser":true}'

# Expected: {"sessionId": "..."}
```

---

## What Happens After This

Once the ECA is created and verified, the remaining code changes are:

1. Lambda token proxy — add /oauth/agent-token endpoint
   (ECA consumer key and secret go in Lambda env vars, not frontend)
2. Frontend agentApi.ts — use My Domain URL + ECA token for Agent API calls
3. Build and deploy both 004 and 005 frontends

The agents, topics, and Apex actions are already deployed and working.
No Salesforce-side code changes needed.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Token returns "invalid_client" | Wrong key/secret | Re-copy from Settings tab |
| Token returns "invalid_grant" | Run As user not set | Policy tab, set Run As |
| Agent API returns 404 | chatbot_api scope missing | Edit app, add scope, save |
| Agent API returns 401 | Token expired or wrong type | Get fresh ECA token |
| Agent API returns 403 | User lacks permissions | Check Run As user has API access |
| "URL No Longer Exists" | Wrong domain URL | Use .develop.my.salesforce.com |

---

## Reference

| Item | Value |
|------|-------|
| Org | orgfarm-035b70d101-dev-ed |
| My Domain URL | https://orgfarm-035b70d101-dev-ed.develop.my.salesforce.com |
| 004 Agent (WA_P1to5_Advisor) | 0XxgK000001IlSySAK |
| 005 Agent (IR_Research_Agent) | 0XxgK000001JItVSAW |
| Agent API URL pattern | {MY_DOMAIN}/einstein/ai-agent/v1/agents/{AGENT_ID}/sessions |
| Token endpoint | {MY_DOMAIN}/services/oauth2/token |
| Grant type | client_credentials |
| Required scope | chatbot_api |
