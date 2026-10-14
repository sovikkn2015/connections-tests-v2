# 006 V3 — Demo Readiness (Board-Critical)

**Question asked:** Is everything wired end-to-end for 006 v3? Demo must run real — no mockery drama. Architecture must be explainable.

**Short answer:** Mostly wired end-to-end, and the trust spine is real code, not prompt-advisory. The remaining gap is the last-mile "has this ever talked to real Bedrock / real Salesforce / real data" — roughly half a day of deploy work, not a rebuild.

---

## What IS wired end-to-end, as designed

Verified by reading the code (not marketing docs).

- Seven-gate serial spine is code-enforced. `openclaw/orchestration/coordinator.py::_run_one()` routes any agent with `serial_by_design=True` and a non-empty `tool_allowlist` through `openclaw/orchestration/tool_dispatch.py::run_tool_loop()`. That function builds a Bedrock `toolConfig` from each skill's Pydantic input model, runs `bedrock.converse(..., toolConfig=...)`, parses `toolUse` blocks on `stopReason == "tool_use"`, dispatches serially to `get_skill(name).run(payload)`, appends `toolResult` back to the message history, and re-invokes until `stopReason != "tool_use"`. Gate trace is recorded with ordered tool names + status.
- Allowlist is fail-closed server-side. A model hallucinating a non-allowlisted tool receives a `tool_not_allowed` `toolResult` and never executes the skill.
- Pydantic validation returns `validation_error` tool_results to the model (so it can retry) rather than silently swallowing bad input.
- Integration test exists: `tests/integration/test_seven_gate_chain.py` drives compliance → HITL → dual_auth → mulesoft → audit in order via scripted `tool_use` envelopes. Also covers out-of-allowlist denial and invalid-input tool-error surfacing.
- MCP auth is fail-closed. `aws/mcp-servers/_base/mcp_server.py::_require_api_key` raises `McpAuthError` when `MCP_API_KEY` is missing unless `MCP_DEV_MODE=true` is explicitly set. (Earlier review incorrectly flagged this as fail-open; verified corrected.)
- Research orchestrator fans out 5 specialists in parallel via `asyncio.gather`, citation-enforcement strips unsourced sentences in `synthesize()`, compliance `DENY` marks `rm_consumable=false`.
- MNPI redaction on the CRM MCP is server-side (field-level: `shares_held`, `market_value`, `cost_basis`, `wire_amount`, etc.). Orchestrators cannot bypass — redaction happens inside the Lambda before the response is serialized.
- Langfuse scrubbing wrapper recursively filters every trace/span payload (MNPI + PII + raw tokens).
- HITL tokens: HMAC-SHA256, 5-min TTL, plan_hash bind, single-use via fingerprint store, raw token never logged, fail-closed on missing signing key.
- OFAC SDN screen is code-enforced inside `mulesoft_api.run()` — cannot be skipped by the LLM.
- Compliance `DENY` has no override flag anywhere.
- Dual-auth second-approver distinctness enforced by a Pydantic `frozen=True` model validator.
- Audit row fires on every outcome (approve, reject, block, timeout, OFAC hit, MuleSoft failure) with hashed approval token, not raw.

## What is NOT yet exercised against real services

These are the only items that matter for the "demo must run real" mandate.

1. **Nothing has ever talked to real Bedrock.** All 267 green tests use `StubBedrockClient`. `run_tool_loop` is coded against Bedrock's documented Converse API, but Sonnet 4.5's actual output shape (markdown fences around JSON, prose preamble, tool_use block ordering) has not been verified end-to-end.
2. **Bedrock model access is not verified in the target account.** SAM default is `anthropic.claude-sonnet-4-5-20250929-v1:0` in `us-east-1`. Model access must be granted in the Bedrock console — 10-minute checkbox, not done in the repo.
3. **Apex has never deployed to a real org.** Custom objects, permsets, triggers, Apex tests all exist as metadata. Zero of it has been `sf project deploy start`'d against a scratch org. First deploy will find 2–4 field/permset/validation-rule mismatches. Budget 30–90 min per issue.
4. **`MULESOFT_MODE=mock` is the only path exercised.** Sandbox-mode client call path in `_mulesoft_client.py::call()` has never been run. For the demo, keep mock mode — it's realistic, audit-rows-all-paths, and the vendor boundary is a legitimate explanation.
5. **RAG has a dimensional trap.** `StubEmbedder` is 64-dim, `BedrockTitanEmbedder` is 1024-dim. Switching embedders between test and prod without re-indexing makes cosine similarity near-random. Untested.
6. **HITL TokenStore is in-memory.** Single-pod AgentCore = fine. Multi-pod = replay errors across pods. For a one-person live demo this doesn't matter.
7. **No real-browser E2E.** Frontend tests run against `MockWebSocket`. Frontend/backend contract drift is undetected.

## Architecture (explainable in one diagram)

```
  User turn (web / Slack)
         │
         ▼
  PersonaCoordinator   ← single entry, routes to persona orchestrator
         │
         ├─► ResearchOrchestrator   (parallel fanout of 5 specialists via asyncio.gather)
         │       │
         │       └─► tool_dispatch.run_tool_loop()   ← Bedrock Converse + toolConfig
         │              │                               Pydantic-validated tool_use
         │              └─► skills: rag_retrieve, financial_statement_analysis, ...
         │
         ├─► AdvisorOrchestrator    (parallel reads OR serial writes)
         │       │
         │       └─► action_specialist (serial_by_design=True)
         │              │
         │              └─► run_tool_loop() enforces 7-gate order:
         │                    Guardrails → MNPI filter → compliance → HITL →
         │                    dual_auth → mulesoft_api → audit_logging
         │
         └─► LiaisonOrchestrator    (Haiku, read-only + rm-handoff)
                 │
                 └─► faq_specialist OR context_specialist (MNPI-filtered)

  Every converse call:        Langfuse span + PII/MNPI/token scrubber
  Every CRM read:              MNPI redaction server-side (field-level)
  Every skill invocation:      Allowlist-checked + schema-validated before run
  Every action attempt:        Audit row regardless of outcome
```

The LLM does not "decide" whether to call gates. The runtime enforces the order. A skill invocation outside the allowlist returns a `tool_not_allowed` `toolResult` to the model without executing. That is a code contract, not a prompt.

## Minimum work to earn "it runs real" for the demo

Half a day of deploy. Not a rebuild.

1. **Grant Bedrock model access** for Sonnet 4.5 + Haiku 4.5 in `$AWS_REGION_BEDROCK`. 10 minutes, AWS console.
2. **Deploy Salesforce metadata** to a scratch org, fix the 2–4 field/permset issues that will surface. 1–2 hours.
3. **Run `./scripts/deploy-all.sh --skip-mulesoft --skip-frontend`** to isolate SAM/CDK deployment issues. 30–60 min.
4. **Write ONE golden-turn smoke test** against real Bedrock: single query, assert `tool_use` blocks parse through `run_tool_loop` end-to-end. This catches real-Claude-output drift before the demo does. 30 min.
5. **Keep `MULESOFT_MODE=mock`** for the demo. The mock mode is deliberate, realistic, writes audit rows on every path, and the vendor boundary is a legitimate part of the explanation.
6. **Demo choreography:**
   - Research turn — real Bedrock, real Tavily, real SEC EDGAR. Shows parallel fanout + citations.
   - Advisor action turn — fires the seven gates serially on screen. Audit strip updates in real time as each gate returns.
   - Liaison turn — CRM MCP MNPI redaction visible in the response (bands, not dollar amounts).

## Correction vs the previous LLMJ review

The Wave-3 Reviewer B report (`docs/llmj-reviewer-b-security-compliance-audit.md`) claimed the seven-gate spine was "prompt-only" and `get_skill()` was never called outside tests. That was wrong.

Ground truth from the current code:
- `openclaw/orchestration/coordinator.py::_run_one()` calls `run_tool_loop()` for every `serial_by_design` agent.
- `openclaw/orchestration/tool_dispatch.py` implements the full Bedrock tool-use loop with allowlist enforcement, Pydantic validation, serial dispatch into `get_skill(name).run(payload)`, and gate trace recording.
- `tests/integration/test_seven_gate_chain.py` exists and exercises the full spine.

The architecture is code-enforced. The earlier report was based on an outdated view.

## Bottom line

- Code: wired end-to-end as designed. Trust spine is real.
- Tests: 267 pass. About a third is load-bearing algorithmically; the rest validates wiring.
- Real-run gap: nothing has ever talked to real Bedrock, Salesforce, Tavily, or EDGAR. Half a day of deploy + one golden-turn test closes it.
- Demo integrity: keep `MULESOFT_MODE=mock`, be upfront it's the vendor boundary, let everything else run real. Defensible and honest.
- Architecture explainability: one diagram, three personas, seven gates code-enforced by a Bedrock tool-use loop. That is the story.
