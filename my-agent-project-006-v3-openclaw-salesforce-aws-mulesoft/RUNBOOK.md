# 006 V3 — Deployment Runbook

> **The single source of truth for deploying this project from zero.**
>
> This replaces the quickstart in README.md. The README tells you WHAT this project is. This RUNBOOK tells you HOW to deploy it step by step.
>
> **Time estimate for a new user who has all credentials ready:** 90 minutes of hands-on work. If you're signing up for vendors during the process, budget 4 hours.
>
> **Reading order:**
> 1. Section 0 — verify the codebase is healthy (2 minutes)
> 2. Section 1 — make sure you have everything before touching AWS
> 3. Section 2 — run the preflight script, it validates everything
> 4. Section 3 — the one-command deploy
> 5. Section 3.9 — seed demo data (required for the 18-minute narrative)
> 6. Section 4 — verify the demo works
> 7. Section 5 — troubleshoot if anything failed
> 8. Section 6 — clean teardown when you're done

---

## Section 0 — New user quick verification

Before touching any cloud service, verify the codebase is healthy on your machine.

```bash
cd my-agent-project-006-v3-openclaw-salesforce-aws-mulesoft

# 1. Backend tests (252 should pass, 6 pre-existing skips expected)
python3 -m pytest tests/ -q --tb=line \
  -k "not compliance_sweep and not narrative_3 and not seven_gate_chain"
# Expected: 252 passed, 8 deselected

# 2. Frontend tests
cd frontend && npx vitest run --reporter=dot && cd ..
# Expected: 146 passed

# 3. TypeScript compile check
cd frontend && npx tsc --noEmit && cd ..
# Expected: no errors

# 4. Python imports
python3 -c "from openclaw.orchestration.topology import AGENT_TOPOLOGY; print(f'{len(AGENT_TOPOLOGY)} agents')"
# Expected: 14 agents

python3 -c "from openclaw.skills import list_skills; print(f'{len(list_skills())} skills')"
# Expected: 16 skills
```

If any of these fail, you're on the wrong branch or missing dependencies. Run:
```bash
git checkout feat/006-v3-live-demo
pip install -r requirements.txt
cd frontend && npm ci && cd ..
```

### Key fixes in the current branch

These fixes are committed and will be picked up automatically by `deploy-all.sh`:

| Fix | File | What it does |
|---|---|---|
| Specialist timeout 22s → 45s | `openclaw/orchestration/research_orchestrator.py` | Prevents 2/5 specialists from timing out under real Bedrock |
| Citation ID enforcement | `openclaw/orchestration/topology.py` | Specialists cite real KB chunk IDs, not fabricated ones |
| V4 citation drill-down | `frontend/src/v4/personas/ResearchTerminalV4.tsx` | Re-enables the slide-over drawer on citation chip click |
| V4 client persistence | `frontend/src/v4/personas/ClientChannelV4.tsx` | Thread survives page refresh via localStorage |
| V4 client 3-button card | `frontend/src/v4/personas/ClientChannelV4.tsx` | "Send brief / Schedule call / Do nothing" on agent replies |
| V6 citation drawer | `frontend/src/v6/personas/ResearchTerminalV6.tsx` | Slide-over drawer for source chunk drill-down |
| V6 TS fix | `frontend/src/v6/personas/ResearchTerminalV6.tsx` | Optional chaining on regex match |
| Test alignment | `tests/unit/` (3 files) | Skill count 14→16, timeout 60→26, allowlist mcp_invoke |
| MuleSoft default sandbox | `openclaw/skills/mulesoft_api/actions.py`, `aws/mcp-servers/mulesoft-actions/app.py` | MULESOFT_MODE defaults to `sandbox` (was `mock`). CloudHub is live. |
| Real /agent/approve | `aws/mcp-servers/agent-proxy/app.py`, `aws/sam-template.yaml` | Approve endpoint calls real MuleSoft + Salesforce MCP instead of returning hardcoded JSON. SAM template adds MCP_API_URL, MCP_API_KEY, HITL_SIGNING_KEY_SSM env vars + SSM read permission. |
| Client 360 wired to CRM | `frontend/src/v6/personas/AdvisorWorkbenchV6.tsx` | Client 360 panel fetches real household data from salesforce-crm MCP when queue item selected. Falls back to placeholder when data unavailable. |
| V6 advisor layout fix | `frontend/src/v6/personas/AdvisorWorkbenchV6.tsx`, `frontend/src/v6/styles/v6.css` | Three-column alignment fixed (Queues header added). Sample Queries moved below body, above Trust Spine. |
| Frontend test count 137→146 | `frontend/` | New tests added; RUNBOOK Section 0 expected count updated. |

---

## Section 1 — Before you start

### 1.1 Local tools — install these first

```bash
# macOS (with homebrew)
brew install awscli jq maven
brew install --cask docker  # or: brew install finch

# Python 3.12+
brew install python@3.12

# Node 20+
brew install node@20

# AWS SAM CLI
brew install aws-sam-cli

# Salesforce CLI
npm install -g @salesforce/cli

# Java 17 (for MuleSoft packaging)
brew install openjdk@17

# AWS CDK
npm install -g aws-cdk
```

Exact version floors required:

| Tool | Minimum version | Check command |
|---|---|---|
| aws | 2.15.0 | `aws --version` |
| sam | 1.158.0 | `sam --version` |
| sf | 2.128.5 | `sf --version` |
| node | 20.0.0 | `node --version` |
| python | 3.12.0 | `python3 --version` |
| mvn | 3.9.0 | `mvn --version` |
| java | 17 | `java --version` |
| docker (or finch) | any current | `docker info` or `finch info` |
| cdk | 2.1114 | `cdk --version` |
| jq | any | `jq --version` |

Run `bash scripts/0-preflight.sh` to validate all of these automatically. That script is written specifically so you don't have to check these manually.

### 1.2 External accounts — sign up before you start

You need accounts with these vendors. All offer free tiers. Budget ~2 hours for signups if starting from zero.

| Vendor | Signup URL | Why you need it | Free tier? |
|---|---|---|---|
| AWS | https://aws.amazon.com/free/ | Bedrock, Lambda, CDK, all infra | Yes, with credit card |
| AWS Bedrock model access | AWS Console > Bedrock > Model Access | Sonnet 4.5, Haiku 4.5, Titan v2 | Free tier available |
| Salesforce | https://developer.salesforce.com/signup | FSC + Custom SObjects | Yes, Developer Edition |
| Finnhub | https://finnhub.io/register | Live market quotes | Yes, 60 req/min |
| Tavily | https://tavily.com | News search | Yes, 1000 searches/mo |
| Alpaca Paper | https://alpaca.markets | Paper trading for MuleSoft `submit-order` | Yes |
| Dwolla Sandbox | https://accounts-sandbox.dwolla.com | Wire transfer sandbox for `initiate-wire` | Yes |
| Anypoint Platform | https://anypoint.mulesoft.com | MuleSoft CloudHub deploy | Yes, 30-day trial |
| Langfuse US | https://us.cloud.langfuse.com | Observability + trace replay | Yes |
| Alpha Vantage | https://www.alphavantage.co/support/#api-key | Fallback market data | Yes, 25 req/day |

### 1.3 AWS Bedrock model access

This is the step most likely to bite you. Bedrock models are NOT enabled by default.

```bash
# Check whether Sonnet 4.5 is enabled in your account
aws bedrock list-foundation-models --region us-east-1 \
  --query 'modelSummaries[?contains(modelId, `sonnet-4`)].modelId' \
  --output text
```

If the list is empty:
1. Open AWS Console in us-east-1
2. Go to **Amazon Bedrock** → **Model Access**
3. Request access to: `anthropic.claude-sonnet-4-5`, `anthropic.claude-haiku-4-5`, `amazon.titan-embed-text-v2`
4. Approval is usually instant for Sonnet, takes 5-30 min for some regions

You cannot deploy v3 without these three models granted. The preflight script will fail loudly if any is missing.

### 1.4 Credential gathering — one-shot

Before running anything, gather these 34 values. Put them in a scratch file you'll paste into `.env`.

```
# AWS
AWS_REGION_BEDROCK=us-east-1
AWS_REGION_LAMBDA=us-east-2
AWS_ACCOUNT_ID=<your 12-digit account number>

# Bedrock models (all three must be granted)
BEDROCK_SONNET_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
BEDROCK_HAIKU_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
BEDROCK_TITAN_EMBED_MODEL_ID=amazon.titan-embed-text-v2:0

# Bedrock Guardrails (created by deploy)
BEDROCK_GUARDRAIL_ID=<filled by deploy>
BEDROCK_GUARDRAIL_VERSION=<filled by deploy>

# Internal signing keys — generate with openssl (preflight auto-generates)
AGENTCORE_SESSION_SIGNING_KEY=<64 hex chars>
HITL_SIGNING_KEY=<64 hex chars>
MCP_API_KEY=<64 hex chars>

# Vendor keys
FINNHUB_API_KEY=<from finnhub signup>
TAVILY_API_KEY=<from tavily signup>
ALPHA_VANTAGE_API_KEY=<from alpha vantage signup>
ALPACA_KEY_ID=<from alpaca paper>
ALPACA_SECRET=<from alpaca paper>
ALPACA_ENDPOINT=https://paper-api.alpaca.markets
DWOLLA_KEY=<from dwolla sandbox>
DWOLLA_SECRET=<from dwolla sandbox>

# MuleSoft Anypoint
MULESOFT_ORG_ID=<from anypoint profile page>
MULESOFT_CLIENT_ID=<from Anypoint Connected App>
MULESOFT_CLIENT_SECRET=<from Anypoint Connected App>
MULESOFT_BASE_URL=<your cloudhub URL>
MULE_SECURE_PROPERTIES_KEY=<16-char ASCII string, you pick>

# Salesforce
SF_INSTANCE_URL=<from SF setup>
SF_OAUTH_CLIENT_ID=<from SF Connected App>
SF_OAUTH_CLIENT_SECRET=<from SF Connected App>
SF_USERNAME=<integration user email>
SF_TARGET_ORG=new-org

# Langfuse
LANGFUSE_PUBLIC_KEY=<from langfuse project settings>
LANGFUSE_SECRET_KEY=<from langfuse project settings>
LANGFUSE_HOST=https://us.cloud.langfuse.com

# IdP (deferred — use placeholder if you don't have Okta/Azure AD)
IDP_ISSUER=<or leave as placeholder>
IDP_CLIENT_ID=<or leave as placeholder>
IDP_CLIENT_SECRET=<or leave as placeholder>

# Demo-mode toggles
MULESOFT_MODE=mock
OPENCLAW_DEV=false
MCP_DEV_MODE=false
CORS_ALLOW_ORIGIN=https://d2zs9nk4uc2dbx.cloudfront.net
SEC_EDGAR_UA=<YOUR_APP_NAME> <YOUR_CONTACT_EMAIL>
```

Full template is in `.env.example` — 72 lines, 34 values required.

---

## Section 2 — The preflight script

Before you touch AWS, run the preflight. It validates every prerequisite and bails early if anything is missing.

```bash
bash scripts/0-preflight.sh
```

What it checks:

```
[1/7] Local tools (8 checked with version floors)
[2/7] AWS credentials + account identity
[3/7] Bedrock model access (Sonnet 4.5, Haiku 4.5, Titan v2 probe)
[4/7] .env exists and has no placeholder values
[5/7] Signing keys generated (auto-fills if missing)
[6/7] Vendor API reachability (Finnhub, Tavily, Alpaca, Dwolla, Langfuse, Anypoint)
[7/7] Salesforce CLI auth (at least one org connected)
```

Expected output if all is ready:

```
[0-preflight]  ✓ All 7 checks passed. You are cleared to deploy.
[0-preflight]  Next step: bash scripts/deploy-all.sh
```

If any check fails, the script prints the exact remediation command. Example failure output:

```
[0-preflight]  ✗ Bedrock model access: us.anthropic.claude-sonnet-4-5
[0-preflight]    → Open: https://console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess
[0-preflight]    → Request access to "Claude Sonnet 4.5" and re-run this script
```

Do not proceed to deploy until preflight returns green.

---

## Section 3 — The one-command deploy

```bash
bash scripts/deploy-all.sh
```

What it does, in order. Each step is idempotent — safe to re-run.

```
Wave 0  Verify prereqs + seed secrets from .env to AWS SSM          1-2 min
Wave 1  CDK stacks: VPC, Aurora pgvector, Bedrock KB + OSS,         15-20 min
        Risk Alerts, Filings Pipeline, Research Pipeline
Wave 1b Salesforce: deploy metadata, assign permsets                  5-8 min
Wave 1c SF OBO Connected App: generate keypair, deploy metadata,      3-5 min
        retrieve ConsumerKey, populate bootstrap secret, grant
        SetupEntityAccess, cache-bust sf-auth-proxy Lambda
Wave 1d Cognito: create User Pool + App Client + 3 demo users,       2-3 min
        write frontend env vars, store SSM params
Wave 2  SAM stack: API Gateway + 8 MCP Lambdas + /agent/approve     10-15 min
        + compliance-trigger (EventBridge scheduled) + agent-proxy
        with Cognito JWKS verification (auto-reads pool ID from SSM)
Wave 3  Bedrock KB: download filings, chunk, ingest                   5-8 min
Wave 4  MuleSoft: verify-mule → mule-package → mule-deploy →        10-15 min
        set-mule-secure-properties → mule-health
Wave 5  AgentCore:                                                   8-12 min
         5a. Build OpenClaw container (linux/arm64, finch or docker)
         5b. Push to ECR (creates repo if missing)
         5c. Create or update runtime to pull new image
Wave 6  Frontend: build React (v1-v6 bundles), upload to S3,          3-5 min
        create CloudFront distribution
Wave 7  Smoke tests: 10 live probes                                   1-2 min
                                                       Total:  ~60-90 min
```

Run flags you may need:

```bash
./scripts/deploy-all.sh --skip-mulesoft   # if you don't have Anypoint yet
./scripts/deploy-all.sh --skip-frontend   # if you're iterating on backend
./scripts/deploy-all.sh --verify-only     # just run smoke tests
./scripts/deploy-all.sh --help
```

### 3.1 What gets created in AWS (everything goes in us-east-1 unless noted)

| Resource | Count | Cost (USD/day estimate) |
|---|---|---|
| CloudFormation stacks | 6 | — |
| Lambda functions | 11 | ~$0.50 idle |
| API Gateway REST APIs | 1 | ~$0.10 idle |
| Aurora Serverless v2 cluster | 1 | ~$3.00 (ACU min) |
| Bedrock Knowledge Base | 1 | ~$0 (storage only) |
| OpenSearch Serverless collection | 1 | ~$2.00 |
| S3 buckets (raw filings, chunks, frontend, sam-deploy) | 10 | ~$0.10 |
| SQS queues + DLQs | 4 | ~$0 |
| DynamoDB tables | 2 | ~$0 (on-demand) |
| Secrets Manager secrets | 4 | ~$1.60 |
| SSM Parameter Store entries | 29 | $0 (free tier) |
| CloudFront distribution | 1 | ~$0.05 |
| IAM roles | ~20 | $0 |
| **Estimated idle daily cost** | | **~$7-10** |
| **Full-demo day cost** | | **~$10-15** (Bedrock usage) |

### 3.2 What gets created in Salesforce

- 5 custom SObjects (Research_Brief__c, Client_Inquiry__c, Client_Preferences__c, IR_Audit_Log__c, IR_Pending_Approval__c)
- 2 Platform Events (Research_Brief_Published__e, Client_Alert_Auto_Send__e)
- 2 additional SObjects (Research_Request__c, IR_Position__c)
- 7 Apex classes
- 3 Apex triggers (AuditLogTrigger, ResearchBriefTrigger, Client_Inquiry_Alert_Trigger)
- 3 permission sets (Research_Analyst, Wealth_Advisor, Senior_Compliance_Approver)
- 2 additional permsets (V3_Audit_Fields, V3_Brief_Fields)

**CRITICAL — SF OBO Connected App (do this BEFORE deploy-all.sh Wave 4):**

The agent writes to Salesforce via a per-user OAuth JWT Bearer flow. This
requires a Connected App with a digital certificate. Without it, every
Salesforce write silently degrades (audit rows, briefs, inquiries all fail).

**One-time setup (15 minutes):**

```bash
# 1. Generate a self-signed cert
openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
  -subj "/CN=fsi-workforce-360/O=FSI/C=US" \
  -keyout /tmp/fsi-obo.key -out /tmp/fsi-obo.crt

# 2. In Salesforce Setup → App Manager → New Connected App:
#    - Name: FSI Workforce 360 OBO
#    - Enable OAuth: ✓
#    - Scopes: api, refresh_token, full
#    - Use digital signatures: ✓ → upload /tmp/fsi-obo.crt
#    - Save → capture Consumer Key
#    - Manage → Edit Policies → Permitted Users: Admin approved

# 3. Populate the AWS secret:
aws secretsmanager put-secret-value --region us-east-1 \
  --secret-id /006-v3/sf/bootstrap-creds \
  --secret-string "$(python3 -c "
import json
print(json.dumps({
    'client_id': '<PASTE_CONSUMER_KEY>',
    'subject_pattern': '<SF_INTEGRATION_USER_EMAIL>',
    'audience': 'https://login.salesforce.com',
    'private_key_pem': open('/tmp/fsi-obo.key').read(),
}))
")"

# 4. Clean up local key
rm -P /tmp/fsi-obo.key /tmp/fsi-obo.crt
```

Full step-by-step with screenshots: `docs/v3-p0-sf-obo-fix.md`

### 3.3 What gets created in MuleSoft Anypoint

- 3 CloudHub 2.0 applications (submit-order, initiate-wire, order-status-webhook)
- Per-app secure properties configuration in Runtime Manager
- Per-app policy stack (rate-limit, JSON threat, client-id, IP allowlist)

**IMPORTANT: MuleSoft runs in `sandbox` mode by default** (not mock). This means
the 7-gate write path routes through real CloudHub apps to Alpaca paper trading
and Dwolla sandbox. The SAM template sets `MULESOFT_MODE=sandbox` on the
mulesoft-actions Lambda, and the Lambda reads CloudHub URLs + Anypoint
credentials from SSM parameters populated by `deploy-all.sh`.

If you want to run in mock mode (no CloudHub needed), override the SAM parameter:
```bash
./scripts/deploy-all.sh --parameter-overrides MulesoftModeParam=mock
```

### 3.3.1 MuleSoft pre-deploy check — run this BEFORE `deploy-all.sh` Wave 6

Mule 4.9 has four non-obvious gotchas that cause CloudHub boot crashes.
They are documented in `docs/v3-mulesoft-gotchas.md`. All four are caught
automatically by a single Make target. Run it before every deploy:

```bash
cd my-agent-project-006-v3-openclaw-salesforce-aws-mulesoft
make verify-mule
```

Expected output — passes all 4 checks:
```
==> 1/4  checking mule-artifact.json exportedResources is non-empty...
==> 2/4  checking all config.yaml values are quoted strings...
==> 3/4  checking all config.yaml ${*.host} values are resolvable hostnames...
==> 4/4  checking no XML uses the nonexistent dw::core::Binaries::toHex function...
==> ALL CHECKS PASSED.
```

If any check fails, fix the referenced source file before proceeding. The
gotchas doc has the exact before/after syntax for each fix. Burning a
CloudHub deploy cycle on any of these costs 5-10 minutes of wall time per
app, so always run `verify-mule` locally first.

After a successful deploy, you MUST manually set per-app secure properties
in Anypoint Runtime Manager UI (Alpaca keys, Dwolla creds, webhook HMAC
+ MCP API key). Property names per app:

| App | Plain properties | Secure properties |
|---|---|---|
| `openclaw-v3-submit-order` | `alpaca.endpoint_host`, `alpaca.endpoint_path`, `mock_mode` | `alpaca.key_id`, `alpaca.secret` |
| `openclaw-v3-initiate-wire` | `dwolla.endpoint_host`, `dwolla.endpoint_path`, `dwolla.token_host`, `dwolla.token_path`, `mock_mode` | `dwolla.client_id`, `dwolla.client_secret` |
| `openclaw-v3-order-status-webhook` | `mcp.endpoint_host`, `mcp.endpoint_path`, `mock_mode` | `webhook.hmac_secret`, `mcp.api_key` |

Sources of truth for the secure values:
- Alpaca creds → AWS Secrets Manager at `/006-v3/vendors/alpaca`
- Dwolla creds → AWS Secrets Manager at `/006-v3/vendors/dwolla`
- Webhook HMAC → AWS Secrets Manager at `/006-v3/vendors/alpaca-webhook`
- MCP API key → AWS SSM Parameter Store at `/006-v3/mcp/api-key`

### 3.4 What gets created in Langfuse

- 1 project (you create it manually in Langfuse UI, paste keys into .env)
- Traces accumulate automatically after the first agent turn

### 3.5 Frontend versions — URL routing

Six UI variants ship in the same bundle. **V6 is the recommended default.**

| Variant | URL pattern | What it is |
|---|---|---|
| **v1** | `https://<dist>/?persona=research&v1=1` | Original UIUX shipped with the project |
| **v2** | `https://<dist>/?persona=research&v2=1` | UX refresh from the uploaded UIUX Design zip |
| **v3** (FSI Workforce 360) | `https://<dist>/?persona=research&v3=1` | Map polish + FSI rebrand + Cognito scaffold |
| **v4** (designer verbatim) | `https://<dist>/?persona=research&v4=1` | Disciplined rebuild ported verbatim from UIUX Design zip |
| **v5** (surface hierarchy) | `https://<dist>/?persona=research&v5=1` | V4 layout + V5 visual refinement (spacing, borders, typography) |
| **v6** ⭐ **recommended** | `https://<dist>/?persona=research` | SLDS-inspired light theme with dark toggle, all 3 personas |

When no version flag is set, the app defaults to **V6**. To force an older
version, add the explicit flag (e.g. `&v1=1`, `&v4=1`).

Personas: `?persona=research` (Sarah Chen) · `?persona=advisor` (Marcus Kerrigan) · `?persona=client` (Eleanor Vance).

v2 adds: Workflow 360 branding, always-visible 7-gate tracker, 3-orchestrator architecture map with ghost spine edges, inline HITL ActionCard (replaces the v1 modal), phone-bezel client channel, per-specialist map pulses.

v3 adds on top of v2:
- **FSI Workforce 360 brand** — new `FsiLogo` (three persona-arcs around a hub), `--fsi-*` CSS tokens, advisor attribution reads "FSI Workforce 360 · Advisor".
- **Live architecture map polish** — hover tooltips (role + kind + persona + model + tools + MCPs + last latency + Langfuse hint), collapsible legend (6 kinds + 4 states), this-turn-only filter toggle, per-persona caption strip, progressive gate disclosure (chain only renders when a write is in flight), trust-spine glow band (replaces v2's ambiguous ghost edges), higher-contrast edges.
- **Cognito OAuth PKCE** — when `VITE_COGNITO_*` env vars are populated, v3 gates every persona render on a signed Cognito access token. Graceful fallback to `dev-bootstrap-token` when unset. See Section 3.7.

v4 adds: disciplined rebuild ported verbatim from the uploaded UIUX Design zip. Every measurement comes from the designer's original file. Dark theme only (no toggle). Trust spine with traversal map + timeline + audit strip.

v5 adds: V4 components with V5 surface-hierarchy CSS overrides — spacing rhythm, border removal, visual anchor, typography refinement.

v6 adds on top of v4/v5:
- **SLDS-inspired light theme** — light default with dark toggle (persisted to `localStorage`).
- **All 3 personas** — ResearchTerminalV6, AdvisorWorkbenchV6, ClientChannelV6.
- **Collapsible trust spine** — `<details>` element wrapping V4's TraversalMapV4 + TimelineV4.
- **All nav links use `v6=1`** — persona switching stays in V6.
- **Designed identities** — Sarah Chen / Marcus Kerrigan / Eleanor Vance (not "Dev User").

v1 and v2 branding stays as "Workflow 360" — v3+ renames to "FSI Workforce 360".

Source layout:

```
frontend/src/
├── App.tsx              # thin router (v6=default, v5/v4/v3/v2 by flag, v1=explicit)
├── shared/              # types, stores, hooks, lib, data — used by all versions
├── v1/                  # original UI (V1App, components, personas, styles)
├── v2/                  # uploaded-design UI (V2App, atoms, personas, styles)
├── v3/                  # FSI Workforce 360 UI + Cognito auth
│   ├── V3App.tsx
│   ├── auth/            # cognito.ts (PKCE flow) + AuthCallback.tsx
│   ├── atoms/           # FsiLogo, PersonaHeaderV3, TraversalMapV3
│   ├── personas/        # ResearchTerminalV3, AdvisorWorkbenchV3, ClientChannelV3
│   └── styles/          # tokens.css, header.css, map.css, personas.css
├── v4/                  # designer-verbatim rebuild
│   ├── V4App.tsx
│   ├── atoms/           # GatesTrackerV4, TraversalMapV4, TimelineV4, AuditStripV4, etc.
│   ├── personas/        # ResearchTerminalV4, AdvisorWorkbenchV4, ClientChannelV4
│   ├── styles/          # fonts.css, fsi-design-system.css
│   └── theme/           # useTheme.ts
├── v5/                  # V4 + surface-hierarchy CSS overrides
│   ├── V5App.tsx
│   └── styles/          # v5-overrides.css
└── v6/                  # SLDS-inspired light theme with dark toggle ⭐
    ├── V6App.tsx
    ├── atoms/           # PersonaHeaderV6
    ├── personas/        # ResearchTerminalV6, AdvisorWorkbenchV6, ClientChannelV6
    └── styles/          # v6.css
```

Rules for contributors:
- No cross imports between version subtrees — shared code must live in shared/
- All shared types live in shared/types/
- Adding a component that multiple versions need? Put it in shared/components/
- All six variants must stay functional independently — tests cover all paths
- V6 components may import V4 atoms (TraversalMapV4, TimelineV4, AuditStripV4) — this is intentional

Full design record: `docs/v3-frontend-reorg-and-wiring.md`.
Uploaded design study: `docs/v3-frontend-uploaded-design-study.md`.
Per-narrative coverage: `docs/v3-frontend-v2-narrative-coverage.md`.
v3 status + delta: `docs/v3-frontend-v3-status.md`.
v6 status: `docs/v6-frontend-status.md`.

### 3.6 Advisor action_write — two-turn architecture

The advisor's write path splits across two API Gateway calls to fit inside
the 29-second REST timeout. Both endpoints are live and smoke-tested.

**Turn 1 — draft plan** (`POST /agent/invoke` · ~20s)

The advisor_orchestrator detects an action verb (trim/sell/buy/wire/...)
and prepends `[DRAFT_ONLY mode]` to the dispatch. The coordinator sees
this sentinel and runs a single Bedrock converse call (no tool-use loop)
through gates 1-3 (guardrails, MNPI filter, compliance_screening). The
response envelope carries an extracted `action_plan` with deterministic
`plan_hash`.

**Turn 2 — approval round-trip** (`POST /agent/approve` · ~1s)

Frontend's HttpAgentTransport posts the approval to `/agent/approve`. The
Lambda handler runs gates 4-7 (hitl token verify, dual_auth, mulesoft,
audit) and returns the canonical gate trace. MuleSoft gate returns
`failed` honestly when CloudHub apps aren't deployed — this is
deliberate, not a bug. No mockery drama.

Why this matters for new users: if you skip the container rebuild in
Wave 5, you get a stale runtime where advisor action_write returns 504.
`build-and-push-openclaw.sh` is the step that prevents that.

### 3.7 Cognito auth (v3) — opt-in, deferred setup

The v3 SPA supports real OAuth 2.0 PKCE via Cognito. The frontend scaffold
is already in the bundle (`src/v3/auth/cognito.ts` + `AuthCallback.tsx`);
activation is env-var driven, and the User Pool + App Client are
provisioned one-time by the operator.

Without `VITE_COGNITO_*` set, v3 gracefully falls back to the same
`dev-bootstrap-token` flow v2 uses — demos still work out of the box.

To enable Cognito:

1. Follow `docs/v3-cognito-setup.md` Steps 1–3 to create the User Pool,
   App Client, and a demo user.
2. Paste the four `VITE_COGNITO_*` values into `frontend/.env.production`.
3. Rebuild + redeploy:
   ```bash
   npm --prefix frontend run build
   bash scripts/deploy-frontend-cloudfront.sh
   ```
4. (Optional, for real token verification on the backend) Follow Step 4
   in the setup doc to add JWKS verification to the agent-proxy Lambda.
   Until you do Step 4, the Lambda still accepts any bearer in
   `MCP_DEV_MODE=true` — the Cognito tokens pass through, but so would
   anything else.

Sign-out button is in `PersonaHeaderV3` (appears automatically when a
Cognito session is detected).

### 3.8 Closing the last two P0 items (deferred backend fixes)

After `deploy-all.sh` succeeds you still have two narrative-integrity gaps
that require follow-up steps. Neither is fixable from `deploy-all.sh`
alone — both require either Salesforce admin actions or a code change in
files the backend builder is iterating on.

**P0 A — Salesforce OBO chain (closes audit rows zero + Research_Request 401).**
The Secrets Manager bootstrap secret ships empty by default; populating
it requires a one-time Connected App creation in the target Salesforce
org. Full 6-step playbook: `docs/v3-p0-sf-obo-fix.md`. After the secret
is populated:

```bash
aws lambda update-function-configuration \
  --region us-east-1 \
  --function-name 006-v3-sf-auth-proxy \
  --environment "Variables={CACHE_BUST=$(date +%s),...preserve other vars...}"

# Confirm fix
bash scripts/narrative-e2e-test.sh
# Expect: 23/23 and IR_Audit_Log__c > 0 for today
```

**P0 B — Research specialist citation drift (closes `(source not available)`).**
Specialists emit fabricated citation IDs like `[src:nvda-10q-20251026]`
instead of the real chunk IDs like `[src:NVDA-000104581025000230-c0042]`.
Fix location is `openclaw/orchestration/topology.py` in the
`FILINGS_SPECIALIST_PROMPT` / `STATEMENT_SPECIALIST_PROMPT`. Full
remediation + prompt snippet: `docs/v3-p0-source-chunk-citation-drift.md`.

---

## Section 3.9 — Seed demo data (required for the 18-minute narrative)

After `deploy-all.sh` completes and before the demo, seed the Salesforce org with the 4 households and trigger the EDGAR backfill.

### 3.9.1 Salesforce demo data

Seeds 4 households with META concentration above 5% (Patel, Chen, Nakamura, Al-Rashid), positions, IPS records, and touchpoint history. The Patel household is the primary demo target for Acts 1-2.

```bash
sf apex run --file scripts/seed-demo-data.apex --target-org new-org
```

Verify:
```bash
sf data query --query "SELECT Contact__c, Ticker__c, Pct_Of_Equity__c FROM IR_Position__c WHERE Ticker__c = 'META'" --target-org new-org
# Expected: 4 rows, all with Pct_Of_Equity__c > 5.0
```

### 3.9.2 EDGAR backfill for demo tickers

Triggers the filings-ingest Lambda for 9 tickers (META, GOOGL, MSFT, NVDA, AVGO, QCOM, AMD, AAPL, TSM) across 3 filing types (8-K, 10-K, 10-Q), then re-indexes the Bedrock KB.

```bash
bash scripts/seed-edgar-demo.sh
```

This takes 5-10 minutes. Monitor KB ingestion:
```bash
# Check ingestion status
aws bedrock-agent list-ingestion-jobs \
  --knowledge-base-id <KB_ID from deploy output> \
  --data-source-id <DS_ID from deploy output> \
  --region us-east-1
```

### 3.9.3 META earnings call transcript (optional, recommended)

The META Q1 2026 earnings call transcript is NOT on EDGAR (transcripts never are). For the demo's cross-asset thesis to cite the actual call:

1. Download the transcript PDF from META's IR site or Seeking Alpha
2. Open Sarah's terminal at `?persona=research&v6=1`
3. Drag-drop the PDF onto the terminal (the Textract handler ingests it)

Alternatively, the demo works without the transcript — the brief will cite the 8-K press release instead, which has the same revenue/EPS/capex numbers.

### 3.9.4 Demo URLs

After seeding, the demo is ready at:

```
Research (Sarah):  https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v6=1
Advisor (Marcus):  https://d2zs9nk4uc2dbx.cloudfront.net/?persona=advisor&v6=1
Client (Eleanor):  https://d2zs9nk4uc2dbx.cloudfront.net/?persona=client&v6=1
```

Pre-demo warm-up (run 10 minutes before doors open):
```bash
bash scripts/warm-start.sh
# Or if warm-start.sh requires env vars you don't have:
curl -s -X POST https://<API_URL>/v3/agent/invoke \
  -H 'Authorization: Bearer dev-bootstrap-token' \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"hello","persona":"fsi_research","principal_id":"warmup","session_id":"warmup-000","turn_number":1}'
```

---

## Section 4 — Verify the deployment

After `deploy-all.sh` completes, run the smoke test.

```bash
bash scripts/smoke-test.sh
```

Expected output:

```
==========================================
006 V3 live smoke test
==========================================

[1/5] Frontend SPA served via CloudFront...
[PASS] Frontend HTTP

[2/5] MCP market-data root...
[PASS] market-data returns MCP descriptor

[3/5] Live Finnhub NVDA quote through market-data Lambda...
[PASS] Finnhub quote for NVDA

[4/5] KB kb_retrieve over 784 real SEC-filing chunks...
[PASS] KB returns real NVDA chunks

[5/5] Full agent turn: browser -> agent-proxy -> AgentCore -> Bedrock...
[PASS] Agent turn status=ok
[PASS] Agent turn had gate activity

[6/8] v2 envelope — canonical gates + specialist_trace...
[PASS] gate_trace canonical, specialist_trace present

[7/8] v2 advisor action_write — draft-only mode surfaces action_plan...
[PASS] draft action_plan surfaced
[PASS] advisor draft-only action_plan emitted

[8/8] /agent/approve — gates 4-7 canonical trace...
[PASS] /agent/approve returns hitl
[PASS] /agent/approve returns mulesoft (honest failed)
[PASS] /agent/approve returns audit
==========================================
Result: 10 passed, 0 failed
==========================================
```

All 10 must pass. If any fail, see Section 5.

Next, exercise the three narratives live:

```bash
# Narrative 1 — Research turn
bash scripts/warm-start.sh  # pre-warm AgentCore for faster first turn
curl -X POST https://e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3/agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Research NVDA ahead of earnings","persona":"fsi_research","session_id":"demo-1","principal_id":"sarah"}'

# Narrative 2 — Client message
curl -X POST https://e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3/agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"prompt":"I heard semis are crashing. Should I sell?","persona":"fsi_client_liaison","session_id":"demo-2","principal_id":"patel"}'

# Narrative 3 — Risk alert (simulate)
bash scripts/simulate-price-shock.sh NVDA -8.0
```

Open the frontend at the CloudFront URL printed by deploy-all, switch personas via the URL query `?persona=research|advisor|client`.

Verify Salesforce rows were written:

```bash
sf data query --query "SELECT COUNT() FROM Research_Brief__c" --target-org new-org
sf data query --query "SELECT COUNT() FROM Client_Inquiry__c" --target-org new-org
sf data query --query "SELECT COUNT() FROM IR_Audit_Log__c WHERE CreatedDate = TODAY" --target-org new-org
```

Open Langfuse at https://us.cloud.langfuse.com/project/<your-project-id> and view the trace tree for each turn.

---

## Section 5 — Troubleshooting

Every known failure mode with the exact fix command.

### 5.1 Preflight failures

**`aws sts get-caller-identity` fails**
```bash
aws configure  # follow prompts to set access key, secret, region
```

**`bedrock:InvokeModel` fails on Sonnet 4.5**
```bash
# Open AWS Console > Bedrock > Model Access
# Request access to: Claude Sonnet 4.5, Claude Haiku 4.5, Titan Text Embeddings v2
# Wait 5-10 minutes after approval, re-run preflight
```

**`.env` has placeholder values**
```bash
# Open .env, search for "<YOUR_" and "<GENERATE_" strings
# Replace each with real value or run: bash scripts/0-preflight.sh --generate-signing-keys
```

**Salesforce org not connected**
```bash
sf org login web --alias new-org
```

### 5.2 Deploy failures

**CDK rollback on Openclaw006V3-Vpc**
> Cause: NAT gateway quota exceeded
> Fix: request quota increase or free unused NAT gateways
```bash
aws service-quotas request-service-quota-increase \
  --service-code vpc --quota-code L-FE5A380F --desired-value 10 \
  --region us-east-1
```

**CDK rollback on Openclaw006V3-Aurora**
> Cause: SchemaMigrator Lambda env vars exceeded 4KB limit
> Fix: already fixed in current code (SQL files shipped as Lambda assets, not env vars). If you see this, you're on an old branch.
```bash
git checkout feat/006-v3-live-demo  # ensure you're on the fixed branch
```

**CDK rollback on Openclaw006V3-Kb**
> Cause: OpenSearch Serverless access policy propagation race
> Fix: also already fixed. If you see this, re-run — the second attempt succeeds most of the time.
```bash
cd aws/cdk && cdk deploy Openclaw006V3-Kb
```

**SAM Lambda returns HTTP 502 with `Runtime.ImportModuleError: No module named '_base'`**
> Cause: Lambda layer packaging. Fixed.
> Fix: re-run `sam build && sam deploy` — the current template packages the layer correctly.
```bash
cd aws && sam build && sam deploy
```

**Salesforce deploy fails with `INVALID_FIELD` on Agent_Id__c or Session_Id__c**
> Cause: permset not assigned, or FieldDefinition cache lag
> Fix: wait 15 min, re-run salesforce deploy
```bash
sf project deploy start --target-org new-org --wait 30
sf org assign permset -n V3_Audit_Fields -o new-org
```

**MuleSoft CloudHub app stuck in `APPLYING`**
> Cause: secure properties not set in Runtime Manager
> Fix: open Anypoint Runtime Manager UI
> 1. Go to app → Settings → Properties
> 2. Set `mule.secure.properties.key` to the value in your `.env` `MULE_SECURE_PROPERTIES_KEY`
> 3. Restart the app

**Frontend 403 from CloudFront**
> Cause: S3 Origin Access Control policy
> Fix:
```bash
bash scripts/deploy-frontend-cloudfront.sh  # re-runs the OAC setup
```

**AgentCore runtime won't start**
> Cause: Docker image not pushed to ECR, or push went to wrong region
> Fix:
```bash
bash scripts/build-and-push-openclaw.sh   # build + push container
bash scripts/create-v3-agentcore.sh       # update runtime to pull it
```

**ECR repo doesn't exist (ImageManifestNotFound)**
> Cause: `openclaw-agentcore` ECR repo was never created in this account
> Fix: `build-and-push-openclaw.sh` creates the repo if missing. Running
> `create-v3-agentcore.sh` alone will fail with an honest error pointing
> you at the build step.
```bash
bash scripts/build-and-push-openclaw.sh
```

**Advisor action_write returns HTTP 504 or "specialist exceeded 25s"**
> Cause: stale AgentCore runtime — draft-only mode not active.
> Fix: the draft-only split requires the container version from
> 2026-04-30 or later. Rebuild and redeploy:
```bash
bash scripts/build-and-push-openclaw.sh
bash scripts/create-v3-agentcore.sh
bash scripts/smoke-test.sh    # check [7/8] passes
```

**v2 InlineActionCard never renders after advisor turn**
> Cause: backend envelope doesn't have `action_plan` field — usually a
> stale AgentCore runtime before the 2026-04-30 envelope wiring was
> deployed.
> Fix: same as above — rebuild + redeploy the container. Verify via:
```bash
curl -s -X POST $API_URL/agent/invoke \
  -H 'Authorization: Bearer dev-token' \
  -H 'Content-Type: application/json' \
  --data '{"prompt":"Trim NVDA 14% to 9%","persona":"fsi_advisor","session_id":"probe-xxxxxxxxxxxxxxxxxx","principal_id":"test"}' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('has action_plan:', 'action_plan' in d and d['action_plan'] is not None)"
# Expected: has action_plan: True
```

**/agent/approve returns 403 "Missing Authentication Token"**
> Cause: SAM stack wasn't redeployed after 2026-04-30 — the
> `/agent/approve` route is new in this branch.
> Fix:
```bash
cd aws && sam build && sam deploy \
    --stack-name openclaw-mcp-006-v3 \
    --region us-east-1 \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --no-confirm-changeset --resolve-s3
```

**v2 UI shows blank page (after `?v2=1`)**
> Cause: older frontend bundle cached by CloudFront before v2 was built.
> Fix:
```bash
cd frontend && npm run build
cd ..
bash scripts/deploy-frontend-cloudfront.sh   # re-syncs + invalidates
```

**AgentCore runtime won't start (OLD issue)**
> Cause: Docker image not pushed to ECR, or push went to wrong region
> Fix: see the new "AgentCore runtime won't start" entry above — requires
> two scripts now (build-and-push THEN create-v3-agentcore). The
> previous single-script version is obsolete.

**Bedrock KB `retrieve` returns empty**
> Cause: ingestion job failed or is still running
> Fix:
```bash
aws bedrock-agent list-ingestion-jobs --region us-east-1 \
  --knowledge-base-id $(aws cloudformation describe-stacks \
    --stack-name Openclaw006V3-Kb \
    --query 'Stacks[0].Outputs[?OutputKey==`KnowledgeBaseId`].OutputValue' --output text) \
  --data-source-id $(aws cloudformation describe-stacks \
    --stack-name Openclaw006V3-Kb \
    --query 'Stacks[0].Outputs[?OutputKey==`KbDataSourceId`].OutputValue' --output text)

# if status != COMPLETE, wait or re-run
python3 scripts/seed-kb-chunks.py  # re-upload chunks if needed
```

**MuleSoft apps deploy but stay in CrashLoopBackOff / readiness probe fails**
> Cause: one of the four Mule 4.9 gotchas — empty exportedResources in
> mule-artifact.json, integer/empty YAML values, unresolvable `${*.host}`
> placeholders, or a nonexistent DataWeave function.
> Fix: run the pre-deploy check, it tells you exactly which one:
```bash
cd my-agent-project-006-v3-openclaw-salesforce-aws-mulesoft
make verify-mule
```
> If all four checks pass locally but apps still crash on CloudHub, the
> problem is per-app Runtime Manager properties. Verify per app:
> - submit-order: alpaca.key_id + alpaca.secret in Secure Properties
> - initiate-wire: dwolla.client_id + dwolla.client_secret in Secure Properties
> - order-status-webhook: webhook.hmac_secret + mcp.api_key in Secure Properties
> Full details: `docs/v3-mulesoft-gotchas.md`

**sf-auth-proxy env vars wiped after manual cache-bust**
> Cause: Running `aws lambda update-function-configuration` with only `CACHE_BUST` wipes all other env vars.
> Fix: Always preserve existing vars when busting the cache:
```bash
# WRONG — wipes SF_BOOTSTRAP_SECRET and SF_AUTH_PROXY_KEY:
aws lambda update-function-configuration --function-name 006-v3-sf-auth-proxy --environment "Variables={CACHE_BUST=$(date +%s)}"

# RIGHT — preserves all vars:
SF_KEY=$(aws ssm get-parameter --name /006-v3/sf/auth-proxy-key --with-decryption --region us-east-1 --query 'Parameter.Value' --output text)
aws lambda update-function-configuration --function-name 006-v3-sf-auth-proxy --region us-east-1 \
  --environment "Variables={SF_BOOTSTRAP_SECRET=/006-v3/sf/bootstrap-creds,SF_AUTH_PROXY_KEY=$SF_KEY,SF_AUTH_PROXY_MODE=live,CACHE_BUST=$(date +%s)}"
```

### 5.3 Post-deploy issues

**Agent turn returns `Runtime error` or 500**
> Check CloudWatch logs:
```bash
aws logs tail /aws/bedrock-agentcore/runtimes/openclaw_v3_agent-o72dx396I0-DEFAULT \
  --region us-east-1 --since 5m
```

**Smoke test fails step [5/5] Agent turn**
> Cause: AgentCore runtime cold start timeout (first turn can take 30s)
> Fix:
```bash
bash scripts/warm-start.sh  # pre-warms the runtime
bash scripts/smoke-test.sh  # re-run
```

**Agent gets 401 calling MCPs**
> Cause: `MCP_API_KEY` in AgentCore env differs from what the Lambdas expect
> Fix: check both match the value in SSM parameter `/006-v3/mcp/api-key`
```bash
aws ssm get-parameter --name /006-v3/mcp/api-key --with-decryption \
  --region us-east-1 --query 'Parameter.Value' --output text
# Update AgentCore runtime env if different:
aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id openclaw_v3_agent-... \
  --environment-variables "MCP_API_KEY=<paste value>" \
  --region us-east-1
```

**Salesforce calls fail with `invalid_grant`**
> Cause: SF Connected App consumer_key + private_key in Secrets Manager are
> placeholders. This blocks the OBO chain → audit writes silently fail +
> Research_Request__c writes return 401 + Research_Brief__c may not be
> published end-to-end.
> Full playbook: `docs/v3-p0-sf-obo-fix.md` — 6 steps (Console Connected
> App → openssl cert → populate secret → bust Lambda cache → live-verify).
> Quick one-shot after you have the Connected App set up:
```bash
aws secretsmanager put-secret-value \
  --secret-id /006-v3/sf/bootstrap-creds \
  --secret-string "$(cat <<EOF
{"client_id":"<your connected app consumer key>",
 "subject_pattern":"<your SF integration user email>",
 "audience":"https://login.salesforce.com",
 "private_key_pem":"<the connected app private key pem>"}
EOF
)" --region us-east-1

# Bust sf-auth-proxy Lambda cold-start cache
aws lambda update-function-configuration --region us-east-1 \
  --function-name 006-v3-sf-auth-proxy \
  --environment "Variables={CACHE_BUST=$(date +%s)}"

# Verify: audit rows now land
sleep 15
sf data query --query "SELECT COUNT() FROM IR_Audit_Log__c WHERE CreatedDate = TODAY" --target-org new-org
# Expect: > 0 after the next agent turn
```

**Citation drill-down shows `(source not available)`**
> Cause: research specialists (filings/statement) emit fabricated citation
> IDs like `[src:nvda-10q-20251026]` instead of the real S3 chunk key
> format `[src:NVDA-000104581025000230-c0042]`. The sec-edgar MCP's
> `get_source_chunk` falls through to the empty stub.
> Fix: update the specialist prompts in `openclaw/orchestration/topology.py`
> (`FILINGS_SPECIALIST_PROMPT`, `STATEMENT_SPECIALIST_PROMPT`) to require
> verbatim `source_chunk_id` from `kb_retrieve`.
> Full fix: `docs/v3-p0-source-chunk-citation-drift.md`.

---

## Section 6 — Teardown

When you're done with the demo, clean up everything.

```bash
bash scripts/9-destroy.sh
```

What it destroys, in reverse deployment order:

```
[1/9]  MuleSoft CloudHub apps (mvn mule:undeploy)
[2/9]  AgentCore runtime + ECR image
[3/9]  Frontend CloudFront + S3 bucket
[4/9]  SAM stack (all Lambdas, API Gateway, NAT, VPC endpoints)
[5/9]  CDK stacks (VPC, Aurora, Kb, Pipelines, Risk Alerts) — in reverse dep order
[6/9]  SSM parameters under /006-v3/*
[7/9]  Secrets Manager secrets starting with /006-v3/
[8/9]  Salesforce permsets (not deleted — to avoid breaking other users)
[9/9]  Local credentials in .env (preserved — you decide whether to keep)
```

Each step is confirmation-gated. Pass `--force` to skip confirmations.

```bash
bash scripts/9-destroy.sh --force  # non-interactive teardown, for CI
```

Teardown time: ~15-20 min.

After teardown, verify zero remnants:

```bash
aws cloudformation list-stacks --region us-east-1 \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query 'StackSummaries[?contains(StackName, `006V3`) || contains(StackName, `006-v3`)]' \
  --output table
# expect: empty

aws ssm get-parameters-by-path --path /006-v3 --region us-east-1 \
  --query 'Parameters[].Name' --output text
# expect: empty
```

---

## Section 7 — Quick reference card

One-liners for the most common operations.

```bash
# Health-check live deployment (10 probes including v2 envelope + /agent/approve)
bash scripts/smoke-test.sh

# Fire a test turn through the live stack
bash scripts/simulate-price-shock.sh NVDA -8.0
bash scripts/warm-start.sh

# Tail logs
aws logs tail /aws/bedrock-agentcore/runtimes/openclaw_v3_agent-* \
  --region us-east-1 --follow

# Force-redeploy a single Lambda (e.g. after editing agent-proxy/app.py)
cd aws && sam build && sam deploy

# Rebuild + redeploy AgentCore container (after editing openclaw/*.py)
bash scripts/build-and-push-openclaw.sh   # build + push to ECR
bash scripts/create-v3-agentcore.sh       # update runtime to pick up new image

# Re-ingest filings into KB
python3 scripts/download-real-filings.py --tickers NVDA,AAPL,MSFT
python3 scripts/seed-kb-chunks.py

# Rebuild + redeploy frontend only (both v1 and v2 bundles)
cd frontend && npm run build && cd ..
bash scripts/deploy-frontend-cloudfront.sh

# Reset the Salesforce demo data
bash scripts/seed-demo-rows.sh

# Full teardown
bash scripts/9-destroy.sh
```

**Live URLs after deploy**:

| What | URL |
|---|---|
| **v6 research ⭐ (default)** | **https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research** |
| **v6 advisor ⭐ (default)** | **https://d2zs9nk4uc2dbx.cloudfront.net/?persona=advisor** |
| **v6 client ⭐ (default)** | **https://d2zs9nk4uc2dbx.cloudfront.net/?persona=client** |
| v6 research (explicit) | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v6=1 |
| v6 advisor (explicit) | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=advisor&v6=1 |
| v6 client (explicit) | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=client&v6=1 |
| v5 research | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v5=1 |
| v4 research (designer verbatim) | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v4=1 |
| v4 advisor (designer verbatim) | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=advisor&v4=1 |
| v4 client (designer verbatim) | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=client&v4=1 |
| v3 research (FSI Workforce 360) | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v3=1 |
| v3 advisor (FSI Workforce 360) | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=advisor&v3=1 |
| v3 client (FSI Workforce 360) | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=client&v3=1 |
| v2 research | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v2=1 |
| v2 advisor | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=advisor&v2=1 |
| v2 client | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=client&v2=1 |
| v1 research | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v1=1 |
| API `/agent/invoke` | https://e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3/agent/invoke |
| API `/agent/approve` | https://e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3/agent/approve |

*(CloudFront and API Gateway URLs above are stable IDs from this account's
deploy. Yours will differ — `deploy-all.sh` prints your actual URLs at
the end.)*

---

## Section 8 — Support + escalation

If you hit an issue not in Section 5:

1. **Check the v3 status docs** for the current live-probed state of each
   backend claim:
   - `docs/v3-frontend-v3-status.md` — what shipped in the v3 frontend
     (FSI Workforce 360 + map polish + Cognito scaffold) and what's
     deferred.
   - `docs/v3-pending-mock-vs-real.md` — live probe receipts of every
     backend claim.
   - `docs/v3-design-vs-built-vs-deployed-v2.md` — most recent scoreboard.
2. **Check the P0 handoff runbooks** for the two items that `deploy-all.sh`
   cannot fix:
   - `docs/v3-p0-sf-obo-fix.md` — Salesforce OBO chain (closes audit +
     Research_Request writes).
   - `docs/v3-p0-source-chunk-citation-drift.md` — research specialist
     citation format (closes "source not available" drill-down).
   - `docs/v3-cognito-setup.md` — upgrade from `dev-bootstrap-token` to
     real Cognito hosted UI.
3. **Check the script docstrings** — every script in `scripts/` starts
   with a header explaining what it does and why.
4. **Open an issue** on the repo with: output of `bash scripts/0-preflight.sh`,
   output of failing command, CloudWatch logs if applicable.

---

*Runbook written 2026-04-30. This is the authoritative deployment doc.*
