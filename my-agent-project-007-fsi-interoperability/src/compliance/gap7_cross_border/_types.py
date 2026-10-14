"""
Gap 7 — Cross-Border Enforcement — internal types.

See .kiro/specs/gap7-cross-border.md R1..R8.
"""

from __future__ import annotations

from enum import Enum

EGRESS_DECISION_SCHEMA_VERSION = "1.0.0"


# =============================================================================
# GDPR Art. 6(1) lawful bases — R2.1
# =============================================================================


class GDPRLawfulBasis(str, Enum):
    consent = "consent"
    contract = "contract"
    legal_obligation = "legal_obligation"
    vital_interests = "vital_interests"
    public_task = "public_task"
    legitimate_interests = "legitimate_interests"


# =============================================================================
# MiFID II client classification — R3.1
# =============================================================================


class MiFIDClientClassification(str, Enum):
    retail = "retail"
    professional = "professional"
    eligible_counterparty = "eligible_counterparty"


# =============================================================================
# Gap 7 allowed wsp_section vocabulary — R7.2
# =============================================================================

ALLOWED_WSP_SECTIONS: frozenset[str] = frozenset(
    {
        "MiFID II Art. 25(2)",
        "MiFID II Art. 25(3)",
        "MiFID II Art. 27",
        "GDPR Art. 6(1)(a)",
        "GDPR Art. 6(1)(b)",
        "GDPR Art. 6(1)(c)",
        "GDPR Art. 6(1)(d)",
        "GDPR Art. 6(1)(e)",
        "GDPR Art. 6(1)(f)",
        "GDPR Art. 17(3)(b)",
        "GDPR Art. 46",
        "MAS Notice 626 §9",
        "SFC Code of Conduct §5.1A",
        "SFC Part XIVA",
        "FCA Consumer Duty PRIN 2A",
        "Reg BI §15l-1",
        "17 CFR §240.17a-4(e)(5)",
    }
)


# =============================================================================
# Errors
# =============================================================================


class UndefinedJurisdictionPair(ValueError):
    """Raised by `matrix_lookup` on any (primary, residency) not in the matrix.

    Gap 7 is fail-closed: the egress gate catches this and emits DENY
    with rule_id `gap7.matrix.undefined_pair`. Tests assert both paths.
    """


class RegoManifestError(ValueError):
    """Raised when opa-bundles/jurisdiction/manifest.json fails R7 validation."""


class AuditWriteFailed(RuntimeError):
    """Same semantics as Gap 5 — fail-closed on audit-sink raise."""

    def __init__(self, reason: str = "audit_write_failed") -> None:
        if reason != "audit_write_failed":
            raise ValueError(
                "AuditWriteFailed.reason must be 'audit_write_failed'"
            )
        super().__init__(reason)
        self.reason = reason
