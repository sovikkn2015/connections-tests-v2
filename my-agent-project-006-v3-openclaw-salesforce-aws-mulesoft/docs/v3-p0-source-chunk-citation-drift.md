# v3 P0 — Citation ID drift (source_chunk drill-down returns empty)

**Status:** Requires a prompt fix in research specialists. Defer to builder
(they're actively editing `coordinator.py` / `advisor_orchestrator.py` /
`liaison_orchestrator.py` in parallel).

---

## Observed symptom

Clicking a citation chip in the v2/v3 research brief opens the drill-down
drawer with **"(source not available)"**.

Live-probed:

```bash
curl -s https://e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3/api/source_chunk/nvda-10q-20251026 \
  -H 'Authorization: Bearer dev-bootstrap-token'
# {"source_id":"nvda-10q-20251026",
#  "title":"(source not available)",
#  "text":""}
```

---

## Root cause

The **S3 chunks bucket is populated** with 784 real chunks:

```
s3://openclaw006v3-kb-chunksbucketa7972c90-hhhf52iniof0/kb-chunks/
  AAPL-000032019326000006-c0000.json
  AAPL-000032019326000006-c0001.json
  ...
  NVDA-000104581025000230-c0042.json
```

**Key format:** `{TICKER}-{accession}-c{chunk_index}.json`

But the research specialist brief emits citations like:

```
[src:finnhub_quote_NVDA]           ← market_specialist — no real chunk
[src:nvda-10q-20251026]            ← filings_specialist — fabricated id
```

Neither of these matches the bucket key format. The sec-edgar MCP's
`_s3_get_chunk` tries `kb-chunks/nvda-10q-20251026.json` → 404 → returns
the empty stub.

---

## What the brief SHOULD emit

When `kb_retrieve` returns:

```json
{
  "chunks": [
    {
      "source_chunk_id": "NVDA-000104581025000230-c0042",
      "text": "...Data-center revenue grew 62% YoY...",
      "score": 0.88
    }
  ]
}
```

The research specialist should paste EXACTLY `[src:NVDA-000104581025000230-c0042]`
into the brief. Currently the LLM invents readable-looking IDs instead of
pasting the opaque real ones.

---

## Fix location

`openclaw/orchestration/topology.py` — the specialist system prompts
(`FILINGS_SPECIALIST_PROMPT`, `STATEMENT_SPECIALIST_PROMPT`, etc).

Add a hard rule like:

```
CITATION FORMAT — MANDATORY:
When you include information sourced from `kb_retrieve`, you MUST cite
using the EXACT `source_chunk_id` returned by the tool. Do NOT invent
human-readable identifiers like "nvda-10q-20251026". The id is always
in the form {TICKER}-{accession}-c{index} — paste it verbatim.

Wrong: [src:nvda-10q-20251026]
Wrong: [src:finnhub_quote_NVDA]
Right: [src:NVDA-000104581025000230-c0042]
```

Plus add a **post-synthesis validator** in the research_orchestrator's
`synthesize` method that checks every `[src:...]` citation against the
actual retrieval results and rewrites mismatches before the brief goes
to the user.

---

## Why I'm deferring

Builder is actively iterating on `coordinator.py` and the orchestrator
files (saw uncommitted changes at diagnostic time). Adding
prompt changes right now risks merge conflict. The citation IDs being
wrong is a **backend fix**, not a UI fix — the UI renders correctly
when given a real chunk payload.

**Handoff to backend builder:**
1. Update `FILINGS_SPECIALIST_PROMPT` + `STATEMENT_SPECIALIST_PROMPT` in
   `openclaw/orchestration/topology.py` with the verbatim-id rule above.
2. Optionally add a regex validator in
   `research_orchestrator.py::synthesize` that strips any `[src:...]`
   that doesn't match the `{TICKER}-{accession}-c{index}` format.
3. Deploy: `bash scripts/build-and-push-openclaw.sh && bash scripts/create-v3-agentcore.sh`
4. Verify: run N1 turn, click a citation chip, confirm drawer shows real text.

**Secondary issue** (`market_specialist` emitting `[src:finnhub_quote_NVDA]`):
market quotes aren't KB-indexed. Options:
- Drop the `[src:...]` requirement for non-KB sources.
- Mint a synthetic chunk id when market data is returned, with a
  dedicated `/api/market_quote/{id}` resolver. More work.

For now, market_specialist citations will fall back to "(source not
available)" — honest, not a regression.
