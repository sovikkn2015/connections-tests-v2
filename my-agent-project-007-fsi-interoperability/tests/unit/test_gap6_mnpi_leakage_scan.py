"""
Gap 6 — MNPI Leakage Scan — Unit Tests.

Covers spec .kiro/specs/gap6-mnpi-leakage-scan.md tasks T6.1..T6.28.

Run:
    PYTHONPATH=my-agent-project-007-fsi-interoperability/src \\
        python3 -m pytest \\
        my-agent-project-007-fsi-interoperability/tests/unit/test_gap6_mnpi_leakage_scan.py -v
"""

from __future__ import annotations

import ast
import re
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from compliance.gap6_mnpi_leakage_scan import (
    ERROR_MESSAGE_RE,
    LayerARegexScanner,
    LlmClassifier,
    MnpiLeakageScanner,
    NamedEntityRecognizer,
    PATTERNS,
    ScanDecision,
    ScanResult,
    StubLlmClassifier,
    StubNamedEntityRecognizer,
)


# =============================================================================
# Test helpers - spies + custom Protocol impls + exotic exception
# =============================================================================


class _Spy:
    """Records calls without doing anything real. Returns a preset result."""

    def __init__(
        self,
        result: tuple[ScanDecision, tuple[str, ...]] = (
            ScanDecision.ALLOW,
            (),
        ),
        raise_exc: Exception | None = None,
    ):
        self._result = result
        self._raise = raise_exc
        self.called = 0
        self.last_text: str | None = None

    def scan(self, text: str):
        self.called += 1
        self.last_text = text
        if self._raise is not None:
            raise self._raise
        return self._result


class _ExoticException(Exception):
    """Exception with a legal-identifier class name for T6.21b."""


# =============================================================================
# T6.1 — ScanDecision enum
# =============================================================================


def test_T6_1_scan_decision_has_two_members():
    assert {d.value for d in ScanDecision} == {"ALLOW", "DENY"}


# =============================================================================
# T6.2 — ScanResult frozen + extra=forbid
# =============================================================================


def test_T6_2_scan_result_frozen():
    r = ScanResult(decision=ScanDecision.ALLOW, layer="none")
    with pytest.raises(ValidationError):
        r.decision = ScanDecision.DENY  # type: ignore[misc]


def test_T6_2_scan_result_extra_forbid():
    with pytest.raises(ValidationError):
        ScanResult(
            decision=ScanDecision.ALLOW,
            layer="none",
            unknown_field="x",  # type: ignore[call-arg]
        )


# =============================================================================
# T6.3 — Layer A golden matches
# =============================================================================


@pytest.mark.parametrize(
    "text,expected",
    [
        ("My ssn is 123-45-6789", (ScanDecision.DENY, ("ssn",))),
        (
            "acct 123456789012 internal",
            (ScanDecision.DENY, ("account_number",)),
        ),
        (
            "IBAN GB29NWBK60161331926819 declined",
            (ScanDecision.DENY, ("iban",)),
        ),
        (
            "Please email john.smith@example.com",
            (ScanDecision.DENY, ("email",)),
        ),
        (
            "ssn 123-45-6789 email a@b.co",
            (ScanDecision.DENY, ("email", "ssn")),  # sorted
        ),
        ("this is clean text", (ScanDecision.ALLOW, ())),
        ("", (ScanDecision.ALLOW, ())),
    ],
)
def test_T6_3_layer_a_golden(text, expected):
    scanner = LayerARegexScanner()
    assert scanner.scan(text) == expected


def test_T6_3b_undashed_ssn_not_matched_by_layer_a():
    # 9 digits < 12 so neither ssn nor account_number fires.
    scanner = LayerARegexScanner()
    decision, codes = scanner.scan("number 123456789 here")
    assert decision is ScanDecision.ALLOW
    assert codes == ()


# =============================================================================
# T6.4 — Layer A input validation
# =============================================================================


def test_T6_4_layer_a_none_raises_type_error():
    with pytest.raises(TypeError):
        LayerARegexScanner().scan(None)  # type: ignore[arg-type]


def test_T6_4_layer_a_non_str_raises_type_error():
    with pytest.raises(TypeError):
        LayerARegexScanner().scan(123)  # type: ignore[arg-type]


def test_T6_4_layer_a_oversized_raises_value_error():
    huge = "a" * (10 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="too large"):
        LayerARegexScanner().scan(huge)


# =============================================================================
# T6.5 — Layer A never emits raw matched text
# =============================================================================


def test_T6_5_layer_a_never_emits_raw_text():
    decision, codes = LayerARegexScanner().scan("SSN 123-45-6789")
    assert decision is ScanDecision.DENY
    for c in codes:
        assert "123-45-6789" not in c
        assert "123456789" not in c


# =============================================================================
# T6.6 — NamedEntityRecognizer Protocol exists
# =============================================================================


def test_T6_6_ner_protocol_defined():
    assert NamedEntityRecognizer is not None
    # Stubs satisfy the protocol structurally.
    stub = StubNamedEntityRecognizer()
    assert hasattr(stub, "scan")


# =============================================================================
# T6.7 — Stub NER positive cases
# =============================================================================


def test_T6_7_stub_ner_name_hit():
    d, codes = StubNamedEntityRecognizer().scan("John Smith called.")
    assert d is ScanDecision.DENY
    assert "ner:name" in codes


def test_T6_7_stub_ner_account_candidate():
    d, codes = StubNamedEntityRecognizer().scan("reference 12345678 issued")
    assert d is ScanDecision.DENY
    assert "ner:account_candidate" in codes


def test_T6_7_stub_ner_both_codes_sorted():
    d, codes = StubNamedEntityRecognizer().scan(
        "John Smith referenced 12345678"
    )
    assert d is ScanDecision.DENY
    assert codes == ("ner:account_candidate", "ner:name")


# =============================================================================
# T6.7b — Aggressive-NER lock-in
# =============================================================================


@pytest.mark.parametrize(
    "text",
    [
        "Federal Reserve",
        "New York",
        "Wall Street",
        "Black Scholes",
    ],
)
def test_T6_7b_aggressive_ner_blocks_common_phrases(text):
    d, codes = StubNamedEntityRecognizer().scan(text)
    assert d is ScanDecision.DENY
    assert "ner:name" in codes


# =============================================================================
# T6.7c — Stub NER input validation
# =============================================================================


def test_T6_7c_stub_ner_none_raises():
    with pytest.raises(TypeError):
        StubNamedEntityRecognizer().scan(None)  # type: ignore[arg-type]


def test_T6_7c_stub_ner_non_str_raises():
    with pytest.raises(TypeError):
        StubNamedEntityRecognizer().scan(42)  # type: ignore[arg-type]


def test_T6_7c_stub_ner_oversized_raises():
    huge = "a" * (10 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="too large"):
        StubNamedEntityRecognizer().scan(huge)


# =============================================================================
# T6.8 — LlmClassifier Protocol
# =============================================================================


def test_T6_8_llm_protocol_defined():
    assert LlmClassifier is not None
    stub = StubLlmClassifier()
    assert hasattr(stub, "scan")


# =============================================================================
# T6.9 — Stub LLM classifier keywords
# =============================================================================


@pytest.mark.parametrize("kw", list(StubLlmClassifier.KEYWORDS))
def test_T6_9_stub_llm_each_keyword_triggers_deny(kw):
    d, codes = StubLlmClassifier().scan(f"context containing {kw} term")
    assert d is ScanDecision.DENY
    assert codes == ("llm:mnpi_keyword",)


def test_T6_9_stub_llm_clean_text_allowed():
    d, codes = StubLlmClassifier().scan("general market commentary.")
    assert d is ScanDecision.ALLOW
    assert codes == ()


def test_T6_9_stub_llm_keyword_list_size():
    assert len(StubLlmClassifier.KEYWORDS) == 25


# =============================================================================
# T6.9b — Stub has NON-PRODUCTION docstring
# =============================================================================


def test_T6_9b_stub_llm_has_non_production_docstring():
    path = (
        Path(__file__).parents[2]
        / "src"
        / "compliance"
        / "gap6_mnpi_leakage_scan"
        / "layer_c_llm.py"
    )
    source = path.read_text()
    tree = ast.parse(source)
    module_doc = ast.get_docstring(tree)
    assert module_doc is not None
    first_line = module_doc.splitlines()[0].strip().upper()
    assert "PHASE 1" in first_line
    assert (
        "MUST NOT" in first_line
        or "NOT BE DEPLOYED" in module_doc.upper()
    )


# =============================================================================
# T6.10 — scanner empty input
# =============================================================================


def test_T6_10_scan_empty_returns_none_layer():
    scanner = MnpiLeakageScanner()
    r = scanner.scan("")
    assert r.decision is ScanDecision.ALLOW
    assert r.layer == "none"
    assert r.match_codes == ()
    assert r.latency_ms_per_layer == {}


# =============================================================================
# T6.11..T6.13 — scanner input validation
# =============================================================================


def test_T6_11_scan_none_raises():
    with pytest.raises(TypeError):
        MnpiLeakageScanner().scan(None)  # type: ignore[arg-type]


def test_T6_12_scan_non_str_raises():
    with pytest.raises(TypeError):
        MnpiLeakageScanner().scan(42)  # type: ignore[arg-type]


def test_T6_13_scan_oversized_raises():
    huge = "x" * (10 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="too large"):
        MnpiLeakageScanner().scan(huge)


# =============================================================================
# T6.14 — Short-circuit: Layer A DENY skips B + C
# =============================================================================


def test_T6_14_short_circuit_layer_a_deny():
    b_spy = _Spy()
    c_spy = _Spy()
    scanner = MnpiLeakageScanner(ner=b_spy, llm=c_spy)
    r = scanner.scan("SSN 123-45-6789 leaked")
    assert r.decision is ScanDecision.DENY
    assert r.layer == "A"
    assert "ssn" in r.match_codes
    assert b_spy.called == 0
    assert c_spy.called == 0


# =============================================================================
# T6.15 — Short-circuit: Layer B DENY skips C
# =============================================================================


def test_T6_15_short_circuit_layer_b_deny():
    b_deny = _Spy(result=(ScanDecision.DENY, ("ner:name",)))
    c_spy = _Spy()
    scanner = MnpiLeakageScanner(ner=b_deny, llm=c_spy)
    r = scanner.scan("clean for regex but B catches it")
    assert r.decision is ScanDecision.DENY
    assert r.layer == "B"
    assert r.match_codes == ("ner:name",)
    assert c_spy.called == 0
    assert "A" in r.latency_ms_per_layer
    assert "B" in r.latency_ms_per_layer
    assert "C" not in r.latency_ms_per_layer


# =============================================================================
# T6.16 — Layer C DENY
# =============================================================================


def test_T6_16_layer_c_deny():
    b_pass = _Spy(result=(ScanDecision.ALLOW, ()))
    c_deny = _Spy(result=(ScanDecision.DENY, ("llm:mnpi_keyword",)))
    scanner = MnpiLeakageScanner(ner=b_pass, llm=c_deny)
    r = scanner.scan("clean enough for A and B, not C")
    assert r.decision is ScanDecision.DENY
    assert r.layer == "C"
    assert r.match_codes == ("llm:mnpi_keyword",)
    assert set(r.latency_ms_per_layer.keys()) == {"A", "B", "C"}


# =============================================================================
# T6.17 — All-pass
# =============================================================================


def test_T6_17_all_pass_clean():
    b_pass = _Spy(result=(ScanDecision.ALLOW, ()))
    c_pass = _Spy(result=(ScanDecision.ALLOW, ()))
    scanner = MnpiLeakageScanner(ner=b_pass, llm=c_pass)
    r = scanner.scan("plain boring text")
    assert r.decision is ScanDecision.ALLOW
    assert r.layer == "none"
    assert set(r.latency_ms_per_layer.keys()) == {"A", "B", "C"}


# =============================================================================
# T6.18 — Fail-closed Layer A raises
# =============================================================================


def test_T6_18_fail_closed_layer_a_raises():
    class _RaisingA:
        PATTERNS = PATTERNS

        def scan(self, text: str):
            raise _ExoticException("should not leak")

    b_spy = _Spy()
    c_spy = _Spy()
    scanner = MnpiLeakageScanner(
        layer_a=_RaisingA(),  # type: ignore[arg-type]
        ner=b_spy,
        llm=c_spy,
    )
    r = scanner.scan("some input")
    assert r.decision is ScanDecision.DENY
    assert r.layer == "error"
    assert r.error_message is not None
    assert r.error_message.startswith("layer_a:")
    assert "_ExoticException" in r.error_message
    assert b_spy.called == 0
    assert c_spy.called == 0
    assert r.latency_ms_per_layer == {}


# =============================================================================
# T6.19 — Fail-closed Layer B raises
# =============================================================================


def test_T6_19_fail_closed_layer_b_raises():
    b_raise = _Spy(raise_exc=_ExoticException("B failed"))
    c_spy = _Spy()
    scanner = MnpiLeakageScanner(ner=b_raise, llm=c_spy)
    r = scanner.scan("clean input")
    assert r.decision is ScanDecision.DENY
    assert r.layer == "error"
    assert r.error_message is not None
    assert r.error_message.startswith("layer_b:")
    assert c_spy.called == 0
    assert "A" in r.latency_ms_per_layer
    assert "B" not in r.latency_ms_per_layer
    assert "C" not in r.latency_ms_per_layer


# =============================================================================
# T6.20 — Fail-closed Layer C raises
# =============================================================================


def test_T6_20_fail_closed_layer_c_raises():
    b_pass = _Spy(result=(ScanDecision.ALLOW, ()))
    c_raise = _Spy(raise_exc=_ExoticException("C failed"))
    scanner = MnpiLeakageScanner(ner=b_pass, llm=c_raise)
    r = scanner.scan("clean input")
    assert r.decision is ScanDecision.DENY
    assert r.layer == "error"
    assert r.error_message is not None
    assert r.error_message.startswith("layer_c:")
    assert "A" in r.latency_ms_per_layer
    assert "B" in r.latency_ms_per_layer
    assert "C" not in r.latency_ms_per_layer


# =============================================================================
# T6.21 — error_message never contains input text (canary)
# =============================================================================


def test_T6_21_error_message_never_contains_input_text():
    canary = "secret_canary_xyz_987654321"

    class _RaiseWithMessage:
        def scan(self, text: str):
            # Even if an exception carries input-like text, we must
            # not leak it via error_message.
            raise ValueError(f"details about {text}")

    scanner = MnpiLeakageScanner(
        ner=_RaiseWithMessage(),  # type: ignore[arg-type]
    )
    r = scanner.scan(f"payload with {canary}")
    assert r.decision is ScanDecision.DENY
    assert r.layer == "error"
    assert r.error_message is not None
    assert canary not in r.error_message
    for code in r.match_codes:
        assert canary not in code


# =============================================================================
# T6.21b — error_message format regex
# =============================================================================


@pytest.mark.parametrize("layer_letter", ["a", "b", "c"])
def test_T6_21b_error_message_matches_format(layer_letter):
    class _RaisingA:
        PATTERNS = PATTERNS

        def scan(self, text: str):
            raise _ExoticException()

    raise_spy = _Spy(raise_exc=_ExoticException())

    if layer_letter == "a":
        scanner = MnpiLeakageScanner(
            layer_a=_RaisingA(),  # type: ignore[arg-type]
        )
    elif layer_letter == "b":
        scanner = MnpiLeakageScanner(ner=raise_spy)
    else:  # "c"
        scanner = MnpiLeakageScanner(llm=raise_spy)

    r = scanner.scan("input")
    assert r.error_message is not None
    assert ERROR_MESSAGE_RE.match(r.error_message), (
        f"error_message {r.error_message!r} does not match format"
    )


# =============================================================================
# T6.22 — Injectable clock deterministic timings
# =============================================================================


def test_T6_22_injectable_clock_deterministic():
    # 6 clock() calls expected (before+after each of 3 layers).
    seq = [0, 5_000_000, 8_000_000, 20_000_000, 25_000_000, 35_000_000]
    it = iter(seq)

    def fake_clock():
        return next(it)

    b_pass = _Spy(result=(ScanDecision.ALLOW, ()))
    c_pass = _Spy(result=(ScanDecision.ALLOW, ()))
    scanner = MnpiLeakageScanner(
        ner=b_pass, llm=c_pass, clock=fake_clock
    )
    r = scanner.scan("clean text")
    assert r.decision is ScanDecision.ALLOW
    assert r.latency_ms_per_layer == {"A": 5, "B": 12, "C": 10}


# =============================================================================
# T6.23 — Public API exports
# =============================================================================


def test_T6_23_public_api_exports():
    import compliance.gap6_mnpi_leakage_scan as g6

    expected = {
        "ScanDecision", "ScanResult",
        "LayerARegexScanner", "PATTERNS",
        "NamedEntityRecognizer", "StubNamedEntityRecognizer",
        "LlmClassifier", "StubLlmClassifier",
        "MnpiLeakageScanner", "ERROR_MESSAGE_RE",
    }
    for name in expected:
        assert hasattr(g6, name), f"missing public export: {name}"


# =============================================================================
# T6.24 — AST import scan
# =============================================================================


_FORBIDDEN_IMPORTS = {
    "openai", "anthropic", "langchain", "langfuse",
    "boto3", "requests", "httpx", "spacy", "transformers",
    # all m*_ modules:
    "m1_identity", "m2_m4_policy_engine", "m3_schema_registry",
    "m5_config_loader", "m6_mcp_gateway", "m7_translators",
    "m8_pipeline_engine", "m9_intent_router", "m10_audit_logger",
    "m11_adapters", "m12_runtime", "m13_fix_bridge",
}


def _gap6_src_files():
    root = (
        Path(__file__).parents[2]
        / "src"
        / "compliance"
        / "gap6_mnpi_leakage_scan"
    )
    return sorted(root.glob("*.py"))


def test_T6_24_no_forbidden_imports_in_gap6_source():
    violations: list[tuple[str, str]] = []
    for path in _gap6_src_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in _FORBIDDEN_IMPORTS:
                        violations.append((str(path), alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    if top in _FORBIDDEN_IMPORTS:
                        violations.append((str(path), node.module))
    assert not violations, f"forbidden imports: {violations}"


# =============================================================================
# T6.25 — No credential-like literals in source
# =============================================================================


_CREDENTIAL_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9]{20,}"),   # OpenAI-style keys
    re.compile(r"\bAKIA[A-Z0-9]{16}"),      # AWS access keys
    re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]{20,}"),
]


def test_T6_25_no_credential_literals_in_source():
    violations: list[tuple[str, str]] = []
    for path in _gap6_src_files():
        source = path.read_text()
        for pattern in _CREDENTIAL_PATTERNS:
            matches = pattern.findall(source)
            for m in matches:
                violations.append((str(path), str(m)))
    assert not violations, f"credential-like literals found: {violations}"


# =============================================================================
# T6.26 — ReDoS: pathological inputs complete fast
# =============================================================================


def test_T6_26_layer_a_redos_a_chars():
    scanner = LayerARegexScanner()
    payload = "a" * 100_000
    start = time.perf_counter()
    decision, codes = scanner.scan(payload)
    elapsed = time.perf_counter() - start
    assert decision is ScanDecision.ALLOW
    assert codes == ()
    # Generous bound for CI variance; 100ms budget per spec.
    assert elapsed < 0.5, f"Layer A took {elapsed:.3f}s on 100K a-chars"


def test_T6_26_layer_a_redos_dash_chars():
    scanner = LayerARegexScanner()
    payload = "-" * 100_000
    start = time.perf_counter()
    decision, codes = scanner.scan(payload)
    elapsed = time.perf_counter() - start
    assert decision is ScanDecision.ALLOW
    assert codes == ()
    assert elapsed < 0.5, f"Layer A took {elapsed:.3f}s on 100K dashes"


# =============================================================================
# T6.27 — Protocol compliance with minimal custom impls
# =============================================================================


class _MinimalNer:
    def scan(self, text: str):
        return ScanDecision.ALLOW, ()


class _MinimalLlm:
    def scan(self, text: str):
        return ScanDecision.ALLOW, ()


def test_T6_27_custom_protocol_impls_compose():
    scanner = MnpiLeakageScanner(ner=_MinimalNer(), llm=_MinimalLlm())
    r = scanner.scan("benign content")
    assert r.decision is ScanDecision.ALLOW
    assert r.layer == "none"


# =============================================================================
# T6.28 — Stub LLM input validation completeness
# =============================================================================


def test_T6_28_stub_llm_none_raises():
    with pytest.raises(TypeError):
        StubLlmClassifier().scan(None)  # type: ignore[arg-type]


def test_T6_28_stub_llm_non_str_raises():
    with pytest.raises(TypeError):
        StubLlmClassifier().scan(3.14)  # type: ignore[arg-type]


def test_T6_28_stub_llm_oversized_raises():
    huge = "a" * (10 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="too large"):
        StubLlmClassifier().scan(huge)
