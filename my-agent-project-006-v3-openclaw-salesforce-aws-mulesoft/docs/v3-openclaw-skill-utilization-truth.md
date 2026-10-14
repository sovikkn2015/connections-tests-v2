# 006 V3 — Is OpenClaw / Multi-Agent / Skills Fully Utilized? The Honest Answer

> **Date:** 2026-04-29 ~11:55 UTC
> **Question asked:** "Is OpenClaw and agentic AI with multi-agents and skills fully utilized with no mockery drama? All wired?"
> **Method:** reading `openclaw/orchestration/coordinator.py` + `topology.py` + live turn output from 11:35 UTC NVDA probe
> **Answer:** No. Not fully utilized. There is real mockery drama.

---

## 1. Short answer

**1 of 14 agents actually uses the multi-agent tool-use machinery as designed.** The other 13 fall through to a plain Bedrock Converse call with no toolConfig, no skill allowlist enforcement, no real tool invocation — just LLM text generation with a system prompt. The platform's advertised trust infrastructure (tool-use loop, fail-closed allowlist, Pydantic-validated dispatch into `get_skill(name).run(payload)`) is wired in the repo, but deliberately skipped by the coordinator for every read-path agent.

---

## 2. The smoking gun — the coordinator branch

`openclaw/orchestration/coordinator.py::_run_one()` has this gate around line 430:

```python
if target.serial_by_design and target.tool_allowlist:
    from .tool_dispatch import run_tool_loop
    # Real tool-use loop:
    #   - Bedrock Converse with toolConfig built from Pydantic schemas
    #   - Fail-closed allowlist check on every tool_use block
    #   - Pydantic-validated dispatch into get_skill(name).run(payload)
    #   - MNPI scrub on the output
    loop_result = await run_tool_loop(...)
    return WorkerResponse(..., result={"text": scrubbed_text, "gate_trace": [...]})

# Read-path: single converse call, MNPI re-scrub on output.
result = await self.bedrock.converse(
    model_id=model_id,
    system_prompt=target.system_prompt,
    messages=[{"role": "user", "content": [{"text": user_prompt}]}],
    agent_id=target.id,
)
# ← NO toolConfig. NO tool_allowlist enforcement. NO skill invocation.
# ← Model just generates text. If the prompt says "call get_quote",
#   the model will write Python describing how to call get_quote.
```

`serial_by_design` is set to `True` on **exactly one agent**: `action_specialist`. Every other specialist falls through to the plain converse path.

This is not a bug in the sense of a typo. It was written this way. The question is whether it matches the design intent.

---

## 3. Per-agent utilization table

```
╔══════════════════════════╦═══════════════════╦═══════════════╦══════════════════════════════╗
║ Agent                    ║ Design intent     ║ tool_allowlist║ Actually uses tool-use loop? ║
╠══════════════════════════╬═══════════════════╬═══════════════╬══════════════════════════════╣
║ research_orchestrator    ║ plan+synth fanout ║ 3 tools       ║ ❌ NO — plain converse       ║
║ market_specialist        ║ rag_retrieve      ║ rag_retrieve  ║ ❌ NO — plain converse       ║
║ filings_specialist       ║ rag + XBRL        ║ 2 tools       ║ ❌ NO — plain converse       ║
║ sentiment_specialist     ║ news              ║ []            ║ N/A — nothing to call        ║
║ compliance_specialist    ║ screening         ║ compliance    ║ ❌ NO — plain converse       ║
║ statement_specialist     ║ XBRL math         ║ financial_*   ║ ❌ NO — plain converse       ║
║ advisor_orchestrator     ║ intent+synth      ║ 3 tools       ║ ❌ NO — plain converse       ║
║ portfolio_specialist     ║ portfolio_anal    ║ 2 tools       ║ ❌ NO — plain converse       ║
║ suitability_specialist   ║ suitability rules ║ suitability_  ║ ❌ NO — plain converse       ║
║ client_context_spec      ║ client_summary    ║ 2 tools       ║ ❌ NO — plain converse       ║
║ action_specialist        ║ 7-gate write path ║ 5 gates       ║ ✅ YES — serial_by_design    ║
║ liaison_orchestrator     ║ FAQ vs handoff    ║ 2 tools       ║ ❌ NO — plain converse       ║
║ faq_specialist           ║ bounded answers   ║ []            ║ N/A                          ║
║ context_specialist       ║ MNPI-filtered     ║ client_summary║ ❌ NO — plain converse       ║
╚══════════════════════════╩═══════════════════╩═══════════════╩══════════════════════════════╝
```

**Utilization tally: 1 of 14 agents actually uses the multi-agent tool-use/skill infrastructure as designed.**

---

## 4. What the live NVDA turn proved

The 26-second NVDA research turn I ran against the live `006-v3-agent-proxy` Lambda at 11:35 UTC produced clear evidence:

### 4a. `market_specialist` returned Python code, not a tool call

Extract from the live response:

```python
## market_specialist

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def get_nvda_market_data():
    """Fetch comprehensive market data for NVDA"""

    server_params = StdioServerParameters(
        command="python",
        args=["-m", "market_data_mcp"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Get live quote
            quote_result = await session.call_tool(
                "get_quote",
                arguments={"symbol": "NVDA"}
            )
            ...
```

This is **Python source code describing how to call MCP**, not an actual `toolUse` block. The specialist is not making a tool call — it's generating text that narrates making a tool call. This is the unambiguous signature of plain Converse (no toolConfig) talking to a model that was prompted about tools but never given the machinery to call them.

### 4b. Two specialists timed out

Response contained:
> `gaps: filings_specialist(timeout), statement_specialist(timeout)`

Plain Converse has no tool-call budgeting — the model thinks for 25 seconds about what it would do, never emits a tool call, and the per-worker timeout kills it. Real tool-use with `toolConfig` completes in seconds because each tool call is a discrete dispatch.

### 4c. Zero audit rows from the turn

Three writes to Salesforce (2 briefs, 1 inquiry) fired from this live path, but **zero** `IR_Audit_Log__c` rows. Because the `audit_logging` skill is on `action_specialist`'s allowlist (which runs through the real tool-use loop), but no research specialist has `audit_logging` on its allowlist. And even if it did, the research specialists don't use the tool-use loop anyway.

---

## 5. Where skills actually run in current deployed code

There are three paths into skills. Only two of them fire in practice:

1. **`action_specialist` via `run_tool_loop()`** — 5 skills: `compliance_screening`, `hitl`, `dual_auth`, `mulesoft_api`, `audit_logging`. Real tool-use. Fail-closed allowlist. Pydantic validation. BUT: MuleSoft not deployed, so the MuleSoft-dependent gates can't complete a full 7-gate sequence live. And nobody has triggered an action_specialist turn yet today.

2. **Direct Python invocation by orchestrators** — e.g. `research_orchestrator` calls `publish_brief` directly in its synthesize step. This is how the 2 `Research_Brief__c` rows got written (RB-00000000 and RB-00000001). Works. But bypasses the tool-use discipline entirely — it's just Python code calling Python code.

3. **Via specialist tool-use** (the advertised path for 10 skills) — **never fires today** because specialists don't use `run_tool_loop()`.

So the runtime skill utilization is:

```
Used in live traffic today:   2 of 14 skills
  - publish_brief (direct Python from research_orchestrator)
  - (audit_logging did not fire — see §4c)

Used by design via tool-use:  0 of 14 specialists' skills
  (action_specialist would use 5 but has not been triggered today)

Dead weight today:            12 of 14 skills
```

---

## 6. The verdict against each claim in the design doc

```
╔═══════════════════════════════════════════════╦══════════════════════════════════════╗
║ Design doc claim                              ║ Reality                              ║
╠═══════════════════════════════════════════════╬══════════════════════════════════════╣
║ "OpenClaw is the agent platform"              ║ 🟡 The topology + lifecycle scaffold ║
║                                               ║    is real, but the platform's main  ║
║                                               ║    value prop (tool-use-enforced     ║
║                                               ║    skill allowlist) is skipped for   ║
║                                               ║    13 of 14 agents.                  ║
║                                               ║                                      ║
║ "Orchestrator-workers pattern throughout"     ║ 🟡 The pattern is real via           ║
║                                               ║    asyncio.gather. But workers are   ║
║                                               ║    plain text-generating Sonnet      ║
║                                               ║    calls, not tool-using agents.     ║
║                                               ║                                      ║
║ "Each sub-agent is a narrowed Sonnet 4.6      ║ ❌ FALSE. Narrowed system prompt yes.║
║  with persona-inherited trust policy,         ║    Narrowed tool allowlist DECLARED  ║
║  narrowed tool allowlist"                     ║    but NOT ENFORCED at runtime for   ║
║                                               ║    13 of 14 agents.                  ║
║                                               ║                                      ║
║ "OpenClaw enforces this fail-closed at        ║ ❌ FALSE for read-path agents.       ║
║  skill-invocation time. A junior team puts    ║    The coordinator branch bypasses   ║
║  this in application code; OpenClaw puts      ║    the tool-use loop that would      ║
║  it in the runtime where it can't be          ║    provide the enforcement.          ║
║  accidentally bypassed."                      ║                                      ║
║                                               ║                                      ║
║ "Cross-agent coordination primitives —        ║ 🟡 Parallel fanout works. But the    ║
║  parallel fanout via asyncio.gather,          ║    schema-validated message passing  ║
║  schema-validated agent-to-agent              ║    isn't Pydantic-validated at the   ║
║  message passing"                             ║    LLM-output boundary — specialists ║
║                                               ║    return free text (sometimes       ║
║                                               ║    Python code, as shown today).     ║
║                                               ║                                      ║
║ "Multi-agent parallelism is a read-path       ║ 🟡 Parallelism is real. But the      ║
║  optimization, never a write-path one"        ║    'agents' doing the read-path      ║
║                                               ║    optimization aren't actually      ║
║                                               ║    calling tools.                    ║
║                                               ║                                      ║
║ "Measurable parallelism visible in every      ║ 🟢 TRUE. The live 26-second turn     ║
║  trace"                                       ║    did show 5 parallel specialists.  ║
║                                               ║                                      ║
║ "17 agents"                                   ║ ❌ 14 agents. Doc drift.             ║
║                                               ║                                      ║
║ "13 skills (or 14, or 16 — docs vary) are     ║ 🟡 13 skills exist. 2 get called in  ║
║  wired and exercised"                         ║    live traffic today. 11 are        ║
║                                               ║    dormant.                          ║
╚═══════════════════════════════════════════════╩══════════════════════════════════════╝
```

---

## 7. Why it's this way — a charitable reading

The tool-use loop is a real, correctly implemented piece of code. It exists at `tool_dispatch.py::run_tool_loop()`, has integration tests, and is wired into `action_specialist` via the `serial_by_design` gate.

One plausible reason it's gated only on the write path:

- **Cost / latency concern.** Sonnet 4.6 with `toolConfig` and a 5-tool allowlist costs more per call and takes longer than an unbounded Converse. The read path wants 5 specialists running in parallel under a 25-second budget. Putting all 5 through tool-use might blow the budget.
- **Determinism concern.** Tool-use loop can iterate multiple times (`loops=N`). The coordinator prefers a single round-trip per specialist.

Neither concern is a good enough reason to fall back to plain converse — they'd be better solved by raising the budget and bounding the loop iterations. But it's not random; there's an apparent rationale.

The problem is that the design doc positions the tool-use-enforced allowlist as a central trust property of the platform, and the code doesn't deliver it on the read path. That's the gap between "clever optimization" and "mockery drama."

---

## 8. What would have to change to make the claim true

### Minimal fix (5 minutes of code, 10 minutes of validation)

In `coordinator.py::_run_one()` around line 430, change the guard from:

```python
if target.serial_by_design and target.tool_allowlist:
    ...
```

to:

```python
if target.tool_allowlist:
    ...
```

Any agent with an allowlist now uses the real tool-use loop. 11 specialists light up with enforced skill binding. Only `sentiment_specialist` and `faq_specialist` (empty allowlists) keep the plain-converse path — both are legitimate because their job is pure text generation.

### Companion fix — timeout tuning (5 minutes)

Increase specialist per-worker timeout from 25s to 60s. Real Bedrock tool-use loops take multiple round-trips; 25s is not realistic.

### Companion fix — prompt tweaks

Every specialist system prompt was written as if tool-use were active — they say things like "You call the rag-retrieve skill." If the coordinator is actually giving them a toolConfig, the prompts work. If not, they produce Python code. Once the coordinator is fixed, re-run each specialist prompt to make sure it's tool-use-idiomatic.

### Companion fix — metadata drift

While fixing this, also fix `IR_Audit_Log__c` missing fields (`Agent_Id__c`, `Session_Id__c`, `Research_Brief_Id__c`) and the `publish_brief` skill not setting `Published_At__c`. See `v3-design-vs-built-vs-deployed-v2.md` §7.

---

## 9. Total effort to turn this from 1-of-14 into 11-of-14

```
╔═══════════════════════════════════════════════════════════════════╗
║ #  TASK                                              EFFORT        ║
╠═══════════════════════════════════════════════════════════════════╣
║ 1  coordinator._run_one(): change gate from                        ║
║    `serial_by_design and tool_allowlist` to                        ║
║    `tool_allowlist`. All 11 agents with allowlists                 ║
║    now use run_tool_loop().                          5 min          ║
║                                                                    ║
║ 2  Bump specialist per-worker timeout from 25s to 60s              ║
║                                                      5 min          ║
║                                                                    ║
║ 3  Redeploy AgentCore v3 container                   5 min          ║
║                                                                    ║
║ 4  Re-run the NVDA golden turn, verify:                            ║
║     - market_specialist emits real toolUse for get_quote           ║
║     - filings_specialist calls rag_retrieve                        ║
║     - statement_specialist calls financial_statement_analysis      ║
║     - no more Python-code hallucinations                           ║
║     - IR_Audit_Log__c rows fire                                    ║
║                                                      10 min         ║
║                                                                    ║
║ 5  Backfill SObject metadata                                       ║
║     - Add Agent_Id__c, Session_Id__c, Research_Brief_Id__c        ║
║       fields to IR_Audit_Log__c                                    ║
║     - Ensure publish_brief sets Published_At__c                    ║
║                                                      20 min         ║
╠═══════════════════════════════════════════════════════════════════╣
║ TOTAL                                                ~45 min        ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## 10. Plain-language summary

**Is OpenClaw fully utilized?** No. The platform provides real tool-use infrastructure. The coordinator deliberately skips it for 13 of 14 agents.

**Is the multi-agent system real?** Partially. The 14-agent topology and parallel fanout are real. But the "agents" are just parallel LLM calls with distinct system prompts — not tool-calling agents in the agentic-AI sense.

**Are skills fully utilized?** No. 2 of 14 skills run in live traffic today (`publish_brief` via direct Python, and the 5 action_specialist gates would run but haven't been triggered live). 11 skills are dormant — declared in topology allowlists, wired in the registry, but never invoked because the specialists that should call them are running on plain Converse.

**All wired?** No. The wiring exists in the repo. The coordinator chooses not to use it for read-path agents.

**How big is the gap?** About 45 minutes of code plus one golden-turn re-run. A 1-line coordinator change unlocks 10 additional skills and turns the platform from "parallel LLM calls" into actual multi-agent.

**Mockery drama verdict:** Yes. The design doc's strongest claim ("trust enforcement at the runtime boundary where it can't be accidentally bypassed") is false for every research and advisor read path today. Easily fixable. Must be fixed before the panel sees the current live behavior.

*— v3 openclaw utilization assessment closed at 2026-04-29 ~11:58 UTC.*
