# Agentforce Agent API Setup Guide — 005 IR Research Agent

> This guide enables the real Agentforce Agent API so the frontend talks to
> the Atlas Reasoning Engine instead of the JavaScript keyword router.

## Current State

- Agent `IR_Research_Agent` is deployed and Active (BotDefinition Id: `0XxgK000001JItVSAW`)
- 12 topics with Apex actions are wired and working
- The Agent API returns 404 because no External Client App (ECA) exists with `chatbot_api` scope
- Frontend falls back to keyword routing in JavaScript (no LLM, no agent reasoning)

## Step 1: Create External Client App

1. Go to Setup, External Client App Manager, New External Client App
2. Name: `IR_Research_Agent_API`
3. Contact Email: your email
4. Check Enable OAuth
5. Add these OAuth scopes:
   - Manage user data via APIs (api)
   - Perform requests at any time (refresh_token, offline_access)
   - Access chatbot services (chatbot_api)
   - Access the Salesforce API Platform (sfap_api)
6. Check Enable Client Credentials Flow
7. Check Issue JWT-based access tokens for named users
8. UNCHECK:
   - Require secret for Web Server Flow
   - Require secret for Refresh Token Flow
   - Require PKCE
9. Save

## Step 2: Configure Client Credentials Policy

1. From the app settings, click Policy tab
2. Click Edit
3. In OAuth Flows and External Client App Enhancements:
   - Check Enable Client Credentials Flow
   - Set Run As to a user with API access (e.g., your admin user)
4. Save

## Step 3: Get Consumer Key and Secret

1. From the app settings, click Settings tab
2. Expand OAuth Settings
3. Click Consumer Key and Secret
4. Copy both values for the token proxy

## Step 4: Update Lambda Token Proxy

Add a second endpoint `/oauth/agent-token` that mints an ECA token:

```
POST /oauth/agent-token
Body: grant_type=client_credentials&client_id=ECA_KEY&client_secret=ECA_SECRET
Returns: access_token with chatbot_api scope
```

ECA credentials go in Lambda env vars, not in the frontend.

## Step 5: Update Frontend agentApi.ts

1. Call `/oauth/agent-token` to get an ECA token (separate from PKCE token)
2. Use My Domain URL (not api.salesforce.com)
3. URL: `{MY_DOMAIN}/einstein/ai-agent/v1/agents/{AGENT_ID}/sessions`

PKCE token continues for Apex calls. ECA token for Agent API only.

## Step 6: Verify

Get ECA token, start session, send message. Should return sessionId.

## What Changes

```
BEFORE (keyword router):
  User -> React -> JS keyword match -> Apex Action directly

AFTER (real Agentforce):
  User -> React -> Agent API -> Atlas Reasoning Engine -> Topic -> Apex Action
```

## Agent IDs

| Agent | BotDefinition ID | Project |
|-------|-----------------|---------|
| WA_P1to5_Advisor | 0XxgK000001IlSySAK | 004 |
| IR_Research_Agent | 0XxgK000001JItVSAW | 005 |
