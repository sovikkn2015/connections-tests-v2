# M12: Agent Runtime — PLUG IN Module

> Type: PLUG IN (configuration, not custom code)
> Lines: 0 custom code
> Phase: 2

## What This Module Does

M12 is the agent runtime layer — OpenClaw for channel gateway (12+ channels:
Slack, Teams, WhatsApp, Web) plus Claude Managed Agents (cloud) or Strands SDK
(hybrid/on-prem) for agent orchestration.

**This is NOT custom code.** The runtime is selected via Helm values toggle:

```yaml
# values-cloud.yaml
agentRuntime:
  type: managed-agents  # Claude Managed Agents (default for cloud)

# values-hybrid.yaml
agentRuntime:
  type: strands-sdk     # Strands SDK (for hybrid/on-prem)
```

Application code is identical across topologies. Only the runtime config changes.

## Architecture

```
M12 OpenClaw (12+ channels)
  + Claude Managed Agents (cloud) / Strands SDK (hybrid)
    |
    +-> M9 Intent Router
    +-> M8 Pipeline Engine
    +-> M6 MCP Gateway (all data access)
```

## Dependencies

M12 calls: M6 (gateway), M8 (pipeline), M9 (intent router)

## 5 Specialist Agents (configured, not coded)

| Specialist | Framework | LLM | Notes |
|-----------|-----------|-----|-------|
| Supervisor | Managed Agents / Strands | Haiku | Routes to specialists |
| Research | LangGraph (M8) | Sonnet | 23-stage pipeline |
| Client Service | Managed Agents / Strands | Haiku | Cross-channel memory |
| Compliance | OPA/Rego | NONE | Deterministic, not LLM |
| Execution | Managed Agents / Strands + FSM | Haiku | HITL mandatory |
| Onboarding | Workflow Engine | Haiku | Multi-session KYC |

## Files

- `runtime_config.py` — Runtime configuration schema (Pydantic v2)
- Helm values files define the actual runtime selection (in `infra/helm/`)
