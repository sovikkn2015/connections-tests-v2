# v3 Cognito Setup — Enterprise Auth Playbook

**Roadmap item #3** — replace `dev-bootstrap-token` with a real IdP. This
doc is the one-time provisioning guide: User Pool + App Client + agent-proxy
JWKS verification. After this runs, the v3 SPA gates every turn on a signed
Cognito access token instead of a hardcoded bearer.

---

## What this delivers

| Boundary | Before | After |
|---|---|---|
| Browser → SPA | `dev-bootstrap-token` synthesized by v2 bootstrap | Cognito hosted UI login (RS256 id/access tokens) |
| SPA → agent-proxy Lambda | Any bearer accepted in `MCP_DEV_MODE=true` | Bearer is Cognito access token; verified against JWKS |
| principal_id | Hardcoded to `"sarah"` / `"marcus"` / `"eleanor"` from the persona prop | Extracted from JWT `sub` claim (real user) |
| Session lifetime | No refresh — reloads mint a new token | 1hr access token + refresh rotation at 55min |
| Sign-out | N/A | SPA header button clears local session + redirects to Cognito `/logout` |

Note: the Salesforce OBO chain (separate from browser auth) is NOT changed.
CRM writes continue through `sf-auth-proxy` with the JWT Bearer flow against
the Connected App. See `docs/v3-p0-sf-obo-fix.md` for that.

---

## Prerequisites

1. AWS account with Cognito permissions (any IAM principal that can create
   User Pools).
2. CloudFront distribution for the v3 SPA already deployed — you need its
   URL to configure the callback.
3. The v3 frontend code already includes the Cognito scaffold
   (`frontend/src/v3/auth/cognito.ts` + `AuthCallback.tsx` + `V3App.tsx`
   gate). No code changes needed; this doc only provisions the backing
   Cognito resources and flips the env flags.

---

## Step 1 — Create the User Pool (Console, one-time)

In the AWS Console, us-east-1:

1. **Cognito → User pools → Create user pool**
2. **Configure sign-in experience:**
   - Cognito user pool sign-in options: **Email**
   - User name requirements: default
3. **Configure security requirements:**
   - Password policy: **Cognito defaults** (8+ chars, mixed case, number, symbol)
   - MFA: **Optional MFA → Authenticator apps** (TOTP). For a demo pool you
     can pick No MFA. For a production pool leave Optional on and advertise
     TOTP.
   - User account recovery: **Email only**
4. **Configure sign-up experience:**
   - Self-service sign-up: **Disabled** (admins invite users — this matters
     for a demo where you don't want strangers).
   - Required attributes: `email`, `name`.
   - Custom attributes (optional — used by agent-proxy to pin Salesforce user):
     - Add `custom:salesforce_user_id` (String, mutable).
5. **Configure message delivery:**
   - Email provider: **Send email with Cognito** (free tier 50/day — fine for demo).
6. **Integrate your app:**
   - User pool name: `fsi-workforce-360`
   - Hosted authentication pages: **Use the Cognito Hosted UI**
   - Domain:
     - Type: **Use a Cognito domain**
     - Domain prefix: `fsi-workforce-360` (or pick another globally unique prefix;
       the full domain becomes `https://fsi-workforce-360.auth.us-east-1.amazoncognito.com`)
   - Initial app client:
     - App type: **Public client** (SPA, no secret)
     - App client name: `fsi-workforce-360-spa`
     - Client secret: **Do not generate** (PKCE doesn't need one)
     - Authentication flows: check only `ALLOW_USER_SRP_AUTH` + `ALLOW_REFRESH_TOKEN_AUTH` — the hosted UI handles the rest.
     - Identity providers: **Cognito user pool** (you can add Google / Azure
       AD / Okta later)
     - OAuth 2.0 grant types: ✓ **Authorization code grant**, leave the
       others unchecked.
     - OpenID Connect scopes: ✓ `OpenID`, `Profile`, `Email`.
     - Callback URL: `https://<your-cloudfront-domain>/auth/callback`
       (e.g. `https://d2zs9nk4uc2dbx.cloudfront.net/auth/callback`)
     - Sign-out URL: `https://<your-cloudfront-domain>/`
7. **Review + create.**

Capture these four values — you'll paste them into `.env.production`:

| Value | Where to find |
|---|---|
| **User Pool ID** | Pool overview → "User pool ID" (e.g. `us-east-1_AbCd1234`) |
| **App Client ID** | App integration → App client list → your client → "Client ID" |
| **Cognito Domain** | App integration → "Domain" section → full URL |
| **Region** | `us-east-1` (hardcoded in this demo; pool must be in same region as agent-proxy) |

---

## Step 2 — Create an initial admin user

```bash
# Adjust region if your pool is elsewhere
POOL_ID="us-east-1_AbCd1234"
USER_EMAIL="demo-admin@example.com"
TEMP_PASS="Temp-$(openssl rand -hex 4)!"

aws cognito-idp admin-create-user \
  --region us-east-1 \
  --user-pool-id "$POOL_ID" \
  --username "$USER_EMAIL" \
  --user-attributes Name=email,Value="$USER_EMAIL" Name=email_verified,Value=true Name=name,Value="Demo Admin" \
  --temporary-password "$TEMP_PASS" \
  --message-action SUPPRESS

echo "User created. Temp password: $TEMP_PASS"
echo "First sign-in at the hosted UI will prompt for a new password."
```

Repeat for each demo persona (Sarah, Marcus, Eleanor) so each can log in
as themselves on stage.

---

## Step 3 — Populate frontend env vars

Edit `frontend/.env.production`:

```bash
# Cognito — v3 auth (roadmap item #3)
VITE_COGNITO_DOMAIN=https://fsi-workforce-360.auth.us-east-1.amazoncognito.com
VITE_COGNITO_CLIENT_ID=<paste App Client ID>
VITE_COGNITO_REDIRECT_URI=https://d2zs9nk4uc2dbx.cloudfront.net/auth/callback
VITE_COGNITO_SCOPE=openid profile email
```

Rebuild + redeploy the frontend:

```bash
npm --prefix frontend run build
bash scripts/deploy-frontend-cloudfront.sh
```

At this point `https://<cf>/?v3=1&persona=research` should render the
"Sign in with Cognito" button instead of the persona UI. Clicking it
redirects to the Cognito hosted UI. After a successful login, the browser
bounces back to `/auth/callback?code=...`, the code is exchanged for
tokens, and the persona renders.

**Graceful fallback:** if any of the three vars is unset, the v3 SPA
falls back to `dev-bootstrap-token` mode. Flipping Cognito on or off is
a build-time env change, not a code change.

---

## Step 4 — Wire agent-proxy Lambda to verify the JWT

Today the Lambda accepts any bearer when `MCP_DEV_MODE=true`. After Step 3
the SPA sends real Cognito access tokens. To actually enforce those, the
Lambda must verify the signature against Cognito's JWKS.

### 4a. Add env vars

Update the SAM template to pass the pool ID + region to agent-proxy:

```yaml
# aws/sam-template.yaml — inside AgentProxyFunction.Properties.Environment.Variables
COGNITO_USER_POOL_ID: !Ref CognitoUserPoolId
COGNITO_APP_CLIENT_ID: !Ref CognitoAppClientId
COGNITO_REGION: us-east-1
```

And add the two parameters at the top of the template:

```yaml
Parameters:
  CognitoUserPoolId:
    Type: String
    Default: ""
    Description: Cognito user pool ID; empty disables JWT verification (dev mode).
  CognitoAppClientId:
    Type: String
    Default: ""
    Description: Cognito app client ID for audience claim check.
```

Then redeploy:

```bash
cd aws
sam build
sam deploy --parameter-overrides \
  CognitoUserPoolId=us-east-1_AbCd1234 \
  CognitoAppClientId=<your client id> \
  --stack-name openclaw-mcp-006-v3 \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --region us-east-1
```

### 4b. Add JWKS verification code

In `aws/mcp-servers/agent-proxy/app.py`, add a helper that:

1. On cold start, fetches `https://cognito-idp.<region>.amazonaws.com/<pool_id>/.well-known/jwks.json`
   and caches the key set for 1hr.
2. On each request, reads `Authorization: Bearer <token>`, decodes the JWT
   header to find the `kid`, looks up the matching key in the JWKS, and
   verifies the RS256 signature.
3. Validates claims: `iss` matches the pool URL, `aud` or `client_id`
   matches the app client id, `token_use` is `"access"`, `exp` is in the
   future.
4. Extracts `sub` and sets it as `principal_id` on the downstream request
   (overrides any `X-Principal-Id` header the browser tried to send — the
   token is the source of truth).
5. Only falls back to the old dev-bootstrap acceptance when
   `COGNITO_USER_POOL_ID` is empty string.

Reference implementation (paste into `agent_proxy/app.py` next to the
existing auth logic):

```python
import json, time, urllib.request
from typing import Any, Dict, Optional

try:
    from jose import jwt, jwk
    from jose.utils import base64url_decode
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False  # add python-jose[cryptography] to requirements.txt

_JWKS_CACHE: Dict[str, Any] = {}
_JWKS_TTL_SEC = 3600


def _load_jwks(pool_id: str, region: str) -> list[dict]:
    now = time.time()
    cached = _JWKS_CACHE.get("keys")
    fetched_at = _JWKS_CACHE.get("at", 0)
    if cached and now - fetched_at < _JWKS_TTL_SEC:
        return cached
    url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json"
    with urllib.request.urlopen(url, timeout=5) as resp:
        body = json.loads(resp.read())
    _JWKS_CACHE["keys"] = body["keys"]
    _JWKS_CACHE["at"] = now
    return body["keys"]


def verify_cognito_access_token(
    token: str,
    pool_id: str,
    app_client_id: str,
    region: str = "us-east-1",
) -> Optional[Dict[str, Any]]:
    """Returns the claims dict on success; None on any verification failure.
    Never raises — callers should treat None as 'reject'."""
    if not JWT_AVAILABLE or not token or not pool_id:
        return None
    try:
        headers = jwt.get_unverified_header(token)
        kid = headers.get("kid")
        if not kid:
            return None
        for key in _load_jwks(pool_id, region):
            if key["kid"] == kid:
                public_key = jwk.construct(key)
                message, encoded_sig = token.rsplit(".", 1)
                decoded_sig = base64url_decode(encoded_sig.encode())
                if not public_key.verify(message.encode(), decoded_sig):
                    return None
                # Signature ok — now decode and validate claims
                claims = jwt.get_unverified_claims(token)
                issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"
                if claims.get("iss") != issuer:
                    return None
                if claims.get("token_use") != "access":
                    return None
                if claims.get("client_id") != app_client_id:
                    return None
                if int(claims.get("exp", 0)) < int(time.time()):
                    return None
                return claims
        return None
    except Exception:  # noqa: BLE001 — any error means reject
        return None
```

Then at the top of `handler(event, context)`, replace the bearer-accept
block with:

```python
pool_id = os.environ.get("COGNITO_USER_POOL_ID", "")
app_client_id = os.environ.get("COGNITO_APP_CLIENT_ID", "")
region = os.environ.get("COGNITO_REGION", "us-east-1")

if pool_id and app_client_id:
    token = auth_header.removeprefix("Bearer ").strip()
    claims = verify_cognito_access_token(token, pool_id, app_client_id, region)
    if not claims:
        return _json(401, {"error": "invalid_token"})
    principal_id = claims.get("sub")
    # Optional — if you set custom:salesforce_user_id, use it to
    # pin the SF OBO subject instead of principal_id.
    sf_user_hint = claims.get("custom:salesforce_user_id")
else:
    # Dev-bootstrap fallback (no Cognito pool configured)
    principal_id = event["headers"].get("x-principal-id", "dev-principal")
    sf_user_hint = None
```

Add to `requirements.txt`:

```
python-jose[cryptography]==3.3.0
```

Rebuild + redeploy.

---

## Step 5 — Live verify

```bash
# Open the v3 SPA
open "https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v3=1"

# Expected: Cognito hosted UI appears. Log in with the user you created.
# Expected: redirected to /auth/callback, then back to /?persona=research&v3=1
# Expected: persona UI renders. Type "NVDA quick brief" + ⌘↵.

# Confirm the bearer token going out on /agent/invoke is a real JWT:
# In browser DevTools → Network → agent/invoke request → Headers
# "Authorization: Bearer eyJra..." (starts with eyJ, three dot-separated parts)

# Confirm agent-proxy Lambda is verifying it:
aws logs tail /aws/lambda/006-v3-agent-proxy --region us-east-1 --since 2m
# Expect: zero errors. If you see "invalid_token" logs, the pool id is
# wrong or JWKS fetch failed.

# Try a negative case — bad token should now be rejected:
curl -s -X POST https://e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3/agent/invoke \
  -H 'Authorization: Bearer garbage' \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"test","persona":"fsi_research","principal_id":"x","session_id":"neg","correlation_id":"neg","turn_number":1}'
# Expected: HTTP 401 {"error":"invalid_token"}  (before Step 4 this returned 200)
```

---

## Step 6 — Sign-out wiring (optional)

The v3 `PersonaHeaderV3` already has a "Sign out" button when a Cognito
session is active. It calls `clearSession()` + redirects to:

```
https://<cognito-domain>/logout?client_id=<client_id>&logout_uri=<app-origin>
```

No backend work needed — Cognito kills the hosted-UI session cookie and
bounces the user back to the app root, which then shows "Sign in with
Cognito" again.

---

## Cost

| Resource | Free tier | Paid tier |
|---|---|---|
| Cognito User Pool — 50,000 MAU | Free | $0.0055 / MAU beyond 50k |
| Hosted UI emails via Cognito | 50/day | $0.10 / 1,000 beyond |
| JWT JWKS fetches by Lambda | Free | Free (cached hourly) |

For a demo user pool (10 users, a few hundred logins per month), expected
cost is **$0.00**.

---

## Security notes

1. **App Client has no secret.** PKCE replaces the client secret for
   public SPAs. Do not add a client secret; it breaks the PKCE flow.
2. **Callback URL must match exactly** including trailing slash (or lack
   thereof). Cognito rejects with `redirect_mismatch` otherwise.
3. **Refresh token is stored in `localStorage`.** This is the standard
   Cognito SPA pattern but means XSS on the domain can steal the refresh
   token. Mitigations: strict CSP (already applied via CloudFront
   default), no untrusted third-party scripts, HttpOnly-cookie-based
   sessions require a separate BFF-style backend (V5 work).
4. **`token_use` check matters.** Cognito issues both an access token and
   an id token per login. The access token is what the API should verify
   (token_use=access); the id token is for SPA use only (token_use=id).
   Never accept id tokens as API bearers.
5. **App client id is the audience for access tokens.** Unlike standard
   OAuth where `aud` is the client, Cognito puts the client id in
   `client_id` for access tokens and in `aud` for id tokens. The verifier
   above checks `client_id` because it's validating the access token.
6. **JWKS rotation.** Cognito rotates keys rarely but does. The 1-hour
   cache above tolerates rotation delays up to 1hr; for tighter SLAs,
   lower `_JWKS_TTL_SEC` or invalidate on first failed `kid` lookup.

---

## Teardown

```bash
# Delete the pool (revokes all sessions immediately)
aws cognito-idp delete-user-pool \
  --region us-east-1 \
  --user-pool-id us-east-1_AbCd1234

# Unset the env vars + rebuild frontend
# (see frontend/.env.example for which VITE_COGNITO_* to blank)
npm --prefix frontend run build
bash scripts/deploy-frontend-cloudfront.sh

# Revert sam deploy to empty Cognito params (restores dev-bootstrap mode)
cd aws
sam deploy --parameter-overrides CognitoUserPoolId="" CognitoAppClientId="" \
  --stack-name openclaw-mcp-006-v3 --region us-east-1 \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM
```

---

## What's NOT in this doc (deferred to V4/V5)

- **Federated IdP** (Google / Okta / Azure AD). Cognito supports all three
  via the App Integration → Identity providers tab. Adding them is a
  Cognito-console action, no code changes — but each IdP requires its
  own app registration on the IdP side and is out of scope for a demo
  user pool.
- **Token exchange for SF OBO.** Today the sf-auth-proxy mints SF JWT
  tokens from a Connected App private key, using a hardcoded subject
  pattern. Ideally the Cognito `custom:salesforce_user_id` claim feeds
  into that subject — see `docs/v3-p0-sf-obo-fix.md` Step 3 Option B.
- **SCIM provisioning** between the enterprise IdP and Cognito, so
  joiners/leavers in the corporate directory auto-sync.
- **Cognito Identity Pool** for per-user temporary AWS credentials (e.g.
  signed S3 pre-signed URLs). Not needed for this architecture; the
  Lambda is the only AWS caller and it uses its execution role.

---

*Written 2026-05-01 as the deferred follow-through on TASK 6 frontend v3.
Complements `docs/v3-p0-sf-obo-fix.md` (backend SF chain) and
`docs/v3-frontend-v3-status.md` (SPA-side scaffold already shipped).*
