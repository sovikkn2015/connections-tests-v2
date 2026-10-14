# V3-C — On-Hold Artifacts

V3-C = Agent Fabric Registry + Broker + Visualizer.
This scope is blocked by the Anypoint Developer/Trial tier
(`agent-fabric/.entitlement-check.json :: agent_fabric=false`), not by
code. The artifacts below are built and tested — they're just inactive.
Once the subscription is upgraded and `scripts/verify-entitlement.sh`
returns `agent_fabric=true`, run the one-line command next to each
artifact to flip it on.

## 1. Agent Network definition

File: `agent-fabric/agent-network.yaml`
Contents: 4 agents (2 Agentforce, 2 Strands), 3 MCP servers, 3 routing
policies (`l1-l2-direct-tools`, `l3-l4-analysis`, `compliance-routing`),
5 governance policy `$ref`s into `agent-fabric/policies/`.

Activate with:
```bash
bash scripts/deploy-agent-network.sh
```

Currently this script gates on `agent_fabric=true` and writes
`agent-fabric/.registered-agents.json` with `status: skipped, path:
B-fallback`. After the subscription upgrade it will push via
`anypoint-cli-v4 agent-fabric registry apply -f agent-fabric/agent-network.yaml`
(CLI-missing fallback: REST `POST
/agent-fabric/api/v1/organizations/{org}/environments/{env}/agent-networks`)
and rewrite the receipt with the registered agent ids.

## 2. A2A manifests on Strands Lambdas

Files: `aws/strands-agents/financial-analysis/a2a_manifest.py`,
`aws/strands-agents/sentiment-analysis/a2a_manifest.py`,
`aws/strands-agents/*/a2a_handler.py`.

These are **already live** at
`/<agent>/.well-known/agent.json` on the deployed API Gateway (see
`.build-receipts/strands.json` — 49 / 49 A2A compliance tests pass).
Nothing in V3-B reads them. V3-C's Registry is what will consume them.

Activate registration with:
```bash
ANYPOINT_ORG_ID=... ANYPOINT_ACCESS_TOKEN=... \
  bash aws/scripts/register-strands-in-fabric.sh --stack ir-research-v3
```

The script is idempotent: on HTTP 409 (already registered) it `PATCH`es
the existing entry. Until it's run, `register-strands-in-fabric.sh`
exits `2` and writes a PENDING receipt at
`agent-fabric/.build-receipts/strands-registration.json`.

## 3. Agent Visualizer panel

Files: `frontend/src/components/AgentVisualizer.tsx`,
`frontend/src/components/AgentVisualizerPanel.css`,
`frontend/src/services/visualizerApi.ts`.

The panel is in the build already — it's wired into
`Layout.tsx :: rightPanelView`. Today it falls back through Anypoint →
Langfuse → empty stub (all three paths tested in
`visualizerApi.test.ts`).

Activate with:
```bash
# 1. add to frontend/.env.local (or export for CI):
VITE_ANYPOINT_VISUALIZER_API=<from Agent Fabric UI>
VITE_ANYPOINT_ORG_ID=<from .registered-agents.json after C-upgrade>

# 2. rebuild
bash scripts/build-and-deploy.sh ir-research-v3
```

`scripts/build-and-deploy.sh` already reads both fields from
`agent-fabric/.registered-agents.json` when they exist — the upgrade
will backfill them automatically.

## 4. MNPI and circuit-breaker policies

Files: `agent-fabric/policies/mnpi-filter.yaml`,
`agent-fabric/policies/circuit-breaker.yaml`.

Both are complete YAML policy bindings. They are **not** in
`agent-fabric/flex-config/` today because each references a policy asset
that needs a registered API instance in Anypoint API Manager — which
needs an Exchange-published API asset, which needs an Anypoint tier
above Developer/Trial.

Activate with (once V3-C entitlement is live):
```bash
cp agent-fabric/policies/mnpi-filter.yaml     agent-fabric/flex-config/
cp agent-fabric/policies/circuit-breaker.yaml agent-fabric/flex-config/
bash scripts/apply-flex-config.sh
```

The self-managed static-config bundle picks them up and binds them to
the `fsi-mcp-servers` `ApiInstance` on the next ECS task roll.

## On the `--mode local` vs `--mode connected` distinction

Flex Gateway has two registration modes:

- **`--mode local`** (what V3-B runs): the gateway reads its whole
  configuration from local files (the S3-synced `flex-config/` bundle).
  It does not need Anypoint API Manager to resolve policy assets at
  runtime. The tradeoff is no auto-discovery: every new API instance
  and policy binding is a hand edit to YAML + a redeploy of the config
  bundle.
- **`--mode connected`** (what V3-C would use): the gateway pulls API
  instances and policy bindings from Anypoint API Manager at runtime,
  and all 5 policies in `agent-fabric/policies/` bind automatically via
  the registration that `scripts/deploy-agent-network.sh` performs. No
  local YAML bundle needed.

V3-B's local-mode choice is what lets Developer/Trial ship a working
gateway today. V3-C's connected-mode promotion is the reward for the
subscription upgrade — Registry, Broker, and Visualizer auto-wire from
the registration, no `scripts/apply-flex-config.sh` required.

## Receipts that confirm the on-hold state

- `agent-fabric/.entitlement-check.json` — `agent_fabric: false`.
- `agent-fabric/.registered-agents.json` — `status: skipped`.
- `agent-fabric/.registered-apis.json` — empty `policies` array.
- `agent-fabric/.build-receipts/strands.json :: pending` — lists the
  missing `FlexGatewayUrl`, `ANYPOINT_AGENT_REGISTRY_URL`, and
  `ANYPOINT_ACCESS_TOKEN` blockers.
- `agent-fabric/.build-receipts/frontend.json :: notes` — confirms the
  visualizer path falls back silently without the C-scope envs.
