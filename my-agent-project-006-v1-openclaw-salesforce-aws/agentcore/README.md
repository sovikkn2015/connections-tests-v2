# OpenClaw on AWS Bedrock AgentCore

## Architecture

```
AgentCore ──POST /invocations──▶ adapter.js (:8080)
                                     │
                                     ├─▶ POST /v1/chat/completions  (primary — synchronous)
                                     └─▶ POST /hooks/agent          (fallback — async)
                                     │
                                     ▼
                            OpenClaw Gateway (:18789)
                              REST API (HTTP)
```

The adapter bridges AgentCore HTTP to OpenClaw Gateway's REST API — no WebSocket.
The gateway's WebSocket handshake rejects Node.js `ws` library connections (`code=1008`),
so we use the documented REST endpoints instead.

## Files

| File | Purpose |
|------|---------|
| `adapter.js` | HTTP adapter: Express on :8080, calls gateway REST on :18789 |
| `adapter-package.json` | Dependencies: express only (no ws) |
| `Dockerfile` | Container: `public.ecr.aws` node:22-slim + OpenClaw + adapter |
| `start.sh` | Entrypoint: launches gateway (background) + adapter (foreground) |
| `openclaw.json` | OpenClaw config (copied from `../openclaw/` at build time) |
| `mcp-rest-bridge.mjs` | MCP stdio-to-HTTP bridge (copied at build time) |
| `.bedrock_agentcore.yaml` | AgentCore SDK deployment state |
| `agentcore-config.yaml` | Deployment config reference (secrets from Secrets Manager) |
| `docker-compose.yml` | Local testing only |

## Deployed Agent

| Resource | Value |
|----------|-------|
| Agent Name | `fsi_research_agent` |
| Agent ID | `fsi_research_agent-Sr1m3j3MUh` |
| Agent ARN | `arn:aws:bedrock-agentcore:us-east-1:875460787302:runtime/fsi_research_agent-Sr1m3j3MUh` |
| ECR Repo | `875460787302.dkr.ecr.us-east-1.amazonaws.com/openclaw-agentcore` |
| Region | us-east-1 |
| Model | `us.anthropic.claude-sonnet-4-6` (Bedrock) |

## Deploy (Reproducible)

```bash
cd agentcore

# 1. Copy OpenClaw config into build context
cp ../openclaw/openclaw.json ./openclaw.json
cp ../openclaw/mcp-rest-bridge.mjs ./mcp-rest-bridge.mjs 2>/dev/null || \
  cp ../mcp-rest-bridge.mjs ./mcp-rest-bridge.mjs

# 2. Generate tokens
GW_TOKEN=$(openssl rand -hex 32)
HOOKS_TOKEN=$(openssl rand -hex 32)

# 3. Deploy via CodeBuild (cloud build, no local Docker needed)
agentcore deploy \
  --auto-update-on-conflict \
  -env "OPENCLAW_GATEWAY_TOKEN=${GW_TOKEN}" \
  -env "OPENCLAW_HOOKS_TOKEN=${HOOKS_TOKEN}"

# 4. Wait ~90s for cold start, then invoke
sleep 90
agentcore invoke \
  '{"prompt": "Who covers NVIDIA?", "action": "chat", "userId": "test", "actorId": "test:1"}' \
  -a fsi_research_agent
```

Expected response: `{"ok":true,"runId":"..."}` (async via hooks endpoint).

## Environment Variables

| Variable | Source | Used By |
|----------|--------|---------|
| `OPENCLAW_GATEWAY_TOKEN` | Generated at deploy | Gateway auth + adapter auth for `/v1/chat/completions` |
| `OPENCLAW_HOOKS_TOKEN` | Generated at deploy | Adapter auth for `/hooks/agent` (must differ from gateway token) |
| `SF_INSTANCE_URL` | Secrets Manager | OpenClaw → Salesforce CRM |
| `SF_ACCESS_TOKEN` | Secrets Manager | OpenClaw → Salesforce CRM |
| `MCP_GATEWAY_URL` | Secrets Manager | OpenClaw → Lambda MCP servers |
| `MCP_API_KEY` | Secrets Manager | OpenClaw → Lambda MCP servers |
| `LANGFUSE_*` | Secrets Manager | Observability |
| `ALPHA_VANTAGE_API_KEY` | Secrets Manager | Market Data MCP |
| `TAVILY_API_KEY` | Secrets Manager | News Search MCP |

## Key Design Decisions

1. **REST over WebSocket**: The gateway's WS handshake rejects Node.js `ws` connections.
   REST endpoints (`/v1/chat/completions`, `/hooks/agent`) work reliably.

2. **Separate hooks token**: OpenClaw requires `hooks.token != gateway.auth.token`.
   Both are generated at deploy time and injected via `-env`.

3. **No wait loop in start.sh**: The adapter starts immediately and polls gateway health
   internally. This keeps total startup under 25s (well within AgentCore's 120s limit).

4. **ECR Public base image**: `public.ecr.aws/docker/library/node:22-slim` avoids
   Docker Hub unauthenticated pull rate limits on CodeBuild.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Runtime initialization time exceeded` | start.sh wait loop too long | Remove wait loop, let adapter poll internally |
| `hooks.token must not match gateway auth token` | Same token for both | Use separate `OPENCLAW_HOOKS_TOKEN` |
| `sessionKey is disabled for external /hooks/agent` | Missing config | Add `"allowRequestSessionKey": true` to hooks config |
| `/v1/chat/completions` returns 404 | Endpoint may not be enabled | Use `/hooks/agent` as primary (it works) |
| Docker Hub 429 rate limit on CodeBuild | Too many unauthenticated pulls | Use `public.ecr.aws` base image |
| `invalid request frame` on WebSocket | Node.js ws library incompatible | Use REST endpoints instead |

## CloudWatch Logs

```bash
# Runtime logs
aws logs tail \
  /aws/bedrock-agentcore/runtimes/fsi_research_agent-Sr1m3j3MUh-DEFAULT \
  --log-stream-name-prefix "$(date -u +%Y/%m/%d)/[runtime-logs]" \
  --follow
```
