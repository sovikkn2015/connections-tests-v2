# v4 Langfuse Prompt Management — Setup Playbook

**Roadmap item #4** — replace hardcoded specialist prompts in
`openclaw/orchestration/topology.py` with prompts fetched from Langfuse
cloud at runtime. Enables prompt edits in seconds (no container rebuild),
full revision history, A/B labels, and per-environment overrides.

**Status:** scaffold + unit tests shipped; backend wire-in deferred to
builder because `topology.py` is their territory.

---

## What this delivers

| Today | After activation |
|---|---|
| Specialist prompt edit needs source change + Docker build + ECR push + AgentCore runtime bump (~15 min per change) | Prompt edit in Langfuse UI → live on next turn (≤ 60s cache TTL) |
| Prompt history lives in git commits | Prompt history lives in Langfuse with diff UI, labels (`prod`, `candidate`, `demo`), rollback |
| A/B testing requires branching + dual deploys | Langfuse built-in label routing — 10% traffic on `candidate`, 90% on `prod` |
| Prompts are opaque to traces | Prompt ID is attached to every span in the Langfuse UI → click span → see exact prompt text used |

Fail-safe: the wrapper always returns the in-code default if the store
is off, unreachable, or missing the entry. No turn ever fails because
Langfuse is down.

---

## What's already in the repo (as of 2026-05-01)

1. `openclaw/observability/langfuse_prompts.py` — the wrapper.
2. `openclaw/observability/__init__.py` — public API: `get_prompt`,
   `invalidate_cache`.
3. `tests/unit/test_langfuse_prompts.py` — 9 tests covering:
   - switch off → default
   - switch on, creds missing → default (warns once)
   - switch on, SDK missing → default (warns once)
   - switch on, name not in store → default (warns once per name)
   - switch on, name in store → stored text
   - cache hit avoids refetch
   - `invalidate_cache(name)` forces refetch
   - SDK exception → default
   - legacy dict-shape SDK compatibility

Run the tests: `pytest tests/unit/test_langfuse_prompts.py -v` →
9 passed in ~0.3s.

**Intentionally NOT in the repo:** any edit to `orchestration/topology.py`.
That file is owned by the backend builder today. This doc is the
handoff.

---

## Backend wire-in — builder steps

### Step 1 — Import the helper in `topology.py`

```python
# At the top of openclaw/orchestration/topology.py
from openclaw.observability import get_prompt
```

### Step 2 — Wrap each prompt constant

Today `topology.py` has lines like:

```python
FILINGS_SPECIALIST_PROMPT = """You are a filings specialist…"""
```

After wire-in:

```python
FILINGS_SPECIALIST_PROMPT_DEFAULT = """You are a filings specialist…"""

def filings_specialist_prompt() -> str:
    """Prompt resolver — Langfuse store when configured, else the default."""
    return get_prompt("research.filings_specialist", FILINGS_SPECIALIST_PROMPT_DEFAULT)
```

Every call-site that used `FILINGS_SPECIALIST_PROMPT` now calls
`filings_specialist_prompt()`.

**Naming convention** for the Langfuse store:

| persona | prompt | name in Langfuse |
|---|---|---|
| research | filings_specialist | `research.filings_specialist` |
| research | statement_specialist | `research.statement_specialist` |
| research | sentiment_specialist | `research.sentiment_specialist` |
| research | market_specialist | `research.market_specialist` |
| research | compliance_specialist | `research.compliance_specialist` |
| advisor | action_specialist | `advisor.action_specialist` |
| advisor | mnpi_specialist | `advisor.mnpi_specialist` |
| liaison | liaison_specialist | `liaison.liaison_specialist` |
| (shared) | guardrails_template | `shared.guardrails_template` |

Keep the keys stable — changing a key orphans the Langfuse entry.

### Step 3 — (optional) Attach prompt ID to spans

When running Bedrock conversation, pass the Langfuse prompt object to
the span so the UI links prompt to trace:

```python
prompt_obj = langfuse_client.get_prompt("research.filings_specialist")
langfuse_client.generation(
    ...,
    prompt=prompt_obj,  # <-- attaches the prompt revision
)
```

This step is optional — the prompt still WORKS without it. You'd only
lose the ability to click a span and see "this trace used prompt
research.filings_specialist v4".

### Step 4 — Update `requirements.txt`

The wrapper uses `langfuse` which is already a dependency of the
coordinator. Confirm the installed version supports `get_prompt()`:

```bash
grep -n "^langfuse" openclaw/requirements.txt
# Expect: langfuse>=2.39 (prompt management added in 2.39)
```

If the pinned version is older, bump it:

```bash
sed -i '' 's/^langfuse.*/langfuse>=2.39,<3.0/' openclaw/requirements.txt
bash scripts/build-and-push-openclaw.sh
bash scripts/create-v3-agentcore.sh
```

---

## Operator (non-code) activation

### Step 1 — Enable the store

Set the env switch in the AgentCore runtime:

```bash
aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id openclaw_v3_agent-o72dx396I0 \
  --region us-east-1 \
  --environment-variables '{"LANGFUSE_USE_PROMPT_STORE":"1","CACHE_BUST":"'$(date +%s)'"}'
```

`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` should
already be set — reuse the values your existing coordinator tracing
uses.

### Step 2 — Seed the initial prompts in Langfuse UI

1. Open `https://us.cloud.langfuse.com` (or self-hosted host).
2. Select your project → **Prompts** → **New prompt**.
3. For each entry in the naming-convention table above:
   - Name: e.g. `research.filings_specialist`
   - Type: `text` (NOT chat — we use single system strings today)
   - Prompt: paste the current default from `topology.py`
   - Labels: add `production`
   - Save.
4. Repeat for all 9 prompts (or whatever subset you're migrating).

### Step 3 — Verify the first fetch

Run a turn, then check Langfuse UI → **Traces** → click the latest trace.
Each Bedrock generation span should now show a `Prompt` tab listing the
prompt name + version used.

If the Prompt tab shows "not linked", you skipped **Step 3 (builder)**
— attach the prompt object to the span call. The prompt text is still
correct; only the trace linkage is missing.

### Step 4 — Use the iteration loop

To edit a prompt now:

1. Langfuse UI → Prompts → pick the prompt → **New version**.
2. Edit text → tag as `candidate`.
3. Run one test turn — the cache refreshes within 60s.
4. If good, re-tag as `production` (old version keeps its history).
5. If bad, tag back to `production` on the previous version.

A/B split:

1. On the prompt edit dialog, tag the new version with weight: `candidate` 10, `production` 90.
2. Langfuse routes 10% of calls to the candidate.
3. In the UI, compare metrics (tokens, errors, ratings) between versions.

---

## Security + ops notes

1. **No secrets in prompts.** Anything typed into Langfuse is plaintext
   accessible by any team member with project access. Keep client IDs,
   Salesforce credentials, API keys, etc., OUT of prompt text.
2. **PII minimization.** If prompts contain example data, use synthetic
   names + tickers only. Don't paste real client data.
3. **Version drift during deploys.** The cache is 60s. A deploy that
   races a prompt update may serve the stale version for up to 60s.
   Trigger `invalidate_cache()` in a post-deploy hook if that matters.
4. **Rollback plan.** If a bad prompt lands in Langfuse and the wrapper
   starts returning garbage, flip `LANGFUSE_USE_PROMPT_STORE` back to
   `0` — the in-code defaults take over immediately on next turn.
5. **Rate limits.** Langfuse prompt fetches are lightweight but if the
   cache TTL drops to 0 you'd hit the API every turn. Keep 60s+.

---

## Where this lives in the roadmap

| Roadmap item | Status |
|---|---|
| #4 Langfuse prompt management | Scaffold done (this session). Backend wire-in + Langfuse seeding deferred to V4. |
| #1 Multi-modal voice | Not started — V5. |
| #2 AgentCore Memory | Not started — V4. |
| #3 Cognito auth | Scaffolded TASK 6 + playbook at `docs/v3-cognito-setup.md`. |
| #5 Light/dark theme | Shipped this session — `useTheme` + theme-aware tokens. |
| #6 FSI Workforce 360 | Shipped TASK 6. |
| #7 Client map redesign | Shipped this session — `variant="client-simple"` + `ClientTraceStripV3`. |
| #8 Map polish | Shipped TASK 6. |

---

## Teardown

If you want to undo:

```bash
# Turn off the switch (in-code defaults take over)
aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id openclaw_v3_agent-o72dx396I0 \
  --region us-east-1 \
  --environment-variables '{"LANGFUSE_USE_PROMPT_STORE":"0","CACHE_BUST":"'$(date +%s)'"}'

# Langfuse UI → Prompts → delete or archive the entries
```

No code rollback needed — the wrapper is inert when the switch is off.

---

*Written 2026-05-01. Complements the scaffold in
`openclaw/observability/langfuse_prompts.py` and the 9 tests in
`tests/unit/test_langfuse_prompts.py`.*
