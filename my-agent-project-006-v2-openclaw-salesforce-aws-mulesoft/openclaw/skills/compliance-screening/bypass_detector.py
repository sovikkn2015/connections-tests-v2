"""
Bypass phrase detector — blocks adversarial queries that attempt to circumvent
compliance, audit, or HITL controls.

v2 steering rule 8: Compliance DENY is a hard stop. No override flag exists.
v2 steering rule 20: Bedrock Guardrail topic 'financial_actions' flags bypass
attempts. This module is the defense-in-depth layer that runs inside the
compliance-screening skill itself, so a guardrail miss still gets caught.

The detector is intentionally coarse. A real compliance team would tune the
phrase list based on actual adversarial samples. This is the starting point.

Returns a structured DENY result that actions.py's _execute_with_gates treats
as a compliance block (writes COMPLIANCE_BLOCKED audit entry, no MuleSoft call,
no HITL prompt shown to human).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Phrases that trigger a hard DENY. Case-insensitive substring match.
# Each phrase is a signal of an attempt to bypass one of the trust controls.
BYPASS_PHRASES: dict[str, str] = {
    # Compliance bypass attempts
    "no compliance check": "attempt to skip compliance pre-check",
    "no compliance needed": "attempt to skip compliance pre-check",
    "bypass compliance": "explicit bypass attempt",
    "skip compliance": "explicit bypass attempt",
    "ignore compliance": "explicit bypass attempt",
    # HITL bypass attempts
    "without approval": "attempt to skip HITL gate",
    "no approval needed": "attempt to skip HITL gate",
    "skip hitl": "explicit HITL bypass attempt",
    "skip approval": "explicit HITL bypass attempt",
    "bypass hitl": "explicit HITL bypass attempt",
    "autopilot": "attempt to invoke non-existent autopilot mode",
    # Audit bypass attempts (FINRA 17a-4 violation territory)
    "don't log": "attempt to skip audit (FINRA 17a-4 violation)",
    "don t log": "attempt to skip audit (FINRA 17a-4 violation)",
    "no logging": "attempt to skip audit (FINRA 17a-4 violation)",
    "without logging": "attempt to skip audit (FINRA 17a-4 violation)",
    "skip audit": "attempt to skip audit (FINRA 17a-4 violation)",
    "bypass audit": "attempt to skip audit (FINRA 17a-4 violation)",
    "delete audit": "attempt to tamper with audit (FINRA 17a-4 violation)",
    "remove audit": "attempt to tamper with audit (FINRA 17a-4 violation)",
    # Timing-based bypass attempts
    "after hours when compliance": "attempt to evade trading-window enforcement",
    "compliance isn t watching": "attempt to evade trading-window enforcement",
    "compliance isn't watching": "attempt to evade trading-window enforcement",
    # MNPI indicators (these may also be caught by _check_mnpi; extra belt)
    "insider tip": "query references potential MNPI",
    "insider info": "query references potential MNPI",
    "heard from their cfo": "query references potential MNPI",
    "heard from their ceo": "query references potential MNPI",
    "inside information": "query references potential MNPI",
    "non-public": "query references potential MNPI",
    "material non-public": "query references potential MNPI",
    # Threshold evasion
    "stay below the threshold": "attempt to structure around reporting threshold",
    "just under 10k": "possible structuring (BSA/AML concern)",
    "keep it under 10000": "possible structuring (BSA/AML concern)",
    "split into multiple": "possible structuring (BSA/AML concern)",
}


@dataclass(frozen=True)
class BypassDetection:
    """Result of scanning a free-text query for bypass attempts."""
    detected: bool
    matched_phrase: str | None
    reason: str | None

    def as_compliance_result(self) -> dict:
        """Shape expected by actions._execute_with_gates (decision + reason)."""
        if self.detected:
            return {
                "decision": "DENY",
                "reason": f"Bypass attempt detected: {self.reason} ('{self.matched_phrase}')",
            }
        return {"decision": "ALLOW", "reason": "No bypass phrases detected"}


def scan_for_bypass(text: str) -> BypassDetection:
    """Scan free-text (query, plan summary, etc.) for bypass phrases.

    Case-insensitive substring match against BYPASS_PHRASES. First match wins.
    Apostrophe variants are normalized before matching.
    """
    if not text:
        return BypassDetection(detected=False, matched_phrase=None, reason=None)

    normalized = text.lower()
    normalized = (
        normalized
        .replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    normalized = re.sub(r"\s+", " ", normalized)

    for phrase, reason in BYPASS_PHRASES.items():
        if phrase in normalized:
            return BypassDetection(detected=True, matched_phrase=phrase, reason=reason)

    return BypassDetection(detected=False, matched_phrase=None, reason=None)


__all__ = ["BYPASS_PHRASES", "BypassDetection", "scan_for_bypass"]
