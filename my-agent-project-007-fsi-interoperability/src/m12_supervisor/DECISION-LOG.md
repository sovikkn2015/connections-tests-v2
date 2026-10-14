# M12 Supervisor — Decision Log

## v0.1.0 — Phase 2 RIA Lighthouse (initial)

### D-1. M12 is glue, not an orchestrator
The channel (OpenClaw, Claude Managed Agents, or Strands in Phase 3)
drives the agent loop. M12 does exactly three things per call:
1. Build M9 `RouterContext` from a verified AID.
2. Call `m9_intent_router.route()` to classify the utterance.
3. Branch on `decision.selected_target.kind`:
   - `pipeline` → run M8.
   - `tool` → return `tool_target` for the channel to forward via M6.
   - `escalate` → return `escalation_target` for the channel to
     hand off to a specialist.

No retry loops, no agent-loop step counting, no planner. That is a
deliberate Phase 2 constraint — the lighthouse RIA journey is a single
user turn → single dispatch → single pipeline run.

### D-2. M12 does NOT call M6
Tool dispatch is the channel's job. M12 surfaces the tool name and
lets the channel forward it through M6. This keeps the M6 Trust Pipeline
(M1 → M2 → M4 → M10) exactly one layer away from the agent loop and
frees M12 from holding M6 connection state.

Consequence: `test_m12_module_boundary.py` enforces no `m6_` import.

### D-3. M12 does NOT call M10 directly
Both M8 and M9 emit their own audit events (M8 via per-stage
`AuditClient`, M9 via single stdout emit). M12 has no client-data
access and no compliance decisions to audit. If a later phase needs a
supervisor-level event line, it will be added via an injected
`AuditClient` parameter — not a new import of `m10_audit_logger`.

### D-4. dispatch() NEVER raises
Every failure path returns a `SupervisorResult` with `status="failed"`
and a reason code:
- `m12_invalid_aid` — caller passed something that's not an `AidClaims`.
- `m12_routing_failed` — M9 raised (it isn't supposed to; this is
  defence in depth).
- `m12_dispatch_failed` — M8 raised (ditto).
- `m12_invalid_pipeline_result` — M8 returned the wrong shape.

Child reason codes (m8_*, m9_*, llm_*, and the M9 passthrough set) are
re-exposed verbatim on `SupervisorResult.reason_code` when M12 has no
reason to override them.

### D-5. Status vocabulary
`SupervisorResult.status` is a 6-way Literal:
`completed | paused | rejected | escalated | timed_out | failed`.
M8's `terminated` (checkpoint-write failure) is folded into `failed`
because the supervisor-level caller doesn't care about the sub-cause.

### D-6. Strands runtime toggle deferred
Per ARCH-10 Decision 2 and Steering Rule 1, the runtime switch is a
Helm values toggle, not a code change. Phase 2 lighthouse is
Managed-Agents-only; M12 v0.1.0 hard-codes `runtime=managed_agents`
when building the M9 `RouterContext` and M8 `PipelineState`.
Phase 3 will read this from `_config`.

### D-7. Dependency injection
M12 accepts `_provider` (M9 LLM) and `_config` as keyword-only
injection points. Production wiring happens in the channel; tests pass
`FakeLlmClient` + `FakeIntentRouterConfig` and rely on M8's built-in
Fake* dependencies (no M12-side injection needed for the pipeline).

### D-8. TypedDict PipelineState
M8's `PipelineState` is a TypedDict. `build_pipeline_state()` returns a
plain dict; M8's `_validate_initial_state()` walks the required keys
and raises if any are missing. This matches how
`tests/fixtures/m8_fixtures.py::make_initial_state` works today.

### Known gaps (future versions)
- v0.2.0 will accept `_supervisor_config` with `runtime` + `max_retries`.
- v0.2.0 will carry the `HitlApproval` round-trip for paused pipelines.
- v0.3.0 (Phase 3) will route onboarding/execution intents to their own
  specialist wrappers (currently escalate-only).
