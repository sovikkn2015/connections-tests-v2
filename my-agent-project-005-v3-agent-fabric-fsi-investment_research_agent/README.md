# Project 005 V3-B committed; V3-C scaffolded

Builds on V2 (Agentforce + Strands + AWS). V3-B adds a MuleSoft Flex
Gateway (self-managed on ECS) + policies + single-choke-point Apex +
A2A manifests on Strands + visualizer-ready frontend. V3-C (Agent
Registry / Broker / Visualizer) is scaffolded but inactive until the
Anypoint subscription upgrades past Developer/Trial.

## Status

- **V3-B live:** Flex Gateway on ECS, 3 policies via self-managed
  config, single `IR_FlexGatewayClient` Apex choke point, frontend
  emitting `X-Correlation-Id` + `X-Agent-Id`, Strands A2A endpoints.
- **V3-C on-hold:** Agent Registry push, Broker routing, Visualizer
  live data, MNPI + mTLS policy binding.
- **Receipts:** `agent-fabric/.build-receipts/*.json`,
  `agent-fabric/.entitlement-check.json`,
  `agent-fabric/.gateway-deploy.json`,
  `agent-fabric/.flex-config-applied.json`.
- **Read first:** `docs/v3-b-architecture.md` (what's live),
  `docs/v3-c-on-hold.md` (what's scaffolded), `docs/GO-LIVE.md`
  (operator checklist), `docs/v3-gateway-runbook.md` (ops + FAQ).

## What's New in V3

- **Agent Registry** — all 7 components (2 Agentforce agents, 2 Strands agents, 3 MCP servers) registered and discoverable
- **Agent Broker** — policy-enforced routing replaces hardcoded Apex wiring
- **Flex Gateway** — MCP/A2A-aware gateway with MNPI filtering, rate limiting, circuit breakers, FINRA audit logging
- **Agent Visualizer** — real-time cross-platform interaction map

## Prerequisites

Everything from V2, plus:
- MuleSoft Anypoint Platform license with Agent Fabric
- Flex Gateway deployed on AWS (ECS recommended)
- Anypoint Code Builder

## Project Structure

```
agent-fabric/                    # NEW — Agent Fabric configs
  agent-network.yaml             # Agent network definition (YAML-first)
  policies/
    mnpi-filter.yaml             # MNPI content filter policy
    rate-limit.yaml              # Per-agent rate limiting
    circuit-breaker.yaml         # Circuit breaker per MCP server
    finra-audit.yaml             # FINRA audit logging at gateway
    auth-mtls.yaml               # mTLS authentication
force-app/                       # Salesforce metadata (from V2)
aws/                             # Lambda MCP servers + Strands agents (from V2)
frontend/                        # React frontend (from V2)
scripts/                         # Deploy scripts (from V2)
docs/                            # Architecture docs
```

## Deploy

### 1. Deploy V2 components (unchanged)
```bash
# Salesforce
sf project deploy start --source-dir force-app
sf apex run --file scripts/apex/grant-fls.apex
sf apex run --file scripts/apex/seed-data.apex

# AWS
cd aws && sam build && sam deploy --guided
```

### 2. Deploy Flex Gateway
```bash
# Pull and run Flex Gateway container
docker pull mulesoft/flex-gateway:latest
# Register with Anypoint Platform (requires Anypoint credentials)
flexctl register --organization=$ANYPOINT_ORG --token=$ANYPOINT_TOKEN
```

### 3. Apply Agent Fabric configs
```bash
# In Anypoint Code Builder:
# 1. Open agent-fabric/agent-network.yaml
# 2. Command Palette → "MuleSoft: Deploy Agent Network"
# 3. Verify in Anypoint Platform → Agent Registry
```

### 4. Apply Flex Gateway policies
```bash
# Policies are applied via Anypoint Platform API Manager
# or via Anypoint CLI:
anypoint-cli api-mgr policy apply --config agent-fabric/policies/mnpi-filter.yaml
anypoint-cli api-mgr policy apply --config agent-fabric/policies/rate-limit.yaml
anypoint-cli api-mgr policy apply --config agent-fabric/policies/circuit-breaker.yaml
anypoint-cli api-mgr policy apply --config agent-fabric/policies/finra-audit.yaml
anypoint-cli api-mgr policy apply --config agent-fabric/policies/auth-mtls.yaml
```

## Architecture

See `docs/005-v3-agent-fabric-architecture.md` in the root docs/ folder for the full ASCII architecture diagram, V2→V3 comparison, and Flex Gateway explainer.
