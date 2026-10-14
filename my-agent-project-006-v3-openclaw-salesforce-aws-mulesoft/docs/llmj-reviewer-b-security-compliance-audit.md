# LLMJ Reviewer B — Security & FSI Compliance Audit

Target: `my-agent-project-006-v3-openclaw-salesforce-aws-mulesoft/`
Lens: FSI production-readiness. Real code only; marketing ignored.

---

## One-line verdict

**NOT production-ready for a regulated FSI trading/wire path.** The skill-layer primitives (MNPI filter, HITL tokens, compliance screener, dual-auth, audit writer) are genuinely well-built, but the **seven-gate "serial spine" is enforced only by an LLM system prompt — there is no runtime code that dispatches gates in sequence from the action_specialist LLM output into the skill modules**. In addition, the MCP servers have an auth-bypass-when-env-is-empty pattern that is a classic FSI red-flag.

---

## Per-area scorecard

| Area | Verdict | One-line evidence |
|------|---------|-------------------|
| A. MNPI leakage | **PARTIAL** | Filter + CRM redactor are real and match the rule set, but `[MNPI_REDACTED]` is only referenced in an LLM prompt, not enforced in code, and specialist LLM responses are **not** re-scrubbed before synthesis. |
| B. Write-path safety | **FAIL (as a runtime spine)** | The seven gates are a prompt instruction in `ACTION_SPECIALIST_PROMPT`; `_run_one()` in `orchestration/coordinator.py` does a single `bedrock.converse()` and returns text — **no tool-use dispatch, no skill invocation loop** (`get_skill()` is only called from tests). The individual skills are well-built defenses, but nothing chains them at runtime from the LLM's action_specialist turn. |
| C. Credential hygiene | **PARTIAL** | No hardcoded API keys in source; `.env.example` is templates. BUT `MCP_API_KEY` is fail-open when env is missing (`_base/mcp_server.py:147`), `SF_AUTH_PROXY_KEY` is fail-open when empty (`sf-auth-proxy/app.py:119`), and `research_pipeline_stack.py:83` pins `"https://placeholder.my.salesforce.com"` as a CDK default. |
| D. Input validation / injection | **PASS (for the surfaces shown)** | `_soql_safe.py` forbids `UPDATE/DELETE/INSERT/UPSERT/MERGE/TRUNCATE/--/;` with a regex, length-caps to 20k, and `validate_identifier()` whitelists identifier shapes. Persona gate in CRM MCP blocks `fsi_client_liaison` from all writes. MCP `tools/call` validates via Pydantic. |
| E. Audit completeness | **PASS (at skill layer)** | Every skill writes exactly one audit row on every outcome (approve/reject/block/timeout), approval tokens are `sha256:` prefix-hashed before Salesforce write, gate trace is an ordered list. But rows fire only if the LLM actually invokes the skills — see Area B. |
| F. Guardrails | **PARTIAL** | `BedrockConverseClient.converse()` attaches `guardrailConfig` when `BEDROCK_GUARDRAIL_ID`+`_VERSION` are set and translates `stopReason == "guardrail_intervened"` into `GuardrailInterventionError`, which `_invoke_specialist` maps to `AgentError(SAFETY, recoverable=False)`. Input-side only when both env vars present; nothing fails closed when they're absent. |

---

## Area A — MNPI leakage (detail)

**What is real:**
- `openclaw/trust/mnpi_filter.py` has a genuine scrubber: regex for `$N[KMB]`, `N shares/contracts`, wire instructions, insider-hint phrases; hard-deny on sentinel tags (`[MNPI_RAW]`, `[MNPI]`, `[INSIDER]`, `{{MNPI}}`) via `MNPIViolation`; strict mode raises on insider phrasing. `scrub_object` recurses dict/list.
- `aws/mcp-servers/salesforce-crm/_mnpi_redact.py` enforces field-level redaction for `shares_held(_c)`, `market_value(_c)`, `cost_basis(_c)`, `unrealized_gain`, `realized_gain`, `position_size`, `holdings_amount`, `trade_amount`, `wire_amount`, `wire_beneficiary`, `wire_account_number`. Replaced with `REDACTED[band=N%-M%]`. Applied server-side in every CRM read path (`query_soql`, `get_object`, `read_household_summary`, `read_household_positions`, `read_research_briefs_with_exposure`, DLM joins). **Orchestrator cannot bypass it** because redaction happens inside the MCP Lambda before the response is serialized.
- Langfuse scrubber in `orchestration/coordinator.py:scrub_before_write` runs three passes (`MNPI`, `PII`, `token`) recursively on every span/trace payload before flush. `_ScrubbingLangfuseWrapper` wraps `trace()/span()/update()`.
- `audit_logging/actions.py:run` calls `MNPIFilter(strict=False).scrub_object(payload.payload)` before the Salesforce row is assembled.

**What is broken or missing:**
- **"`[MNPI_REDACTED]` handled as empty by orchestrators" — NOT IMPLEMENTED IN CODE.** Grep for `MNPI_REDACTED` returns **exactly one match**, inside `RESEARCH_ORCHESTRATOR_PROMPT` (topology.py:99): _"If any specialist returns a block marked [MNPI_REDACTED], treat that region as empty and continue."_ That is a prompt instruction to the LLM. `research_orchestrator.py:synthesize()` has no check for the sentinel.
- **Specialist responses are not re-filtered before synthesis.** `coordinator._run_one()` returns `WorkerResponse(result={"text": text})` straight from the Bedrock converse output. Neither `advisor_orchestrator.synthesize` nor `research_orchestrator.synthesize` runs `MNPIFilter` over the specialists' `text`. The trust is that the CRM MCP redacted the upstream data — but if a specialist LLM reintroduces a dollar amount or shares count (hallucination or prompt-leak), nothing strips it before it reaches the synthesized brief/response.
- The `MNPIFilter` used in `audit_logging.run` is `strict=False` (`audit_logging/actions.py:170`), so insider-style phrasing is quietly redacted-in-place rather than raising. That's probably intentional for audit rows but it means the audit log cannot be trusted as a detector of MNPI violations upstream.

---

## Area B — Write-path safety (detail — this is the failure)

**What is real at the skill level:**
- `hitl/_tokens.py`: HMAC-SHA256 with `HITL_SIGNING_KEY` (min 32 chars enforced at `_signing_key()`; raises `RuntimeError` if unset — fail-closed). TTL bounded to 1..3600 s with default 300 s. `verify_token` enforces signature (`hmac.compare_digest`), expiry (`exp < now`), plan_hash rebinding (`expected_plan_hash != plan_hash`), optional user_id. `TokenStore.consume()` makes tokens single-use; `is_consumed` drops expired entries. Fingerprint = `hmac-sha256(key, mac_hex)[:32]` — token value is never stored.
- `hitl/actions.py`: on any `ValueError` from `verify_token`, maps to a `HITLError(kind=...)` AND writes an `HITL_REJECTED` audit row before raising. Replay-path also writes `HITL_REJECTED` with `kind=replay`. Happy path writes `HITL_APPROVED`.
- `dual_auth/actions.py`: distinctness of second approver enforced by a Pydantic `model_validator` (`_guard_distinct`) — **cannot** be bypassed by caller since model is `frozen=True`. `senior_permset_held=False` forces `REJECTED` regardless of `second_approver_decision` (`approved = decision=="approve" AND senior_permset_held`). Thresholds are pure-function in `threshold_required()`.
- `compliance_screening/actions.py`: DENY is hard-coded in the lattice with **no override flag anywhere in the function** — `if restricted_hit: decision = DENY`, `elif not conc_ok: decision = DENY`, `elif trading_window_closed AND submit/modify: decision = DENY`. A DENY always writes `COMPLIANCE_BLOCKED` audit before returning (lines 199-221).
- `mulesoft_api/actions.py`: `MuleSoftInput` Pydantic model has `_writes_require_approval` model_validator — a write method without `hitl_approval` raises at construction. OFAC SDN screen on every wire BEFORE the call. Audit row written for success (`TRADE_SUBMITTED`/`WIRE_INITIATED`) AND for failure (`TRADE_REJECTED`/`WIRE_BLOCKED`) AND for OFAC hit.
- Approval tokens hashed (not raw) before audit write — `audit_logging/actions.py:hash_token` → `sha256:<first-16-hex>` stored in `Approval_Token_Hash__c`.

**Why the spine is still broken:**
- `action_specialist` is defined in `topology.py` as a Bedrock LLM sub-agent (Sonnet, `serial_by_design=True`, tool_allowlist=[compliance_screening, hitl, dual_auth, mulesoft_api, audit_logging]). Its "behavior" is `ACTION_SPECIALIST_PROMPT` (topology.py:213+) — text that tells the LLM _"You sequence SEVEN GATES IN ORDER"_.
- `orchestration/coordinator.py:_run_one()` (lines ~407-435) is the only code path that executes a specialist. It calls `self.bedrock.converse(...)` and returns `WorkerResponse(result={"text": text})`. **There is no tool-use response parsing, no function-calling loop, no dispatch of skill names back into `get_skill(name).run(input)`.** Grep: `"toolUse"` / `"tool_use"` / `"toolConfig"` → **zero matches** in the entire repo; `get_skill(` is called only from tests.
- The skill-registry docstring (`skills/_registry.py:3`) says _"Orchestrators that need to invoke a skill do so via `get_skill(name)`"_ — aspirational; no orchestrator code calls it.
- The `serial_by_design=True` flag works mechanically: when the advisor orchestrator's `plan()` returns a single `action_specialist` dispatch, `coordinator.run_turn()` sets `serial=True` for `fanout()`, and `fanout()` with `serial=True` uses a for-loop instead of `asyncio.gather`. This is correct but vacuous — there is only ever ONE dispatch in that list, and that one dispatch is just a single LLM call whose **output text** is then handed back to the advisor orchestrator's `synthesize()`. The LLM can claim "I called all seven gates" in its text; the runtime has no way to verify.
- Consequence for a FINRA-style audit: **no IR_Audit_Log__c rows are actually produced by a real action_specialist turn today**, because no skill is invoked. The audit rows exist only in unit tests and in orchestrator synthesis scaffolding — not in a real RM write request path.

**Severity: CRITICAL blocker.** This is the single largest finding. Every other skill-level defense is genuine; the harness that ties them together is missing.

---

## Area C — Credential hygiene (detail)

**Clean:**
- Grep for `AKIA`, `sk_live`, `sk_test`, raw bearers → zero matches in non-test code.
- `.env.example` uses `<YOUR_X>` placeholders; `.gitignore` excludes `.env`.
- Signing keys fail-closed when unset: `HITL_SIGNING_KEY` raises `RuntimeError` if absent or <32 chars (`hitl/_tokens.py:_signing_key`). `AGENTCORE_SESSION_SIGNING_KEY` raises `RuntimeError` at `SessionTokenMinter.__init__` if absent.
- `mulesoft/process-apis/*/src/main/resources/config.yaml` placeholders are explicitly marked `PLACEHOLDER_SET_VIA_SECURE_PROPERTIES_AT_DEPLOY`, with `NEVER committed` comments on HMAC secrets.
- Secrets seeded via `scripts/seed-secrets.sh` into AWS Secrets Manager under `/006-v3/*`.

**Issues:**
- **`aws/mcp-servers/_base/mcp_server.py:145-151` fail-open on missing `MCP_API_KEY`:**
  ```python
  expected = os.environ.get("MCP_API_KEY")
  if not expected:
      # Local/dev mode: no key configured = skip auth. Lambda env always sets it.
      return
  ```
  "Lambda env always sets it" is a deploy-time hope, not a code invariant. If a config drift ever strips this env var in a live Lambda (rotation script bug, missing CloudFormation param), the MCP is wide open. FSI rule: auth must fail closed even on misconfig.
- **`aws/mcp-servers/sf-auth-proxy/app.py:119`:** `if SF_AUTH_PROXY_KEY and headers.get(...) != SF_AUTH_PROXY_KEY` — if the env var is empty string, internal auth is skipped entirely. Same class of fail-open.
- **`aws/mcp-servers/mulesoft-actions/_mulesoft_client.py:23`:** `MULESOFT_PROCESS_API_BASE` defaults to `https://006-v3-trade-process-api.us-e2.cloudhub.io/api` — a hardcoded CloudHub URL as default. Not a secret but pins an environment; ops drift risk.
- **`aws/cdk/stacks/research_pipeline_stack.py:83`:** `"SF_INSTANCE_URL": "https://placeholder.my.salesforce.com"` — CDK default that would deploy a Lambda with a dead instance URL if the override is forgotten. Should be a required stack parameter with no default.

---

## Area D — Input validation / injection (detail)

**Solid:**
- `_soql_safe.py:_FORBIDDEN_KEYWORDS = re.compile(r"\b(UPDATE|DELETE|INSERT|UPSERT|MERGE|TRUNCATE|--|;)\b", re.IGNORECASE)`; `ensure_read_only()` rejects on match and caps length at 20,000 chars.
- `validate_identifier(allow_dotted=False|True)` uses `^[A-Za-z][A-Za-z0-9_]{0,78}[A-Za-z0-9]$` anchors — no interpolation of arbitrary user input.
- `escape_literal()` double-escapes backslashes, single-quotes, newlines.
- `handle_create_object` / `handle_update_object` in CRM MCP check `persona == "fsi_client_liaison"` → `McpError` (`-32003`). Research is not explicitly blocked from writes at the MCP level, but the skill-level allowlist in `topology.py` prevents research specialists from even reaching `mulesoft_api` / `action_specialist`.
- `mulesoft-actions/app.py` requires `plan_hash` (min len 32) AND `approval_token` (min len 32) for every write; `handle_submit_order` validates side in `{buy, sell}` and `quantity > 0`.
- `_base/mcp_server._handle_call` runs the request body through `ToolCall(**body)` Pydantic model; `ValidationError` → `McpValidationError`.

**Gaps:**
- **`handle_order_status_webhook` accepts `X-Principal-Id` as the ONLY authentication** for an inbound Alpaca callback path (`mulesoft-actions/app.py:170-203`). No plan_hash / approval_token (correctly, since it's not RM-initiated) BUT also no HMAC signature verification against the Alpaca-supplied signature header. The docstring claims the edge handles it ("_authenticated at the API Gateway edge via a shared-secret signature_"); the `mulesoft/process-apis/order-status-webhook/src/main/resources/config.yaml` has an `hmac_secret` placeholder, but the Mule flow `.xml` was not reviewed and the MCP-side handler does no defense-in-depth check. An attacker who reaches this endpoint with any `X-Principal-Id` and a well-formed body can inject order-status events that the skill layer will then record and act on.
- `handle_read_research_briefs_with_exposure` builds a Data Cloud SQL string with **raw string interpolation** of `ticker_filter` and `min_pct` (`salesforce-crm/app.py` near the bottom). `ticker_filter` is pre-validated against `_TICKER_RE.fullmatch()`, and `min_pct` is type-checked as number in `[0,100]`. That validation is tight but it's inside the same file; any future contributor relaxing those checks breaks the SQL safety. Prefer parameterized queries.

---

## Area E — Audit completeness (detail)

**Every attempt produces one audit row.** Confirmed in:
- `compliance_screening/actions.py` — DENY writes `COMPLIANCE_BLOCKED` audit (lines 199-221).
- `hitl/actions.py` — mint writes `DUAL_AUTH_REQUESTED`; verify writes `HITL_APPROVED` on success, `HITL_REJECTED` on any failure mode (tamper, expiry, plan_mismatch, user_mismatch, replay, malformed).
- `dual_auth/actions.py` — request phase writes `DUAL_AUTH_REQUESTED`; resolve writes `DUAL_AUTH_APPROVED` or `DUAL_AUTH_REJECTED`; `NOT_REQUIRED` path writes `DUAL_AUTH_APPROVED` with `outcome=not_required`.
- `mulesoft_api/actions.py` — success/error/OFAC-hit all write. Maps to `TRADE_SUBMITTED`/`WIRE_INITIATED`/`TRADE_REJECTED`/`WIRE_BLOCKED`.
- `publish_brief/actions.py` — writes `RESEARCH_PUBLISHED` with `research_brief_id` back-linked.
- `client_summary`, `research_awareness`, `suitability_check` — write `ADVISORY_QUERY` audit rows with `gate_trace`.

**Audit row schema (`audit_logging/actions.py:run`):**
- `Action__c`, `Principal_Id__c`, `Agent_Id__c`, `Session_Id__c`, `Correlation_Id__c`, `Research_Brief_Id__c`, `Client_Contact_Id__c`, `Linked_Trade_Id__c`, `Linked_Wire_Id__c`, `Approved_By__c`, `Dual_Approver__c`, `Approval_Token_Hash__c` (`sha256:<first-16-hex>`), `MuleSoft_Reference__c`, `Gate_Trace__c` (ordered list), `Payload__c` (MNPI-scrubbed), `Timestamp__c`.
- Raw approval token is **never** written: `hash_token(raw) → "sha256:<hex[:16]>"`.

**Caveats:**
- Audit for a research publish is gated on `publish_brief.run()` being called. That call site is in `research_orchestrator` scaffolding but the orchestrator's `synthesize()` returns text, not a structured `PublishBriefInput`, and nothing in `coordinator._run_one` translates a "publish this brief" decision into a `publish_brief.run()` invocation. Same structural gap as Area B.
- `MNPI scrub is `strict=False` for audit payloads (`audit_logging/actions.py:170`) — insider-hint phrases in a payload get silently replaced with `[INSIDER_REDACTED]` rather than raising. That means an audit row alone cannot prove MNPI did or did not arrive; only the `mnpi_redactions` counter signals something was scrubbed.

---

## Area F — Guardrails (detail)

- `coordinator.py:BedrockConverseClient.converse()` builds `guardrailConfig={guardrailIdentifier, guardrailVersion}` **only when BOTH** `BEDROCK_GUARDRAIL_ID` and `BEDROCK_GUARDRAIL_VERSION` env vars are set. Otherwise the converse call runs with no guardrail. No `RuntimeError` raised on missing config — silent fallback. In production that's a fail-open.
- On `stopReason == "guardrail_intervened"` the client raises `GuardrailInterventionError`; `_invoke_specialist` catches it and returns `WorkerResponse(errors=[AgentError(error_type=SAFETY, recoverable=False)])`. That part is correct.
- Input-side only. Output-side guardrailing is not wired; specialist text goes straight to synthesis.
- No test harness asserts what happens when the guardrail env vars are absent; a reviewer would expect a boot-time fail-fast similar to `resolve_model_id`'s behavior.

---

## Top 5 security/compliance risks

| # | Severity | Risk | Fix here |
|---|----------|------|----------|
| 1 | **CRITICAL** | Seven-gate trust spine is prompt-only. The action_specialist is a Bedrock LLM whose gate sequence is not dispatched into the skill modules at runtime. No audit rows fire on a real RM write request because no skill is actually invoked. A FINRA audit of a submitted trade would find no `IR_Audit_Log__c` trail. | `openclaw/orchestration/coordinator.py` `_run_one()` (~line 425) — add a Bedrock `toolConfig` parameter with `compliance_screening`/`hitl`/`dual_auth`/`mulesoft_api`/`audit_logging` as declared tools, implement a tool-use loop that routes tool_use blocks to `get_skill(name).run(input)`, and enforce the seven-gate order deterministically in code instead of in prose. |
| 2 | **HIGH** | MCP server auth fail-open when env var missing. `aws/mcp-servers/_base/mcp_server.py:145-151`: `if not expected: return`. Same pattern in `sf-auth-proxy/app.py:119`. A config drift in Lambda environment silently removes authentication. | `_base/mcp_server.py:_require_api_key` — remove the dev-mode branch; raise `McpAuthError("MCP_API_KEY not configured")` when env is unset. Same for `sf-auth-proxy/app.py` `lambda_handler`. |
| 3 | **HIGH** | Specialist LLM outputs are not MNPI re-scrubbed before orchestrator synthesis. If a specialist hallucinates a dollar amount or reintroduces redacted fields, it flows through to the synthesized brief/response verbatim. `[MNPI_REDACTED]` is a prompt token with no code enforcement. | `openclaw/orchestration/research_orchestrator.py` `synthesize()` (~line 85) and `advisor_orchestrator.py` `synthesize()` (~line 145) — after extracting `text = r.result.get("text", "")`, run `MNPIFilter(strict=True).scrub_text(text)` and fail the response (or mark `rm_consumable=false`) on `MNPIViolation`. |
| 4 | **HIGH** | Inbound Alpaca order-status webhook at the MCP layer has no HMAC verification. `aws/mcp-servers/mulesoft-actions/app.py:handle_order_status_webhook` relies on `X-Principal-Id` + an edge check that is not visible in code. | `mulesoft-actions/app.py:handle_order_status_webhook` — verify a `X-Alpaca-Signature` header against an HMAC over the body using the secret pulled from Secrets Manager `/006-v3/vendors/alpaca-webhook`. Defense in depth; don't rely on the edge. |
| 5 | **MED** | Bedrock Guardrails are fail-open on missing env. `coordinator.py:BedrockConverseClient.converse()` builds the `guardrailConfig` only when both env vars are set; otherwise the call proceeds unguarded. | `coordinator.py` — at `PersonaCoordinator.__init__` (the same boot-time audit that runs `resolve_model_id`), require `BEDROCK_GUARDRAIL_ID` + `_VERSION` in non-dev mode; raise `RuntimeError` if absent. |

---

## What would block a FINRA-style audit TODAY

1. **No reliable audit trail for writes.** A regulator asking "show me the audit row for this trade ticket" would get nothing, because the action_specialist LLM's stated gate sequence never translates into an actual `audit_logging.run()` call. This is a book-and-records gap under FINRA 4511 / SEC 17a-4.
2. **Cannot demonstrate HITL enforcement.** HITL token logic is bullet-proof (HMAC-SHA256, 5-min TTL, plan_hash binding, single-use via fingerprint store), but there is no code path that requires the token to be verified before MuleSoft is called — the LLM has to "remember" to call `hitl.verify` first. Auditor test: mint a token, never verify it, submit an order; today the system has no runtime enforcement that stops this.
3. **Dual-auth thresholds not enforced at the choke point.** `dual_auth.threshold_required()` is correct and deterministic, but `mulesoft_api.run()` accepts `hitl_approval` alone as sufficient — it does not check that a matching `IR_Pending_Approval__c` row is `APPROVED` before dispatching a `$600K` trade. A regulator probing Reg BI high-dollar safeguards would flag this.
4. **MNPI leakage to the client channel is not enforceable end-to-end.** The CRM MCP redacts; the liaison orchestrator is read-only; the prompts say the right things. But a specialist LLM response that invents a dollar amount reaches the client verbatim because no output-side scrubber exists.
5. **Webhook fan-out path is effectively unauthenticated at the MCP.** An attacker who learns the invoke URL + a valid principal_id can inject order-status events. This is a tampering surface against book-and-records integrity.

## What is already defensible

1. **OFAC SDN screening** is genuinely enforced by code (`mulesoft_api/actions.py:_screen_ofac`) before the wire request leaves the skill; a hit writes `WIRE_BLOCKED` audit and short-circuits — no way for the LLM to skip it because the check runs inside `run()` before the MCP call.
2. **Compliance DENY is a true hard stop** within `compliance_screening.run` — no override flag, no conditional, DENY writes audit + returns. _If_ the skill is called, DENY cannot be softened downstream.
3. **Persona write gate at the CRM MCP** — `fsi_client_liaison` cannot create or update any Salesforce object; the block is server-side, not in the prompt (`salesforce-crm/app.py:handle_create_object` / `handle_update_object` / `_require_writer_persona`).
4. **SOQL injection surface** is genuinely locked down: forbidden-keyword regex, identifier whitelists, literal-escape, length cap, parameterized via `httpx.QueryParams`.
5. **Langfuse scrubbing** happens in a wrapping layer (`_ScrubbingLangfuseWrapper` / `_ScrubbingSpan`) so every `trace/span/update` payload is filtered through `scrub_before_write` before the real Langfuse client sees it. MNPI/PII/token field keys all covered.
6. **HITL token primitives** (HMAC-SHA256, TTL 1..3600s with 5-min default, plan_hash rebinding, single-use fingerprint store, raw-token-never-logged, distinct signing key from session tokens) are the strongest piece of the codebase. Fail-closed on missing key.
7. **Dual-auth distinctness** enforced by a Pydantic model_validator on a frozen model — caller cannot construct a `DualAuthInput` with `second_approver_id == first_approver_id`.
8. **Deterministic suitability check** with a documented rule matrix, pure-function evaluation, no LLM math.
9. **Audit row schema** carries the right FSI fields (cross-persona stitching IDs, gate trace, hashed approval token, MNPI-scrubbed payload).
10. **`.env.example` + `seed-secrets.sh`** wire secrets via AWS Secrets Manager and keep the repo free of credentials.

---

## Summary

The skill-layer trust primitives are authentically built and would pass a code review in isolation. The architectural failure is the orchestrator-to-skill bridge: the action_specialist is a Bedrock LLM sub-agent without a tool-use dispatch loop, so the "seven-gate serial spine" is a system-prompt statement rather than a runtime contract. Until `coordinator._run_one()` (or an equivalent dispatcher) issues Bedrock Converse calls with `toolConfig` and routes tool_use blocks into `get_skill(name).run(...)`, none of the well-built skill-layer defenses can be relied on by an FSI auditor for any real write path. Fix that bridge, close the four HIGH items above, and the stack becomes a credible candidate for a regulated pilot.
