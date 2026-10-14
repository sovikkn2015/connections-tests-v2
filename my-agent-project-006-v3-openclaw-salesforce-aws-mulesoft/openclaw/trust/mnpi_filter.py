"""MNPI filter — regex + keyword scrubbing of holdings amounts, trade intents, wires.

Applied to any context that would flow to the client-liaison persona or any
user-memory write. Hard-deny on unresolved sentinels — raises MNPIViolation.

Steering rule 21/22: MNPI never reaches the LLM in raw form. Approval-token
plan summaries are human-only; those go through HITL UI, not LLM context.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


class MNPIViolation(Exception):
    """Raised when MNPI scrubbing cannot safely proceed.

    Triggers:
    - An unresolved `[MNPI_RAW]` or similar sentinel tag is present (caller
      violated the boundary contract).
    - Insider-style phrasing detected that regex cannot safely redact.

    Handlers MUST fail-closed: reject the agent turn, write audit row, never
    pass this content to an LLM.
    """

    def __init__(self, reason: str, sample: str = "") -> None:
        self.reason = reason
        self.sample = sample[:120]
        super().__init__(f"mnpi_violation: {reason}")


@dataclass
class MNPIFilterReport:
    """What the filter did, without containing the raw content itself."""

    redactions: Dict[str, int] = field(default_factory=dict)
    sentinels_detected: List[str] = field(default_factory=list)

    def record(self, kind: str, count: int = 1) -> None:
        self.redactions[kind] = self.redactions.get(kind, 0) + count

    @property
    def any_redaction(self) -> bool:
        return sum(self.redactions.values()) > 0 or bool(self.sentinels_detected)


_DOLLAR = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?\s?[KMB]?", re.IGNORECASE)
_SHARES = re.compile(
    r"\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\s+(shares?|contracts?)\b", re.IGNORECASE
)
_SHARES_BARE = re.compile(r"\b\d{2,}\s+(shares?|contracts?)\b", re.IGNORECASE)
_WIRE_INSTRUCTION = re.compile(
    r"\b(wire|transfer|ach|swift)\b[^.\n]{0,60}?\b(to|from)\b[^.\n]{0,80}",
    re.IGNORECASE,
)

_SENTINELS = ["[MNPI_RAW]", "[MNPI]", "[INSIDER]", "{{MNPI}}"]

_INSIDER_HINTS = re.compile(
    r"\b(about\s+to\s+(buy|sell|report)|before\s+announcement|unpublished|"
    r"material\s+non-public|insider\s+tip)\b",
    re.IGNORECASE,
)


class MNPIFilter:
    """Scrub MNPI from a text payload. Hard-deny on unresolved sentinels."""

    def __init__(self, *, strict: bool = True) -> None:
        """
        Args:
            strict: when True (default), insider-style phrasing raises
                MNPIViolation. When False, such phrasing is redacted but the
                call continues. Production paths (client-liaison, user-memory
                writes) MUST use strict=True.
        """
        self.strict = strict

    def scrub_text(self, text: str) -> Tuple[str, MNPIFilterReport]:
        """Scrub a single text payload. Raises MNPIViolation on hard-deny."""
        if text is None:
            return "", MNPIFilterReport()

        report = MNPIFilterReport()

        for tag in _SENTINELS:
            if tag in text:
                report.sentinels_detected.append(tag)
        if report.sentinels_detected:
            raise MNPIViolation(
                reason=f"sentinel(s) {report.sentinels_detected!r} reached filter",
                sample=text,
            )

        if _INSIDER_HINTS.search(text):
            if self.strict:
                raise MNPIViolation(
                    reason="insider-style phrasing detected", sample=text
                )
            text = _INSIDER_HINTS.sub("[INSIDER_REDACTED]", text)
            report.record("insider_hint")

        def _dollar_sub(m: re.Match) -> str:
            report.record("dollar")
            return "[$REDACTED]"

        text = _DOLLAR.sub(_dollar_sub, text)

        def _shares_sub(m: re.Match) -> str:
            report.record("shares")
            return "[SHARES_REDACTED]"

        text = _SHARES.sub(_shares_sub, text)
        text = _SHARES_BARE.sub(_shares_sub, text)

        def _wire_sub(m: re.Match) -> str:
            report.record("wire")
            return "[WIRE_REDACTED]"

        text = _WIRE_INSTRUCTION.sub(_wire_sub, text)
        return text, report

    def scrub_object(
        self, obj: Any, *, path: str = "$"
    ) -> Tuple[Any, MNPIFilterReport]:
        """Recursively scrub a dict/list. Keys preserved; values scrubbed."""
        if isinstance(obj, str):
            return self.scrub_text(obj)
        if isinstance(obj, dict):
            combined = MNPIFilterReport()
            out: Dict[Any, Any] = {}
            for k, v in obj.items():
                scrubbed_v, child_report = self.scrub_object(v, path=f"{path}.{k}")
                out[k] = scrubbed_v
                for kind, n in child_report.redactions.items():
                    combined.record(kind, n)
                combined.sentinels_detected.extend(child_report.sentinels_detected)
            return out, combined
        if isinstance(obj, list):
            combined = MNPIFilterReport()
            out_list = []
            for i, v in enumerate(obj):
                scrubbed_v, child_report = self.scrub_object(v, path=f"{path}[{i}]")
                out_list.append(scrubbed_v)
                for kind, n in child_report.redactions.items():
                    combined.record(kind, n)
                combined.sentinels_detected.extend(child_report.sentinels_detected)
            return out_list, combined
        return obj, MNPIFilterReport()
