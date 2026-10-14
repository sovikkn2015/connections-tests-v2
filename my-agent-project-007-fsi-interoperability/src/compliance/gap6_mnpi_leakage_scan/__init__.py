"""
Gap 6 — MNPI Leakage Scan — Public API.

Parent module: M6 (MCP Gateway).

3-layer output guardrail scanning agent outputs (LLM responses +
structured results) for MNPI and PII leakage BEFORE they leave M6.
Distinct from M4 (which filters INPUTS to the LLM).

Phase 1: Layer A fully implemented (regex). Layers B and C are stubs
behind Protocols. Phase 2 swaps Bedrock Haiku into Layer C, spaCy into
Layer B, without touching Gap 6 internals.

Fail-closed: any layer DENY -> scanner DENY. Any layer exception ->
scanner DENY.

Usage:
    from compliance.gap6_mnpi_leakage_scan import (
        MnpiLeakageScanner, ScanDecision,
    )

    scanner = MnpiLeakageScanner()
    result = scanner.scan(llm_output_text)
    if result.decision is ScanDecision.DENY:
        audit_and_block(result.layer, result.match_codes)
    else:
        deliver(llm_output_text)

See `.kiro/specs/gap6-mnpi-leakage-scan.md` for the full contract.
"""

from __future__ import annotations

from compliance.gap6_mnpi_leakage_scan._types import ScanDecision
from compliance.gap6_mnpi_leakage_scan.layer_a_regex import (
    LayerARegexScanner,
    PATTERNS,
)
from compliance.gap6_mnpi_leakage_scan.layer_b_ner import (
    NamedEntityRecognizer,
    StubNamedEntityRecognizer,
)
from compliance.gap6_mnpi_leakage_scan.layer_c_llm import (
    LlmClassifier,
    StubLlmClassifier,
)
from compliance.gap6_mnpi_leakage_scan.scanner import (
    ERROR_MESSAGE_RE,
    MnpiLeakageScanner,
    ScanResult,
)

__all__ = [
    # Decision + Result
    "ScanDecision",
    "ScanResult",
    # Layer A
    "LayerARegexScanner",
    "PATTERNS",
    # Layer B
    "NamedEntityRecognizer",
    "StubNamedEntityRecognizer",
    # Layer C
    "LlmClassifier",
    "StubLlmClassifier",
    # Scanner
    "MnpiLeakageScanner",
    "ERROR_MESSAGE_RE",
]
