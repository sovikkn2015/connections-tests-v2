# Gap 6 — MNPI Leakage Scan — Spec (v2, post-review)

> Sub-module: Gap 6 MNPI Leakage Scan
> Parent module: M6 (MCP Gateway)
> Phase: 1-2
> Agent: 007-compliance-agent
> Source docs: ARCH-06 v3 (Gap 6), ARCH-09, 007-consolidated (Part 9),
>   IMPL-06.
> Status: v2 — addresses F1..F8, R1..R8 from v1 review.

---

## 0. CONTEXT AND SCOPE

Gap 6 is a 3-layer OUTPUT guardrail that scans agent outputs (LLM
responses, structured agent results) for MNPI and other sensitive data
leakage BEFORE they leave M6.

Distinction from M4: M4 filters INPUTS to the LLM (strips MNPI fields
before prompt). Gap 6 filters OUTPUTS from the LLM.

### 0.1 Three layers

| Layer | Technique      | Budget | Phase 1         | Phase 2             |
|-------|----------------|--------|-----------------|---------------------|
| A     | Regex          | <10ms  | Implemented     | Unchanged           |
| B     | NER            | <100ms | Stub interface  | spaCy / cloud NER   |
| C     | LLM classifier | <2s    | Stub interface  | Bedrock Haiku       |

**Layer A is intentionally trigger-happy** (fail-closed):
- Email regex fires on benign mentions.
- `account_number` fires on any 12+ digits (includes timestamps,
  tracking IDs).
- SSN regex catches DASHED only. Undashed 9-digit SSNs are NOT
  matched by Layer A (would cause catastrophic FP rate on order IDs).
  Phase 2 NER catches undashed.
- IBAN regex is shape-only (no mod-97-10 checksum).

**Layer B stub is intentionally aggressive**: any two-word Title-Case
phrase ("John Smith", "Federal Reserve", "Wall Street") triggers DENY.
High FP by design. Phase 2 NER replaces.

**Layer C Phase 1 stub is a keyword list** — NOT a production
classifier. MUST be replaced with Bedrock Haiku (Phase 2) before any
customer deployment. Source file carries a STUB warning docstring.

### 0.2 Decision model

- A → B → C. Short-circuit on first DENY.
- Any DENY → scanner DENY.
- Any layer raises → scanner DENY (fail-closed).
- All ALLOW → scanner ALLOW.
- Binary. No partial delivery. No redaction.

### 0.3 Phase 1 scope

- Layer A fully implemented.
- Layer B: `NamedEntityRecognizer` Protocol + stub.
- Layer C: `LlmClassifier` Protocol + rule-based stub.
- NO LLM SDK imports. `openai`, `anthropic`, `langchain`, `spacy`,
  `transformers`, `boto3` FORBIDDEN in Phase 1.
- Phase 2 Bedrock adapter lives OUTSIDE Gap 6.

### 0.4 Directory layout

```
src/compliance/gap6_mnpi_leakage_scan/
  __init__.py
  _types.py               # internal: ScanDecision
  layer_a_regex.py
  layer_b_ner.py
  layer_c_llm.py
  scanner.py
```

### 0.5 Threading

Layer A thread-safe. Stubs stateless. Scanner holds no mutable state.

### 0.6 Line budget

ARCH-06 target: ~550 for Gap 6.
- `_types.py`: ~30
- `layer_a_regex.py`: ~130
- `layer_b_ner.py`: ~100
- `layer_c_llm.py`: ~90
- `scanner.py`: ~200
- `__init__.py`: ~40
- Tests: ~400

Python source ≈ 590. Tests ≈ 400. On target.

---

## 1. REQUIREMENTS

### R1. ScanDecision & ScanResult

**R1.1** `ScanDecision` enum: `ALLOW`, `DENY`. DENY is terminal.

**R1.2** `ScanResult` frozen Pydantic (`ConfigDict(frozen=True,
extra="forbid")`):
- `decision: ScanDecision`
- `layer: str` — `"A"` | `"B"` | `"C"` | `"none"` | `"error"`
- `match_codes: tuple[str, ...]` — short codes only. NEVER raw text.
  (Renamed from `matches` per v1 R1.)
- `latency_ms_per_layer: dict[str, int]`
- `error_message: str | None` — when `layer=="error"`; max 200 chars;
  NEVER contains input text; MUST match regex
  `^layer_[abc]:[A-Za-z_][A-Za-z0-9_]*$`.

### R2. Layer A — regex

**R2.1** Patterns (Phase 1):

| code             | pattern                                              |
|------------------|------------------------------------------------------|
| `ssn`            | `\b\d{3}-\d{2}-\d{4}\b` (dashed only; §0.1)          |
| `account_number` | `\b\d{12,}\b`                                        |
| `iban`           | `\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b`                   |
| `email`          | `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b` |

All patterns linear-time (no nested quantifiers on overlapping
classes, no backreferences). ReDoS-safe. T6.26 asserts pathological
inputs complete in <100ms.

**R2.2** Compiled once. Module-level `PATTERNS`.

**R2.3** `LayerARegexScanner.scan(text)`:
- None → `TypeError`. (F6 strict.)
- Non-str → `TypeError`.
- >10MB → `ValueError`.
- Empty / no match → `(ALLOW, ())`.
- Hits → `(DENY, sorted(dedup(codes)))`.

Budget <10ms for <=100KB input (documented; not CI-asserted).

**R2.4** Layer A MUST NOT emit matched text. Only codes.

**R2.5** Scanner iterates all patterns (emits union of hits). Short-
circuit is at scanner level, not within Layer A.

### R3. Layer B — NER

**R3.1** Protocol:
```
class NamedEntityRecognizer(Protocol):
    def scan(self, text: str) -> tuple[ScanDecision, tuple[str, ...]]: ...
```

**R3.2** `StubNamedEntityRecognizer` — intentionally aggressive:
- Two consecutive Title-Case words → `ner:name` DENY.
- 8–11 consecutive digits → `ner:account_candidate` DENY.
- Both → sorted multi-code tuple.

"Federal Reserve", "New York", "Wall Street", "Black Scholes" ALL
trigger DENY. Fail-closed by design. T6.7b locks it in.

**R3.3** Same input validation as Layer A.

**R3.4** Phase 2 NER impls implement same Protocol. No hard-coded
imports.

### R4. Layer C — LLM classifier

**R4.1** Protocol:
```
class LlmClassifier(Protocol):
    def scan(self, text: str) -> tuple[ScanDecision, tuple[str, ...]]: ...
```

**R4.2** `StubLlmClassifier` — PHASE 1 NON-PRODUCTION.

Source file docstring MUST begin with:

```
"""
PHASE 1 STUB — MUST NOT BE DEPLOYED TO PRODUCTION.
Replace with Bedrock Haiku classifier (Phase 2) before any customer
deployment. This stub uses a small English-phrase keyword list as a
placeholder; it is not a real MNPI classifier.
"""
```

Source MUST NOT contain real-world MNPI examples in comments.

Keyword list (case-insensitive, 25 entries):
- earnings: `earnings surprise`, `pre-announcement`, `beat consensus`,
  `will beat consensus`, `missed earnings`, `guidance revision`,
  `preliminary results`
- deals: `merger discussions`, `takeover talks`, `acquisition target`,
  `tender offer`, `spin-off`, `strategic review`,
  `exclusive negotiations`
- insider: `insider`, `material non-public`, `mnpi`,
  `confidential information`, `non-public information`
- timing: `before the announcement`, `ahead of the press release`,
  `embargo`, `blackout period`, `prior to disclosure`, `pre-release`

First match → DENY `("llm:mnpi_keyword",)`. Else ALLOW.

**R4.3** Phase 2 Bedrock: PrivateLink, 2s timeout, timeout → SCAN
ERROR (scanner converts to DENY per R5.4).

**R4.4** Gap 6 Phase 1 MUST NOT import `anthropic`, `openai`, `boto3`,
`langchain`, `spacy`, `transformers`.

### R5. MnpiLeakageScanner

**R5.1** Composes Layer A + NER + LLM classifier. All injectable.
Protocol compliance test (T6.27).

**R5.2** Layer order: A → B → C.

**R5.3** Short-circuit on first DENY.

**R5.4 Fail-closed.** Any layer raises → scanner returns:

```
ScanResult(
    decision=DENY, layer="error",
    match_codes=(),
    latency_ms_per_layer=<prior layers' timings>,
    error_message=f"layer_{letter}:{type(exc).__name__}",
)
```

- letter in `{a, b, c}` (lowercase).
- ONLY `type(exc).__name__`; never `str(exc)` / `repr(exc)`.
- Failing layer's latency NOT recorded.
- Prior layers' latencies ARE recorded.
- error_message matches `^layer_[abc]:[A-Za-z_][A-Za-z0-9_]*$`.

**R5.5** `clock: () -> int` injectable (monotonic ns). Default
`time.monotonic_ns`.

**R5.6** `scan(text)`:
- `None` → `TypeError`.
- non-str → `TypeError`.
- >10MB → `ValueError`.
- `""` → `ScanResult(ALLOW, layer="none", match_codes=(),
  latency_ms_per_layer={})`. Empty dict documents fast-path (no layers
  ran). Metrics callers MUST handle this.

**R5.7** `layer == "none"` iff all three layers ran and ALLOWed.

**R5.8 Latency rules.**
- Layer A recorded when it completes (ALLOW or DENY).
- Layer B recorded when completes and A ALLOWed.
- Layer C recorded when completes and A+B ALLOWed.
- When layer raises: own latency NOT recorded; prior layers ARE
  recorded.
- Empty-string fast path: empty dict.
- Values non-negative int ms from ns delta.

**R5.9** Scanner MUST NOT log input. MUST NOT include input in error
messages.

### R6. Deterministic testability

**R6.1** Injectable clock.
**R6.2** Stubs deterministic.
**R6.3** Layer A deterministic.
**R6.4** Tests cover edge cases: see §3.

### R7. Public API

`gap6_mnpi_leakage_scan/__init__.py` re-exports:
```
ScanDecision, ScanResult,
LayerARegexScanner, PATTERNS,
NamedEntityRecognizer, StubNamedEntityRecognizer,
LlmClassifier, StubLlmClassifier,
MnpiLeakageScanner,
```

`src/compliance/__init__.py` re-exports gap2 + gap6.

### R8. Security

- No credentials, no secrets.
- No network I/O (Phase 1).
- No filesystem I/O.
- No input logging.
- DoS cap: 10MB.
- ReDoS-safe patterns.
- Fail-closed.
- Stub has NON-PRODUCTION docstring.
- No credential-like literals (T6.25).

### R9. Module boundary

- IMPORTS: stdlib + pydantic only.
- DOES NOT IMPORT: any `m*_` module, any LLM SDK, spaCy, transformers.

---

## 2. DESIGN

### 2.1 File layout

```
src/compliance/gap6_mnpi_leakage_scan/
  __init__.py              # ~40
  _types.py                # ~30
  layer_a_regex.py         # ~130
  layer_b_ner.py           # ~100
  layer_c_llm.py           # ~90
  scanner.py               # ~200
tests/unit/
  test_gap6_mnpi_leakage_scan.py   # ~400
```

### 2.2 Shared `_types.py`

Defines `ScanDecision` only. Avoids circular imports.

### 2.3 Layer A sketch

```python
PATTERNS = (
    ("ssn",            re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("account_number", re.compile(r"\b\d{12,}\b")),
    ("iban",           re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")),
    ("email",          re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
)

class LayerARegexScanner:
    PATTERNS = PATTERNS
    _MAX_BYTES = 10 * 1024 * 1024

    def scan(self, text):
        if text is None:
            raise TypeError("text must be str (not None)")
        if not isinstance(text, str):
            raise TypeError("text must be str")
        if len(text.encode("utf-8")) > self._MAX_BYTES:
            raise ValueError("input too large for regex scan")
        hits: set[str] = set()
        for code, pattern in self.PATTERNS:
            if pattern.search(text):
                hits.add(code)
        if not hits:
            return ScanDecision.ALLOW, ()
        return ScanDecision.DENY, tuple(sorted(hits))
```

### 2.4 Scanner sketch

```python
class MnpiLeakageScanner:
    _MAX_BYTES = 10 * 1024 * 1024
    _ERROR_MSG_RE = re.compile(r"^layer_[abc]:[A-Za-z_][A-Za-z0-9_]*$")

    def __init__(self, *, layer_a=None, ner=None, llm=None, clock=None):
        self._a = layer_a or LayerARegexScanner()
        self._b = ner or StubNamedEntityRecognizer()
        self._c = llm or StubLlmClassifier()
        self._clock = clock or _default_clock

    def scan(self, text):
        # input validation identical to Layer A ...
        if text == "":
            return ScanResult(
                decision=ScanDecision.ALLOW, layer="none",
                match_codes=(), latency_ms_per_layer={},
            )

        timings: dict[str, int] = {}

        for letter, impl in (("A", self._a), ("B", self._b), ("C", self._c)):
            try:
                t0 = self._clock()
                dec, matches = impl.scan(text)
                timings[letter] = max(0, (self._clock() - t0) // 1_000_000)
            except Exception as exc:
                return ScanResult(
                    decision=ScanDecision.DENY, layer="error",
                    match_codes=(),
                    latency_ms_per_layer=dict(timings),
                    error_message=f"layer_{letter.lower()}:{type(exc).__name__}",
                )
            if dec is ScanDecision.DENY:
                return ScanResult(
                    decision=dec, layer=letter, match_codes=matches,
                    latency_ms_per_layer=dict(timings),
                )

        return ScanResult(
            decision=ScanDecision.ALLOW, layer="none",
            match_codes=(), latency_ms_per_layer=dict(timings),
        )
```

### 2.5 Wiring (docs; Phase 1)

```
llm_output = specialist.run(...)
result = scanner.scan(llm_output)
if result.decision is ScanDecision.DENY:
    audit(m10, action="mnpi.leakage_blocked",
          layer=result.layer, match_codes=result.match_codes)
    raise MnpiLeakageBlocked(...)
# else deliver
```

### 2.6 Security

- No credentials / network / filesystem.
- No input logging.
- 10MB DoS cap.
- ReDoS-verified patterns.
- Fail-closed.

### 2.7 Module boundary

stdlib + pydantic only.

---

## 3. TASKS

T6.1 — `ScanDecision` enum with 2 members.

T6.2 — `ScanResult` frozen (`extra="forbid"`). Mutation raises. Unknown
kwarg raises.

T6.3 — Layer A golden:
- `"My ssn is 123-45-6789"` → DENY `("ssn",)`
- `"acct 123456789012"` → DENY `("account_number",)`
- `"IBAN GB29NWBK60161331926819"` → DENY `("iban",)`
- `"john.smith@example.com"` → DENY `("email",)`
- `"ssn 123-45-6789 email a@b.co"` → DENY `("email", "ssn")` sorted
- `"this is clean text"` → ALLOW `()`
- `""` → ALLOW `()`

T6.3b — `"123456789"` (undashed 9-digit SSN) → ALLOW. Documents
Phase 1 limitation.

T6.4 — Layer A None → TypeError; non-str → TypeError; >10MB →
ValueError.

T6.5 — No raw text in match_codes. `"123-45-6789"` input; assert
string NOT in any match_code.

T6.6 — `NamedEntityRecognizer` Protocol defined.

T6.7 — Stub NER positive:
- `"John Smith"` → `ner:name`
- `"12345678"` → `ner:account_candidate`
- `"John Smith visited 12345678"` → both codes sorted

T6.7b — Aggressive-NER lock-in: `"Federal Reserve"`, `"New York"`,
`"Wall Street"`, `"Black Scholes"` → DENY `ner:name`.

T6.7c — Stub NER input validation: None / non-str / >10MB.

T6.8 — `LlmClassifier` Protocol defined.

T6.9 — `StubLlmClassifier` parametrized over all 25 keywords — each
→ DENY. Clean text → ALLOW.

T6.9b — Stub docstring starts with required STUB warning (AST / text
check).

T6.10 — `scan("")` → ALLOW layer="none", empty timings.

T6.11 — `scan(None)` → TypeError.

T6.12 — `scan(<non-str>)` → TypeError.

T6.13 — `scan(<>10MB>)` → ValueError.

T6.14 — Short-circuit Layer A DENY. Spy B and C NOT called.

T6.15 — Short-circuit Layer B DENY. Spy C NOT called.

T6.16 — Layer C DENY → result layer="C".

T6.17 — All-pass clean text → ALLOW layer="none"; timings for A, B, C.

T6.18 — Fail-closed Layer A raises → DENY layer="error",
error_message starts `"layer_a:"`; timings empty; spies B + C NOT
called.

T6.19 — Fail-closed Layer B raises → DENY layer="error",
error_message `"layer_b:..."`; timings has `"A"` only; spy C NOT
called.

T6.20 — Fail-closed Layer C raises → DENY layer="error",
error_message `"layer_c:..."`; timings has `"A"` and `"B"`.

T6.21 — Canary: input contains `"secret_canary_xyz"` with failing
layer. Assert that string NOT in `error_message` / any field.

T6.21b — error_message regex compliance. Parametrized injected
exceptions whose `__name__` is a legal Python identifier — message
matches format regex.

T6.22 — Injectable clock: sequence `[0, 5_000_000, 8_000_000,
20_000_000, 25_000_000, 35_000_000]` ns → timings `{"A": 5, "B": 12,
"C": 10}`.

T6.23 — Public API exports all R7 names.

T6.24 — AST import scan: no forbidden imports in Gap 6 source.

T6.25 — No credential-like literals (grep `sk-`, `AKIA`, `Bearer `,
`api_key` in source).

T6.26 — ReDoS: Layer A scan of `"a" * 100_000` and `"-" * 100_000`
each completes <100ms; both return ALLOW.

T6.27 — Protocol compliance: minimal custom class `.scan(text) ->
(ScanDecision, tuple)` works as `ner=` and `llm=` on scanner.

T6.28 — Stub input validation completeness (R3.3, R4.x implicit).
Covered by T6.7c and similar for Layer C stub.

---

## 4. TRACEABILITY

| AC    | Task(s)                                      |
|-------|----------------------------------------------|
| R1.1  | T6.1                                         |
| R1.2  | T6.2, T6.17, T6.18, T6.21, T6.21b            |
| R2.1  | T6.3, T6.3b                                  |
| R2.2  | T6.3                                         |
| R2.3  | T6.3, T6.4                                   |
| R2.4  | T6.5                                         |
| R2.5  | T6.3 (multi-hit union)                       |
| R3.1  | T6.6                                         |
| R3.2  | T6.7, T6.7b                                  |
| R3.3  | T6.7c, T6.28                                 |
| R3.4  | T6.24                                        |
| R4.1  | T6.8                                         |
| R4.2  | T6.9, T6.9b                                  |
| R4.3  | (docs; Phase 2)                              |
| R4.4  | T6.24                                        |
| R5.1  | T6.23, T6.27                                 |
| R5.2  | T6.14, T6.15, T6.16                          |
| R5.3  | T6.14, T6.15                                 |
| R5.4  | T6.18, T6.19, T6.20, T6.21, T6.21b           |
| R5.5  | T6.22                                        |
| R5.6  | T6.10, T6.11, T6.12, T6.13                   |
| R5.7  | T6.10, T6.14, T6.15, T6.16, T6.17, T6.18     |
| R5.8  | T6.10, T6.17, T6.19, T6.20, T6.22            |
| R5.9  | T6.21                                        |
| R6.1  | T6.22                                        |
| R6.2  | T6.7, T6.9                                   |
| R6.3  | T6.3                                         |
| R6.4  | T6.3, T6.7b, T6.14, T6.15, T6.18, T6.26, T6.27|
| R7    | T6.23                                        |
| R8    | T6.4, T6.13, T6.21, T6.24, T6.25, T6.26, T6.9b|
| R9    | T6.24                                        |

---

## 5. REVIEW FIX TRACEABILITY (v1 — v2)

| Review item | v2 section                              |
|-------------|-----------------------------------------|
| F1 (FP/FN docs)             | §0.1                     |
| F2 (STUB docstring)         | R4.2, T6.9b              |
| F3 (aggressive-NER)         | R3.2, T6.7b              |
| F4 (error_message regex)    | R1.2, R5.4, T6.21b       |
| F5 (ReDoS)                  | R2.1, T6.26              |
| F6 (None strict unified)    | R2.3                     |
| F7 (empty-latency doc)      | R5.6, R5.8               |
| F8 (error-path latency)     | R5.8                     |
| R1 (match_codes rename)     | R1.2                     |
| R2 (keyword list 25 items)  | R4.2                     |
| R3 (scan_id)                | deferred to Phase 2      |
| R4 (T6.22 expected dict)    | T6.22                    |
| R5 (KEYWORDS stability)     | R4.2                     |
| R6 (Protocol compliance)    | T6.27                    |
| R7 (latency scope)          | R6.3, §0.1               |
| R8 (no-match fast path)     | T6.3                     |
