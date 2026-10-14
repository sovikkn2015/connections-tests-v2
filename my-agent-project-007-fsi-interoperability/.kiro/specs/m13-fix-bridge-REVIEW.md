# M13 FIX Bridge — LLMJ Review v1

> Reviewer: Self-LLMJ (harsh, specific, scored)
> Spec version reviewed: v1 dated concurrent with review
> Review date: M13 Phase-4 build cycle

---

## Scoring dimensions (weighted total /10)

| Dim | Weight | Score | Weighted |
|---|---|---|---|
| Completeness | 25% | 6.5 | 1.625 |
| Accuracy (vs steering rules) | 20% | 7.0 | 1.400 |
| Security (credentials/MNPI/boundaries) | 20% | 7.0 | 1.400 |
| Testability (ACs deterministic) | 15% | 7.5 | 1.125 |
| Design alignment (ARCH-09 + Rule 11) | 10% | 8.0 | 0.800 |
| Gaps called out | 10% | 6.0 | 0.600 |
| **TOTAL** | | | **6.95 / 10** |

**Verdict:** CONDITIONAL GO. Address 9 required fixes + 4 recommended before re-review.

---

## REQUIRED fixes (blocking)

### Q1. FakeFixEngine deterministic ExecReport generation is underspecified

R6 says ExecReport ingestion forwards to audit, but the spec never defines how the FakeFixEngine simulates inbound ExecReports for tests. Without this, the drop-copy tests can't be written deterministically. **Fix:** add `FakeFixEngine.simulate_exec_report(venue, exec_report_dict)` to the engine protocol. Document in D7 that drop-copy tests drive inbound via this hook.

### Q2. `fix.kill_switch` tool input schema missing

R7.5 describes the toggle API but doesn't define a pydantic input model in R10. The models.py schema list is silent on it. **Fix:** add `KillSwitchInput` to R10 with fields `{scope: Literal["global","venue"], venue: Optional[str], state: Literal["on","off"], reason: str}`, plus cross-field validation: `venue` required iff `scope=="venue"`, `reason` min length 8.

### Q3. AID verification path + header not fully specified

R13 refers to `X-Agent-AID` but doesn't state: (a) what HTTP status on missing header (200 with isError per MCP envelope? or 401?), (b) which claims key holds the role (`role`?), (c) what happens on JWT decode failure, (d) whether every tool call requires AID or only kill_switch. **Fix:** clarify:
- Every tool call (all 6) requires X-Agent-AID; missing header → `unauthorized` via MCP envelope (HTTP 200 isError=true).
- JWT claim shape: `{sub: str, aid: str, role: str, tenant_id: str, firm_id: str, iat: int, exp: int}`.
- Role gate only enforced for `fix.kill_switch`; other tools require any valid AID.
- `tenant_id`/`firm_id` extracted from AID and passed into audit events (avoids client-spoofed headers).

### Q4. Drop-copy "account hashing" not deterministic

R6.3 says accounts are hashed SHA-256 first 16 hex chars but doesn't specify salt. Unsalted SHA-256 on account numbers is reversible via rainbow table. **Fix:** use HMAC-SHA256 with a per-tenant hashing salt pulled from Vault at `FIX_ACCOUNT_HASH_SALT_VAULT_PATH`. Tests can inject a static salt. Document in R6.3 + D10.

### Q5. Helm template count and names inconsistent

Spec §Scope says 9 templates in the sub-chart, then lists 11 items (statefulset, service-headless, service, serviceaccount, networkpolicy, pdb, certificate, externalsecret, configmap + _helpers.tpl which is a helper not a template). The task description says 9. **Fix:** state 10 k8s templates + 1 _helpers.tpl = 11 files total. Explicitly list: Chart.yaml, values.yaml, _helpers.tpl, statefulset.yaml, service.yaml, service-headless.yaml, serviceaccount.yaml, networkpolicy.yaml, pdb.yaml, certificate.yaml, externalsecret.yaml, configmap.yaml.

### Q6. `fix.session_status` input validates venue but doesn't say what "venue not found" returns

R2.5 doesn't specify error behavior for unknown venue. **Fix:** `session_status` for unknown venue returns AdapterError `session_not_found` via MCP envelope. For known-but-not-yet-connected venue, returns `{logon_status:"DISCONNECTED", seq_num_in:0, seq_num_out:0, last_heartbeat_ts:null}`.

### Q7. Missing spec for pod-lifecycle when FIX_ENABLED=false

R4.1 says "with FIX_ENABLED=true, pull session config and open sessions." But what about `FIX_ENABLED=false`? Startup behavior and tool behavior are unspecified. **Fix:** when `FIX_ENABLED=false`: sessions are NOT opened, `session_status` returns `{logon_status:"DISCONNECTED", ...}` for any configured venue, order_* tools return `fix_enabled_false` error. `GET /` returns 200 `{status:"ok", checks:{"fix":"disabled"}}`.

### Q8. Multi-session-in-one-pod concurrency safety is hand-waved in D8

D8 says "no shared mutable state except the read-only venue registry" but the KillSwitch is shared mutable state and crosses venues. **Fix:** explicitly call out that KillSwitch and drop-copy emitter are the only shared mutables; KillSwitch uses a single threading.Lock around its state file write, and the emitter uses AuditEmitter's own stdout lock (same pattern as M11 audit_emitter.py).

### Q9. Test bundle pytest invocation command not matching spec

Scope says `pytest tests/unit/test_m13_fix_*.py tests/unit/test_m13_drop_copy.py tests/unit/test_m13_kill_switch.py tests/integration/test_m13_integration.py tests/security/test_m13_boundary.py`. But spec includes test_m13_config.py which doesn't match `test_m13_fix_*` glob. **Fix:** either rename `test_m13_config.py` to `test_m13_fix_config.py` OR extend the verification-gate command to include it. Choosing rename for consistency with `fix_*` prefix family.

---

## RECOMMENDED fixes (non-blocking but would raise score)

### Q10. Drop-copy field `trader_aid` vs `sender_comp_id` ambiguous

R6.1 emits `trader_aid` but ExecReport doesn't carry AID — only SenderCompID/TargetCompID. Resolve: `trader_aid` is the AID of the trader who submitted the PARENT order (extracted from the outbound order dispatch audit and correlated via cl_ord_id). If no parent found (inbound ExecReport on a cl_ord_id we didn't send), emit `trader_aid=null` and log a warning.

### Q11. Session-config vault path YAML schema not typed

R4.1 mentions YAML list. Add an explicit pydantic model (`VenueConfig`) with fields: `venue`, `sender_comp_id_path`, `target_comp_id_path`, `host`, `port`, `heartbeat_interval_s`, `reset_on_logon`, `use_tls`, `cert_path_vault_path`, `key_path_vault_path`, `ca_path_vault_path`. Validate at startup; invalid config → refuse-to-start (fail-closed Rule 8).

### Q12. FIX 4.4 vs 4.2 — task header says 4.4, ARCH-07 mentions 4.2 broker FIX

ARCH-07 says "FIX 4.2 TCP". Task says FIX 4.4. Resolve: task scope-line is authoritative since it's the build instruction; spec explicitly pins 4.4 (more common in 2026 and simplefix defaults). Note that 4.2 support can be added in v2 by swapping FIX version tags in message builder. Add to §5 non-goals.

### Q13. Integration test for Vault mapping

The spec doesn't require a test that verifies the YAML-from-Vault config is parsed and each venue comes up. Add one to test_m13_integration.py that uses a fake vault client to supply YAML, asserts `session_status` on each venue after startup returns ACTIVE.

---

## Going to v2 with these 9 required fixes

All 9 are concrete edits. The spec is structurally sound — Requirements, Design, Tasks sections are complete, traceability matrix exists, module boundary is called out, FIX MsgType matrix is present. The gaps are in (a) input models for the kill switch tool, (b) AID/header mechanics, (c) FakeFixEngine simulation hooks, (d) hash salt, (e) FIX_ENABLED=false mode, (f) template inventory clarity, (g) concurrency callout, (h) test filename, (i) session_status error cases.

Post-fix estimated score: **8.3-8.6 / 10 GO.**
