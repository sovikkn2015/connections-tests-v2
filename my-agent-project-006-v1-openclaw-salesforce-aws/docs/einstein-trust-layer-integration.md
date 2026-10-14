# Einstein Trust Layer Integration — Project 006

## Status: IMPLEMENTED

The Einstein Trust Layer is integrated via `openclaw/skills/salesforce-crm/trust_layer.py` and wired into the pipeline at stages 14 and 17. It operates alongside Bedrock Guardrails as the second trust layer.

---

## Dual Trust Layer Architecture

Project 006 uses two independent trust layers for defense-in-depth:

### Layer 1: Bedrock Guardrails (all LLM calls)

- Applied to every Bedrock `converse` call via the pipeline's `_llm_generate()` method
- PII masking (regex + ML patterns)
- Toxicity filtering
- Denied topics (MNPI, trade instructions)
- Prompt injection detection
- Configured in `aws/guardrails/bedrock-guardrails.yaml`

### Layer 2: Einstein Trust Layer (CRM data reasoning)

- Applied to pipeline stages that reason about CRM data via `_llm_generate_with_trust()`
- Routes prompts through SF Models API (`/services/data/v66.0/einstein/llm/prompt-completions`)
- Prompt injection detection (independent of Bedrock)
- PII/sensitive data masking (CRM-aware, knows SF field types)
- Toxicity filtering
- Zero data retention (enforced by Salesforce contract)
- Native audit trail in Salesforce Einstein audit log
- Implemented in `openclaw/skills/salesforce-crm/trust_layer.py`

### How They Work Together

```
User query → OpenClaw → Pipeline Stage (CRM reasoning)
                              │
                              ├─→ _llm_generate_with_trust()
                              │       │
                              │       ├─→ SF Models API (Einstein Trust Layer)
                              │       │       • Prompt defense
                              │       │       • PII masking
                              │       │       • Toxicity check
                              │       │       • Audit event logged in SF
                              │       │
                              │       └─→ [fallback] _llm_generate() → Bedrock
                              │               • Bedrock Guardrails apply
                              │               • PII masking
                              │               • Toxicity check
                              │
                              └─→ Result → next stage
```

Both layers fire independently. If the trust layer is unavailable, Bedrock Guardrails still protect the call.

---

## Pipeline Stages Using Trust Layer

The trust layer is used in stages that reason about CRM data:

| Stage | Name | Why Trust Layer |
|-------|------|-----------------|
| 14 | Thesis Generation | Synthesizes CRM context (coverage, watchlist, prior notes) into investment thesis |
| 17 | Rating Determination | Uses CRM context alongside financial models to determine Buy/Hold/Sell |

Other stages use `_llm_generate()` (Bedrock only) because they don't involve CRM data reasoning.

---

## Fallback Behavior

The trust layer is designed to never break the pipeline:

1. **Availability check**: On first CRM reasoning call, `is_trust_layer_available()` probes the Models API endpoint. Result is cached for the pipeline run.
2. **If unavailable (404)**: Logs a warning, falls back to Bedrock silently. Pipeline continues.
3. **If blocked (injection/toxicity)**: Logs a warning with the block reason, falls back to Bedrock. Pipeline continues.
4. **If error (timeout, auth, HTTP error)**: Logs the error, falls back to Bedrock. Pipeline continues.

The pipeline never fails due to trust layer issues. Bedrock Guardrails remain the safety net.

---

## Enabling Einstein Trust Layer on a Salesforce Org

### Prerequisites

1. Einstein AI features enabled (Setup → Einstein → Enable Einstein)
2. Models API provisioned (Setup → Einstein → Models)
3. Connected App with `einstein_gpt_api` OAuth scope
4. Einstein 1 license or Einstein AI credits on the org

### Steps

1. In Salesforce Setup, navigate to Einstein → Einstein Settings
2. Enable Einstein AI features
3. Navigate to Einstein → Models and verify the Models API is active
4. Edit the existing Connected App and add the `einstein_gpt_api` scope
5. Rotate the SF access token in AWS Secrets Manager to include the new scope
6. The pipeline will auto-detect availability on the next run via `is_trust_layer_available()`

### Verification

Run a pipeline execution and check the logs for:
```
INFO einstein-trust-layer Trust Layer audit event: <event-id>
```

If the org doesn't have Einstein AI:
```
INFO einstein-trust-layer Einstein Trust Layer not available on this org (404)
WARNING fsi-research-pipeline Trust layer call failed, falling back to Bedrock: Einstein Trust Layer not available on this org
```

Both are normal. The pipeline works either way.

---

## Implementation Files

| File | Purpose |
|------|---------|
| `openclaw/skills/salesforce-crm/trust_layer.py` | Core module: `generate_with_trust_layer()`, `is_trust_layer_available()`, response parsing |
| `openclaw/skills/fsi-research/pipeline.py` | Pipeline integration: `_llm_generate_with_trust()` helper, stages 14 + 17 updated |
| `docs/einstein-trust-layer-integration.md` | This document |

---

## Security Considerations

- **No credentials in code**: SF instance URL and access token are passed as function parameters from env vars
- **Timeout protection**: 30s timeout on Models API calls, 10s on availability probe
- **Error isolation**: Trust layer errors never propagate — always fall back to Bedrock
- **Audit dual-write**: Trust layer audit events logged in SF + pipeline audit in IR_Audit_Log__c via Langfuse
- **MNPI protection**: Trust layer adds CRM-aware PII masking on top of Bedrock Guardrails regex patterns

---

## Comparison: Before and After

| Aspect | Before (Bedrock only) | After (Dual trust layer) |
|--------|----------------------|--------------------------|
| PII masking | Bedrock regex + ML | Bedrock + SF CRM-aware masking |
| Prompt injection | Bedrock detection | Bedrock + SF independent detection |
| Toxicity | Bedrock filtering | Bedrock + SF filtering |
| Zero data retention | Bedrock config-dependent | SF contractually enforced |
| CRM audit trail | Langfuse + IR_Audit_Log__c | + SF Einstein native audit |
| Pipeline failure risk | N/A | Zero — graceful fallback to Bedrock |
