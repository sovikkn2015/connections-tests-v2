# V3 Reproducibility Plan — Zero-to-Demo for a New User

Date: April 2026
Status: plan. Nothing built from this doc yet.
Constraint: no new IaC. CDK + SAM + SFDX cover infra; this plan adds orchestration + data seeding + verification scripts on top.

---

## Ground truth from an actual AWS inspection

Ran against the live account (875460787302, us-east-1, IAM `fsi_investment_user2`, AdministratorAccess) before drafting this plan. Findings:

| Check | State | Impact on plan |
|---|---|---|
| AWS CLI authenticated, admin IAM | ✓ | plan.layer0 can verify with `aws sts get-caller-identity` |
| CDK bootstrap v30 in `/cdk-bootstrap/hnb659fds/version` | ✓ already bootstrapped | plan.layer2 can skip `cdk bootstrap` if this param exists |
| `anthropic.claude-sonnet-4-6` model | agreement AVAILABLE | good — but not invocable by raw model id |
| `anthropic.claude-haiku-4-5-20251001-v1:0` model | agreement AVAILABLE | same |
| On-demand invoke with raw model id | **FAILS** — `ValidationException: "Invocation ... with on-demand throughput isn't supported. Retry with the ID or ARN of an inference profile"` | V3's `BEDROCK_SONNET_MODEL_ID` / `BEDROCK_HAIKU_MODEL_ID` must resolve to inference profile IDs, not raw model ids |
| Active inference profiles: `us.anthropic.claude-sonnet-4-6`, `us.anthropic.claude-haiku-4-5-20251001-v1:0` | ACTIVE | **use these as the defaults in `.env.example`** |
| Actual converse via `us.anthropic.claude-sonnet-4-6` → `READY`. Via `us.anthropic.claude-haiku-4-5-20251001-v1:0` → `OK` | invokes work | no code change — only the env-var default needs to become the profile id |
| SSM `/006-v3/*` | **empty** | seed-secrets.sh must run before any Lambda invoke |
| Secrets Manager in us-east-1 | pending (clock skew during inspection) | treat as "assume empty, seed before deploy" |
| SF CLI sees 2 connected orgs; default `new-org`. No DevHub marked | no scratch-org creation capability on this machine | plan.layer2 deploys against `new-org` directly; skips `sf org create scratch` |

### Net: what already exists vs what I need

**Have (no work):** AWS admin, CDK bootstrap v30, Bedrock Sonnet 4.6 + Haiku 4.5 + Titan v2 model agreements, two connected SF orgs, installed CLIs (aws 2.15+, sf 2.128, mvn 3.9, cdk 2.1114, sam, docker, node 25, python 3.10).

**Need (to acquire):** Finnhub key, Tavily key, Alpha Vantage key, Alpaca paper account keys, Dwolla sandbox keys, Langfuse cloud keys, Anypoint Connected App credentials, three generated signing keys (openssl).

**Need (to seed into AWS):** 11 SSM parameters + 4 Secrets Manager entries (both in us-east-1 to match `AWS_REGION_BEDROCK`). seed-secrets.sh already writes the right shapes.

**Need (to build):** 7 new scripts + 1 runbook documented below.

---

## The approach — layered, numbered, idempotent

Nine scripts, numbered. Each does exactly one thing. The umbrella `demo.sh` runs them in order with prompts.

```
scripts/
├── 0-preflight.sh       (new) — verify CLIs, versions, AWS/SF auth. Generate signing keys. Print provisioning checklist.
├── 1-validate-env.sh    (new) — parse .env, check every required var is filled, flag placeholders, confirm Bedrock model ids resolve.
├── 2-bootstrap.sh       (new) — one-time infra bootstrap: CDK bootstrap if missing, confirm target SF org is connected, ensure frontend S3 bucket exists.
├── 3-seed-secrets.sh    (exists, rename from seed-secrets.sh) — push .env → SSM + Secrets Manager.
├── 4-deploy.sh          (exists, rename from deploy-all.sh) — CDK + SAM + Mulesoft + AgentCore + frontend.
├── 5-seed-demo-data.sh  (new) — Apex script: 3 households, 3 contacts, 5 positions, 3 Client_Preferences. Stages one pre-seeded Client_Inquiry for Act 3 wildcard.
├── 6-verify.sh          (new) — end-to-end smoke: sign Sarah in, publish brief, assert SObject counts; simulate NVDA shock, assert 3 alerts appear.
├── 7-warm-start.sh      (exists, rename from warm-start.sh) — pre-heat AgentCore persona containers before demo.
├── 9-destroy.sh         (new) — inverse of 2/3/4: sf project retrieve → delete, cdk destroy --all, sam delete, aws ssm delete-parameters on /006-v3/*.
└── demo.sh              (new) — umbrella: runs 0→6 with clean prompts. Supports `fresh`, `reset`, `destroy`, `verify-only`.
```

Everything idempotent. Re-running any step is safe. No state lives in any script.

---

## What each script does — in detail

### scripts/0-preflight.sh (~180 lines)

Verifies 9 CLIs with version floors. Verifies AWS auth + current region + account id. Verifies SF default org is connected. Generates signing keys via `openssl rand -hex 32` if `.env` has placeholder `<GENERATE_64_HEX_CHARS>` values, writing them back in-place. Prints a provision-these-yourself checklist with sign-up URLs (Finnhub, Alpaca paper, Dwolla sandbox, Tavily, Langfuse cloud, Anypoint trial). Never blocks — user gates their own progress.

Output shape:
```
✓ aws          2.15.3         (account 875460787302 · us-east-1)
✓ sf           2.128.5        (default org: new-org)
✓ cdk          2.1114.1
✓ sam          1.129.0
✓ mvn          3.9.15
✓ docker       24.0.7         (running)
✓ npm          10.2.3         node 22.11.0
✓ python       3.10.9

Signing keys (written to .env — never committed):
  AGENTCORE_SESSION_SIGNING_KEY  generated
  HITL_SIGNING_KEY               already set
  MCP_API_KEY                    already set

Provision yourself (free tier exists for all):
  [ ] Finnhub                https://finnhub.io/register
  [ ] Alpaca paper           https://alpaca.markets
  [ ] Tavily                 https://tavily.com
  [ ] Dwolla sandbox         https://accounts-sandbox.dwolla.com
  [ ] Langfuse cloud         https://cloud.langfuse.com
  [ ] Anypoint (30-day trial)https://anypoint.mulesoft.com/login
```

### scripts/1-validate-env.sh (~140 lines, uses Python)

Reads `.env`. For each of the 27 required variables:
- Confirm set and non-empty.
- Confirm not a `<YOUR_...>` or `<GENERATE_...>` placeholder.
- Spot-check value shape (e.g. `BEDROCK_SONNET_MODEL_ID` starts with `us.anthropic.claude-sonnet-4` per the inventory finding; `HITL_SIGNING_KEY` is 64 hex; `SF_INSTANCE_URL` is https URL).
- For `BEDROCK_SONNET_MODEL_ID` and `BEDROCK_HAIKU_MODEL_ID` specifically: call `bedrock list-inference-profiles` and confirm the id is `ACTIVE`. This catches the real failure mode we discovered on inspection.

Exit non-zero if any check fails, printing a fix-it table.

### scripts/2-bootstrap.sh (~120 lines)

Only the things that must exist before seed/deploy can run. Idempotent.

1. CDK bootstrap in us-east-1 if `/cdk-bootstrap/hnb659fds/version` is missing (skip if present — we have it already).
2. Confirm the chosen SF target org is connected (`sf org list`). If not, print command to auth: `sf org login web --alias v3-demo-org`. Do NOT attempt scratch-org creation — that needs DevHub which may not be available.
3. Create the frontend S3 bucket + CloudFront distribution if `FRONTEND_BUCKET` is set in .env and doesn't exist.
4. Verify Anypoint credentials by calling `curl -X POST https://anypoint.mulesoft.com/accounts/api/v2/oauth2/token` with the Connected App client creds — refuses the deploy if auth fails here to avoid a 20-minute SAM + CDK roundtrip before Mulesoft fails.

### scripts/3-seed-secrets.sh (renamed from seed-secrets.sh — zero change, 90 lines)

Already built and working. Re-run any time credentials rotate. Pushes 11 SSM + 4 Secrets.

### scripts/4-deploy.sh (renamed from deploy-all.sh, ~220 lines)

Already built. Runs CDK → SAM → Mulesoft → AgentCore → Frontend in order. Each step has a `--skip-*` flag. Already idempotent.

One addition: **before** any step runs, assert the previous step's outputs exist (e.g. SAM step asserts CDK outputs exist in CFN; Mulesoft step asserts SAM's `ApiUrl` + `NatEip` outputs are present so the Mulesoft allowlist can be populated). No step runs blind.

### scripts/5-seed-demo-data.sh (~140 lines — Apex + shell)

One anonymous-Apex payload + one SOQL upsert script. Inserts, against `SF_TARGET_ORG`:

| Record | Count | Purpose |
|---|---|---|
| `Account` (household) | 3 | Patel, Okafor, Lee |
| `Contact` (client) | 3 | one per household, with realistic names |
| `IR_Position__c` | 5 | NVDA, AAPL, MSFT, TSLA, GOOGL across 3 households at 6-8.5% concentration |
| `Client_Preferences__c` | 3 | two auto-send on volatility, one off |
| `Client_Inquiry__c` (research-suggestion) | 1 | pre-seeded for Act 3 panel wildcard |
| `Research_Brief__c` (historical) | 2 | 30-day-old briefs, so the RM's `research_awareness` skill has something to surface |

Uses `sf apex run --file scripts/apex/seed-demo-data.apex --target-org "${SF_TARGET_ORG}"`. Idempotent via upsert-on-external-id pattern.

Also pre-stages EDGAR filings: runs a one-shot invocation of the `filings-corpus/ingest_handler.py` Lambda with a 5-ticker watchlist override. That way the retriever has something to retrieve from the Bedrock KB on the first query.

### scripts/6-verify.sh (~200 lines)

End-to-end smoke against the real deployed stack. No mocks. Four scenarios:

**Narrative 1 — Earnings Morning**
- Open a WS session as principal Sarah, persona `fsi_research`.
- Send the canonical query: `Research NVDA ahead of earnings...`
- Assert `stopReason: end_turn` within 90s.
- SOQL: `Research_Brief__c` count increased by 1, author = Sarah, has non-empty `source_chunk_ids`.

**Narrative 2 — Client Drives Research (inversion)**
- Open WS as principal Patel (client).
- Send: `I heard NVDA is down. Should I be worried?`
- Assert the client-liaison returns the RM-gated disclaimer.
- SOQL: `Client_Inquiry__c` count increased by 1, `Type__c = question`.

**Narrative 3 — Risk Alert**
- Directly drop a synthetic shock event onto `ComplianceSweepQueue`: `{"ticker":"NVDA","price_change_pct":-7.5,...}`
- Wait 30s.
- SOQL: 3 new `Client_Inquiry__c` rows with `Type__c = alert`, 2 with `Auto_Send_Eligible__c = true`.
- Poll `/api/inquiries?type=alert` via BFF — assert 3 items.

**Narrative 5 — Large Liquidation (7-gate spine)**
- Open WS as RM, send the liquidation query.
- Simulate HITL approval via Apex direct write (faster than waiting for a UI tab).
- Simulate dual-auth approval.
- Assert the tool-use dispatch loop completes; `IR_Audit_Log__c` has a row with `Gate_Trace__c` containing all 5 gates in order.

Output:
```
✓ Narrative 1  earnings morning               42.3s
✓ Narrative 2  client drives research          7.1s
✓ Narrative 3  risk alert fanout              28.4s   (3 alerts, 2 auto, 1 review)
✓ Narrative 5  large liquidation 7-gate       61.8s   (all gates ok)

Demo is READY. Open:
  https://d1234.cloudfront.net?persona=research
  https://d1234.cloudfront.net?persona=advisor
  https://d1234.cloudfront.net?persona=advisor&view=alerts
  https://d1234.cloudfront.net?persona=client
  https://cloud.langfuse.com/project/<id>/traces
```

### scripts/9-destroy.sh (~130 lines)

Inverse of 2/3/4, in reverse order. Each step is guarded with a confirm unless `--force` passed.

1. `cdk destroy --all` on all 6 V3 stacks.
2. `sam delete --stack-name openclaw-mcp-006-v3 --region us-east-1`.
3. For each Mulesoft app: `mvn mule:undeploy -Pcloudhub-sandbox`.
4. `sf project delete source -r` on the scaffolded SObjects (do NOT delete the org — user owns that).
5. Delete every SSM param under `/006-v3/*`.
6. Delete every Secrets Manager entry starting with `/006-v3/`.
7. `aws s3 rb s3://${FRONTEND_BUCKET} --force` and `aws cloudfront delete-distribution`.

### scripts/demo.sh (~120 lines)

```bash
./scripts/demo.sh fresh        # 0→1→2→3→4→5→6
./scripts/demo.sh reset        # 9→fresh
./scripts/demo.sh destroy      # 9 only
./scripts/demo.sh verify-only  # 6 only (against existing deploy)
./scripts/demo.sh partial      # 4→5→6 (assumes 0-3 already ran)
```

Each transition is interactive by default. `--yes` flag skips confirms for CI.

---

## Runbook doc — `docs/DEMO-RUNBOOK.md`

~100 lines, checklist-formatted. Single page for a new user.

Sections:

1. **Prerequisites (10 min)** — AWS account with Bedrock access agreed for Sonnet 4.6 + Haiku 4.5 + Titan v2; Salesforce org; Anypoint trial; terminal with the 8 CLIs installed. Links to each.
2. **Clone and configure (5 min)** — `git clone`, `cp .env.example .env`, fill in vendor keys. Run `./scripts/0-preflight.sh` to auto-generate signing keys. Run `./scripts/1-validate-env.sh` to confirm every variable.
3. **One-time bootstrap (5 min)** — `./scripts/2-bootstrap.sh` (skips what's already there).
4. **Deploy (20-25 min, walk away)** — `./scripts/demo.sh fresh`.
5. **Warm up for demo (1 min)** — `./scripts/7-warm-start.sh`.
6. **Smoke test (3 min)** — `./scripts/6-verify.sh`.
7. **Open the four URLs** — research, advisor, advisor+alerts, client.
8. **Troubleshooting** — 6 known failure modes with fix commands:
   - `on-demand throughput isn't supported` → use inference profile id (the real bug from inventory)
   - `sf project deploy start` fails with `INVALID_FIELD` → upstream SF platform issue, retry
   - SAM `changeset empty` on second deploy → expected, `--no-fail-on-empty-changeset` handles
   - Aurora cold-start on first Aurora query → 90-second wait, one-time
   - `429 Too Many Requests` from Finnhub → throttle hit, back off 60s
   - Mulesoft `403 approval_required` → means the HITL token didn't propagate; check `HITL_SIGNING_KEY` is same on AgentCore + skill layer

---

## What I verified from the inventory that the current code needs changed

Three fixes to make reproducibility real, discovered by the inspection above. None are in scope for this plan to build; listed here so the deploy plan knows.

### Fix 1: Bedrock model id defaults must be inference profiles

`.env.example` currently says:
```
BEDROCK_SONNET_MODEL_ID=anthropic.claude-sonnet-4-6-20260215-v1:0
BEDROCK_HAIKU_MODEL_ID=anthropic.claude-haiku-4-5-20251022-v1:0
```

Both are **raw model ids** and will fail on-demand converse with `ValidationException`. Must become:
```
BEDROCK_SONNET_MODEL_ID=us.anthropic.claude-sonnet-4-6
BEDROCK_HAIKU_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
```

Confirmed by direct invoke during inventory — both profiles return successfully.

### Fix 2: `SF_TARGET_ORG=v3-demo-org` hardcoded default is wrong

`deploy-all.sh` sets `SF_TARGET_ORG:=v3-demo-org`. That org doesn't exist on a fresh machine. On the inspected machine, the connected orgs are `new-org` and an unaliased one. The default must either be:
- read from `sf org list` and pick the `🍁` default, or
- error with a clear message and ask the user to set `SF_TARGET_ORG` in `.env`.

### Fix 3: No retry on "Guardrail id not set" — fail earlier

Coordinator currently raises on start in production mode if guardrails env vars are missing. Good. But the error message doesn't say which two to set. Improve the message to include the exact `.env` var names.

---

## Scope and time estimate (for when you say "build it")

**Total: ~900 lines shell + ~300 lines Python + ~120 lines Apex + one 100-line runbook. 5-6 hours with two sub-agents running in parallel.**

| Script | Lines | Agent |
|---|---|---|
| 0-preflight.sh | 180 bash | Sub-agent A |
| 1-validate-env.sh | 140 bash+python | Sub-agent A |
| 2-bootstrap.sh | 120 bash | Sub-agent A |
| 3-seed-secrets.sh | (already built) | — |
| 4-deploy.sh | (already built; +50 lines for pre-step asserts) | Me |
| 5-seed-demo-data.sh | 140 bash + 120 Apex | Sub-agent B |
| 6-verify.sh | 200 python | Sub-agent B |
| 7-warm-start.sh | (already built) | — |
| 9-destroy.sh | 130 bash | Sub-agent A |
| demo.sh | 120 bash | Me |
| DEMO-RUNBOOK.md | 100 md | Me |
| Fix 1 (env-var defaults) | 2 line edit in .env.example | Me |
| Fix 2 (SF_TARGET_ORG auto-detect) | 15 line edit in 4-deploy.sh | Me |
| Fix 3 (guardrail error message) | 5 line edit in coordinator.py | Me |

Every script ends with a hermetic dry-run test in `tests/scripts/`. Real execution against AWS is gated on operator confirmation, same pattern as every other build wave.

---

## What this plan does NOT include

Honesty, for the doc record:

- **No multi-tenant isolation.** One-tenant scaffolding. If a second bank needed this, the `/006-v3/` prefix would need to become `/006-v3/${TENANT_ID}/` and every script would take a `--tenant` flag.
- **No CI pipeline.** `demo.sh fresh` works locally; wiring it into GitHub Actions to run nightly against a throwaway AWS sub-account is V4 scope.
- **No disaster-recovery runbook.** Aurora snapshots, Bedrock regional fallback, SF org restore. Mentioned in `v3-scalability-and-hooks-assessment.md` as V4+.
- **No per-developer env.** Every engineer running `demo.sh fresh` would step on each other in a shared AWS account. A per-developer env prefix (`/006-v3-${USER}/`) would need every script's SSM/Secrets path to template on `$USER`. Not in this plan; every engineer needs their own sub-account or the plan runs under an agreed `staging` prefix.

---

## Decision

I'll build this unless you change direction. Pattern: 3 sub-agents parallel, LLMJ review after, full verification pass, zero regression on the existing 236 backend + 43 frontend tests. I will **not** deploy anything to AWS — just ship the scripts, tests, runbook, and the three fixes above. You run `./scripts/demo.sh fresh` when you decide.
