# V3-B — Committed Architecture

> The MuleSoft org attached to this build is **Developer/Trial** tier
> (`subscription.category=Developer, type=Trial` in
> `agent-fabric/.entitlement-check.json`). Agent Fabric is not in that
> entitlement, so we ship V3-B: Flex Gateway in self-managed mode + the
> five policies + a single-choke-point Apex client + A2A manifests on
> Strands + a visualizer-ready frontend. V3-C (Agent Registry / Broker /
> Visualizer) is scaffolded alongside but on-hold. See
> `docs/v3-c-on-hold.md` for the hold list.

---

## What's live

### Flex Gateway on ECS (self-managed)

From `.gateway-deploy.json`:

- ECR image: `875460787302.dkr.ecr.us-east-1.amazonaws.com/ir-flex-gateway`
- ECS cluster / service: `ir-flex-gateway-cluster` / `ir-flex-gateway-svc`
- Task definition: `ir-flex-gateway-task:2` (Fargate 512 CPU / 1024 MB),
  re-registered as revision `:5` by `apply-flex-config.sh` with an S3
  config-sync init container.
- ALB: `http://ir-flex-gateway-alb-1565333524.us-east-1.elb.amazonaws.com`
  (recorded in `.gateway-url.txt`).
- Mode: `self-managed-static-config`. Flex reads its API instance and
  policy bindings from `s3://ir-flex-gateway-config-875460787302/v3-b/`
  via a `config-sync` init container that mounts
  `/etc/mulesoft/flex-gateway/conf.d/custom`.
- Credentials: ECS task pulls `client_id` / `client_secret` / `org_id` /
  `environment_id` from Secrets Manager `/006-v2/mulesoft/credentials`
  (same secret as 006 v2; do not fork).

### 3 policies applied via self-managed config bundle

In `agent-fabric/flex-config/`:

- `api.yaml` — one `ApiInstance` named `fsi-mcp-servers` that proxies
  the V2 API Gateway
  (`og256a1neb.execute-api.us-east-1.amazonaws.com/prod`) on port 8081
  with a wildcard route.
- `policy-rate-limit.yaml` — 25 req/sec burst 50, keyed by `x-agent-id`
  header, `clusterizable: true`.
- `policy-message-logging.yaml` — FINRA audit line per call:
  `FINRA_AUDIT | agent=... | tool=... | corr=... | path=... | status=...`.
- api-instance routing (via `api.yaml` upstream binding) — every inbound
  request at port 8081 is forwarded to the V2 upstream.

### 2 policies written but NOT currently applied

`agent-fabric/policies/mnpi-filter.yaml` and
`agent-fabric/policies/circuit-breaker.yaml` exist and are complete.
They are not in the `flex-config/` bundle because both reference a
registered API asset (for policy-reference resolution) in Anypoint API
Manager — the exact entitlement that Developer/Trial doesn't grant.
When V3-C is unlocked, copy them into `flex-config/` and re-run
`apply-flex-config.sh`.

### Apex — IR_FlexGatewayClient single choke point

From `.build-receipts/apex.json`:

- One class, `IR_FlexGatewayClient.cls`, owns every outbound HTTP
  `HttpRequest` to the gateway. All 5 invocable actions
  (`IR_MarketDataAction`, `IR_SecFilingsAction`, `IR_NewsSearchAction`,
  `IR_FinancialAnalysisAction`, `IR_SentimentAnalysisAction`) delegate
  to `callMcpTool(...)` or `callAgent(...)`.
- Every request carries `X-Correlation-Id`, `X-Agent-Id`, `X-Tool-Name`.
  Correlation ids are locked per logical call so retries share the same id.
- Tests: 16 / 16 pass, 96 % coverage on `IR_FlexGatewayClient`
  (threshold 75 %).
- `IR_MnpiGuard.cls` (V2) has been deleted — MNPI is a gateway policy
  once we re-enable that policy binding.
- Named Credential `IR_FlexGateway` + External Credential
  `IR_FlexGateway_EC` are the only gateway credentials. Endpoint is
  driven by the `FlexGatewayUrl` custom label (override per env).

### V3 Frontend with correlation + agent-id headers

From `.build-receipts/frontend.json`:

- `frontend/src/services/agentApi.ts` emits `X-Correlation-Id` (UUIDv4,
  session-scoped) and `X-Agent-Id` (default `ir-research-orchestrator`)
  on every gateway-bound call.
- 10 / 10 unit tests pass, lint + build clean.
- `scripts/build-and-deploy.sh` reads `.gateway-url.txt` and writes
  `frontend/.env.local` so the build picks up the ALB URL automatically.
- When `VITE_FLEX_GATEWAY_URL` is unset, the frontend silently falls
  back to the V2 direct API Gateway — the V2 rollback path always works.
- `AgentVisualizer.tsx` panel ships dark — it falls back to Langfuse and
  then to an empty stub until `VITE_ANYPOINT_VISUALIZER_API` is set
  (V3-C gating; see `docs/v3-c-on-hold.md`).

### Strands agents with A2A manifests

From `.build-receipts/strands.json`:

- Both Lambdas (`financial-analysis`, `sentiment-analysis`) serve
  `GET /.well-known/agent.json` returning a valid A2A v0.1.0 `AgentCard`.
- Both serve `POST /agent` as JSON-RPC 2.0 (`tasks/send` sync,
  `tasks/get` shell, `tasks/sendSubscribe` stubbed as `-32004`).
- 49 / 49 compliance tests pass.
- `scripts/register-strands-in-fabric.sh` is implemented but unused in
  V3-B — it writes a PENDING receipt when `ANYPOINT_AGENT_REGISTRY_URL`
  is unset. That's V3-C's job.
- All outbound MCP calls from Strands route through `FLEX_GATEWAY_URL`
  via `aws/shared/mcp_client.py`.

---

## What's on-hold pending Anypoint subscription upgrade

Blocked strictly by entitlement, not by code:

| Capability | Already-built artifact | Why it's off |
|---|---|---|
| Agent Registry push | `agent-fabric/agent-network.yaml`, `scripts/deploy-agent-network.sh` | Script gates on `agent_fabric=true` in entitlement check and writes `.registered-agents.json` with `status: skipped`. |
| Agent Broker routing | `agent-network.yaml :: routing.policies` | Broker is part of Agent Fabric — same gate. |
| Agent Visualizer | `frontend/src/services/visualizerApi.ts`, `frontend/src/components/AgentVisualizer.tsx` | Needs `VITE_ANYPOINT_VISUALIZER_API`; that URL only exists once the org has Agent Fabric. |
| MNPI policy enforcement | `agent-fabric/policies/mnpi-filter.yaml` | Policy references a custom Exchange asset; without a registered API instance the asset can't bind. |
| mTLS auth | `agent-fabric/policies/auth-mtls.yaml`, External Credential `IR_FlexGateway_EC` | Same asset-registration dependency. Cert distribution is also pending. The current fallback is `ApiKey` on the External Credential. |

Everything else either ships in V3-B or degrades silently to the V2 path.

---

## V2 → V3-B delta

- **Single Named Credential.** V2 used `AWS_IR_API` +
  `AWS_IR_API_Credential`. V3-B uses one `IR_FlexGateway` +
  `IR_FlexGateway_EC` pair. Endpoint is driven by the `FlexGatewayUrl`
  custom label (overridable per env).
- **`IR_MnpiGuard` deleted.** The Apex MNPI class is gone from V3-B (see
  `docs/v3-deleted-v2-code.md`). MNPI enforcement moves to
  `agent-fabric/policies/mnpi-filter.yaml` when that policy can bind
  (V3-C).
- **Correlation ID threading.** New in V3-B. `IR_FlexGatewayClient`
  stores a run-scoped correlation id, stamps it on every request, and
  reuses it across retries. The frontend emits the same header
  (`X-Correlation-Id`) so Langfuse and the (future) Agent Visualizer can
  join traces end to end.
- **FINRA audit at the gateway.** V2 wrote FINRA lines from Apex. V3-B
  writes them from the Flex Gateway `message-logging` policy binding,
  tagged with `x-agent-id`, `x-tool-name`, `x-correlation-id`. Apex no
  longer duplicates the audit.
- **Single HTTP choke point in Apex.** Only `IR_FlexGatewayClient`
  constructs `new HttpRequest()`; all 5 invocable actions delegate to
  `callMcpTool` / `callAgent`. This is grep-verifiable.
- **A2A manifests on Strands.** Both Strands Lambdas now advertise
  themselves per A2A v0.1.0. Nothing reads those manifests yet in V3-B;
  V3-C's Registry is what would consume them.

---

## Upgrade path to full V3-C

Three steps. No code changes.

1. **Upgrade the Anypoint subscription** to a tier that includes Agent
   Fabric. Today the org is `Developer / Trial`
   (`.entitlement-check.json :: subscription`); target is any tier where
   `entitlements` includes an Agent-Fabric flag.
2. **Re-run `scripts/verify-entitlement.sh`.** The current run exits `2`
   with `agent_fabric: false`; after the upgrade it will exit `0` with
   `agent_fabric: true` and write a new `.entitlement-check.json`.
3. **Re-run `scripts/deploy-agent-network.sh`.** Today it exits `0` but
   writes `.registered-agents.json` with `status: skipped`; after the
   upgrade it will push `agent-fabric/agent-network.yaml` to the Agent
   Registry via `anypoint-cli-v4 agent-fabric registry apply` (CLI
   fallback path: REST POST to
   `/agent-fabric/api/v1/.../agent-networks`).

At that point, also:

- Copy `agent-fabric/policies/mnpi-filter.yaml` and
  `circuit-breaker.yaml` into `agent-fabric/flex-config/` and re-run
  `scripts/apply-flex-config.sh` — the static bundle picks them up.
- Set `VITE_ANYPOINT_VISUALIZER_API` + `VITE_ANYPOINT_ORG_ID` in
  `frontend/.env.local` and re-run `scripts/build-and-deploy.sh` — the
  visualizer panel lights up automatically.

See `docs/v3-c-on-hold.md` for the per-artifact one-liners.

---

## Receipts that back this doc

- `agent-fabric/.entitlement-check.json` — `agent_fabric: false`,
  `flex_gateway: true`.
- `agent-fabric/.gateway-deploy.json` — ECR / ECS / ALB identifiers.
- `agent-fabric/.gateway-url.txt` — the ALB URL.
- `agent-fabric/.flex-config-applied.json` — task def `:5`, S3 bundle
  `s3://ir-flex-gateway-config-875460787302/v3-b/`.
- `agent-fabric/.registered-agents.json` — `status: skipped`, reason:
  Developer/Trial.
- `agent-fabric/.registered-apis.json` — `policies_applied: 0` via the
  CLI path (policies apply through the self-managed bundle instead).
- `agent-fabric/.build-receipts/*.json` — per-subagent acceptance tests.
- `docs/v3-gateway-runbook.md` — operations: health checks, rotation,
  rollback, full troubleshoot FAQ.
