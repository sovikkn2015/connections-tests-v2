"""
Gap 6 — MnpiLeakageScanner.

Composes Layer A (regex) + Layer B (NER) + Layer C (LLM classifier)
into a fail-closed 3-layer output guardrail. Short-circuits on first
DENY. Any layer raising -> scanner returns DENY with layer="error".

Clock is injectable for deterministic latency tests.

See `.kiro/specs/gap6-mnpi-leakage-scan.md` R5 for the contract.
"""

from __future__ import annotations

import re
import time
from typing import Callable, Optional

from pydantic import BaseModel, ConfigDict, Field

from compliance.gap6_mnpi_leakage_scan._types import ScanDecision
from compliance.gap6_mnpi_leakage_scan.layer_a_regex import (
    LayerARegexScanner,
)
from compliance.gap6_mnpi_leakage_scan.layer_b_ner import (
    NamedEntityRecognizer,
    StubNamedEntityRecognizer,
)
from compliance.gap6_mnpi_leakage_scan.layer_c_llm import (
    LlmClassifier,
    StubLlmClassifier,
)


_MAX_INPUT_BYTES = 10 * 1024 * 1024


# =============================================================================
# ScanResult (spec R1.2).
# =============================================================================


ERROR_MESSAGE_RE = re.compile(r"^layer_[abc]:[A-Za-z_][A-Za-z0-9_]*$")


class ScanResult(BaseModel):
    """Frozen result of a full scanner pass."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: ScanDecision
    # "A" | "B" | "C" | "none" | "error"
    layer: str
    match_codes: tuple[str, ...] = ()
    latency_ms_per_layer: dict[str, int] = Field(default_factory=dict)
    error_message: Optional[str] = Field(default=None, max_length=200)


# =============================================================================
# Clock (spec R5.5).
# =============================================================================


def _default_clock() -> int:
    """Return monotonic nanoseconds. Overridable in tests."""
    return time.monotonic_ns()


# =============================================================================
# Scanner (spec R5).
# =============================================================================


class MnpiLeakageScanner:
    """3-layer fail-closed output guardrail.

    Layers run sequentially A -> B -> C. Short-circuit on first DENY.
    Any layer raising -> scanner returns a DENY ScanResult with
    layer="error".

    Never logs the input text. error_message contains ONLY a layer
    code + exception class name (never str(exc) / repr(exc)).
    """

    _MAX_BYTES = _MAX_INPUT_BYTES

    def __init__(
        self,
        *,
        layer_a: Optional[LayerARegexScanner] = None,
        ner: Optional[NamedEntityRecognizer] = None,
        llm: Optional[LlmClassifier] = None,
        clock: Optional[Callable[[], int]] = None,
    ):
        self._a = layer_a or LayerARegexScanner()
        self._b = ner or StubNamedEntityRecognizer()
        self._c = llm or StubLlmClassifier()
        self._clock = clock or _default_clock

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def scan(self, text: str) -> ScanResult:
        """Scan `text` through A -> B -> C, returning a ScanResult.

        Input validation:
            - None -> TypeError (strict; unified with Layer A).
            - non-str -> TypeError.
            - >10MB -> ValueError.
            - "" -> ALLOW, layer="none", empty timings.
        """
        if text is None:
            raise TypeError("text must be str (not None)")
        if not isinstance(text, str):
            raise TypeError("text must be str")
        if len(text.encode("utf-8")) > self._MAX_BYTES:
            raise ValueError("input too large for mnpi scan")

        if text == "":
            return ScanResult(
                decision=ScanDecision.ALLOW,
                layer="none",
                match_codes=(),
                latency_ms_per_layer={},
            )

        timings: dict[str, int] = {}

        layers: tuple[tuple[str, object], ...] = (
            ("A", self._a),
            ("B", self._b),
            ("C", self._c),
        )

        for letter, impl in layers:
            try:
                t0 = self._clock()
                dec, matches = impl.scan(text)  # type: ignore[attr-defined]
                elapsed_ms = max(
                    0, (self._clock() - t0) // 1_000_000
                )
                timings[letter] = elapsed_ms
            except Exception as exc:
                # Fail-closed. Never re-raise; never expose exc message.
                return ScanResult(
                    decision=ScanDecision.DENY,
                    layer="error",
                    match_codes=(),
                    latency_ms_per_layer=dict(timings),
                    error_message=(
                        f"layer_{letter.lower()}:{type(exc).__name__}"
                    ),
                )
            if dec is ScanDecision.DENY:
                return ScanResult(
                    decision=dec,
                    layer=letter,
                    match_codes=matches,
                    latency_ms_per_layer=dict(timings),
                )

        return ScanResult(
            decision=ScanDecision.ALLOW,
            layer="none",
            match_codes=(),
            latency_ms_per_layer=dict(timings),
        )


__all__ = [
    "MnpiLeakageScanner",
    "ScanResult",
    "ERROR_MESSAGE_RE",
]
