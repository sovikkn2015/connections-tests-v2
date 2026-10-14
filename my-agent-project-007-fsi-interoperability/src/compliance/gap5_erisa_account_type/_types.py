"""
Gap 5 — ERISA Account-Type Gating — internal types.

See .kiro/specs/gap5-erisa-account-type.md R1, R2, R6.
"""

from __future__ import annotations

from enum import Enum

ACCOUNT_TYPE_DECISION_SCHEMA_VERSION = "1.0.0"


class AccountType(str, Enum):
    """16 canonical account types (ARCH-06 §5.2).

    Enum *names* are Python identifiers; enum *values* are the
    regulatory names. Tests cover all 16 × matrix permutations.
    """

    taxable_brokerage = "taxable_brokerage"
    traditional_ira = "traditional_ira"
    roth_ira = "roth_ira"
    sep_ira = "sep_ira"
    simple_ira = "simple_ira"
    k401 = "401k"
    k403b = "403b"
    k457 = "457"
    erisa_pension = "erisa_pension"
    erisa_profit_sharing = "erisa_profit_sharing"
    trust_revocable = "trust_revocable"
    trust_irrevocable = "trust_irrevocable"
    custodial_utma = "custodial_utma"
    custodial_ugma = "custodial_ugma"
    account_529 = "529"
    hsa = "hsa"


class Outcome(str, Enum):
    """R2.2 — ALLOW / BLOCK / REQUIRE_ENHANCED_DOC."""

    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REQUIRE_ENHANCED_DOC = "REQUIRE_ENHANCED_DOC"


# =============================================================================
# Allowed wsp_section vocabulary (R6.2)
# =============================================================================

ALLOWED_WSP_SECTIONS: frozenset[str] = frozenset(
    {
        "ERISA Policy §404(a)(1)(B)",
        "ERISA Policy §406",
        "ERISA Policy §PTE 2020-02(b)",
        "ERISA Policy §PTE 2020-02(e)",
        "ERISA Policy §IRC 4975",
    }
)


# =============================================================================
# Errors
# =============================================================================


class RegoManifestError(ValueError):
    """Raised when opa-bundles/account-type/manifest.json fails R6 validation."""


class AuditWriteFailed(RuntimeError):
    """Raised when the injected `AuditClient.write(...)` raises.

    `reason` is always `"audit_write_failed"` and `str(exc) == reason`.
    No PII, no stack trace propagated through.
    """

    def __init__(self, reason: str = "audit_write_failed") -> None:
        if reason != "audit_write_failed":
            raise ValueError(
                "AuditWriteFailed.reason must be 'audit_write_failed'"
            )
        super().__init__(reason)
        self.reason = reason
