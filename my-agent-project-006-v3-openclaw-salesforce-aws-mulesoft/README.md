# 006 V3 — OpenClaw + Salesforce + AWS + MuleSoft

> **FSI Wealth Platform** — Analyst · RM · Client — one runtime, one system of record, one audit trail.

## What this is

V3 is a multi-agent wealth-research-and-trading platform built on OpenClaw (Bedrock AgentCore) with three personas (`fsi_research`, `fsi_advisor`, `fsi_client_liaison`), 14 specialist sub-agents, 14 skills (including a generic `mcp_invoke`), and a Salesforce-native data layer with MuleSoft for regulated writes.

The read-path fans out via `asyncio.gather`. The write path runs a serial 7-gate trust spine (Guardrails → MNPI → compliance → HITL → dual-auth → MuleSoft → audit).

See:
- `docs/v3-narrative-arc.md` — architecture + depth layer + 5 narratives
- `docs/v3-demo-choreography.md` — live demo plan
- `docs/v3-design-vs-built-vs-deployed-v2.md` — honest scoreboard vs design
- `docs/_deploy_assessment/` — live post-deploy findings

## Folder structure

```
openclaw/       agent platform: coordinator, 3 orchestrators, 11 specialists,
                14 skills, trust layer, tool dispatch, agent-core HTTP server
aws/
  cdk/          6 CDK stacks (Vpc, Aurora, Kb, Risk-Alerts, Filings/ResearchPipeline)
  mcp-servers/  7 Lambdas: market-data, sec-edgar, news-search, salesforce-crm,
                mulesoft-actions, bff, sf-auth-proxy, agent-proxy (browser bridge)
  data-pipelines/ Bedrock KB + Aurora pgvector ingest
  sam-template.yaml 33-resource SAM stack with API Gateway + 7 Lambdas
mulesoft/       3 Process APIs (submit-order, initiate-wire, order-status-webhook)
salesforce/     SObjects, Apex, permsets incl. V3_Audit_Fields and V3_Brief_Fields
frontend/       React + SLDS + Zustand: Sarah's terminal, RM advisor screen,
                client liaison channel, TraversalMap, SevenGateTracker
scripts/        deploy-all.sh (orchestration),
                seed-secrets.sh, create-v3-agentcore.sh,
                deploy-frontend-cloudfront.sh,
                bootstrap-kb-oos.py, seed-kb-chunks.py,
                download-real-filings.py, seed-aurora-schema.sh,
                seed-demo-rows.sh
tests/          backend unit + integration + frontend vitest
docs/           narrative arc, demo choreography, assessments
```

## Deployment

**See [`RUNBOOK.md`](./RUNBOOK.md) for the authoritative deployment guide.**

The RUNBOOK covers:

- Section 1 — Prerequisites (local tools, external accounts, credential gathering)
- Section 2 — Preflight validation (`bash scripts/0-preflight.sh`)
- Section 3 — One-command deploy (`bash scripts/deploy-all.sh`) with wave-by-wave timing and cost estimates
- Section 4 — Verification (`bash scripts/smoke-test.sh`) + per-narrative test commands
- Section 5 — Troubleshooting — every known failure mode with exact remediation commands
- Section 6 — Clean teardown (`bash scripts/9-destroy.sh`)
- Section 7 — Quick reference card

Estimated time for a new user with all credentials ready: **90 minutes** of hands-on work.

## Deployment fingerprint

- All source code committed to git on branch `feat/006-v3-live-demo`
- Zero credentials in git; all secrets live in AWS SSM (`/006-v3/*`) and Secrets Manager
- `.env.example` enumerates every required env var (34 values)
- `scripts/deploy-all.sh` is the single-entry orchestrator — every sub-script is idempotent
- `scripts/0-preflight.sh` validates all prereqs before touching AWS
- `scripts/9-destroy.sh` provides clean teardown when you're done
- Post-deploy state snapshots captured in `docs/_deploy_assessment/`

## Known gaps as of the latest live deploy

See `docs/_deploy_assessment/REVIEWER_FIXES_APPLIED.md` and
`docs/v3-design-vs-deployment-deviation.md` for the honest scoreboard. Short list:

1. **Okta/Cognito IdP handshake** not wired; SPA uses `dev-bootstrap-token`. Enterprise IdP wires via `IDP_ISSUER` + `IDP_CLIENT_ID` env vars — not productionized.
2. **Salesforce Connected App consumer_key/secret** in Secrets Manager are placeholders for a fresh org. Must be replaced before the SF OBO chain produces real per-user JWTs. Without this, the `salesforce-crm` MCP falls back to degraded audit mode (writes succeed, but token exchange fails silently).
3. **MuleSoft CloudHub secure properties** (Alpaca paper key, Dwolla sandbox key) must be set in Anypoint Runtime Manager UI after `mvn deploy`. Maven deploy publishes the JAR; CloudHub app boot needs the property file.
4. **API Gateway 29-second REST timeout** caps per-turn latency. The agent-proxy Lambda is sized for 5 minutes but the browser path is REST. For deep-fanout turns, switch the frontend transport env var `VITE_AGENT_TRANSPORT=ws` once a WebSocket gateway is wired.
5. **Salesforce FieldDefinition metadata cache** can lag up to ~15 min after a field deploy; if `describe` doesn't show a field you just pushed, wait or refresh the tooling API cache.

## What's real and defensible

- Real Bedrock Sonnet 4.5 turns via AgentCore (`openclaw_v3_agent-o72dx396I0`)
- Real Finnhub live quotes (NVDA $211.27 verified in-turn)
- Real Bedrock KB with 784 chunks from 10 real SEC filings (Titan v2 embeddings)
- Real SF per-user OBO (sf-auth-proxy Lambda)
- Real 3-specialist parallel fanout via `asyncio.gather`
- Real tool-use dispatch with `mcp_invoke` binding — specialists emit Bedrock `toolUse` blocks that invoke Lambda MCPs
- Real 7-gate trust-spine code for the action_specialist write path
- SevenGateTracker animates via post-hoc `gate_trace` replay in `useStreamingTurn`
