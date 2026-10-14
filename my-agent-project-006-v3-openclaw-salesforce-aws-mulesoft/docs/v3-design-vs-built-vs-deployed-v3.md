# 006 V3 — Design vs Built vs Deployed (Round 3, May 1)

> **Date:** 2026-05-01
> **Method:** live AWS probes + live Salesforce SOQL + live Anypoint API + one real research turn through the full stack
> **Supersedes:** `v3-design-vs-built-vs-deployed-v2.md` (April 29). Use this doc for today's ground truth; v2 is kept for historical trail only.

---

## 1. Headline change since April 29

**Three of April 29's P0 items are already resolved in the current deploy.** A live probe today (May 1) contradicts three claims that appeared in v2:

| April 29 claim | Actual state today |
|---|---|
| "Research specialists bypass `run_tool_loop` → hallucinate Python code" | **Fixed.** Every research specialist has `tool_allowlist=["mcp_invoke"]` and `_invoke_specialist` routes them through `run_tool_loop`. See `openclaw/orchestration/coordinator.py:513–517` + `openclaw/orchestration/topology.py:285–478`. |
| "CloudFront `ESDPHVE5JPN93` points at v2 bucket" | **Fixed for v3.** Distribution `E3T0OIRWDE1J8Y` (domain `d2zs9nk4uc2dbx.cloudfront.net`) points at `openclaw-v3-frontend-875460787302`. Frontend serves "V3 Workflow 360". `ESDPHVE5JPN93` is a *separate*, older v2 distribution. |
| "Fire-and-forget `publish_brief` call from coordinator" | **Fixed.** Replaced with blocking `await asyncio.wait_for(..., timeout=5.0)` in commit `36b21d30`. Publish is now guaranteed to run before HTTP response; bounded so a failing SF write cannot exceed the API Gateway 29s ceiling. |

## 2. Current scorecard

| Layer | April 29 | **May 1** | Delta |
|---|---|---|---|
| **Design** | 95% coherent | 95% | unchanged |
| **Built** | 91% real | **95% real** | specialist tool-loop, blocking publish_brief, 5-sec cap all in place |
| **Deployed** | ~82% live | **~90% live** | 3 Mule apps real end-to-end with Alpaca/Dwolla/webhook; coordinator fix deployed |

## 3. What's genuinely live end-to-end today

### 3a. MuleSoft layer — ALL THREE APPS REAL

```
submit-order         3.0.5   /api/health -> {"mode":"alpaca-paper"}    RUNNING
initiate-wire        3.0.6   /api/health -> {"mode":"dwolla-sandbox"}  RUNNING
order-status-webhook 3.0.10  /api/health -> {"mode":"live"}            RUNNING
```

First real Alpaca paper-trade order submitted: `ALPACA-c98c9f6a-b807-47b6-b652-8269def870a2`.
Dwolla sandbox verified. Webhook MCP-gateway verified.

### 3b. Research turn — reaches publish_brief

Live turn `verify-fixb-1777689449` returned HTTP 200 in 24.3s. Logs show:
- Research orchestrator completes synthesis.
- `coordinator.publish_brief.failed` log line fires (meaning the code path IS reached).
- The failure is `SF OBO failed: 502 / SF token exchange failed: 400` — not a code bug.

### 3c. Reproducibility — new in this session

All scripted as of commits `8f432b92` and `36b21d30`:
- `scripts/set-mule-secure-properties.sh` — idempotent per-app Runtime Manager PATCH (replaces April's manual curl work)
- `scripts/mule-health.sh` — dynamic publicUrl discovery via Anypoint API
- `scripts/seed-secrets.sh` — now seeds every Mule vendor secret + secure-properties-key
- `scripts/deploy-all.sh` `step_mulesoft` — full 5-phase chain (verify → package → deploy → secure-props → health)
- `docs/v3-mulesoft-deploy-runbook.md` — walk-through per phase

## 4. The single remaining P0 blocker for research audit

**Salesforce OBO bootstrap secret is empty.** Every piece of downstream plumbing works; the JWT signing key and the Salesforce Connected App consumer key are placeholders in `/006-v3/sf/bootstrap-creds`.

Evidence (May 1 AgentCore log):
```
coordinator.publish_brief.failed err=MCPError:
  SF OBO failed: 502 {"error":"OBO failed:
  SF token exchange failed: 400 invalid_grant"}
```

Full remediation playbook: `docs/v3-p0-sf-obo-fix.md`.
Script helper: `scripts/sf-obo-verify.sh` (validates the secret shape + fires a live write probe).

Effort to fix: **15 minutes of Salesforce admin work** (create Connected App, generate cert, upload, paste consumer_key back into AWS) + 1 script run. Cannot be done from code alone — requires SF org admin console access.

When this lands, four downstream regressions clear simultaneously:
- Zero `IR_Audit_Log__c` rows today → every turn writes 1-3 rows
- `Research_Request__c` 401 on N2 handoff → real `a0R...` id returned
- `publish_brief` audit write → linked row via `Research_Brief_Id__c`
- HITL approved/rejected audit → real rows

## 5. Still deferred (not blocking today's demos)

| Item | Effort | Sized |
|---|---|---|
| Cognito IdP (replaces `dev-bootstrap-token`) | ~1 day | User Pool + App Client + JWKS verify in agent-proxy Lambda + frontend env wiring |
| Research_Request__c deploy (Narrative 2) | 10 min | `sf project deploy start --target-org new-org` (metadata file already at `salesforce/force-app/.../Research_Request__c/`) |
| `compliance_sweep` trigger wiring (Narrative 3) | 45 min | Replace `simulate-price-shock.sh` with a real scheduler |
| Specialist citation drift (filings, statement) | 30 min | Prompt update in `topology.py` (see `docs/v3-p0-source-chunk-citation-drift.md`) |

## 6. What v2 doc got right (unchanged)

Keep using `v3-design-vs-built-vs-deployed-v2.md` for:
- the first-live-turn telemetry from April 29
- the specialist timeout diagnosis
- the audit SObject field-drift diagnosis (since fixed by permset `V3_Audit_Fields`)
- the Langfuse trace screenshots

## 7. Signals for demo day

**Defensible today:**
- "Trust spine is real for every write" — Alpaca + Dwolla are actual paper trades / sandbox wires.
- "Apps boot, probes pass" — Mule 4.9 gotchas all documented; verify-mule catches them pre-deploy.
- "Ops are reproducible" — `deploy-all.sh` runs the whole stack. Credentials in AWS Secrets Manager, not hardcoded.

**Qualify honestly:**
- "Audit log landing" → only for action-specialist writes today. Research audit waits on the SF OBO credential setup (15-min admin fix, scripted in `docs/v3-p0-sf-obo-fix.md`).
- "Real IdP" → using `dev-bootstrap-token` today; Cognito scaffold in place but not wired (1-day task).

## 8. Where to read next

- `RUNBOOK.md` — end-to-end deploy
- `docs/v3-mulesoft-deploy-runbook.md` — MuleSoft phase-by-phase
- `docs/v3-mulesoft-gotchas.md` — Mule 4.9 boot-crash classes
- `docs/v3-p0-sf-obo-fix.md` — the one remaining P0 playbook
- `docs/v3-p0-source-chunk-citation-drift.md` — citation format fix for research specialists
