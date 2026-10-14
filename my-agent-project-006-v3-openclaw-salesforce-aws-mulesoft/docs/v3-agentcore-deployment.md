# 006 V3 — How OpenClaw Is Deployed in AgentCore Runtime

> **Purpose:** explain, concretely, how the 14 OpenClaw agents live inside a Bedrock AgentCore runtime. Where they run, how they get invoked, what memory they have access to, how a single container hosts all 14.
>
> **Audience:** anyone trying to understand the runtime layout, redeploy it, debug it, or explain it on stage.
>
> **Source material:** live `aws bedrock-agentcore-control get-agent-runtime` probes, the Docker image in ECR, `openclaw/orchestration/topology.py`, `openclaw/agentcore_server.py`, and the architecture design in `docs/v3-narrative-arc.md`.

---

## 1. TL;DR — one runtime, all 14 agents

```
AgentCore Runtime "openclaw_v3_agent"
  └─ 1 Docker container (openclaw-agentcore:v3-latest)
       └─ Python 3.11 process
            └─ 14 AgentDefinition Pydantic records in topology.py
                 ├─ 3 orchestrators (research, advisor, liaison)
                 └─ 11 specialists (market, filings, sentiment, compliance,
                    statement, portfolio, suitability, client_context,
                    action, faq, liaison_context)
```

The 14 agents are **not** 14 separate runtimes or 14 separate containers. They are 14 logical personalities in a single Python process. The AgentCore runtime is ONE container. The container picks which agent definition to use per turn based on the incoming persona.

This is by design — chosen in `v3-narrative-arc.md` §"Where V3 Runs":

> "Single deployment, two persona configs. Same Docker image, same AgentCore agent ID, two entry configs in `agentcore-config.yaml`. Persona selected at session-open time by an `X-Persona` header set by the channel adapter. Nothing forks at the container layer."

---

## 2. The live runtime — verified by probe

Running `aws bedrock-agentcore-control get-agent-runtime` against the production v3 runtime returns:

```json
{
  "agentRuntimeArn":      "arn:aws:bedrock-agentcore:us-east-1:875460787302:runtime/openclaw_v3_agent-o72dx396I0",
  "agentRuntimeName":     "openclaw_v3_agent",
  "agentRuntimeId":       "openclaw_v3_agent-o72dx396I0",
  "agentRuntimeVersion":  "16",
  "status":               "READY",

  "containerConfiguration": {
    "containerUri": "875460787302.dkr.ecr.us-east-1.amazonaws.com/openclaw-agentcore:v3-latest"
  },

  "protocolConfiguration": {
    "serverProtocol": "HTTP"
  },

  "networkConfiguration": {
    "networkMode": "PUBLIC"
  },

  "lifecycleConfiguration": {
    "idleRuntimeSessionTimeout": 900,
    "maxLifetime": 28800
  },

  "workloadIdentityDetails": {
    "workloadIdentityArn": "arn:aws:bedrock-agentcore:us-east-1:875460787302:workload-identity-directory/default/workload-identity/openclaw_v3_agent-o72dx396I0"
  },

  "roleArn": "arn:aws:iam::875460787302:role/AmazonBedrockAgentCoreSDKRuntime-us-east-1-a63986f981",

  "metadataConfiguration": {
    "requireMMDSV2": true
  }
}
```

### Facts from this probe

| Fact | Value |
|---|---|
| **Runtime count** | 1 (not 14) |
| **Runtime version** | 16 (16 deploys during v3 dev cycle) |
| **Container image** | `openclaw-agentcore:v3-latest` in account ECR |
| **Protocol** | HTTP (POST requests with a JSON body) |
| **Network** | PUBLIC (no VPC — the runtime reaches out to API Gateway + Bedrock) |
| **Session idle timeout** | 900 sec (15 minutes) |
| **Max session lifetime** | 28800 sec (8 hours) |
| **IAM role** | `AmazonBedrockAgentCoreSDKRuntime-us-east-1-...` — boto3-managed |
| **Workload identity** | Issued by AgentCore's workload-identity-directory |
| **MMDSv2** | Required (Instance Metadata Service v2, security best practice) |

The runtime is a **Fargate-equivalent managed by AWS**. We don't see the underlying ECS/EKS; we just see the runtime abstraction.

---

## 3. What's inside the container

The `openclaw-agentcore:v3-latest` Docker image is built by `scripts/create-v3-agentcore.sh` and pushed to ECR. Its contents:

```
Base image:   python:3.11-slim

/app/
  ├── requirements.txt         # langfuse, boto3, pydantic, httpx, openai, structlog
  └── openclaw/
       ├── __init__.py
       ├── coordinator.py                   # thin shim for AgentCore entry
       ├── agentcore_server.py              # HTTP listener AgentCore invokes
       ├── openclaw.json                    # platform config
       │
       ├── orchestration/
       │    ├── coordinator.py              # PersonaCoordinator, _run_one, _invoke_specialist
       │    ├── tool_dispatch.py            # run_tool_loop — Bedrock tool-use binding
       │    ├── topology.py                 # 14 AgentDefinition records (source of truth)
       │    ├── messages.py                 # Pydantic: SessionContext, OrchestratorDispatch, WorkerResponse
       │    ├── research_orchestrator.py    # 5-way fanout planner/synthesizer
       │    ├── advisor_orchestrator.py     # intent-classified read vs serial write
       │    └── liaison_orchestrator.py     # FAQ vs rm-handoff decision
       │
       ├── skills/                           # 14 skills (Python modules, each is a tool the agent can call)
       │    ├── _mcp_client.py              # HTTP client to MCP API Gateway
       │    ├── _registry.py                # _SKILL_MODULES list
       │    ├── publish_brief/
       │    ├── rag_retrieve/
       │    ├── financial_statement_analysis/
       │    ├── portfolio_analytics/
       │    ├── scenario_modeling/
       │    ├── suitability_check/
       │    ├── client_summary/
       │    ├── research_awareness/
       │    ├── compliance_screening/
       │    ├── compliance_sweep/
       │    ├── hitl/                       # HMAC token mint + verify
       │    ├── dual_auth/
       │    ├── mulesoft_api/               # writes OFAC screening + MuleSoft invocation
       │    ├── audit_logging/              # writes IR_Audit_Log__c
       │    ├── rm_handoff/                 # writes Client_Inquiry__c
       │    └── mcp_invoke/                 # generic MCP proxy — specialists call MCPs through this
       │
       └── trust/
            ├── gate_enforcer.py            # fail-closed skill/MCP allowlist check
            ├── mnpi_filter.py              # regex-based MNPI scrub (strict + non-strict)
            └── idp_session.py              # SessionTokenMinter (mint + verify HMAC session tokens)
```

### Image size + rebuild signals

- Image is ~400 MB compressed in ECR
- Rebuilds whenever any code in `openclaw/` changes
- `scripts/create-v3-agentcore.sh` handles: `docker build` → ECR auth → push → `update-agent-runtime` (version bump from 15 → 16 on latest deploy)

---

## 4. The 14 agents — they are Pydantic records, not deployments

All 14 agents are defined in ONE Python file: `openclaw/orchestration/topology.py`. Each is an `AgentDefinition` with these fields:

```python
class AgentDefinition(BaseModel):
    id: str                         # unique identifier (snake_case)
    persona: str                    # fsi_research | fsi_advisor | fsi_client_liaison
    role: AgentRole                 # ORCHESTRATOR | SPECIALIST
    model: ModelTier                # SONNET | HAIKU
    system_prompt: str              # real 100-300 word prompt (not a stub)
    tool_allowlist: List[str]       # skills this agent is allowed to call
    mcp_allowlist: List[str]        # MCP servers this agent is allowed to reach
    memory_scope: List[MemoryScope] # SESSION | USER | ARTIFACT | READ_ONLY
    description: str                # 1-line role summary
    serial_by_design: bool          # True only for action_specialist (write-path)
```

The 14 definitions, grouped by persona:

```
fsi_research (6 agents)
  ├─ research_orchestrator      plan + fanout + synthesize
  ├─ market_specialist          live quotes via market-data MCP
  ├─ filings_specialist         SEC filings via sec-edgar MCP + rag_retrieve
  ├─ sentiment_specialist       30-day news via news-search MCP
  ├─ compliance_specialist      restricted-list + MNPI check
  └─ statement_specialist       XBRL deterministic math

fsi_advisor (5 agents)
  ├─ advisor_orchestrator       intent classification + routing
  ├─ portfolio_specialist       portfolio-analytics + scenario-modeling
  ├─ suitability_specialist     deterministic suitability rules
  ├─ client_context_specialist  client_summary + research_awareness
  └─ action_specialist          7-gate serial write path (compliance → HITL → dual-auth → MuleSoft → audit)

fsi_client_liaison (3 agents)
  ├─ liaison_orchestrator       FAQ-vs-escalation decision
  ├─ faq_specialist             Haiku-backed bounded answers
  └─ context_specialist         MNPI-filtered client context reads
```

**Same Python process, same 14 records.** When a turn comes in, the coordinator reads the `X-Persona` header, calls `orchestrator_for_persona(persona)` which returns one orchestrator record, then that orchestrator plans which specialists to invoke. Each specialist is dispatched by looking up its `AgentDefinition` in the `AGENT_TOPOLOGY` registry.

**No per-agent container. No per-agent Lambda. No per-agent runtime.** All 14 share the one Python process.

---

## 5. Request flow — what happens on a turn

```
┌──────────────────────────────────────────────────────────────────────────┐
│  BROWSER — user types query in SPA (d2zs9nk4uc2dbx.cloudfront.net)      │
└────────────────┬─────────────────────────────────────────────────────────┘
                 │  POST /v3/agent/invoke
                 │  {prompt, persona, session_id, principal_id}
                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  006-v3-agent-proxy  (SAM Lambda, thin bridge)                           │
│    - parses HTTP request from API Gateway                                │
│    - calls: aws bedrock-agentcore InvokeAgentRuntime                     │
│        agentRuntimeArn=arn:...openclaw_v3_agent-o72dx396I0               │
│        qualifier="DEFAULT"                                               │
│        payload={prompt, persona, session_id, principal_id}               │
└────────────────┬─────────────────────────────────────────────────────────┘
                 │  AgentCore API call
                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  AgentCore control plane                                                 │
│    - finds or creates a session (sessionId is keyed by principal_id)     │
│    - routes to a running container instance (or cold-starts one)         │
│    - 900s idle timeout, 8h max lifetime                                  │
└────────────────┬─────────────────────────────────────────────────────────┘
                 │  HTTP POST to container's /invoke endpoint
                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  openclaw-agentcore container (Python 3.11 process)                      │
│                                                                          │
│   openclaw/agentcore_server.py  ← HTTP listener                          │
│     FastAPI or similar → dispatches to:                                  │
│                                                                          │
│   openclaw/orchestration/coordinator.py::PersonaCoordinator              │
│     .run_turn(query, ctx):                                               │
│       1. orchestrator_for_persona(ctx.persona) → research/advisor/       │
│          liaison                                                         │
│       2. orchestrator.plan(query, ctx) → List[OrchestratorDispatch]      │
│       3. fanout(dispatches) →  ───────────────┐                          │
│          for each dispatch:                    │                         │
│            _invoke_specialist(dispatch, ctx)   │                         │
│          (asyncio.gather if parallel,          │                         │
│           sequential if action_specialist)     │                         │
│       4. orchestrator.synthesize(responses)    │                         │
│       5. return final text                     │                         │
│                                                │                         │
│   orchestration/coordinator.py::_run_one:      │                         │
│     if target.tool_allowlist:                  │                         │
│       run_tool_loop() ← Bedrock tool-use       │                         │
│         with toolConfig built from             │                         │
│         Pydantic input models                  │                         │
│     else:                                      │                         │
│       plain Bedrock Converse                   │                         │
│                                                ▼                         │
│   orchestration/tool_dispatch.py::run_tool_loop:                         │
│     - converse(system_prompt, toolConfig)                                │
│     - on stopReason="tool_use":                                          │
│         validate allowlist (fail-closed)                                 │
│         Pydantic-validate the input                                      │
│         skills.get_skill(name).run(payload)                              │
│         append toolResult, re-converse                                   │
│     - on stopReason="end_turn": return final text                        │
│                                                                          │
└──────────────┬───────────────────────────┬───────────────────────────────┘
               │                           │
               │  Bedrock Converse        │  MCP call
               ▼                           ▼
     ┌────────────────────┐      ┌──────────────────────────────┐
     │  Bedrock Runtime    │      │  API Gateway                  │
     │  - Sonnet 4.5       │      │  e5zbqnkmx8.execute-api...    │
     │  - Haiku 4.5        │      │                               │
     │  - Titan v2         │      │  7 MCP Lambdas behind it:     │
     │  - Guardrail        │      │   market-data (Finnhub)        │
     │    nlouzhamlv7h     │      │   sec-edgar (EDGAR + KB)      │
     └────────────────────┘      │   news-search (Tavily)         │
                                  │   salesforce-crm (OBO)        │
                                  │   mulesoft-actions             │
                                  │   bff                          │
                                  │   sf-auth-proxy                │
                                  └──────────────────────────────┘
                                              │
                                              ▼
                                       Real vendors
                                       (Finnhub, EDGAR, Tavily,
                                        Salesforce, MuleSoft)
```

Typical turn timings (from live golden turn on 2026-04-29):
- Total end-to-end: 22–25 seconds
- AgentCore cold start on first turn: ~3–5 sec
- Per-specialist fanout (5 concurrent): ~15–20 sec
- Synthesis round-trip: ~3–5 sec
- Warm session: idle timeout 15 min, so subsequent turns are faster

---

## 6. Memory — four layers, explicit ownership

OpenClaw's design specifies four distinct memory layers. Each has a different storage backend, different lifetime, and different cross-persona sharing rule.

### The rule (from `v3-narrative-arc.md`)

> **Agent memory is per-user per-persona. Cross-persona state exchange goes through Salesforce SObjects. No shared agent memory bus.**

### Layer 1 — Session memory

| Property | Value |
|---|---|
| What | Per-turn conversation within one user's session |
| Lifetime | Minutes to hours (window between first and last turn in a session) |
| Storage | **AgentCore built-in session store** (managed by AWS) |
| Shared across personas? | No — keyed by `(principal_id, persona)` |
| Used today? | **Yes** — implicitly, via AgentCore session abstraction |

AgentCore auto-creates a session the first time a principal invokes the runtime. As long as the `session_id` matches, subsequent turns share state. 900 sec idle timeout, 8 hours max lifetime. We don't call the session API directly; AgentCore manages it.

### Layer 2 — User memory

| Property | Value |
|---|---|
| What | Persistent user-specific context (Sarah's preferred sectors, RM's book scope) |
| Lifetime | Weeks+ |
| Storage | **AgentCore Memory API** (keyed by `principal_id`) |
| Shared across personas? | No — per-user only |
| Used today? | **No** — designed for but not explicitly wired |

The design prescribes user memory via the AgentCore Memory API. The current code does not call it. The `memory_scope` field on `AgentDefinition` specifies USER for some agents (advisor_orch, client_context_spec), but no production code paths write or read user memory yet.

### Layer 3 — Artifact memory

| Property | Value |
|---|---|
| What | First-class cross-persona exchange records: briefs, inquiries, approvals, audit rows |
| Lifetime | Forever |
| Storage | **Salesforce SObjects** |
| Shared across personas? | **YES — this is the whole point** |
| Used today? | **Yes** — every turn that produces a brief, inquiry, or audit writes here |

The 7 v3 SObjects:
- `Research_Brief__c` (artifact of research turns)
- `Client_Inquiry__c` (artifact of client-liaison escalations)
- `Client_Preferences__c` (per-client communication preferences)
- `IR_Audit_Log__c` (the cross-stitched audit chain)
- `IR_Pending_Approval__c` (dual-auth queue)
- `Research_Request__c` (RM → analyst demand-pull queue)
- `IR_Position__c` (client position snapshots)

Cross-persona handoff works like this: Sarah's research_orchestrator calls `publish_brief` skill → writes `Research_Brief__c` with principal=sarah, ticker=NVDA, `Published_At__c=now()` → Apex trigger fires `Research_Brief_Published__e` Platform Event → the RM's screen picks up the event and refreshes the Briefs queue. No agent talks to another agent directly. Salesforce is the bus.

### Layer 4 — Audit memory

| Property | Value |
|---|---|
| What | Immutable record of every action, every outcome, every gate fire |
| Lifetime | Forever (immutable post-insert by Apex trigger) |
| Storage | **Salesforce `IR_Audit_Log__c`** + **Langfuse traces** |
| Shared across personas? | Yes (gated by Senior_Compliance_Approver permset) |
| Used today? | **Yes** — every skill invocation writes an audit row |

Every gate outcome (`ALLOW`, `DENY`, `APPROVED`, `HITL_APPROVED`, `DUAL_AUTH_REQUESTED`, `TRADE_SUBMITTED`, `WIRE_INITIATED`, `WIRE_BLOCKED`, etc.) writes an `IR_Audit_Log__c` row with cross-stitching fields: `Principal_Id__c`, `Agent_Id__c`, `Session_Id__c`, `Correlation_Id__c`, `Research_Brief_Id__c`. The Langfuse trace for the same turn has a `parent_brief_id` attribute linking it to the artifact.

---

## 7. Environment variables — the runtime's configuration

From the live probe, the container receives these 15 env vars:

```
AGENTCORE_SESSION_SIGNING_KEY    b58627cc87a176...d7afd5   (HMAC key for session tokens)
AWS_REGION_BEDROCK               us-east-1
BEDROCK_GUARDRAIL_ID             93d93n37i1sp              (Bedrock Guardrail for input/output filter)
BEDROCK_GUARDRAIL_VERSION        2
BEDROCK_HAIKU_MODEL_ID           us.anthropic.claude-haiku-4-5-20251001-v1:0
BEDROCK_KB_ID                    NBR5AFTREI                (the openclaw-v3-filings KB)
BEDROCK_SONNET_MODEL_ID          us.anthropic.claude-sonnet-4-5-20250929-v1:0
HITL_SIGNING_KEY                 b1ba3296f93fea...6a23df   (HMAC key for HITL approval tokens)
LANGFUSE_BASE_URL                https://us.cloud.langfuse.com
LANGFUSE_PUBLIC_KEY              pk-lf-44b3...5ad8
LANGFUSE_SECRET_KEY              sk-lf-0d94...15f0d
MCP_API_KEY                      5a671c33...db749b         (shared secret for MCP auth)
MCP_API_URL                      https://e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3
MULESOFT_MODE                    mock                       (mock | sandbox | production)
OPENCLAW_DEV                     false                      (true disables Guardrail enforcement)
```

No vendor API keys live inside the runtime. Those live in Secrets Manager and are loaded by the MCP Lambdas on invocation. The runtime only needs:
- Bedrock access (via IAM role)
- API Gateway URL + MCP_API_KEY (to reach MCPs)
- Signing keys (for session + HITL token verification)
- Langfuse keys (for traces)
- Guardrail ID (to attach to Converse calls)

---

## 8. Identity and security boundaries

The runtime has three distinct identities:

1. **Runtime IAM role** (`AmazonBedrockAgentCoreSDKRuntime-us-east-1-...`) — permissions to invoke Bedrock Converse, InvokeModel, Retrieve on the KB. This is AgentCore-managed.

2. **Workload identity** (`workload-identity-directory/default/workload-identity/openclaw_v3_agent-...`) — a distinct identity the runtime container uses for its own IAM-less calls (future use, not heavily exercised today).

3. **Session tokens** — HMAC-SHA256 tokens bound to `principal_id + persona + session_id`. The channel adapter mints these. The coordinator (should) verify them on every turn. Signing key comes from the `AGENTCORE_SESSION_SIGNING_KEY` env var.

Outbound traffic:
- To Bedrock: IAM role-signed calls
- To API Gateway: requires `X-MCP-API-Key` header (shared secret)
- To Langfuse: Basic auth via `LANGFUSE_PUBLIC_KEY:LANGFUSE_SECRET_KEY`
- All outbound goes via `PUBLIC` network mode (no VPC)

Inbound:
- Only `aws bedrock-agentcore-control InvokeAgentRuntime` can reach the runtime
- The `agent-proxy` Lambda is the only caller in this deployment

---

## 9. Scaling, concurrency, lifecycle

### Concurrency

AgentCore auto-scales the underlying container pool. Multiple concurrent sessions → multiple concurrent container instances. A session sticks to one container for its lifetime (15 min idle or 8 hr max).

Rough ceilings:
- Per-account concurrent AgentCore sessions: 500+ (managed by AWS)
- Per-account Bedrock Sonnet 4.5 RPS: ~100 on-demand (us-east-1, default quota)
- A research turn = 5 parallel Sonnet calls. So ~20 concurrent research turns saturate Bedrock before AgentCore.

The bottleneck is Bedrock, not AgentCore.

### Cold start

- First turn after a 15-min idle: 3–5 sec container cold-start
- `scripts/warm-start.sh` pre-fires a throwaway ping per persona to warm the container before a demo
- `agentRuntimeVersion=16` — 16 versions deployed during v3 dev. Each `update-agent-runtime` creates a new version. `DEFAULT` qualifier points to the current version.

### Lifecycle events

- Container created by AgentCore when a session is invoked
- Container idle 15 min → AgentCore spins it down
- Session max 8 hours → forced termination (if exceeded)
- Runtime version bump: `aws bedrock-agentcore-control update-agent-runtime` creates a new version; `DEFAULT` qualifier points to it on next invoke

---

## 10. Observability — what you see when a turn runs

Three parallel observability streams:

### Stream 1 — CloudWatch Logs

`/aws/bedrock-agentcore/runtimes/openclaw_v3_agent-o72dx396I0-DEFAULT` log group receives every `print()` and `structlog` output from the container. Live tail:

```bash
aws logs tail /aws/bedrock-agentcore/runtimes/openclaw_v3_agent-o72dx396I0-DEFAULT \
  --region us-east-1 --follow
```

### Stream 2 — Langfuse traces

Every turn emits a span hierarchy. The coordinator wraps Bedrock Converse calls and skill invocations in Langfuse spans with this canonical taxonomy:

```
session.<session_id>
  turn.<turn_number>.persona.<persona_id>
    skill.<orchestrator_id>
      tool_call.<mcp_server>.<tool_name>
        — inputs (MNPI-scrubbed)
        — outputs (MNPI-scrubbed)
        — latency_ms
        — status (ok | tool_error | validation_error)
      llm_call.<model_id>
        — input_tokens, output_tokens
        — cost_usd
```

MNPI + PII + raw-token scrubbers run recursively before the trace is written. Cost attribution is available per-persona, per-user, per-skill.

### Stream 3 — Salesforce `IR_Audit_Log__c`

Every gate fire and every turn writes a durable, queryable audit row. A compliance officer can pull the full chain with SOQL:

```sql
SELECT Action__c, Principal_Id__c, Agent_Id__c, Correlation_Id__c,
       Research_Brief_Id__c, Gate_Trace__c, CreatedDate
FROM IR_Audit_Log__c
WHERE Correlation_Id__c = '<correlation_id from Langfuse>'
ORDER BY CreatedDate
```

The audit row's `Correlation_Id__c` is identical to the Langfuse trace's correlation attribute, so the two streams stitch together.

---

## 11. How to redeploy the runtime

```bash
# 1. Edit any file in openclaw/
# 2. Run the create-v3-agentcore script
bash scripts/create-v3-agentcore.sh

# What this does:
# - docker build -t openclaw-agentcore:v3-latest .
# - aws ecr get-login-password | docker login ... (or finch login)
# - docker tag ... push to ECR
# - aws bedrock-agentcore-control update-agent-runtime
#     --agent-runtime-id openclaw_v3_agent-o72dx396I0
#     --agent-runtime-artifact containerConfiguration='{containerUri=...v3-latest}'
# - Wait for status=READY (typically 3-5 min)
```

Common operations:

```bash
# Check runtime status
aws bedrock-agentcore-control get-agent-runtime \
  --agent-runtime-id openclaw_v3_agent-o72dx396I0 \
  --region us-east-1

# List all runtime versions
aws bedrock-agentcore-control list-agent-runtime-versions \
  --agent-runtime-id openclaw_v3_agent-o72dx396I0 \
  --region us-east-1

# Update env vars (without rebuilding container)
aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id openclaw_v3_agent-o72dx396I0 \
  --environment-variables "NEW_KEY=new_value" \
  --region us-east-1

# Pre-warm before demo
bash scripts/warm-start.sh

# Tail logs
aws logs tail /aws/bedrock-agentcore/runtimes/openclaw_v3_agent-*-DEFAULT \
  --region us-east-1 --follow
```

---

## 12. Why one runtime, not 14 — the design rationale

From `v3-narrative-arc.md`:

- **Single deployment reduces surface area.** 14 deploys = 14 images × 14 IAM roles × 14 configs to keep in sync.
- **Session state is per-user-per-persona.** AgentCore already partitions sessions by principal. Adding a third partition by agent-id is redundant.
- **Demo cost.** One reserved warm instance = low idle cost. 14 reserved instances = 14× cost.
- **LangGraph-style mental model.** Agents are graph nodes, not deployments. Coordinator picks the node per call.
- **Trust enforcement is in-process.** `tool_dispatch.py` and `trust/` live in the same Python process so allowlist checks happen before any network call. Cross-process would add latency + attack surface.

When would you split? If you needed:
- Per-agent scaling (e.g., the Haiku FAQ agent has 10× traffic of others)
- Per-agent blue-green deploys
- Per-agent IAM isolation (e.g., a trust-critical action_specialist runs in a separate account)

None of those apply to v3 today. The one-runtime architecture fits the demo and the first production phase.

---

## 13. Known gaps and caveats

Honest, from the live probes and code review:

1. **`SessionTokenMinter.verify()` is not called in the coordinator.** Session tokens are minted by the channel adapter, but the coordinator trusts whatever `principal_id` arrives. For a multi-user production deploy, this must be wired (~30 LOC).

2. **`GateEnforcer.check_mcp()` is not called from production paths.** The `mcp_allowlist` field on each `AgentDefinition` is advisory only today. The fail-closed enforcement is a planned 45-min fix.

3. **User memory layer is not used.** The `memory_scope` fields are set but the Memory API isn't called. Design-ready, runtime-not-wired.

4. **WebSocket gate events are not emitted mid-turn.** The coordinator writes the full gate trace at end-of-turn in the response payload. The SPA's SevenGateTracker renders the whole trace at once, not gate-by-gate. 45-min backend fix pending.

5. **HITL TokenStore is in-memory.** On pod restart (idle timeout hit), minted-but-unconsumed approval tokens are lost. For a one-pod demo this is fine; for multi-pod prod, wire Redis.

6. **AgentCore Memory API unused.** The design calls for user memory via `bedrock-agentcore memory:put/get`. Not currently exercised. Code paths can be added when a real multi-session user demand exists.

---

## 14. One-picture summary

```
┌────────────────────────────────────────────────────────────────────────┐
│                                                                        │
│     AGENTCORE RUNTIME (managed by AWS)                                │
│     openclaw_v3_agent-o72dx396I0  · version 16  · status READY        │
│                                                                        │
│     ┌──────────────────────────────────────────────────────────────┐  │
│     │  1 Docker container: openclaw-agentcore:v3-latest             │  │
│     │                                                                │  │
│     │    Python 3.11 process                                         │  │
│     │                                                                │  │
│     │    ┌────────────────────────────────────────────────────────┐ │  │
│     │    │  agentcore_server.py  (HTTP listener)                    │ │  │
│     │    └───────────────┬────────────────────────────────────────┘ │  │
│     │                    ▼                                          │  │
│     │    ┌────────────────────────────────────────────────────────┐ │  │
│     │    │  PersonaCoordinator                                     │ │  │
│     │    │    ├─ picks 1 of 3 orchestrators by X-Persona          │ │  │
│     │    │    └─ run_turn() → plan → fanout → synthesize          │ │  │
│     │    └───────────────┬────────────────────────────────────────┘ │  │
│     │                    ▼                                          │  │
│     │    ┌────────────────────────────────────────────────────────┐ │  │
│     │    │  topology.py  — 14 AgentDefinition Pydantic records     │ │  │
│     │    │  (3 orchestrators + 11 specialists)                     │ │  │
│     │    │  Each with: system_prompt, tool_allowlist,              │ │  │
│     │    │  mcp_allowlist, memory_scope, model_tier                │ │  │
│     │    └───────────────┬────────────────────────────────────────┘ │  │
│     │                    ▼                                          │  │
│     │    ┌────────────────────────────────────────────────────────┐ │  │
│     │    │  tool_dispatch.py::run_tool_loop                        │ │  │
│     │    │  Bedrock Converse + toolConfig from Pydantic schemas    │ │  │
│     │    │  Fail-closed allowlist check. Serial skill dispatch.    │ │  │
│     │    └───────────────┬────────────────────────────────────────┘ │  │
│     │                    ▼                                          │  │
│     │    ┌────────────────────────────────────────────────────────┐ │  │
│     │    │  skills/ — 14 Python modules, each is a tool          │ │  │
│     │    │  Pydantic input/output, .run() method                 │ │  │
│     │    │  Each skill can call MCPs via _mcp_client.py          │ │  │
│     │    └────────────────────────────────────────────────────────┘ │  │
│     └──────────────────────────────────────────────────────────────┘  │
│                                                                        │
│     15 env vars:                                                       │
│       - Bedrock model IDs, Guardrail ID, KB ID                         │
│       - Signing keys (session + HITL)                                 │
│       - MCP_API_URL + MCP_API_KEY                                      │
│       - Langfuse keys                                                  │
│       - MULESOFT_MODE, OPENCLAW_DEV flags                              │
│                                                                        │
└──────────┬─────────────────────────────────────────────────────────────┘
           │ (outbound, via PUBLIC network mode)
           │
           ▼
    ┌────────────────────────┐      ┌───────────────────────────────┐
    │  Bedrock Runtime API    │      │  API Gateway (MCP)            │
    │    - Sonnet 4.5          │      │    7 MCP Lambdas behind it:   │
    │    - Haiku 4.5           │      │      market-data, sec-edgar,  │
    │    - Titan v2            │      │      news-search, salesforce- │
    │    - Guardrail           │      │      crm, mulesoft-actions,   │
    │      nlouzhamlv7h        │      │      bff, sf-auth-proxy        │
    └────────────────────────┘      └───────────────────────────────┘
                                                │
                                                ▼
                                        Real vendors
                                        (Finnhub, EDGAR, Tavily,
                                         Salesforce, MuleSoft, Alpaca)


    ┌────────────────────────┐      ┌───────────────────────────────┐
    │  Langfuse US cloud     │      │  Salesforce new-org            │
    │  Trace + span          │      │  IR_Audit_Log__c rows          │
    │  telemetry             │      │  Research_Brief__c, etc.       │
    └────────────────────────┘      └───────────────────────────────┘
```

---

*Doc written 2026-04-30. Sourced from live AWS probes + topology.py + v3-narrative-arc.md.*
