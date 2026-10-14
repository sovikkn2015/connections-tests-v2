"""
Gap 6 — Internal shared types.

Defines `ScanDecision` (imported by all three layer files + scanner).
Kept in a separate module to avoid circular imports.
"""

from __future__ import annotations

from enum import Enum


class ScanDecision(str, Enum):
    """Binary scan decision. DENY is terminal — no partial delivery."""

    ALLOW = "ALLOW"
    DENY = "DENY"


__all__ = ["ScanDecision"]
