# 005 Agentforce Wiring Plan — From Keyword Router to Real Agent

> Date: April 18, 2026
> Status: PLAN (not yet implemented)

---

## The Problem

005's frontend claims to use Agentforce but actually uses a JavaScript keyword
router that pattern-matches user queries to Apex actions. No LLM reasoning,
no topic selection, no multi-turn conversation, no Atlas Reasoning Engine.

```
WHAT THE ARCHITECTURE CLAIMS:
  User → Agent API → Agentforce Agent → Atlas Reasoning Engine → Topic → Apex Action

WHAT ACTUALLY HAPPENS:
  User → agentApi.ts → routeMessage() → keyword match in JS → Apex Action directly
```

The agent IS deployed and Active on the org. The wiring is broken.

---

## Root Cause Analysis

```
COMPONENT                    STATUS    DETAIL
─────────────────────────── ──────── ─────────────────────────────────────────
IR_Research_Agent            ACTIVE   BotDefinition 0XxgK000001JItVSAW
  12 topics                  WIRED    All point to apex:// InvocableActions
  Apex actions (12)          WORKING  Tested, return real data
GenAiPlannerDefinition       EXISTS   16jgK000001FxIXQA0
GenAiFunctionDefinition      EXISTS   10 functions registered
BotVersion                   ACTIVE   v1, Status=Active

Agent API endpoint           404      api.salesforce.com returns 404
                                      MY_DOMAIN/einstein/ai-agent/v1 returns 404

WHY 404:
  The Agent API requires an External Client App (ECA) with:
    - chatbot_api OAuth scope
    - sfap_api OAuth scope
    - Client credentials flow enabled
    - JWT-based access tokens

  The current Connected App (IR_Research_Workbench) has:
    - api scope only
    - PKCE flow only
    - No chatbot_api scope
    - No client credentials flow

  Result: Agent API is not activated for this app. Returns 404.
```

---

## What Exists on the Org Today

```
AGENTS DEPLOYED (all Active):
  ┌──────────────────────┬──────────────────────────┬─────────┐
  │ Agent                │ BotDefinition ID         │ Project │
  ├──────────────────────┼──────────────────────────┼─────────┤
  │ WA_P1to5_Advisor     │ 0XxgK000001IlSySAK      │ 004     │
  │ WA_Advisor_v2        │ 0XxgK000001IqM9SAK      │ 004 v2  │
  │ WA_DC_Advisor        │ 0XxgK000001IqNlSAK      │ 004 DC  │
  │ IR_Research_Agent    │ 0XxgK000001JItVSAW      │ 005     │
  │ Hello_World_Agent    │ 0XxgK000001IqKXSA0      │ 001     │
  └──────────────────────┴──────────────────────────┴─────────┘

GENAI FUNCTIONS (10 registered):
  get_client_360, get_portfolio_summary, get_financial_goals,
  get_meeting_prep, check_rebalancing, get_transactions,
  get_referrals, run_compliance, get_market_data, search_news

CONNECTED APPS (current):
  IR_Research_Workbench — PKCE, api+refresh_token scopes
  WA_Workbench — PKCE, api+refresh_token scopes

EXTERNAL CLIENT APPS:
  NONE — this is the gap
```

---

## The Fix — 4 Steps

### Step 1: Create External Client App (Manual — Salesforce Setup UI)

This cannot be done via API or CLI. Must be done in Setup.

```
1. Setup → External Client App Manager → New External Client App

2. Basic Info:
   Name:          IR_Agent_API
   Contact Email: [your email]

3. OAuth Settings — Enable OAuth, add scopes:
   [x] Manage user data via APIs (api)
   [x] Perform requests at any time (refresh_token, offline_access)
   [x] Access chatbot services (chatbot_api)
   [x] Access the Salesforce API Platform (sfap_api)

4. OAuth Settings — Check:
   [x] Enable Client Credentials Flow
   [x] Issue JWT-based access tokens for named users

5. OAuth Settings — Uncheck:
   [ ] Require secret for Web Server Flow
   [ ] Require secret for Refresh Token Flow
   [ ] Require PKCE

6. Save

7. Policy tab → Edit:
   [x] Enable Client Credentials Flow
   Run As: [your admin username]
   Save

8. Settings tab → OAuth Settings → Consumer Key and Secret:
   Copy CONSUMER_KEY and CONSUMER_SECRET
```

### Step 2: Update Lambda Token Proxy

The existing token proxy at /oauth/token handles PKCE exchange.
Add a new endpoint /oauth/agent-token for ECA client credentials.

```
CURRENT SAM TEMPLATE (token proxy):
  POST /oauth/token → forwards PKCE code exchange to SF

NEW ENDPOINT:
  POST /oauth/agent-token → client credentials grant
    - ECA_CLIENT_ID and ECA_CLIENT_SECRET stored in Lambda env vars
    - Calls: POST {MY_DOMAIN}/services/oauth2/token
      grant_type=client_credentials
      client_id={ECA_CLIENT_ID}
      client_secret={ECA_CLIENT_SECRET}
    - Returns: { access_token, instance_url, token_type }
    - Token has chatbot_api scope → Agent API works

SECURITY:
  - ECA credentials NEVER go to the frontend
  - Frontend calls /oauth/agent-token (no params needed)
  - Lambda holds the secrets in env vars (SAM NoEcho parameters)
  - Token is returned to frontend, used for Agent API calls only
```

SAM template changes:

```yaml
Parameters:
  EcaClientId:
    Type: String
    NoEcho: true
    Description: External Client App consumer key for Agent API
  EcaClientSecret:
    Type: String
    NoEcho: true
    Description: External Client App consumer secret for Agent API

TokenProxyFunction:
  Environment:
    Variables:
      SF_TOKEN_URL: https://orgfarm-035b70d101-dev-ed.develop.my.salesforce.com/services/oauth2/token
      ECA_CLIENT_ID: !Ref EcaClientId
      ECA_CLIENT_SECRET: !Ref EcaClientSecret
```

Lambda handler addition (Python):

```python
def handle_agent_token(event):
    """Mint an ECA token for Agent API access."""
    form_data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": os.environ["ECA_CLIENT_ID"],
        "client_secret": os.environ["ECA_CLIENT_SECRET"],
    }).encode()
    req = urllib.request.Request(
        os.environ["SF_TOKEN_URL"],
        data=form_data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": resp.read().decode(),
        }
```

### Step 3: Update Frontend agentApi.ts

```
CURRENT FLOW:
  startSession()
    → tries api.salesforce.com/einstein/ai-agent/v1 with PKCE token
    → 404
    → falls back to apex-fallback-* keyword routing

NEW FLOW:
  startSession()
    → calls /oauth/agent-token to get ECA token
    → calls {MY_DOMAIN}/einstein/ai-agent/v1/agents/{AGENT_ID}/sessions
      with ECA token
    → gets real sessionId from Agentforce
    → sendMessage() uses Agent API with real session
    → Atlas Reasoning Engine routes to topics
    → Agent selects Apex action based on LLM reasoning
    → Response includes natural language formatting

  FALLBACK (if Agent API still fails):
    → same apex-fallback keyword routing as today
```

Key changes in agentApi.ts:

```typescript
// NEW: Agent API base URL uses My Domain, not api.salesforce.com
const MY_DOMAIN_URL = import.meta.env.VITE_SF_LOGIN_URL;
const API_GATEWAY_URL = import.meta.env.VITE_API_GATEWAY_URL;

// Cache the ECA token (lasts ~2 hours)
let agentToken: string | null = null;
let agentTokenExpiry = 0;

async function getAgentToken(): Promise<string> {
  if (agentToken && Date.now() < agentTokenExpiry) return agentToken;
  const res = await fetch(`${API_GATEWAY_URL}/oauth/agent-token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error('Failed to get agent token');
  const data = await res.json();
  agentToken = data.access_token;
  agentTokenExpiry = Date.now() + 7000 * 1000; // ~2hr minus buffer
  return agentToken!;
}

async function startAgentApiSession(agentId: string): Promise<string> {
  const token = await getAgentToken();
  const res = await fetch(
    `${MY_DOMAIN_URL}/einstein/ai-agent/v1/agents/${agentId}/sessions`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        externalSessionKey: crypto.randomUUID(),
        bypassUser: true,
      }),
    },
  );
  if (!res.ok) throw new Error(`Agent API: ${res.status}`);
  const data = await res.json();
  return data.sessionId;
}
```

### Step 4: Add .env Variables

```
# frontend/.env — already has:
VITE_SF_LOGIN_URL=https://orgfarm-035b70d101-dev-ed.develop.my.salesforce.com
VITE_API_GATEWAY_URL=https://og256a1neb.execute-api.us-east-1.amazonaws.com/prod
VITE_SF_AGENT_ID=0XxgK000001JItVSAW

# No new frontend env vars needed.
# ECA credentials go in Lambda env vars only (never in frontend).
```

---

## Verification Script

After all 4 steps are complete:

```bash
# 1. Get ECA token via Lambda proxy
AGENT_TOKEN=$(curl -s -X POST \
  "https://og256a1neb.execute-api.us-east-1.amazonaws.com/prod/oauth/agent-token" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "Token: ${AGENT_TOKEN:0:20}..."

# 2. Start Agent API session
SESSION=$(curl -s -X POST \
  "https://orgfarm-035b70d101-dev-ed.develop.my.salesforce.com/einstein/ai-agent/v1/agents/0XxgK000001JItVSAW/sessions" \
  -H "Authorization: Bearer $AGENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"externalSessionKey":"verify-test","bypassUser":true}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['sessionId'])")
echo "Session: $SESSION"

# 3. Send message to agent
curl -s -X POST \
  "https://orgfarm-035b70d101-dev-ed.develop.my.salesforce.com/einstein/ai-agent/v1/sessions/$SESSION/messages" \
  -H "Authorization: Bearer $AGENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":{"text":"Tell me about NVIDIA","sequenceId":1}}'

# Expected: Agent routes to company_lookup topic via Atlas Reasoning Engine,
# calls IR_CompanyLookupAction, returns natural language response.
```

---

## Before vs After

```
BEFORE (keyword router — no agent):
  ┌──────────┐     ┌──────────────┐     ┌──────────────┐
  │ Frontend │ ──→ │ JS keyword   │ ──→ │ Apex Action  │
  │          │     │ routeMessage │     │ (direct)     │
  └──────────┘     └──────────────┘     └──────────────┘

  "NVDA quote"              → matches "quote"   → IR_MarketDataAction
  "NVDA filing"             → matches "filing"  → IR_SecFilingsAction
  "What should I research?" → no match          → IR_CompanyLookupAction (wrong)
  "Compare NVDA and AAPL"   → matches "NVDA"    → IR_CompanyLookupAction (wrong)

  No LLM. No reasoning. Brittle keyword matching.


AFTER (real Agentforce):
  ┌──────────┐     ┌──────────────┐     ┌───────────────┐     ┌──────────────┐
  │ Frontend │ ──→ │ Agent API    │ ──→ │ Atlas Engine  │ ──→ │ Apex Action  │
  │          │     │ (ECA token)  │     │ (LLM routing) │     │ (selected)   │
  └──────────┘     └──────────────┘     └───────────────┘     └──────────────┘

  "NVDA quote"              → LLM → market_data topic    → IR_MarketDataAction
  "NVDA filing"             → LLM → sec_filings topic    → IR_SecFilingsAction
  "What should I research?" → LLM → off_topic/escalation → appropriate response
  "Compare NVDA and AAPL"   → LLM → chains topics        → multiple actions

  Multi-turn: Agent remembers context across messages in a session.
  Natural language: Agent formats responses conversationally.
  Topic selection: LLM picks the right action, not keyword matching.
```

---

## Files to Change

```
SALESFORCE (manual Setup UI):
  Create External Client App with chatbot_api scope

AWS (SAM template + Lambda):
  aws/sam-template.yaml          — add ECA params + /oauth/agent-token route
  aws/token-proxy/app.py         — add agent_token handler (or inline in SAM)

FRONTEND:
  frontend/src/services/agentApi.ts  — use My Domain URL + ECA token
  frontend/.env.example              — document the flow

NO CHANGES NEEDED:
  Apex classes                   — already wired to agent topics
  Agent definition               — already deployed and Active
  Agent topics (12)              — already mapped to Apex actions
  Research panel (researchApi)   — stays on Apex path (independent of chat)
```

---

## Risk Assessment

```
RISK                              MITIGATION
────────────────────────────────  ──────────────────────────────────────
Agent API still 404s after ECA    Verify ECA has chatbot_api scope,
                                  agent is Active, Run As user has access

Agent API slow (cold start)       First message may take 5-10s.
                                  Subsequent messages faster.

Agent misroutes queries           Agent topics have clear instructions.
                                  12 topics cover all use cases.
                                  off_topic topic handles edge cases.

ECA token expires                 Token proxy can cache/refresh.
                                  Client credentials tokens last 2hrs.

CORS on Agent API                 Agent API is called from frontend to
                                  SF My Domain (same-origin after login).
                                  If CORS issues, route through Lambda.

Fallback still works              apex-fallback keyword routing stays
                                  as the safety net if Agent API fails.
```

---

## Applies to Both 004 and 005

The same ECA can serve both projects. Both agents are on the same org.
The token proxy mints a generic ECA token — any agent can use it.

```
004: Use BotDefinition ID 0XxgK000001IlSySAK (WA_P1to5_Advisor)
005: Use BotDefinition ID 0XxgK000001JItVSAW (IR_Research_Agent)
```

Same agentApi.ts changes apply to 004's frontend.
