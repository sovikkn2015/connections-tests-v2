# 006 v2: MuleSoft Anypoint Onboarding — Step by Step

> Owner: project lead
> Status: in progress
> Goal: get a working MuleSoft Connected App, store the credentials in AWS Secrets Manager, and confirm the OAuth token endpoint returns successfully. All without putting a single secret in git or chat.

---

## Prerequisites

- [x] MuleSoft Anypoint Platform account created (free trial)
- [x] Logged in at https://anypoint.mulesoft.com
- [ ] AWS CLI installed and configured with a profile that can write to Secrets Manager
- [ ] A password manager or local .env.local file outside the repo for temporary secret storage

---

## Step 1: Note the Organization ID

The Anypoint org ID is in the browser URL when logged in:

```
https://anypoint.mulesoft.com/home/organizations/{ORG_ID}
```

This ID is a tenant/account identifier, not a secret. It is safe to share in chat.

Record it in a local note for Step 5.

---

## Step 2: Create the Connected App

1. Click the green avatar in the top right corner.
2. Click Access Management from the dropdown.
3. In the left sidebar, click Connected Apps.
4. Click Create App.
5. Fill in:
   - Name: openclaw-006-v2-mulesoft-mcp
   - Type: select "App acts on its own behalf (client credentials)"
     - Do NOT pick "App acts on behalf of user"
6. Click Add Scope and add all four:
   - Exchange Viewer
   - Design Center Developer
   - API Manager Environment Administrator (when prompted, select the Sandbox environment)
   - Runtime Manager Read Only (when prompted, select the Sandbox environment)
7. Click Save.
8. A dialog appears with:
   - Client ID (visible and copyable any time)
   - Client Secret — shown only once. Copy it immediately.
9. Paste both into a password manager, or into a local .env.local file OUTSIDE the repo.

Do NOT paste the Client Secret into chat, git, Slack, or any shared channel.

---

## Step 3: Find the Environment ID

1. Still in Access Management (left sidebar).
2. Click Environments.
3. Locate the Sandbox environment (named "Sandbox" or "Design" by default).
4. Click it. The URL or the details page will show an ID field.
5. Copy the UUID.

The environment ID is safe to share.

---

## Step 4: Verify the Credentials Work

Open a local terminal. Do NOT paste these commands into chat with real values.

```bash
# Set temporary env vars for this shell only. They disappear when the terminal closes.
export CLIENT_ID='paste-client-id-from-step-2'
export CLIENT_SECRET='paste-client-secret-from-step-2'

curl -s -X POST "https://anypoint.mulesoft.com/accounts/api/v2/oauth2/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=$CLIENT_ID&client_secret=$CLIENT_SECRET"
```

Expected response:

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

- If the response has `access_token` — the Connected App is working. Move to Step 5.
- If the response has an `error` field — copy the error message (NOT the access_token) and share it in chat.

Do NOT paste the access_token anywhere outside the local terminal. It is a live credential.

---

## Step 5: Store Credentials in AWS Secrets Manager

Still in the same terminal (so CLIENT_ID and CLIENT_SECRET env vars are still set from Step 4):

```bash
# Replace the placeholders with the values from Steps 1 and 3.
ENV_ID='PASTE_ENV_UUID_FROM_STEP_3'
ORG_ID='PASTE_ORG_UUID_FROM_STEP_1'

aws secretsmanager create-secret \
  --name /006-v2/mulesoft/credentials \
  --description "MuleSoft Anypoint Connected App — 006 v2 Phase 6" \
  --secret-string "{
    \"client_id\": \"$CLIENT_ID\",
    \"client_secret\": \"$CLIENT_SECRET\",
    \"base_url\": \"https://anypoint.mulesoft.com\",
    \"organization_id\": \"$ORG_ID\",
    \"environment_id\": \"$ENV_ID\"
  }" \
  --region us-east-1 \
  --tags Key=Project,Value=006-v2 Key=Phase,Value=6
```

Expected output:

```
{
  "ARN": "arn:aws:secretsmanager:us-east-1:XXXXXXXXXXXX:secret:/006-v2/mulesoft/credentials-abc123",
  "Name": "/006-v2/mulesoft/credentials",
  "VersionId": "..."
}
```

The ARN is safe to share. The values inside the secret are not.

---

## Step 6: Clear Secrets From Shell History

```bash
unset CLIENT_ID
unset CLIENT_SECRET
history -c   # wipes bash shell history for this session
```

On zsh, optionally also run:

```bash
rm ~/.zsh_history   # aggressive — only if a shell leak is suspected
```

If the Client Secret was pasted into a temporary file during Step 2, delete that file now (or move it into the password manager and then delete the temp file).

---

## Step 7: Report Back in Chat

Paste this in chat. All values below are safe to share — none are secrets.

```
region: us (anypoint.mulesoft.com)
org id: <from step 1>
env id: <from step 3>
secret arn: <from step 5>
token test: returned ok
```

If anything failed, paste the error message instead.

---

## Reference: What NOT to Share in Chat or Git

- Client Secret from Step 2
- Access Token from Step 4
- The secret-string JSON body from Step 5 (contains the secret)
- AWS account credentials

## Reference: What IS Safe to Share

- Organization ID from Step 1
- Environment ID from Step 3
- Client ID from Step 2 (it is a public identifier, like a username)
- Secret ARN from Step 5 (it points to the secret, it does not contain it)
- AWS region
- Error messages

---

## If Something Goes Wrong

| Problem | Fix |
|---|---|
| "Invalid client or scope" on token call | Recheck the scopes added in Step 2. Client-credentials apps need explicit environment scope bindings. |
| `Unable to locate credentials` on AWS CLI | Run `aws configure` or set `AWS_PROFILE` first. |
| Secret already exists | Use `aws secretsmanager update-secret` instead, or delete the old one: `aws secretsmanager delete-secret --secret-id /006-v2/mulesoft/credentials --force-delete-without-recovery` |
| Lost the Client Secret (did not copy it at Step 2) | Regenerate in Connected Apps → your app → Rotate Secret. The old secret stops working. |
| Trial expires before code ships | Free tier keeps API Designer and Exchange access. Connected App keeps working for design artifacts. Only CloudHub 2.0 deploy is disabled. |

---

## After This Is Done

The assistant will:

1. Update `aws/sam-template.yaml` to grant `MuleSoftActionsFunction` Lambda permission to read the secret by ARN.
2. Add `mulesoft_client.py` to the MCP server that reads the secret and handles OAuth token refresh.
3. Implement the `MULESOFT_MODE=sandbox` code path in `aws/mcp-servers/mulesoft-actions/app.py`.
4. Update `docs/v2-vendor-onboarding-tracker.md` to mark MuleSoft as onboarded.

No code changes until Step 7 is complete.

---

## Notes on the MuleSoft Free Trial

- Full Anypoint features for 30 days (CloudHub 2.0 deploy, Runtime Manager, API Manager, Design Center).
- After 30 days the account reverts to Basic Services — API Designer, limited API Portals, and Anypoint Exchange (public).
- The Connected App keeps working for API-level calls against free-tier features.
- Plan: use the 30 days to design process APIs (RAML + DataWeave) in Anypoint Code Builder. Deploy to CloudHub only when ready for an end-to-end demo.
- Anypoint Studio (desktop IDE) is free forever — design work can continue offline.

## Notes on the Agent Fabric Splash Page

The "MuleSoft Agent Fabric is Here!" banner on the Anypoint home page is a separate MuleSoft product. It is NOT used in 006. Per steering rule 1, OpenClaw on AgentCore is the only agent runtime in 006. Ignore the banner.

"MuleSoft Vibes" (natural-language prompt builder) is also not part of the 006 stack. Ignore.
