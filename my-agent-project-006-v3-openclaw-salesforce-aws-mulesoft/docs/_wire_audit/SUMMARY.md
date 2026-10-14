# V3 Wire Audit — Consolidated Summary

Six parallel sub-agents reviewed the entire 006 V3 tree. Read-only. No edits, no deploys. Per-section reports live in this directory (A/B/C/D/E/F). This is the synthesis.

Date: April 2026
Scope: `my-agent-project-006-v3-openclaw-salesforce-aws-mulesoft/` — backend + AWS + Salesforce + MuleSoft + frontend + tests/scripts.

## Green verdict up front

The project is more-wired than not. Six sub-agents returned with **zero hardcoded credentials in git, 236/236 backend tests passing, 101/101 frontend tests passing, `cdk synth --all` producing 6 valid CloudFormation templates, `mvn validate` succeeding on all 3 Mule apps.** The 14-agent topology asserts its own integrity at import. The tool-use dispatch loop is live and enforces the 7-gate spine in code, not prompt.

But there are **9 real wire defects that would bite in a live demo**, ordered by bite depth below. Five are fixable in under an hour. Four are structural and worth naming now so they don't surprise you on stage.

---

## Blockers — must fix before live demo

### B1. BFF has import-time-dead handlers. 3 of 4 REST endpoints return empty payloads.
Sub-agent B + D both found this independently.

`aws/mcp-servers/bff/app.py` lines 91, 147, 166 do:
```python
from salesforce_crm_client import call_tool as sf_call
from sec_edgar_client import call_tool as edgar_call
```
Neither module exists anywhere in the repo. The imports are wrapped in `try/except ImportError` with an empty-payload fallback. So the React frontend gets HTTP 200 with no data:
- `/api/inquiries` → `{"items": []}` (AlertQueue shows "no alerts" forever)
- `/api/source_tables/{id}` → `_empty_source_table()` (charts blank)
- `/api/source_chunk/{id}` → `_empty_source_chunk()` (citation drill-downs show "source not available")

Only `/api/session/warm` works.

**Fix cost:** ~80 lines. Create `bff/salesforce_crm_client.py` and `bff/sec_edgar_client.py` as thin httpx wrappers posting to the existing `/mcp/{server}/tools/call` endpoints. Or inline direct httpx calls in each handler.

### B2. `sec-edgar` MCP doesn't register the tools the BFF calls.
Related to B1. Sub-agent D found it.

Even after B1 is fixed, calling `sec_edgar_client.call_tool("get_source_table", …)` and `("get_source_chunk", …)` fails because those tool names are not registered in `aws/mcp-servers/sec-edgar/app.py`. Only `get_latest_filing`, `get_filing_sections`, `get_financial_statements` exist.

**Fix cost:** ~150 lines. Add two tools to sec-edgar MCP that look up pre-indexed table / chunk by `source_id` against the Bedrock KB catalog. Or repoint the BFF to a different backend (e.g. an S3 JSON catalog written by the filings-corpus ingest job).

### B3. MNPI filter does NOT cover the write path (tool-use loop output).
Sub-agent A found it.

`coordinator.py:484` applies `MNPIFilter(strict=False).scrub_text(text)` to read-path converse returns. But `coordinator.py:451-461` (the tool-use loop branch) returns `loop_result.text` directly into `WorkerResponse.result["text"]` with **zero scrubbing**. The `action_specialist` (write-path agent) is the one place this matters most, and it's the one place the scrub is missing.

A hallucinated "recommend wiring $450,000 to Beneficiary X" from the action_specialist would reach the orchestrator synthesizer unscrubbed. Upstream CRM redaction catches structured MNPI fields; this gap is LLM-output free text.

**Fix cost:** ~6 lines. Add the same `MNPIFilter(strict=False).scrub_text(loop_result.text)` call at `coordinator.py:452` that exists at line 484.

### B4. `GateEnforcer` defined, never called. Agent-level MCP allowlist is prompt-advisory.
Sub-agent A found it.

`openclaw/trust/gate_enforcer.py` defines `check_tool()`, `check_mcp()`, `check_write_safe()`. Grep shows zero production callers — only `tests/unit/test_trust.py` uses it. Meaning: the `mcp_allowlist` in `topology.py` (e.g. `action_specialist.mcp_allowlist=["salesforce-crm","mulesoft-actions"]`) exists in config but is not enforced at runtime.

The tool-use loop has its own allowlist at `tool_dispatch.py:293-307` which covers the tool side. MCP calls happen inside skills (e.g. `await client.call(server="salesforce-crm", ...)`) with no gate check.

Severity note: for V3 demo this is mostly moot — the read-path has no `toolConfig` so the model has no tools to misuse, and `check_write_safe()` just guards READ_ONLY agents which the write path never touches. But the invariant is absent. A skill calling an out-of-allowlist MCP server would silently succeed.

**Fix cost:** ~30 lines. Wire `GateEnforcer.check_mcp(agent_id, server)` into `openclaw/skills/_mcp_client.py::MCPClient.call()` with a per-session context variable for the active agent_id. Or accept that enforcement happens at the network boundary (IAM, VPC) and delete the unused trust classes to avoid dead-weight.

### B5. `SessionTokenMinter.verify()` never called.
Sub-agent A found it.

Same pattern as B4. Session tokens are produced by the channel adapter (external) and passed in via `SessionContext`, but there is no in-tree verification call on the token. If the channel adapter forgets to verify, session tokens flow through unchecked.

**Fix cost:** boot-time assertion in `PersonaCoordinator.__init__` that the caller passes a verifier callback, OR a hook in `run_turn()`. Either way ~15 lines.

---

## Data-shape drift — will lose data silently on first SF deploy

### D1. `IR_Audit_Log__c` — 7 fields Python writes don't exist in XML.
Sub-agent C found it.

`audit_logging/actions.py` writes these keys that have no `field-meta.xml`:
- `Agent_Id__c`
- `Session_Id__c`
- `Correlation_Id__c`
- `Linked_Trade_Id__c`
- `Linked_Wire_Id__c`
- `Approval_Token_Hash__c`
- `Payload__c`

Effect: deploys succeed (SF REST silently drops unknown keys), but audit rows are missing the cross-persona stitching fields and the approval-token fingerprint. Steering rule 22 ("approval tokens are hashed before write") becomes a write that goes nowhere.

**Fix cost:** 7 new field-meta.xml files. ~5 min.

### D2. `IR_Pending_Approval__c` — 8 Python-written fields don't exist in XML.
Sub-agent C found it.

`dual_auth/actions.py` writes 10 fields; only `Status__c` matches the XML. Python uses `Plan_Hash__c`, XML has `ActionPlan_Hash__c`. Python uses `First_Approver__c` + `Second_Approver__c`, XML has one `Senior_Approver_Id__c`. Python writes `Notional_Usd__c`, `Thresholds__c`, `Requested_At__c`, `Resolved_At__c`, `Senior_Permset_Held__c`, `Action_Type__c` — all absent.

Effect: dual-auth records are nearly empty after a real deploy. Narrative 5's dual-auth gate looks broken from a FINRA audit standpoint even though the flow runs.

**Fix cost:** 8-9 field renames/additions in SF metadata, or rename Python to match. Either direction is ~15-30 min of edits plus a re-deploy.

---

## Config drift — confusing but non-blocking

### C1. Bedrock model IDs in `.env.example` are raw, not inference profiles.
Sub-agent E found it. Already flagged in previous sessions.

Current `.env.example`:
```
BEDROCK_SONNET_MODEL_ID=anthropic.claude-sonnet-4-6-20260215-v1:0
BEDROCK_HAIKU_MODEL_ID=anthropic.claude-haiku-4-5-20251022-v1:0
```
Required:
```
BEDROCK_SONNET_MODEL_ID=us.anthropic.claude-sonnet-4-6
BEDROCK_HAIKU_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
```
On-demand converse with raw IDs returns `ValidationException`. Verified live against the target AWS account.

**Fix cost:** 2-line edit.

### C2. `.env.example` missing 7 operator-facing vars.
Sub-agent E found it.

`BEDROCK_GUARDRAIL_ID`, `BEDROCK_GUARDRAIL_VERSION`, `SF_AUTH_PROXY_URL`, `CORS_ALLOW_ORIGIN`, `OPENCLAW_DEV`, `MCP_DEV_MODE`, `SEC_EDGAR_UA` — all read by code, none declared in the template. Plus no `frontend/.env.example` for the 3 `VITE_*` vars the SPA consumes.

**Fix cost:** 2 file edits, ~20 lines total.

### C3. Skill count is advertised differently in three places.
Sub-agent A found it.

- `openclaw/skills/_registry.py::_SKILL_MODULES` → **14 skills**
- `openclaw/openclaw.json` skills map → **16 entries** (adds `research_prompt`, `rm_handoff`, `mnpi_filter`)
- `openclaw/orchestration/tool_dispatch.py::_DESCRIPTIONS` → **13 entries** (omits `compliance_sweep`)
- `openclaw/__init__.py` docstring → "17 agents"

The runtime source of truth is `_SKILL_MODULES` (14). Everything else disagrees.

Consequence today: harmless — `compliance_sweep` isn't in any agent's `tool_allowlist`, so the tool-use loop doesn't need its description. If that changes, `build_tool_config()` will silently drop the tool with a debug log.

**Fix cost:** align all 3 sources. ~15 min.

### C4. `rm_handoff` skill declared, module missing.
Sub-agent A + F found it.

Referenced in:
- `openclaw.json:113` (as a persona-scoped skill)
- `topology.py:255` (in liaison orchestrator's `tool_allowlist`)
- Narrative 2 documentation

Missing:
- `openclaw/skills/rm_handoff/actions.py` does not exist
- Not in `_SKILL_MODULES`

Effect on Narrative 2: the client→RM handoff path has no dedicated skill. The `Client_Inquiry__c` creation happens via the context_specialist + manual SF writes, not via a deployed skill. Narrative 2 runs but looks hand-wavy.

**Fix cost:** ~150 lines to create the skill properly. Or remove from openclaw.json + topology.py and document that the handoff is prompt-driven. ~5 min for the removal path.

### C5. `dynamodb` MCP server called but not declared.
Sub-agent F found it.

`compliance_sweep/actions.py` calls `await client.call(server="dynamodb", ...)` for its idempotency layer. `openclaw.json::mcp.servers` declares 5 servers (market-data, sec-edgar, news-search, salesforce-crm, mulesoft-actions) — no dynamodb.

In tests, `MockMCPRouter` registers a handler. In prod, the call would fail with "no MCP server for 'dynamodb'".

Actually re-reading: the compliance_sweep can run in prod with `get_shared_mock_client()` as the fallback — the mock router returns the skipped-idempotent path. But the real DynamoDB-based idempotency claimed in Narrative 3 isn't wired.

**Fix cost:** either add a `dynamodb` MCP server Lambda (~200 LOC) or rewrite `compliance_sweep` to use boto3 directly (~20 LOC). The skill is running in AWS Lambda where boto3 is available anyway — direct boto3 is the right call.

---

## Minor stuff (won't break the demo but should be fixed in V3.1)

- Two HMAC-SHA256 implementations with duplicated helpers and inconsistent key-length checks (`idp_session.py` + `hitl/_tokens.py`). Sub-agent A, D9.
- `ResearchBriefTrigger.trigger` sits under `salesforce/.../classes/` instead of `triggers/`. Works via meta.xml but breaks convention. Sub-agent C.
- MCP `handle_order_status_webhook` POSTs `/orders/{id}/webhook`, Mule webhook RAML is `POST /webhooks/orders`. Dead path — webhook is inbound only in practice — but misleading code. Sub-agent C.
- Case drift: Python uses `MuleSoft_Reference__c`, XML uses `Mulesoft_Reference__c`. SF API is case-insensitive so it works. Sub-agent C.
- `ConversationPanel.tsx` fallback `ownApproval` has no reconciler — stranded `optimistic` state if parent omits `approval` prop. Dead branch (AdvisorScreen always passes the prop). Sub-agent D.
- Liaison `_mnpi_tripwire` duplicates a subset of `MNPIFilter` with narrower regexes. Should just call the shared filter. Sub-agent A, D7.
- Root `.gitignore` doesn't block `.env` / `.env.local` / `*.pem` / `*.key`. The v3-folder `.gitignore` does. If anyone `git add`s from repo root, the safety net isn't there. Sub-agent E.
- `requirements.txt` ships pytest + pytest-asyncio into the prod image. Split dev deps. Sub-agent E.

---

## Narrative readiness after this audit

| # | Narrative | State | Live-ready? |
|---|---|---|---|
| 1 | Earnings Morning | Complete end-to-end. Parallel fanout, citation harness, brief publish, audit row. | **YES** — will run end-to-end live once SF org + secrets are seeded. |
| 2 | Client drives research | Read path works. Write path reuses Narrative 5. **Gaps:** `rm_handoff` skill missing, `Research_Request__c` SObject missing. | **PARTIAL** — demo shows via pre-seeded `Client_Inquiry__c` rows rather than the hand-off emitting them. |
| 3 | Risk Alert | Code complete. `monitor.py` → SQS → `sweep_dispatcher` → `compliance_sweep` → SF writes → Apex trigger → PE. **Gaps:** `dynamodb` MCP server undeclared (idempotency degrades); no channel-side PE consumer. | **STAGED** — narrative arc itself marks this V4 roadmap. Manual trigger works. |
| 4 | Demand Signal | UI tab + pre-seeded data only. No clustering. | **ROADMAP** — explicit per narrative arc. |
| 5 | Large Liquidation | 7-gate tool-use loop is real in code. Gates: compliance_screening, hitl, dual_auth, mulesoft_api × 2 (submit_order + initiate_wire), audit_logging. OFAC screen live. MuleSoft branches on `MULESOFT_MODE`. | **YES in mock mode**; **PARTIAL in live** (needs CloudHub deploy of the 3 Mule apps + Anypoint Connected App creds). |

---

## Priority-ordered fix list

If you want to close every finding before live demo, here's the order by impact × cost:

| # | Fix | Why | Effort |
|---|---|---|---|
| 1 | B3 — MNPI scrub on tool-use output | Trust invariant; one-line location | 6 LOC |
| 2 | C1 — Model ID defaults to inference profiles | First live Bedrock call fails without this | 2 LOC |
| 3 | B1 + B2 — BFF handlers + missing sec-edgar tools | Three of four UI routes are dead | 230 LOC |
| 4 | D1 — Add 7 missing IR_Audit_Log__c fields | Audit rows are incomplete | 7 XML files |
| 5 | D2 — Reconcile IR_Pending_Approval__c field names | Dual-auth rows look broken | 8-9 fields either way |
| 6 | C2 — Add 7 missing env vars to `.env.example` + frontend/.env.example | Prevents fail-fast guardrail crash on first non-dev boot | 2 files |
| 7 | C5 — Replace `dynamodb` MCP call with boto3 in compliance_sweep | Real idempotency for Narrative 3 | 20 LOC |
| 8 | C3 — Align skill-count across 4 sources | Documentation drift | 15 min |
| 9 | B4 + B5 — GateEnforcer + SessionTokenMinter wired or removed | Trust invariants promised but not enforced | 45 LOC or delete |
| 10 | C4 — `rm_handoff` skill build-or-delete | Narrative 2 cleanliness | 150 LOC or 5 min delete |

Items 1-4 are the ones that would actually break a live demo. Items 5-10 are correctness/cleanliness.

---

## What to say on stage

You can honestly describe V3 as:

- **Three personas, 14 agents, 14 skills, real tool-use dispatch loop, parallel fanout on reads, serial 7-gate spine on writes, OFAC-screened wires, audit row per gate, 236 backend tests green, 101 frontend tests green, six CDK stacks + one SAM stack + three MuleSoft Maven projects all build clean.**

Don't say:
- "Every MNPI leak path is covered" — the write-path tool-use output isn't scrubbed yet.
- "Every trust invariant is runtime-enforced" — `GateEnforcer` and `SessionTokenMinter` are defined but never called.
- "Citation drill-down lights up in the UI" — the BFF returns empty table/chunk data until B1+B2 are fixed.

The five live-demo-blocking items (MNPI-on-tool-use, inference-profile model IDs, BFF handlers, sec-edgar tools, audit-log field gaps) are **3-5 hours of focused work** combined. Everything else is non-blocking polish.
