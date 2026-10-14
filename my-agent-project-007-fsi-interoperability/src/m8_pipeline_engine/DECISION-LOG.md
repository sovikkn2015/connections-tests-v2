# M8 Pipeline Engine — Decision Log

## 2026-05-18 — v0.1.0 Initial Draft

### D1. LangGraph chosen over custom pipeline engine
Source: ARCH-04 v2 §M8. Native checkpointing + HITL + time-travel + `Send`
fan-out. 006 `pipeline.py` lacks checkpointing.

### D2. 23 stages ported from 006 `pipeline.py` (stage numbers stable; 2 names renamed — see D13)
Source: 006 v2 `pipeline.py::_all_stage_methods()` line 160-174. Of 23
stages, 21 match 006 verbatim; stages 12 and 21 renamed per D13.

### D3. 3 HITL gates at stages 7, 13, 21
Source: 006 v2 `pipeline.py` line 58 `HITL_STAGES = {7, 13, 21}`.

### D4. PostgreSQL checkpointer default, DynamoDB reserved
Schema segregation via `search_path=m8_checkpoints`.

### D5. Sonnet model ID tentative
Pinned: `anthropic.claude-sonnet-4-5-20250929-v1:0`. PENDING-VERIFICATION.

### D6. HITL token HMAC-SHA-256 with Vault-resolved key
HMAC adds tamper defense. TTL = `hitl_timeout_seconds`.

### D7. 20 reason codes in v0.1.0 (reconciled v0.2.0)
Initial intent was 10; drafting forced 20. Pinned in AC11.1.

### D8. Map-reduce cap at 10 instruments
Preserves Bedrock regional TPS budget.

### D9. Wall-clock ceiling EXCLUDES HITL wait
HITL could be 4h; compute budget 20 min.

### D10. Anti-fabrication check at stage 21 (guardrail)
006 pattern. Human reviewer at Gate 3 decides.

### D11. 006 v2 MetaClaw lesson capture deferred to Phase 3
Stateless-per-run simplifies Phase 2.

### D12. No `langchain-aws` despite ARCH-04 v2 "Key Libraries"
`boto3` Bedrock Runtime `converse` suffices; LangChain umbrella would
break Steering Rule 15. Elevated to Known Blockers row 17 in v0.2.0.

## 2026-05-20 — v0.2.0 LLMJ v1 Fix Pass

### D13. Stage 12 and Stage 21 renames vs 006
- **Stage 12**: 006 `_stage_12_sentiment_synthesis` → 007
  `stage_12_cross_source_synthesis`. Map-reduce REDUCE across instruments
  + sources, not single-source sentiment.
- **Stage 21**: 006 `_stage_21_final_approval_gate` → 007
  `stage_21_anti_fabrication_check`. Anti-fab FIRST, then HITL gate.

Audit consumers MUST query on `stage_number` (stable identifier).

### D14. Hypothesis CI budget (Rec-Fix 4)
`max_examples=20` under `CI=1`, `max_examples=50` locally.

### D15. HITL HMAC key rotation contract (Req-Fix 12)
Quarterly (90 days) pod-restart-triggered re-fetch. Cross-pod-boundary
verification failures emit `m8_hitl_token_expired`.
