# Gap 1 — Reg BI Doc Generator — Decision Log

## D1. LLM is cosmetic, compliance is deterministic

Reg BI compliance decisions (applicability, min-bullet floors, four-
obligation populate, advisor-review gate) are 100% deterministic
Python. LLM is used ONLY to stitch pre-assembled bullets into prose
(`NarrativeClient` Protocol).

Rationale:
- Steering rule 14 — no LLM for compliance decisions.
- SEC §15l-1 is a rule-based regime, not a judgment-based one.
- LLM failure must not block a document — the bullets are the truth.

LLM failure is caught in `_stitch_one` and degrades to empty
narrative + forced `advisor_review_required=True`.

## D2. Audit failure is the ONE raise

The generator is tolerant of every failure mode EXCEPT audit-sink
failure. Rationale:
- 17 CFR §240.17a-4(e)(5) mandates durable storage.
- A document without a audit-tier write is non-compliant.
- Retries are the caller's job — Gap 1 is fire-and-forget.

No DLQ (v1 R7 recommendation): keeping Gap 1 small; if M10 exposes a
DLQ via the AuditClient Protocol implementation, callers can wire it
in without Gap 1 changes.

## D3. PII scrubbed at 3 checkpoints

1. `reason_trace` field validator (user-supplied input).
2. Each bullet at populator finalize (defence-in-depth).
3. Each narrative post-stitch (the one LLM-ish path).

Uses the same 4 regex patterns as Gap 2 / Gap 6. Duplicated locally
to avoid cross-gap imports (same decoupling as Gap 2 vs Gap 6 —
compliance gaps must be independently auditable).

## D4. `client.display_name` is never emitted in bullets or narrative

F3 from v1 review. Populators reference `"the client"` / `"the
household"`. Reason: display_name can legitimately contain digit
sequences (corporate suffixes, trust names) that the 12+-digit
account-number regex false-positives on. Banning its use upstream
sidesteps the problem; locks in via T1.18b.

## D5. Trust clients are SKIP_INSTITUTIONAL

F2 from v1 review. Reg BI applies to retail customers = natural
persons. Trusts operate under Uniform Trust Code and are treated as
institutional for Reg BI purposes. T1.6 parametrizes.

## D6. Populator versioning is independent

F4 from v1 review. Each obligation's `populated_by` is versioned
separately (`reg_bi/{obligation}/populate.v{N}`). A DISCLOSURE bug
fix bumps DISCLOSURE to v2 without disturbing CARE/COI/COMPLIANCE.
Golden hex test T1.19 breaks on any version bump — intentional drift
detection.

## D7. `firm_registration_type` sourced from AidClaims

R6 from v1 review. Redundant `firm_registration_type` dropped from
GenerationInput. `advisor.registration_type` is canonical.

## D8. Module boundary — Protocol-only integration

Gap 1 does NOT import `m10_audit_logger` directly. Instead:
- `AuditClient` Protocol defines the wire shape.
- `InMemoryAuditClient` is the Phase-2 test default.
- M10's real adapter implements the Protocol at the edge.

Same pattern as Gap 2's relationship to M10's ProvenanceChainBuilder
(consumed via injected data; Gap 2 does not reach INTO M10).

## D9. `InsufficientBulletsError` is a hard error

F1 from v1 review. Populators MUST reach the min-bullet floor; too
few bullets means the input doesn't support a Reg BI document. Hard
raise (no degradation) upholds steering rule 8 (fail-closed).

## D10. Max-bullet overflow is silent truncate

R3.7 — newest bullets dropped. Document still produced. Rationale:
max is a display-quality cap, not a correctness check; losing the
newest alternative is better than blocking.

## D11. No Jinja in Phase 2

R1 from v1 review. ARCH-06 mentions Jinja for firm-customized
templates. Phase 2-3 ships the Python structure; Phase 3 adds the
templates. The Python layer feeds structured JSON into whichever
template engine the firm wires in.
